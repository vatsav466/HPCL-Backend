import urdhva_base
import api_manager.hpcl_ceg_model as hpcl_ceg_model
from datetime import datetime


class BCUAlertCondtions:
    async def alert_history_check(params):
        date_check = datetime.now().strftime("%Y-%m-%d")
        if params.get("month_check"):
            month = datetime.now().strftime("%Y-%b")
            query = (
                f"""bu = 'TAS' and """
                f"""sap_id = '{params.get('sap_id', '')}' and """
                f"""alert_section = 'TAS' and """
                f"""device_id = '{params.get('device_id', '')}' and """
                f"""device_name = '{params.get('device_name', '')}' and """
                f"""interlock_name = '{params.get('interlock_name', '')}' and """
                f"""TO_CHAR(created_at, 'YYYY-Mon') = '{month}' and alert_status='Close'"""
            )
        else:
            query = (
                f"""bu = 'TAS' and """
                f"""sap_id = '{params.get('sap_id', '')}' and """
                f"""alert_section = 'TAS' and """
                f"""device_id = '{params.get('device_id', '')}' and """
                f"""device_name = '{params.get('device_name', '')}' and """
                f"""interlock_name = '{params.get('interlock_name', '')}' and """
                f"""DATE(created_at) = '{date_check}' and alert_status='Close' """
            )
        params = urdhva_base.queryparams.QueryParams(q=query)
        resp = await hpcl_ceg_model.Alerts.get_all(params,resp_type='plain')
        if resp["data"]:
            return True, "not approved"
        return True, "approved"