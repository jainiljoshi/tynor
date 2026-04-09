from odoo import models, fields, api, _
from odoo.exceptions import UserError

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    x_wholesale_tax_id = fields.Char(string='Tax ID / ABN')
    x_wholesale_business_type = fields.Selection([
        ('pharmacy', 'Pharmacy'),
        ('physio', 'Physiotherapist'),
        ('retail', 'Retailer'),
        ('distributor', 'Distributor')
    ], string='Business Type')

    def action_approve_wholesale(self):
        for lead in self:
            # Create partner if not exist
            if not lead.partner_id:
                lead._handle_partner_assignment()
            
            partner = lead.partner_id
            if not partner:
                raise UserError(_("Could not create or find a partner for this lead."))

            # 1. Assign Wholesale VIP Pricelist
            wholesale_pricelist = self.env.ref('tynor_b2b_wholesale.list_b2b_wholesale_vip', raise_if_not_found=False)
            if wholesale_pricelist:
                partner.property_product_pricelist = wholesale_pricelist.id
            
            # 2. Assign Wholesale Tag
            wholesale_tag = self.env.ref('tynor_b2b_wholesale.res_partner_category_wholesale', raise_if_not_found=False)
            if not wholesale_tag:
                wholesale_tag = self.env['res.partner.category'].create({'name': 'Wholesale'})
                self.env['ir.model.data'].create({
                    'name': 'res_partner_category_wholesale',
                    'module': 'tynor_b2b_wholesale',
                    'model': 'res.partner.category',
                    'res_id': wholesale_tag.id
                })
            partner.category_id = [(4, wholesale_tag.id)]

            # 3. Grant Portal Access
            portal_wizard = self.env['portal.wizard'].create({
                'user_ids': [(0, 0, {
                    'partner_id': partner.id,
                    'email': partner.email or lead.email_from,
                })]
            })
            portal_wizard.user_ids.action_grant_access()
            
            # 4. Notify success
            lead.message_post(body=_("Wholesale Account Approved! Portal invitation sent to the customer."))
            lead.action_set_won()
