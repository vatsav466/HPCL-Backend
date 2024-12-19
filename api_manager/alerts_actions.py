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
from pathlib import Path
import utilities.helpers as helpers
import orchestrator.alerting.alert_manager as alert_manager

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
        # Save the uploaded file
        file_extension = Path(upload_file.filename).suffix
        if file_extension.lower() not in [".png", ".jpg", ".jpeg", ".gif"]:
            return JSONResponse(
                status_code=400, content={"message": "Unsupported file type"}
            )

        # Save the uploaded file
        file_name = f"{upload_file.filename}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        with open(file_path, "wb") as f:
            f.write(await upload_file.read())

        # Generate encryption key and encrypt the file
        encrypted_file_path = helpers.encrypt_file(file_path)

        # Delete the original file
        os.remove(file_path)

        return {
            "message": "File uploaded and encrypted successfully",
            "file_path": file_path,
            "encrypted_file_key": encrypted_file_path,
        }

    except Exception as e:
        return fastapi.responses.JSONResponse(
            status_code=500, content={"message": "An error occurred", "details": str(e)}
        )
