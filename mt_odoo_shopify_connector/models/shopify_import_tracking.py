from odoo import fields, models, api, _
from datetime import timedelta

import logging

_logger = logging.getLogger(__name__)

class ImportTrackingBaseModal(models.AbstractModel):
    
    _name = 'import.tracking.base.modal'
    _description = 'Import Tracking Base Modal'

    since_id = fields.Char('Since ID', help="The ID from which the import starts (for incremental imports)", default='0')
    is_completed = fields.Boolean(string="Is Completed", default=False)
    status = fields.Selection([
        ('start', 'Start'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ], string="Status", default='start')
    imported_count = fields.Integer('Imported Count', default=0)
    total_count = fields.Integer('Total Count', default=0)
    time = fields.Datetime('Import Time', default=fields.Datetime.now, required=True)


    @api.model
    def create_or_update_record(self, vals):
        vals['time'] = fields.Datetime.now()

        existing_record = self.search([], limit=1)
        _logger.info('\n\n\n existing_record %s \n\n' % existing_record.read())
        if existing_record:
            existing_record.write({
                'since_id': vals.get('since_id', '0'),
                'status': vals.get('status', 'in_progress'),
                'is_completed': vals.get('is_completed', False),
                'time': vals['time']
            })
            return existing_record
        else:
            return super(ImportTrackingBaseModal, self).create({
                'since_id': '0',
                'is_completed': False,
                'status': 'start',
                'time': vals['time']
            })
            
    def mark_as_completed(self):
        # Mark the import process as completed
        tracking_record = self.search([], limit=1)
        if tracking_record:
            tracking_record.write({
                'status': 'completed',
                'is_completed': True,
                'time': fields.Datetime.now()
            })
            _logger.info('\n\n\n mark_as_completed %s \n\n' % tracking_record.id)

    def clear_all_rows(self):
        # Method to clear all rows in the model
        self.search([]).unlink()
        _logger.info('\n\n\n clear_all_rows in tracking \n\n\n')

        
    @api.model
    def is_cool_off_minutes_passed(self, minutes=10):
        last_entry = self.search([], order="time desc", limit=1)
        
        if last_entry:
            time_difference = fields.Datetime.now() - last_entry.time
            
            if time_difference >= timedelta(minutes=minutes):
                return True
            else:
                return False
        else:
            return True #if no entry
        
    @api.model
    def is_import_completed(self):
        last_entry = self.search([], order="time desc", limit=1)
        
        if last_entry:
            if last_entry.status == 'completed':
                return True
            else:
                return False
        else:
            return True #if no entry    

    def update_count(self, increment=100):
        
        tracking_record = self.search([], limit=1)
        if tracking_record:
            new_imported_count = tracking_record.imported_count + increment
            tracking_record.write({
                'imported_count': int(new_imported_count)
            })
            _logger.info('\n\n\n increment %s \n\n\n' % new_imported_count)
            
    def update_total_count(self, total=0):
        
        tracking_record = self.search([], limit=1)
        if tracking_record:        
            _logger.info('\n\n\n total count %s \n\n\n' % total)
            try:
                total = int(total)
            except ValueError:
                total = 0


            tracking_record.write({
                'total_count': int(total)
            })

    @api.model
    def get_import_counts(self):
        """
        Returns the imported_count and total_count values if a row exists.
        If no row exists, returns 0 for both values.
        """
        record = self.search([], order="time desc", limit=1)

        if record:
            return {
                'imported_count': str(record.imported_count) or '0',  
                'total_count': str(record.total_count) or '0'
            }
        else:
            return {
                'imported_count': '0',
                'total_count': '0'
            }         
            

class CustomerImportTracking(models.Model):
    
    _name = 'customer.import.tracking'
    _inherit = 'import.tracking.base.modal'
    _description = 'Customer Import Tracking'
            
class ProductImportTracking(models.Model):
    
    _name = 'product.import.tracking'
    _inherit = 'import.tracking.base.modal'
    _description = 'Product Import Tracking'
    
class InventoryImportTracking(models.Model):
    
    _name = 'inventory.import.tracking'
    _inherit = 'import.tracking.base.modal'
    _description = 'Inventory Import Tracking'    
    
class SaleOrderImportTracking(models.Model):
    
    _name = 'sale.order.import.tracking'
    _inherit = 'import.tracking.base.modal'
    _description = 'Sale Order Import Tracking'    