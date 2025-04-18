import urdhva_base
import datetime
import traceback
import hpcl_ceg_model

async def duplicate_check(alertdata):
    query = (
        f"""bu = 'TAS' and """
        f"""alert_section = 'TAS' and """
        f"""device_id = '{alertdata.get('device_id', '')}' and """
        f"""device_name = '{alertdata.get('device_name', '')}' and """
        f"""interlock_name = '{alertdata.get('interlock_name', '')}'"""
        f"""alert_status != 'Close'"""
    )
    params = urdhva_base.queryparams.QueryParams(q=query)
    resp = await hpcl_ceg_model.Alerts.get_all(params,resp_type='plain')

    if resp["data"]:
        #TODO: Check in the thingsboard using the device id where the
        # already the respective alert is in CLEARED_UNCAK if it is CLEARED_UNCAK then close the alert in the DB also manually
        return True
    return False