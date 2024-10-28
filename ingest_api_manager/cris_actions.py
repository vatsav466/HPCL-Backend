from data_ingest_enum import *
from data_ingest_model import *
import fastapi

router = fastapi.APIRouter(prefix='/cris')


# Action ingest_data
@router.post('/ingest_data', tags=['CRIS'])
async def cris_ingest_data(data: Cris_Ingest_DataParams, vendor: str = fastapi.Header(description="Specifies the vendor name, e.g., 'hpcl_va'"),
    ceg_auth_token: str = fastapi.Header(description="Authentication token for the API call")):
    """
    Endpoint to ingest CRIS data.

    Args:
        data (Cris_Ingest_DataParams): The CRIS data parameters including vendor, 
        authentication token, vendor ID, location ID, and optional data list.

    Returns:
        Response object indicating success or failure of the data ingestion process.
    """
    ...
