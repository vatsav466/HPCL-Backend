import urdhva_base
import pytz
import asyncio
import traceback
import datetime
import polars as pl
import pandas as pd
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
        ro_data_schema = {
            "site_id": pl.String, "fcc_code": pl.String, "tank_no": pl.Int64,
            "product_no": pl.Int64, "item_name": pl.String, "capacity": pl.Int64,
            "volume": pl.Float64, "ullage": pl.Float64, "avgsales_7days": pl.String,
            "stock_date": pl.Datetime, "status": pl.Int64, "daysstatus": pl.Int64,
            "sap_color": pl.String, "lastrocdate": pl.Datetime, "executed_on": pl.Datetime,
            "executed_by": pl.String, "pumpable_stock": pl.Float64, "rosapcode": pl.String,
            "product_grp": pl.String, "product_sap_color": pl.String
        }
        ro_data = pd.DataFrame(ro_data)
        _list_column = ['site_type', 'is_abhyuday', 'receipt_grp']
        for col in _list_column:
            if col in ro_data.columns:
                del ro_data[col]
        ro_data = pl.DataFrame(ro_data, schema=ro_data_schema)
        ist = pytz.timezone('Asia/Kolkata')
        sync_date = datetime.datetime.now(ist).strftime("%y%m%d-%H") + "00"
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
