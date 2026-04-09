from odoo import api, fields, models

from .utils import strip_shopify_label


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    tynor_public_note_name = fields.Char(
        string="Public Note",
        compute="_compute_tynor_public_note_name",
        store=True,
    )

    @api.depends("name", "display_type")
    def _compute_tynor_public_note_name(self):
        for line in self:
            if line.display_type == "line_note":
                line.tynor_public_note_name = strip_shopify_label(line.name)
            else:
                line.tynor_public_note_name = line.name or ""

