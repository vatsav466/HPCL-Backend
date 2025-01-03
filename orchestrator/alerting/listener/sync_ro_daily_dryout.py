import urdhva_base
import asyncio
import traceback
import datetime
import polars as pl
import charts_actions
import dashboard_studio_model
import utilities.connection_mapping as connection_mapping


async def indent_sync_ro_daily_dryout():
    try:
        ro_query = f"""SELECT * FROM "HPCL_HOS".sch_inventory_forecast_dashboard """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get(
            "cris", "1")  # 1  ro_master
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        ro_data = await function(query=ro_query)
        ro_data = pl.DataFrame(ro_data)
        sync_date = datetime.datetime.now().strftime("%y%m%d-%H") + "00"
        ro_data = ro_data.with_columns(pl.lit(sync_date).alias("run_id"))

        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get(
            "hpcl_ceg", "1")
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'upsert_data'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        resp = await function(
            schema_name="HPCL_HOS",
            table_name="sch_inventory_forecast_dashboard",
            records=ro_data.to_dicts(),
            conflict_columns=["site_id", "fcc_code", "product_no", "tank_no", "run_id"]
        )
        return {"status": True, "message": "Data Synced Successfully", "data": []}
    except Exception as e:
        print(traceback.format_exc())
        return {"status": False, "message": "Data Sync Failed", "data": e}

if __name__ == "__main__":
    asyncio.run(indent_sync_ro_daily_dryout())
