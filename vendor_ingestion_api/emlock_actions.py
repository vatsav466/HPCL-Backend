from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi
import traceback
import orchestrator.alerting.alert_manager as alert_manager

router = fastapi.APIRouter(prefix='/emlock')
logger = urdhva_base.logger.Logger.getInstance("emlock_data_ingestion")


# Action ingest_data
@router.post('/ingest_data', tags=['EMLock'])
async def emlock_ingest_data(data: Emlock_Ingest_DataParams):
    """
    API endpoint to ingest EMLock data.

    Args:
    - data (Ims_Ingest_DataParams): IMS data ingestion parameters

    Processes each IMS data entry by constructing a payload with vendor, location, and IMS details,
    then sends it to the Camunda process engine for processing.

    Returns:
    - dict: Status message indicating the success of the data submission.
    """
    try:
        logger.info(f"Received EMLock data ingestion from vendor {data.vendor_id} {data.dict()}")
        await alert_manager.create_alert({**data.dict(), "alert_type": "EMLock"})
        redis_ins = await urdhva_base.redispool.get_redis_connection()
        vendor = "hpcl_emlock"
        db_access_key = ""
        if await redis_ins.hexists("vendor_auth", f"{vendor}_access_key"):
            db_access_key = await redis_ins.hget("vendor_auth", f"{vendor}_access_key")
        return {"status": True, "message": "Ok"}
    
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"Error ingesting EMLock data: {str(e)}")
        return False, str(e)
