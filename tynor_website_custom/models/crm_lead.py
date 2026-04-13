from odoo import models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    def action_approve_wholesale(self):
        res = super().action_approve_wholesale()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("tynor.new_wholesaler_notification_active", "True")
        if not params.get_str("tynor.new_wholesaler_notification_text"):
            params.set_param(
                "tynor.new_wholesaler_notification_text",
                "Welcome to our growing wholesale network! A new wholesaler has joined.",
            )
        return res
