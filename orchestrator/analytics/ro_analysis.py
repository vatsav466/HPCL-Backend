import urdhva_base
import json
import requests
import charts_actions
import hpcl_ceg_model
import dashboard_studio_model
import orchestrator.analytics.va_analysis as va_analysis
import utilities.cris_alert_mapping as cris_alert_mapping


async def interlock_disable(params: dict):
    """

    Args:
        params: {
            "rocode": "",
            "reqno": "",
            "interlocktype": "",
            "device": "",
            "deviceid": "",
            "disablehrs": ""
        }

    Returns:

    """
    alert_id = ""
    if 'alert_id' in params.keys():
        alert_id = params['alert_id']
        del params['alert_id']
    url = "https://crisuat.hpcl.co.in/HOSApp/dashboard/api/getinterlockreqdtls"
    default_headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=params, headers=default_headers)
        audit_data = {
            "method": "POST",
            "url": url,
            "payload": params,
            "alert_id": alert_id,
            "request_no": params['reqno'],
            "response": str(response.status_code),
            "response_msg": json.dumps(response.json()),
            "request_datetime": urdhva_base.utilities.get_present_time().isoformat(),
            "api_ack": None,
            "api_ack_datetime": None
        }
        await api_audit_log(audit_data=audit_data)
        return response.json()
    except Exception as e:
        print(f"Error while disabling interlock {e}")
        return {"status": False, "message": "Failed to post cris API"}

async def get_ro_alerts_count(bu: str, violation_type: str, sap_id: str):
    ro_mapping = cris_alert_mapping.Cris_Alert_Mapping
    if bu in ro_mapping.keys() and violation_type in ro_mapping[bu].keys():
        ro_mapping = ro_mapping[bu][violation_type]
        start_date, end_date = await va_analysis.get_period_datetime(ro_mapping['period'])
        query = (f"""select count(*) as "count" from alerts """
                 f"where bu = '{bu}' and "
                 f"alert_section = 'RO' and "
                 f"violation_type = '{violation_type}' and "
                 f"sap_id = '{sap_id}' and "
                 f"created_at BETWEEN TO_DATE('{start_date}', 'YYYY-MM-DD') AND TO_DATE('{end_date}', 'YYYY-MM-DD')")
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        print("Query: ", query)
        print(resp)
        if resp:
            resp = resp[0]
            return resp.get("count", 0)
    return 0

async def get_ro_levels(bu: str, violation_type: str, sap_id: str):
    ro_mapping = cris_alert_mapping.Cris_Alert_Mapping
    if bu in ro_mapping.keys() and violation_type in ro_mapping[bu].keys():
        ro_mapping = ro_mapping[bu][violation_type]
        ro_alert_count = await get_ro_alerts_count(bu=bu, violation_type=violation_type, sap_id=sap_id)
        previous_count = 0
        for key, value in ro_mapping['escalations'].items():
            if value['condition'] == "<":
                if int(ro_alert_count) <= int(value['value']):
                    return "level - 1"
            if value['condition'] == "<>":
                if int(previous_count) < ro_alert_count <= int(value['value']):
                    return "level - 2"
            if value['condition'] == ">":
                if ro_alert_count > int(value['value']):
                    return "level - 3"
            previous_count = value['value']
    return ""

async def check_alert_exists(alert_id, violation_type):
    query = f"select external_id from alerts where external_id = '{alert_id}' and bu = 'RO' and violation_type = '{violation_type}'"
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    resp = await function(query=query)
    print("Query: ", query)
    print("resp: ", resp)
    if resp:
        return True
    return False

async def api_audit_log(audit_data):
    """

    Args:
        audit_data:

    Returns:

    """
    return await hpcl_ceg_model.VendorApiAuditCreate(**audit_data).create()