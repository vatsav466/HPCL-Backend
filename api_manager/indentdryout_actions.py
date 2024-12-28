import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import pytz
import json
import math
import fastapi
import datetime
import polars as pl
import dateutil.parser as parser
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from orchestrator.alerting.alert_manager import create_alert
import orchestrator.analytics.dry_out_analysis as dry_out_analysis
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
from orchestrator.actions.indent_dry_out import IndentDryOut as indent_dry_out
import orchestrator.alerting.listener.sync_ro_daily_sales as sync_ro_daily_sales

router = fastapi.APIRouter(prefix='/indentdryout')


# Action sync_data_from_cris_to_ceg
@router.post('/sync_data_from_cris_to_ceg', tags=['IndentDryOut'])
async def indentdryout_sync_data_from_cris_to_ceg(data: Indentdryout_Sync_Data_From_Cris_To_CegParams):
    Charts_Connection_Vault_RoutingParams.connection_id = data.source_connection
    Charts_Connection_Vault_RoutingParams.action = 'get_data'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    records = await function(schema_name=data.source_schema, table_name=data.source_table)

    Charts_Connection_Vault_RoutingParams.connection_id = data.destination_connection
    Charts_Connection_Vault_RoutingParams.action = 'upsert_data'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    return await function(
        schema_name=data.destination_schema,
        table_name=data.destination_table,
        records=records,
        conflict_columns=data.conflict_columns
    )


# Action create_dry_out_alert
@router.post('/create_dry_out_alert', tags=['IndentDryOut'])
async def indentdryout_create_dry_out_alert(data: Indentdryout_Create_Dry_Out_AlertParams):
    def assign_values_to_dataframe(df, values):
        """
        Assigning camunda urls equally for each flow
        :param df:
        :param values:
        :return:
        """
        n = len(df)
        if n == 0:
            df = df.with_columns(pl.Series("camunda_listener", []))
            return df
        if n <= 10:
            assigned_values = values[:n]
        else:
            repeats = math.ceil(n / len(values))
            assigned_values = (values * repeats)[:n]
        df = df.with_columns(pl.Series("camunda_listener", assigned_values))
        return df

    redis_queue = urdhva_base.redispool.RedisQueue('dry_out_camunda_queue')
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    schema = connection_mapping.schema_mapping.get("cris", "public")
    table = connection_mapping.table_mapping.get("dry_out", "")
    query = f'''SELECT * FROM "{schema}"."{table}" WHERE "volume" > 0 AND "indent_status" NOT IN ('Raised', 'Completed') AND "status" IN ('0', '1', '2');'''
    query = f'''select site_id, fcc_code, item_name,count(distinct tank_no) tank_cnt,
            rosapcode, STRING_AGG(CAST(tank_no AS TEXT), ',') tank_no, product_no, indent_status, 
            case when sum(pumpable_Stock) <=0 then 1
            when sum(pumpable_Stock) <(sum(sch.avgsales_7days)/7) then 2
            when sum(pumpable_Stock) between (sum(sch.avgsales_7days)/7) and (sum(sch.avgsales_7days)/7)*3 then 3
            when sum(pumpable_Stock) between (sum(sch.avgsales_7days)/7)*3 and (sum(sch.avgsales_7days)/7)*6 then 4
            else 5 end status
            from "{schema}".{table} sch
            where 1=1 and sch.volume>0
            group by site_id, fcc_code, item_name, rosapcode, product_no, indent_status
            order by site_id, fcc_code, item_name, rosapcode, product_no'''
    # records = await function(schema_name=schema, table_name=table, query=query)
    records = await function(query=query)
    records = pl.DataFrame(records)
    records = records.filter(~pl.col("indent_status").is_in(['Raised', 'Completed']))
    records = records.unique(subset=['site_id', 'fcc_code', 'item_name', 'product_no'], keep='first')
    records = records.filter(pl.col('status') == 1)
    records = assign_values_to_dataframe(records,
                                             list(connection_mapping.camunda_listener_mapping.values()))
    records = records.head(10).to_dicts()

    alert_data = {
        'bu': 'RO',
        'alert_type': 'RO',
        'sop_id': 'SOP293',
        'interlock_name': 'Dry Out Triggering Flow',
        'sap_id': '',  # location_id
        'product_code': '',
        'indent_no': '',
        'dealer_id': '',
        'severity': "",
        'workflow_datetime': '',
        'terminal_plant_id': ''
    }

    _mapping = await indent_dry_out().prod_code_mapping()

    for _dry in records:
        _dry['indent_status'] = 'Raised'
        status = _dry['status']
        # alert_data['product_code'] = _dry['product_no']
        alert_data['product_code'] = _mapping.get(_dry['item_name'], _dry['product_no'])
        alert_data['sap_id'] = _dry['rosapcode']
        alert_data['device_id'] = str(_dry['tank_no'])
        alert_data['device_name'] = "Tank"
        # alert_data['severity'] = 'Critical' if status == 0 else 'High' if status == 1 else 'Medium' if status == 2 else 'Low'
        alert_data['severity'] = 'Critical' if status == 1 else 'High' if status == 2 else 'Medium' if status == 3 else 'Low'
        alert_data['indent_no'] = ''
        alert_data['dealer_id'] = _dry['rosapcode']
        alert_data['workflow_datetime'] = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"
        alert_data['terminal_plant_id'] = ''
        alert_data['camunda_host'] = connection_mapping.camunda_listener_mapping.get(_dry['camunda_listener'])['host']
        alert_data['camunda_port'] = connection_mapping.camunda_listener_mapping.get(_dry['camunda_listener'])['port']
        alert_data['dry_out_in_days'] = _dry['status']
        await redis_queue.put(json.dumps(alert_data))
        # await create_alert(alert_data)

        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        query = f"""UPDATE "HPCL_HOS".sch_inventory_forecast_dashboard SET "indent_status" = 'Raised' """ \
                f"""WHERE "site_id" = '{_dry['site_id']}' """ \
                f"""AND "fcc_code" = '{_dry['fcc_code']}' """ \
                f"""AND "product_no" = '{_dry['product_no']}' """
        await function(
            query=query
        )
        # await function(
        #     schema_name="HPCL_HOS",
        #     table_name=connection_mapping.table_mapping.get("dry_out", ""),
        #     records=_dry,
        #     conflict_columns=["site_id", "fcc_code", "product_no", "tank_no"]
        # )

    return {"status": True, "message": "Alerts created successfully", "data": []}


# Action get_dried_out_plants
@router.post('/get_dried_out_plants', tags=['IndentDryOut'])
async def indentdryout_get_dried_out_plants(data: Indentdryout_Get_Dried_Out_PlantsParams):
    top_x_axis = [
        "Indent Not Raised", "Pending Indents", "Indent On Hold", "Truck Allocated", "Sent to SAP",
        "Sales Order Placed", "R2 Swiped", "Invoice Created", "R3 Swiped", "VTS", "Indent Delivered"
    ]
    bottom_x_axis = [
        "Dealer", "SO\nRM", "SO\nCO", "SO", "SO\nRM", "SO\nRM", "PO\nRM", "PO\nRM", "PO\nRM", "PO\nRM", "SO\nRM"
    ]
    where_clause = ["interlock_name = 'Indent Dry Out'"]
    where_clause = ["interlock_name = 'Dry Out Each Indent Wise MainFlow'"]
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    for record in data.filters:
        # If filter was on Sales Area Getting all ro id's under that sales area
        # if record.key in ['sales_area', 'category']:
        #     if record.value:
        #         if record.key == "sales_area":
        #             if len(record.value) == 1:
        #                 query = f"select ro_id from location_master where sales_area='{record.value[0]}' and bu='RO'"
        #             else:
        #                 query = f"select ro_id from location_master where sales_area in {tuple(record.value)} and bu='RO'"
        #         else:
        #             values = []
        #             for rec in record.value:
        #                 if "(" in rec:
        #                     values.append(rec.split("(")[-1].split(")")[0].strip())
        #                 else:
        #                     values.append(rec)
        #             if len(values) == 1:
        #                 query = f"select ro_id from location_master where terminal_plant_id='{values[0]}' and bu='RO'"
        #             else:
        #                 query = f"select ro_id from location_master where terminal_plant_id in {tuple(values)} and bu='RO'"
        #         function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        #         resp = await function(
        #             query=query
        #         )
        #         ro_ids = [rec['ro_id'] for rec in resp]
        #         if len(ro_ids) == 1:
        #             where_clause.append(f"sap_id='{ro_ids[0]}'")
        #         elif len(ro_ids) > 1:
        #             where_clause.append(f"sap_id in {tuple(ro_ids)}")
        if record.key == "progress_rate":
            where_clause.append(f"progress_rate={int(record.value[0])-1}")
        else:
            if record.value:
                if record.key == "plant":
                    record.key = "terminal_plant_id"
                if len(record.value) == 1:
                    where_clause.append(f"{record.key}='{record.value[0]}'")
                else:
                    where_clause.append(f"{record.key} in {tuple(record.value)}")
    conditions = ' AND '.join(where_clause)
    query = "select location_name as name, sap_id, progress_rate as present_stage, id as alert_id," \
            "case when severity = 'Critical' then '1' " \
            "when severity = 'High' then '2' " \
            "when severity = 'Medium' then '3' " \
            "when severity = 'Low' then '4' " \
            "else severity " \
            "end as dry_out_days " \
            f"from alerts where {conditions}"
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    resp = await function(
        query=query
    )
    stats = {i+1: 0 for i, _ in enumerate(top_x_axis)}
    for rec in resp:
        if rec['present_stage'] == 0:
            rec['present_stage'] = 1
        if rec['present_stage'] not in stats:
            stats[rec['present_stage']] = 0
        stats[rec['present_stage']] += 1
    stats = [{"section": top_x_axis[key-1], "value": value, "serial": key}
             for key, value in stats.items() if key <= len(top_x_axis)]
    stats = sorted(stats, key=lambda x: x['serial'])
    return {"status": True, "message": "Success", "data": resp, "top_x_axis": top_x_axis,
            "bottom_x_axis": bottom_x_axis, "stats": stats}


# Action get_dry_out_stats
@router.post('/get_dry_out_stats', tags=['IndentDryOut'])
async def indentdryout_get_dry_out_stats(data: Indentdryout_Get_Dry_Out_StatsParams):
    ...


# Action get_alert_history
@router.post('/get_alert_history', tags=['IndentDryOut'])
async def indentdryout_get_alert_history(data: Indentdryout_Get_Alert_HistoryParams):
    resp = await Alerts.get(data.alert_id)
    if not isinstance(resp, dict):
        resp = resp.__dict__
    alert_history = {
        "details": {},
        "data": []
    }

    def convert_time_read_format(date_time):
        try:
            utc_timestamp = parser.parse(date_time).replace(tzinfo=None)
            # Define UTC and IST timezones
            utc = pytz.utc
            ist = pytz.timezone('Asia/Kolkata')
            # Localize the UTC timestamp and convert it to IST
            utc_time = utc.localize(utc_timestamp)
            ist_time = utc_time.astimezone(ist)
            # Format the IST timestamp in the desired format
            formatted_ist_time = ist_time.strftime('%Y-%m-%dT%H:%M:%S.%f')
            return formatted_ist_time
        except:
            return "-"

    if resp:
        alert_history["details"] = {"name": resp['location_name'], "sap_id": resp['sap_id'], "zone": resp["zone"],
                                    "state": resp["state"], "indent_status": resp["indent_status"],
                                    "indent_raised_date": convert_time_read_format(str(resp['indent_raised_date']))}
        alert_history["data"].append({"action_msg": "Dry-out Location Identified",
                                      "allocated_time": convert_time_read_format(str(resp['created_at'])),
                                      "processed_time": convert_time_read_format(str(resp['created_at']))})
        for history in resp.get("alert_history", []):
            alert_history["data"].append({"action_msg": history['action_msg'],
                                          "allocated_time": convert_time_read_format(str(history['allocated_time'])),
                                          "processed_time": convert_time_read_format(str(history['processed_time']))})
        # alert_history["data"].append(f"Dry-out Location Identified at "
        #                              f"{convert_time_read_format(str(resp['created_at']))}")
        # for history in resp.get("alert_history", []):
        #     alert_history["data"].append(f"Action:- {history['action_msg']}, {history['action_type']} at"
        #                                  f" {convert_time_read_format(str(history['allocated_time']))}, "
        #                                  f"Processed at {convert_time_read_format(str(history['processed_time']))}")
    return alert_history


# Action get_distinct_plant
@router.post('/get_distinct_plant', tags=['IndentDryOut'])
async def indentdryout_get_distinct_plant(data: Indentdryout_Get_Distinct_PlantParams):
    region = " ".join(data.region.split()[:-2])
    query = (f"select DISTINCT terminal_plant_id FROM location_master where bu='RO' and "
             f"LOWER(sales_area) like '%{region.lower()}%' and terminal_plant_id!=''")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    resp = await function(
        query=query
    )
    plant_id = [rec['terminal_plant_id'] for rec in resp if rec['terminal_plant_id']]
    cond = ""
    if len(plant_id) == 1:
        cond = f"sap_id = {plant_id[0]}"
    else:
        cond = f"sap_id IN {tuple(plant_id)}"
    query = f"select name,sap_id from location_master where {cond}"
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    resp = await function(
        query=query
    )
    map_data = {rec['sap_id']: rec['name'] for rec in resp}
    for key in plant_id:
        if key not in map_data:
            map_data[key] = key
    return [f"{key}({value})" for key, value in map_data.items()]

    # Correct return statement
    return [f"{rec['terminal_plant_id']}({rec['terminal_plant_name']})" for rec in resp if rec['terminal_plant_id']]


# Action get_distinct_location_details
@router.post('/get_distinct_location_details', tags=['IndentDryOut'])
async def indentdryout_get_distinct_location_details(data: Indentdryout_Get_Distinct_Location_DetailsParams):
    return {"status": True, "message": "Success",
            "data": await dry_out_analysis.get_locations(data.bu, data.zone, data.region, data.sales_area, data.plant)}


# Action sync_ro_daily_sales
@router.post('/sync_ro_daily_sales', tags=['IndentDryOut'])
async def indentdryout_sync_ro_daily_sales(data: Indentdryout_Sync_Ro_Daily_SalesParams):

    return await sync_ro_daily_sales.indent_dryout_sync_ro_daily_sales(data.from_date, data.to_date)

# Action get_indent_analysis
@router.post('/get_indent_analysis', tags=['IndentDryOut'])
async def indentdryout_get_indent_analysis(data: Indentdryout_Get_Indent_AnalysisParams):
    conditions = {rec.key: rec.value for rec in data.filters}
    if conditions["model"] == "all":
        if conditions.get("category") == "cat_a":
            ...
        return {"indents_not_placed": 300, "indents_on_hold": 50, "indents_in_progress": 34,
                "pending_indents": 23, "total": 407}
    elif conditions["model"] == "pending_indents":
        if conditions.get("category") == "cat_a":
            ...
        return {"dealer_tt": 10, "tt_available": 0, "dealer_tt_return": 4, "tt_return": 11,
                "pending_indents": 23, "date": str(datetime.datetime.utcnow())}
    elif conditions["model"] == "indents_not_placed":
        if conditions.get("category") == "cat_a":
            ...
        return {"indents_not_placed": 1000, "date": str(datetime.datetime.utcnow()),
                "dry_out_2days": 50, "dry_out_7days": 34, "dry_out_15days": 12, "dry_out_30days": 0}
    else:
        return {}


# Action get_dry_out_count
@router.post('/get_dry_out_count', tags=['IndentDryOut'])
async def indentdryout_get_dry_out_count(data: Indentdryout_Get_Dry_Out_CountParams):
    schema = connection_mapping.schema_mapping.get("cris")
    table = connection_mapping.table_mapping.get("dry_out")
    query = f'''select site_id, fcc_code, item_name,count(distinct tank_no) tank_cnt,
                rosapcode, STRING_AGG(CAST(tank_no AS TEXT), ',') tank_no, product_no, 
                case when sum(pumpable_Stock) <=0 then 1
                when sum(pumpable_Stock) <(sum(sch.avgsales_7days)/7) then 2
                when sum(pumpable_Stock) between (sum(sch.avgsales_7days)/7) and (sum(sch.avgsales_7days)/7)*3 then 3
                when sum(pumpable_Stock) between (sum(sch.avgsales_7days)/7)*3 and (sum(sch.avgsales_7days)/7)*6 then 4
                else 5 end status
                from "{schema}".{table} sch
                where 1=1 and sch.volume>0
                group by site_id, fcc_code, item_name, rosapcode, product_no
                order by site_id, fcc_code, item_name, rosapcode, product_no'''
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("cris", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    dry_out_data = await function(query=query)
    dry_out_data = pl.DataFrame(dry_out_data)
    dry_out = dry_out_data.filter(
        pl.col("status") == 1).select(
        [pl.col("rosapcode")]
    ).unique().shape[0]

    intraday_dry_out = dry_out_data.filter(
        pl.col("status") == 2).select(
        [pl.col("rosapcode")]
    ).unique().shape[0]

    potential_dry_out = dry_out_data.filter(
        pl.col("status").is_in([3])).select(
        [pl.col("rosapcode")]
    ).unique().shape[0]

    return {
        "dry_out": dry_out, "intraday_dry_out": intraday_dry_out,
        "potential_dry_out": potential_dry_out, "aging_analysis": "-"
    }


# Action get_filtered_location_data
@router.post('/get_filtered_location_data', tags=['IndentDryOut'])
async def indentdryout_get_filtered_location_data(data: Indentdryout_Get_Filtered_Location_DataParams):
    return await dry_out_analysis.get_filtered_location_data(data.bu, data.request_parameter, data.filters)


# Action get_indent_data
@router.post('/get_indent_data', tags=['IndentDryOut'])
async def indentdryout_get_indent_data(data: Indentdryout_Get_Indent_DataParams):
    record = data.filters
    indent_mapping = {
        "indent_not_placed": ["Pending"],
        "indent_on_hold": ["IndentOnHold"],
        "indent_in_progress": [
            "IndentRaised", "TruckAllocated", "InvoiceCreated",
            "ValidIndent", "SentToSAP", "SalesOrderPlaced",
            "R2Swipe", "R3Swipe"
        ]
    }
    # Prepare a dictionary to store results
    result = {}
    total_count = 0
    # Loop through each indent group to calculate the count
    for indent_key, indent_values in indent_mapping.items():
    # Construct conditions
        conditions = []
        for rec in record:
            if rec.key == "indent_status":
                # Map the input value to the corresponding list in indent_mapping
                mapped_values = indent_values  # Use the values for the current indent group
                # Create the condition for indent_status
                condition = f"""indent_status IN ({', '.join([f"'{val}'" for val in mapped_values])})"""
            else:
                # Default condition for other keys
                condition = f"{rec.key} = '{rec.value}'"
            conditions.append(condition)
        # Combine all conditions using AND
        where_clause = ' AND '.join(conditions)
        # Build the SQL query
        query = f'''SELECT COUNT(indent_status) as count FROM alerts WHERE {where_clause}'''
        print(f"Generated Query for {indent_key}:", query)
        # Execute the query
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)

        print(f"Response for {indent_key} --> ", resp)

        # Extract the count from the response and store it in the result dictionary
        if resp and isinstance(resp, list) and "count" in resp[0]:
            count = resp[0]["count"]
            result[indent_key] = count
            total_count += count 
        else:
            result[indent_key] = 0  # Default to 0 if no result is found
    dry_out_counts = await indentdryout_get_dry_out_count(data)
    dry_out_count = dry_out_counts.get("dry_out", 0)
    # Add the dry_out count to the result dictionary
    result["dry_out"] = dry_out_count
    total_count += dry_out_count
    result["total_count"] = total_count
    # Return the final result
    return result


# Action get_dried_out_ro
@router.post('/get_dried_out_ro', tags=['IndentDryOut'])
async def indentdryout_get_dried_out_ro(data: Indentdryout_Get_Dried_Out_RoParams):
    top_x_axis = connection_mapping.dry_out_top_x_axis

    where_clause = ["interlock_name = 'Dry Out Each Indent Wise MainFlow'"]
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    for record in data.filters:
        if record.key == "progress_rate":
            where_clause.append(f"progress_rate={int(record.value[0])}")
        else:
            if record.value:
                if record.key == "plant":
                    record.key = "terminal_plant_id"
                if len(record.value) == 1:
                    where_clause.append(f"{record.key}='{record.value[0]}'")
                else:
                    where_clause.append(f"{record.key} in {tuple(record.value)}")
    conditions = ' AND '.join(where_clause)
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

    stats_query = "select sap_id, min(progress_rate) as present_stage " \
                  f"from alerts where {conditions} and indent_status != 'Cancelled' " \
                  f"group by sap_id"
    stats_resp = await function(
        query=stats_query
    )

    dealer_tt = pl.read_csv("/opt/ceg/algo/utilities/DealerOwnedTrucks.csv", infer_schema_length=0)['DEALERID'].to_list()

    stats = {i + 1: 0 for i, _ in enumerate(top_x_axis)}
    dealer_tt_count = {x: 0 for x in connection_mapping.truck_details}
    for rec in stats_resp:
        if rec['present_stage'] == 0:
            rec['present_stage'] = 1
        if rec['present_stage'] not in stats:
            stats[rec['present_stage']] = 0
        stats[rec['present_stage']] += 1
        if str(rec['sap_id']) in dealer_tt:
            dealer_tt_count['Dealer TT'] += 1

    stats = [{"section": top_x_axis[key - 1]['name'], "value": value, "serial": key, "condition": "=",
              "group": top_x_axis[key - 1]['group']}
             for key, value in stats.items() if key <= len(top_x_axis)]
    stats.extend([{
            "section": "Indent Raised",
            "value": sum(item['value'] for item in stats if 2 <= item['serial'] <= 10),
            "serial": 12, "condition": "=", "group": "not_raised"
        },{
            "section": "Valid \\ WIP Indents",
            "value": sum(item['value'] for item in stats if 4 <= item['serial'] <= 10),
            "serial": 13, "condition": "=", "group": "pending"
        }])
    stats.extend([{"section": x, "value": dealer_tt_count.get(x, 0), "serial": 0, "condition": "=", "group": "truck_details"}
                  for x in connection_mapping.truck_details])
    stats.extend([{"section": x, "value": 0, "serial": 0, "condition": "=", "group": "dryout_aging"}
                  for x in connection_mapping.dryout_aging])
    stats = sorted(stats, key=lambda x: x['serial'])
    return {
        "status": True, "message": "Success", "stats": stats,
        "valid_indents": {
            "section": "Valid Indents", "value": sum([rec['value'] for rec in stats[3:-1]]),
            "serial": stats[3]['serial'], "condition": ">", "group": "valid_indents"
        }
    }


# Action get_dried_out_ro_data
@router.post('/get_dried_out_ro_data', tags=['IndentDryOut'])
async def indentdryout_get_dried_out_ro_data(data: Indentdryout_Get_Dried_Out_Ro_DataParams):
    top_x_axis = connection_mapping.dry_out_top_x_axis
    bottom_x_axis = connection_mapping.dry_out_bottom_x_axis

    where_clause = ["interlock_name = 'Dry Out Each Indent Wise MainFlow'"]
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    for record in data.filters:
        if record.key == "progress_rate":
            where_clause.append(f"progress_rate={int(record.value[0])}")
        else:
            if record.value:
                if record.key == "plant":
                    record.key = "terminal_plant_id"
                if len(record.value) == 1:
                    where_clause.append(f"{record.key}='{record.value[0]}'")
                else:
                    where_clause.append(f"{record.key} in {tuple(record.value)}")
    conditions = ' AND '.join(where_clause)
    query = "select location_name as name, sap_id, progress_rate as present_stage, id as alert_id," \
            "indent_no as indent_no, product_code as product_code, dry_out_in_days " \
            f"from alerts where {conditions} limit 500"
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    resp = await function(
        query=query
    )

    grouped_data = {}
    for entry in resp:
        sap_id = entry["sap_id"]
        if sap_id not in grouped_data:
            grouped_data[sap_id] = []
        grouped_data[sap_id].append(entry)
    formatted_data = [{key: value} for key, value in grouped_data.items()]

    return {"status": True, "message": "Success", "data": formatted_data,
            "top_x_axis": [rec['name'] for rec in top_x_axis],
            "bottom_x_axis": bottom_x_axis}
