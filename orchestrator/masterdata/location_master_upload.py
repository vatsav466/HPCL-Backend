import urdhva_base
import traceback
import api_manager
import hpcl_ceg_model
import urdhva_base.redispool
import utilities.bu_key_mapping as bu_key_mapping
import orchestrator.alerting.alert_helper as alert_helper


async def upload_location_master_data(df):
    """
    Upload Location Master data.
    :param df: polars dataframe
    :return: status, message
    """
    redis_client = await urdhva_base.redispool.get_redis_connection()
    # Iterate through the rows of the CSV and extract `bu` and `sapid`
    df = df.rename(bu_key_mapping.Location)
    try:
        data = df.to_dicts()
        for data_dump in data:
            data_obj = hpcl_ceg_model.LocationMasterCreate(**data_dump)
            await data_obj.create()
            await alert_helper.set_location_details(data_dump["bu"], data_dump["sap_id"], data_dump, redis_client)
        return True, "Location Master Uploaded Successfully"
    except Exception as e:
        print(traceback.format_exc())
        return False, str(e)
