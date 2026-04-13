from odoo import api, models


class ProductTag(models.Model):
    _inherit = "product.tag"

    @api.model
    def _tynor_archive_odoo_product_tag(self):
        domain = [("name", "=ilike", "Odoo")]
        if "active" in self._fields:
            domain.append(("active", "=", True))
        elif "visible_to_customers" in self._fields:
            domain.append(("visible_to_customers", "=", True))

        tags = self.search(domain)
        if not tags:
            return True

        if "active" in self._fields:
            tags.write({"active": False})
        elif "visible_to_customers" in self._fields:
            tags.write({"visible_to_customers": False})
        return True
