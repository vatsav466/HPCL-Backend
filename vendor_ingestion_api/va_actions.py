import urdhva_base
from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi
import json
import pytz
import requests
import datetime
import traceback
import hpcl_ceg_model
import orchestrator.alerting.alert_manager as alert_manager

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
    try:
      logger.info(f"Received VA data ingestion from vendor {data.location_id}({data.location_type}) {data.dict()}")
      # Ensure data.data is a list and contains items
      if isinstance(data.data, list) and len(data.data) > 0:
         enriched_data = [
            {
               **entry.dict(),
               'vendor_id': data.vendor_id,
               'location_id': data.location_id,
               'location_type': data.location_type.value if hasattr(data.location_type, 'value') else str(data.location_type),
            }
            for entry in data.data
            ]
      else:
          logger.error(f"Invalid data structure: data.data is not a list or is empty")
          return {"status": False, "message": "Invalid data", "data": []}
      
      for entry in enriched_data:
          entry['alert_section'] = entry['alert_type']
          entry['alert_timestamp'] = datetime.datetime.strptime(entry['alert_timestamp'], "%m/%d/%Y %I:%M:%S %p")
          ist = pytz.timezone("Asia/Kolkata")
          entry['alert_timestamp'] = entry['alert_timestamp'].astimezone(ist)
          entry['alert_timestamp'] = entry['alert_timestamp'].isoformat()
          await hpcl_ceg_model.VaAlertHistoryCreate(**entry).create()
          # entry['vendor_alert_id'] = entry.pop("alert_id")
          await alert_manager.create_alert({**entry, "alert_type": "VA"})
    
      return True, "Success"
        
    except Exception as e:
        print(traceback.format_exc())
        logger.error(e)
        return {"status": False, "message": "Error", "data": []}

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


# Action ingest_data_score
@router.post('/ingest_data_score', tags=['VA'])
async def va_ingest_data_score(data: Va_Ingest_Data_ScoreParams):
    """
    Args:
        data:
    Returns:
    """
    try:
        logger.info(f"Received VA data ingestion from vendor {data.location_id}({data.location_type}) {data.dict()}")
        return True, "Success"
    except Exception as e:
        print(traceback.format_exc())
        logger.error(e)
        return False, e
