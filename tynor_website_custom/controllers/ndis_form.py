from odoo import http, _
from odoo.http import request


class TynorNdisFormController(http.Controller):
    def _is_ndis_enabled(self):
        return request.env["ir.config_parameter"].sudo().get_param("tynor.ndis_enabled", default="1") == "1"

    @http.route("/ndis", type="http", auth="public", website=True)
    def ndis_page(self, **kwargs):
        if not self._is_ndis_enabled():
            return request.redirect("/")
        products = request.env["product.product"].sudo().search(
            [
                ("sale_ok", "=", True),
                ("product_tmpl_id.website_published", "=", True),
                ("active", "=", True),
            ],
            order="name asc",
            limit=500,
        )
        return request.render("tynor_website_custom.ndis_page", {"products": products, "selected_product_ids": []})

    @http.route("/ndis/thank-you", type="http", auth="public", website=True)
    def ndis_thank_you(self, **kwargs):
        if not self._is_ndis_enabled():
            return request.redirect("/")
        return request.render("tynor_website_custom.ndis_thank_you", {})

    @http.route("/ndis/submit", type="http", auth="public", website=True, methods=["POST"], csrf=True)
    def ndis_submit(self, **post):
        if not self._is_ndis_enabled():
            return request.redirect("/")
        required_fields = {
            "ndis_number": _("NDIS Number"),
            "plan_type": _("Plan Type"),
            "participant_name": _("Participant Name"),
            "email": _("Email"),
            "date_of_birth": _("Date of Birth"),
            "shipping_address": _("Shipping Address"),
            "invoice_email": _("Invoice Email"),
        }
        product_ids = request.httprequest.form.getlist("product_ids")
        clean_product_ids = [int(pid) for pid in product_ids if str(pid).isdigit()]

        missing = [label for key, label in required_fields.items() if not (post.get(key) or "").strip()]
        if not clean_product_ids:
            missing.append(_("Products"))
        if missing:
            return request.render(
                "tynor_website_custom.ndis_page",
                {
                    "products": request.env["product.product"].sudo().search(
                        [("sale_ok", "=", True), ("product_tmpl_id.website_published", "=", True)],
                        order="name asc",
                        limit=500,
                    ),
                    "error": _("Please complete required fields: %s") % ", ".join(missing),
                    "form_vals": post,
                    "selected_product_ids": clean_product_ids,
                },
            )

        vals = {
            "ndis_number": (post.get("ndis_number") or "").strip(),
            "plan_type": (post.get("plan_type") or "").strip(),
            "participant_name": (post.get("participant_name") or "").strip(),
            "email": (post.get("email") or "").strip(),
            "date_of_birth": post.get("date_of_birth") or False,
            "shipping_address": (post.get("shipping_address") or "").strip(),
            "phone": (post.get("phone") or "").strip(),
            "plan_start_date": post.get("plan_start_date") or False,
            "plan_end_date": post.get("plan_end_date") or False,
            "invoice_email": (post.get("invoice_email") or "").strip(),
            "product_ids": [(6, 0, clean_product_ids)],
        }
        ndis = request.env["tynor.ndis.order"].sudo().create(vals)

        template = request.env.ref("tynor_website_custom.mail_template_tynor_ndis_order", raise_if_not_found=False)
        if template:
            template.sudo().send_mail(
                ndis.id,
                force_send=True,
                email_values={"email_to": ndis.email},
            )

        internal_email = request.env["ir.config_parameter"].sudo().get_str("tynor.ndis_notification_email") or \
            "info@tynoraus.com.au"
        recipients = [internal_email]
        if ndis.invoice_email and ndis.invoice_email not in recipients:
            recipients.append(ndis.invoice_email)
        if template and recipients:
            template.sudo().send_mail(
                ndis.id,
                force_send=True,
                email_values={"email_to": ",".join(recipients)},
            )

        return request.redirect("/ndis/thank-you")
