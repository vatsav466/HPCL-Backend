import json
import api_manager
import urdhva_base
import urdhva_base.redispool
import urdhva_base.utilities as utils


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
    query = f"bu = '{bu.upper()}' AND sap_id = '{sap_id}'"
    params = urdhva_base.queryparams.QueryParams()
    params.limit = 100
    params.fields = None
    params.q = query
    params.sort = None
    # Fetching data from database
    locdata = await api_manager.hpcl_ceg_model.LocationMaster.get_all(params, resp_type='plain')
    print(locdata)
    if locdata.get('data', []):
        location_data = locdata.get('data')[0]
        print("location_data: ", location_data)
        if not isinstance(location_data, dict):
            location_data = location_data.__dict__
        await redis_ins.hset("location_master", f"{bu.upper()}_{sap_id}", json.dumps(location_data, default=utils.datetime_serializer))
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


def pad_digits(number, padding_count=8):
    """
    Pads the given number with leading zeros to ensure it has a length of 8 digits.

    Parameters:
    number (int or str): The input number to pad.
    padding_count (int): The desired length of the padded number, defaults to 10.

    Returns:
    str: The number as a string with leading zeros if needed.
    """
    # Convert the number to a string and pad with leading zeros
    return str(number).zfill(padding_count)


async def get_alert_unique_id(bu, sap_id, sop_id, device_id=None):
    """
    Generate a unique ID for an alert based on the business unit and SOP ID.
    Parameters:
    bu (str): Business unit identifier.
    sap_id (str): SAP ID / LocationId.
    sop_id (str): SOP ID.
    device_id (str): SOP ID.

    Returns:
    str: Unique ID.
    """
    redis_ins = await urdhva_base.redispool.get_redis_connection()
    redis_key = [f"{bu.upper()}", f"{sap_id.upper()}", f"{sop_id.upper()}"]
    if device_id:
        redis_key.append(f"_{device_id.upper()}")
    number = await redis_ins.incr("_".join(redis_key))
    redis_key.append(f"{pad_digits(number, 8)}")
    return "_".join(redis_key)
