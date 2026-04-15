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

        website = self.env["website"].get_current_website()
        currency = website.currency_id
        symbol = currency.symbol or ""
        position = currency.position or "after"
        decimals = currency.decimal_places or 2

        return {
            "size_attribute_id": size_line.attribute_id.id,
            "size_attribute_label": size_line.attribute_id.name,
            "options": [
                {"ptav_id": ptav.id, "label": ptav.name}
                for ptav in size_line.product_template_value_ids._only_active()
            ],
            "currency_symbol": symbol,
            "currency_position": position,
            "currency_decimals": decimals,
        }
