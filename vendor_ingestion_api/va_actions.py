import urdhva_base
from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi
import json
import requests

router = fastapi.APIRouter(prefix='/va')

logger = urdhva_base.logger.Logger.getInstance("va_data_ingestion")

# Action ingest_data
@router.post('/ingest_data', tags=['VA'])
async def va_ingest_data(data: Va_Ingest_DataParams):
    """
    API endpoint to ingest VA data.

    Args:
    - data (Va_Ingest_DataParams): VA data ingestion parameters

    Processes each VA data entry by constructing a payload with vendor, location, and VA details,
    then sends it to the Camunda process engine for processing.

    Returns:
    - dict: Status message indicating the success of the data submission.
    """
    logger.info(f"Received VA data ingestion for Location {data.location_id}({data.location_type}) {data.dict()}")
    return True, "Success"

    # try:
        # header = {"Content-Type": "application/json", "Accept": "application/json"}

        # tagmap = dict()
        # alertid = ""
        
        # for _data in data.data:
        #     if isinstance(_data, dict):
        #         _data = _data.__dict__
        
        #     va_interlock = {"businessKey": alertid,
        #             "variables": {"vendor_id": {"value": data.vendor_id, "type": "String"},
        #                             "location_id": {"value": data.location_id, "type": "String"},
        #                             "location_type": {"value": data.location_type, "type": "String"},
        #                             "alert_type": {"value": _data['alert_type'], "type": "String"},
        #                             "alert_description": {"value": _data['alert_description'], "type": "String"},
        #                             "device_id": {"value": _data['device_id'], "type": "String"},
        #                             "video_url": {"value": _data['video_url'], "type": "String"}
        #                             }}
        #     camundaurl = urdhva_base.settings.camundaurl + "/engine-rest/process-definition/key/" + tagmap[alertname] + "/start"
        #     r = requests.post(camundaurl, headers=headers, data=json.dumps(va_interlock))
        #     logger.info("Justify for:%s Data:%s Camunda Resp:%s" % (businesskey, body, r.status_code))
        # return {
        #     "status": True, "message": "Justification Submitted", "data": []
        # }

    # except Exception as e:
    #     logger.error(e)
    #     return {"status": False, "message": "Error submitting justification", "data": []}
