{
    'name': 'CTIT Website Pricelist',
    'version': 'saas~19.2.1.1',
    'category': 'Website',
    'summary': 'Website Pricelist',
    'description': """
        This module is used to hide the price of the product on the website.
    """,
    'author': 'CTIT',
    'website': 'https://coretrustitservices.lovable.app',
    'depends': ['website_sale'],
    'data': [
        'views/website_sale_price_hide.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}