{
    "name": "Tynor Wholesaler Reporting",
    "summary": "Wholesaler dashboard cards and pivot reporting.",
    "version": "saas~19.2.1.0",
    "category": "Sales/Reporting",
    "author": "Tynor",
    "license": "LGPL-3",
    "depends": ["account", "sale_management", "web", "tynor_shopify_inbound_bridge"],
    "data": [
        "security/ir.model.access.csv",
        "views/wholesaler_reporting_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "tynor_wholesaler_reporting/static/src/js/wholesaler_dashboard_action.js",
            "tynor_wholesaler_reporting/static/src/xml/wholesaler_dashboard.xml",
            "tynor_wholesaler_reporting/static/src/scss/wholesaler_dashboard.scss",
        ],
    },
    "application": True,
    "installable": True,
}

