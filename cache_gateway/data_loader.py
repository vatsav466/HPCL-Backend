import urdhva_base
import json
import asyncio
import traceback
import urdhva_base.redispool
import cache_gateway.data_cache_handler as cache_handler


class CacheDataInstance:
    _instances = {}

    @classmethod
    def get_instance(cls, cache_key, loader_func):
        """
        get instance for the given cache_key
        """
        if cache_key not in CacheDataInstance._instances:
            print(f"Cache Key Not Available {cache_key}")
            CacheDataInstance._instances[cache_key] = CacheDataInstance(loader_func).cache_handler

        return CacheDataInstance._instances[cache_key]

    def __init__(self, loader_func):
        """
        Initializing cache class
        """
        self.cache_handler = cache_handler.InMemTTLCache(ttl_seconds=urdhva_base.settings.default_masters_cache_seconds,
                                                         fetch_function=loader_func)


async def load_location_master():
    """
    Loading location master from redis database
    :return:
    """
    print(f"Loading data")
    count = 0
    while count < 3:
        try:
            redis_ins = urdhva_base.redispool.get_synchronous_redis_connection()
            try:
                location_data = redis_ins.hgetall("location_master")
                location_data = {key.decode(): json.loads(value) for key, value in location_data.items()}
                return location_data
            except Exception as e:
                print(f"Redis Exception: {e}, Traceback {traceback.format_exc()}")
                # return {}
            finally:
                try:
                    redis_ins.close()
                except Exception as e:
                    print(f"Exception in closing redis connection {e}")
        except Exception as e:
            print(f"Error in getting redis connection, retrying")
        # Sleeping a second before retry
        await asyncio.sleep(1)
        count += 1
    return {}


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
        return False, {"msg": "Invalid parameters: 'bu' and 'sap_id' are required."}
    ins = CacheDataInstance.get_instance("location_master", load_location_master)
    location_data = await ins.get(f"location_master")
    if not location_data or f"{bu.upper()}_{sap_id}" not in location_data:
        return False, {}
    return True, location_data[f"{bu.upper()}_{sap_id}"]

