import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import os
import pytz
import time
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
import orchestrator.analytics.vts_analysis as vts_analysis
from utilities.helpers import generate_filter_query, get_location_details
import orchestrator.alerting.alert_manager as alert_manager
import orchestrator.alerting.alert_factory as alert_factory
import orchestrator.actions.check_violation_count as check_violation_count
import orchestrator.analytics.dry_out_analysis as dry_out_analysis
from orchestrator.gen_ai.vts_nlp.core_functions import process_vts_query

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
    if data.alert_section in ["VTS"] and data.bu in ['TAS','LPG']:
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
    print("data",data)
    print("data filters",dir(data.filters))
    alert_status_value = next(
    (f.value for f in data.filters if f.key == 'alert_status'),
    None
)
    print("alert_status_value",alert_status_value)
    query = f"alert_section='VTS' AND alert_status='{alert_status_value}'"
    query = await generate_filter_query(data.filters, query)
    print("query",query)
    alert_data = await Alerts.get_all(
        urdhva_base.queryparams.QueryParams(
            q=query, limit=0
            ), resp_type='plain')
    # print("alert_data",alert_data)
    required_columns =  [
            "bu", "tt_number", "sap_id", "location_name", "severity","zone",
            "instance_level", "instance_status", "violation_type",
            "maker", "checker", "actual_trip_end_date", "novex_alert_created_date",
            "vehicle_blocked_start_date", "vehicle_blocked_end_date", "alert_id", "id","action_type","action_by"
        ]
    
    if alert_data["data"]:
        alert_data = alert_data["data"]
        df = pl.DataFrame(alert_data)
        '''
        df = df.with_columns(
            pl.col("alert_history")
            .str.json(pl.Struct)        # convert JSON string to struct
            .struct.field("action_type")        # pick only the action_type
            .alias("action_type")
        )
        '''
        df = df.with_columns(
    pl.col("alert_history")
      .list.last()                     # get last struct in the list
      .struct.field("action_type")     # extract action_type
      .alias("action_type")
)
        df = df.with_columns(
    pl.col("alert_history")
      .list.last()                     # get last struct in the list
      .struct.field("action_by")     # extract action_type
      .alias("action_by")
)
        print(df['action_type'].unique())
       
        df = df.rename(
            {
                "unique_id": "alert_id", "interlock_name": "instance_level", 
                "vehicle_number": "tt_number", "device_id": "instance_status", 
                "assigned_user_roles": "maker", "last_escalated_to": "checker", 
                "external_timestamp": "actual_trip_end_date", "created_at": "novex_alert_created_date"
            }
        )
        df = df.select(required_columns)
        print("columns",df.columns)

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


# Action block_vts_truck
@router.post('/block_vts_truck', tags=['Alerts'])
async def alerts_block_vts_truck(data: Alerts_Block_Vts_TruckParams):
    rpt = urdhva_base.context.context.get('rpt', {})
    if not rpt:
        return {"status": False, "message": "Session got expired, Please Re-Login"}
    
    if ("HQO HSE SOD" not in rpt.get('novex_role',[])) and ("HQO LPG" not in rpt.get('novex_role',[])):
        return {"status": False, "message": "Not Allowed To Perform This Action"}

    query = (f"""vehicle_unblocked_date is null and alert_section='VTS' and bu='{data.bu.value}' and vehicle_number='{data.truck_number}' """)
    print("-"*10)
    print("query :", query)
    print("-"*10)    

    alert_data = await Alerts.get_all(
        urdhva_base.queryparams.QueryParams(q=query),resp_type='plain'
        )
    
    query = f"blocking_status='blocked' and truck_number='{data.truck_number}'"
    manual_blocked = await VtsManualBlocked.get_all(
        urdhva_base.queryparams.QueryParams(q=query),resp_type='plain'
        )
    if alert_data["data"] or manual_blocked["data"]:
        return {"status": False, "message": "Truck has already been blocked"}
    
    headers = {
        "Content-Type": "application/json"
        }
    payload = {
        "VehicleRtoNo": data.truck_number
        }
    response = requests.post(
        urdhva_base.settings.vts_truck_status_url,
        json=payload,
        headers=headers,
        timeout=30
        )
    response = json.dumps(response.json(), indent=4)
    response = eval(response)

    print("-"*20)
    print("vts_truck_status :", response)
    print("-"*20)

    if isinstance(response, dict) and response.get("TripStatus", "").lower() == "loaded":
        return {"status": False, "message": "Cannot block as the truck is in a trip"}
    
    start_date = urdhva_base.utilities.get_present_time()
    end_date = start_date + relativedelta(days=data.blocking_days)

    transaction_number = str(int(time.time() * 1000))[-7:] + "1"

    if data.bu in ['TAS']:
        payload = [
            {
                "transactNo": transaction_number,
                "truckRegNo": data.truck_number,
                "blockingFlag": "Y",
                "blockingFrom": start_date.strftime("%Y%m%d"),
                "blockingTo": end_date.strftime("%Y%m%d")
            }
        ]
        print("-"*20)
        print("payload :", payload)
        print("-"*20)
        await vts_analysis.post_blocked_tt_ims(payload)
    
    if data.bu in ['LPG']:
        payload = {
                    "Request":{
                        "Request_ID": transaction_number,
                        "Vehicle_ID": data.truck_number,
                        "Status": "B",
                        "User_ID": "NOVEX_SYSTEM",
                        "IP_Address": urdhva_base.settings.server_ip
                    }
        }
        await vts_analysis.post_lpg_tt(payload)

    truck_details = {
        "bu": data.bu.value,
        "blocked_by": rpt["username"],
        "blocked_date": start_date,
        "truck_number": data.truck_number,
        "transaction_number": transaction_number,
        "blocking_status": "blocked",
        "blocking_flag": "Y",
        "blocking_days": data.blocking_days,
        "blocking_from": start_date,
        "blocking_to": end_date,
        "remarks": data.remarks
    }
    query = f"select sap_id from vts_truck_master where truck_no='{data.truck_number}'"
    location_data = await urdhva_base.BasePostgresModel.get_aggr_data(query)
    if location_data["data"]:
        location_data = location_data["data"][0]
        truck_details.update(
            {   
                "location_name": location_data.get("name", ""),
                "zone": location_data.get("zone", ""),
                "region": location_data.get("region", "")
            }
        )

    await VtsManualBlockedCreate(**truck_details).create()
    return {"status": True, "message": "Truck has been blocked successfully"}


# Action unblock_vts_truck
@router.post('/unblock_vts_truck', tags=['Alerts'])
async def alerts_unblock_vts_truck(data: Alerts_Unblock_Vts_TruckParams):
    try:
        rpt = urdhva_base.context.context.get('rpt', {})
        if not rpt:
            return {"status": False, "message": "Session got expired, Please Re-Login"}
        
        if ("HQO HSE SOD" not in rpt.get('novex_role',[])) and ("HQO LPG" not in rpt.get('novex_role',[])):
            return {"status": False, "message": "Not Allowed To Perform This Action"}

        alert_data = await VtsManualBlocked.get(int(data.unblock_id))
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__
        _date = urdhva_base.utilities.get_present_time()
        
        if alert_data['bu'] in ['TAS']:
            payload = [
                {
                    "transactNo": str(alert_data["transaction_number"]) + "0",
                    "truckRegNo": alert_data["truck_number"],
                    "blockingFlag": "N",
                    "blockingFrom": (alert_data['blocking_from'] + datetime.timedelta(hours=5, minutes=30)).strftime("%Y%m%d"),
                    "blockingTo": (alert_data['blocking_to'] + datetime.timedelta(hours=5, minutes=30)).strftime("%Y%m%d")
                }
            ]
            print("-"*20)
            print("payload :", payload)
            print("-"*20)
            await vts_analysis.post_blocked_tt_ims(payload)
        
        if alert_data['bu'] in ['LPG']:
            payload = {
                    "Request":{
                        "Request_ID": str(alert_data["transaction_number"]) + "0",
                        "Vehicle_ID": alert_data["truck_number"],
                        "Status": "U",
                        "User_ID": "NOVEX_SYSTEM",
                        "IP_Address": urdhva_base.settings.server_ip
                    }
            }
            print("-"*20)
            print("payload :", payload)
            print("-"*20)
            await vts_analysis.post_lpg_tt(payload)

        await VtsManualBlocked(**{
            "id": int(data.unblock_id),
            "unblocked_by": rpt["username"],
            "blocking_status": "unblocked",
            "blocking_flag": "N",
            "unblocked_date": _date
        }).modify()

        return {"status": True, "message": "Truck has been unblocked successfully"}
    except Exception:
        return {"status": False, "message": "Failed to unblock the truck"}


# Action get_vts_blocked_trucks
@router.post('/get_vts_blocked_trucks', tags=['Alerts'])
async def alerts_get_vts_blocked_trucks(data: Alerts_Get_Vts_Blocked_TrucksParams):

    tab = getattr(data, "tab", None)   

    # ============================================================
    # TAB 1: VTS BLOCKED LIST  (NO FILTERS SHOULD APPLY HERE)
    # ============================================================
    if tab == "vts":
        query = "blocking_status='blocked'"

       
        vts_params = urdhva_base.queryparams.QueryParams(q=query)

        alert_data = await VtsManualBlocked.get_all(vts_params, resp_type='plain')
        vts_blocked_data = alert_data.get("data", [])

        return {
            "status": True,
            "message": "success",
            "data": {
                "vts_blocked_list": vts_blocked_data
            }
        }


    # ============================================================
    # TAB 2: ALERT BLOCKED LIST (ONLY THIS NEEDS FILTERS)
    # ============================================================
    if tab == "alerts":

        # -------------------------
        # Extract BU from filters
        # -------------------------
        bu_value = None
        if data.cross_filters:
            for f in data.cross_filters:
                if getattr(f, "key", None) == "bu" and getattr(f, "value", None):
                    bu_value = f.value
                    break

        # -------------------------
        # Build alert query
        # -------------------------
        alert_query = "alert_status='Open' AND alert_section='VTS'"

        if bu_value:
            alert_query += f" AND bu='{bu_value}'"

        # -------------------------
        # Prepare params
        # -------------------------
        alert_params = urdhva_base.queryparams.QueryParams(q=alert_query , limit=0)
        alert_params.fields = [
            "bu",
            "zone",
            "location_name",
            "sap_id",
            "alert_status",
            "alert_section",
            "vehicle_number",
            "vehicle_blocked_start_date",
            "vehicle_blocked_end_date",
            "transporter_code",
            "unique_id"
        ]

        alerts_resp = await Alerts.get_all(alert_params, resp_type='plain')
        alert_blocked_data = alerts_resp.get("data", [])

        return {
            "status": True,
            "message": "success",
            "data": {
                "alert_blocked_list": alert_blocked_data
            }
        }


    # ============================================================
    # INVALID TAB HANDLING
    # ============================================================
    return {
        "status": False,
        "message": "Invalid tab. Valid values: 'vts', 'alerts'",
        "data": {}
    }

# Action get_vts_unblocked_trucks
@router.post('/get_vts_unblocked_trucks', tags=['Alerts'])
async def alerts_get_vts_unblocked_trucks(data: Alerts_Get_Vts_Unblocked_TrucksParams):
    query = "blocking_status='unblocked'"
    query = await generate_filter_query(data.cross_filters, query)
    alert_data = await VtsManualBlocked.get_all(
        urdhva_base.queryparams.QueryParams(q=query),resp_type='plain'
        )
    if alert_data["data"]:
        return {
            "status": True, 
            "message": "success", 
            "data": alert_data["data"]
            }
    
    return {
        "status": True, 
        "message": "No data found",
        "data": []
        }


# Action alerts_get_vts_query
@router.post('/alerts_get_vts_query', tags=['Alerts'])
async def alerts_alerts_get_vts_query(data: Alerts_Alerts_Get_Vts_QueryParams):
    """
    API endpoint to process VTS queries using LLM.
    Accepts vehicle_number with cross_filters.
    Returns vehicle details, prompt, or SQL query results.
    """
    try:
        logger.info(f"VTS Query request received: vehicle_number={data.vehicle_number}")
        
        # Log the cross_filters structure for debugging
        if data.cross_filters:
            logger.info(f"Cross filters received: {len(data.cross_filters)} items")
            for i, filter_item in enumerate(data.cross_filters):
                logger.info(f"Filter {i}: {filter_item.dict()}")
        
        result = await process_vts_query(vehicle_number=data.vehicle_number, cross_filters=data.cross_filters)
        return result
        
    except Exception as e:
        logger.error(f"Error in get_vts_query: {e}")
        logger.error(f"Input data: {data.dict() if hasattr(data, 'dict') else 'Unable to serialize'}")
        return {
            "success": False,
            "error": str(e),
            "message": "Internal error processing VTS query",
            "generated_sql": None
        }

# Action unblock_alert_truck
@router.post('/unblock_alert_truck', tags=['Alerts'])
async def alerts_unblock_alert_truck(data: Alerts_Unblock_Alert_TruckParams):
    try:
        rpt = urdhva_base.context.context.get("rpt", {})
        if not rpt:
            return {"status": False, "message": "Session expired, please login again"}

        username = rpt.get("username")
        unique_id = data.unique_id

        # ----------------------------
        # FETCH ALERT BY unique_id
        # ----------------------------
        params = urdhva_base.queryparams.QueryParams(
            q=f"unique_id='{unique_id}'", limit=1
        )
        params.fields = ["id", "alert_history", "alert_state", "alert_status"]

        alert_resp = await Alerts.get_all(params, resp_type="plain")

        if not alert_resp or not alert_resp.get("data"):
            return {"status": False, "message": "Alert not found"}

        alert = alert_resp["data"][0]
        alert_id = alert["id"]
        history = alert.get("alert_history", []) or []

        # ----------------------------
        # ADD NEW HISTORY DICT ONLY
        # ----------------------------
        new_history = {
            "action_msg": "Alert unblocked",
            "action_type": "UnBlocked",
            "allocated_time": urdhva_base.utilities.get_present_time().isoformat(),
            "processed_time": urdhva_base.utilities.get_present_time().isoformat(),
            "action_by": username
        }

        history.append(new_history)

        # ----------------------------
        # UPDATE MAIN ALERT
        # ----------------------------
        update_payload = {
            "id": alert_id,
            "alert_status": "Close",
            "alert_state": "Resolved",
            "alert_history": history
        }

        await Alerts(**update_payload).modify()

        return {"status": True, "message": "Alert unblocked successfully"}

    except Exception as e:
        print("Error:", e)
        return {"status": False, "message": "Failed to unblock alert"}
