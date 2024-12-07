import urdhva_base
import datetime
import charts_actions
from hpcl_ceg_enum import AlertState as AlertState
from hpcl_ceg_enum import AlertStatus as AlertStatus
from hpcl_ceg_enum import IndentStatus as IndentStatus
import utilities.connection_mapping as connection_mapping
from hpcl_ceg_model import Alerts_Alert_ActionParams, Alerts
from hpcl_ceg_enum import AlertActionType as AlertActionType
from alerts_actions import alerts_alert_action as alerts_alert_action
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams


class IndentDryOut:
    def __init__(self):
        self.params = dict()

    async def prod_code_mapping(self):
        _mapping_code = {
            "MS": "2811000",
            "HSD": "2812000",
            "TURBO": "3912000",
            "E20": "2822000",
            "POWER 95": "3672000",
            "POWER 99": "2816000",
            "POWER 100": "3373000"
        }
        return _mapping_code

    async def get_connection_name(self):
        self.params['connection_name'] = connection_mapping.connection_mapping.get(
            self.params['connection_name'], self.params['connection_name']
        )

    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the action.

        Returns:
            list: A list of strings representing the required variables.
        """
        return [
            "alert_id", "bu", "interlock_name", "interlock_id",
            "dealer_id", "connection_name", "indent_no", "location_no",
            "product_code", "sap_id", "sop_id",
        ]

    async def send_alert_action(
            self,
            is_atr_uploaded: bool = False,
            is_maintenance_exception: bool = False,
            is_revocation: bool = False,
            no_exception: bool = False,
            is_approved: bool = False,
            is_exc_approval_time_exp: bool = False,
            is_raised: bool = False,
            is_cancelled: bool = False,
            is_allocated: bool = False,
            is_sent_to_sap: bool = False,
            is_order_placed: bool = False,
            is_created: bool = False
    ):
        msg_block = {
            "isAtrUploaded": is_atr_uploaded,
            "isMaintenanceException": is_maintenance_exception,
            "isRevocation": is_revocation,
            "noException": no_exception,
            "approved": is_approved,
            "isExcApprovalTimeExp": is_exc_approval_time_exp,
            "raised": is_raised,
            "cancelled": is_cancelled,
            "allocated": is_allocated,
            "senttosap": is_sent_to_sap,
            "orderplaced": is_order_placed,
            "created": is_created
        }
        return True, msg_block

    async def check_indent_status(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        print("Params: ", self.params)
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        dealer_code = self.params.get("dealer_id")
        now = (datetime.datetime.now() - datetime.timedelta(days=0)).strftime("%Y-%m-%d")
        next_date = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" WHERE SUBSTR(DEALER_CODE,1,10) = '{dealer_code}' """ \
                f"AND PROD_REQD_DT BETWEEN TO_DATE('{now}', 'YYYY-MM-DD') AND TO_DATE('{next_date}', 'YYYY-MM-DD') AND CANCEL_INDENT IS NULL"
        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        if not resp:
            return False, {}
        resp = resp[0]
        if resp.get("count") > 0:
            # await self.update_alert_status(indent_status=IndentStatus.IndentRaised)
            return await self.send_alert_action(is_raised=True)
        await self.update_alert_status(indent_status=IndentStatus.IndentNotRaised)
        return await self.send_alert_action(is_raised=False)

    async def is_truck_allocated(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        dealer_code = self.params.get("dealer_id")
        now = (datetime.datetime.now() - datetime.timedelta(days=0)).strftime("%Y-%m-%d")
        next_date = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" WHERE SUBSTR(DEALER_CODE,1,10) = '{dealer_code}' """ \
                f"AND PROD_REQD_DT BETWEEN TO_DATE('{now}', 'YYYY-MM-DD') AND TO_DATE('{next_date}', 'YYYY-MM-DD') AND CANCEL_INDENT IS NULL AND TRUCK_REGNO IS NULL"
        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        print("resp: ", resp)
        if not resp:
            return False, {}
        resp = resp[0]
        if resp.get("count") > 0:
            await self.update_alert_status(indent_status=IndentStatus.TruckNotAllocated)
            return await self.send_alert_action(is_allocated=False)
        await self.update_alert_status(indent_status=IndentStatus.TruckAllocated)
        return await self.send_alert_action(is_allocated=True)

    async def is_indent_cancelled(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        dealer_code = self.params.get("dealer_id")
        now = (datetime.datetime.now() - datetime.timedelta(days=0)).strftime("%Y-%m-%d")
        next_date = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" WHERE SUBSTR(DEALER_CODE,1,10) = '{dealer_code}' """ \
                f"AND PROD_REQD_DT BETWEEN TO_DATE('{now}', 'YYYY-MM-DD') AND TO_DATE('{next_date}', 'YYYY-MM-DD') AND CANCEL_INDENT IS NOT NULL"
        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        if not resp:
            return False, {}
        resp = resp[0]
        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" WHERE SUBSTR(DEALER_CODE,1,10) = '{dealer_code}' """ \
                f"AND PROD_REQD_DT BETWEEN TO_DATE('{now}', 'YYYY-MM-DD') AND TO_DATE('{next_date}', 'YYYY-MM-DD')"
        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp_1 = await function(query=query)
        if not resp_1:
            return False, {}
        resp_1 = resp_1[0]
        if resp.get("count") > 0 & resp_1.get("count") == resp.get("count"):
            await self.update_alert_status(
                indent_status=IndentStatus.Cancelled,
                alert_status=AlertStatus.Close,
                alert_state=AlertState.Resolved
            )
            return await self.send_alert_action(is_cancelled=True)
        return await self.send_alert_action(is_cancelled=False)

    async def is_indent_on_hold(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        dealer_code = self.params.get("dealer_id")
        now = (datetime.datetime.now() - datetime.timedelta(days=0)).strftime("%Y-%m-%d")
        next_date = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" WHERE SUBSTR(DEALER_CODE,1,10) = '{dealer_code}' """ \
                f"AND PROD_REQD_DT BETWEEN TO_DATE('{now}', 'YYYY-MM-DD') AND TO_DATE('{next_date}', 'YYYY-MM-DD') AND CANCEL_INDENT IS NULL AND VALID_INDENT = 'N'"
        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        if not resp:
            return False, {}
        resp = resp[0]
        if resp.get("count") > 0:
            await self.update_alert_status(
                indent_status=IndentStatus.IndentOnHold,
                alert_status=AlertStatus.OnHold,
                alert_state=AlertState.InProgress
            )
            return await self.send_alert_action(is_raised=True)
        return await self.send_alert_action(is_raised=False)

    async def is_indent_valid(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        dealer_code = self.params.get("dealer_id")
        now = (datetime.datetime.now() - datetime.timedelta(days=0)).strftime("%Y-%m-%d")
        next_date = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" WHERE SUBSTR(DEALER_CODE,1,10) = '{dealer_code}' """ \
                f"AND PROD_REQD_DT BETWEEN TO_DATE('{now}', 'YYYY-MM-DD') AND TO_DATE('{next_date}', 'YYYY-MM-DD') AND CANCEL_INDENT IS NULL AND " \
                f"(VALID_INDENT = 'Y' OR VALID_INDENT = 'H')"
        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        if not resp:
            return False, {}
        resp = resp[0]
        if resp.get("count") > 0:
            await self.update_alert_status(indent_status=IndentStatus.ValidIndent)
            return await self.send_alert_action(is_raised=True)
        await self.update_alert_status(indent_status=IndentStatus.IndentOnHold)
        return await self.send_alert_action(is_raised=False)

    async def is_indent_sent_sap(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        dealer_code = self.params.get("dealer_id")
        now = (datetime.datetime.now() - datetime.timedelta(days=0)).strftime("%Y-%m-%d")
        next_date = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" WHERE SUBSTR(DEALER_CODE,1,10) = '{dealer_code}' """ \
                f"AND PROD_REQD_DT BETWEEN TO_DATE('{now}', 'YYYY-MM-DD') AND TO_DATE('{next_date}', 'YYYY-MM-DD') AND CANCEL_INDENT IS NULL AND " \
                f"(VALID_INDENT = 'Y' OR VALID_INDENT = 'H') AND BATCH_FLAG = 'Y'"
        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        print(resp)
        if not resp:
            return False, {}
        resp = resp[0]
        if resp.get("count") > 0:
            await self.update_alert_status(indent_status=IndentStatus.SentToSAP)
            return await self.send_alert_action(is_sent_to_sap=True)
        return await self.send_alert_action(is_sent_to_sap=False)

    async def check_r1_status(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        r1_status = self.params.get("r1_status")
        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" WHERE R1_STATUS = '{r1_status}'"""
        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        print(resp)
        if resp:
            return True
        return False

    async def check_r2_status(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        r2_status = self.params.get("r2_status")
        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" WHERE R2_STATUS = '{r2_status}'"""
        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        print(resp)
        if not resp:
            return False, {}
        resp = resp[0]
        if resp.get("count") > 0:
            return True, {"msg": "R2 status is generated"}
        return False, {}

    async def check_r3_status(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        r3_status = self.params.get("r3_status")
        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" WHERE R3_STATUS = '{r3_status}'"""
        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        print(resp)
        if resp:
            return True
        return False

    async def is_invoice_created(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        dealer_code = self.params.get("dealer_id")
        now = (datetime.datetime.now() - datetime.timedelta(days=0)).strftime("%Y-%m-%d")
        next_date = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        indent_no = self.params.get("indent_no")
        location_no = self.params.get("location_no")
        query = f"""SELECT * FROM "IMS_SAP"."INDENT_PRODUCTS" where SUBSTR(DEALER_CODE,1,10) = '{dealer_code}' """ \
                f"AND PROD_REQD_DT BETWEEN TO_DATE('{now}', 'YYYY-MM-DD') AND TO_DATE('{next_date}', 'YYYY-MM-DD') AND INDENT_NO = '{indent_no}' " \
                f"AND LOCN_CODE = '{location_no}' AND SALES_ORDERNO IS NOT NULL AND INVOICE_NO IS NOT NULL"

        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        if not resp:
            return False, {}
        resp = resp[0]
        if resp.get("count") > 0:
            await self.update_alert_status(
                indent_status=IndentStatus.Completed,
                alert_status=AlertStatus.Close,
                alert_state=AlertState.Resolved
            )
            # await self.update_alert_status(indent_status=IndentStatus.InvoiceCreated)
            return await self.send_alert_action(is_created=True)
        return await self.send_alert_action(is_created=False)

    async def check_sales_order(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        dealer_code = self.params.get("dealer_id")
        now = (datetime.datetime.now() - datetime.timedelta(days=0)).strftime("%Y-%m-%d")
        next_date = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        indent_no = self.params.get("indent_no")
        location_no = self.params.get("location_no")

        query = f"""SELECT COUNT(*) AS "count" FROM "IMS_SAP"."INDENT_REQUEST" AS a, "IMS_SAP"."INDENT_PRODUCTS" AS b WHERE SUBSTR(a.DEALER_CODE,1,10) = '{dealer_code}' AND """ \
                f"a.LOCN_CODE = b.LOCN_CODE AND a.PROD_REQD_DT BETWEEN TO_DATE('{now}', 'YYYY-MM-DD') AND TO_DATE('{next_date}', 'YYYY-MM-DD') AND a.INDENT_NO = b.INDENT_NO " \
                f"AND a.CANCEL_INDENT IS NULL AND a.TRUCK_REGNO IS NOT NULL AND (a.VALID_INDENT = 'Y' OR a.VALID_INDENT = 'H') " \
                f"AND a.BATCH_FLAG = 'Y' AND b.SALES_ORDERNO IS NOT NULL"

        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        if not resp:
            return False, {}
        resp = resp[0]
        if resp.get("count") > 0:
            await self.update_alert_status(indent_status=IndentStatus.SalesOrderPlaced)
            return await self.send_alert_action(is_order_placed=True)
        return await self.send_alert_action(is_order_placed=False)

    async def indent_wait_time(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        start_time = datetime.time(6, 0)  # 6:00 AM
        end_time = datetime.time(16, 0)  # 4:00 PM

        current_time = datetime.datetime.now().time()

        if start_time <= current_time <= end_time:
            return await self.send_alert_action(is_approved=True)
        return await self.send_alert_action(is_approved=False)

    async def update_alert_status(
            self,
            indent_status: str,
            alert_status: str = AlertStatus.InProgress,
            alert_state: str = AlertState.InProgress
    ):
        alert_id = self.params.get("alert_id")
        alert_data = await Alerts.get(alert_id)
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__
        alert_data['indent_status'] = indent_status
        alert_data['alert_status'] = alert_status
        alert_data['alert_state'] = alert_state
        print("alert_data: ", alert_data)
        alert_data = Alerts(**alert_data)
        await alert_data.modify()

    async def get_prod_code_and_indent_no(self, params: dict):
        if not self.params:
            self.params = params
            await self.get_connection_name()
        _mapping = await self.prod_code_mapping()
        indent_no = self.params.get("indent_no")
        location_no = self.params.get("location_no")

        prod_code = _mapping.get(self.params.get("product_code"))

        Charts_Connection_Vault_RoutingParams.connection_id = self.params['connection_name']
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        dealer_code = self.params.get("dealer_id")
        now = (datetime.datetime.now() - datetime.timedelta(days=0)).strftime("%Y-%m-%d")
        next_date = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        query = f"""SELECT a.INDENT_NO AS "indent_no", b.PROD AS "product_no" FROM "IMS_SAP"."INDENT_REQUEST" AS a, "IMS_SAP"."INDENT_PRODUCTS" AS b WHERE SUBSTR(a.DEALER_CODE,1,10) = '{dealer_code}' AND """ \
                f"a.LOCN_CODE = b.LOCN_CODE AND a.PROD_REQD_DT BETWEEN TO_DATE('{now}', 'YYYY-MM-DD') AND TO_DATE('{next_date}', 'YYYY-MM-DD') AND a.INDENT_NO = b.INDENT_NO " \
                f"AND a.CANCEL_INDENT IS NULL AND (a.VALID_INDENT = 'Y' OR a.VALID_INDENT = 'H') "

        function = await charts_actions.charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        print("resp: ", resp)
        if not resp:
            return False, {}
        result = {}
        for entry in resp:
            indent_no = entry["indent_no"]
            product_no = entry["product_no"]
            if indent_no not in result:
                result[indent_no] = []
            result[indent_no].append(product_no)
        return result
