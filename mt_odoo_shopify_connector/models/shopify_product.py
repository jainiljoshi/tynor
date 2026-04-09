# -*- coding: utf-8 -*-
import mimetypes
import base64
import requests
import logging
import time
import shopify
from .shopify_graphql_api import ShopifyGraphQLAPI

from datetime import timedelta, datetime
from odoo.exceptions import UserError, MissingError
from odoo import models, api, fields, _
from odoo.tools import config
from bs4 import BeautifulSoup
config['limit_time_real'] = 10000000
config['limit_time_cpu'] = 150


_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = 'product.product'

    shopify_variant_id = fields.Char('Shopify ID')
    shopify_variant_title = fields.Char('Shopify Variant Title')    
    shopify_regular_price = fields.Float('Shopify Regular Price')
    shopify_varient_description = fields.Text('Shopify Variant Description')
    shopify_sale_price = fields.Float('Shopify Sales Price')
    shopify_inventory_id = fields.Char('Shopify Inventory Id')
    shopify_image_id = fields.Char('Shopify Image Id', related = "shopify_product_image_id.image_shopify_id", store=True)
    shopify_product_free_qty = fields.Float("Shopify Stock Quantity")
    last_stock_update = fields.Datetime(string="Last Stock Update", readonly=True)
    stock_update_status = fields.Char(string="Stock Update Status", default="new")
    
    is_exported = fields.Boolean('Synced In Shopify', default=False)
        
    shopify_instance_id = fields.Many2one('shopify.instance', ondelete='cascade')    
    shopify_product_image_id = fields.Many2one('shopify.product.image')
        
    def _compute_product_price_extra(self):
        for product in self:
            if product.shopify_variant_id:
                product.price_extra = product.shopify_sale_price - product.list_price # to remove the base price if the product is from shopify
            else:
                product.price_extra = sum(product.product_template_attribute_value_ids.mapped('price_extra'))
                   
    def mark_as_completed(self):
        self.write({'stock_update_status': 'completed'})


class Product(models.Model):
    _inherit = 'product.template'

    @api.model
    def default_get(self, fields):
        res = super(Product, self).default_get(fields)
        if self.env['shopify.instance']._context.get('shopify_instance_id'):
            res['shopify_instance_id'] = self.env['shopify.instance']._context.get('shopify_instance_id')
            
        res['type'] = "product"
        
        return res

    shopify_id = fields.Char('Shopify ID', index=True)
    shopify_regular_price = fields.Float('Shopify Regular Price')
    shopify_sale_price = fields.Float('Shopify Sale Price')
    shopify_product_status = fields.Char('Shopify Product Status')
    shopify_barcode = fields.Char('Shopify Barcode')
    shopify_sku = fields.Char('Shopify SKU')
    shopify_product_scope = fields.Char('Shopify Product Scope')
    shopify_product_weight = fields.Float("Shopify Weight")
    shopify_product_qty = fields.Float("Shopify Stock Quantity")

    is_shopify_product = fields.Boolean('Is Shopify Product', default=False)
    is_exported = fields.Boolean('Synced In Shopify', default=False)
    is_product_active = fields.Boolean()
    
    shopify_instance_id = fields.Many2one('shopify.instance', ondelete='cascade')
    shopify_image_ids = fields.One2many("shopify.product.image", "product_template_id")
    shopify_tag_ids = fields.Many2many("product.tag.shopify", relation='product_shopify_tags_rel', string="Tags")
    product_category_ids = fields.Many2many("product.category", relation='product_temp_category_rel', string="Categories")

    def init_shopify_session(self, instance_id):
        if instance_id.is_authenticated:
            try:
                session = shopify.Session(instance_id.shop_url, instance_id.api_version, instance_id.admin_api_key)
                return session
            except Exception as error:
                raise UserError(_("Please check your connection and try again"))  
        else :
            raise UserError(_("Connection Instance needs to authenticate first. \n Please try after authenticating connection!!!"))
    
    @staticmethod
    def get_extension(img_url):    
        mime_type, encoding = mimetypes.guess_type(img_url)
    
        if mime_type:
            extension = mimetypes.guess_extension(mime_type)
            return extension
        else:
            return None  
        
    def get_all_products(self, instance_id, limit=100):
        session = self.init_shopify_session(instance_id)
        shopify.ShopifyResource.activate_session(session)

        current_import = self.env['product.import.tracking'].sudo().search([], limit=1)
        
        count = 0
        get_next_page = True
        if not current_import:
            since_id = 0
            self.env['product.import.tracking'].create_or_update_record({'since_id': '0','is_completed': False,'status': 'start'})
            total_count = shopify.Product.count()
            self.env['product.import.tracking'].update_total_count(total_count)            
        else:
            since_id = current_import.since_id
            
        while get_next_page:
            products = shopify.Product.find(since_id=since_id, limit=limit)

            for product in products:
                count+=1
                yield product
                since_id = product.id
                
            self.env['product.import.tracking'].create_or_update_record({'since_id': since_id,'is_completed': False,'status': 'in_progress'})
            self.env['product.import.tracking'].update_count(limit)

            if len(products) < limit:
                get_next_page = False
                self.env['product.import.tracking'].clear_all_rows()
                
            if count >= 2000:
                get_next_page = False
                self.env['product.import.tracking'].mark_as_completed()
            
            time.sleep(5) # 5 second delay
    
    def import_product(self, instance_id, is_force_update = False):
        count = 0
        for p_item in self.get_all_products(instance_id, limit=100):
            count = count + 1

            ''' To avoid duplications of products already having shopify_id. '''
            exist = self.env['product.template'].sudo().search([('shopify_id', '=', p_item.id)],limit=1)
            
            if exist and not is_force_update:
                continue
            
            self.create_product( p_item, instance_id)
            
    def create_product(self, p_item, instance_id):
    
        ''' This is used to update shopify_id of a product, this
        will avoid duplication of product while syncing product.
        '''
        p_tags = []
        
        dict_p = {}
        dict_p['is_exported'] = True
        dict_p['is_shopify_product'] = True
        dict_p['shopify_instance_id'] = instance_id.id
        dict_p['company_id'] = instance_id.shopify_company_id.id
        dict_p['shopify_id'] = p_item.id if p_item.id else ''
        dict_p['type'] = 'product'
        dict_p['name'] = p_item.title if p_item.title else ''           
        dict_p['shopify_product_scope'] = p_item.published_scope if p_item.published_scope else ''           
        dict_p['purchase_ok'] = True
        dict_p['sale_ok'] = True 
        dict_p['shopify_product_status'] = p_item.status
        dict_p['is_product_active'] = True if p_item.status == 'active' else False
        
        if p_item.body_html:
            dict_p['description'] = p_item.body_html
            soup = BeautifulSoup(p_item.body_html, 'html.parser')
            description_converted_to_text = soup.get_text()
            dict_p['description_sale'] = description_converted_to_text

        if p_item.product_type:
            categ = self.env['product.category'].sudo().search([('name', '=', p_item.product_type)], limit=1)
            if categ:
                dict_p['categ_id'] = categ[0].id
            else:
                dict_cat = {}
                dict_cat['name'] = p_item.product_type
                dict_cat['is_shopify'] = True
                dict_cat['shopify_instance_id'] = instance_id.id
                category = self.env['product.category'].sudo().create(dict_cat)
                dict_p['categ_id'] = category.id
        
        if p_item.tags:
            for tag_str in p_item.tags.split(','):
                existing_tag = self.env['product.tag.shopify'].sudo().search([('name', '=', tag_str.strip()), ('shopify_instance_id', '=', instance_id.id)], limit=1)
                dict_value = {}
                dict_value['is_shopify'] = True
                dict_value['shopify_instance_id'] = instance_id.id
                dict_value['name'] = tag_str.strip()

                if not existing_tag:
                    create_tag_value = self.env['product.tag.shopify'].sudo().create(dict_value)
                    p_tags.append(create_tag_value.id)
                else:
                    write_tag_value = existing_tag.sudo().write(dict_value)
                    p_tags.append(existing_tag.id)
            
        product = self.env['product.template'].sudo().search([('shopify_id', '=', p_item.id)],limit=1)

        if not product:
            archived_products  = self.env['product.template'].sudo().search([('shopify_id', '=', p_item.id), ('active', '=', False)])
            if archived_products:
                archived_products.write({'shopify_id' : False, 'is_exported': False, 'shopify_instance_id' : False})
            
            product = self.env['product.template'].sudo().create(dict_p)
        else:
            product.sudo().write(dict_p)

        product.shopify_tag_ids = [(4, val) for val in p_tags]

        self.env.cr.commit()
        
        # Need to check product delete issue after attribute adding.
        if p_item.options:
            dict_attr = {}
            for attr in p_item.options:
                product_attr = self.env['product.attribute'].sudo().search(
                    ['|', ('shopify_id', '=', attr.id),
                        ('name', '=', attr.name)], limit=1)
                dict_attr['is_shopify'] = True
                dict_attr['shopify_instance_id'] = instance_id.id
                dict_attr['shopify_id'] = attr.id if attr.id else ''
                dict_attr['name'] = attr.name if attr.name else ''
                if not product_attr:
                    product_attr = self.env['product.attribute'].sudo().create(dict_attr)

                p_attr_val = []
                if attr.values:
                    for value in attr.values:
                        if value != 'Default Title':
                            existing_attr_value = self.env['product.attribute.value'].sudo().search(
                                [('name', '=', value), ('attribute_id', '=', product_attr.id)], limit=1)
                            dict_value = {}
                            dict_value['is_shopify'] = True
                            dict_value['shopify_instance_id'] = instance_id.id
                            dict_value['name'] = value if value else ''
                            dict_value['attribute_id'] = product_attr.id

                            if not existing_attr_value and dict_value['attribute_id']:
                                create_value = self.env['product.attribute.value'].sudo().create(dict_value)
                                p_attr_val.append(create_value.id)
                            elif existing_attr_value:
                                write_value = existing_attr_value.sudo().write(dict_value)
                                p_attr_val.append(existing_attr_value.id)

                    if product_attr:
                        if p_attr_val:
                            exist = self.env['product.template.attribute.line'].sudo().search(
                                [('attribute_id', '=', product_attr.id),
                                    ('value_ids', 'in', p_attr_val),
                                    ('product_tmpl_id', '=', product.id)], limit=1)
                            if not exist:
                                exist = self.env['product.template.attribute.line'].sudo().create({
                                    'attribute_id': product_attr.id,
                                    'value_ids': [(6, 0, p_attr_val)],
                                    'product_tmpl_id': product.id
                                })
                            else:
                                exist.sudo().write({
                                    'attribute_id': product_attr.id,
                                    'value_ids': [(6, 0, p_attr_val)],
                                    'product_tmpl_id': product.id
                                })
                    
        product_variant = self.env['product.product'].sudo().search([('product_tmpl_id', '=', product.id)])
        if p_item.variants:
            for variant in p_item.variants:
                variant_options = []
                if variant.option1 == 'Default Title' and product:
                    product.sudo().write({
                        'list_price': variant.price,
                        'default_code': variant.sku,
                        'shopify_sku': variant.sku,
                        'barcode': variant.barcode,
                        'shopify_barcode': variant.barcode,
                        'weight': variant.weight,
                    })
                    if len(product_variant) == 1:
                        product_variant.shopify_inventory_id = getattr(variant, 'inventory_item_id') or ''
                        product_variant.shopify_variant_id = variant.id

                if variant.option1:
                    variant_options.append(variant.option1)
                if variant.option2:
                    variant_options.append(variant.option2)
                if variant.option3:
                    variant_options.append(variant.option3)
                for item in product_variant:
                    if item.product_template_attribute_value_ids:
                        list_values = []
                        for rec in item.product_template_attribute_value_ids:
                            list_values.append(rec.name)
                        if set(variant_options).issubset(list_values):
                            item.shopify_variant_title = variant.title
                            item.default_code = variant.sku
                            item.barcode = variant.barcode
                            item.shopify_variant_id = variant.id
                            item.shopify_instance_id = instance_id.id
                            item.is_exported = True
                            item.shopify_barcode = variant.barcode
                            item.shopify_sku = variant.sku
                            item.shopify_image_id = variant.image_id
                            item.weight = variant.weight
                            item.taxes_id = [(6, 0, [])]
                            item.shopify_sale_price = variant.price
                            item.product_tmpl_id.list_price = 0.00
                            item.shopify_inventory_id = getattr(variant, 'inventory_item_id') or ''
                            break
                self.env.cr.commit()
                            
        # syn product images             
        if p_item.images:
            for image in p_item.images:
                if image.src:
                    self.import_product_images_sync(image,product)
                            
        self.env.cr.commit()

    def import_product_images_sync(self, image, product):
        def shopify_image_create_or_update(img_vals):
            ext_image = self.env['shopify.product.image'].sudo().search(
                [('image_shopify_id', '=', img_vals['image_shopify_id'])], limit=1)
            if not ext_image:
                ext_image = self.env['shopify.product.image'].sudo().create(img_vals)
            else:
                ext_image.sudo().write(img_vals)
            return
                
        try:
            img_vals = {
                'name': getattr(image, 'alt', '') or product.name,
                'image_shopify_id': str(image.id),
                'product_template_id': product.id,
                'url': image.src,
                's_image_pos' : image.position,
                'is_auto_create' : True,
                'is_main_image' : False
            }       
                        
            if hasattr(image, 'position') and image.position == 1:
                img_vals.update({'is_main_image' : True})
            
            if hasattr(image, 'variant_ids') and image.variant_ids:
                ids_list = []
                for variant_id in image.variant_ids:                        
                    varient_product_id = self.env['product.product'].sudo().search([('shopify_variant_id', '=', variant_id)])
                    if varient_product_id:
                        ids_list.append((4, varient_product_id.id))
                    
                img_vals.update({'shopify_image_variant_ids': ids_list})  
                
            shopify_image_create_or_update(img_vals)
                                   
        except Exception as error:
            pass

    def export_product(self, instance_id, sync=True):
        
        session = self.init_shopify_session(instance_id)
        shopify.ShopifyResource.activate_session(session)
        
        selected_ids = self.env.context.get('active_ids', [])
        products_ids = self.sudo().search([('id', 'in', selected_ids)])

        if not products_ids:
            raise UserError(_("Please select products!!!"))
        
        for product in products_ids:
                       
            p_tags = ','.join(str(tag.name) for tag in product.shopify_tag_ids) if product.shopify_tag_ids else ''

            if product.is_shopify_product and product.shopify_instance_id.id == instance_id.id and sync == True:
                data =  self.product_export_data_generate(product, p_tags)
            else:
                if product.is_shopify_product == False or not product.shopify_instance_id.id == instance_id.id:
                    data =  self.product_export_data_generate(product, p_tags)
                    
            _logger.info('\n\n\n\n  Product Export Data   =  %s \n\n\n\n' % (data) )    
            try:               
                if data['product'].__contains__('id'):
                    result = shopify.Product(data['product'])                        
                    result.save()
                else:
                    result = shopify.Product.create(data['product'])

                if result:
                    product.shopify_id = result.id
                    product.is_shopify_product = True
                    product.shopify_instance_id = instance_id.id
                    product.is_exported = True
                    product.is_product_active = True
                    product.shopify_product_status = "active"
                    
                    self.env.cr.commit()
                    
                    self.import_exported_product_variant_details(instance_id, result.variants, product.id)
                    self.export_images_to_shopify(product)
                    
                    if product.type == 'product':
                        self.export_product_stock_to_shopify(instance_id, product.id)
                    
                    _logger.info("\n\n\nProduct created/updated successfully\n\n")
                    # _logger.info("\n\n\nProduct data %s\n\n" % result.__dict__)
                    
            except Exception as error:
                _logger.info("Product creation/updation Failed")
                _logger.info('\n\n\n\n Error message: -- %s \n\n\n\n\n' % error)
                raise UserError(_("Please check your connection and try again"))
               
    def product_export_data_generate(self, product, p_tags):
        
        data = {"title": product.name,
                "body_html": product.description or '',
                "tags": p_tags,
                }
        if product.shopify_id:
            if shopify.Product.exists(product.shopify_id):
                data.update({"id": product.shopify_id})
                               
        if product.categ_id:
            data.update({"product_type": product.categ_id.name})
            
        option_list = []
        if product.attribute_line_ids:
            for attr in product.attribute_line_ids:
                val_list = []
                for val in attr.value_ids:
                    val_list.append(val.name)
                attr_vals = {
                    "name": attr.attribute_id.name,
                    "values": val_list
                }
                option_list.append(attr_vals)

            data.update({"options": option_list})
            
            product_variant_ids = self.env['product.product'].sudo().search(
                [('product_tmpl_id', '=', product.id)])
            if product_variant_ids:
                variant_val_list = []
                for variant in product_variant_ids:
                    variant_val = {
                        'option1': "",
                        'option2': "",
                        'option3': "",
                        'price': "0.00",
                        'inventory_management':	"shopify",
                    }
                    if variant.shopify_variant_id:
                        variant_val.update({
                            'id': variant.shopify_variant_id,
                            'product_id': variant.product_tmpl_id.shopify_id })
                        if variant.default_code:
                            variant_val.update({'sku': variant.default_code,})
                    if variant.product_template_variant_value_ids:
                        count = 1
                        for value in variant.product_template_variant_value_ids:
                            if count == 1:
                                variant_val['option1'] = value.name
                            elif count == 2:
                                variant_val['option2'] = value.name
                            else:
                                variant_val['option3'] = value.name
                            count += 1
                        variant_val['price'] = variant.lst_price
                        variant_val_list.append(variant_val)
                    
                    #added if one attribute is added without any variant    
                    if len(product.attribute_line_ids) == 1:
                        if len(product.attribute_line_ids[0].value_ids) == 1:
                            variant_val['option1'] = option_list[0]['values'][0]
                            variant_val['price'] = product.list_price
                            variant_val_list.append(variant_val)                           
                        
                data.update({"variants": variant_val_list}) 
     
        else:
            default_variant = [
                    {
                        "title": "Default Title",
                        "price": product.list_price or '0.00',
                        "sku": product.default_code or '',
                        "option1": "Default Title",
                        "barcode": product.barcode or '',
                    }
                ]
            default_options  = [
                    {
                        "name": "Title",
                        "position": 1,
                        "values": [
                            "Default Title"
                        ]
                    }
                ]     
            data.update({"options": default_options})
            data.update({"variants": default_variant})
             
        return {"product": data }

    def import_exported_product_variant_details(self, instance_id, variants, product_id):
        product_variant = self.env['product.product'].sudo().search(
                [('product_tmpl_id', '=', product_id)])
        for variant in variants:
            variant_options = []
                       
            if variant.option1:
                variant_options.append(variant.option1)
            if variant.option2:
                variant_options.append(variant.option2)
            if variant.option3:
                variant_options.append(variant.option3)
            for item in product_variant:
                if variant.option1 == 'Default Title':
                    item.shopify_variant_title = variant.title
                    item.shopify_sku = variant.sku
                    item.shopify_variant_id = variant.id
                    item.shopify_instance_id = instance_id.id
                    item.shopify_image_id = variant.image_id
                    item.shopify_sale_price = variant.price
                    item.shopify_inventory_id = getattr(variant, 'inventory_item_id') or ''
                    item.is_exported = True
                    continue
                
                if item.product_template_attribute_value_ids:
                    list_values = []
                    for rec in item.product_template_attribute_value_ids:
                        list_values.append(rec.name)
                    if set(variant_options).issubset(list_values):
                        item.shopify_variant_title = variant.title or ''
                        item.shopify_sku = variant.sku
                        item.shopify_variant_id = variant.id
                        item.shopify_instance_id = instance_id.id
                        item.shopify_image_id = variant.image_id
                        item.shopify_sale_price = variant.price
                        item.shopify_inventory_id = getattr(variant, 'inventory_item_id') or ''
                        item.is_exported = True
                        break

        self.env.cr.commit()     
       
    def export_images_to_shopify(self, product):

        session = self.init_shopify_session(product.shopify_instance_id)
        shopify.ShopifyResource.activate_session(session)
        
        data = {"product_id": product.shopify_id}
        
        img_count = 0
        s_image_lists = shopify.Image.find(product_id = product.shopify_id)
        img_count = len(s_image_lists)
        
        s_image_id_lists = []
        for img_id in s_image_lists:
            s_image_id_lists.append(str(img_id.id))

        #to add main image
        if img_count == 0 and product.image_1920 :
            data.update({'attachment' : product.image_1920.decode("utf-8")})
            new_img = shopify.Image.create(data)
            s_image_id_lists.append(str(new_img.id))
            self.shopify_product_image_add(new_img, product, is_variant = False)
        
        product_variant_ids = self.env['product.product'].sudo().search([('product_tmpl_id', '=', product.id)])
        if product_variant_ids:
            for variant in product_variant_ids:
                if variant.image_variant_1920:
                    if variant.shopify_image_id not in s_image_id_lists:
                        data.update({'attachment' : variant.image_variant_1920.decode("utf-8"),
                                    'variant_ids' : [variant.shopify_variant_id]})
                        new_img = shopify.Image.create(data)
                        s_image_id_lists.append(str(new_img.id))
                        self.shopify_product_image_add(new_img, variant, is_variant = True)
                              
        product_extra_images = self.env['shopify.product.image'].sudo().search([('product_template_id', '=', product.id)])
        if product_extra_images:
            for image in product_extra_images:
                if image.shopify_image:
                    if image.image_shopify_id not in s_image_id_lists:
                        data.update({'attachment' : image.shopify_image.decode("utf-8"),
                                    'variant_ids' : [id.shopify_variant_id for id in image.shopify_image_variant_ids]})
                        new_img = shopify.Image.create(data)
                        s_image_id_lists.append(str(new_img.id))
                        image.sudo().write({
                                    'image_shopify_id': str(new_img.id),
                                    'url': new_img.src,
                                    's_image_pos' : new_img.position
                                })     
                                                                     
    def shopify_product_image_add(self, s_img, product, is_variant = False):
        img_vals = {
                    'image_shopify_id': str(s_img.id),
                    'name': product.name,
                    'shopify_image': '',
                    'product_template_id': product.id,
                    'url': s_img.src,
                    'is_auto_create': True,
                    's_image_pos' : s_img.position
                }
        if s_img.position == 1:
            img_vals.update({'is_main_image': True,})
        if is_variant:
            v_name = ", ".join([v.name for v in product.product_template_attribute_value_ids])
            img_vals.update({
                    'name': v_name and "%s (%s)" % (product.name, v_name) or product.name,
                    'product_template_id': product.product_tmpl_id.id,
                    'image_variant_id': product.id,
                    'shopify_image_variant_ids': [product.id],
                    'is_main_image': False,
                })
        ext_image = self.env['shopify.product.image'].sudo().search(
                [('image_shopify_id', '=', img_vals['image_shopify_id'])], limit=1)
        if not ext_image:
            ext_image = self.env['shopify.product.image'].sudo().create(img_vals)
        else:
            ext_image.sudo().write(img_vals) 
                
    def set_product_status(self):
        ''' Set product status in shopify'''
        session = self.init_shopify_session(self.shopify_instance_id)
        shopify.ShopifyResource.activate_session(session)
        
        status = self.env.context.get('status')
        
        if not shopify.Product.exists(self.shopify_id):
            self.is_product_active = False
            self.is_exported = False
            self.shopify_product_status = 'draft'
            self.env.cr.commit()
            
            raise MissingError(_("Product Not Exist in Shopify, Please export first!!!"))
            
        data = {"id": self.shopify_id, "status": status,}
        
        try:
            result = shopify.Product(data)                        
            result.save()
            if result:
                self.shopify_product_status = result.status
                self.is_product_active = True if result.status == 'active' else False
        except Exception as error:
            _logger.info("Product Enable/Disable failed!! \n\n %s" % error)
            raise UserError(_("Please check your connection and try again"))


    # Inventory Export to shopify
    def get_variant_inventory_level(self, shopify_instance_id, p_id = False, limit=100): 
        sessiongql = ShopifyGraphQLAPI.init_shopify_session(shopify_instance_id)
        ShopifyGraphQLAPI.activate_session(sessiongql)
        
        locations = self.env['shopify.location'].sudo().search([('is_shopify', '=', True),('is_default', '=', True)], order='id asc')
        first_location = "gid://shopify/Location/" + locations[0].shopify_location_id
        
        count = 0               
        get_next_page = True
        while get_next_page:
            if p_id:
                p_variants = self.env['product.product'].sudo().search([('stock_update_status', '=', 'changed'), ('product_tmpl_id', '=', p_id), ('shopify_variant_id', '!=', False)], limit=100, order='last_stock_update asc')
            else :
                p_variants = self.env['product.product'].sudo().search([('stock_update_status', '=', 'changed'), ('shopify_variant_id', '!=', False)], limit=100, order='last_stock_update asc')
            if not p_variants:
                yield {"error" :  "empty_data"}
            for variant in p_variants:
                count+=1
                if variant.shopify_inventory_id and variant.shopify_variant_id:
                    quantity_list = {"available" : 0, "on_hand" : 0, "reserved" : 0,}
                    inv_lvl = ShopifyGraphQLAPI.Inventory.find(inventory_item_id = "gid://shopify/InventoryItem/"+variant.shopify_inventory_id)
                    
                    location_id = ""
                    if inv_lvl['tracked']:                
                        if inv_lvl["inventoryLevels"]['edges']: 
                            for data in inv_lvl["inventoryLevels"]['edges']:
                                if data['node']['location']['id'] == first_location:
                                    inventoryItem_gid = inv_lvl['id']
                                    inventoryLevel_gid = data['node']['id']
                                    location_id = data['node']['location']['id']
                                    
                                    for quantity in data['node']['quantities']:
                                        quantity_list[quantity['name']] = quantity['quantity']                           
                        
                        if location_id:
                            new_data = {
                                        'product_variant': variant,
                                        'qty_available': variant.qty_available,}
                            if inv_lvl:
                                new_data.update({                     
                                        'inventory_level_id':inventoryLevel_gid,
                                        'inventory_item_id':inventoryItem_gid,
                                        'available': quantity_list["available"],
                                        'on_hand': quantity_list["on_hand"],
                                        'location_id': location_id })
                            yield new_data
                        else:
                            _logger.info("\n\n\nLocation not found!!! -- %s \n\n" % inv_lvl["variant"].get('id',''))
                            yield {"error" :  "location_not_found"}
                        
                    else :
                        _logger.info("\n\n\nTracking not enabled!!! -- %s \n\n" % inv_lvl["variant"].get('id',''))
                        yield {"error" :  "tracking_disabled"}
                        
            if len(p_variants) < limit :
                get_next_page = False

            if count >= 5000:
                get_next_page = False        

    def export_product_variant_stock_to_shopify(self, shopify_instance_id, p_id=False):

        sessiongql = ShopifyGraphQLAPI.init_shopify_session(shopify_instance_id)
        ShopifyGraphQLAPI.activate_session(sessiongql)

        batch_id = str(int(time.time()))
        status = set()
        for inv_data in self.get_variant_inventory_level(shopify_instance_id, p_id):
            try:
                if "error" not in inv_data:
                    inv_input = {
                        "name": "on_hand",
                        "reason": "correction",
                        "quantities": [{
                            "inventoryItemId": str(inv_data['inventory_item_id']),
                            "locationId": str(inv_data['location_id']),
                            "quantity": int(inv_data['qty_available']),
                            "compareQuantity": int(inv_data['on_hand'])
                        }]
                    }
                    inventory = ShopifyGraphQLAPI.Inventory.inventorySet(inv_input)
                    
                    status.add("success")
                    inv_data['product_variant'].mark_as_completed()

                    self.env['shopify.export.inventory.data'].save_inventory_export_data_log(inv_data, batch_id, "success")
                    
                else:
                    status.add(inv_data["error"])

            except Exception as error:
                _logger.info('\n\n\n Quantity Update for the product %s failed!!! \n\n\n Error : %s \n\n' % (inv_data['product_variant'].product_tmpl_id, error))
                status.add("fail")

        return status
                
    def export_inventory(self, shopify_instance_id):
        ''' * **Inventory export to shopify from all variants** '''
        cron_lock = self.env['shopify.cron.job.lock'].search([('name', '=', 'cron_export_product_inventory')], limit=1)
        if cron_lock and cron_lock.is_running:
            _logger.info("\n\n\nThe cron job for exporting inventory is already running.\n\n")
            return self.env['message.wizard'].fail("The cron job for exporting inventory is already running.")
        else:
            result = self.export_product_variant_stock_to_shopify(shopify_instance_id, p_id = False)
            return self.status_messages(result)
    
    def action_export_product_stock_to_shopify(self):
        ''' * **Inventory export to shopify from individual product** '''
        product = self.sudo().search([('id', 'in', self.env.context.get('active_ids', []))], limit=1)
        if product:
            if product.shopify_instance_id:
                result =  self.export_product_variant_stock_to_shopify(product.shopify_instance_id, product.id)
                return self.status_messages(result)
                
    def cron_export_product_inventory(self):
        ''' * **Inventory export to shopify using cron** '''
        cron_lock = self.env['shopify.cron.job.lock'].search([('name', '=', 'cron_export_product_inventory')], limit=1)
        if cron_lock and cron_lock.is_running:
            _logger.info("\n\n\nThe cron job is already running.\n\n")
            
        if not cron_lock:
            cron_lock = self.env['shopify.cron.job.lock'].create({'name': 'cron_export_product_inventory', 'is_running': True})
        else:
            cron_lock.is_running = True
        try:
            shopify_instance_id = self.env["shopify.instance"].sudo().search([], limit=1)
            result = self.export_product_variant_stock_to_shopify(shopify_instance_id, p_id = False)
            return self.status_messages(result, is_return = False)
        finally:
            cron_lock.is_running = False

    def status_messages(self, status, is_return = True):
        if status == {"success"}:
            message_type, message =  True, "Quantity Update Successfull."
        elif status == {"fail"}:
            message_type, message =  False, "Quantity Update Failed."
        elif status == {"empty_data"}:
            message_type, message = True, "No changes to process."
        elif status == {"tracking_disabled"}:
            message_type, message = False, "Quantity updates could not be processed because tracking is disabled for the products."
        elif status == {"location_not_found"}:
            message_type, message = False, "Quantity updates could not be processed because location not matching."            
        else:
            if {"tracking_disabled", "fail"} <= status:
                message_type, message = False, "Quantity update failed due to invalid data, and some updates couldn't be processed because tracking is disabled for some products."
            elif {"tracking_disabled", "success"} <= status:
                message_type, message = False, "Quantity update partially successful. Some updates could not be processed due to tracking being disabled."
            elif {"success", "fail"} <= status:
                message_type, message = False, "Quantity update partially successful. Some updates failed due to invalid data."

        _logger.info("\n\n\n Shopify Inventory Update - "+ message +" \n\n")

        if is_return:
            if message_type:
                return self.env['message.wizard'].success(message)
            else:
                return self.env['message.wizard'].fail(message)

    # Inventory Export to shopify

    #bulk inventory import from shopify
    def get_all_inventory_levels(self, instance_id, location_id="", limit=100):
        session = ShopifyGraphQLAPI.init_shopify_session(instance_id)
        ShopifyGraphQLAPI.activate_session(session)

        current_import = self.env['inventory.import.tracking'].sudo().search([], limit=1)

        count = 0
        get_next_page = True
        if not current_import:
            since_id = None
            self.env['inventory.import.tracking'].create_or_update_record({'since_id': '0', 'is_completed': False, 'status': 'start'})
        else:
            since_id = current_import.since_id

        while get_next_page:
            inventory_items = ShopifyGraphQLAPI.Inventory.find_all(since_id=since_id, locationId=location_id,  limit=limit)

            for item in inventory_items["edges"]:
                count += 1
                yield item["node"]
                since_id = inventory_items["pageInfo"]["endCursor"]

            self.env['inventory.import.tracking'].create_or_update_record({'since_id': since_id, 'is_completed': False, 'status': 'in_progress'})
            self.env['inventory.import.tracking'].update_count(limit)

            get_next_page = inventory_items["pageInfo"]["hasNextPage"]

            if not get_next_page:
                self.env['inventory.import.tracking'].clear_all_rows()
                self.env['shopify.inventory.import.time'].set_last_import_time()

            if count >= 10000:
                get_next_page = False
                self.env['inventory.import.tracking'].mark_as_completed()

            _logger.info('\n\n\n\n count %s \n\n\n\n\n' % count)
            time.sleep(5)  # 5 second delay

    def import_shopify_inventory(self, shopify_instance_id):
        
        if self.env['shopify.inventory.import.time'].is_imported():
            _logger.info("\n\n\nThe inventory has already been imported once. Importing again may cause incorrect inventory values. This action is blocked.\n\n")
            return self.env['message.wizard'].fail("Unsuccessful..!! \nThe inventory has already been imported once. Importing again may cause incorrect inventory values. This action is blocked.")

        locations = self.env['shopify.location'].sudo().search([('is_shopify', '=', True),('is_default', '=', True)], order='id asc')
        location_ids = ','.join(str(loc.shopify_location_id) for loc in locations) if locations else ''

        if location_ids == "":
            return self.env['message.wizard'].fail("Unsuccessful..!! \nPlease import locations first and try again!!!")

        # only to import data from first locaton, don't support multiple location currently
        first_location = "gid://shopify/Location/" + locations[0].shopify_location_id

        instance_inventory_levels = []
        for level in self.get_all_inventory_levels(shopify_instance_id,  first_location, limit=200):
            instance_inventory_levels.append(level)
        if instance_inventory_levels:
            updated_products = self.update_product_stock(instance_inventory_levels, shopify_instance_id)
            return updated_products
        else:
            _logger.info("Inventory Levels not found in shopify store")
            return []

    def update_product_stock(self, levels, shopify_instance_id):
        stock_inventory = self.env["stock.quant"]
        shopify_stock_inventory = self.env["shopify.stock.quant"]
        warehouse_id = self.env['stock.warehouse'].sudo().search([('id', '=', 1)], limit=1)

        stock_inventory_array = {}
        product_ids_list = []
        stock_inventory_list = []

        _logger.info("\n\nInventory levels   \n\n\n\n %s" % levels)
        for level in levels:
            quantity_list = {"available": 0, "on_hand": 0, "reserved": 0, }
            product = self.env['product.product'].sudo().search([('shopify_inventory_id', '=', level['legacyResourceId'])], limit=1)

            inventory_levels_data = level['inventoryLevel']

            for quantity in inventory_levels_data['quantities']:
                quantity_list[quantity['name']] = quantity['quantity']

            location_id = inventory_levels_data["location"]["id"]

            if product and product not in product_ids_list:
                stock_inventory_line = {
                    product.id: quantity_list['on_hand'],
                }

                stock_inventory_tuple = (product.id, level['legacyResourceId'], quantity_list['on_hand'], location_id)
                stock_inventory_list.append(stock_inventory_tuple)
                stock_inventory_array.update(stock_inventory_line)
                product_ids_list.append(product)

        inventory_name = 'Inventory For Instance "%s"' % (shopify_instance_id.name)
        _logger.info("\n\n -- %s \n\n" % inventory_name)

        _logger.info("Inventory Details   \n\n %s" % stock_inventory_list)
        shopify_stock_inventory.inventory_adjustment_operation(stock_inventory_list)
        inventories = stock_inventory.inventory_adjustment_operation(stock_inventory_array,
                                                                     warehouse_id.lot_stock_id, True,
                                                                     inventory_name)


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    is_shopify = fields.Boolean(string='Is Shopify?')
    shopify_instance_id = fields.Many2one('shopify.instance', string='Shopify Instance')
    shopify_id = fields.Char(string='Shopify Attribute Id')

class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    is_shopify = fields.Boolean(string='Is Shopify?')
    shopify_instance_id = fields.Many2one('shopify.instance', string='Shopify Instance')
    shopify_id = fields.Char(string='Shopify Id')

class ProductTag(models.Model):
    _description = "Product Tag"
    _name = 'product.tag.shopify'

    name = fields.Char('Tag name')    
    is_shopify = fields.Boolean(string='Is Shopify?')
    shopify_instance_id = fields.Many2one('shopify.instance', ondelete='cascade')

class ShopifyInventoryLastImportTime(models.Model):
    _name = 'shopify.inventory.import.time'
    _description = 'Shopify Inventory Last Import Time'

    name = fields.Char('Name', default='last_import_time')
    last_import_time = fields.Datetime('Last Import Time')
    
    
    def is_imported(self):
        record = self.search([('name', '=', 'last_import_time')], limit=1)

        if record:
            return True
        else:
            return False
            
    def set_last_import_time(self):
        record = self.search([('name', '=', 'last_import_time')], limit=1)

        if record:
            record.write({'last_import_time': fields.Datetime.now()})
        else:
            self.create({'last_import_time': fields.Datetime.now()})
            
class ShopifyCronJobLock(models.Model):
    _name = 'shopify.cron.job.lock'
    
    name = fields.Char('Job Name', required=True)
    is_running = fields.Boolean('Is Running', default=False)            
            

class ShopifyExportInventoryData(models.Model):
    _name = 'shopify.export.inventory.data'
    _description = 'Shopify Export Inventory Data'

    name = fields.Char(string="Export Name", required=True)
    batch_id = fields.Char(string="Export Batch ID", required=True)
    inventory_level_id = fields.Char(string="Inventory level ID")
    inventory_item_id = fields.Char(string="Inventory ID")
    location_id = fields.Char(string="Location ID")
    export_date = fields.Datetime(string="Export Date", default=fields.Datetime.now)
    product_id = fields.Many2one('product.product', string="Product")
    quantity = fields.Float(string="Quantity")
    shopify_on_hand_quantity = fields.Float(string="Shopify on Hand Quantity")
    shopify_available_quantity = fields.Float(string="Shopify available Quantity")
    export_status = fields.Char(string="Export Status", default='fail')
    
    
    def save_inventory_export_data_log(self, export_data, batch_id, status="fail"):
        try:
            self.env['shopify.export.inventory.data'].create({
                    "name":"Inventory Export",
                    "batch_id":batch_id,
                    "inventory_level_id":export_data['inventory_level_id'],
                    "inventory_item_id":export_data['inventory_item_id'],
                    "location_id":export_data['location_id'],
                    "product_id":export_data['product_variant'].id,
                    "quantity":export_data['qty_available'],
                    "shopify_on_hand_quantity":export_data['on_hand'],
                    "shopify_available_quantity":export_data['available'],
                    "export_status":status,
                })

        except:
            pass
        
    def cron_remove_inventory_export_data_log(self):
        """
        Remove 30 days before entries from the Shopify Export Inventory Data table.
        """
       
        date_30_days_before = datetime.now() - timedelta(days=30)
        date_30_days_before_midnight = date_30_days_before.replace(hour=0, minute=0, second=0, microsecond=0)
        epoch_time_30_days_before = int(time.mktime(date_30_days_before_midnight.timetuple()))
        
        old_entries = self.env['shopify.export.inventory.data'].search([
            ('batch_id', '<', str(epoch_time_30_days_before))
        ])
        
        old_entries.unlink()
        
        _logger.info("\n\n\n Removed %s Export Inventory Log!!!\n\n"%len(old_entries))

        return True