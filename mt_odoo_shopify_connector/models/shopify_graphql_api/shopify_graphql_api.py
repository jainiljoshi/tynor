import re
import requests
import logging
from odoo.exceptions import UserError
from odoo import _

_logger = logging.getLogger(__name__)
class ShopifyGraphQLAPI:
    class Session:
        def __init__(self, shop_url, api_version, admin_api_key):
            self.shop_url = shop_url
            self.api_version = api_version
            self.admin_api_key = admin_api_key

    @staticmethod
    def init_shopify_session(instance_id):
        if instance_id.is_authenticated:
            try:
                session = ShopifyGraphQLAPI.Session(instance_id.shop_url, instance_id.api_version, instance_id.admin_api_key)
                return session
            except Exception as error:
                raise UserError(_("Please check your connection and try again"))  
        else :
            raise UserError(_("Connection Instance needs to authenticate first. \n Please try after authenticating connection!!!"))

    @staticmethod
    def get_shopify_id(input_string):
        match = re.search(r'\d+', input_string)
        
        if match:
            return match.group(0)
        else:
            return None  # Return None if no match is found  

    @classmethod
    def activate_session(cls, session):
        cls._current_session = session
        
    @classmethod
    def clear_session(cls):
        cls._current_session = None        

    @classmethod
    def _send_request(cls, query, variables=None):
        """Send GraphQL request to Shopify API."""
        if not hasattr(cls, '_current_session'):
            raise Exception("No active session. Please activate a session first.")
        
        session = cls._current_session
        headers = {
            'X-Shopify-Access-Token': session.admin_api_key,
            'Content-Type': 'application/json'
        }
        url = f"https://{session.shop_url}/admin/api/{session.api_version}/graphql.json"
        response = requests.post(url, json={'query': query, "variables": variables}, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"GraphQL Query Failed: {response.status_code}, {response.text}")
        
