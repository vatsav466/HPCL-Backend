import urdhva_base
import json
import time
import requests
import traceback
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
    url = urdhva_base.settings.cris_interlock_disable_url
    default_headers = {"Content-Type": "application/json"}
    log_payload = {"status_code": 401, "response": {}}
    audit_data = {
        "method": "POST", "url": url, "payload": params, "alert_id": alert_id,
        "request_no": params['reqno'], "response": str(401), "vendor": "CRIS",
        "response_msg": json.dumps(log_payload), "request_datetime":
            urdhva_base.utilities.get_present_time().isoformat(), "api_ack": None, "api_ack_datetime": None
    }
    try:
        response = requests.post(url, json=params, headers=default_headers)
        try:
            response_data = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            response_data = {"raw_text": response.text or "Empty response"}
        log_payload = {"status_code": response.status_code, "response": response_data}
        audit_data['response'] = str(response.status_code)
        audit_data['response_msg'] = json.dumps(log_payload)
        await api_audit_log(audit_data=audit_data)
        return response.json()
    except Exception as e:
        print(traceback.format_exc())
        print(f"Error while disabling interlock {e}")
        await api_audit_log(audit_data=audit_data)
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
        # dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
        # dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        # function = await charts_actions.charts_connection_vault_routing(
        #     dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        # resp = await function(query=query)
        # print("Query: ", query)
        resp = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=0)
        resp = resp.get("data", [])
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

async def check_alert_exists(alert_id, violation_type, sap_id):
    query = (f"select external_id from alerts where external_id = '{alert_id}' and bu = 'RO' and "
             f"violation_type = '{violation_type}' and sap_id = '{sap_id}'")
    # dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
    # dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    # function = await charts_actions.charts_connection_vault_routing(
    #     dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    # resp = await function(query=query)
    resp = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=0)
    resp = resp.get("data", [])
    # print("Query: ", query)
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

async def get_process_instance_id(business_key, camunda_url):
    camunda_url = f"{camunda_url}/engine-rest/process-instance"
    params = {"businessKey": business_key}
    response = requests.get(camunda_url, params=params)
    process_instance_id = ""
    if response.status_code == 200:
        instances = response.json()
        if instances:
            process_instance_id = instances[0]["id"]  # Get first instance ID
            return process_instance_id
    return process_instance_id

async def close_camunda_workflow(alert_data, camunda_url):
    # camunda_url = await helpers.get_alert_camunda_url(self.params['alert_id'], "error")
    MAX_RETRIES = 5
    RETRY_DELAY = 5
    headers = {"Content-Type": "application/json"}
    if camunda_url != 'error':
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__
        # instance_id = alert_data.get("workflow_instance_id")
        business_key = alert_data.get("unique_id")
        instance_id = await get_process_instance_id(business_key, camunda_url)
        if not instance_id:
            instance_id = alert_data.get("workflow_instance_id")
        url = f"{camunda_url}/engine-rest/process-instance/{instance_id}"
        print("instance_id: ", instance_id)
        if not instance_id:
            return False
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.delete(url, headers=headers)

                if response.status_code == 204:  # Success in Camunda
                    print(f"Workflow {instance_id} Deleted successfully. Alert ID {alert_data['id']}")
                    break
                else:
                    print(
                        f"Error Deleting {instance_id} {camunda_url} (attempt {attempt + 1}): {response.status_code} - {response.text}")

            except requests.RequestException as e:
                print(f"Request error for {camunda_url} {instance_id} (attempt {attempt + 1}): {e}")

            # Retry logic with exponential backoff
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (2 ** attempt))
            else:
                print(f"Failed to Deleting {camunda_url} {instance_id} after {MAX_RETRIES} retries.")
                return False
        return True
    return False