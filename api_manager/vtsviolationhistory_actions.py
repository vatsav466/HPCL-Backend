import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import traceback
import orchestrator.alerting.alert_manager as alert_manager

router = fastapi.APIRouter(prefix='/vtsviolationhistory')

logger = urdhva_base.logger.Logger.getInstance("api_manager")

# Action vts_alert_action
@router.post('/vts_alert_action', tags=['VtsViolationHistory'])
async def vtsviolationhistory_vts_alert_action(data: Vtsviolationhistory_Vts_Alert_ActionParams):
    """
    API endpoint to perform an action on an alert.

    Args:
    - data (Alerts_Alert_ActionParams): Alert action parameters

    Returns:
    - dict: Response with status, message and empty data
    """
    try:
        logger.info(f"Alert data received to perform action: {data}")
        return await alert_manager.AlertAction().update_alert_data_vts(data.dict())
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"Error in performing action on alert: {e}, InputData {data.dict()}, Traceback: {traceback.format_exc()}")
        return False, "Error in performing action on alert"
