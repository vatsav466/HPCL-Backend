from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/tasactionlogs')


# Action capture_logs
@router.post('/capture_logs', tags=['TasActionLogs'])
async def tasactionlogs_capture_logs(data: Tasactionlogs_Capture_LogsParams):
    rpt = urdhva_base.context.context.get('rpt', {})
    print("rpt :",rpt)
    return
