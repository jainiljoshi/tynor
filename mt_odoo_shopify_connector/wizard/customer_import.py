# -*- coding: utf-8 -*-
import logging
from odoo.exceptions import UserError
from odoo import models, api, _, fields

_logger = logging.getLogger(__name__)
class ResPartnerInstance(models.TransientModel):
    _name = 'res.partner.instance.exp'
    _description = 'Customer Export'

    shopify_instance_id = fields.Many2one('shopify.instance')

    def customer_instance_for_exp(self):
        instance_id = self.shopify_instance_id
        self.env['res.partner'].export_customers(instance_id)
        
    @api.model
    def default_get(self, fields):
        res = super(ResPartnerInstance, self).default_get(fields)
        try:
            instance = self.env['shopify.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please set up and configure a Shopify instance."))

        if instance:
            res['shopify_instance_id'] = instance.id

        if self.env['shopify.instance']._context.get('shopify_instance_id'):
            res['shopify_instance_id'] = self.env['shopify.instance']._context.get('shopify_instance_id')

        return res


class ResPartnerInstanceImp(models.TransientModel):
    _name = 'res.partner.instance.imp'
    _description = 'Customer Import'

    shopify_instance_id = fields.Many2one('shopify.instance')
    is_restart_import = fields.Boolean(string="Restart Import", default=False)
    current_count_display = fields.Char(readonly=True)
   
    def customer_instance_for_imp(self):
        instance_id = self.shopify_instance_id
        
        if self.is_restart_import:
            self.env['customer.import.tracking'].clear_all_rows()
        
        if not self.env['customer.import.tracking'].is_import_completed() :
            if not self.env['customer.import.tracking'].is_cool_off_minutes_passed() :
                return self.env['message.wizard'].fail("Previous import is running. Please try after some time!!!")

        cron_lock = self.env['shopify.cron.job.lock'].search([('name', '=', 'cron_import_shopify_customers')], limit=1)
        if cron_lock and cron_lock.is_running:
            _logger.info("\n\n\nThe cron job for importing customers is already running. Please try after some time.\n\n")
            return self.env['message.wizard'].fail("The cron job for importing customers is already running. Please try after some time.")
        
        self.env['res.partner'].import_customer(instance_id)

        
        current_instance = self.env['shopify.instance'].sudo().search([('id','=',self.shopify_instance_id.id)],limit=1)
        customer_action = current_instance.get_customers()
        customer_action['customer_action'].update({'target': "main",})
        return customer_action['customer_action']
  
          
    @api.model
    def default_get(self, fields):
        res = super(ResPartnerInstanceImp, self).default_get(fields)
        try:
            instance = self.env['shopify.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("\n\n\nPlease set up and configure a Shopify instance.\n\n"))
        
        if instance:
            res['shopify_instance_id'] = instance.id
            
            
        counts = self.env['customer.import.tracking'].get_import_counts()
        
        if int(counts['total_count']) != 0:
            res['current_count_display'] = f"{counts['imported_count']} customers have been imported out of a total of {counts['total_count']}"

        return res

