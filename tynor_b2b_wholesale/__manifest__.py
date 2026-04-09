{
    'name': 'Tynor B2B Wholesale App',
    'summary': 'Standalone B2B wholesale workflow and website logic',
    'version': 'saas~19.2.1.0',
    'sequence': 6,
    'description': """Separated B2B logic for CRM wholesale partner onboarding, VIP pricelists and theme configurations.""",
    'author': 'Your Company',
    'category': 'Sales',
    'depends': ['base', 'web', 'sale_management', 'website_sale', 'crm', 'portal'],
    'data': [
        'data/b2b_wholesale_data.xml',
        'views/theme_customizations.xml',
        'views/wholesale_application_templates.xml',
    ],
    'installable': True,
    'application': True,
}
