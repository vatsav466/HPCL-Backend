from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/lpgplantoperations')


# Action check_connection_status
@router.post('/check_connection_status', tags=['LpgPlantOperations'])
async def lpgplantoperations_check_connection_status(data: Lpgplantoperations_Check_Connection_StatusParams):
    ...
