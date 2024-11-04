from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi
import json
import requests
import urdhva_base

router = fastapi.APIRouter(prefix='/cris')

logger = urdhva_base.logger.Logger.getInstance("api_manager")


# Action ingest_data
@router.post('/ingest_data', tags=['CRIS'])
async def cris_ingest_data(data: Cris_Ingest_DataParams):
    """
    Endpoint to ingest data for CRIS.

    Args:
        data (Cris_Ingest_DataParams): The data parameters required for CRIS ingestion,
        including vendor ID, location ID, and optional list of crisDataCreate objects.

    Returns:
        JSON response with the status of the ingestion process.
    """
    
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
    
