import urdhva_base
from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi
import datetime
import pytz
import traceback
import polars as pl
import hpcl_ceg_model
import utilities.helpers as helpers
import orchestrator.analytics.va_analysis as va_analysis
import orchestrator.analytics.ro_analysis as ro_analysis
import utilities.connection_mapping as connection_mapping
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

      enriched_data = pl.DataFrame(enriched_data)
      enriched_data = await va_analysis.assign_values_to_dataframe(
          enriched_data, list(connection_mapping.camunda_listener_va_mapping.values())
      )
      enriched_data = enriched_data.to_dicts()
      for entry in enriched_data:
          entry['alert_section'] = entry['alert_type']
          entry['alert_timestamp'] = datetime.datetime.strptime(entry['alert_timestamp'], "%m/%d/%Y %I:%M:%S %p")
          utc = pytz.timezone("UTC")
          ist = pytz.timezone("Asia/Kolkata")
          # First localize to UTC
          entry['alert_timestamp'] = utc.localize(entry['alert_timestamp'])
          # Convert to IST
          entry['alert_timestamp'] = entry['alert_timestamp'].astimezone(ist)
          # ist = pytz.timezone("Asia/Kolkata")
          # entry['alert_timestamp'] = entry['alert_timestamp'].astimezone(ist)
          entry['alert_timestamp'] = entry['alert_timestamp'].isoformat()
          await hpcl_ceg_model.VaAlertHistoryCreate(**entry).create()
          # entry['vendor_alert_id'] = entry.pop("alert_id")
          camunda_url = urdhva_base.settings.camunda_url
          if 'camunda_host' in entry.keys():
            camunda_url = f"http://{entry['camunda_host']}:{entry['camunda_port']}"
          await alert_manager.create_alert({**entry, "alert_type": "VA"}, camunda_url=camunda_url)
    
      return True, "Success"
        
    except Exception as e:
        print(traceback.format_exc())
        logger.error(e)
        return {"status": False, "message": "Error", "data": []}


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


# Action ingest_data_close
@router.post('/ingest_data_close', tags=['VA'])
async def va_ingest_data_close(data: Va_Ingest_Data_CloseParams):
    try:
        va_query = f"select * from va_alert_history where alert_id = '{data.alert_id}'"
        va_alert = await hpcl_ceg_model.VaAlertHistory.get_aggr_data(va_query, limit=0)
        if va_alert.get("data", []):
            va_alert = va_alert.get("data", [])[0]
            va_alert['status'] = data.status
            va_alert['acknowledged_by'] = data.acknowledged_by
            va_alert['closed_at'] = data.closed_at
            va_alert['action_description'] = data.action_description
            va_alert['action_code'] = data.action_code
            va_alert['action_reason'] = data.action_reason
            va_alert['action_category'] = data.action_category
            await hpcl_ceg_model.VaAlertHistory(**va_alert).modify()

        alert_query = f"select * from alerts where alert_section = 'VA' and external_id = '{data.alert_id}'"
        alert_data = await hpcl_ceg_model.Alerts.get_aggr_data(alert_query, limit=0)
        if not alert_data.get("data", []):
            return {"status": False, "message": "Alert not found", "data": []}

        alert_data = alert_data.get("data", [])[0]
        alert_data['alert_status'] = 'Close'
        alert_data['alert_state'] = 'Resolved'
        alert_data['alert_history'].append({
            "action_type": "Resolved", "alert_status": "Close", "action_msg": data.action_code,
            "remarks": data.action_description, "action_by": data.acknowledged_by,
            "processed_time": datetime.datetime.strptime(data.closed_at, "%Y-%m-%dT%H:%M:%S").isoformat()
        })
        await hpcl_ceg_model.Alerts(**alert_data).modify()
        camunda_url = await helpers.get_camunda_url(bu=alert_data['bu'], sap_id=alert_data['bu'],
                                                    alert_section="VA")
        await ro_analysis.close_camunda_workflow(alert_data, camunda_url=camunda_url)
        return {"status": True, "message": "Success", "data": []}

    except Exception as e:
        print(traceback.format_exc())
        logger.error(e)
        return {"status": False, "message": "Error", "data": []}