from odoo import models, fields, api, _

class CrmLeadWholesaleManagement(models.Model):
    _inherit = 'crm.lead'

    def action_approve_wholesale(self):
        # Let the base b2b_wholesale module do its approval magic (portal, pricelist)
        res = super(CrmLeadWholesaleManagement, self).action_approve_wholesale()
        
        for lead in self:
            partner = lead.partner_id
            if partner:
                # Schedule a To-Do Activity for 3 days from now
                activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
                if activity_type:
                    self.env['mail.activity'].create({
                        'res_name': partner.name,
                        'res_id': partner.id,
                        'res_model_id': self.env['ir.model']._get('res.partner').id,
                        'activity_type_id': activity_type.id,
                        'summary': 'Wholesale Onboarding Check-in',
                        'note': '<p>Check if this new wholesale partner has logged into the portal and placed their first MOQ order.</p>',
                        'date_deadline': fields.Date.add(fields.Date.today(), days=3),
                        'user_id': self.env.user.id,
                    })
        return res
