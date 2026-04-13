from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _is_tynor_wholesale_partner(self):
        self.ensure_one()
        tag_match = any((tag.name or "").strip().lower() == "wholesale" for tag in self.category_id)
        pricelist = self.property_product_pricelist
        pricelist_match = bool(pricelist and (pricelist.name or "").strip().lower() == "wholesale vip")
        return bool(tag_match or pricelist_match)
