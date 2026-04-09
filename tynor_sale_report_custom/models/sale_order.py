from odoo import _, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_tynor_quotation_send(self):
        self.ensure_one()
        action = self.with_context(
            hide_default_template=True,
            validate_analytic=True,
            check_document_layout=True,
        ).action_quotation_send()

        template = self.env.ref(
            "tynor_sale_report_custom.mail_template_sale_order_tynor_custom_send",
            raise_if_not_found=False,
        )
        if template:
            action_context = dict(action.get("context", {}))
            action_context.update(
                {
                    "default_use_template": True,
                    "default_template_id": template.id,
                    "mark_so_as_sent": self.state == "draft",
                    "force_email": True,
                }
            )
            action["context"] = action_context
        action["name"] = _("Send")
        return action
