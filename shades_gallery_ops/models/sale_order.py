from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    shades_installation_job_id = fields.Many2one("shades.installation.job", string="Installation Job", copy=False)
    shades_paid_amount = fields.Monetary(string="Paid Amount", currency_field="currency_id", compute="_compute_shades_payment_stats")
    shades_balance_due = fields.Monetary(string="Balance Due", currency_field="currency_id", compute="_compute_shades_payment_stats")
    shades_paid_ratio = fields.Float(string="Paid Ratio", compute="_compute_shades_payment_stats")

    def _compute_shades_payment_stats(self):
        for order in self:
            invoices = order.invoice_ids.filtered(lambda m: m.state == "posted" and m.move_type == "out_invoice")
            total = sum(invoices.mapped("amount_total"))
            residual = sum(invoices.mapped("amount_residual"))
            paid = total - residual
            order.shades_paid_amount = paid
            order.shades_balance_due = residual
            order.shades_paid_ratio = (paid / total) if total else 0.0

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            # Requirement: confirmation should immediately generate invoice draft(s).
            if order.state in ("sale", "done") and not order.invoice_ids.filtered(lambda m: m.move_type == "out_invoice"):
                order._create_invoices()
        return res
