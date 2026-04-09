{
    'name': 'Wholesale Management',
    'summary': 'Dedicated dashboard, views, and activities for Wholesale Managers',
    'version': 'saas~19.2.1.0',
    'sequence': 5,
    'description': """
Wholesale Management App
========================
Provides a dedicated top-level application and workspace for Wholesale Managers to handle CRM leads, approved wholesale partners, and wholesale orders, along with automated next-activity scheduling.
    """,
    'author': 'Your Company',
    'category': 'Sales',
    'depends': ['base', 'crm', 'sale_management', 'mail', 'tynor_b2b_wholesale'],
    'data': [
        'security/wholesale_security.xml',
        'security/ir.model.access.csv',
        'views/wholesale_menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
