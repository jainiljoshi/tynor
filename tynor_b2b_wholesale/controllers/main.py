from odoo import http
from odoo.http import request


class B2BWholesaleController(http.Controller):

    @http.route(['/wholesale'], type='http', auth="public", website=True)
    def b2b_wholesale_landing(self, **kw):
        """ Render the Wholesale Program marketing landing page """
        return request.render('tynor_b2b_wholesale.b2b_landing_page', {})

    @http.route(['/b2b/apply'], type='http', auth="public", website=True)
    def b2b_wholesale_apply(self, **kw):
        """ Render the Wholesale Application form """
        return request.render('tynor_b2b_wholesale.b2b_application_page', {})

    @http.route(['/b2b/submit'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def b2b_wholesale_submit(self, **post):
        """ Process the submitted form and create a CRM Lead """
        
        company_name = post.get('company_name')
        contact_name = post.get('contact_name')
        email_from = post.get('email_from')
        phone = post.get('phone')
        tax_id = post.get('x_wholesale_tax_id')
        business_type = post.get('x_wholesale_business_type')
        street = post.get('street')
        city = post.get('city')
        zip_code = post.get('zip_code')
        notes = post.get('notes')

        # Format Lead Name
        lead_name = f"Wholesale Application - {company_name or contact_name}"

        # Create CRM Lead via sudo (since public user has no create rights on crm.lead)
        lead_vals = {
            'name': lead_name,
            'partner_name': company_name,
            'contact_name': contact_name,
            'email_from': email_from,
            'phone': phone,
            'x_wholesale_tax_id': tax_id,
            'x_wholesale_business_type': business_type,
            'street': street,
            'city': city,
            'zip': zip_code,
            'description': notes,
            'type': 'lead',
        }
        
        request.env['crm.lead'].sudo().create(lead_vals)

        return request.render('tynor_b2b_wholesale.b2b_application_success', {})
