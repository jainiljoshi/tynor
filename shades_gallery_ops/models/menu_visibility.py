from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    hide_menu_ids = fields.Many2many(
        "ir.ui.menu",
        "shades_menu_user_rel",
        "user_id",
        "menu_id",
        string="Hidden Menus",
        help="Menus that should be hidden for this user.",
    )


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    restrict_user_ids = fields.Many2many(
        "res.users",
        "shades_menu_user_rel",
        "menu_id",
        "user_id",
        string="Restricted Users",
        help="Users who should not see this menu.",
    )

    def _filter_visible_menus(self):
        menus = super()._filter_visible_menus()
        if self.env.user.has_group("base.group_system"):
            return menus
        return menus.filtered(
            lambda menu: self.env.user.id not in menu.restrict_user_ids.ids
        )
