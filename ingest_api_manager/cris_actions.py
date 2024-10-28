from data_ingest_enum import *
from data_ingest_model import *
import fastapi

router = fastapi.APIRouter(prefix='/cris')


# Action ingest_data
@router.post('/ingest_data', tags=['CRIS'])
async def cris_ingest_data(data: Cris_Ingest_DataParams):
    ...
