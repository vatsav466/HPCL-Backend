import urdhva_base
import polars as pl
import traceback
import dashboard_studio_model
import charts_actions
import utilities.connection_mapping as connection_mapping


async def indent_dryout_sync_ro_daily_sales(data):
    try:
        since = data.from_date
        until = data.to_date
        # tr_transaction_dailysales
        query = f'''
            SELECT 
                "site_id",
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
                "{connection_mapping.schema_mapping.get("cris", "HPCL_HOS")}"."tr_transaction_dailysales"
            WHERE 
                "transaction_date" BETWEEN '{since}' AND '{until}';
        '''
        print(query)

        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("cris", "2")  #2   # tr_transaction_dailysales
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        data = await function(query=query)
        column_mapping = {
            "site_id": pl.Utf8,                
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
                "ro_id", 
                "sap_id"
            FROM 
                "public"."location_master"; '''
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1") # 1  ro_master
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        ro_data = await function(query=ro_query)
        ro_master = pl.DataFrame(ro_data)
        ro_master = ro_master.rename(mapping={"sap_id": "ro_sap_code"})

        tr_daily_sales = tr_daily_sales.join(ro_master.unique(subset='ro_id', keep='first'), left_on='site_id', right_on='ro_id', how='left')
        
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'upsert_data'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        conflict_columnsList = ['site_id', 'ro_sap_code', 'transaction_date', 'tank_no', 'pump_no', 
                            'nozzle_no', 'product_no', 'transaction_type']
        return await function(
            schema_name='HPCL_HOS',
            table_name='ro_daily_sales',
            records=tr_daily_sales.to_dicts(),
            conflict_columns=conflict_columnsList
        )
    except Exception as e:
        print(traceback.format_exc())
        print("Exception in retrieving daily ro sales: ", str(e))