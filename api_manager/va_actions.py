from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi

router = fastapi.APIRouter(prefix='/va')


# Action ingest_data
@router.post('/ingest_data', tags=['VA'])
async def va_ingest_data(data: Va_Ingest_DataParams):
    """
    Endpoint to ingest data for VA.

    Args:
        data (Va_Ingest_DataParams): The data parameters required for VA ingestion,
        including vendor ID, location ID, location type, and optional list of vaData.

    Returns:
        JSON response with the status of the ingestion process.
    """
    ...
