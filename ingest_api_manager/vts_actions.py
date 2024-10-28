from data_ingest_enum import *
from data_ingest_model import *
import fastapi

router = fastapi.APIRouter(prefix='/vts')


# Action ingest_data
@router.post('/ingest_data', tags=['VTS'])
async def vts_ingest_data(data: Vts_Ingest_DataParams, vendor: str = fastapi.Header(description="Specifies the vendor name, e.g., 'hpcl_va'"),
    ceg_auth_token: str = fastapi.Header(description="Authentication token for the API call")):
    """
    Endpoint to ingest VTS data.

    Args:
        data (Vts_Ingest_DataParams): The VTS data parameters including vendor, 
        authentication token, vendor ID, location ID, location type, and optional data.

    Returns:
        Response object indicating success or failure of the data ingestion process.
    """
    ...
