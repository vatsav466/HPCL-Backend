import urdhva_base
import requests
import datetime
import orchestrator.dbconnector.credential_loader as credential_loader


async def get_va_headers(db_name):
    creds = credential_loader.get_va_creds(db_name=db_name)
    creds['url'] = f"https://{creds['host']}/api/v1/Violation/capa"
    creds['Origin'] = f"https://{creds['host']}"
    creds['Referer'] = f"https://{creds['host']}/home/dashboard/{creds['cust_id']}"
    return creds


async def close_va_alerts(params: dict):
    """

    Args:
        params: Dict
        {
            "AlarmId": "AlarmId",
            "Status": "CLOSED",
            "AcknowledgedBy": "UserId",
            "ActionCode": "INVALID", Options: ["Invalid", "Valid", "False"]
            "ActionReason":"Lack of awareness", Options: ["Person issue", "Equipment issue", "Lack of awareness", "Not following SOP", "Other"]
            "ActionCategory":"Safety", Options: ["Safety", "Security", "Operation", "Others"]
            "ActionDescription": "ActionDescription"
        }

    Returns:

    """
    creds = await get_va_headers("VA_ALERT")
    ack_datetime = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    headers = {
        "Content-Type": "application/json",
        "CustId": creds['cust_id'],
        "MessageId": f"ACKNOWLEDGE_ALARM{ack_datetime}",
        "Origin": creds['Origin'],
        "Referer": creds['Referer'],
        "UserId": creds['user'],
        "ApplicationId": creds['application_id'],
        "Cookie": creds['cookie'],
        "SessionToken": creds['session_token']
    }
    response = requests.post(
        url=creds['url'], json=params, headers=headers
    )
    if response.status_code // 100 == 2:
        return {"status": True, "message": "Data posted successfully", "data": response.json()}
    return {"status": False, "message": "Data posting unsuccessfully", "data": response.json()}
