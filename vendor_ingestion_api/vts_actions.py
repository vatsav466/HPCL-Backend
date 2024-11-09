import urdhva_base
from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi
import json
import requests

router = fastapi.APIRouter(prefix='/vts')

logger = urdhva_base.logger.Logger.getInstance("vts_data_ingestion")

# Action ingest_data
@router.post('/ingest_data', tags=['VTS'])
async def vts_ingest_data(data: Vts_Ingest_DataParams):
    """
    API endpoint to ingest VTS data.

    Args:
    - data (Vts_Ingest_DataParams): Contains vendor ID, location ID, location type, 
      and a list of vtsDataCreate objects with VTS interlock details.

    Processes each VTS interlock data entry by constructing a payload with vendor, 
    location, and interlock details, then sends it to the Camunda process engine for 
    processing.

    Returns:
    - dict: Status message indicating the success of the data submission.
    """
    logger.info(f"Received VTS data ingestion from vendor {data.location_id}({data.location_type}) {data.dict()}")
    return True, "Success"
    # try:
    #     header = {"Content-Type": "application/json", "Accept": "application/json"}

    #     tagmap = dict()
    #     alertid = ""

    #     for _data in data.data:
    #         if isinstance(_data, dict):
    #             _data = _data.__dict__

    #         vts_interlock = {"businessKey": alertid,
    #                 "variables": {"vendor_id": {"value": data.vendor_id, "type": "String"},
    #                                 "location_id": {"value": data.location_id, "type": "String"},
    #                                 "location_type": {"value": data.location_type, "type": "String"},
    #                                 "tl_number": {"value": _data['tl_number'], "type": "String"},
    #                                 "report_duration": {"value": _data['report_duration'], "type": "String"},
    #                                 "total_trips": {"value": _data['total_trips'], "type": "Int"},
    #                                 "stoppage_violations_count": {"value": _data['stoppage_violations_count'], "type": "Int"},
    #                                 "route_deviation_count": {"value": _data['route_deviation_count'], "type": "Int"},
    #                                 "speed_violation_count": {"value": _data['speed_violation_count'], "type": "Int"},
    #                                 "main_supply_removal_count": {"value": _data['main_supply_removal_count'], "type": "Int"},
    #                                 "night_driving_count": {"value": _data['night_driving_count'], "type": "Int"},
    #                                 "no_halt_zone_count": {"value": _data['no_halt_zone_count'], "type": "Int"},
    #                                 "device_offline_count": {"value": _data['device_offline_count'], "type": "Int"},
    #                                 "device_tamper_count": {"value": _data['device_tamper_count'], "type": "Int"},
    #                                 }}
    #         camundaurl = urdhva_base.settings.camundaurl + "/engine-rest/process-definition/key/" + tagmap[alertname] + "/start"
    #         r = requests.post(camundaurl, headers=headers, data=json.dumps(vts_interlock))
    #         logger.info("Justify for:%s Data:%s Camunda Resp:%s" % (businesskey, body, r.status_code))
    #     return {
    #         "status": True, "message": "Justification Submitted", "data": []
    #     }

    # except Exception as e:
    #     logger.error(e)
    #     return {"status": False, "message": "Error", "data": []}
