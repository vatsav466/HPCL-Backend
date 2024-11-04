from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi
import re
import pytz
import json
import datetime
import requests
import urdhva_base

router = fastapi.APIRouter(prefix='/alerts')

logger = urdhva_base.logger.Logger.getInstance("api_manager")

# Action justification
@router.post('/justification', tags=['Alerts'])
async def alerts_justification(data: Alerts_JustificationParams):
    """
    API endpoint to send justification for an alert.

    Args:
    - data (Alerts_JustificationParams): Alert justification parameters

    Returns:
    - None
    """
    header = {"Content-Type": "application/json", "Accept": "application/json"}
    tags_data = data.event_tags.__dict__
    isMaintenanceException = tags_data['is_maintenance_exception']
    isRevocation = tags_data['is_revocation']
    alert_data = Alerts.get(data.alert_id)
    if alert_data:
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__
        alerthistory = alert_data.get('alertHistory', [])
    else:
        return {
            "status": False, "message": "Alert not available", "data": []
        }
    
    if not alert_data.get("role", ""):
        return {
            "status": False, "message":"User has no permission for this action", "data": []
        }
    
    condition = re.compile('<.*?>')
    alertmsg = re.sub(condition, '', data.alert_msg)

    session_details = urdhva_base.context.context.get("rpt", {})

    user = session_details.get('email', '')
    IST = pytz.timezone('Asia/Kolkata')
    currtime = datetime.datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')
    updatedoc = {'alertHistory': alerthistory, "isMaintenanceException": isMaintenanceException,
                    "dealer_justify_type": data.justification_type, "isRevocation": isRevocation}
    # alerthistory.append('Justified by: %s, Message: %s at %s' % (user, alertmsg, str(currtime)))
    ah = 'Justified by: %s, Message: %s at %s' % (user, alertmsg, str(currtime))
    if data.justification_type:
        alerthistory.append('Justified with:%s' % data.justification_type)
    isjustify = True if not isMaintenanceException else False
    businesskey = alert_id
    bu = alert_data['type']
    body = {'messageName': 'justification',
            'businessKey': businesskey,
            'processVariables': {'msg': {'type': 'String', 'value': alertmsg},
                                    'user': {'type': 'String', 'value': user},
                                    'action_type': {'type': 'String', 'value': 'Justification'},
                                    'isMaintenanceException': {'type': 'Boolean', 'value': isMaintenanceException},
                                    'isRevocation': {'type': 'Boolean', 'value': isRevocation},
                                    'justify': {'type': 'Boolean', 'value': isjustify}}}
    if data.days:
        updatedoc['days'] = data.days
        body['processVariables']['overridedays'] = {'type': 'String', 'value': data.days}
    
    alerthistory.append(ah)

    _alerts = Alerts(**updatedoc)
    _alerts.modify()
    
    camundaurl = urdhva_base.settings.camundaurl + "/engine-rest/message"
    r = requests.post(camundaurl, headers=headers, data=json.dumps(body))
    logger.info("Justify for:%s Data:%s Camunda Resp:%s" % (businesskey, body, r.status_code))

    return {
        "status": True, "message": "Justification Submitted", "data": []
    }


# Action reject
@router.post('/reject', tags=['Alerts'])
async def alerts_reject(data: Alerts_RejectParams):
    """
    API endpoint to reject an alert.

    Args:
    - data (Alerts_RejectParams): Alert reject parameters

    Returns:
    - None
    """
    header = {"Content-Type": "application/json", "Accept": "application/json"}
    try:
        data.days = int(data.days)
    except Exception as e:
        data.days = 0

    alert_data = Alerts.get(data.alert_id)
    if alert_data:
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__
        alerthistory = alert_data.get('alertHistory', [])
    else:
        return {
            "status": False, "message": "Alert not available", "data": []
        }

    if not alert_data.get("role", ""):
        return {
            "status": False, "message": "User has no permission for this action", "data": []
        }
    
    condition = re.compile('<.*?>')
    alertmsg = re.sub(condition, '', data.alert_msg)

    session_details = urdhva_base.context.context.get("rpt", {})

    user = session_details.get('email', '')
    sopid = alert_data['sopId']
    role = alert_data['role']

    IST = pytz.timezone('Asia/Kolkata')
    currtime = datetime.datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')
    alerthistory.append('Rejected by: %s, Message: %s at: %s' % (user, alertmsg, currtime))
    
    _alerts = Alerts(**{'_id': data.alert_id, 'alertHistory': alerthistory})
    _alerts.modify()
    

    businesskey = data.alert_id
    bu = alert_data['type']
    body = {'messageName': 'message',
            'businessKey': businesskey,
            'processVariables': {'overridedays': {'type': 'String', 'value': data.days},
                                    'approved': {'type': 'Boolean', 'value': False},
                                    'user': {'type': 'String', 'value': user},
                                    'msg': {'type': 'String', 'value': alertmsg},
                                    'action_type': {'type': 'String', 'value': 'Reject'},
                                    'justify': {'type': 'Boolean', 'value': False}}}
    
    camundaurl = urdhva_base.settings.camundaurl + '/engine-rest/message'
    
    r = requests.post(camundaurl, headers=headers, data=json.dumps(body))
    logger.info("Reject for:%s Data:%s Camunda Resp:%s" % (businesskey, body, r.status_code))
    return {
        "status": True, "message": "Submitted Successfully", "data": []
    }


# Action approve
@router.post('/approve', tags=['Alerts'])
async def alerts_approve(data: Alerts_ApproveParams):
    """
    API endpoint to approve an alert.

    Args:
    - data (Alerts_ApproveParams): Alert approve parameters

    Returns:
    - None
    """
    ...


# Action override
@router.post('/override', tags=['Alerts'])
async def alerts_override(data: Alerts_OverrideParams):
    """
    API endpoint to override an alert.

    Args:
    - data (Alerts_OverrideParams): Alert override parameters

    Returns:
    - None
    """
    ...
