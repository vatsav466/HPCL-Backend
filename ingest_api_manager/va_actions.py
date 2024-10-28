from data_ingest_enum import *
from data_ingest_model import *
import fastapi

router = fastapi.APIRouter(prefix='/va')


# Action ingest_data
@router.post('/ingest_data', tags=['VA'])
async def va_ingest_data(data: Va_Ingest_DataParams, vendor: str = fastapi.Header(description="Specifies the vendor name, e.g., 'hpcl_va'"),
    ceg_auth_token: str = fastapi.Header(description="Authentication token for the API call")):
    """
    Endpoint to ingest VA data.

    Args:
        data (Va_Ingest_DataParams): The VA data parameters including vendor, 
        authentication token, vendor ID, location ID, location type, and 
        optional data list.

    Returns:
        Response object indicating success or failure of the data ingestion process.
    """
    ...
