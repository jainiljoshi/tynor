from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_post(self):
        res = super().action_post()
        for payment in self:
            sale_orders = self.env["sale.order"]
            for invoice in payment.reconciled_invoice_ids.filtered(lambda m: m.move_type == "out_invoice"):
                sale_orders |= invoice.invoice_line_ids.sale_line_ids.order_id

            for order in sale_orders:
                if order.shades_paid_ratio >= 0.5 and not order.shades_installation_job_id:
                    job = self.env["shades.installation.job"].create({
                        "name": f"{order.name} - Installation",
                        "sale_order_id": order.id,
                        "stage": "deposit_received",
                    })
                    order.shades_installation_job_id = job.id
        return res
