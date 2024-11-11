import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import re
import pytz
import json
import datetime
import requests
import urdhva_base

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
        
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        alert_data = Alerts.get(data.alert_id)
        
        if alert_data:
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__
            alerthistory = alert_data.get('alertHistory', [])
        else:
            return {"status": False, "message": "Alert not available", "data": []}
        
        if not alert_data.get("role", ""):
            return {"status": False, "message": "User has no permission for this action", "data": []}

        condition = re.compile('<.*?>')
        alertmsg = re.sub(condition, '', data.action_msg or "")

        session_details = urdhva_base.context.context.get("rpt", {})
        user = session_details.get('email', '')

        IST = pytz.timezone('Asia/Kolkata')
        currtime = datetime.datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')
        action_text = f"{data.action_type.capitalize()} by: {user}, Message: {alertmsg} at {currtime}"
        
        tags_data = data.event_tags.__dict__ if data.event_tags else {}
        isMaintenanceException = tags_data.get('is_maintenance_exception', False)
        isRevocation = tags_data.get('is_revocation', False)
        
        if data.action_type == AlertActionType.Justification:
            alerthistory.append(action_text)
            if data.justification_type:
                alerthistory.append(f"Justified with: {data.justification_type}")
            isjustify = not isMaintenanceException
        elif data.action_type == AlertActionType.Rejected:
            alerthistory.append(action_text)
            isjustify = False
        
        updatedoc = {
            'alertHistory': alerthistory,
            "isMaintenanceException": isMaintenanceException,
            "dealer_justify_type": data.justification_type if data.action_type == AlertActionType.Justification else "",
            "isRevocation": isRevocation,
        }

        if data.days:
            updatedoc['days'] = data.days

        _alerts = Alerts(**updatedoc)
        _alerts.modify()

        businesskey = data.alert_id
        body = {
            'messageName': 'justification' if data.action_type == AlertActionType.Justification else 'message',
            'businessKey': businesskey,
            'processVariables': {
                'msg': {'type': 'String', 'value': alertmsg},
                'user': {'type': 'String', 'value': user},
                'action_type': {'type': 'String', 'value': data.action_type.value},
                'isMaintenanceException': {'type': 'Boolean', 'value': isMaintenanceException},
                'isRevocation': {'type': 'Boolean', 'value': isRevocation},
                'justify': {'type': 'Boolean', 'value': isjustify},
                'overridedays': {'type': 'String', 'value': str(data.days)}
            }
        }

        camundaurl = urdhva_base.settings.camundaurl + "/engine-rest/message"
        response = requests.post(camundaurl, headers=headers, data=json.dumps(body))
        logger.info(f"{data.action_type.capitalize()} for:{businesskey} Data:{body} Camunda Resp:{response.status_code}")

        return {"status": True, "message": f"{data.action_type.capitalize()} Submitted Successfully", "data": []}
    
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": str(e), "data": []}
        
