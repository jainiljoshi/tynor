from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tynor_size_chart_image = fields.Image(
        string="Size Chart Image",
        max_width=1920,
        max_height=1920,
        help="Shown on the website product page in a Size Chart popup.",
    )
    tynor_size_chart_title = fields.Char(
        string="Size Chart Title",
        default="Size Chart",
        help="Title shown in the website size chart popup.",
    )
    tynor_enable_bulk_size_order = fields.Boolean(
        string="Enable Quick Size Ordering",
        default=True,
        help="Show one-line multi-size quantity inputs on the website product page.",
    )
    tynor_size_attribute_id = fields.Many2one(
        "product.attribute",
        string="Size Attribute",
        help="Optional. Select the attribute to use for quick size ordering.",
    )

    def _tynor_get_size_attribute_line(self):
        self.ensure_one()
        candidate_lines = self.valid_product_template_attribute_line_ids.filtered(
            lambda line: line.attribute_id.create_variant == "always"
            and line.product_template_value_ids._only_active()
        )
        if self.tynor_size_attribute_id:
            configured_line = candidate_lines.filtered(
                lambda line: line.attribute_id == self.tynor_size_attribute_id
            )[:1]
            if configured_line:
                return configured_line
        return candidate_lines.filtered(
            lambda line: "size" in (line.attribute_id.name or "").lower()
        )[:1]

    def _tynor_get_bulk_size_context(self):
        self.ensure_one()
        size_line = self._tynor_get_size_attribute_line()
        if not size_line:
            return {"size_attribute_id": False, "options": []}

        base_combination = self._get_first_possible_combination()
        size_attribute = size_line.attribute_id
        base_without_size = base_combination.filtered(
            lambda ptav: ptav.attribute_line_id.attribute_id != size_attribute
        )

        website = self.env["website"].get_current_website()
        currency = website.currency_id
        symbol = currency.symbol or ""
        position = currency.position or "after"
        decimals = currency.decimal_places or 2

        size_options = []
        for ptav in size_line.product_template_value_ids._only_active():
            combination = base_without_size + ptav
            combination_info = self._get_combination_info(combination=combination, add_qty=1.0)
            price = combination_info.get("price", 0.0)

            if position == "before":
                price_display = f"{symbol}{price:.{decimals}f}"
            else:
                price_display = f"{price:.{decimals}f}{symbol and (' ' + symbol)}"

            size_options.append({
                "ptav_id": ptav.id,
                "label": ptav.name,
                "price": price,
                "price_display": price_display,
            })

        return {
            "size_attribute_id": size_line.attribute_id.id,
            "options": size_options,
            "currency_symbol": symbol,
            "currency_position": position,
            "currency_decimals": decimals,
        }
