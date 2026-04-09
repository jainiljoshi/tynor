# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, api, _, fields

import shopify
import logging

_logger = logging.getLogger(__name__)

class SaleOrderInstance(models.TransientModel):
    _name = 'sale.order.instance.exp'
    _description = 'Sales Order Export'

    shopify_instance_id = fields.Many2one('shopify.instance')

    def sale_order_instance_for_exp(self):
        instance_id = self.shopify_instance_id
        self.env['sale.order'].export_selected_so(instance_id)
        
        return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                }

    @api.model
    def default_get(self, fields):
        res = super(SaleOrderInstance, self).default_get(fields)
        try:
            instance = self.env['shopify.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please set up and configure a Shopify instance."))

        if instance:
            res['shopify_instance_id'] = instance.id

        if self.env['shopify.instance']._context.get('shopify_instance_id'):
            res['shopify_instance_id'] = self.env['shopify.instance']._context.get('shopify_instance_id')
                        
        return res


class SaleOrderInstanceImp(models.Model):
    _name = 'sale.order.instance.imp'
    _description = 'Sales Order Import'

    shopify_instance_id = fields.Many2one('shopify.instance')
    is_restart_import = fields.Boolean(string="Restart Import", default=False)
    is_all_import = fields.Boolean(string="Import All Orders (Last 2 Months)*", default=False)
    current_count_display = fields.Char(readonly=True)     

    def sale_order_instance_for_imp(self):
        instance_id = self.shopify_instance_id
        order_status = "open"
        
        if self.is_restart_import:
            self.env['sale.order.import.tracking'].clear_all_rows()
        
        if not self.env['sale.order.import.tracking'].is_import_completed() :
            if not self.env['sale.order.import.tracking'].is_cool_off_minutes_passed() :
                return self.env['message.wizard'].fail("Previous import is running. Please try after some time!!!")
            
        cron_lock = self.env['shopify.cron.job.lock'].search([('name', '=', 'cron_import_shopify_orders')], limit=1)
        if cron_lock and cron_lock.is_running:
            _logger.info("\n\n\nThe cron job for importing orders is already running. Please try after some time.\n\n")
            return self.env['message.wizard'].fail("The cron job for importing orders is already running. Please try after some time.")
        
        if self.is_all_import:
            order_status = "any"
        
        self.env['sale.order'].import_sale_order(instance_id, order_status)

        current_instance = self.env['shopify.instance'].sudo().search([('id','=',self.shopify_instance_id.id)],limit=1)
        order_action = current_instance.get_total_orders()
        return order_action['order_action']

    @api.model
    def default_get(self, fields):
        res = super(SaleOrderInstanceImp, self).default_get(fields)
        try:
            instance = self.env['shopify.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please set up and configure a Shopify instance."))

        if instance:
            res['shopify_instance_id'] = instance.id
            
        if self.env['shopify.instance']._context.get('shopify_instance_id'):
            res['shopify_instance_id'] = self.env['shopify.instance']._context.get('shopify_instance_id')

        counts = self.env['sale.order.import.tracking'].get_import_counts()
        
        if int(counts['total_count']) != 0:
            # res['current_count_display'] = f"{counts['imported_count']} orders have been imported out of a total of {counts['total_count']}"
            res['current_count_display'] = "Import was not completed. Please continue with the import to finish the process."
              
        return res
