from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi

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
    logger.info(f"Received EMLock data ingestion for Location {data.location_id}({data.location_type}) {data.dict()}")

