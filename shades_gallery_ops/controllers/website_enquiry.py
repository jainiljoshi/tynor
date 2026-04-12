from odoo import http
from odoo.http import request


class ShadesWebsiteEnquiryController(http.Controller):
    @http.route(["/enquiry"], type="http", auth="public", website=True)
    def shades_enquiry_form(self, **kwargs):
        return request.render("shades_gallery_ops.shades_enquiry_page", {})

    @http.route(["/enquiry/submit"], type="http", auth="public", website=True, methods=["POST"], csrf=True)
    def shades_enquiry_submit(self, **post):
        name = (post.get("name") or "").strip()
        email = (post.get("email") or "").strip()
        phone = (post.get("phone") or "").strip()
        source = (post.get("lead_source") or "website").strip()
        details = (post.get("details") or "").strip()

        lead = request.env["crm.lead"].sudo().create({
            "name": f"Website Enquiry - {name or email or 'New Lead'}",
            "contact_name": name,
            "email_from": email,
            "phone": phone,
            "description": details,
            "type": "lead",
            "shades_lead_source": source,
        })

        if lead.email_from:
            template = request.env.ref("shades_gallery_ops.mail_template_shades_enquiry_auto_reply", raise_if_not_found=False)
            if template:
                template.sudo().send_mail(lead.id, force_send=True)

        return request.render("shades_gallery_ops.shades_enquiry_thank_you", {"lead": lead})
