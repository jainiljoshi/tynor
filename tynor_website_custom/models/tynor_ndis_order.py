from odoo import api, fields, models


class TynorNdisOrder(models.Model):
    _name = "tynor.ndis.order"
    _description = "NDIS Order Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(string="Reference", readonly=True, default="New", tracking=True)
    ndis_number = fields.Char(string="NDIS Number", required=True, tracking=True)
    plan_type = fields.Selection(
        [
            ("self_managed", "Self-Managed"),
            ("plan_managed", "Plan-Managed"),
            ("ndia_managed", "NDIA-Managed"),
        ],
        string="Plan Type",
        required=True,
        tracking=True,
    )
    participant_name = fields.Char(string="Participant Full Name", required=True, tracking=True)
    email = fields.Char(string="Email", required=True, tracking=True)
    date_of_birth = fields.Date(string="Date of Birth", required=True)
    shipping_address = fields.Text(string="Full Shipping Address", required=True)
    phone = fields.Char(string="Phone Number")
    plan_start_date = fields.Date(string="Plan Start Date")
    plan_end_date = fields.Date(string="Plan End Date")
    product_ids = fields.Many2many("product.product", string="Products Required")
    invoice_email = fields.Char(string="Invoice Email", required=True)
    state = fields.Selection(
        [
            ("new", "New"),
            ("processing", "Processing"),
            ("order_created", "Order Created"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="new",
        tracking=True,
    )
    sale_order_id = fields.Many2one("sale.order", string="Sale Order", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Partner", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("tynor.ndis.order") or "New"
        return super().create(vals_list)

    def action_show_sale_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.sale_order_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_sale_order(self):
        SaleOrder = self.env["sale.order"].sudo()
        Partner = self.env["res.partner"].sudo()

        for rec in self:
            partner = Partner.search([("email", "=", rec.email)], limit=1)
            if not partner:
                partner_vals = {
                    "name": rec.participant_name,
                    "email": rec.email,
                    "phone": rec.phone,
                    "street": (rec.shipping_address or "")[:255],
                    "type": "contact",
                }
                partner = Partner.create(partner_vals)

            if rec.sale_order_id:
                continue

            order = SaleOrder.create(
                {
                    "partner_id": partner.id,
                    "partner_invoice_id": partner.id,
                    "partner_shipping_id": partner.id,
                    "client_order_ref": rec.name,
                    "note": f"NDIS Request: {rec.name}\nNDIS Number: {rec.ndis_number}",
                }
            )

            line_vals = []
            for product in rec.product_ids:
                line_vals.append(
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": product.display_name,
                            "product_uom_qty": 1.0,
                            "price_unit": product.lst_price,
                        },
                    )
                )
            if line_vals:
                order.write({"order_line": line_vals})

            rec.write({"sale_order_id": order.id, "partner_id": partner.id, "state": "order_created"})

        return True
