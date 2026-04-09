from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    tynor_source_invoice_id = fields.Many2one("account.move", string="Source Invoice", index=True, copy=False, readonly=True)
    tynor_external_order_no = fields.Char(string="External Order No", copy=False, readonly=True)
    tynor_external_payment_method = fields.Char(string="External Payment Method", copy=False, readonly=True)
    tynor_bridge_generated = fields.Boolean(default=False, copy=False, readonly=True)

