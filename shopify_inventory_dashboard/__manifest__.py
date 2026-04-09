{
    "name": "Shopify Inventory Dashboard",
    "version": "saas~19.2.1.0",
    "summary": "OWL-based inventory dashboard for Shopify/Odoo sync monitoring.",
    "description": "Standalone OWL dashboard with inventory KPIs, low stock lines, and sync issue visibility.",
    "category": "Inventory",
    "author": "Tynor",
    "license": "LGPL-3",
    "depends": ["base", "web", "stock", "product", "shopify_sync_health_check"],
    "data": [
        "views/inventory_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "shopify_inventory_dashboard/static/src/js/inventory_dashboard_action.js",
            "shopify_inventory_dashboard/static/src/xml/inventory_dashboard.xml",
            "shopify_inventory_dashboard/static/src/scss/inventory_dashboard.scss",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": True,
    "installable": True,
}
