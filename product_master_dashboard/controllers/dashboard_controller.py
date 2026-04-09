from hashlib import md5
import os
import re

from collections import defaultdict

from odoo import http
from odoo.http import request


class ProductMasterDashboardController(http.Controller):
    @http.route("/product_master_dashboard/image/<int:product_tmpl_id>", type="http", auth="user")
    def product_dashboard_image(self, product_tmpl_id, **kwargs):
        product = request.env["product.template"].sudo().browse(product_tmpl_id)
        if not product.exists():
            return request.redirect("/web/static/img/placeholder.png", code=302)

        cr = request.env.cr
        cr.execute(
            """
            SELECT store_fname
            FROM ir_attachment
            WHERE res_model = %s
              AND res_id = %s
              AND type = 'binary'
              AND res_field LIKE 'image%%'
            ORDER BY id DESC
            LIMIT 5
            """,
            ("product.template", product_tmpl_id),
        )
        store_fnames = [row[0] for row in cr.fetchall()]
        if not store_fnames:
            return request.redirect("/web/static/img/placeholder.png", code=302)

        filestore = request.env["ir.attachment"].sudo()._filestore()
        for store_fname in store_fnames:
            if not store_fname:
                # Stored in DB column, safe to delegate to /web/image.
                return request.redirect(f"/web/image/product.template/{product_tmpl_id}/image_128", code=302)
            normalized = re.sub(r"[.:]", "", store_fname).strip("/\\")
            if os.path.exists(os.path.join(filestore, normalized)):
                return request.redirect(f"/web/image/product.template/{product_tmpl_id}/image_128", code=302)

        return request.redirect("/web/static/img/placeholder.png", code=302)

    @http.route("/product_master_dashboard/data", type="json", auth="user")
    def get_dashboard_data(self):
        env = request.env
        tmpl_model = env["product.template"].sudo()
        variant_model = env["product.product"].sudo()
        warehouse_model = env["stock.warehouse"].sudo()

        total_templates = tmpl_model.search_count([])
        storable_templates = tmpl_model.search_count([("is_storable", "=", True)])
        active_templates = tmpl_model.search_count([("active", "=", True)])
        variants = variant_model.search([("product_tmpl_id.is_storable", "=", True)])

        loc_ids = env["stock.location"].sudo().search([("usage", "=", "internal")]).ids
        qty_map = {}
        if variants and loc_ids:
            qty_map = {v.id: 0.0 for v in variants}
            quant_rows = env["stock.quant"].sudo().search_read(
                [("product_id", "in", variants.ids), ("location_id", "in", loc_ids)],
                ["product_id", "quantity"],
                limit=200000,
            )
            for row in quant_rows:
                pid = row.get("product_id") and row["product_id"][0]
                if pid:
                    qty_map[pid] = qty_map.get(pid, 0.0) + float(row.get("quantity", 0.0) or 0.0)

        in_stock = sum(1 for q in qty_map.values() if q > 0)
        out_of_stock = sum(1 for q in qty_map.values() if q <= 0)

        quick_templates = tmpl_model.search([], order="write_date desc")
        dashboard_variants = quick_templates.mapped("product_variant_ids")

        warehouses = warehouse_model.search([], order="id")
        warehouse_payload = [{"id": wh.id, "name": wh.name, "view_location_id": wh.view_location_id.id} for wh in warehouses]

        internal_locations = env["stock.location"].sudo().search([("usage", "=", "internal")])
        location_to_warehouse = {}
        for location in internal_locations:
            normalized_parent_path = f"/{location.parent_path or ''}"
            for warehouse in warehouse_payload:
                if not warehouse["view_location_id"]:
                    continue
                token = f"/{warehouse['view_location_id']}/"
                if token in normalized_parent_path:
                    location_to_warehouse[location.id] = warehouse["id"]
                    break

        product_warehouse_qty = defaultdict(lambda: defaultdict(float))
        if dashboard_variants and location_to_warehouse:
            grouped_quants = env["stock.quant"].sudo()._read_group(
                [("product_id", "in", dashboard_variants.ids), ("location_id", "in", list(location_to_warehouse.keys()))],
                groupby=["product_id", "location_id"],
                aggregates=["quantity:sum"],
            )
            for row in grouped_quants:
                product_rec = row[0] if len(row) > 0 else False
                location_rec = row[1] if len(row) > 1 else False
                quantity_sum = row[2] if len(row) > 2 else 0.0
                product_id = product_rec.id if product_rec else False
                location_id = location_rec.id if location_rec else False
                if not product_id or not location_id:
                    continue
                warehouse_id = location_to_warehouse.get(location_id)
                if not warehouse_id:
                    continue
                product_warehouse_qty[product_id][warehouse_id] += float(quantity_sum or 0.0)

        cards = []
        for tmpl in quick_templates:
            stock_qty = float(tmpl.qty_available or 0.0)
            warehouse_stock = []
            for warehouse in warehouse_payload:
                qty = 0.0
                for variant in tmpl.product_variant_ids:
                    qty += product_warehouse_qty[variant.id].get(warehouse["id"], 0.0)
                warehouse_stock.append(
                    {
                        "warehouse_id": warehouse["id"],
                        "warehouse_name": warehouse["name"],
                        "qty": round(qty, 2),
                    }
                )
            max_abs_qty = max([abs(item["qty"]) for item in warehouse_stock] or [0.0])
            cards.append(
                {
                    "id": tmpl.id,
                    "name": tmpl.display_name,
                    "sku": (tmpl.product_variant_ids[:1].default_code or "") if tmpl.product_variant_ids else "",
                    "sale_price": float(tmpl.list_price or 0.0),
                    "stock_qty": stock_qty,
                    "is_storable": bool(tmpl.is_storable),
                    "image_url": f"/product_master_dashboard/image/{tmpl.id}?v={md5((tmpl.write_date or '').__str__().encode()).hexdigest()[:8]}",
                    "warehouse_stock": warehouse_stock,
                    "warehouse_max_qty": max_abs_qty,
                }
            )

        return {
            "kpis": {
                "total_templates": total_templates,
                "storable_templates": storable_templates,
                "active_templates": active_templates,
                "in_stock_variants": in_stock,
                "out_of_stock_variants": out_of_stock,
            },
            "cards": cards,
        }
