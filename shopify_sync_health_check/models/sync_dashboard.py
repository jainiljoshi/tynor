import base64
import csv
import io
import math
import os
import re
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

from odoo import api, fields, models
from odoo.exceptions import UserError


SHEET_TYPES = [
    ("customers", "Customers"),
    ("products", "Products"),
    ("inventory", "Inventory"),
    ("orders", "Orders"),
]

SHEET_PATTERNS = {
    "customers": [r"^customers_export.*\.zip$", r"^customers.*\.zip$"],
    "products": [r"^products_export.*\.csv$", r"^products.*\.csv$"],
    "inventory": [r"^inventory_export.*\.csv$", r"^inventory.*\.csv$"],
    "orders": [r"^orders_export.*\.zip$", r"^orders.*\.zip$", r"^orders_export.*\.csv$", r"^orders.*\.csv$"],
}


class ShopifySyncDashboard(models.Model):
    _name = "shopify.sync.dashboard"
    _description = "Shopify Sync Health Dashboard"

    name = fields.Char(default="Shopify Sync Health", required=True)
    export_folder = fields.Char(
        default="/Users/jainiljoshi/workspace/odoo/19.2/custom/exported data",
        required=True,
    )
    active = fields.Boolean(default=True)
    last_check_at = fields.Datetime(readonly=True)

    sheet_ids = fields.One2many("shopify.sync.sheet", "dashboard_id", string="Sheets")
    issue_ids = fields.One2many("shopify.sync.issue", "dashboard_id", string="Issues")
    issue_count = fields.Integer(compute="_compute_issue_count")

    customer_total = fields.Integer(default=0, readonly=True)
    customer_correct = fields.Integer(default=0, readonly=True)
    customer_partial = fields.Integer(default=0, readonly=True)
    customer_false = fields.Integer(default=0, readonly=True)
    customer_score = fields.Float(compute="_compute_scores", store=False)

    product_total = fields.Integer(default=0, readonly=True)
    product_correct = fields.Integer(default=0, readonly=True)
    product_partial = fields.Integer(default=0, readonly=True)
    product_false = fields.Integer(default=0, readonly=True)
    product_score = fields.Float(compute="_compute_scores", store=False)

    inventory_total = fields.Integer(default=0, readonly=True)
    inventory_correct = fields.Integer(default=0, readonly=True)
    inventory_partial = fields.Integer(default=0, readonly=True)
    inventory_false = fields.Integer(default=0, readonly=True)
    inventory_score = fields.Float(compute="_compute_scores", store=False)

    order_total = fields.Integer(default=0, readonly=True)
    order_correct = fields.Integer(default=0, readonly=True)
    order_partial = fields.Integer(default=0, readonly=True)
    order_false = fields.Integer(default=0, readonly=True)
    order_score = fields.Float(compute="_compute_scores", store=False)

    low_stock_threshold = fields.Float(default=5.0)
    inv_kpi_total_products = fields.Integer(default=0, readonly=True)
    inv_kpi_in_stock_products = fields.Integer(default=0, readonly=True)
    inv_kpi_out_of_stock_products = fields.Integer(default=0, readonly=True)
    inv_kpi_low_stock_products = fields.Integer(default=0, readonly=True)
    inv_kpi_total_qty = fields.Float(default=0.0, readonly=True)
    inventory_kpi_line_ids = fields.One2many(
        "shopify.inventory.kpi.line", "dashboard_id", string="Low Stock Products", readonly=True
    )

    overall_score = fields.Float(compute="_compute_scores", store=False)

    @api.depends("issue_ids")
    def _compute_issue_count(self):
        for rec in self:
            rec.issue_count = len(rec.issue_ids)

    @api.depends(
        "customer_total",
        "customer_correct",
        "customer_partial",
        "product_total",
        "product_correct",
        "product_partial",
        "inventory_total",
        "inventory_correct",
        "inventory_partial",
        "order_total",
        "order_correct",
        "order_partial",
    )
    def _compute_scores(self):
        for rec in self:
            rec.customer_score = rec._calc_score(rec.customer_total, rec.customer_correct, rec.customer_partial)
            rec.product_score = rec._calc_score(rec.product_total, rec.product_correct, rec.product_partial)
            rec.inventory_score = rec._calc_score(rec.inventory_total, rec.inventory_correct, rec.inventory_partial)
            rec.order_score = rec._calc_score(rec.order_total, rec.order_correct, rec.order_partial)
            totals = rec.customer_total + rec.product_total + rec.inventory_total + rec.order_total
            corrects = rec.customer_correct + rec.product_correct + rec.inventory_correct + rec.order_correct
            partials = rec.customer_partial + rec.product_partial + rec.inventory_partial + rec.order_partial
            rec.overall_score = rec._calc_score(totals, corrects, partials)

    def _calc_score(self, total, correct, partial):
        if not total:
            return 0.0
        return round(((correct + (0.5 * partial)) / total) * 100.0, 2)

    def action_refresh_sheets(self):
        self.ensure_one()
        folder = self.export_folder
        if not folder or not os.path.isdir(folder):
            raise UserError(f"Export folder not found: {folder}")

        self._ensure_sheet_rows()

        for sheet_type, _label in SHEET_TYPES:
            patterns = [re.compile(p, re.IGNORECASE) for p in SHEET_PATTERNS[sheet_type]]
            candidates = []
            for fname in os.listdir(folder):
                fpath = os.path.join(folder, fname)
                if not os.path.isfile(fpath):
                    continue
                if any(p.match(fname) for p in patterns):
                    candidates.append((os.path.getmtime(fpath), fname, fpath))

            latest = max(candidates, key=lambda x: x[0]) if candidates else None
            existing = self.sheet_ids.filtered(lambda s: s.sheet_type == sheet_type)
            use_all = bool(existing[:1].use_all_matching_files) if existing else False

            if latest:
                mtime, fname, fpath = latest
                row_count = self._sheet_row_count(sheet_type, fpath)
                file_name = fname
                size_bytes = os.path.getsize(fpath)
                if sheet_type == "orders" and use_all and candidates:
                    row_count = 0
                    size_bytes = 0
                    for _m, _fn, _fp in candidates:
                        row_count += self._sheet_row_count(sheet_type, _fp)
                        size_bytes += os.path.getsize(_fp)
                    if len(candidates) > 1:
                        file_name = f"{fname} (+{len(candidates)-1} more)"
                vals = {
                    "dashboard_id": self.id,
                    "sheet_type": sheet_type,
                    "file_name": file_name,
                    "file_path": fpath,
                    "file_mtime": datetime.fromtimestamp(mtime),
                    "row_count": row_count,
                    "size_bytes": size_bytes,
                    "status": "available",
                }
                if existing:
                    existing.sorted("id", reverse=True)[0].write(vals)
                    if len(existing) > 1:
                        existing.sorted("id")[:-1].unlink()
                else:
                    self.env["shopify.sync.sheet"].create(vals)
            else:
                if existing:
                    keep = existing.sorted("id", reverse=True)[0]
                    keep.write({"status": "missing"})
                    if len(existing) > 1:
                        existing.sorted("id")[:-1].unlink()

        return True

    def action_run_health_check(self):
        self.ensure_one()
        self.action_refresh_sheets()
        self.issue_ids.unlink()

        customers = self._health_check_customers()
        products = self._health_check_products()
        inventory = self._health_check_inventory()
        orders = self._health_check_orders()

        self.write(
            {
                "last_check_at": fields.Datetime.now(),
                "customer_total": customers["total"],
                "customer_correct": customers["correct"],
                "customer_partial": customers["partial"],
                "customer_false": customers["false"],
                "product_total": products["total"],
                "product_correct": products["correct"],
                "product_partial": products["partial"],
                "product_false": products["false"],
                "inventory_total": inventory["total"],
                "inventory_correct": inventory["correct"],
                "inventory_partial": inventory["partial"],
                "inventory_false": inventory["false"],
                "order_total": orders["total"],
                "order_correct": orders["correct"],
                "order_partial": orders["partial"],
                "order_false": orders["false"],
            }
        )
        self.action_refresh_inventory_dashboard()
        return True

    def action_open_issues(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Sync Issues",
            "res_model": "shopify.sync.issue",
            "view_mode": "list,form",
            "domain": [("dashboard_id", "=", self.id)],
            "context": {"default_dashboard_id": self.id},
        }

    def action_import_customers(self):
        self.ensure_one()
        rows = self._load_customers_rows()
        emails = []
        for r in rows:
            email = (r.get("Email") or "").strip().lower()
            if email:
                emails.append(email)
        partner_model = self.env["res.partner"].sudo()
        existing = partner_model.search_read([("email", "in", list(set(emails)))], ["email"])
        existing_set = {(p.get("email") or "").strip().lower() for p in existing if p.get("email")}

        create_vals = []
        for r in rows:
            email = (r.get("Email") or "").strip().lower()
            if not email or email in existing_set:
                continue
            first = (r.get("First Name") or "").strip()
            last = (r.get("Last Name") or "").strip()
            name = (f"{first} {last}").strip() or "Unnamed Customer"
            phone = (r.get("Phone") or "").strip() or (r.get("Default Address Phone") or "").strip()
            create_vals.append(
                {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "street": (r.get("Default Address Address1") or "").strip(),
                    "street2": (r.get("Default Address Address2") or "").strip(),
                    "city": (r.get("Default Address City") or "").strip(),
                    "zip": (r.get("Default Address Zip") or "").strip(),
                }
            )
        if create_vals:
            partner_model.create(create_vals)

        self.action_run_health_check()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Customers Imported",
                "message": f"Created {len(create_vals)} customers.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_import_products(self):
        self.ensure_one()
        handle_images, handle_skus = self._parse_products_sheet()
        handle_template_map, _ambiguous = self._build_handle_template_map(handle_skus)

        created = 0
        set_main = 0
        product_image_model = self.env["product.image"].sudo()
        template_model = self.env["product.template"].sudo()

        for handle, tmpl_id in handle_template_map.items():
            images = handle_images.get(handle, [])
            if not images:
                continue

            tmpl = template_model.browse(tmpl_id)
            existing_images = product_image_model.search([("product_tmpl_id", "=", tmpl_id)])
            existing_names = set(existing_images.mapped("name"))
            existing_sequences = set(existing_images.mapped("sequence"))

            for idx, meta in enumerate(images, start=1):
                seq = meta["position"] if meta["position"] != 9999 else idx
                name = meta["alt"] or meta["url"]
                if name in existing_names or seq in existing_sequences:
                    continue
                content = self._download_image(meta["url"])
                if not content:
                    continue
                b64 = base64.b64encode(content)
                product_image_model.create(
                    {
                        "product_tmpl_id": tmpl_id,
                        "name": name,
                        "sequence": seq,
                        "image_1920": b64,
                    }
                )
                created += 1
                existing_names.add(name)
                existing_sequences.add(seq)
                if idx == 1 and not tmpl.image_1920:
                    tmpl.write({"image_1920": b64})
                    set_main += 1

        self.action_run_health_check()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Product Media Imported",
                "message": f"Created {created} media rows, set {set_main} main images.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_import_inventory(self):
        self.ensure_one()
        rows = self._load_inventory_rows()
        if not rows:
            raise UserError("No inventory rows found.")

        sku_rows = [r for r in rows if (r.get("SKU") or "").strip() and self._inventory_qty_from_row(r) is not None]
        if not sku_rows:
            raise UserError("No inventory rows with SKU and usable quantity found.")

        skus = list({(r.get("SKU") or "").strip() for r in sku_rows})
        locations = list({(r.get("Location") or "").strip() for r in sku_rows if (r.get("Location") or "").strip()})

        product_map = {
            p.default_code: p
            for p in self.env["product.product"].sudo().search([("default_code", "in", skus)])
        }

        all_locs = self.env["stock.location"].sudo().search([("usage", "=", "internal")])
        loc_map = self._build_location_map(all_locs)
        fallback_loc = self._inventory_fallback_location()

        updated = 0
        skipped = 0
        mapped_with_fallback = 0
        skipped_non_storable = 0
        quant_model = self.env["stock.quant"].sudo()
        for r in sku_rows:
            sku = (r.get("SKU") or "").strip()
            location_name = (r.get("Location") or "").strip()
            qty_new = self._inventory_qty_from_row(r)
            product = product_map.get(sku)
            loc, used_fallback = self._inventory_resolve_location(location_name, loc_map, fallback_loc)
            if used_fallback and loc:
                mapped_with_fallback += 1
            if not product or not loc:
                skipped += 1
                continue
            if not self._is_storable_template(product.product_tmpl_id):
                skipped_non_storable += 1
                continue
            if qty_new is None:
                skipped += 1
                continue

            quant = quant_model.search(
                [
                    ("product_id", "=", product.id),
                    ("location_id", "=", loc.id),
                    ("company_id", "=", self.env.company.id),
                ],
                limit=1,
            )
            if not quant:
                quant = quant_model.create(
                    {
                        "product_id": product.id,
                        "location_id": loc.id,
                        "company_id": self.env.company.id,
                        "inventory_quantity": qty_new,
                    }
                )
            else:
                quant.write({"inventory_quantity": qty_new})
            quant.action_apply_inventory()
            updated += 1

        self.action_run_health_check()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Inventory Imported",
                "message": f"Updated {updated} rows, skipped {skipped}, non-storable {skipped_non_storable}, fallback-mapped {mapped_with_fallback}.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_import_orders(self):
        self.ensure_one()
        rows = self._load_orders_rows()
        if not rows:
            raise UserError("No orders rows found in export folder/sheet.")

        grouped = self._group_order_rows(rows)
        if not grouped:
            raise UserError("No valid orders found in provided files.")

        order_refs = list(grouped.keys())
        sale_model = self.env["sale.order"].sudo()
        existing_orders = sale_model.search_read([("client_order_ref", "in", order_refs)], ["client_order_ref"])
        existing_refs = {r.get("client_order_ref") for r in existing_orders if r.get("client_order_ref")}

        partner_model = self.env["res.partner"].sudo()
        all_emails = sorted(
            {
                (meta.get("email") or "").strip().lower()
                for meta in grouped.values()
                if (meta.get("email") or "").strip()
            }
        )
        partner_map = {}
        if all_emails:
            existing_partners = partner_model.search_read([("email", "in", all_emails)], ["id", "email"])
            partner_map = {(p.get("email") or "").strip().lower(): p["id"] for p in existing_partners if p.get("email")}

        sku_values = sorted(
            {
                (line.get("sku") or "").strip()
                for meta in grouped.values()
                for line in meta["lines"]
                if (line.get("sku") or "").strip()
            }
        )
        variants = self.env["product.product"].sudo().search_read(
            [("default_code", "!=", False)], ["id", "default_code"]
        )
        sku_map = {(v.get("default_code") or "").strip(): v["id"] for v in variants if v.get("default_code")}
        sku_norm_map = {}
        for v in variants:
            code = (v.get("default_code") or "").strip()
            if code:
                nkey = self._normalize_sku(code)
                if nkey and nkey not in sku_norm_map:
                    sku_norm_map[nkey] = v["id"]

        created = 0
        skipped_existing = 0
        skipped_no_lines = 0
        missing_product_lines = 0
        created_partners = 0

        for order_ref, meta in grouped.items():
            if order_ref in existing_refs:
                skipped_existing += 1
                continue

            email = (meta.get("email") or "").strip().lower()
            partner_id = partner_map.get(email) if email else False
            if not partner_id:
                name = meta.get("billing_name") or meta.get("shipping_name") or email or "Shopify Customer"
                vals = {"name": name}
                if email:
                    vals["email"] = email
                partner = partner_model.create(vals)
                partner_id = partner.id
                if email:
                    partner_map[email] = partner_id
                created_partners += 1

            lines = []
            for line in meta["lines"]:
                sku = (line.get("sku") or "").strip()
                prod_id = sku_map.get(sku)
                if not prod_id and sku:
                    prod_id = sku_norm_map.get(self._normalize_sku(sku))
                if not prod_id:
                    missing_product_lines += 1
                    continue
                qty = self._to_float(line.get("qty"), 0.0)
                if qty <= 0:
                    qty = 1.0
                price = self._to_float(line.get("price"), 0.0)
                lines.append(
                    (
                        0,
                        0,
                        {
                            "product_id": prod_id,
                            "product_uom_qty": qty,
                            "price_unit": price,
                            "name": line.get("name") or sku or "Shopify Item",
                        },
                    )
                )

            if not lines:
                skipped_no_lines += 1
                continue

            order_vals = {
                "partner_id": partner_id,
                "client_order_ref": order_ref,
                "origin": f"Shopify {order_ref}",
                "order_line": lines,
            }
            date_order = self._parse_shopify_datetime(meta.get("created_at"))
            if date_order:
                order_vals["date_order"] = date_order

            sale_model.create(order_vals)
            created += 1

        self.action_run_health_check()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Orders Imported",
                "message": (
                    f"Created {created} orders, skipped existing {skipped_existing}, "
                    f"skipped no-valid-lines {skipped_no_lines}, missing-product-lines {missing_product_lines}, "
                    f"new partners {created_partners}."
                ),
                "type": "success",
                "sticky": True,
            },
        }

    def action_refresh_inventory_dashboard(self):
        self.ensure_one()
        storable_variants = self.env["product.product"].sudo().search(
            [("product_tmpl_id.is_storable", "=", True)]
        )
        storable_ids = storable_variants.ids

        if not storable_ids:
            self.write(
                {
                    "inv_kpi_total_products": 0,
                    "inv_kpi_in_stock_products": 0,
                    "inv_kpi_out_of_stock_products": 0,
                    "inv_kpi_low_stock_products": 0,
                    "inv_kpi_total_qty": 0.0,
                }
            )
            self.inventory_kpi_line_ids.unlink()
            return True

        loc_ids = self.env["stock.location"].sudo().search([("usage", "=", "internal")]).ids
        qty_map = defaultdict(float)
        quant_rows = self.env["stock.quant"].sudo().search_read(
            [("product_id", "in", storable_ids), ("location_id", "in", loc_ids)],
            ["product_id", "quantity"],
            limit=200000,
        )
        for row in quant_rows:
            product = row.get("product_id")
            if not product:
                continue
            qty_map[product[0]] += float(row.get("quantity", 0.0) or 0.0)

        total = len(storable_ids)
        in_stock = 0
        out_of_stock = 0
        low_stock = 0
        total_qty = 0.0
        threshold = float(self.low_stock_threshold or 0.0)
        low_lines = []

        for product in storable_variants:
            qty = float(qty_map.get(product.id, 0.0))
            total_qty += qty
            if qty <= 0:
                out_of_stock += 1
            else:
                in_stock += 1
                if qty <= threshold:
                    low_stock += 1
                    low_lines.append((qty, product))

        low_lines.sort(key=lambda x: x[0])
        self.inventory_kpi_line_ids.unlink()
        if low_lines:
            vals = []
            for qty, product in low_lines[:100]:
                vals.append(
                    {
                        "dashboard_id": self.id,
                        "product_id": product.id,
                        "sku": product.default_code or "",
                        "qty_available": qty,
                    }
                )
            self.env["shopify.inventory.kpi.line"].create(vals)

        self.write(
            {
                "inv_kpi_total_products": total,
                "inv_kpi_in_stock_products": in_stock,
                "inv_kpi_out_of_stock_products": out_of_stock,
                "inv_kpi_low_stock_products": low_stock,
                "inv_kpi_total_qty": round(total_qty, 4),
            }
        )
        return True

    def _sheet_row_count(self, sheet_type, path):
        if not path or not os.path.exists(path):
            return 0
        if path.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(path) as zf:
                    names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                    if not names:
                        return 0
                    with zf.open(names[0]) as f:
                        text = io.TextIOWrapper(f, encoding="utf-8-sig")
                        return max(sum(1 for _ in text) - 1, 0)
            except Exception:
                return 0
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                return max(sum(1 for _ in f) - 1, 0)
        except Exception:
            return 0

    def _sheet_for_type(self, sheet_type):
        self.ensure_one()
        sheet = self.sheet_ids.filtered(lambda s: s.sheet_type == sheet_type)
        return sheet[:1]

    def _ensure_sheet_rows(self):
        self.ensure_one()
        for sheet_type, _label in SHEET_TYPES:
            if not self.sheet_ids.filtered(lambda s: s.sheet_type == sheet_type):
                self.env["shopify.sync.sheet"].create(
                    {
                        "dashboard_id": self.id,
                        "sheet_type": sheet_type,
                        "status": "missing",
                        "use_all_matching_files": sheet_type == "orders",
                    }
                )

    def _load_customers_rows(self):
        sheet = self._sheet_for_type("customers")
        if not sheet or not sheet.file_path:
            return []
        path = sheet.file_path
        rows = []
        if path.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as zf:
                names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if not names:
                    return []
                with zf.open(names[0]) as f:
                    text = io.TextIOWrapper(f, encoding="utf-8-sig")
                    rows = list(csv.DictReader(text))
        else:
            with open(path, newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
        return rows

    def _parse_products_sheet(self):
        sheet = self._sheet_for_type("products")
        if not sheet or not sheet.file_path:
            return {}, {}

        handle_images = defaultdict(list)
        handle_skus = defaultdict(set)
        seen = defaultdict(set)

        with open(sheet.file_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                handle = (row.get("Handle") or "").strip()
                sku = (row.get("Variant SKU") or "").strip()
                image_src = (row.get("Image Src") or "").strip()
                image_position_raw = (row.get("Image Position") or "").strip()
                image_alt = (row.get("Image Alt Text") or "").strip()

                if not handle:
                    continue
                if sku:
                    handle_skus[handle].add(sku)
                if not image_src:
                    continue
                if image_src in seen[handle]:
                    continue
                seen[handle].add(image_src)

                try:
                    position = int(image_position_raw) if image_position_raw else 9999
                except ValueError:
                    position = 9999

                handle_images[handle].append(
                    {"url": image_src, "position": position, "alt": image_alt}
                )

        for handle in handle_images:
            handle_images[handle].sort(key=lambda x: (x["position"], x["url"]))

        return handle_images, handle_skus

    def _load_inventory_rows(self):
        sheet = self._sheet_for_type("inventory")
        if not sheet or not sheet.file_path:
            return []
        with open(sheet.file_path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def _orders_source_paths(self):
        sheet = self._sheet_for_type("orders")
        use_all = bool(sheet.use_all_matching_files) if sheet else False
        folder = self.export_folder
        paths = []
        if folder and os.path.isdir(folder):
            patterns = [re.compile(p, re.IGNORECASE) for p in SHEET_PATTERNS["orders"]]
            for fname in os.listdir(folder):
                fpath = os.path.join(folder, fname)
                if not os.path.isfile(fpath):
                    continue
                if any(p.match(fname) for p in patterns):
                    paths.append(fpath)
        paths = sorted(paths)
        if use_all and paths:
            return paths
        if paths:
            return [paths[-1]]
        if sheet and sheet.file_path and os.path.isfile(sheet.file_path):
            return [sheet.file_path]
        return []

    def _load_orders_rows(self):
        rows = []
        for path in self._orders_source_paths():
            if path.lower().endswith(".zip"):
                with zipfile.ZipFile(path) as zf:
                    names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                    if not names:
                        continue
                    with zf.open(names[0]) as f:
                        text = io.TextIOWrapper(f, encoding="utf-8-sig")
                        rows.extend(list(csv.DictReader(text)))
            else:
                with open(path, newline="", encoding="utf-8-sig") as f:
                    rows.extend(list(csv.DictReader(f)))
        return rows

    def _group_order_rows(self, rows):
        grouped = {}
        for r in rows:
            raw_ref = (r.get("Name") or "").strip()
            order_ref = self._normalize_order_ref(raw_ref)
            if not order_ref:
                continue
            meta = grouped.setdefault(
                order_ref,
                {
                    "raw_ref": raw_ref,
                    "email": (r.get("Email") or "").strip().lower(),
                    "created_at": (r.get("Created at") or "").strip(),
                    "currency": (r.get("Currency") or "").strip(),
                    "billing_name": (r.get("Billing Name") or "").strip(),
                    "shipping_name": (r.get("Shipping Name") or "").strip(),
                    "total": self._to_float(r.get("Total"), 0.0),
                    "lines": [],
                },
            )
            qty = (r.get("Lineitem quantity") or "").strip()
            meta["lines"].append(
                {
                    "sku": (r.get("Lineitem sku") or "").strip(),
                    "name": (r.get("Lineitem name") or "").strip(),
                    "qty": qty,
                    "price": (r.get("Lineitem price") or "").strip(),
                }
            )
        return grouped

    def _build_handle_template_map(self, handle_skus):
        handles = list(handle_skus.keys())
        all_skus = sorted({sku for h in handles for sku in handle_skus.get(h, set()) if sku})

        product_rows = self.env["product.product"].sudo().search_read(
            [("default_code", "in", all_skus)], ["default_code", "product_tmpl_id"]
        )
        sku_to_templates = defaultdict(set)
        for p in product_rows:
            sku = p.get("default_code")
            tmpl = p.get("product_tmpl_id")
            if sku and tmpl:
                sku_to_templates[sku].add(tmpl[0])

        mapped = {}
        ambiguous = {}
        for handle, skus in handle_skus.items():
            templates = set()
            for sku in skus:
                templates.update(sku_to_templates.get(sku, set()))
            if len(templates) == 1:
                mapped[handle] = list(templates)[0]
            elif len(templates) > 1:
                ambiguous[handle] = sorted(templates)
        return mapped, ambiguous

    def _health_check_customers(self):
        rows = self._load_customers_rows()
        if not rows:
            return {"total": 0, "correct": 0, "partial": 0, "false": 0}

        by_email = {}
        for r in rows:
            email = (r.get("Email") or "").strip().lower()
            if email:
                by_email[email] = r

        emails = list(by_email.keys())
        partners = self.env["res.partner"].sudo().search_read(
            [("email", "in", emails)], ["name", "email", "phone", "street", "city", "zip"]
        )
        partner_map = {(p.get("email") or "").strip().lower(): p for p in partners if p.get("email")}

        total = len(by_email)
        correct = partial = false = 0

        for email, row in by_email.items():
            partner = partner_map.get(email)
            exp_name = ((row.get("First Name") or "") + " " + (row.get("Last Name") or "")).strip()
            exp_phone = (row.get("Phone") or "").strip() or (row.get("Default Address Phone") or "").strip()
            exp_city = (row.get("Default Address City") or "").strip()
            if not partner:
                false += 1
                self._create_issue(
                    issue_type="customers",
                    status="false",
                    external_ref=email,
                    name=exp_name or email,
                    details="Customer email not found in Odoo.",
                    expected_value=email,
                    current_value="Missing",
                )
                continue

            mismatches = 0
            if exp_name and partner.get("name") and exp_name.lower() != partner.get("name").strip().lower():
                mismatches += 1
            if exp_phone and (partner.get("phone") or "").strip() and exp_phone != (partner.get("phone") or "").strip():
                mismatches += 1
            if exp_city and (partner.get("city") or "").strip() and exp_city.lower() != (partner.get("city") or "").strip().lower():
                mismatches += 1

            if mismatches == 0:
                correct += 1
            else:
                partial += 1
                self._create_issue(
                    issue_type="customers",
                    status="partial",
                    external_ref=email,
                    name=partner.get("name") or email,
                    details=f"Customer exists but has {mismatches} field mismatch(es).",
                    expected_value=f"Name:{exp_name} | Phone:{exp_phone} | City:{exp_city}",
                    current_value=f"Name:{partner.get('name')} | Phone:{partner.get('phone')} | City:{partner.get('city')}",
                )

        return {"total": total, "correct": correct, "partial": partial, "false": false}

    def _health_check_products(self):
        handle_images, handle_skus = self._parse_products_sheet()
        if not handle_images:
            return {"total": 0, "correct": 0, "partial": 0, "false": 0}

        mapped, ambiguous = self._build_handle_template_map(handle_skus)
        total = len(handle_images)
        correct = partial = false = 0

        template_ids = list(set(mapped.values()))
        templates = self.env["product.template"].sudo().search_read(
            [("id", "in", template_ids)], ["id", "name", "image_1920", "product_template_image_ids"]
        )
        template_map = {t["id"]: t for t in templates}

        for handle, images in handle_images.items():
            if handle in ambiguous:
                false += 1
                self._create_issue(
                    issue_type="products",
                    status="false",
                    external_ref=handle,
                    name=handle,
                    details="Handle matched multiple templates.",
                    expected_value=f"1 template for {handle}",
                    current_value=f"{len(ambiguous[handle])} templates",
                )
                continue

            tmpl_id = mapped.get(handle)
            if not tmpl_id:
                false += 1
                self._create_issue(
                    issue_type="products",
                    status="false",
                    external_ref=handle,
                    name=handle,
                    details="Handle not mapped by SKU to any product template.",
                    expected_value="Mapped template",
                    current_value="Missing",
                )
                continue

            tmpl = template_map.get(tmpl_id)
            media_count = len((tmpl or {}).get("product_template_image_ids") or [])
            has_main = bool((tmpl or {}).get("image_1920"))
            expected = len(images)

            if media_count >= expected and has_main:
                correct += 1
            elif media_count > 0 or has_main:
                partial += 1
                self._create_issue(
                    issue_type="products",
                    status="partial",
                    external_ref=handle,
                    name=(tmpl or {}).get("name") or handle,
                    details="Product has partial image sync.",
                    expected_value=f"media>={expected}, main image=True",
                    current_value=f"media={media_count}, main image={has_main}",
                )
            else:
                false += 1
                self._create_issue(
                    issue_type="products",
                    status="false",
                    external_ref=handle,
                    name=(tmpl or {}).get("name") or handle,
                    details="No website media and no main image.",
                    expected_value=f"media>={expected}, main image=True",
                    current_value="media=0, main image=False",
                )

        return {"total": total, "correct": correct, "partial": partial, "false": false}

    def _health_check_inventory(self):
        rows = self._load_inventory_rows()
        if not rows:
            return {"total": 0, "correct": 0, "partial": 0, "false": 0}

        clean_rows = [
            r
            for r in rows
            if (r.get("SKU") or "").strip() and self._inventory_qty_from_row(r) is not None
        ]
        if not clean_rows:
            return {"total": 0, "correct": 0, "partial": 0, "false": 0}

        skus = list({(r.get("SKU") or "").strip() for r in clean_rows})
        loc_names = list({(r.get("Location") or "").strip() for r in clean_rows})

        products = self.env["product.product"].sudo().search([("default_code", "in", skus)])
        product_map = {p.default_code: p for p in products}

        locations = self.env["stock.location"].sudo().search([("usage", "=", "internal")])
        loc_map = self._build_location_map(locations)
        fallback_loc = self._inventory_fallback_location()

        total = len(clean_rows)
        correct = partial = false = 0

        for r in clean_rows:
            sku = (r.get("SKU") or "").strip()
            loc_name = (r.get("Location") or "").strip()
            qty_new_raw = (r.get("On hand (new)") or "").strip() or (r.get("On hand (current)") or "").strip()
            product = product_map.get(sku)
            location, _used_fallback = self._inventory_resolve_location(loc_name, loc_map, fallback_loc)

            if not product:
                false += 1
                self._create_issue(
                    issue_type="inventory",
                    status="false",
                    external_ref=sku,
                    name=sku,
                    details="SKU not found in Odoo.",
                    expected_value="Existing SKU",
                    current_value="Missing",
                )
                continue
            if not self._is_storable_template(product.product_tmpl_id):
                product_type = getattr(product.product_tmpl_id, "detailed_type", False) or getattr(
                    product.product_tmpl_id, "type", False
                )
                is_storable = getattr(product.product_tmpl_id, "is_storable", False)
                false += 1
                self._create_issue(
                    issue_type="inventory",
                    status="false",
                    external_ref=f"{sku}@{loc_name}",
                    name=product.display_name,
                    details="Product is not storable (service/consumable), quant sync skipped.",
                    expected_value="Storable product / Track Inventory enabled",
                    current_value=f"type={product_type}, is_storable={is_storable}",
                )
                continue
            if not location:
                false += 1
                self._create_issue(
                    issue_type="inventory",
                    status="false",
                    external_ref=f"{sku}@{loc_name}",
                    name=sku,
                    details="Inventory location not found (internal).",
                    expected_value=loc_name,
                    current_value="Missing",
                )
                continue

            qty_new = self._inventory_qty_from_row(r)
            if qty_new is None:
                false += 1
                self._create_issue(
                    issue_type="inventory",
                    status="false",
                    external_ref=f"{sku}@{loc_name}",
                    name=sku,
                    details="Invalid numeric quantity in On hand (new).",
                    expected_value=qty_new_raw,
                    current_value="Invalid",
                )
                continue

            quant = self.env["stock.quant"].sudo().search(
                [
                    ("product_id", "=", product.id),
                    ("location_id", "=", location.id),
                    ("company_id", "=", self.env.company.id),
                ],
                limit=1,
            )
            qty_cur = quant.quantity if quant else 0.0
            diff = abs(qty_new - qty_cur)

            if math.isclose(diff, 0.0, abs_tol=0.0001):
                correct += 1
            elif diff <= 2.0:
                partial += 1
                self._create_issue(
                    issue_type="inventory",
                    status="partial",
                    external_ref=f"{sku}@{loc_name}",
                    name=product.display_name,
                    details="Inventory close but not exact.",
                    expected_value=str(qty_new),
                    current_value=str(round(qty_cur, 4)),
                )
            else:
                false += 1
                self._create_issue(
                    issue_type="inventory",
                    status="false",
                    external_ref=f"{sku}@{loc_name}",
                    name=product.display_name,
                    details="Inventory mismatch is high.",
                    expected_value=str(qty_new),
                    current_value=str(round(qty_cur, 4)),
                )

        return {"total": total, "correct": correct, "partial": partial, "false": false}

    def _health_check_orders(self):
        rows = self._load_orders_rows()
        if not rows:
            return {"total": 0, "correct": 0, "partial": 0, "false": 0}

        grouped = self._group_order_rows(rows)
        if not grouped:
            return {"total": 0, "correct": 0, "partial": 0, "false": 0}

        refs = list(grouped.keys())
        naked_refs = [r[1:] if r.startswith("#") else r for r in refs]
        sale_orders = self.env["sale.order"].sudo().search_read(
            ["|", ("client_order_ref", "in", refs), ("client_order_ref", "in", naked_refs)],
            ["client_order_ref", "amount_total", "order_line"],
            limit=200000,
        )
        order_map = {}
        for s in sale_orders:
            ref = (s.get("client_order_ref") or "").strip()
            if not ref:
                continue
            order_map[self._normalize_order_ref(ref)] = s

        total = len(grouped)
        correct = partial = false = 0
        for order_ref, expected in grouped.items():
            so = order_map.get(order_ref)
            if not so:
                false += 1
                self._create_issue(
                    issue_type="orders",
                    status="false",
                    external_ref=order_ref,
                    name=order_ref,
                    details="Order missing in Odoo sale orders.",
                    expected_value="Order exists",
                    current_value="Missing",
                )
                continue

            # Current operational requirement: measure existence sync only.
            # (Detailed amount/line reconciliation can be added as a separate check mode.)
            correct += 1

        return {"total": total, "correct": correct, "partial": partial, "false": false}

    def _inventory_qty_from_row(self, row):
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

    def _inventory_fallback_location(self):
        warehouse = self.env["stock.warehouse"].sudo().search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        if warehouse and warehouse.lot_stock_id and warehouse.lot_stock_id.usage == "internal":
            return warehouse.lot_stock_id
        loc = self.env["stock.location"].sudo().search(
            [("usage", "=", "internal"), ("company_id", "in", [self.env.company.id, False])],
            limit=1,
        )
        return loc or False

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

    def _inventory_resolve_location(self, location_name, loc_map, fallback_loc):
        nkey = self._normalize_location_key(location_name)
        if nkey and nkey in loc_map:
            return loc_map[nkey], False

        # Shopify export names do not always match Odoo internal names exactly.
        # Keep this deterministic to avoid applying qty to wrong location.
        alias_candidates = []
        if "warehouselevel1" in nkey or "level1" in nkey or "lvl1" in nkey:
            alias_candidates.extend(("lvl1stock", "level1stock", "lvl1"))
        if "tynoraustralia" in nkey:
            alias_candidates.extend(("whgrstock", "whgr", "whstock", "stock"))
        if "whgr" in nkey:
            alias_candidates.extend(("whgrstock", "whgr"))

        for alias in alias_candidates:
            loc = loc_map.get(alias)
            if loc:
                return loc, False
        for alias in alias_candidates:
            for key, loc in loc_map.items():
                if alias in key:
                    return loc, False

        # If source row has explicit location and we can't map it confidently,
        # fail instead of silent fallback.
        if nkey:
            return False, True
        return fallback_loc, True

    def _is_storable_template(self, tmpl):
        # Newer Odoo builds expose Track Inventory as `is_storable`.
        if hasattr(tmpl, "is_storable"):
            return bool(tmpl.is_storable)
        # Fallback for builds where storable is represented in selection value.
        product_type = getattr(tmpl, "detailed_type", False) or getattr(tmpl, "type", False)
        return product_type == "product"

    def _create_issue(self, issue_type, status, external_ref, name, details, expected_value, current_value):
        self.env["shopify.sync.issue"].create(
            {
                "dashboard_id": self.id,
                "issue_type": issue_type,
                "status": status,
                "external_ref": external_ref,
                "name": name,
                "details": details,
                "expected_value": expected_value,
                "current_value": current_value,
            }
        )

    def _download_image(self, url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read()
        except Exception:
            return None

    def _normalize_order_ref(self, value):
        value = (value or "").strip()
        if not value:
            return ""
        return value if value.startswith("#") else f"#{value}"

    def _normalize_sku(self, value):
        return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())

    def _to_float(self, value, default=0.0):
        raw = (value or "").strip().replace(",", "")
        if not raw:
            return default
        try:
            return float(raw)
        except Exception:
            return default

    def _parse_shopify_datetime(self, value):
        raw = (value or "").strip()
        if not raw:
            return False
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")
            return fields.Datetime.to_string(dt.astimezone(timezone.utc).replace(tzinfo=None))
        except Exception:
            return False


class ShopifySyncSheet(models.Model):
    _name = "shopify.sync.sheet"
    _description = "Shopify Sync Source Sheet"
    _order = "sheet_type, file_mtime desc"

    dashboard_id = fields.Many2one("shopify.sync.dashboard", required=True, ondelete="cascade")
    sheet_type = fields.Selection(SHEET_TYPES, required=True)
    file_name = fields.Char()
    file_path = fields.Char()
    file_mtime = fields.Datetime()
    row_count = fields.Integer(default=0)
    size_bytes = fields.Integer(default=0)
    upload_file = fields.Binary(string="Upload Sheet")
    upload_filename = fields.Char(string="Upload Filename")
    manual_file_path = fields.Char(string="Use Existing File Path")
    use_all_matching_files = fields.Boolean(string="Use All Matching Files", default=False)
    status = fields.Selection(
        [("available", "Available"), ("missing", "Missing")],
        default="available",
        required=True,
    )

    def action_apply_uploaded_file(self):
        self.ensure_one()
        if not self.upload_file:
            raise UserError("Upload a sheet file first.")
        folder = self.dashboard_id.export_folder
        if not folder:
            raise UserError("Dashboard export folder is not configured.")
        os.makedirs(folder, exist_ok=True)

        filename = (self.upload_filename or "").strip()
        if not filename:
            ext = ".zip" if self.sheet_type == "customers" else ".csv"
            filename = f"{self.sheet_type}_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

        safe_name = os.path.basename(filename)
        target = os.path.join(folder, safe_name)
        content = base64.b64decode(self.upload_file)
        with open(target, "wb") as f:
            f.write(content)

        row_count = self.dashboard_id._sheet_row_count(self.sheet_type, target)
        self.write(
            {
                "file_name": safe_name,
                "file_path": target,
                "file_mtime": fields.Datetime.now(),
                "row_count": row_count,
                "size_bytes": len(content),
                "status": "available",
            }
        )
        return True

    def action_apply_manual_file_path(self):
        self.ensure_one()
        path = (self.manual_file_path or "").strip()
        if not path:
            raise UserError("Enter a valid file path first.")
        if not os.path.isfile(path):
            raise UserError(f"File not found: {path}")

        row_count = self.dashboard_id._sheet_row_count(self.sheet_type, path)
        self.write(
            {
                "file_name": os.path.basename(path),
                "file_path": path,
                "file_mtime": datetime.fromtimestamp(os.path.getmtime(path)),
                "row_count": row_count,
                "size_bytes": os.path.getsize(path),
                "status": "available",
            }
        )
        return True


class ShopifySyncIssue(models.Model):
    _name = "shopify.sync.issue"
    _description = "Shopify Sync Health Issue"
    _order = "status desc, issue_type, id desc"

    dashboard_id = fields.Many2one("shopify.sync.dashboard", required=True, ondelete="cascade")
    issue_type = fields.Selection(SHEET_TYPES, required=True)
    status = fields.Selection(
        [("false", "False"), ("partial", "Partial")],
        required=True,
    )
    external_ref = fields.Char(string="External Ref")
    name = fields.Char(required=True)
    details = fields.Text()
    expected_value = fields.Text()
    current_value = fields.Text()
    manual_fix_note = fields.Text(compute="_compute_fix_notes")
    auto_fix_plan = fields.Text(compute="_compute_fix_notes")
    is_auto_fix_available = fields.Boolean(compute="_compute_fix_notes")

    @api.depends("issue_type", "status", "details", "external_ref")
    def _compute_fix_notes(self):
        for rec in self:
            rec.manual_fix_note = rec._manual_fix_note_value()
            rec.auto_fix_plan = rec._auto_fix_plan_value()
            rec.is_auto_fix_available = bool(rec._auto_fix_kind())

    def _manual_fix_note_value(self):
        self.ensure_one()
        ref = self.external_ref or "-"
        if self.issue_type == "customers":
            return (
                "Manual fix steps:\n"
                "1. Open Contacts and search email from External Ref.\n"
                "2. If missing, create contact from Customers sheet.\n"
                "3. If partial mismatch, update Name/Phone/City.\n"
                f"Target: {ref}"
            )
        if self.issue_type == "inventory":
            return (
                "Manual fix steps:\n"
                "1. Open Product by SKU from External Ref.\n"
                "2. Ensure Track Inventory (storable) is enabled.\n"
                "3. Update on-hand qty from Inventory sheet for same SKU/location.\n"
                f"Target: {ref}"
            )
        if self.issue_type == "orders":
            return (
                "Manual fix steps:\n"
                "1. Open Sales Orders and search client reference.\n"
                "2. If not found, decide whether to import/create missing order.\n"
                "3. Re-run health check after correction.\n"
                f"Target: {ref}"
            )
        if self.issue_type == "products":
            return (
                "Manual fix steps:\n"
                "1. Open Product template mapped to this handle/SKU.\n"
                "2. Upload missing website media images and set main image.\n"
                "3. Re-run health check.\n"
                f"Target: {ref}"
            )
        return "Manual fix: open related record, correct data, then run health check."

    def _auto_fix_kind(self):
        self.ensure_one()
        details = (self.details or "").lower()
        if self.issue_type == "customers":
            if "not found" in details:
                return "customer_create"
            return "customer_update"
        if self.issue_type == "inventory":
            if "not storable" in details:
                return "inventory_enable_storable"
            if "mismatch" in details or "close but not exact" in details:
                return "inventory_sync_qty"
        return ""

    def _auto_fix_plan_value(self):
        self.ensure_one()
        kind = self._auto_fix_kind()
        plans = {
            "customer_create": "Will create missing Contact from Customers sheet by email.",
            "customer_update": "Will update Contact Name/Phone/City from Customers sheet.",
            "inventory_enable_storable": "Will enable Track Inventory (storable) on product template.",
            "inventory_sync_qty": "Will set inventory quantity from Inventory sheet for this SKU/location.",
        }
        return plans.get(kind, "No safe automated fix for this issue type. Use Manual Fix.")

    def action_manual_fix(self):
        self.ensure_one()
        if self.issue_type == "customers":
            email = (self.external_ref or "").strip().lower()
            partner = self.env["res.partner"].sudo().search([("email", "=", email)], limit=1)
            if partner:
                return {
                    "type": "ir.actions.act_window",
                    "name": "Customer",
                    "res_model": "res.partner",
                    "res_id": partner.id,
                    "view_mode": "form",
                    "target": "current",
                }
            return {
                "type": "ir.actions.act_window",
                "name": "Contacts",
                "res_model": "res.partner",
                "view_mode": "list,form",
                "domain": [("email", "=", email)],
            }
        if self.issue_type == "inventory":
            sku = (self.external_ref or "").split("@")[0].strip()
            product = self.env["product.product"].sudo().search([("default_code", "=", sku)], limit=1)
            if product:
                return {
                    "type": "ir.actions.act_window",
                    "name": "Product",
                    "res_model": "product.product",
                    "res_id": product.id,
                    "view_mode": "form",
                    "target": "current",
                }
        if self.issue_type == "orders":
            ref = (self.external_ref or "").strip()
            naked = ref[1:] if ref.startswith("#") else ref
            return {
                "type": "ir.actions.act_window",
                "name": "Sales Orders",
                "res_model": "sale.order",
                "view_mode": "list,form",
                "domain": ["|", ("client_order_ref", "=", ref), ("client_order_ref", "=", naked)],
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Manual Fix Guidance",
                "message": self.manual_fix_note or "Open related data and fix manually.",
                "type": "warning",
                "sticky": True,
            },
        }

    def action_automated_fix(self):
        fixed = 0
        skipped = 0
        dashboards = self.env["shopify.sync.dashboard"]
        for rec in self:
            ok = rec._apply_automated_fix()
            if ok:
                fixed += 1
                dashboards |= rec.dashboard_id
            else:
                skipped += 1

        for dash in dashboards:
            dash.action_run_health_check()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Automated Fix",
                "message": f"Applied {fixed} fix(es), skipped {skipped}. Resolved issues are removed after re-check.",
                "type": "success" if fixed else "warning",
                "sticky": True,
            },
        }

    def _apply_automated_fix(self):
        self.ensure_one()
        kind = self._auto_fix_kind()
        if not kind:
            return False
        if kind == "customer_create":
            return self._auto_fix_customer_create()
        if kind == "customer_update":
            return self._auto_fix_customer_update()
        if kind == "inventory_enable_storable":
            return self._auto_fix_inventory_enable_storable()
        if kind == "inventory_sync_qty":
            return self._auto_fix_inventory_qty()
        return False

    def _auto_fix_customer_create(self):
        self.ensure_one()
        dash = self.dashboard_id
        email = (self.external_ref or "").strip().lower()
        if not email:
            return False
        partner = self.env["res.partner"].sudo().search([("email", "=", email)], limit=1)
        if partner:
            return True
        row = None
        for r in dash._load_customers_rows():
            if (r.get("Email") or "").strip().lower() == email:
                row = r
                break
        if not row:
            return False
        first = (row.get("First Name") or "").strip()
        last = (row.get("Last Name") or "").strip()
        name = (f"{first} {last}").strip() or email
        phone = (row.get("Phone") or "").strip() or (row.get("Default Address Phone") or "").strip()
        self.env["res.partner"].sudo().create(
            {
                "name": name,
                "email": email,
                "phone": phone,
                "street": (row.get("Default Address Address1") or "").strip(),
                "street2": (row.get("Default Address Address2") or "").strip(),
                "city": (row.get("Default Address City") or "").strip(),
                "zip": (row.get("Default Address Zip") or "").strip(),
            }
        )
        return True

    def _auto_fix_customer_update(self):
        self.ensure_one()
        dash = self.dashboard_id
        email = (self.external_ref or "").strip().lower()
        if not email:
            return False
        partner = self.env["res.partner"].sudo().search([("email", "=", email)], limit=1)
        if not partner:
            return False
        row = None
        for r in dash._load_customers_rows():
            if (r.get("Email") or "").strip().lower() == email:
                row = r
                break
        if not row:
            return False
        first = (row.get("First Name") or "").strip()
        last = (row.get("Last Name") or "").strip()
        name = (f"{first} {last}").strip() or partner.name
        phone = (row.get("Phone") or "").strip() or (row.get("Default Address Phone") or "").strip()
        city = (row.get("Default Address City") or "").strip()
        vals = {"name": name}
        if phone:
            vals["phone"] = phone
        if city:
            vals["city"] = city
        partner.write(vals)
        return True

    def _auto_fix_inventory_enable_storable(self):
        self.ensure_one()
        sku = (self.external_ref or "").split("@")[0].strip()
        if not sku:
            return False
        product = self.env["product.product"].sudo().search([("default_code", "=", sku)], limit=1)
        if not product:
            return False
        tmpl = product.product_tmpl_id
        if hasattr(tmpl, "is_storable"):
            tmpl.write({"is_storable": True})
            return True
        return False

    def _auto_fix_inventory_qty(self):
        self.ensure_one()
        dash = self.dashboard_id
        ref = (self.external_ref or "").strip()
        if "@" not in ref:
            return False
        sku, loc_name = ref.split("@", 1)
        sku = sku.strip()
        loc_name = loc_name.strip()
        if not sku:
            return False
        row = None
        for r in dash._load_inventory_rows():
            if (r.get("SKU") or "").strip() == sku:
                row_loc = (r.get("Location") or "").strip()
                if not loc_name or row_loc == loc_name:
                    row = r
                    break
        if not row:
            return False
        qty = dash._inventory_qty_from_row(row)
        if qty is None:
            return False
        product = self.env["product.product"].sudo().search([("default_code", "=", sku)], limit=1)
        if not product:
            return False
        all_locs = self.env["stock.location"].sudo().search([("usage", "=", "internal")])
        loc_map = dash._build_location_map(all_locs)
        fallback = dash._inventory_fallback_location()
        loc, _used_fallback = dash._inventory_resolve_location(loc_name, loc_map, fallback)
        if not loc:
            return False
        quant = self.env["stock.quant"].sudo().search(
            [
                ("product_id", "=", product.id),
                ("location_id", "=", loc.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if not quant:
            quant = self.env["stock.quant"].sudo().create(
                {
                    "product_id": product.id,
                    "location_id": loc.id,
                    "company_id": self.env.company.id,
                    "inventory_quantity": qty,
                }
            )
        else:
            quant.write({"inventory_quantity": qty})
        quant.action_apply_inventory()
        return True


class ShopifyInventoryKpiLine(models.Model):
    _name = "shopify.inventory.kpi.line"
    _description = "Shopify Inventory KPI Line"
    _order = "qty_available asc, id desc"

    dashboard_id = fields.Many2one("shopify.sync.dashboard", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", required=True, ondelete="cascade")
    sku = fields.Char()
    qty_available = fields.Float()
