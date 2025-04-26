import urdhva_base
from datetime import datetime
import traceback
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("alert_factory_log")

async def duplicate_check(alertdata):
    query = (
        f"""bu = 'TAS' and """
        f"""sap_id = '{alertdata.get('sap_id', '')}' and """
        f"""alert_section = 'TAS' and """
        f"""device_id = '{alertdata.get('device_id', '')}' and """
        f"""device_name = '{alertdata.get('device_name', '')}' and """
        f"""interlock_name = '{alertdata.get('interlock_name', '')}' and """
        f"""alert_status != 'Close'"""
    )
    logger.info("query --> ", query)
    params = urdhva_base.queryparams.QueryParams(q=query)
    resp = await hpcl_ceg_model.Alerts.get_all(params,resp_type='plain')

    if resp["data"]:
        #TODO: Check in the thingsboard using the device id where the
        # already the respective alert is in CLEARED_UNCAK if it is CLEARED_UNCAK then close the alert in the DB also manually
        return True
    return False


async def alert_history_check(alertdata, month_check=None):
    date_check = datetime.now().strftime("%Y-%m-%d")
    if month_check:
        month = datetime.now().strftime("%Y-%b")
        query = (
            f"""bu = 'TAS' and """
            f"""sap_id = '{alertdata.get('sap_id', '')}' and """
            f"""alert_section = 'TAS' and """
            f"""device_id = '{alertdata.get('device_id', '')}' and """
            f"""device_name = '{alertdata.get('device_name', '')}' and """
            f"""interlock_name = '{alertdata.get('interlock_name', '')}' and """
            f"""TO_CHAR(created_at, 'YYYY-Mon') = '{month}' and alert_status='Close'"""
        )
    else:
        query = (
            f"""bu = 'TAS' and """
            f"""sap_id = '{alertdata.get('sap_id', '')}' and """
            f"""alert_section = 'TAS' and """
            f"""device_id = '{alertdata.get('device_id', '')}' and """
            f"""device_name = '{alertdata.get('device_name', '')}' and """
            f"""interlock_name = '{alertdata.get('interlock_name', '')}' and """
            f"""DATE(created_at) = '{date_check}' and alert_status='Close' """
        )
    params = urdhva_base.queryparams.QueryParams(q=query)
    resp = await hpcl_ceg_model.Alerts.get_all(params,resp_type='plain')
    if resp["data"]:
        return True
    return False