import urdhva_base
import asyncio
import hpcl_ceg_model
import urdhva_base.redispool
import orchestrator.alerting.alert_helper as alert_helper


async def sync_location_data_to_redis():
    redis_client = await urdhva_base.redispool.get_redis_connection()
    query = "SELECT * from location_master"
    resp = await hpcl_ceg_model.LocationMaster.get_aggr_data(query, limit=100000)
    for rec in resp['data']:
        for key in ["created_at", "updated_at"]:
            if key in rec:
                del rec[key]
        await alert_helper.set_location_details(rec["bu"], rec["sap_id"], rec, redis_client)


if __name__ == "__main__":
    asyncio.run(sync_location_data_to_redis())