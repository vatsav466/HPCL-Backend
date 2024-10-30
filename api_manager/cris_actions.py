from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi

router = fastapi.APIRouter(prefix='/cris')


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
    ...
