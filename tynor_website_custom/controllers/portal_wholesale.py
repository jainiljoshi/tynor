from odoo.addons.portal.controllers.web import Home as PortalHome
from odoo.addons.web.controllers.utils import is_user_internal


class Home(PortalHome):
    def _login_redirect(self, uid, redirect=None):
        if uid and not is_user_internal(uid):
            user = self.env_user(uid)
            if user and user.partner_id._is_tynor_wholesale_partner():
                return super()._login_redirect(uid, redirect="/wholesale")
        return super()._login_redirect(uid, redirect=redirect)

    @staticmethod
    def env_user(uid):
        from odoo.http import request

        return request.env["res.users"].sudo().browse(uid)
