from odoo import http
from odoo.http import request


class TynorWebsiteCategoryController(http.Controller):
    @http.route("/tynor/categories/json", type="json", auth="public", website=True)
    def category_tiles(self):
        categories = (
            request.env["product.public.category"]
            .sudo()
            .search([("has_published_products", "=", True), ("not_in_shop", "=", False), ("parent_id", "=", False)],
                    order="sequence, name")
        )
        payload = []
        for category in categories:
            payload.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "url": f"/shop/category/{category.id}",
                }
            )
        return payload
