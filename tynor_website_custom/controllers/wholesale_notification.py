from odoo import http
from odoo.http import request


class TynorWholesaleNotificationController(http.Controller):
    @http.route("/tynor/wholesale_notification", type="json", auth="user")
    def wholesale_notification(self):
        partner = request.env.user.partner_id
        is_wholesale = partner._is_tynor_wholesale_partner()
        params = request.env["ir.config_parameter"].sudo()
        active = (params.get_str("tynor.new_wholesaler_notification_active") or "False").lower() in (
            "1",
            "true",
            "yes",
        )
        text = params.get_str("tynor.new_wholesaler_notification_text") or \
            "Welcome to our growing wholesale network! A new wholesaler has joined."
        return {
            "show": bool(active and is_wholesale),
            "text": text,
        }
