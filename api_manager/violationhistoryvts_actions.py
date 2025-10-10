from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/violationhistoryvts')


# Action vts_alert_action
@router.post('/vts_alert_action', tags=['ViolationHistoryVts'])
async def violationhistoryvts_vts_alert_action(data: Violationhistoryvts_Vts_Alert_ActionParams):
    ...


# Action get_closed_alerts_details_vts
@router.post('/get_closed_alerts_details_vts', tags=['ViolationHistoryVts'])
async def violationhistoryvts_get_closed_alerts_details_vts(data: Violationhistoryvts_Get_Closed_Alerts_Details_VtsParams):
    ...


# Action alert_action_vts
@router.post('/alert_action_vts', tags=['ViolationHistoryVts'])
async def violationhistoryvts_alert_action_vts(data: Violationhistoryvts_Alert_Action_VtsParams):
    ...
