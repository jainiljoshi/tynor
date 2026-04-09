# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, _, api, fields


class ShopifyUpdateInventory(models.Model):
    _name = 'shopify.inventory.update'
    _description = 'Shopify inventory update'

    shopify_instance_id = fields.Many2one('shopify.instance')
    current_message_display = fields.Char(readonly=True)     

    def import_shopify_inventory(self):
               
        if not self.env['inventory.import.tracking'].is_import_completed() :
            if not self.env['inventory.import.tracking'].is_cool_off_minutes_passed() :
                return self.env['message.wizard'].fail("Previous import is running. Please try after some time!!!")        
        
        return self.env['product.template'].import_shopify_inventory(self.shopify_instance_id)

    
    @api.model
    def default_get(self, fields):
        res = super(ShopifyUpdateInventory, self).default_get(fields)
        try:
            instance = self.env['shopify.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please set up and configure a Shopify instance."))

        if instance:
            res['shopify_instance_id'] = instance.id

        res['current_message_display'] = "Import orders before importing inventory to ensure accurate inventory updates."
        if self.env['shopify.inventory.import.time'].is_imported():
            res['current_message_display'] = "The inventory has already been imported once. Importing again may cause incorrect inventory values.\n\nThis action is blocked."
        elif not self.env['inventory.import.tracking'].is_import_completed():
            res['current_message_display'] = "Import not completed. Please continue importing to complete the process."            

        return res

class ShopifyExportInventory(models.Model):
    _name = 'shopify.export.update'
    _description = 'Shopify export update'

    shopify_instance_id = fields.Many2one('shopify.instance')

    def export_shopify_inventory(self):
        return self.env['product.template'].export_inventory(self.shopify_instance_id)

    
    @api.model
    def default_get(self, fields):
        res = super(ShopifyExportInventory, self).default_get(fields)
        try:
            instance = self.env['shopify.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please set up and configure a Shopify instance."))

        if instance:
            res['shopify_instance_id'] = instance.id

        return res