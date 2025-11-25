import urdhva_base
import asyncio
import charts_actions
import dashboard_studio_model


logger = urdhva_base.logger.Logger.getInstance("direct-sales-logging")

class IndentDryOutDirectSales:
    async def get_indent_raised_direct_sales(self):
        ims_query = f"""SELECT "INDENT_NO","INDENT_DATE","PROD_REQD_DT","DEALER_CODE","TRUCK_REGNO","VALID_INDENT","CANCEL_INDENT"
                        FROM "IMS_SAP"."INDENT_REQUEST" WHERE
                        TO_CHAR("DELIVERY_DATE",'yyyymmdd') = TO_CHAR(SYSDATE,'yyyymmdd') AND SUBSTR("DEALER_CODE",15,2)='12'
                    """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        indent_raised_resp = await function(query=ims_query)
        if indent_raised_resp:
            return {
                "status": "success",
                "indent_raised_count": len(indent_raised_resp)
            }
        return {
            "status": "success",
            "indent_raised_count": 0
            }
        
    async def get_indent_on_hold_direct_sales(self):
        ims_query = f"""SELECT "INDENT_NO","INDENT_DATE","PROD_REQD_DT","DEALER_CODE","TRUCK_REGNO",
                        "VALID_INDENT","CANCEL_INDENT" FROM "IMS_SAP"."INDENT_REQUEST" WHERE 
                        TO_CHAR("DELIVERY_DATE",'yyyymmdd') =  TO_CHAR(SYSDATE,'yyyymmdd') 
                        AND SUBSTR("DEALER_CODE",15,2)='12' AND "VALID_INDENT" = 'N' AND ("CANCEL_INDENT" IS NULL OR "CANCEL_INDENT" <> 'Y')
                    """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        indent_raised_resp = await function(query=ims_query)
        if indent_raised_resp:
            return {
                "status": "success",
                "indent_on_hold_count": len(indent_raised_resp)
            }
        return {
            "status": "success",
            "indent_on_hold_count": 0
            }

    async def get_pending_indents_direct_sales(self):
        ims_query = f"""SELECT "INDENT_NO","INDENT_DATE","PROD_REQD_DT","DEALER_CODE","TRUCK_REGNO",
                        "VALID_INDENT","CANCEL_INDENT" FROM "IMS_SAP"."INDENT_REQUEST" WHERE 
                        TO_CHAR("DELIVERY_DATE",'yyyymmdd') =  TO_CHAR(SYSDATE,'yyyymmdd')
                        AND SUBSTR("DEALER_CODE",15,2)='12' AND "TRUCK_REGNO" IS NULL AND ("CANCEL_INDENT" IS NULL OR "CANCEL_INDENT" <> 'Y')
                    """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        indent_raised_resp = await function(query=ims_query)
        if indent_raised_resp:
            return {
                "status": "success",
                "pending_indent_count": len(indent_raised_resp)
            }
        return {
            "status": "success",
            "pending_indent_count": 0
            }
    
    async def get_valid_indent_direct_sales(self):
        ims_query = f"""SELECT "INDENT_NO","INDENT_DATE","PROD_REQD_DT","DEALER_CODE","TRUCK_REGNO",
                        "VALID_INDENT","CANCEL_INDENT" FROM "IMS_SAP"."INDENT_REQUEST" WHERE 
                        TO_CHAR("DELIVERY_DATE",'yyyymmdd') =  TO_CHAR(SYSDATE,'yyyymmdd')
                        AND SUBSTR("DEALER_CODE",15,2)='12' AND "VALID_INDENT" IN ('Y','H') AND ("CANCEL_INDENT" IS NULL OR "CANCEL_INDENT" <> 'Y')
                        AND "TRUCK_REGNO" IS NOT NULL
                    """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        indent_raised_resp = await function(query=ims_query)
        if indent_raised_resp:
            return {
                "status": "success",
                "valid_indent_count": len(indent_raised_resp)
            }
        return {
            "status": "success",
            "valid_indent_count": 0
            }
    
    async def get_truck_allocated_direct_sales(self):
        ims_query = f"""SELECT "INDENT_NO","INDENT_DATE","PROD_REQD_DT","DEALER_CODE","TRUCK_REGNO",
                        "VALID_INDENT","CANCEL_INDENT" FROM "IMS_SAP"."INDENT_REQUEST" WHERE 
                        TO_CHAR("DELIVERY_DATE",'yyyymmdd') =  TO_CHAR(SYSDATE,'yyyymmdd')
                        AND SUBSTR("DEALER_CODE",15,2)='12' AND "VALID_INDENT" IN ('Y','H') AND ("CANCEL_INDENT" IS NULL OR "CANCEL_INDENT" <> 'Y')
                        AND "TRUCK_REGNO" IS NOT NULL AND "SEND_TO_JDE_TIME" IS NULL
                    """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        indent_raised_resp = await function(query=ims_query)
        if indent_raised_resp:
            return {
                "status": "success",
                "truck_allocated_count": len(indent_raised_resp)
            }
        return {
            "status": "success",
            "truck_allocated_count": 0
            }
    
    async def get_send_to_sap_direct_sales(self):
        ims_query = f"""SELECT "INDENT_NO","INDENT_DATE","PROD_REQD_DT","DEALER_CODE","TRUCK_REGNO",
                        "VALID_INDENT","CANCEL_INDENT" FROM "IMS_SAP"."INDENT_REQUEST" WHERE 
                        TO_CHAR("DELIVERY_DATE",'yyyymmdd') =  TO_CHAR(SYSDATE,'yyyymmdd')
                        AND SUBSTR("DEALER_CODE",15,2)='12' AND "TRUCK_REGNO" IS NOT NULL AND ("CANCEL_INDENT" IS NULL OR "CANCEL_INDENT" <> 'Y')
                        AND "VALID_INDENT" IN ('Y','H') AND "SEND_TO_JDE_TIME" IS NOT NULL
                    """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        indent_raised_resp = await function(query=ims_query)
        if indent_raised_resp:
            return {
                "status": "success",
                "indent_send_sap_count": len(indent_raised_resp)
            }
        return {
            "status": "success",
            "indent_send_sap_count": 0
            }
    
    async def get_sales_order_placed_direct_sales(self):
        ims_query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" a, 
                        "IMS_SAP"."INDENT_PRODUCTS" b WHERE SUBSTR(a."DEALER_CODE",15,2) = '12' AND
                        a."LOCN_CODE" = b."LOCN_CODE" 
                        AND TO_CHAR(a."DELIVERY_DATE",'yyyymmdd') =  TO_CHAR(SYSDATE,'yyyymmdd') 
                        AND a."CANCEL_INDENT" IS NULL AND a."TRUCK_REGNO" IS NOT NULL 
                        AND (a."VALID_INDENT" = 'Y' OR a."VALID_INDENT" = 'H')
                        AND a."BATCH_FLAG" = 'Y' AND b."SALES_ORDERNO" IS NOT NULL AND a."INDENT_NO"=b."INDENT_NO"
                    """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        indent_raised_resp = await function(query=ims_query)
        if indent_raised_resp:
            indent_raised_resp = indent_raised_resp[0]
            return {
                "status": "success",
                "sales_order_placed_count": indent_raised_resp.get("count")
            }
        return {
            "status": "success",
            "sales_order_placed_count": 0
        }
    
    async def get_r2_swipe_direct_sales(self):
        ims_query = f"""
                        SELECT COUNT(*) AS "count" FROM
                        "IMS_SAP"."INDENT_REQUEST" a,
                        "IMS_SAP"."TRUCK_SWIPE_ENTRY_SAP" b
                        WHERE a."LOCN_CODE" = b."LOCN_CODE"
                        AND TO_CHAR(a."DELIVERY_DATE",'yyyymmdd') =  TO_CHAR(SYSDATE,'yyyymmdd')
                        AND a."TRUCK_REGNO" = b."TRUCK_REGNO"
                        AND b."CARD_STATUS" = 'I'
                        AND a."DELIVERY_DATE" = b."CARD_DATE"
                        AND SUBSTR(a."DEALER_CODE",15,2)='12'
                        ORDER BY a."LOCN_CODE", a."TRUCK_REGNO", a."INDENT_NO",
                        TO_CHAR(a."PROD_REQD_DT",'yyyymmdd'), b."CARD_DATE"
                        """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        indent_raised_resp = await function(query=ims_query)
        if indent_raised_resp:
            indent_raised_resp = indent_raised_resp[0]
            return {
                "status": "success",
                "r2_swiped_count": indent_raised_resp.get("count")
            }
        return {
            "status": "success",
            "r2_swiped_count": 0
        }

    async def get_is_invoice_created_direct_sales(self):
        ims_query = f"""SELECT COUNT(*) AS "count"
                        FROM "IMS_SAP"."INDENT_REQUEST" a, 
                        "IMS_SAP"."INDENT_PRODUCTS" b 
                        WHERE SUBSTR(a."DEALER_CODE",15,2) = '12' 
                        AND a."LOCN_CODE" = b."LOCN_CODE" 
                        AND TO_CHAR(a."DELIVERY_DATE",'yyyymmdd') = TO_CHAR(SYSDATE,'yyyymmdd')
                        AND a."CANCEL_INDENT" IS NULL
                        AND a."DEALER_CODE" = b."DEALER_CODE" 
                        AND a."INDENT_NO" = b."INDENT_NO" AND b."INVOICE_NO" IS NOT NULL
                    """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        indent_raised_resp = await function(query=ims_query)
        if indent_raised_resp:
            indent_raised_resp = indent_raised_resp[0]
            return {
                "status": "success",
                "is_invoice_created_count": indent_raised_resp.get("count")
            }
        return {
            "status": "success",
            "is_invoice_created_count": 0
        }
    
    async def get_r3_swiped_direct_sales(self):
        ims_query = f"""
                        SELECT COUNT(*) AS "count" FROM
                        "IMS_SAP"."INDENT_REQUEST" a,
                        "IMS_SAP"."TRUCK_SWIPE_ENTRY_SAP" b
                        WHERE a."LOCN_CODE" = b."LOCN_CODE"
                        AND TO_CHAR(a."DELIVERY_DATE",'yyyymmdd') = TO_CHAR(SYSDATE,'yyyymmdd')
                        AND a."TRUCK_REGNO" = b."TRUCK_REGNO"
                        AND b."CARD_STATUS" = 'O'
                        AND a."DELIVERY_DATE" = b."CARD_DATE"
                        AND SUBSTR(a."DEALER_CODE",15,2)='12'
                        ORDER BY a."LOCN_CODE", a."TRUCK_REGNO", a."INDENT_NO",
                        TO_CHAR(a."PROD_REQD_DT",'yyyymmdd'), b."CARD_DATE"
                        """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        indent_raised_resp = await function(query=ims_query)
        if indent_raised_resp:
            indent_raised_resp = indent_raised_resp[0]
            return {
                "status": "success",
                "r3_swiped_count": indent_raised_resp.get("count")
            }
        return {
            "status": "success",
            "r3_swiped_count": 0
        }
    
# async def main():
#     obj = IndentDryOutDirectSales()
#     summary = {
#         "indent_raised": await obj.get_indent_raised_direct_sales(),
#         "indent_on_hold": await obj.get_indent_on_hold_direct_sales(),
#         "pending_indent": await obj.get_pending_indents_direct_sales(),
#         "valid_indent": await obj.get_valid_indent_direct_sales(),
#         "truck_allocated": await obj.get_truck_allocated_direct_sales(),
#         "indent_send_sap": await obj.get_send_to_sap_direct_sales(),
#         "sales_order_placed": await obj.get_sales_order_placed_direct_sales(),
#     }

#     print("Summary:", summary)

# if __name__ == "__main__":
#     asyncio.run(main())