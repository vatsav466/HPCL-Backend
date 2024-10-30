from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi

router = fastapi.APIRouter(prefix='/vts')


# Action ingest_data
@router.post('/ingest_data', tags=['VTS'])
async def vts_ingest_data(data: Vts_Ingest_DataParams):
    ...
