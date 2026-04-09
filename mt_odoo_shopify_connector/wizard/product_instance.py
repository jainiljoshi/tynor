# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, _, api, fields
import logging

_logger = logging.getLogger(__name__)
class ShopifyProductInstanceExp(models.Model):
    _name = 'shopify.product.instance.exp'
    _description = 'Product Export Instance'

    shopify_instance_id = fields.Many2one('shopify.instance', string="Shopify Instance")
    # is_update = fields.Boolean(string="Sync Product To Shopify?")

    def product_instance_selected_for_exp(self):
        # self.is_update
        self.env['product.template'].export_product(self.shopify_instance_id)

    @api.model
    def default_get(self, fields):
               
        res = super(ShopifyProductInstanceExp, self).default_get(fields)
        try:
            instance = self.env['shopify.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please set up and configure a Shopify instance."))

        if instance:
            res['shopify_instance_id'] = instance.id
        
        if self.env['shopify.instance']._context.get('shopify_instance_id'):
            res['shopify_instance_id'] = self.env['shopify.instance']._context.get('shopify_instance_id')
                          
        return res


class ShopifyProductInstanceImp(models.Model):
    _name = 'shopify.product.instance.imp'
    _description = 'Product Import Instance'

    shopify_instance_id = fields.Many2one('shopify.instance')
    is_force_update = fields.Boolean(string="Force Import and Update From Shopify", default=False)
    is_restart_import = fields.Boolean(string="Restart Import", default=False)
    current_count_display = fields.Char(readonly=True)

    def product_instance_selected_for_imp(self):

        if self.is_restart_import:
            self.env['product.import.tracking'].clear_all_rows()
        
        if not self.env['product.import.tracking'].is_import_completed() :
            if not self.env['product.import.tracking'].is_cool_off_minutes_passed() :
                return self.env['message.wizard'].fail("Previous import is running. Please try after some time!!!")         
        
        self.env['product.template'].import_product(self.shopify_instance_id, self.is_force_update)
        
        current_instance = self.env['shopify.instance'].sudo().search([('id','=',self.shopify_instance_id.id)],limit=1)
        product_action = current_instance.get_products()
        product_action['product_action'].update({'target': "main",})
        return product_action['product_action']

    @api.model
    def default_get(self, fields):
        res = super(ShopifyProductInstanceImp, self).default_get(fields)
        try:
            instance = self.env['shopify.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please set up and configure a Shopify instance."))

        if instance:
            res['shopify_instance_id'] = instance.id

        counts = self.env['product.import.tracking'].get_import_counts()
        
        if int(counts['total_count']) != 0:
            res['current_count_display'] = f"{counts['imported_count']} products have been imported out of a total of {counts['total_count']}"
        return res
