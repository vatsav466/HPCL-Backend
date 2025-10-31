import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import os
import pytz
import json
import datetime
import requests
import traceback
import utilities
import polars as pl
from pathlib import Path
import utilities.helpers as helpers
from fastapi.responses import FileResponse
import utilities.vts_mapping as vts_mapping
from dateutil.relativedelta import relativedelta
import utilities.connection_mapping as connection_mapping
from utilities.helpers import generate_filter_query
import orchestrator.alerting.alert_manager as alert_manager
import orchestrator.alerting.alert_factory as alert_factory
import orchestrator.actions.check_violation_count as check_violation_count
import orchestrator.analytics.dry_out_analysis as dry_out_analysis

router = fastapi.APIRouter(prefix='/alerts')

logger = urdhva_base.logger.Logger.getInstance("api_manager")


# Action alert_action
@router.post('/alert_action', tags=['Alerts'])
async def alerts_alert_action(data: Alerts_Alert_ActionParams):
    """
    API endpoint to perform an action on an alert.

    Args:
    - data (Alerts_Alert_ActionParams): Alert action parameters

    Returns:
    - dict: Response with status, message and empty data
    """
    try:
        logger.info(f"Alert data received to perform action: {data}")
        return await alert_manager.AlertAction().update_alert_data(data.dict())
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"Error in performing action on alert: {e}, InputData {data.dict()}, Traceback: {traceback.format_exc()}")
        return False, "Error in performing action on alert"
        

# Action get_performance_index
@router.post('/get_performance_index', tags=['Alerts'])
async def alerts_get_performance_index(data: Alerts_Get_Performance_IndexParams):
    query = f"SELECT sap_id, name from location_master where bu='{data.bu}'"
    if not data.limit:
        data.limit = 100
    if not data.skip:
        data.skip = 0
    resp = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=data.limit, skip=data.skip)
    for rec in resp['data']:
        rec.update({"in_charge": "Location Incharge", "score": 99, "rank": 1})
    return resp['data']


# Action upload_document
@router.post('/upload_document', tags=['Alerts'])
async def alerts_upload_document(bu: str, upload_file: fastapi.UploadFile = fastapi.File(None)):
    try:
        UPLOAD_DIR = os.path.join(urdhva_base.settings.uploads, bu)  # Directory to save the uploaded files
        os.makedirs(UPLOAD_DIR, exist_ok=True)  # Ensure the upload directory exists

        # Validate the uploaded file type
        file_extension = Path(upload_file.filename).suffix.lower()
        allowed_extensions = [".png", ".jpg", ".jpeg", ".gif", ".csv", ".xlsx", ".xls", ".pdf", ".doc", ".docx"]
        if file_extension not in allowed_extensions:
            return fastapi.responses.JSONResponse(
                status_code=400, content={"message": "Unsupported file type"}
            )

        # Save the uploaded file
        file_name = upload_file.filename
        file_path = os.path.join(UPLOAD_DIR, file_name)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())

        # Generate encryption key and encrypt the file
        encrypted_file_key = helpers.encrypt_file(file_path)

        # Delete the original file
        os.remove(file_path)

        return {
            "message": "File uploaded and encrypted successfully",
            "original_file_path": file_path,
            "encrypted_file_key": encrypted_file_key,
        }

    except Exception as e:
        return fastapi.responses.JSONResponse(
            status_code=500, content={"message": "An error occurred", "details": str(e)}
        )


# Action intitiate_vts_exception
@router.post('/intitiate_vts_exception', tags=['Alerts'])
async def alerts_intitiate_vts_exception(data: Alerts_Intitiate_Vts_ExceptionParams):
    data=data.dict()
    alert_id = data["alert_id"]
    IST = pytz.timezone('Asia/Kolkata')
    current_time = datetime.datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')
    alert_data = await Alerts.get(int(alert_id))
    if not isinstance(alert_data, dict):
        alert_data = alert_data.__dict__
    print("alert_data----->",alert_data)
    #user = flask.session['sessionData']['email']
    user = ''
    altcount = await check_violation_count.CheckViolationCount().check_violation_count(alert_data['sap_id'],
                                                                                    alert_data['bu'],
                                                                                    alert_data['vehicle_number'], alert_data['violation_type'], alert_data["created_at"])
    altcount = altcount['count']
    print("altcount------>",altcount)
    details=vts_mapping.vts_exception_interlock_mapping[alert_data['violation_type']]
    max_limit = int(max(list(details['alerting_rules'].keys())))
    if altcount > max_limit:
        altcount = max_limit
    future_time = details['alerting_rules'][str(altcount)]['block_duration'] * 24 * 60 * 60
    # Add future_time to the original timestamp
    unblock_time = (alert_data["created_at"] + datetime.timedelta(seconds=future_time)).strftime('%d-%m-%Y')
    # Convert original created time to the desired format
    print("Unblock_time---->",unblock_time)
    alert_message = (
                        f"Exception request raised by: {user}, Message: {data["excep_msg"]} at {current_time}"
                        f"Violation Type:{alert_data["violation_type"]}"
                        f"Vehicle :{alert_data['vehicle_number']},Total Violation for {alert_data['violation_type']} by the Tank Lorry:{str(altcount)}"
                        f"Block Duration: {details['alerting_rules'][str(altcount)]['block_msg']} From {str(alert_data["created_at"])} to {str(unblock_time)}"
                    )
    #alert_data['']
    alert_history = [
        {
            "action_msg": alert_message,
            "action_type": "Created",  # Replace with an appropriate value
            "alert_status": "Open",  # Replace with the correct alert status
        }]
    interlock_details = utilities.interlock_mapping.get_interlock_name(
        alert_data['bu'], details['alerting_rules'][str(altcount)]['interlock_name'])
    if not interlock_details:
        return False, "interlock name not found "
    vts_alert_data={"bu": alert_data["bu"],
                    "alert_section": "VTS", 
                    "alert_history": alert_history, 
                    "clear_count": details['alerting_rules'][str(altcount)]['clear_count'], 
                    "sop_id":"SOP001E", "alert_message": "exception","sap_id":alert_data['sap_id'], 
                    "interlock_name": interlock_details["interlock_name"],
                    "origin_altid": data["alert_id"],
                    "vehicle_number": alert_data["vehicle_number"],
                    "violation_type": alert_data["violation_type"],
                    "location_name": alert_data['location_name']}
    
    query = (f"sap_id='{alert_data["sap_id"]}' and bu='{alert_data["bu"]}' and vehicle_number='{alert_data["vehicle_number"]}' "
             f"and sop_id='SOP001E' and alert_status='Open' and origin_altid='{alert_id}' and interlock_name='{interlock_details["interlock_name"]}'")
    data = await Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query),resp_type='plain')
    if data['total']!=0:
        logger.info("exist:%s" % (vts_alert_data))
        return True, "Exception already raised"
    else:
        camunda_url=urdhva_base.settings.camunda_url
        cls = alert_factory.AlertFactory()
        await cls.create_alert(vts_alert_data, camunda_url)


# Action get_frequent_dryout_ro
@router.post('/get_frequent_dryout_ro', tags=['Alerts'])
async def alerts_get_frequent_dryout_ro(data: Alerts_Get_Frequent_Dryout_RoParams):
    return await dry_out_analysis.current_month_frequent_dryout_ros(data)


# Action get_frequent_dryout_terminals
@router.post('/get_frequent_dryout_terminals', tags=['Alerts'])
async def alerts_get_frequent_dryout_terminals(data: Alerts_Get_Frequent_Dryout_TerminalsParams):
    return await dry_out_analysis.current_month_frequent_drout_terminals(data)


# Action get_closed_alerts_details
@router.post('/get_closed_alerts_details', tags=['Alerts'])
async def alerts_get_closed_alerts_details(data: Alerts_Get_Closed_Alerts_DetailsParams):
    if urdhva_base.context.context.exists():
        rpt = urdhva_base.context.context.get('rpt', {})
    else:
        rpt = {}

    alert_data = await Alerts.get(int(data.alert_id))
    if not isinstance(alert_data, dict):
        alert_data = alert_data.__dict__

    alert_role = alert_data['assigned_user_roles'] if alert_data['assigned_user_roles'] else ""

    close_alert_details = {
        "actions": {},
        "category": [],
        "rca_reason": []
    }
    action_data = connection_mapping.alert_action.get(data.bu)[data.alert_section]

    close_alert_details['category'] = list(action_data.get("category", {"Others": "Others"}).keys())
    if data.alert_section in ["VTS"]:
        if not data.category:
            for key in close_alert_details['category']:
                close_alert_details['rca_reason'].extend(action_data.get('category')[key])
        else:
            close_alert_details['rca_reason'].extend(action_data.get('category')[data.category])
    else:
        close_alert_details['rca_reason'] = action_data.get("rca_reason", ["Other"])


    all_actions = {
        key: value['name'] for key, value in action_data.get("actions", {}).items()
        if any(role in value.get("roles", []) for role in alert_role)
    }
    if data.alert_section in ["VTS"] and data.bu in ['TAS']:
        if alert_data.get("action_on","") in ['maker']:
            allowed = {"UnBlock", "Accept & Block"}
            close_alert_details['actions'] = {k: v for k, v in all_actions.items() if k in allowed}
        elif alert_data.get("action_on","") in ['checker']:
            allowed = {"Approve", "Reject", "Send It Back"}
            close_alert_details['actions'] = {k: v for k, v in all_actions.items() if k in allowed}
        else:
            close_alert_details['actions'] = all_actions
    else:
        close_alert_details['actions'] = all_actions
    return close_alert_details


# Action stored_document
@router.get('/stored_document', tags=['Alerts'])
async def alerts_stored_document(file_name: str):
    file_path = os.path.join(urdhva_base.settings.uploads, f"{file_name}.enc")
    file_path = f"{file_name}.enc"
    return FileResponse(
        file_path, filename=os.path.basename(file_name), media_type="application/octet-stream"
    )


# Action vts_alert_manager
@router.post('/vts_alert_manager', tags=['Alerts'])
async def alerts_vts_alert_manager(data: Alerts_Vts_Alert_ManagerParams):
    query = f"alert_section='VTS' AND alert_status='Open'"
    query = await generate_filter_query(data.filters, query)
    alert_data = await Alerts.get_all(
        urdhva_base.queryparams.QueryParams(
            q=query, limit=0
            ), resp_type='plain')
    
    required_columns =  [
            "bu", "tt_number", "sap_id", "location_name", "severity","zone",
            "instance_level", "instance_status", "violation_type",
            "maker", "checker", "actual_trip_end_date", "novex_alert_created_date",
            "vehicle_blocked_start_date", "vehicle_blocked_end_date", "alert_id", "id"
        ]
    if alert_data["data"]:
        alert_data = alert_data["data"]
        df = pl.DataFrame(alert_data)
        df = df.rename(
            {
                "unique_id": "alert_id", "interlock_name": "instance_level", 
                "vehicle_number": "tt_number", "device_id": "instance_status", 
                "assigned_user_roles": "maker", "last_escalated_to": "checker", 
                "external_timestamp": "actual_trip_end_date", "created_at": "novex_alert_created_date"
            }
        )
        df = df.select(required_columns)
        alert_data = df.to_dicts()
    return {"status": True, "message": "success", "data": alert_data}


# Action bulk_send_to_unblock
@router.post('/bulk_send_to_unblock', tags=['Alerts'])
async def alerts_bulk_send_to_unblock(data: Alerts_Bulk_Send_To_UnblockParams):
    try:
        if urdhva_base.context.context.exists():
            rpt = urdhva_base.context.context.get('rpt', {})
        else:
            rpt = {}

        if rpt.get("novex_role", None):
            if not any(role in rpt.get("novex_role") 
                       for role in ["Creator SOD", "Creator LPG", "Creator RO"]):
                return False, "Action not available for your Role"
        elif not rpt.get("novex_role", None):
            return False, "Session not found"
        
        alert_data = {}
        alert_data["task_type"] = "unblock"
        alert_data["alert_ids"] = data.alert_ids

        redis_queue = urdhva_base.redispool.RedisQueue('vts_unblocking_queue')
        await redis_queue.put(json.dumps(alert_data))
        return True, "Request sent successfully, Processing the request. Please wait for sometime"
    except Exception as e:
        print(traceback.format_exc())
        logger.error(e)
        return {"status": False, "message": "Error", "data": []}


# Action bulk_send_to_approve
@router.post('/bulk_send_to_approve', tags=['Alerts'])
async def alerts_bulk_send_to_approve(data: Alerts_Bulk_Send_To_ApproveParams):
    try:
        if urdhva_base.context.context.exists():
            rpt = urdhva_base.context.context.get('rpt', {})
        else:
            rpt = {}
                        
        if rpt.get("novex_role", None):
            if not any(role in rpt.get("novex_role") 
                       for role in ["Approver SOD", "Approver LPG", "Approver RO"]):
                return False, "Action not available for your Role"
        elif not rpt.get("novex_role", None):
            return False, "Session not found"
        
        alert_data = {}
        alert_data["task_type"] = "approve"
        alert_data["alert_ids"] = data.alert_ids

        redis_queue = urdhva_base.redispool.RedisQueue('vts_unblocking_queue')
        await redis_queue.put(json.dumps(alert_data))
        return True, "Approved successfully, Processing the approval. Please wait for sometime"
    except Exception as e:
        print(traceback.format_exc())
        logger.error(e)
        return {"status": False, "message": "Error", "data": []}
