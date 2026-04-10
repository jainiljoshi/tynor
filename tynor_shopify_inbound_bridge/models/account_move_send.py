from odoo import models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    def _get_mail_layout(self):
        return "tynor_shopify_inbound_bridge.mail_notification_layout_with_responsible_signature_tynor"

