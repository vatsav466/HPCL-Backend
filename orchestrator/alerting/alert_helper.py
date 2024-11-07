import urdhva_base
import json
import api_manager
import urdhva_base.redispool


async def get_location_details(bu, sap_id):
    """
    Retrieves location details based on the provided business unit and SAP ID.

    Parameters:
    bu (str): The business unit identifier.
    sap_id (str): The SAP ID of the location.

    Returns:
    dict: Location details, including name, address, coordinates, etc., or None if not found.
    """
    if not bu or not sap_id:
        print("Invalid parameters: 'bu' and 'sap_id' are required.")
        return False, "Invalid parameters: 'bu' and 'sap_id' are required."
    redis_ins = await urdhva_base.redispool.get_redis_connection()
    if await redis_ins.hexists("location_master", f"{bu.upper()}_{sap_id}"):
        location_data = json.loads(await redis_ins.hget("location_master", f"{bu.upper()}_{sap_id}"))
        return True, location_data

    # Verifying the same available in database or not
    query = f"'bu='%{bu.upper()}%' AND sap_id='%{sap_id}%'"
    params = urdhva_base.queryparams.QueryParams()
    params.limit = 100
    params.fields = None
    params.q = query
    params.sort = json.dumps({"updated": -1})
    # Fetching data from database
    locdata = await api_manager.hpcl_cng_model.LocationMaster.get_all(params)
    if locdata:
        location_data = locdata[0]
        await redis_ins.hset("location_master", f"{bu.upper()}_{sap_id}", json.dumps(location_data))
        return True, location_data
    return False, "Data not available"


async def set_location_details(bu, sap_id, location_data, redis_client=None):
    """
    Stores or updates location details based on the provided business unit, SAP ID, and location data.

    Parameters:
    bu (str): The business unit identifier.
    sap_id (str): The SAP ID of the location.
    location_data (dict): Dictionary containing location details to be stored or updated,
                          such as name, address, coordinates, etc.
    redis_client (Redis Instance): None or async redis connection

    Returns:
    bool: True if the location details were successfully stored/updated, False otherwise.
    """
    if not bu or not sap_id:
        print("Invalid parameters: 'bu' and 'sap_id' are required.")
        return False
    if not isinstance(location_data, dict):
        print("Invalid parameter: 'location_data' must be a dictionary.")
        return False
    if not redis_client:
        redis_client = await urdhva_base.redispool.get_redis_connection()
    await redis_client.hset("location_master", f"{bu.upper()}_{sap_id}", json.dumps(location_data))
    return True
