import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import re
import pytz
import json
import datetime
import requests
import traceback
import orchestrator.alerting.alert_manager as alert_manager

router = fastapi.APIRouter(prefix='/alerts')

logger = urdhva_base.logger.Logger.getInstance("api_manager")


# Action alert_action
@router.post('/alert_action', tags=['Alerts'])
async def alerts_alert_action(data: Alerts_Alert_ActionParams):
    """
    API endpoint to perform an action on an alert.

    Args:
    - data (Alerts_Alert_ActionParams): Alert action parameters

    Returns:
    - dict: Response with status, message and empty data
    """
    try:
        logger.info(f"Alert data received to perform action: {data}")
        return await alert_manager.AlertAction().update_alert_data(data.dict())
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"Error in performing action on alert: {e}, InputData {data.dict()}, Traceback: {traceback.format_exc()}")
        return False, "Error in performing action on alert"
        

# Action get_performance_index
@router.post('/get_performance_index', tags=['Alerts'])
async def alerts_get_performance_index(data: Alerts_Get_Performance_IndexParams):
    query = f"SELECT sap_id, name from location_data where bu='{data.bu}'"
    resp = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=50000, skip=0)
    for rec in resp['data']:
        rec.update({"in_charge": "Location Incharge", "score": 99, "rank": 1})
    return resp['data']
