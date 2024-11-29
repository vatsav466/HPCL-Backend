import urdhva_base
from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi
import json
import requests
import traceback
import orchestrator.alerting.alert_manager as alert_manager

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
    try:
      logger.info(f"Received VTS data ingestion from vendor {data.location_id}({data.location_type}) {data.dict()}")
      await alert_manager.create_alert({**data.dict(), "alert_type": "VTS"})
      return True, "Success"
      
    except Exception as e:
        print(traceback.format_exc())
        logger.error(e)
        return {"status": False, "message": "Error", "data": []}
