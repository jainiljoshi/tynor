from odoo import _
from odoo.http import request, route
from odoo.addons.website_sale.controllers.main import WebsiteSale


class TynorWebsiteSaleBulkSize(WebsiteSale):
    def _get_active_pricelist(self):
        order_sudo = request.cart
        if order_sudo and order_sudo.pricelist_id:
            return order_sudo.pricelist_id
        return request.website.pricelist_id

    def _get_combination_price(self, product_template, combination):
        pricelist = self._get_active_pricelist()
        template_ctx = product_template.with_context(
            pricelist=pricelist.id,
            partner=request.env.user.partner_id.id,
            quantity=1.0,
        )
        combination_info = template_ctx._get_combination_info(
            combination=combination,
            add_qty=1.0,
            pricelist=pricelist.id,
        )
        price = combination_info.get("price", 0.0)
        currency = pricelist.currency_id
        symbol = currency.symbol or ""
        position = currency.position or "after"
        decimals = currency.decimal_places or 2
        if position == "before":
            price_display = f"{symbol}{price:.{decimals}f}"
        else:
            price_display = f"{price:.{decimals}f}{symbol and (' ' + symbol)}"
        return price, price_display

    @route(
        "/shop/tynor/bulk_size_pricing",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def bulk_size_pricing(self, product_template_id, selected_ptav_ids=None, **kwargs):
        product_template = request.env["product.template"].browse(int(product_template_id)).exists()
        if not product_template:
            return {"ok": False, "message": _("Product not found."), "rows": []}

        size_line = product_template._tynor_get_size_attribute_line()
        if not size_line:
            return {"ok": False, "message": _("Size attribute is not configured."), "rows": []}

        ptav_model = request.env["product.template.attribute.value"]
        selected_ptavs = ptav_model.browse(
            [int(ptav_id) for ptav_id in (selected_ptav_ids or []) if ptav_id]
        ).exists().filtered(lambda ptav: ptav.product_tmpl_id == product_template)

        rows = []
        size_attribute = size_line.attribute_id
        base_combination = selected_ptavs.filtered(
            lambda ptav: ptav.attribute_line_id.attribute_id != size_attribute
        )

        for size_ptav in size_line.product_template_value_ids._only_active():
            combination = base_combination + size_ptav
            variant = product_template._get_variant_for_combination(combination)
            is_available = bool(variant and variant._is_add_to_cart_allowed())
            price, price_display = self._get_combination_price(product_template, combination)
            rows.append({
                "ptav_id": size_ptav.id,
                "label": size_ptav.name,
                "unit_price": price,
                "price_display": price_display,
                "available": is_available,
            })

        return {"ok": True, "rows": rows}

    @route(
        "/shop/tynor/add_bulk_sizes",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def add_bulk_sizes(self, product_template_id, selected_ptav_ids=None, size_lines=None, **kwargs):
        product_template = request.env["product.template"].browse(int(product_template_id)).exists()
        if not product_template:
            return {"ok": False, "message": _("Product not found.")}

        size_lines = size_lines or []
        normalized_lines = []
        for line in size_lines:
            try:
                qty = int(float(line.get("qty", 0)))
                ptav_id = int(line.get("ptav_id", 0))
            except (TypeError, ValueError):
                continue
            if qty > 0 and ptav_id:
                normalized_lines.append({"ptav_id": ptav_id, "qty": qty})

        if not normalized_lines:
            return {"ok": False, "message": _("Please enter quantity for at least one size.")}

        ptav_model = request.env["product.template.attribute.value"]
        selected_ptav_ids = selected_ptav_ids or []
        selected_ptavs = ptav_model.browse(
            [int(ptav_id) for ptav_id in selected_ptav_ids if ptav_id]
        ).exists().filtered(lambda ptav: ptav.product_tmpl_id == product_template)

        order_sudo = request.cart or request.website._create_cart()
        total_added = 0
        sizes_added = 0
        warnings = []

        for line in normalized_lines:
            size_ptav = ptav_model.browse(line["ptav_id"]).exists()
            if not size_ptav or size_ptav.product_tmpl_id != product_template:
                continue

            size_attribute = size_ptav.attribute_line_id.attribute_id
            base_combination = selected_ptavs.filtered(
                lambda ptav: ptav.attribute_line_id.attribute_id != size_attribute
            )
            combination = base_combination + size_ptav
            variant = product_template._get_variant_for_combination(combination)

            if not variant or not variant._is_add_to_cart_allowed():
                warnings.append(_("Some selected size combinations are unavailable."))
                continue

            values = order_sudo.with_context(skip_cart_verification=True)._cart_add(
                product_id=variant.id,
                quantity=line["qty"],
            )
            added_qty = max(values.get("added_qty", 0), 0)
            if added_qty:
                total_added += added_qty
                sizes_added += 1

        if total_added:
            order_sudo._verify_cart_after_update()

        if not total_added:
            message = _("No sizes were added. Please review selected options.")
            if warnings:
                message = warnings[0]
            return {"ok": False, "message": message, "cart_quantity": order_sudo.cart_quantity}

        success_message = _("Added %(qty)s unit(s) across %(sizes)s size type(s).") % {
            "qty": total_added,
            "sizes": sizes_added,
        }
        if warnings:
            success_message = "%s %s" % (success_message, warnings[0])

        return {
            "ok": True,
            "message": success_message,
            "cart_quantity": order_sudo.cart_quantity,
            "total_added": total_added,
            "sizes_added": sizes_added,
        }
