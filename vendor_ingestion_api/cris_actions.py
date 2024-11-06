import urdhva_base
from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi
import json
import requests

router = fastapi.APIRouter(prefix='/cris')

logger = urdhva_base.logger.Logger.getInstance("cris_data_ingestion")

# Action ingest_data
@router.post('/ingest_data', tags=['CRIS'])
async def cris_ingest_data(data: Cris_Ingest_DataParams):
    """
    API endpoint to ingest CRIS data.

    Args:
    - data (Cris_Ingest_DataParams): Contains vendor ID, location ID, location type, 
      and a list of crisDataCreate objects with interlock details.

    Processes each interlock data entry by constructing a payload with vendor, location, 
    and interlock details, then sends it to the Camunda process engine for processing.

    Returns:
    - dict: Status message indicating the success of the data submission.
    """

    try:
        header = {"Content-Type": "application/json", "Accept": "application/json"}

        tagmap = dict()
        alertid = ""
        
        for _data in data.data:
            if isinstance(_data, dict):
                _data = _data.__dict__
        
            cris_interlock = {"businessKey": alertid,
                    "variables": {"vendor_id": {"value": data.vendor_id, "type": "String"},
                                    "location_id": {"value": data.location_id, "type": "String"},
                                    "location_type": {"value": data.location_type, "type": "String"},
                                    "interlock_type": {"value": _data['interlock_type'], "type": "String"},
                                    "interlock_description": {"value": _data['interlock_description'], "type": "String"},
                                    "device_id": {"value": _data['device_id'], "type": "String"},
                                    "device_value": {"value": _data['device_value'], "type": "String"}
                                    }}
            camundaurl = urdhva_base.settings.camundaurl + "/engine-rest/process-definition/key/" + tagmap[alertname] + "/start"
            r = requests.post(camundaurl, headers=headers, data=json.dumps(cris_interlock))
            logger.info("Justify for:%s Data:%s Camunda Resp:%s" % (businesskey, body, r.status_code))
        return {
            "status": True, "message": "Justification Submitted", "data": []
        }
        
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": str(e), "data": []}
