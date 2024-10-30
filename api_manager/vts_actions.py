from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi

router = fastapi.APIRouter(prefix='/vts')


# Action ingest_data
@router.post('/ingest_data', tags=['VTS'])
async def vts_ingest_data(data: Vts_Ingest_DataParams):
    """
    Endpoint to ingest data for VTS.

    Args:
        data (Vts_Ingest_DataParams): The data parameters required for VTS ingestion,
            including vendor ID, location ID, and optional list of vtsDataCreate objects.

    Returns:
        JSON response with the status of the ingestion process.
    """
    vendorId = data.vendor_id
    locationId = data.location_id
    locationType = data.location_type
    if data.data is not None:
        vtsData = data.data
    else:
        vtsData = None
    return
    
