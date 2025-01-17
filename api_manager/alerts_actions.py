import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import re
import pytz
import json
import datetime
import requests
import traceback
import utilities
from pathlib import Path
import utilities.helpers as helpers
import utilities.vts_mapping as vts_mapping
import orchestrator.alerting.alert_manager as alert_manager
import orchestrator.alerting.alert_factory as alert_factory
import orchestrator.actions.check_violation_count as check_violation_count

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


# Action upload_image
@router.post('/upload_image', tags=['Alerts'])
async def alerts_upload_image(upload_file: fastapi.UploadFile = fastapi.File(None)):
    try:
        UPLOAD_DIR = urdhva_base.settings.uploads  # Directory to save the uploaded files
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
        return false, "interlock name not found "
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
