import urdhva_base
import asyncio
import traceback
import datetime
import polars as pl
import charts_actions
import urdhva_base.redispool
import dashboard_studio_model
import dateutil.parser as parser
import utilities.connection_mapping as connection_mapping
import utilities.helpers as helpers


async def indent_dryout_sync_ro_daily_sales(since, until):
    try:
        total_days = (parser.parse(until) - parser.parse(since)).days
        if total_days == 0:
            total_days = 1
        for day in range(0, total_days):
            start_date = helpers.get_time_stamp_by_delta(parser.parse(since), days=day, 
                                                         ascending=True, 
                                                         with_month_start_day=False)
            end_date = helpers.get_time_stamp_by_delta(parser.parse(start_date), days=1, 
                                                       ascending=True, 
                                                       with_month_start_day=False)
            where_clause = f""""transaction_date" BETWEEN '{start_date}' AND '{end_date}'"""
            if (parser.parse(until) - parser.parse(since)).days == 0:
                where_clause = f'''"transaction_date"='{start_date}' '''
            print(f"Query executing from {start_date} to {end_date}")
            # tr_transaction_dailysales
            query = f'''
                SELECT 
                    "site_id",
                    (select erp_code from ms_site ms where ms.site_id = trd.site_id) as "sap_id",
                    "fcc_code",
                    "transaction_date", 
                    "tank_no", 
                    "pump_no",
                    "nozzle_no", 
                    "product_no", 
                    "transaction_type",
                    "total_sales", 
                    "start_totalizer", 
                    "end_totalizer", 
                    "txn_amount", 
                    "last_transaction_date",
                    "first_transaction_date"
                FROM
                    "{connection_mapping.schema_mapping.get("cris", "HPCL_HOS")}"."tr_transaction_dailysales" trd
                WHERE 
                    {where_clause}
            '''
            print(query)

            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("cris", "2")  #2   # tr_transaction_dailysales
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
            function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
            data = await function(query=query)
            column_mapping = {
                "site_id": pl.Utf8,
                "sap_id": pl.Utf8,
                "fcc_code": pl.Utf8,               
                "transaction_date": pl.Date,   
                "tank_no": pl.Int32,               
                "pump_no": pl.Int32,               
                "nozzle_no": pl.Int32,             
                "product_no": pl.Int32,            
                "transaction_type": pl.Utf8,       
                "total_sales": pl.Float64,         
                "start_totalizer": pl.Float64,
                "end_totalizer": pl.Float64,
                "txn_amount": pl.Float64,
                "last_transaction_date": pl.Datetime, 
                "first_transaction_date": pl.Datetime 
            }
            tr_daily_sales = pl.DataFrame(data, schema=column_mapping)

            # ro master
            ro_query = f''' 
                SELECT 
                    "sap_id" as "ro_id", 
                    "sap_id"
                FROM 
                    "public"."location_master"; '''
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1") # 1  ro_master
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
            function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
            ro_data = await function(query=ro_query)
            ro_master = pl.DataFrame(ro_data)
            ro_master = ro_master.rename(mapping={"sap_id": "ro_sap_code"})
            ro_master = ro_master.with_columns(pl.col("ro_id").str.replace(",", "").alias("ro_id"))
            ro_master = ro_master.with_columns(pl.col("ro_id").str.replace(",", "").alias("ro_id"))
            tr_daily_sales = tr_daily_sales.join(ro_master.unique(subset='ro_id', keep='first'), left_on='site_id', right_on='ro_id', how='left')
            tr_daily_sales = tr_daily_sales.filter(pl.col("ro_sap_code").is_not_null())
            tr_daily_sales = tr_daily_sales.drop('sap_id')
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'upsert_data'
            function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
            conflict_columnsList = ['site_id', 'ro_sap_code', 'transaction_date', 'tank_no', 'pump_no', 
                                'nozzle_no', 'product_no', 'transaction_type']
            resp = await function(
                schema_name='HPCL_HOS',
                table_name='ro_daily_sales',
                records=tr_daily_sales.to_dicts(),
                conflict_columns=conflict_columnsList
            )
        return until #tr_daily_sales.sort("transaction_date", desc)[0]
    except Exception as e:
        print(traceback.format_exc())
        print("Exception in retrieving daily ro sales: ", str(e))
        return None

async def execute_daily_sales():
    redis_ins = await urdhva_base.redispool.get_redis_connection()
    last_synced_time = await redis_ins.get("cris_daily_sales_sync_time")
    if not last_synced_time:
        last_synced_time = datetime.datetime.now(
            tz=datetime.timezone.utc).replace(day=1).strftime("%Y-%m-%d")
    if isinstance(last_synced_time, bytes):
        last_synced_time = last_synced_time.decode()
    sync_until = datetime.datetime.now(
            tz=datetime.timezone.utc).strftime("%Y-%m-%d")
    synced_date = await indent_dryout_sync_ro_daily_sales(last_synced_time, sync_until)
    if synced_date:
        await redis_ins.set("cris_daily_sales_sync_time", synced_date)


if __name__ == "__main__":
    asyncio.run(execute_daily_sales())
