{
    "name": "Tynor Sale Report Custom",
    "summary": "Custom quotation and sales order report layout",
    "version": "saas~19.2.1.0",
    "category": "Sales/Sales",
    "author": "Codex",
    "license": "LGPL-3",
    "depends": ["sale_management", "account", "mail", "tynor_shopify_inbound_bridge"],
    "data": [
        "report/sale_report_templates.xml",
        "data/mail_template_data.xml",
        "views/account_move_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
