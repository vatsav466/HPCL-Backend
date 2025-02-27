import urdhva_base
import requests
import orchestrator.dbconnector.credential_loader as credential_loader


async def close_emlock_alert(alert_data: dict):
    """
    Args:
        alert_data:{
            "emlockExceptionId":"6146",
            "terminalCode":"location code",
            "truckNumber":"TT Reg No",
            "exceptionType":"exception name",
            "status":"1",
            "acknowledgedUser":"Employee code",
            "acknowledgedTime":"2025-02-01 17:00:00",
            "remarks":"",
            "metaData": "{'loadNumber':'456123','fanNumber':'987456', 'loadNumber':'456123','invoiceNumber':'987456-
123','tripType':'single', 'roCode':'123', 'terminalCode':''}"
        }

    Returns:

    """
    redis_ins = await urdhva_base.redispool.get_redis_connection()
    vendor = "hpcl_emlock"
    db_access_key = ""
    if await redis_ins.hexists("vendor_auth", f"{vendor}_access_key"):
        db_access_key = await redis_ins.hget("vendor_auth", f"{vendor}_access_key")
    headers = {
        "Content-Type": "application/json",
        "ceg-auth-token": db_access_key
    }
    creds = credential_loader.get_credentials("EM_LOCK")
    url = f"http://{creds['host']}:{creds['port']}/api/exceptionCloseAlert"
    response = requests.post(
        url=url, json=alert_data, headers=headers
    )
    if response.status_code // 100 == 2:
        return {"status": True, "message": "Data posted successfully", "data": response.json()}
    return {"status": False, "message": "Data posting unsuccessfully", "data": response.json()}