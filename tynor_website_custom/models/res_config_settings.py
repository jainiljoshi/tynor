from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    tynor_new_wholesaler_notification_active = fields.Boolean(
        string="Enable New Wholesaler Banner",
        config_parameter="tynor.new_wholesaler_notification_active",
        default=False,
    )
    tynor_new_wholesaler_notification_text = fields.Text(
        string="New Wholesaler Banner Text",
        config_parameter="tynor.new_wholesaler_notification_text",
        default="A new wholesale partner has joined our network!",
    )
    x_tynor_auto_invoice_card = fields.Boolean(
        string="Auto Invoice + Auto Pay for Card Methods",
        config_parameter="tynor.auto_invoice_card",
        default=True,
    )
    x_tynor_auto_invoice_bank_require_validation = fields.Boolean(
        string="Bank/Net30 Requires Manual Invoice Validation",
        config_parameter="tynor.auto_invoice_bank_require_validation",
        default=True,
    )
    x_tynor_ndis_notification_email = fields.Char(
        string="NDIS Internal Notification Email",
        config_parameter="tynor.ndis_notification_email",
        default="info@tynoraus.com.au",
    )
