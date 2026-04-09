import csv
import io
import os
import re
import zipfile
from collections import defaultdict

from odoo import http
from odoo.http import request


class ShopifyInventoryDashboardController(http.Controller):
    @http.route("/shopify_inventory_dashboard/data", type="json", auth="user")
    def get_dashboard_data(self, threshold=5.0):
        env = request.env
        threshold = float(threshold or 0.0)

        products = env["product.product"].sudo().search([("product_tmpl_id.is_storable", "=", True)])
        product_ids = products.ids
        loc_ids = env["stock.location"].sudo().search([("usage", "=", "internal")]).ids

        qty_map = {}
        if product_ids and loc_ids:
            qty_map = defaultdict(float)
            quant_rows = env["stock.quant"].sudo().search_read(
                [("product_id", "in", product_ids), ("location_id", "in", loc_ids)],
                ["product_id", "quantity"],
                limit=200000,
            )
            for row in quant_rows:
                product = row.get("product_id")
                if not product:
                    continue
                qty_map[product[0]] += float(row.get("quantity", 0.0) or 0.0)

        total = len(product_ids)
        in_stock = 0
        out_of_stock = 0
        low_stock = 0
        total_qty = 0.0
        low_lines = []
        out_lines = []

        for product in products:
            qty = float(qty_map.get(product.id, 0.0))
            total_qty += qty
            if qty <= 0:
                out_of_stock += 1
                out_lines.append(
                    {
                        "id": product.id,
                        "name": product.display_name,
                        "sku": product.default_code or "",
                        "qty": 0.0,
                    }
                )
            else:
                in_stock += 1
                if qty <= threshold:
                    low_stock += 1
                    low_lines.append(
                        {
                            "id": product.id,
                            "name": product.display_name,
                            "sku": product.default_code or "",
                            "qty": round(qty, 4),
                        }
                    )

        low_lines = sorted(low_lines, key=lambda x: x["qty"])[:150]
        out_lines = sorted(out_lines, key=lambda x: x["name"])[:150]

        issue_rows = []
        score = None
        dashboard = env["shopify.sync.dashboard"].sudo().search([], limit=1)
        if dashboard:
            score = dashboard.inventory_score
            issues = env["shopify.sync.issue"].sudo().search(
                [("dashboard_id", "=", dashboard.id), ("issue_type", "=", "inventory")], limit=150
            )
            issue_rows = [
                {
                    "id": issue.id,
                    "status": issue.status,
                    "ref": issue.external_ref or "",
                    "name": issue.name or "",
                    "details": issue.details or "",
                    "expected_value": issue.expected_value or "",
                    "current_value": issue.current_value or "",
                    "auto_fix_available": bool(issue.is_auto_fix_available),
                }
                for issue in issues
            ]

        return {
            "kpis": {
                "total_products": total,
                "in_stock_products": in_stock,
                "out_of_stock_products": out_of_stock,
                "low_stock_products": low_stock,
                "total_qty": round(total_qty, 2),
                "threshold": threshold,
                "inventory_sync_score": score if score is not None else 0.0,
            },
            "low_stock_lines": low_lines,
            "out_of_stock_lines": out_lines,
            "inventory_issues": issue_rows,
        }

    @http.route("/shopify_inventory_dashboard/reconcile", type="json", auth="user")
    def reconcile_inventory(self, apply=False):
        env = request.env
        dashboard = env["shopify.sync.dashboard"].sudo().search([], limit=1)
        if not dashboard:
            return {"error": "No Shopify Sync dashboard found."}

        rows = self._load_inventory_rows_from_export_folder(dashboard.export_folder)
        if not rows:
            return {"error": "No inventory rows found in export folder."}

        sku_qty_map = {}
        sku_loc_map = {}
        for row in rows:
            sku = (row.get("SKU") or "").strip()
            if not sku:
                continue
            qty = self._qty_from_row(row)
            if qty is None:
                continue
            sku_qty_map[sku] = qty
            sku_loc_map[sku] = (row.get("Location") or "").strip()

        if not sku_qty_map:
            return {"error": "No usable SKU/quantity rows found in inventory sheet."}

        skus = list(sku_qty_map.keys())
        products = env["product.product"].sudo().search([("default_code", "in", skus)])
        product_map = {p.default_code: p for p in products}

        all_locs = env["stock.location"].sudo().search([("usage", "=", "internal")])
        loc_map = self._build_location_map(all_locs)
        fallback_loc = self._fallback_location(env)

        summary = {
            "sheet_skus": len(sku_qty_map),
            "matched_skus": 0,
            "missing_skus": 0,
            "qty_match": 0,
            "qty_mismatch": 0,
            "increase_units": 0.0,
            "decrease_units": 0.0,
            "required_space_m3": 0.0,
            "applied_updates": 0,
            "applied_skipped": 0,
        }
        lines = []
        quant_model = env["stock.quant"].sudo()

        for sku, target_qty in sku_qty_map.items():
            product = product_map.get(sku)
            if not product:
                summary["missing_skus"] += 1
                continue
            summary["matched_skus"] += 1

            location_name = sku_loc_map.get(sku) or ""
            location = self._resolve_location(location_name, loc_map, fallback_loc)
            if not location:
                summary["applied_skipped"] += 1
                continue

            quant = quant_model.search(
                [
                    ("product_id", "=", product.id),
                    ("location_id", "=", location.id),
                    ("company_id", "=", env.company.id),
                ],
                limit=1,
            )
            current_qty = float(quant.quantity if quant else 0.0)
            diff = round(target_qty - current_qty, 4)
            is_match = abs(diff) < 0.0001
            if is_match:
                summary["qty_match"] += 1
            else:
                summary["qty_mismatch"] += 1
                if diff > 0:
                    summary["increase_units"] += diff
                    unit_vol = float(product.product_tmpl_id.volume or 0.0)
                    summary["required_space_m3"] += diff * unit_vol
                else:
                    summary["decrease_units"] += abs(diff)

            if apply and not is_match:
                if not quant:
                    quant = quant_model.create(
                        {
                            "product_id": product.id,
                            "location_id": location.id,
                            "company_id": env.company.id,
                            "inventory_quantity": target_qty,
                        }
                    )
                else:
                    quant.write({"inventory_quantity": target_qty})
                quant.action_apply_inventory()
                summary["applied_updates"] += 1

            if not is_match and len(lines) < 200:
                lines.append(
                    {
                        "sku": sku,
                        "product": product.display_name,
                        "current_qty": round(current_qty, 4),
                        "target_qty": round(target_qty, 4),
                        "delta_qty": diff,
                        "location": location_name,
                        "unit_volume_m3": round(float(product.product_tmpl_id.volume or 0.0), 6),
                    }
                )

        summary["increase_units"] = round(summary["increase_units"], 4)
        summary["decrease_units"] = round(summary["decrease_units"], 4)
        summary["required_space_m3"] = round(summary["required_space_m3"], 4)
        summary["sync_percent"] = round(
            (summary["qty_match"] / summary["matched_skus"] * 100.0) if summary["matched_skus"] else 0.0, 2
        )
        return {"summary": summary, "lines": lines}

    @http.route("/shopify_inventory_dashboard/fix_issue", type="json", auth="user")
    def fix_inventory_issue(self, issue_id=None):
        if not issue_id:
            return {"ok": False, "message": "Missing issue id."}

        issue = request.env["shopify.sync.issue"].sudo().browse(int(issue_id))
        if not issue.exists():
            return {"ok": False, "message": "Issue not found."}
        if issue.issue_type != "inventory":
            return {"ok": False, "message": "Only inventory issues can be fixed from this dashboard."}
        if not issue.is_auto_fix_available:
            return {"ok": False, "message": "No automated fix available for this issue."}

        ref = issue.external_ref or ""
        dashboard = issue.dashboard_id
        fixed = bool(issue._apply_automated_fix())
        if fixed and dashboard:
            dashboard.action_run_health_check()
            return {"ok": True, "message": f"Synced {ref} from sheet to Odoo quantity."}
        return {"ok": False, "message": "Fix skipped. Could not find valid sheet row/SKU/location."}

    def _load_inventory_rows_from_export_folder(self, folder):
        if not folder or not os.path.isdir(folder):
            return []
        patterns = [re.compile(r"^inventory_export.*\.csv$", re.I), re.compile(r"^inventory.*\.csv$", re.I)]
        candidates = []
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath):
                continue
            if any(p.match(fname) for p in patterns):
                candidates.append((os.path.getmtime(fpath), fpath))
        if not candidates:
            return []
        latest = sorted(candidates, key=lambda x: x[0])[-1][1]
        with open(latest, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def _qty_from_row(self, row):
        for key in ("On hand (new)", "On hand (current)"):
            raw = (row.get(key) or "").strip()
            if not raw:
                continue
            if raw.lower() in {"not stocked", "na", "n/a", "-"}:
                return None
            try:
                return float(raw)
            except Exception:
                continue
        return None

    def _normalize_location_key(self, value):
        return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())

    def _build_location_map(self, locations):
        mapping = {}
        for loc in locations:
            for key in {loc.name or "", loc.complete_name or ""}:
                nkey = self._normalize_location_key(key)
                if nkey and nkey not in mapping:
                    mapping[nkey] = loc
        return mapping

    def _fallback_location(self, env):
        warehouse = env["stock.warehouse"].sudo().search([("company_id", "=", env.company.id)], limit=1)
        if warehouse and warehouse.lot_stock_id and warehouse.lot_stock_id.usage == "internal":
            return warehouse.lot_stock_id
        return env["stock.location"].sudo().search(
            [("usage", "=", "internal"), ("company_id", "in", [env.company.id, False])], limit=1
        )

    def _resolve_location(self, location_name, loc_map, fallback):
        nkey = self._normalize_location_key(location_name)
        if nkey and nkey in loc_map:
            return loc_map[nkey]

        alias_candidates = []
        if "warehouselevel1" in nkey or "level1" in nkey or "lvl1" in nkey:
            alias_candidates.extend(("lvl1stock", "level1stock", "lvl1"))
        if "tynoraustralia" in nkey:
            alias_candidates.extend(("whgrstock", "whgr", "whstock", "stock"))
        if "whgr" in nkey:
            alias_candidates.extend(("whgrstock", "whgr"))

        for alias in alias_candidates:
            if alias in loc_map:
                return loc_map[alias]
        for alias in alias_candidates:
            for key, loc in loc_map.items():
                if alias in key:
                    return loc

        if nkey:
            return False
        return fallback
