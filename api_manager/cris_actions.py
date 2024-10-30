from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi

router = fastapi.APIRouter(prefix='/cris')


# Action ingest_data
@router.post('/ingest_data', tags=['CRIS'])
async def cris_ingest_data(data: Cris_Ingest_DataParams):
    ...
