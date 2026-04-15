import logging

from odoo.addons.website_sale.controllers.variant import WebsiteSaleVariantController
from odoo.http import request, route

_logger = logging.getLogger(__name__)


class TynorWebsiteSaleVariantController(WebsiteSaleVariantController):
    def _tynor_empty_combination_info(self):
        currency = request.website.currency_id
        return {
            'product_id': 0,
            'is_combination_possible': False,
            'currency_precision': currency.decimal_places,
            'price': 0.0,
            'list_price': 0.0,
            'has_discounted_price': False,
            'base_unit_price': 0.0,
            'base_unit_name': '',
            'prevent_sale': True,
            'hide_price': False,
            'display_name': '',
            'no_product_change': True,
            'carousel': '',
            'product_tags': '',
        }

    @route()
    def get_combination_info_website(
        self, product_template_id, product_id, combination, add_qty, uom_id=None, **kwargs
    ):
        try:
            product_template_id = int(product_template_id)
        except (TypeError, ValueError):
            _logger.warning(
                "website_sale/get_combination_info called with invalid product_template_id=%r",
                product_template_id,
            )
            return self._tynor_empty_combination_info()

        if not request.env['product.template'].browse(product_template_id).exists():
            _logger.warning(
                "website_sale/get_combination_info called for missing/inaccessible template id=%s",
                product_template_id,
            )
            return self._tynor_empty_combination_info()

        return super().get_combination_info_website(
            product_template_id, product_id, combination, add_qty, uom_id=uom_id, **kwargs
        )
