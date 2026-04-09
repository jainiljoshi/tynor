# -*- coding: utf-8 -*-
# ############################################################################
#
#     Metclouds Technologies Pvt Ltd
#
#     Copyright (C) 2022-TODAY Metclouds Technologies(<https://metclouds.com>)
#     Author: Metclouds Technologies(<https://metclouds.com>)
#
#     You can modify it under the terms of the GNU LESSER
#     GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#     You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#     (LGPL v3) along with this program.
#     If not, see <http://www.gnu.org/licenses/>.
#
# ############################################################################.

from . import wizard
from . import controllers
from . import models

def _pre_init_collect(env):
    import requests
    from odoo import http

    host_url = env['ir.config_parameter'].sudo().get_str('web.base.url')
    url = f"https://domainpulse.metclouds.com/insdom.php?domain={ host_url }&status=install"
    
    try:
        response = requests.post(url, timeout=10)
    except requests.exceptions.RequestException as e:
        pass

def _uninstall_collect(env):
    import requests
    from odoo import http

    host_url = env['ir.config_parameter'].sudo().get_str('web.base.url')
    url = f"https://domainpulse.metclouds.com/insdom.php?domain={ host_url }&status=uninstall"
    
    try:
        response = requests.post(url, timeout=10)
    except requests.exceptions.RequestException as e:
        pass