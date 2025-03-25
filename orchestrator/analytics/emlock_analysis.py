import urdhva_base
import pytz
import requests
import datetime
import charts_actions
import hpcl_ceg_model
import dashboard_studio_model
import orchestrator.alerting.alert_manager as alert_manager
import orchestrator.alerting.alert_factory as alert_factory
import orchestrator.dbconnector.credential_loader as credential_loader
from utilities.connection_mapping import product_code_mapping, connection_mapping


async def get_emlock_headers():
    redis_ins = await urdhva_base.redispool.get_redis_connection()
    vendor = "hpcl_emlock"
    db_access_key = ""
    if await redis_ins.hexists("vendor_auth", f"{vendor}_access_key"):
        db_access_key = await redis_ins.hget("vendor_auth", f"{vendor}_access_key")
    headers = {
        "Content-Type": "application/json",
        "ceg-auth-token": db_access_key
    }
    return headers

async def close_emlock_alert(alert_data: dict):
    """
    Args:
        alert_data:{
            "emlockExceptionId":"6146",
            "terminalCode":"location code",
            "truckNumber":"TT Reg No",
            "exceptionType":"exception name",
            "status":"1",
            "acknowledgedUser":"Employee code",
            "acknowledgedTime":"2025-02-01 17:00:00",
            "remarks":"",
            "metaData": "{'loadNumber':'456123','fanNumber':'987456', 'invoiceNumber':'987456-
123','tripType':'single', 'roCode':'123', 'terminalCode':''}"
        }

    Returns:

    """

    headers = await get_emlock_headers()
    creds = credential_loader.get_credentials("EM_LOCK")
    url = f"http://{creds['host']}:{creds['port']}/api/exceptionCloseAlert"
    response = requests.post(
        url=url, json=alert_data, headers=headers
    )
    if response.status_code // 100 == 2:
        return {"status": True, "message": "Data posted successfully", "data": response.json()}
    return {"status": False, "message": "Data posting unsuccessfully", "data": response.json()}

async def close_alerts_by_schedule():
    time_stamp = datetime.datetime.now(datetime.timezone.utc)
    to_day = time_stamp.astimezone(pytz.timezone('Asia/Kolkata')) - datetime.timedelta(1)

    query = f"select id from alerts where alert_status != 'Close' and created_at::date = '{to_day}' and alert_section = 'EMLock'"
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    alerts = await function(query=query)
    for alert in alerts:
        alert_data = await hpcl_ceg_model.Alerts.get(alert['id'])
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__
        alert_data['alert_id'] = alert_data['id']
        input_data = {
            "action_type": "Message",
            "action_msg": "SYSTEM Auto Closed On EOD"
        }
        # Updating Alert History
        await alert_manager.AlertAction().update_alert_history(input_data, alert_data)

        # Closing Alert Data.
        await alert_factory.AlertFactory().close_alert(alert_data)
        break
    return {"status": True, "message": "Alerts Closed"}

async def close_alerts_by_vendor():
    query = (f"select id, external_id from alerts where alert_section = 'EMLock' and alert_status != 'Close' and "
             f"created_at between date_trunc('day', now()) and now() - interval '30 minutes'")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    alerts = await function(query=query)
    alert_mapping = {x['external_id']: x['id'] for x in alerts}
    creds = credential_loader.get_credentials("EM_LOCK")
    url = f"http://{creds['host']}:{creds['port']}/api/exceptionStatusCheck"
    headers = await get_emlock_headers()
    response = requests.post(
        url=url, json={"emlockExceptionIds": list(alert_mapping.keys())}, headers=headers
    )
    response = response.json()
    for status in response:
        if status['status'] == 'INACTIVE':
            alert_data = await hpcl_ceg_model.Alerts.get(alert_mapping.get("emlockExceptionId"))
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__
            alert_data['alert_id'] = alert_data['id']
            input_data = {
                "action_type": "Message",
                "action_msg": "SYSTEM Auto Closed Response From Vendor"
            }
            # Updating Alert History
            await alert_manager.AlertAction().update_alert_history(input_data, alert_data)

            # Closing Alert Data.
            await alert_factory.AlertFactory().close_alert(alert_data)
            break
    return {"status": True, "message": "Alerts Closed"}
