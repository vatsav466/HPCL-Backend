from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/vts')


# Action alert_manager
@router.post('/alert_manager', tags=['VTS'])
async def vts_alert_manager(data: Vts_Alert_ManagerParams):
    ...
