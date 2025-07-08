import urdhva_base
from datetime import datetime
import traceback
import hpcl_ceg_model
import aiohttp
from orchestrator.alerting.alert_manager import close_alert
from orchestrator.alerting.listener.tas_duplicate_alert_check import get_thingsboard_jwt, check_tb_alert_status


logger = urdhva_base.logger.Logger.getInstance("alert_factory_log")

THINGSBOARD_URL = urdhva_base.settings.things_board_url
THINGSBOARD_USERNAME = urdhva_base.settings.things_board_username
THINGSBOARD_PASSWORD = urdhva_base.settings.things_board_password

async def close_all_cleared_alerts():
    query = "bu = 'TAS' and alert_section = 'TAS' and alert_status != 'Close'"
    params = urdhva_base.queryparams.QueryParams(q=query)
    resp = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
    
    if not resp.get("data"):
        print("No alerts found to close.")
        return
    
    # need to handle multiple records 300+ records
    for alert in resp["data"]:
        jwt_token = await get_thingsboard_jwt()
        external_id = alert.get("external_id", "").strip()
        if external_id:
            print(f"Processing alert with external_id: {external_id}")
            tb_status = await check_tb_alert_status(external_id, jwt_token)
            print(f"Alert status from ThingsBoard: {tb_status}")
            
            if tb_status == "CLEARED_UNACK":
                alert_data = {
                    "bu": alert.get("bu"),
                    "sap_id": alert.get("sap_id"),
                    "sop_id": alert.get("sop_id"),
                    "alert_type": 'TAS',
                    "interlock_name": alert.get("interlock_name", ""),
                    "alert_id": external_id,
                    "device_name": alert.get("device_name", "")
                }
                await close_alert(alert_data)
                print(f"Closed alert with external_id: {external_id}")

async def main():
    try:
        await close_all_cleared_alerts()
    except Exception as e:
        print(f"Error closing alerts: {e}")
        print(traceback.format_exc())