from odoo import api, models


CARD_METHOD_KEYS = {
    "stripe",
    "card",
    "mastercard",
    "visa",
    "amex",
    "credit_card",
    "credit card",
    "shopify_payments",
    "shopify payments",
}

BANK_METHOD_KEYS = {
    "bank",
    "bpay",
    "eft",
    "net30",
    "net_30",
    "pay_on_account",
    "pay on account",
    "cash",
    "manual",
}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _tynor_method_key(self):
        self.ensure_one()
        return (self.tynor_external_payment_method or "").strip().lower().replace("-", "_")

    def _tynor_is_card_payment_method(self):
        self.ensure_one()
        key = self._tynor_method_key()
        return key in CARD_METHOD_KEYS

    def _tynor_is_bank_payment_method(self):
        self.ensure_one()
        key = self._tynor_method_key()
        return key in BANK_METHOD_KEYS

    def _tynor_auto_invoice_and_pay(self):
        params = self.env["ir.config_parameter"].sudo()
        auto_card = (params.get_str("tynor.auto_invoice_card") or "True").lower() in ("1", "true", "yes")
        bank_require_validation = (params.get_str("tynor.auto_invoice_bank_require_validation") or "True").lower() in (
            "1", "true", "yes"
        )

        for order in self:
            if order.state not in ("sale", "done"):
                continue
            if not order.tynor_external_payment_method:
                continue

            existing = order.invoice_ids.filtered(lambda m: m.move_type in ("out_invoice", "out_receipt") and m.state != "cancel")
            invoices = existing
            if not invoices and order.invoice_status == "to invoice":
                invoices = order._create_invoices(final=False)

            for invoice in invoices.filtered(lambda m: m.state in ("draft", "posted")):
                if order._tynor_is_card_payment_method():
                    if not auto_card:
                        continue
                    if invoice.state == "draft":
                        invoice.action_post()
                    if invoice.amount_residual > 0:
                        invoice._tynor_create_payment_from_bridge()
                    if invoice.payment_state == "paid" and not invoice.tynor_paid_email_sent:
                        invoice._tynor_send_paid_invoice_email()
                elif order._tynor_is_bank_payment_method():
                    if bank_require_validation:
                        # Keep draft to enforce manual validation and manual payment.
                        continue
                    if invoice.state == "draft":
                        invoice.action_post()
                else:
                    # Fallback behavior: create invoice draft only.
                    continue

    def action_confirm(self):
        res = super().action_confirm()
        self._tynor_auto_invoice_and_pay()
        return res

    @api.model
    def _cron_tynor_auto_invoice_orders(self, limit=200):
        orders = self.search(
            [
                ("state", "in", ("sale", "done")),
                ("tynor_external_payment_method", "!=", False),
                ("invoice_status", "=", "to invoice"),
            ],
            order="id asc",
            limit=limit,
        )
        orders._tynor_auto_invoice_and_pay()
        return True
