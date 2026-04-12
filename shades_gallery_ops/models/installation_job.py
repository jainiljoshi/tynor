from odoo import fields, models


class ShadesInstallationJob(models.Model):
    _name = "shades.installation.job"
    _description = "Shades Installation Job"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    sale_order_id = fields.Many2one("sale.order", required=True, ondelete="cascade", tracking=True)
    partner_id = fields.Many2one(related="sale_order_id.partner_id", store=True)
    email = fields.Char(related="partner_id.email", store=True)
    stage = fields.Selection(
        [
            ("deposit_received", "Deposit Received"),
            ("order_placed", "Order Placed with Supplier"),
            ("production", "Production in Progress"),
            ("ready_install", "Ready for Installation"),
            ("install_scheduled", "Installation Scheduled"),
            ("install_completed", "Installation Completed"),
        ],
        default="deposit_received",
        required=True,
        tracking=True,
    )
    expected_date = fields.Date(string="Expected Date")

    def write(self, vals):
        stage_before = {rec.id: rec.stage for rec in self}
        res = super().write(vals)
        if "stage" in vals:
            for rec in self:
                if stage_before.get(rec.id) != rec.stage:
                    rec._send_stage_update_email()
                    if rec.stage == "install_scheduled" and rec.sale_order_id.shades_balance_due > 0:
                        rec._send_final_payment_reminder()
        return res

    def _send_stage_update_email(self):
        self.ensure_one()
        if not self.partner_id.email:
            return
        template = self.env.ref("shades_gallery_ops.mail_template_shades_stage_update", raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def _send_final_payment_reminder(self):
        self.ensure_one()
        if not self.partner_id.email:
            return
        template = self.env.ref("shades_gallery_ops.mail_template_shades_final_payment", raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
