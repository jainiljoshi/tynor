from .shopify_graphql_api import ShopifyGraphQLAPI
import logging


_logger = logging.getLogger(__name__)
class Inventory:
    
    @staticmethod    
    def inventoryLevel(inventory_id):
        # $inventoryId "gid://shopify/InventoryLevel/523463154?inventory_item_id=30322695"
        query = '''
            query GetInventoryLevel($inventoryId: ID!,) {
            inventoryLevel(id: $inventoryId) {
                id
                quantities(names: ["available", "on_hand", "reserved"]) {
                    name
                    quantity
                }
                item {
                    id
                    sku
                }
                location {
                    id
                    name
                }
            }
        }
    '''
        variables = {'inventoryId': inventory_id}
        response = ShopifyGraphQLAPI._send_request(query, variables)
        # _logger.info('\n\n\n response   =  %s \n\n' % (response))
        if not response.get('data', ''):
            _logger.info('\n\n\n response   =  %s \n\n' % (response))
        return response['data']['inventoryLevel']
    
    @staticmethod    
    def find(inventory_item_id):
        # $inventoryId "gid://shopify/InventoryItem/30322695"
        query = '''
            query inventoryItemFind($InventoryItemId: ID!,) {
                inventoryItem(id: $InventoryItemId) {
                    id
                    tracked
                    inventoryLevels(first: 1) {
                        edges {
                            node {
                                id
                                location {
                                    id
                                    name
                                }
                                quantities(names: ["available", "on_hand", "reserved"]) {
                                    name
                                    quantity
                                }
                            }
                        }
                    }
                    variant {
                        id
                        title
                        product {
                            id
                            title
                        }
                    }
                }
            }
    '''
        variables = {'InventoryItemId': inventory_item_id}
        response = ShopifyGraphQLAPI._send_request(query, variables)
        # _logger.info('\n\n\n response   =  %s \n\n' % (response))
        if not response.get('data', ''):
            _logger.info('\n\n\n response   =  %s \n\n' % (response))
        return response['data']['inventoryItem']    

    @staticmethod    
    def find_all(since_id=None, locationId = "", limit=50):
        # $inventoryId "gid://shopify/InventoryItem/30322695"
        query = '''
            query inventoryItemsFindAll($first : Int, $after : String, $locationId : ID!) {
                inventoryItems(first: $first, after : $after) {
                    edges {
                        node {
                            id
                            legacyResourceId
                            tracked
                            inventoryLevel(locationId: $locationId) {
                                id
                                location {
                                    id
                                    name
                                }
                                quantities(names: ["available", "on_hand", "reserved"]) {
                                    name
                                    quantity
                                }                                
                            }
                            variant {
                                id
                                title
                                product {
                                    id
                                    title
                                }
                            }
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }                       
                }
            }
    '''
        variables = {'first': limit, "after" : since_id, "locationId" : locationId}
        response = ShopifyGraphQLAPI._send_request(query, variables)
        # _logger.info('\n\n\n response   =  %s \n\n' % (response))
        if not response.get('data', ''):
            _logger.info('\n\n\n response   =  %s \n\n' % (response))
        return response['data']['inventoryItems'] 

    
    @staticmethod    
    def inventoryAdjustQuantities(inventory_input):
        # $inventoryId "gid://shopify/InventoryLevel/523463154?inventory_item_id=30322695"
        mutation = '''
            mutation inventoryAdjustQuantities($input: InventoryAdjustQuantitiesInput!) {
                inventoryAdjustQuantities(input: $input) {
                    userErrors {
                        field
                        message
                    }
                    inventoryAdjustmentGroup {
                        createdAt
                        reason
                        referenceDocumentUri
                        changes {
                            name
                            delta
                        }
                    }
                }
            }
        '''
        variables = {'input': inventory_input}
        response = ShopifyGraphQLAPI._send_request(mutation, variables)
        # _logger.info('\n\n\n response   =  %s \n\n' % (response))
        if not response.get('data', ''):
            _logger.info('\n\n\n response   =  %s \n\n' % (response))
            
        # {
        #   "input": {
        #     "reason": "correction",
        #     "name": "available",
        #     "referenceDocumentUri": "logistics://some.warehouse/take/2023-01/13",
        #     "changes": [
        #       {
        #         "delta": -4,
        #         "inventoryItemId": "gid://shopify/InventoryItem/30322695",
        #         "locationId": "gid://shopify/Location/124656943"
        #       }
        #     ]
        #   }
        # }
        return response['data']['inventoryAdjustQuantities']
    
    @staticmethod    
    def inventorySet(inventory_input):
        # $inventoryId "gid://shopify/InventoryLevel/523463154?inventory_item_id=30322695"
        mutation = '''
            mutation InventorySet($input: InventorySetQuantitiesInput!) {
                inventorySetQuantities(input: $input) {
                    inventoryAdjustmentGroup {
                        createdAt
                        reason
                        referenceDocumentUri
                        changes {
                            name
                            delta
                        }
                    }
                    userErrors {
                        field
                        message
                    }
                }
            }
    '''
        variables = {'input': inventory_input}
        response = ShopifyGraphQLAPI._send_request(mutation, variables)
        # _logger.info('\n\n\n response   =  %s \n\n' % (response))
        if not response.get('data', ''):
            _logger.info('\n\n\n response   =  %s \n\n' % (response))
            
        # {
        # "input": {
        #     "name": "available",
        #     "reason": "correction",
        #     "referenceDocumentUri": "logistics://some.warehouse/take/2023-01-23T13:14:15Z",
        #     "quantities": [
        #     {
        #         "inventoryItemId": "gid://shopify/InventoryItem/30322695",
        #         "locationId": "gid://shopify/Location/124656943",
        #         "quantity": 11,
        #         "compareQuantity": 1
        #     }
        #     ]
        # }
        # }        
        return response['data']['inventorySetQuantities']        
    
    @staticmethod    
    def inventoryActivate(inventory_input):
        mutation = '''
            mutation ActivateInventoryItem($inventoryItemId: ID!, $locationId: ID!) {
                inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId) {
                    inventoryLevel {
                        id
                        quantities(names: ["available", "on_hand", "reserved"]) {
                            name
                            quantity
                        }
                        item {
                            id
                        }
                        location {
                            id
                        }
                    }
                }
            }
    '''
        variables = {'inventoryItemId': inventory_input['inventoryItemId'], 'locationId': inventory_input['locationId']}
        response = ShopifyGraphQLAPI._send_request(mutation, variables)
        if not response.get('data', ''):
            _logger.info('\n\n\n response   =  %s \n\n' % (response))
                    
        # {
        # "inventoryItemId": "gid://shopify/InventoryItem/43729076",
        # "locationId": "gid://shopify/Location/346779380",
        # }       
        return response['data']['inventoryActivate']
    
    @staticmethod    
    def inventoryBulkToggleActivation(inventory_input):
        mutation = '''
            mutation inventoryBulkToggleActivation($inventoryItemId: ID!, $inventoryItemUpdates: [InventoryBulkToggleActivationInput!]!) {
                inventoryBulkToggleActivation(inventoryItemId: $inventoryItemId, inventoryItemUpdates: $inventoryItemUpdates) {
                    inventoryItem {
                        id
                        tracked
                    }
                    inventoryLevels {
                        id
                        quantities(names: ["available", "on_hand", "reserved"]) {
                            name
                            quantity
                        }
                        location {
                            id
                        }
                    }
                    userErrors {
                        field
                        message
                        code
                    }
                }
            }
        '''
        variables = {'inventoryItemId': inventory_input['inventoryItemId'], 'inventoryItemUpdates': inventory_input['inventoryItemUpdates']}
        response = ShopifyGraphQLAPI._send_request(mutation, variables)
        if not response.get('data', ''):
            _logger.info('\n\n\n response   =  %s \n\n' % (response))
        return response['data']['inventoryBulkToggleActivation']
    
    @staticmethod    
    def enable(product_id, variant_id):
        mutation = f'''
            mutation UpdateProductVariantInventory {{
                productVariantsBulkUpdate(productId: "gid://shopify/Product/{product_id}",variants: [{{
                        id: "gid://shopify/ProductVariant/{variant_id}",
                        inventoryItem: {{tracked : true }}
                    }}
                    ]
                ) {{
                    productVariants {{
                        id
                    }}
                    userErrors {{
                        field
                        message
                    }}
                }}
            }}
        '''
        response = ShopifyGraphQLAPI._send_request(mutation)
        if not response.get('data', ''):
            _logger.info('\n\n\n response   =  %s \n\n' % (response))
        return response['data']['productVariantsBulkUpdate']      