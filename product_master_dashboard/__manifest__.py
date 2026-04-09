{
    "name": "Product Master Dashboard",
    "version": "saas~19.2.1.0",
    "summary": "OWL dashboard and kanban view for product master management.",
    "description": "Shows product KPIs, quick product cards, and direct access to full product kanban.",
    "category": "Inventory",
    "author": "Tynor",
    "license": "LGPL-3",
    "depends": ["base", "web", "product", "stock"],
    "data": [
        "views/product_master_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "product_master_dashboard/static/src/js/product_master_dashboard_action.js",
            "product_master_dashboard/static/src/xml/product_master_dashboard.xml",
            "product_master_dashboard/static/src/scss/product_master_dashboard.scss",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": True,
    "installable": True,
}
