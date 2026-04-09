{
    'name': 'Shopify Odoo Sync Health Check',
    'version': 'saas~19.2.1.0',
    'summary': 'Dashboard and utilities for customer/product/inventory Shopify sync health.',
    'description': 'Tracks latest exported sheets, computes sync quality %, logs issues, and runs imports for customers, products, and inventory.',
    'category': 'Tools',
    'author': 'Tynor',
    'license': 'LGPL-3',
    'depends': ['base', 'contacts', 'product', 'stock', 'website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/shopify_sync_dashboard_data.xml',
        'views/sync_dashboard_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': True,
    'installable': True,
}
