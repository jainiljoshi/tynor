from odoo import models


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


class AccountMove(models.Model):
    _inherit = "account.move"

    def _tynor_method_key(self):
        self.ensure_one()
        return (self.tynor_external_payment_method or "").strip().lower().replace("-", "_")

    def _tynor_is_card_payment_method(self):
        self.ensure_one()
        return self._tynor_method_key() in CARD_METHOD_KEYS

    def _tynor_is_bank_payment_method(self):
        self.ensure_one()
        return self._tynor_method_key() in BANK_METHOD_KEYS

    def _tynor_create_payment_from_bridge(self):
        self.ensure_one()
        if self._tynor_is_bank_payment_method():
            return False
        return super()._tynor_create_payment_from_bridge()

    def write(self, vals):
        old_states = {move.id: move.payment_state for move in self}
        result = super().write(vals)
        paid_moves = self.filtered(
            lambda move: move.move_type in ("out_invoice", "out_receipt")
            and old_states.get(move.id) != "paid"
            and move.payment_state == "paid"
            and not move.tynor_paid_email_sent
        )
        for move in paid_moves:
            move._tynor_send_paid_invoice_email()
        return result
