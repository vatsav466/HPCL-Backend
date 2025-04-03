import urdhva_base
from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi
import json
import requests
import traceback
import hpcl_ceg_model
import orchestrator.analytics.vts_analysis as vts_analysis
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
      logger.info(f"Received VTS data ingestion from vendor {data.dict()}")
      # await alert_manager.create_alert({**data.dict(), "alert_type": "VTS"})
      # return True, "Success"

      # Ensure data.data is a list and contains items
      if isinstance(data.data, list) and len(data.data) > 0:
          enriched_data = [
              {
                  **entry.dict()
              }
              for entry in data.data
          ]
      else:
          logger.error(f"Invalid data structure: data.data is not a list or is empty")
          return {"status": False, "message": "Invalid data", "data": []}

      for entry in enriched_data:
          entry['auto_unblock'] = True
          entry['violation_type'] = await vts_analysis.get_vts_violation(entry)
          entry['vts_start_datetime'], entry['vts_end_datetime'] = map(
              lambda x: datetime.datetime.strptime(x, "%Y-%m-%d %H:%M:%S"), entry['report_duration'].split(" to "))
          await hpcl_ceg_model.VtsAlertHistoryCreate(**entry).create()
          if not await vts_analysis.is_alert_exists(entry['tl_number']):
            await alert_manager.create_alert({**entry, "alert_type": "VTS"})
      
      return True, "Success"

    except Exception as e:
        print(traceback.format_exc())
        logger.error(e)
        return {"status": False, "message": "Error", "data": []}


# Action ingest_data_blocked_trucks
@router.post('/ingest_data_blocked_trucks', tags=['VTS'])
async def vts_ingest_data_blocked_trucks(data: Vts_Ingest_Data_Blocked_TrucksParams):
    """
        Args:
            data:
        Returns:
        """
    try:
        logger.info(f"Received VTS data ingestion from TT Blocked {data.location_id}({data.location_type}) {data.dict()}")
        return True, "Success"
    except Exception as e:
        print(traceback.format_exc())
        logger.error(e)
        return False, e


# Action ingest_data_un_blocked_trucks
@router.post('/ingest_data_un_blocked_trucks', tags=['VTS'])
async def vts_ingest_data_un_blocked_trucks(data: Vts_Ingest_Data_Un_Blocked_TrucksParams):
    """
            Args:
                data:
            Returns:
            """
    try:
        logger.info(
            f"Received VTS data ingestion from TT UnBlocking {data.location_id}({data.location_type}) {data.dict()}")
        return True, "Success"
    except Exception as e:
        print(traceback.format_exc())
        logger.error(e)
        return False, e
