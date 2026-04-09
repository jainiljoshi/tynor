# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class ShopifyStockInventory(models.Model):
    _name = 'shopify.stock.quant'
    _description = 'Shopify Stock Inventory'

    inventory_item_id = fields.Char('Shopify Inventory Item Id')
    inventory_quantity = fields.Char('Shopify inventory Quantity')
    location_id = fields.Char('Shopify Location ID')
    
    product_id = fields.Many2one('product.product', string='Product Id')
    shopify_instance_id = fields.Many2one('shopify.instance', string="Shopify Instance")    
    
    def inventory_adjustment_operation(self, p_inventory_data):
        if p_inventory_data:
            for p_id, inv_item_id, p_qty, inv_loc in p_inventory_data:
                val = {
                        'product_id': p_id,
                        'inventory_item_id': inv_item_id,
                        'location_id': inv_loc,                         
                        'inventory_quantity': p_qty
                        }
                old_inv = self.env['shopify.stock.quant'].sudo().search(
                [('inventory_item_id', '=', inv_item_id),('product_id', '=', p_id)], limit=1)
                if old_inv:
                    inv_item = old_inv.write(val)
                else:
                    inv_item = self.create(val)

class StockInventory(models.Model):
    _inherit = "stock.quant"

    def inventory_adjustment_operation(self, p_inventory_data, location_id, auto_apply=False, name=""):
        
        quant_list = self.env['stock.quant']
        if p_inventory_data and location_id:
            for p_id, new_qty in p_inventory_data.items():
                val = {
                        'product_id': p_id,
                        'location_id': location_id.id,                         
                        'inventory_quantity': float(new_qty)
                        # 'new_quantity': float(new_qty)
                        }
                _logger.info("Product ID: %s with Qty: %s" % (p_id, new_qty))
                quant_list += self.with_context(inventory_mode=True).create(val)
            if auto_apply and quant_list:
                quant_list.filtered(lambda x: x.product_id.tracking not in ['lot', 'serial']).with_context(
                    inventory_name=name).action_apply_inventory()
        return quant_list
    
    @api.model
    def create(self, vals):
        quant = super(StockInventory, self).create(vals)

        if quant.quantity != 0:        
            if quant.product_id:
                quant.product_id.write({
                    'stock_update_status': 'changed',
                    'last_stock_update': fields.Datetime.now(),
                })
        return quant

    def write(self, vals):
        try:
            if 'quantity' in vals:
                for quant in self:
                    if quant.product_id and quant.product_id.shopify_variant_id:
                        #to check weather the quant changes to a warehouse only.
                        if quant.location_id and quant.location_id.warehouse_id:
                            old_quantity = quant.quantity
                            new_quantity = vals.get('quantity', old_quantity)

                            if new_quantity != old_quantity:
                                quant.product_id.write({
                                    'stock_update_status': 'changed',
                                    'last_stock_update': fields.Datetime.now(),
                                })
        except Exception as error:
            _logger.info('\n\n\n\n stock_update_status failed - %s \n\n\n\n\n', error)
            
        return super(StockInventory, self).write(vals) 


        