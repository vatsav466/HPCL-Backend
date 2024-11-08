import urdhva_base.redispool
import json


async def update_vendor_authentication_headers():
    redis_client = await urdhva_base.redispool.get_redis_connection()
    # For VA
    vendor = 'va'
    await redis_client.hset("vendor_auth", f"hpcl_{vendor}_access_key",
                            "Mauad4ysWfCzb1eAOSLKYM9yp8DyxLtio0H7QbXl7kkkzaTePw7dYJui3KWCccSp")
    await redis_client.hset("vendor_auth", f"hpcl_{vendor}_allowed_apis", json.dumps([f"/api/{vendor}/ingest_data"]))

    # For VTS
    vendor = 'vts'
    await redis_client.hset("vendor_auth", f"hpcl_{vendor}_access_key",
                            "ZALpdEQTyfc6hZ1Oc98msUc3srqQGIfLYDEu7wxqhWy3FbPECaHejcEMUiSsZiB0")
    await redis_client.hset("vendor_auth", f"hpcl_{vendor}_allowed_apis", json.dumps([f"/api/{vendor}/ingest_data"]))

    # For IMS
    # vendor = 'ims'
    # await redis_client.hset("vendor_auth", f"hpcl_{vendor}_access_key",
    #                         ".....")
    # await redis_client.hset("vendor_auth", f"hpcl_{vendor}_allowed_apis", json.dumps([f"/api/{vendor}/ingest_data"]))

    # For CMES
    # vendor = 'cmes'
    # await redis_client.hset("vendor_auth", f"hpcl_{vendor}_access_key",
    #                         "....")
    # await redis_client.hset("vendor_auth", f"hpcl_{vendor}_allowed_apis", json.dumps([f"/api/{vendor}/ingest_data"]))

    # For CRIS
    vendor = 'cris'
    await redis_client.hset("vendor_auth", f"hpcl_{vendor}_access_key",
                            "FOA5iiG81MK0kWSOJh5jtlAbYvkJ4viIZh2yRqzam9DWlGzzFPpYkhvtMSmcsjwq")
    await redis_client.hset("vendor_auth", f"hpcl_{vendor}_allowed_apis", json.dumps([f"/api/{vendor}/ingest_data"]))

    # For EMLock
    vendor = 'emlock'
    await redis_client.hset("vendor_auth", f"hpcl_{vendor}_access_key",
                            "ghArMdF7wcjSLUpo9fvDoRXfoExJlSqBaT9rd1gxotblW7VmFtROy9qFQMjqJkEo")
    await redis_client.hset("vendor_auth", f"hpcl_{vendor}_allowed_apis", json.dumps([f"/api/{vendor}/ingest_data"]))
