import urdhva_base
import json
import requests
import datetime
import orchestrator.dbconnector.credential_loader as credential_loader


async def get_va_headers(db_name):
    creds = credential_loader.get_va_creds(db_name=db_name)
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
            "ActionDescription": "ActionDescription",
            "DocLink": "",
        }

    Returns:

    """
    creds = await get_va_headers("VA_ALERT")
    creds['url'] = f"https://{creds['host']}/api/v1/Violation/capa"
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

async def get_ro_terminal_scores(params: dict):
    """

    Args:
        params:
        {
            LocationType(string) - RO, TAS, LPG
            StartDate(Mandatory) - 2025-01-27(yyyy-MM-dd)
            EndDate(Nullable) - 2025-01-27(yyyy-MM-dd) (when nullable returns only one day data W.R.T start date)
        }
    Returns:
        [
          {
            "VENDOR_ID": "Ms_ROCKROSE_AUTO_CENTRE",
            "LOCATION_ID": "M/s Rockrose Auto Centre ,16144210",
            "LOCATION_TYPE": "RO",
            "OVERALL_SCORE": "0",
            "DATE": "2025-01-27"
          },
          {
            "VENDOR_ID": "Ms_ROCKROSE_AUTO_CENTRE",
            "LOCATION_ID": "M/s Rockrose Auto Centre ,16144210",
            "LOCATION_TYPE": "RO",
            "OVERALL_SCORE": "0",
            "DATE": "2025-01-28"
          }
        ]
    """
    creds = await get_va_headers("VA_ALERT_SCORE")
    creds['url'] = f"https://{creds['host']}/api/Platform/v1/HPCLVendor/Scores"
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
    response = requests.get(
        url=creds['url'], params=params, headers=headers
    )
    if response.status_code // 100 == 2:
        data = response.json()
        if 'RespBody' in data.keys() and 'Payload' in data['RespBody'].keys():
            data = json.loads(data['RespBody']['Payload'])
        else:
            data = []
        return {"status": True, "message": "Data fetched successfully", "data": data}
    return {"status": False, "message": "Data fetching unsuccessfully", "data": response.json()}