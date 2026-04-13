from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tynor_retail_price = fields.Monetary(
        string="Retail Price (AUD)",
        currency_field="currency_id",
        help="Reference retail price shown for savings calculations.",
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    tynor_retail_price = fields.Monetary(
        string="Retail Price (AUD)",
        currency_field="currency_id",
        related="product_tmpl_id.tynor_retail_price",
        readonly=False,
        store=True,
    )

