import urdhva_base
import os
import json
import datetime
import requests
import pandas as pd
import polars as pl
import hpcl_ceg_model
import charts_actions
import mysql.connector
import urdhva_base.redispool
import dashboard_studio_model
import utilities.helpers as helpers
from dashboard_studio_model import Charts_Get_Distinct_ValuesParams
from orchestrator.dbconnector.widget_actions import widget_actions
from api_manager.charts_actions import charts_connection_vault_routing
import orchestrator.dbconnector.credential_loader as credential_loader
from orchestrator.dbconnector.widget_actions.lpg_plant_queries import today
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
from utilities.connection_mapping import product_code_mapping, connection_mapping

req_keys = {
    "TAS": ["zone", "sap_id", "name", "category"],
    "LPG": ["zone", "sap_id", "name", "category"],
    "RO": ["zone", 'region', "sales_area", "terminal_plant_id", "terminal_plant_name", "category", "sap_id", "name"]
}


async def get_locations(bu, zone=[], region=[], sales_area=[], plant=[], cat_a_dealers=False, dry_out_dealers=False):
    """
    This function is used to get the location information for a given BU.
    It fetches the location master data from Redis and filters based on the BU provided.
    If zone, region and sales_area are provided, then it filters based on those as well.
    :param bu:
    :param zone:
    :param region:
    :param sales_area:
    :param plant:
    :param cat_a_dealers
    :param dry_out_dealers
    :return:
    """
    bu = bu.upper()
    cond = await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)
    dry_out_plants = []
    dry_out_customers = []
    for rec in cond:
        if rec['key'] == 'zone':
            if not zone:
                zone = []
            if isinstance(rec['value'], list):
                zone.extend(rec['value'])
            else:
                zone.append(rec['value'])
        elif rec['key'] == 'region':
            if not region:
                region = []
            if isinstance(rec['value'], list):
                region.extend(rec['value'])
            else:
                region.append(rec['value'])
        elif rec['key'] == 'sap_id':
            if not plant:
                plant = []
            if isinstance(rec['value'], list):
                plant.extend(rec['value'])
            else:
                plant.append(rec['value'])
        elif rec['key'] == 'sales_area':
            if not sales_area:
                sales_area = []
            if isinstance(rec['value'], list):
                sales_area.extend(rec['value'])
            else:
                sales_area.append(rec['value'])
    redis_client = await urdhva_base.redispool.get_redis_connection()
    location_data = await redis_client.hgetall("location_master")

    bu_data = [json.loads(helpers.normalize_string(rec)) for key, rec in location_data.items()
               if helpers.normalize_string(key).startswith(f"{bu}_")]
    bu_data = pd.DataFrame(bu_data)
    for key in req_keys[bu]:
        if key not in bu_data:
            bu_data[key] = ""
    bu_data = bu_data[req_keys[bu]]
    bu_data.fillna("", inplace=True)
    if bu.upper() == "RO":
        # Updating Plant Name in case if missing
        tas_data = [json.loads(helpers.normalize_string(rec)) for key, rec in location_data.items()
                    if helpers.normalize_string(key).startswith(f"TAS_")]
        terminal_name_mapping = {rec['sap_id']: rec['name'] for rec in tas_data}
        bu_data['terminal_plant_name'] = bu_data['terminal_plant_id'].apply(lambda x: terminal_name_mapping.get(x, x))
        bu_data = bu_data[bu_data['terminal_plant_name'].notna()]
    final_data = {"zone": {}, "plant": {}, "customer": {}}
    if bu.upper() == "RO":
        final_data.update({"region": {}, "sales_area": {}, "customer": {}})

    def check_category(category):
        if category and category.upper() == "R01":
            return "A"
        return ""

    key_mapping = {}

    # Filtering zone
    for rec in bu_data.to_dict(orient='records'):
        if rec["zone"]:
            if cond and plant and rec['sap_id'] not in plant:
                continue
            final_data["zone"][rec["zone"]] = {"name": rec["zone"], "id": rec["zone"]}
    if dry_out_dealers:
        query = """select dealer_id, terminal_plant_id
                from public.alerts where interlock_name='Dry Out Each Indent Wise MainFlow' and dry_out_in_days='1' and 
                alert_status in ('Open', 'InProgress') 
                group by dealer_id, terminal_plant_id"""
        data = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=10000)
        dry_out_plants = list(set([rec['terminal_plant_id'] for rec in data['data']]))
        dry_out_customers = list(set([rec['dealer_id'] for rec in data['data']]))
    if zone:
        key_mapping["zone"] = zone
    if bu in ["TAS", "LPG"]:
        for rec in bu_data.to_dict(orient='records'):
            skip_record = False
            if key_mapping:
                for key, value in key_mapping.items():
                    if rec.get(key) not in value:
                        skip_record = True
                        break
            if skip_record or not rec["sap_id"]:
                continue
            if rec["sap_id"]:
                if plant and rec['sap_id'] not in plant:
                    continue
                if dry_out_dealers and rec["sap_id"] not in dry_out_plants:
                    continue
                final_data["plant"][rec["sap_id"]] = {"name": rec["name"], "id": rec["sap_id"]}
        bu_data_ro = [json.loads(helpers.normalize_string(rec)) for key, rec in location_data.items()
                      if helpers.normalize_string(key).startswith(f"RO_")]
        bu_data_ro = pd.DataFrame(bu_data_ro)
        for key in ["name", "category"]:
            if key not in bu_data_ro:
                bu_data_ro[key] = ""
            bu_data_ro[key] = bu_data_ro[key].fillna("")
        # bu_data_ro['name'] = bu_data_ro['name'].fillna("")
        # bu_data_ro['category'] = bu_data_ro['category'].fillna("")
        if plant:
            key_mapping["terminal_plant_id"] = plant
        for rec in bu_data_ro.to_dict(orient='records'):
            skip_record = False
            if key_mapping:
                for key, value in key_mapping.items():
                    if rec.get(key) not in value:
                        skip_record = True
                        break
            if skip_record or not rec["sap_id"]:
                continue
            if rec["sap_id"]:
                if dry_out_dealers and rec["sap_id"] not in dry_out_customers:
                    continue
                if cat_a_dealers and check_category(rec['category']) != "A":
                    continue
                final_data["customer"][rec["sap_id"]] = {"name": str(rec["sap_id"]) + " - " + rec["name"], "id": rec["sap_id"],
                                                         "category": check_category(rec['category'])}
    else:
        if region:
            key_mapping["region"] = region

        # Filtering region
        for rec in bu_data.to_dict(orient='records'):
            skip_record = False
            if key_mapping:
                for key, value in key_mapping.items():
                    if rec.get(key) not in value:
                        skip_record = True
                        break
            if skip_record or not rec.get("region"):
                continue
            if rec.get("region"):
                final_data["region"][rec["region"]] = {"name": rec["region"], "id": rec["region"]}

        # Filtering Sales Area
        if sales_area:
            key_mapping["sales_area"] = sales_area
        for rec in bu_data.to_dict(orient='records'):
            skip_record = False
            if key_mapping:
                for key, value in key_mapping.items():
                    if rec.get(key) not in value:
                        skip_record = True
                        break
            if skip_record or not rec.get("sales_area"):
                continue
            if rec.get("sales_area"):
                final_data["sales_area"][rec["sales_area"]] = {"name": rec["sales_area"], "id": rec["sales_area"]}

        # Filtering Plant
        for rec in bu_data.to_dict(orient='records'):
            skip_record = False
            if key_mapping:
                for key, value in key_mapping.items():
                    if rec.get(key) not in value:
                        skip_record = True
                        break
            if skip_record or not rec["sap_id"]:
                continue
            if rec["sap_id"]:
                if dry_out_dealers and rec["sap_id"] not in dry_out_customers:
                    continue
                if cat_a_dealers and check_category(rec['category']) != "A":
                    continue
                final_data["customer"][rec["sap_id"]] = {"name": rec["name"], "id": rec["sap_id"],
                                                         "category": check_category(rec['category'])}

    for key, details in final_data.items():
        final_data[key] = list(details.values())

    # adding products
    final_data["products"] = [{"name": val, "id": key} for val, key in product_code_mapping.items()]

    return final_data


async def get_filtered_location_data(bu, request_parameter, filters):
    """
    Fetch and filter location data for a given business unit (BU).

    :param bu: Business Unit (e.g., "RO", "TAS")
    :param request_parameter: The key to retrieve (e.g., "name", "zone", "dry-out", etc.)
    :param filters: A list of filter objects containing `key`, `value`, and `cond` (condition: "contains" or "equals").
    :return: Filtered location data as a list of dictionaries.
    """
    # Ensure business unit is in uppercase
    bu = bu.upper()

    # Connect to Redis and fetch location data
    redis_client = await urdhva_base.redispool.get_redis_connection()
    location_data = await redis_client.hgetall("location_master")

    # Filter data by business unit
    bu_data = [
        json.loads(helpers.normalize_string(rec))
        for key, rec in location_data.items()
        if helpers.normalize_string(key).startswith(f"{bu}_")
    ]

    # Convert the filtered data to a pandas DataFrame
    bu_data = pd.DataFrame(bu_data)

    # Ensure required keys are present in the DataFrame, filling with empty strings if missing
    for key in req_keys[bu]:
        if key not in bu_data:
            bu_data[key] = ""

    # Restrict DataFrame to only the required keys
    bu_data = bu_data[req_keys[bu]]

    # Replace NaN values with empty strings
    bu_data.fillna("", inplace=True)
    dry_out_locations = False
    if request_parameter == "dry-out":
        dry_out_locations = True
        request_parameter = "name"

    # Apply filters to the DataFrame
    for filter in filters:
        if filter.cond.lower() == "contains":
            # Filter rows where the value of the key contains any of the strings in filter.value
            bu_data = bu_data[bu_data[filter.key].str.contains('|'.join(filter.value), case=False, na=False)]
        else:
            # Filter rows where the value of the key matches exactly with filter.value
            bu_data = bu_data[bu_data[filter.key].isin(filter.value)]

    # If the request is for names, process the output accordingly
    if request_parameter == "name":
        fields = ["sap_id", "name"]
        if bu == "RO":
            # Add "category" field for RO business unit
            fields.append("category")

        # Restrict DataFrame to the required fields and rename "sap_id" to "id"
        bu_data = bu_data[fields]
        bu_data.rename(columns={"sap_id": "id"}, inplace=True)

        # Drop rows where "id" is null
        bu_data = bu_data[bu_data.id.notna()]

        # Convert DataFrame to a list of dictionaries
        return bu_data.to_dict(orient='records')

    else:
        # Process the DataFrame to get unique values for the requested parameter
        bu_data = bu_data[[request_parameter]]
        unique_keys_list = [key for key in list(bu_data[request_parameter].unique()) if key]

        # Convert unique values into a list of dictionaries with "id" and "name"
        resp = [{'id': key, "name": key} for key in unique_keys_list]
        # Filtering dry out locations
        if dry_out_locations:
            query = ("select DISTINCT(sap_id) from alerts where interlock_name = 'Dry Out Each Indent Wise MainFlow' "
                     "and alert_status='Open'")
            data = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=10000)
            dry_out_locations = [rec['sap_id'] for rec in data['data']]
            resp = [rec for rec in resp if rec['id'] in dry_out_locations]
        return resp

async def get_carry_fwd_indent(get_only_dry_out_ro: bool):
    query = f"""SELECT DISTINCT 
                    "LOCN_CODE", 
                    SUBSTR("DEALER_CODE", 3, 8) AS "DEALER_CODE",
                    "PROD_REQD_DT",
                    "INDENT_NO"
                FROM 
                    "IMS_SAP"."INDENT_REQUEST"
                WHERE 
                    "PROD_REQD_DT" < SYSDATE
                    AND "TRUCK_REGNO" IS NULL
                    AND "CANCEL_INDENT" IS NULL
                    AND "VALID_INDENT" IN ('Y', 'H')
                ORDER BY 
                    "LOCN_CODE" """

    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get("ims", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    data = await function(query=query)
    data = pd.DataFrame(data)
    data['DEALER_CODE'] = str(data['DEALER_CODE']) + '-' + str(data['INDENT_NO'])

    if get_only_dry_out_ro:
        query = f"""SELECT DISTINCT 
                        ir."LOCN_CODE",
                        SUBSTR(ir."DEALER_CODE", 3, 8) AS "DEALER_CODE",
                       ir. "INDENT_NO",
                       ir."PROD_REQD_DT"
                    FROM 
                        "IMS_SAP"."INDENT_REQUEST" ir
                    INNER JOIN 
                        "alerts" a
                    ON 
                        SUBSTR(ir."DEALER_CODE", 3, 8) = a."dealer_id"
                        AND ir."INDENT_NO"::TEXT = a."indent_no"::TEXT
                    WHERE 
                        ir."PROD_REQD_DT" < CURRENT_DATE
                        AND ir."TRUCK_REGNO" IS NULL
                        AND ir."CANCEL_INDENT" IS NULL
                        AND ir."VALID_INDENT" IN ('Y', 'H')"""

    return data['DEALER_CODE'].unique().tolist()

async def get_indent_pattern(is_cat_a: bool, dealer_code: str = None):
    if is_cat_a:
        dealer_code_condition = []
        dealer_code_condition = ", ".join(f"'{code}'" for code in dealer_code_condition)
        where_clause = f"""
            WHERE 
                SUBSTR(a."DEALER_CODE", 1, 10) = '{dealer_code_condition}'
                AND a."CANCEL_INDENT" IS NULL 
                AND a."VALID_INDENT" != 'N'
                AND a."INDENT_DATE" >= ADD_MONTHS(SYSDATE, -3)
            """
    elif dealer_code:
        # dealer_codes = ", ".join(f"'{code}'" for code in dealer_code)
        where_clause = f"""
            WHERE 
                SUBSTR(a.DEALER_CODE, 1, 10) = '{dealer_code}'
                AND a."CANCEL_INDENT" IS NULL 
                AND a."VALID_INDENT" != 'N'
                AND a."INDENT_DATE" >= ADD_MONTHS(SYSDATE, -3)
            """
    else:
        where_clause = """
            WHERE 
                a."CANCEL_INDENT" IS NULL 
                AND a."VALID_INDENT" != 'N'
                AND a."INDENT_DATE" >= ADD_MONTHS(SYSDATE, -3)
            """
    query = f"""WITH base_data AS (
                    SELECT 
                        TRUNC(a."INDENT_DATE") AS "INDENT_DATE", 
                        a."INDENT_NO", 
                        a."DEALER_CODE", 
                        a."LOCN_CODE", 
                        b."PROD"
                    FROM 
                        "IMS_SAP"."INDENT_REQUEST" a
                    INNER JOIN 
                        "IMS_SAP"."INDENT_PRODUCTS" b
                    ON 
                        a."INDENT_NO" = b."INDENT_NO" AND a."LOCN_CODE" = b."LOCN_CODE"
                    {where_clause}
                ),
                frequency_calculation AS (
                    SELECT 
                        "INDENT_DATE", 
                        "INDENT_NO", 
                        "PROD",
                        LEAD("INDENT_DATE") OVER (PARTITION BY "DEALER_CODE", "PROD" ORDER BY "INDENT_DATE") AS "NEXT_INDENT_DATE",
                        "DEALER_CODE", 
                        "LOCN_CODE"
                    FROM 
                        base_data
                )
                SELECT 
                    b."INDENT_DATE", 
                    f."NEXT_INDENT_DATE",
                    b."DEALER_CODE", 
                    b."LOCN_CODE", 
                    b."PROD",
                    b."INDENT_NO",
                    CASE 
                        WHEN f."NEXT_INDENT_DATE" IS NOT NULL THEN f."NEXT_INDENT_DATE" - b."INDENT_DATE"
                        ELSE NULL
                    END AS frequency_in_days
                FROM 
                    base_data b
                INNER JOIN 
                    frequency_calculation f
                ON 
                    b."LOCN_CODE" = f."LOCN_CODE" 
                    AND b."INDENT_NO" = f."INDENT_NO"
                    AND b."PROD" = f."PROD"
                ORDER BY 
                    b."INDENT_DATE" DESC, b."PROD" """
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get("ims", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    data = await function(query=query)
    return data

async def get_ro_with_no_indent_in_ims():
    ...

async def get_category_sync():
    query = f"""SELECT SUBSTR("DEALER_CODE", 1, 10) AS "DEALER_CODE", "CATEGORY1" FROM "IMS_SAP"."DEALER_DETAILS"
                WHERE "CATEGORY1" = 'R01'"""
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get("ims", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    data = await function(query=query)
    data = pd.DataFrame(data)
    data['DEALER_CODE'] = data['DEALER_CODE'].astype(str).str.lstrip('0')

    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get("hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'upsert_data'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    return await function(
        schema_name="IMS_SAP",
        table_name="DEALER_DETAILS_CATA",
        records=data.to_dict(orient="records"),
        conflict_columns=["DEALER_CODE"]
    )


async def sync_carry_fwd_indent(insert_to_db: bool):
    conditions = await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)
    where_clause = []
    for rec in conditions:
        if rec['key'] == 'sap_id':
            if isinstance(rec['value'], str):
                where_clause.append(f"terminal_plant_id='{rec['value']}'")
            else:
                if len(rec['value']) == 1:
                    where_clause.append(f"terminal_plant_id='{rec['value'][0]}'")
                else:
                    where_clause.append(f"terminal_plant_id in {tuple(rec['value'])}")
    base_conditions = " AND ".join(where_clause)
    if base_conditions:
        combined_query = " where a." + " AND a.".join(where_clause)
        cd_query = " where cd." + " AND cd.".join(where_clause)
        where_clause = " AND " + base_conditions
    else:
        where_clause = ""
        combined_query = ""
        cd_query = ""
    query = f"""WITH INDENT_DATA AS (
                    SELECT DISTINCT 
                        SUBSTR("DEALER_CODE", 3, 8) AS sap_id, 
                        "PROD_REQD_DT" AS prod_reqd_dt,
                        "INDENT_NO" AS indent_no
                    FROM 
                        "IMS_SAP"."INDENT_REQUEST"
                    WHERE 
                        "PROD_REQD_DT" < CURRENT_DATE
                        AND "TRUCK_REGNO" IS NULL
                        AND "CANCEL_INDENT" IS NULL
                        AND "VALID_INDENT" IN ('Y', 'H')
                        AND SUBSTR("DEALER_CODE", 11, 7) = '7000111'
                ),
                ALERT_DATA AS (
                    SELECT DISTINCT ON (sap_id, 
                        "indent_no", 
                        "terminal_plant_id")
                        sap_id, 
                        "indent_no", 
                        "terminal_plant_id",
                        dry_out_in_days, 
                        "indent_status",
                        TRUE AS dried_out
                    FROM 
                        "alerts"
                    WHERE
                        alert_status != 'Close' AND indent_status NOT IN ('Cancelled', 'Completed') {where_clause}
                ),
                COMBINED_DATA AS (
                    SELECT 
                        i.sap_id, 
                        a.terminal_plant_id, 
                        i.indent_no, 
                        i.prod_reqd_dt,
                        NOW() AT TIME ZONE 'Asia/Kolkata' AS reported_date,
                        a.dry_out_in_days, 
                        a.dried_out,
                        a.indent_status
                    FROM 
                        INDENT_DATA i
                    LEFT JOIN 
                        ALERT_DATA a
                    ON 
                        i.sap_id::TEXT = a.sap_id::TEXT AND TRIM(i.indent_no::TEXT) = TRIM(a.indent_no::TEXT)
                    {combined_query}
                )
                SELECT 
                    cd.sap_id, 
                    cd.terminal_plant_id, 
                    cd.indent_no, 
                    cd.prod_reqd_dt, 
                    cd.reported_date, 
                    cd.dry_out_in_days, 
                    cd.dried_out, 
                    d."CATEGORY1" AS category,
                    cd.indent_status
                FROM 
                    COMBINED_DATA cd
                LEFT JOIN 
                    "IMS_SAP"."DEALER_DETAILS_CATA" d
                ON 
                    d."DEALER_CODE" = cd.sap_id
                {cd_query}
                ORDER BY 
                    cd.sap_id;"""

    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get("hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    data = await function(query=query)
    data = pd.DataFrame(data)
    for key in ['dry_out_in_days', 'indent_no', 'category']:
        if key in data.columns:
            data[key] = data[key].fillna("").astype(str)

    if not insert_to_db:
        return data.to_dict(orient="records")

    for each_record in data.to_dict(orient="records"):
        await hpcl_ceg_model.CarryFwdIndentCreate(**each_record).create()
    return


async def ro_not_in_ims():
    query = f"""SELECT DISTINCT a.rosapcode
                FROM "HPCL_HOS".sch_inventory_forecast_dashboard a
                WHERE a.rosapcode NOT IN (
                    SELECT DISTINCT SUBSTR("DEALER_CODE", 3, 8)
                    FROM "IMS_SAP"."INDENT_REQUEST"
                );"""
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get("hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    data = await function(query=query)
    data = pd.DataFrame(data)
    redis_cli = await urdhva_base.redispool.get_redis_connection()
    locations = {key.decode(): json.loads(value.decode())
                 for key, value in (await redis_cli.hgetall('location_master')).items()}
    conditions = await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)
    rosapcodes = data['rosapcode'].unique().tolist()
    plants = []
    for rec in conditions:
        if rec['key'] == 'sap_id':
            plants = [rec['value']] if isinstance(rec['value'], str) else rec['value']
            break
    if plants:
        allowed_dealers = []
        for dealer in rosapcodes:
            if f'RO_{dealer}' in locations and locations[f'RO_{dealer}'].get('terminal_plant_id', '') in plants:
                if f'RO_{dealer}' in locations.keys():
                    allowed_dealers.append({dealer: locations[f'RO_{dealer}'].get("name", "")})
                else:
                    allowed_dealers.append({dealer: ""})
        return allowed_dealers
    else:
        sap_code = []
        for dealer in rosapcodes:
            if f'RO_{dealer}' in locations.keys():
                sap_code.append({dealer: locations[f'RO_{dealer}'].get("name", "")})
            else:
                sap_code.append({dealer: ""})
        return sap_code

async def _generate_where_clause(where_clause):
    # where_clause = ["interlock_name = 'Dry Out Each Indent Wise MainFlow'"]
    where_clause.extend(await hpcl_ceg_model.Alerts.get_clause_conditions(
        extra_key_mapping={"sap_id": "terminal_plant_id"}))
    for record in where_clause:
        if record['key'] == "progress_rate":
            if record['value']:
                where_clause.append(f"progress_rate={int(record['value'][0])}")
        else:
            if record['value']:
                if record['key'] == 'dry_out_in_days':
                    dry_out_in_days_query = record['value'][0]
                if record['key'] == "plant":
                    record['key'] = "terminal_plant_id"
                if len(record['value']) == 1:
                    where_clause.append(f"{record['key']}='{record['value'][0]}'")
                else:
                    where_clause.append(f"{record['key']} in {tuple(record['value'])}")
    conditions = ' AND '.join(where_clause)
    return conditions

async def _get_ims_day_wise_report(report_date: str):
    query = f"""SELECT 
                    ir.LOCN_CODE,
                    ir.INDENT_NO,
                    ir.INDENT_DATE,
                    ir.PROD_REQD_DT,
                    ir.DEALER_CODE,
                    ir.BATCH_FLAG,
                    ir.TRUCK_REGNO,
                    ir.VALID_INDENT,
                    ir.SEND_TO_JDE_TIME,
                    ir.DELIVERY_DATE,
                    ir.INDENT_HOLD_RELEASE_TIME,
                    ir.INDENT_EXECUTABLE_TIME,
                    ip.PROD,
                    ip.QTY,
                    ip.PROD_ALLOT_TIME,
                    ip.SALES_ORDERNO,
                    ip.INVOICE_NO,
                    ip.JDE_TRUCK_NO,
                    tse.LOADED_ON,
                    tse.CARD_STATUS,
                    ROW_NUMBER() OVER (
                            PARTITION BY COALESCE(ir."LOCN_CODE"::TEXT, ''), 
                                         COALESCE(ir."INDENT_NO"::TEXT, ''), 
                                         COALESCE(ir."DEALER_CODE"::TEXT, ''), 
                                         COALESCE(ip."PROD"::TEXT, '') 
                            ORDER BY tse."LOADED_ON" ASC
                        ) AS rn
                FROM 
                    (
                        SELECT * FROM "IMS_SAP"."INDENT_REQUEST" WHERE PROD_REQD_DT = TO_DATE('{report_date}', 'YYYY-MM-DD')
                    ) AS ir
                LEFT JOIN 
                    "IMS_SAP"."INDENT_PRODUCTS" ip
                ON 
                    ir.LOCN_CODE = ip.LOCN_CODE
                    AND ir.DEALER_CODE = ip.DEALER_CODE
                    AND ir.INDENT_NO = ip.INDENT_NO
                LEFT JOIN 
                    "IMS_SAP"."TRUCK_SWIPE_ENTRY_SAP" tse
                ON 
                    ir.LOCN_CODE = tse.LOCN_CODE
                    AND ir.TRUCK_REGNO = tse.TRUCK_REGNO
                    AND tse.CARD_STATUS = 'O'
                    AND tse."LOADED_ON" >= ir."PROD_REQD_DT"
                    AND tse."LOADED_ON" <= ir."PROD_REQD_DT" + INTERVAL '1 day'
                WHERE
                    cd.rn = 1
                    AND ir.PROD_REQD_DT = TO_DATE('{report_date}', 'YYYY-MM-DD') 
                ORDER BY 
                    ir.INDENT_NO"""
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "ims", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    stats_resp = await function(
        query=query
    )
    stats_resp = pd.DataFrame(stats_resp)
    stats_resp = stats_resp.drop_duplicates(subset=["LOCN_CODE", "INDENT_NO", "DEALER_CODE", "PROD"], keep='first')
    return stats_resp.to_dict(orient='records')

async def get_custom_timestamp():
    now = datetime.datetime.now()
    # If minutes are less than 10, take the previous hour
    if now.minute < 10:
        adjusted_time = now - datetime.timedelta(hours=1)
    else:
        adjusted_time = now
    # Format as YYMMDD-HH00
    timestamp = adjusted_time.strftime("%y%m%d-%H00")

    return timestamp

async def _get_dry_out_ims_report(dry_out_in_days=['1']):
    dry_out_in_days = "', '".join(x for x in dry_out_in_days)
    date_time = await get_custom_timestamp()
    query = f"""WITH CombinedData AS (
                    SELECT 
                        ir."LOCN_CODE",
                        ir."INDENT_NO",
                        ir."INDENT_DATE",
                        ir."PROD_REQD_DT",
                        ir."DEALER_CODE",
                        ir."BATCH_FLAG",
                        ir."TRUCK_REGNO",
                        ir."VALID_INDENT",
                        ir."SEND_TO_JDE_TIME",
                        ir."DELIVERY_DATE",
                        ir."INDENT_HOLD_RELEASE_TIME",
                        ir."INDENT_EXECUTABLE_TIME",
                        ip."PROD" AS "PRODUCT_CODE",
                        ip."QTY",
                        ip."PROD_ALLOT_TIME",
                        ip."SALES_ORDERNO",
                        ip."INVOICE_NO",
                        ip."JDE_TRUCK_NO",
                        tse."LOADED_ON",
                        ROW_NUMBER() OVER (
                            PARTITION BY ir."LOCN_CODE", ir."INDENT_NO", ir."DEALER_CODE", ip."PROD"
                            ORDER BY tse."LOADED_ON" ASC NULLS LAST
                        ) AS rn
                    FROM 
                        "IMS_SAP"."INDENT_REQUEST" ir
                    LEFT JOIN 
                        (select * from "IMS_SAP"."INDENT_PRODUCTS" where substr(run_id, 1, 6) = '{date_time[:6]}') as ip
                    ON 
                        COALESCE(ir."LOCN_CODE"::TEXT, '') = COALESCE(ip."LOCN_CODE"::TEXT, '')
                        AND COALESCE(ir."DEALER_CODE"::TEXT, '') = COALESCE(ip."DEALER_CODE"::TEXT, '')
                        AND COALESCE(ir."INDENT_NO"::TEXT, '') = COALESCE(ip."INDENT_NO"::TEXT, '')
                    LEFT JOIN 
                        (select * from "IMS_SAP"."TRUCK_SWIPE_ENTRY_SAP" where substr(run_id, 1, 6) = '{date_time[:6]}') as tse 
                    ON 
                        COALESCE(ir."LOCN_CODE"::TEXT, '') = COALESCE(tse."LOCN_CODE"::TEXT, '')
                        AND COALESCE(ir."TRUCK_REGNO"::TEXT, '') = COALESCE(tse."TRUCK_REGNO"::TEXT, '')
                        AND tse."CARD_STATUS" = 'O'
                        AND tse."LOADED_ON" >= ir."PROD_REQD_DT"
                        AND tse."LOADED_ON" BETWEEN ir."PROD_REQD_DT" AND (ir."PROD_REQD_DT" + INTERVAL '1 day')
                ),
                SalesData AS (
                    SELECT 
                        rosapcode, 
                        CASE
                            WHEN item_name = 'HSD' THEN '2812000'
                            WHEN item_name = 'MS' THEN '2811000'
                            WHEN item_name = 'TURBO' THEN '3912000'
                            WHEN item_name = 'E20' THEN '2822000'
                            WHEN item_name = 'POWER 95' THEN '3672000'
                            WHEN item_name = 'POWER 99' THEN '2816000'
                            WHEN item_name = 'POWER 100' THEN '3373000'
                            ELSE NULL
                        END AS item_name_code,
                        avgsales_7days
                    
                    FROM "HPCL_HOS"."sch_inventory_forecast_dashboard"
                    WHERE run_id = '{date_time}'
                )
                SELECT 
                    a.zone as "ZONE",
                    a.region as "REGION",
                    a.sales_area as "SALES_AREA",
                    a.sap_id as "SAP_ID",
                    a.location_name as "LOCATION_NAME",
                    a.terminal_plant_id as "TERMINAL_PLANT_ID",
                    a.indent_no as "INDENT_NO",
                    a.product_code as "PRODUCT_CODE",
                    a.indent_status as "INDENT_STATUS",
                    a.dry_out_in_days as "DRY_OUT_IN_DAYS",
                    cd."LOCN_CODE" AS "ASSIGNED_TO_LOCN",
                    cd."PROD_REQD_DT",
                    cd."TRUCK_REGNO",
                    cd."VALID_INDENT",
                    cd."SEND_TO_JDE_TIME",
                    cd."DELIVERY_DATE",
                    cd."INDENT_HOLD_RELEASE_TIME",
                    cd."INDENT_EXECUTABLE_TIME",
                    cd."QTY",
                    cd."PROD_ALLOT_TIME",
                    cd."SALES_ORDERNO",
                    cd."INVOICE_NO",
                    cd."LOADED_ON",
                    sd.avgsales_7days as "AVGSALES_7DAYS"
                FROM 
                    (SELECT sap_id, indent_no, product_code, zone, region, sales_area, location_name, terminal_plant_id, indent_status, dry_out_in_days
                     FROM alerts 
                     WHERE interlock_name = 'Dry Out Each Indent Wise MainFlow'
                     AND indent_status NOT IN ('Cancelled', 'Completed')
                     AND dry_out_in_days IN ('{dry_out_in_days}')) a
                LEFT JOIN 
                    CombinedData cd
                ON 
                    COALESCE(substr(cd."DEALER_CODE", 3, 8)::TEXT, '') = COALESCE(a.sap_id::TEXT, '')
                    AND COALESCE(cd."INDENT_NO"::TEXT, '') = COALESCE(a.indent_no::TEXT, '')
                    AND COALESCE(cd."PRODUCT_CODE"::TEXT, '') = COALESCE(a.product_code::TEXT, '')
                LEFT JOIN 
                    SalesData sd
                ON 
                    COALESCE(a.sap_id::TEXT, '') = COALESCE(sd.rosapcode::TEXT, '')
                    AND COALESCE(a.product_code::TEXT, '') = COALESCE(sd.item_name_code::TEXT, '')
                WHERE 
                    cd.rn = 1 or cd.rn is null
                ORDER BY 
                    a.indent_no desc;"""
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    stats_resp = await function(
        query=query
    )
    stats_resp = pd.DataFrame(stats_resp)
    stats_resp['DRY_OUT_IN_DAYS'] = stats_resp['DRY_OUT_IN_DAYS'].fillna("").astype(str)
    stats_resp.replace({"DRY_OUT_IN_DAYS": {"1": "DRY_OUT", "2": "INTRA_DAY_DRY_OUT"}}, inplace=True)
    stats_resp.replace({"VALID_INDENT": {"H": "ON_HOLD_RELEASED", "Y": "VALID_INDENT", "N": "ON_HOLD"}}, inplace=True)
    stats_resp['PROD_REQD_DT'] = stats_resp['PROD_REQD_DT'].dt.strftime("%Y-%m-%d %H:%M:%S")
    stats_resp['SEND_TO_JDE_TIME'] = stats_resp['SEND_TO_JDE_TIME'].dt.strftime("%Y-%m-%d %H:%M:%S")
    stats_resp['DELIVERY_DATE'] = stats_resp['DELIVERY_DATE'].dt.strftime("%Y-%m-%d %H:%M:%S")
    stats_resp['INDENT_HOLD_RELEASE_TIME'] = stats_resp['INDENT_HOLD_RELEASE_TIME'].dt.strftime("%Y-%m-%d %H:%M:%S")
    stats_resp['INDENT_EXECUTABLE_TIME'] = stats_resp['INDENT_EXECUTABLE_TIME'].dt.strftime("%Y-%m-%d %H:%M:%S")
    stats_resp['PROD_ALLOT_TIME'] = stats_resp['PROD_ALLOT_TIME'].dt.strftime("%Y-%m-%d %H:%M:%S")
    stats_resp['LOADED_ON'] = stats_resp['LOADED_ON'].dt.strftime("%Y-%m-%d %H:%M:%S")
    stats_resp = stats_resp.fillna("")
    return stats_resp.to_dict(orient='records')


async def _get_on_hold_data(dry_out_in_days='1'):
    where_clause = {
        "a.interlock_name": ["Dry Out Each Indent Wise MainFlow"],
        "a.progress_rate": ["2"],
        "a.dry_out_in_days": [dry_out_in_days]
    }
    conditions = _generate_where_clause(where_clause)
    stats_query = f"""SELECT 
                            a.sap_id,
                            a.indent_no,
                            a.product_code,
                            a.progress_rate AS present_stage,
                            ir."PROD_REQD_DT",
                            ir."VALID_INDENT",
                            ir."INDENT_HOLD_RELEASE_TIME",
                            ir."INDENT_EXECUTABLE_TIME",
                            ir."CANCEL_INDENT"
                        FROM 
                            alerts a
                        JOIN 
                            "IMS_SAP"."INDENT_REQUEST" ir 
                        ON 
                            a.sap_id::TEXT = SUBSTR(ir."DEALER_CODE", 3, 8)::TEXT
                            AND a.indent_no::TEXT = ir."INDENT_NO"::TEXT
                            AND ir."CANCEL_INDENT" IS NULL
                        WHERE 
                            {conditions}
                            AND a.indent_status NOT IN ('Cancelled', 'Completed')
                        order by a.sap_id"""
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get("hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    stats_resp = await function(
        query=stats_query
    )
    stats_resp = pd.DataFrame(stats_resp)
    return stats_resp.to_dict(orient='records')


async def _get_pending_indents(dry_out_in_days='1'):
    where_clause = {
        "a.interlock_name": ["Dry Out Each Indent Wise MainFlow"],
        "a.progress_rate": ["3"],
        "a.dry_out_in_days": [dry_out_in_days]
    }


async def constant_dryout_ros(days=7):
    now = datetime.datetime.now()
    run_id = [
        (now - datetime.timedelta(days=i)).strftime('%y%m%d-2300') for i in range(1, days+1)
    ]
    run_ids = tuple(run_id)
    print(run_ids)
    query = f"""
    WITH forecast_dashboard AS (
        SELECT
            site_id,
            fcc_code,
            rosapcode,
            run_id,
            COUNT(DISTINCT tank_no) AS tank_cnt,
            STRING_AGG(CAST(tank_no AS TEXT), ',') AS tank_no,
            CASE
                WHEN SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) <= 0 THEN 1
                WHEN SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) < (SUM(sch.avgsales_7days) / 7) THEN 2
                WHEN SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) >= (SUM(sch.avgsales_7days) / 7)
                     AND SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) <= (SUM(sch.avgsales_7days) / 7) * 3 THEN 3
                WHEN SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) > (SUM(sch.avgsales_7days) / 7) * 3
                     AND SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) <= (SUM(sch.avgsales_7days) / 7) * 6 THEN 4
                ELSE 6
            END AS newstatus
        FROM "HPCL_HOS".sch_inventory_forecast_dashboard AS sch
        WHERE run_id IN {run_ids}
        GROUP BY site_id, fcc_code, rosapcode, run_id
        ORDER BY run_id, site_id, fcc_code, rosapcode
    )
    SELECT *
    FROM forecast_dashboard
    WHERE newstatus = 1
    """

    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    stats_resp = await function(
        query=query
    )
    df = pl.DataFrame(stats_resp)
    df = df.with_columns(
        pl.col("run_id")
        .str.slice(0, 6)
        .str.strptime(pl.Date, format="%y%m%d")
        .alias("run_id_date")
    )
    print("days: ", days)
    aggregated_df = df.group_by("rosapcode").agg(
        pl.col("run_id_date").n_unique().alias("unique_days_count")
    )

    filtered_df = aggregated_df.filter(
        pl.col("unique_days_count") == days
    )
    data = df.join(filtered_df.select("rosapcode"), on="rosapcode", how="inner")
    redis_cli = await urdhva_base.redispool.get_redis_connection()
    locations = {key.decode(): json.loads(value.decode())
                 for key, value in (await redis_cli.hgetall('location_master')).items()}
    loc_data = [value for key, value in locations.items()]
    locations_data = pl.DataFrame(loc_data)
    result = data.join(locations_data.select(["sap_id", "name"]).unique(subset="sap_id", keep='first'), left_on = "rosapcode", right_on = "sap_id", how = "left")
    print('printing columns')
    print(result.columns)
    return result.select(["rosapcode", "name"]).to_dicts()


async def current_month_frequent_dryout_ros(data):
    datetime_condition = ""
    if data.start_date and data.end_date:
        datetime_condition = f" AND workflow_datetime BETWEEN '{data.start_date}' AND '{data.end_date}' "

    where_condition = ''' interlock_name = 'Dry Out Each Indent Wise MainFlow'
                                AND location_name != '' AND  indent_status != 'Cancelled' 
                                AND (workflow_datetime >= DATE_TRUNC('month', CURRENT_DATE)
                                    AND workflow_datetime < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
                            ) ''' + datetime_condition

    dry_out_query = f'''WITH unique_sap_ids AS (
                              SELECT location_name, sap_id, DATE(workflow_datetime) AS workflow_date
                              FROM alerts
                              WHERE {where_condition}
                              GROUP BY location_name, sap_id, DATE(workflow_datetime)
                            ),
                            monthly_sap_count AS (
                              SELECT location_name, sap_id, COUNT(sap_id) AS total_count
                              FROM unique_sap_ids
                              GROUP BY location_name, sap_id
                            )
                            SELECT location_name, sap_id, SUM(total_count) AS "Total_Count"
                            FROM monthly_sap_count
                            WHERE total_count > 1
                            GROUP BY location_name, sap_id
                            ORDER BY "Total_Count" DESC '''

    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    dryout_resp = await function(
        query=dry_out_query
    )

    return dryout_resp


async def current_month_frequent_drout_terminals(data):
    datetime_condition = ""
    if data.start_date and data.end_date:
        datetime_condition = f" AND workflow_datetime BETWEEN '{data.start_date}' AND '{data.end_date}' "

    where_condition = ''' interlock_name = 'Dry Out Each Indent Wise MainFlow'
                                    AND location_name != '' AND  indent_status != 'Cancelled' 
                                    AND (workflow_datetime >= DATE_TRUNC('month', CURRENT_DATE)
                                        AND workflow_datetime < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
                                    AND category != ''
                                ) ''' + datetime_condition

    dry_out_query = f'''WITH unique_terminal_plant_ids AS (
                          SELECT location_name, terminal_plant_id, category, DATE(workflow_datetime) AS workflow_date
                          FROM alerts
                          WHERE {where_condition}
                          GROUP BY location_name, terminal_plant_id, category, DATE(workflow_datetime)
                        ),
                        monthly_sap_count AS (
                          SELECT location_name, terminal_plant_id, category, COUNT(terminal_plant_id) AS total_count
                          FROM unique_terminal_plant_ids
                          GROUP BY location_name, terminal_plant_id, category
                        )
                        SELECT location_name, terminal_plant_id, category, SUM(total_count) AS "Total_Count"
                        FROM monthly_sap_count
                        WHERE total_count > 1
                        GROUP BY location_name, terminal_plant_id, category
                        ORDER BY "Total_Count" DESC '''

    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    dryout_resp = await function(
        query=dry_out_query
    )
    return dryout_resp

async def get_atg_ack(sap_id: str, product_code: str):
    to_day = datetime.datetime.now().strftime("%Y-%m-%d")
    query = f"""select Site_id, (select erp_code from "HPCL_HOS".ms_site ms where ms.site_id = trd.site_id) as "sap_ro_code", Tank_no, Product_no, Recptentrydate """ \
            f"""from "HPCL_HOS".tr_delivery_data trd where enable = true and net_volume > 0 """ \
            f"""and sap_ro_code = '{sap_id}' and "Product_no" = '{product_code}' """ \
            f"""and Recptentrydate::DATE = '{to_day}'"""
    query = f"""
        SELECT trd.Site_id, 
               ms.erp_code AS sap_ro_code, 
               trd.Tank_no, 
               trd.Product_no, 
               trd.Product_no as item_name,
               trd.Recptentrydate
        FROM "HPCL_HOS".tr_delivery_data trd
        JOIN "HPCL_HOS".ms_site ms 
            ON trd.site_id = ms.site_id
        WHERE trd.enable = true 
            AND trd.net_volume > 0
            AND ms.erp_code = '{sap_id}'
--             AND trd.Product_no = '{product_code}'
            AND trd.Recptentrydate::DATE = '{to_day}'
    """
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "cris", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    atg_resp = await function(
        query=query
    )
    print("atg_resp: ", atg_resp)
    atg_resp = pd.DataFrame(atg_resp)
    if 'item_name' in atg_resp.columns:
        atg_resp['item_name'] = atg_resp['item_name'].astype(str)
    atg_resp.replace({"item_name": await cris_product_mapping()}, inplace=True)
    print("atg_resp: ", atg_resp)

    # query = f"""select distinct sap_id from alerts where interlock_name = 'Dry Out Each Indent Wise MainFlow' and alert_status = 'Open' and dry_out_in_days = '{dry_out_in_days}'"""
    # dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
    #     "hpcl_ceg", "1")
    # dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    # function = await charts_actions.charts_connection_vault_routing(
    #     dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    # resp = await function(
    #     query=query
    # )
    # alert_df = pd.DataFrame(resp)
    #
    # df = pd.merge(
    #     atg_ack_df.drop_duplicates(subset="sap_ro_code"), alert_df,
    #     left_on=["sap_ro_code"], right_on=["sap_id"], how="inner")
    if atg_resp.empty:
        return []
    atg_resp = atg_resp[atg_resp['item_name'] == product_code]
    print("atg_resp: ", atg_resp)
    return atg_resp.to_dict(orient='records')

async def update_dry_out_from_cris(records):
    records = pd.DataFrame(records)
    records["product_code"] = records["product_grp"].replace(product_code_mapping)
    records = records.astype(str)

    query = f"""select sap_id as rosapcode, product_code from alerts where interlock_name = 'Dry Out Each Indent Wise MainFlow' and alert_status != 'Close' and dry_out_in_days in ('1','2')"""
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    dryout_resp = await function(
        query=query
    )
    dryout_resp = pd.DataFrame(dryout_resp)
    dryout_resp = dryout_resp.astype(str)
    dryout_resp = dryout_resp.drop_duplicates(subset=["rosapcode", "product_code"])

    final_resp = pd.merge(
        records, dryout_resp,
        left_on=["rosapcode", "product_code"],
        right_on=["rosapcode", "product_code"],
        how='outer', indicator=True
    )
    right_df = final_resp[final_resp['_merge'] == 'right_only']
    print(right_df)
    for right in right_df.to_dict(orient='records'):
        query = f"""update alerts set mark_as_false=false where alert_status != 'Close' and sap_id = '{right["rosapcode"]}' and product_code = '{right["product_code"]}' and interlock_name = 'Dry Out Each Indent Wise MainFlow'"""
        await hpcl_ceg_model.Alerts.update_by_query(query)

    for both in final_resp[final_resp['_merge'] == 'both'].to_dict(orient='records'):
        query = f"""update alerts set mark_as_false=true where alert_status != 'Close' and sap_id = '{both["rosapcode"]}' and product_code = '{both["product_code"]}' and interlock_name = 'Dry Out Each Indent Wise MainFlow'"""
        await hpcl_ceg_model.Alerts.update_by_query(query)

async def update_atg_ack(alert_id: str, sap_id: str, product_code: str):
    print(f"alert_id: {alert_id} sap_id: {sap_id} product_code: {product_code}")
    alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
    if not isinstance(alert_data, dict):
        alert_data = alert_data.__dict__

    atg_resp = await get_atg_ack(sap_id=sap_id, product_code=product_code)
    if atg_resp:
        atg_resp = atg_resp[0]
        if not alert_data.get("atg_ack", False):
            query = f"""update alerts set atg_ack=true, atg_ack_time='{atg_resp.get("recptentrydate").strftime("%Y-%m-%d %H:%M:%S")}' where id = {alert_id}"""
            print(f"update query for atg: {query}")
            await hpcl_ceg_model.Alerts.update_by_query(query)

async def get_atg_ack_count(dry_out_in_days='1'):
    to_day = urdhva_base.utilities.get_present_time().strftime("%Y-%m-%d")
    query = (f"select count(distinct sap_id) from alerts where interlock_name = 'Dry Out Each Indent Wise MainFlow' "
             f"and dry_out_in_days='{dry_out_in_days}' and atg_ack=true and atg_ack_time::DATE = '{to_day}'")
    data = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=10000)
    print("Data: ", data)
    if data.get("data", []):
        data = data.get("data", [])
        return data[0].get("count", 0)
    return 0

async def cris_product_mapping():
    product_mapping = {
        "3672000": "POWER 95",
        "2821000": "MS",
        "3925000": "POWER 95",
        "2812000": "HSD",
        "3373000": "POWER 100",
        "1683000": "HSD",
        "4211000": "MS",
        "1322100": "POWER 95",
        # "2822000": "E20",
        "2822000": "MS",
        "1683100": "TURBO",
        "1322000": "MS",
        "2823000": "MS",
        "2682000": "POWER 99",
        "2811000": "MS",
        "3912000": "TURBO",
        "2816000": "POWER 99"
    }
    return product_mapping

async def dry_out_diff():
    cris_query = f'''select site_id, fcc_code, item_name,item_name product_grp, rosapcode, tank_no, status, tank_cnt
                        from (
                                select site_id, fcc_code,product_grp item_name,count(distinct tank_no) tank_cnt, 
                                rosapcode, STRING_AGG(CAST(tank_no AS TEXT), ',') tank_no,
                                case when sum(case when pumpable_Stock>=0 then pumpable_Stock else 0 end) <=0 then 1 
                                when sum(case when pumpable_Stock>=0 then pumpable_Stock else 0 end) < 
                                (sum(sch.avgsales_7days)/7) then 2
                                when sum(case when pumpable_Stock>=0 then pumpable_Stock else 0 end) >= 
                                (sum(sch.avgsales_7days)/7) and sum(case when pumpable_Stock>=0 
                                then pumpable_Stock else 0 end) <= (sum(sch.avgsales_7days)/7)*3 then 3
                                when sum(case when pumpable_Stock>=0 then pumpable_Stock else 0 end) > 
                                (sum(sch.avgsales_7days)/7)*3 and sum(case when pumpable_Stock>=0 then 
                                pumpable_Stock else 0 end) <=(sum(sch.avgsales_7days)/7)*6 then 4 
                                else 5 end status
                                from "HPCL_HOS".sch_inventory_forecast_dashboard sch
                                where sch.volume>0
                                group by site_id, fcc_code, product_grp,rosapcode
                                order by site_id, fcc_code, product_grp
                            ) result1
                            where result1.status in ('1', '2')
            '''
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "cris", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    cris_resp = await function(
        query=cris_query
    )

    novex_query = (f"select bu, sap_id, sop_id, id, product_code, indent_no, dealer_id, workflow_instance_id, workflow_datetime, dry_out_in_days, "
                   f"mark_as_false from alerts where interlock_name = 'Dry Out Each Indent Wise MainFlow' and alert_status != 'Close'")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    novex_resp = await function(
        query=novex_query
    )

    cris_resp = pd.DataFrame(cris_resp)
    novex_resp = pd.DataFrame(novex_resp)
    novex_resp.replace({"product_code": await cris_product_mapping()}, inplace=True)

    cris_resp = cris_resp.astype(str)
    novex_resp = novex_resp.astype(str)
    cris_resp = cris_resp.drop_duplicates(subset=['item_name', 'rosapcode', 'status'])
    novex_resp = novex_resp.drop_duplicates(subset=['product_code', 'sap_id', 'dry_out_in_days'])

    resp = pd.merge(
        cris_resp, novex_resp,
        left_on=['item_name', 'rosapcode', 'status'],
        right_on=['product_code', 'sap_id', 'dry_out_in_days'],
        how='outer',
        indicator=True
    )
    resp = resp[resp['_merge'] != 'both']
    resp.to_csv("/tmp/dryout_difference.csv", index=False)
    return resp

async def dry_out_report(dry_out_in_days='1'):
    alerts_query = f"""
            SELECT sap_id, indent_no, product_code, zone, region, sales_area, 
                   location_name, terminal_plant_id, indent_status, dry_out_in_days
            FROM alerts 
            WHERE interlock_name = 'Dry Out Each Indent Wise MainFlow'
            AND indent_status NOT IN ('Cancelled', 'Completed')
            AND dry_out_in_days = '{dry_out_in_days}';
            """
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    alerts_resp = await function(
        query=alerts_query
    )
    alerts_resp = pd.DataFrame(alerts_resp)

    query_combined = f"""
                    SELECT ir."LOCN_CODE", ir."INDENT_NO", ir."PROD_REQD_DT", ir."DEALER_CODE", 
                           ir."TRUCK_REGNO", ip."PROD" AS "PRODUCT_CODE", ip."QTY",
                           tse."LOADED_ON"
                    FROM (select * from "IMS_SAP"."INDENT_REQUEST" where substr(run_id, 1, 6) = '250317') ir
                    LEFT JOIN (select * from "IMS_SAP"."INDENT_PRODUCTS" where substr(run_id, 1, 6) = '250317') ip
                        ON ir."LOCN_CODE" = ip."LOCN_CODE"
                        AND ir."DEALER_CODE" = ip."DEALER_CODE"
                        AND ir."INDENT_NO" = ip."INDENT_NO"
                        AND substr(ip.run_id, 1, 6) = %s
                    LEFT JOIN (select * from "IMS_SAP"."TRUCK_SWIPE_ENTRY_SAP" where substr(run_id, 1, 6) = '250317') tse
                        ON ir."LOCN_CODE" = tse."LOCN_CODE"
                        AND ir."TRUCK_REGNO" = tse."TRUCK_REGNO"
                        AND tse."CARD_STATUS" = 'O'
                        AND substr(tse.run_id, 1, 6) = %s;
                    """

    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    combined_resp = await function(
        query=query_combined
    )
    combined_resp = pd.DataFrame(combined_resp)

    query_sales = """
                    SELECT rosapcode, 
                           CASE item_name
                               WHEN 'HSD' THEN '2812000'
                               WHEN 'MS' THEN '2811000'
                               WHEN 'TURBO' THEN '3912000'
                               WHEN 'E20' THEN '2822000'
                               WHEN 'POWER 95' THEN '3672000'
                               WHEN 'POWER 99' THEN '2816000'
                               WHEN 'POWER 100' THEN '3373000'
                           END AS item_name_code,
                           avgsales_7days
                    FROM "HPCL_HOS"."sch_inventory_forecast_dashboard"
                    WHERE run_id = '250317';
                    """
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    sales_resp = await function(
        query=query_sales
    )
    sales_resp = pd.DataFrame(sales_resp)

    final_df = alerts_resp.merge(
        combined_resp,
        left_on=['sap_id', 'indent_no', 'product_code'],
        right_on=['DEALER_CODE', 'INDENT_NO', 'PRODUCT_CODE'],
        how='left'
    ).merge(
        sales_resp,
        left_on=['sap_id', 'product_code'],
        right_on=['rosapcode', 'item_name_code'],
        how='left'
    )
    final_df = final_df.sort_values(by="LOADED_ON", ascending=True).groupby("INDENT_NO").first().reset_index()
    print(final_df)
    return final_df.to_dict(orient="records")

async def get_dryout_aging(conditions):
    query = f"""WITH distinct_alerts AS (
                SELECT DISTINCT ON (sap_id) sap_id, created_at
                FROM alerts
                WHERE {conditions} AND progress_rate = '1'
                ORDER BY sap_id, created_at ASC
            )
            SELECT 
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '2 days' THEN 1 END) AS "less_than_2_days",
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '7 days' AND created_at < NOW() - INTERVAL '2 days' THEN 1 END) AS "from_3_to_7_days",
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '15 days' AND created_at < NOW() - INTERVAL '7 days' THEN 1 END) AS "from_8_to_15_days",
                COUNT(CASE WHEN created_at < NOW() - INTERVAL '15 days' THEN 1 END) AS "more_than_15_days"
            FROM distinct_alerts;"""
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    resp = await function(
        query=query
    )
    print("resp: ", resp)
    return resp[0] if resp else {}

async def get_ro_count_less_50(condition):
    query = (f"SELECT SUBSTRING(CUST_CD, 3) AS CUST_CD, SUM(QTY_KL) AS Total_Net_Weight "
             f"FROM PS.EDW_PRIMARY_SALES_FACT "
             f"WHERE "
             f"INVOICE_DT >= CURDATE() - INTERVAL 30 DAY "
             f"GROUP BY CUST_CD "
             f"HAVING Total_Net_Weight < 50;")
    creds = credential_loader.get_credentials('TIBCO')
    params = {
        "host": creds['host'],
        "database": creds['database'],
        "user": creds['user'],
        "password": creds['password'],
        "port": creds['port'],
        "connection_type": "mssql"
    }
    conn = get_db_connection(params)
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    data = pd.DataFrame.from_records(data, columns=columns)
    data['CUST_CD'] = data['CUST_CD'].astype(str)

    query = f"select distinct on (sap_id) sap_id, created_at from alerts where {condition} and progress_rate = '1' order by sap_id, created_at asc"
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    resp = await function(
        query=query
    )
    resp = pd.DataFrame(resp)
    resp['sap_id'] = resp['sap_id'].astype(str)

    resp = pd.merge(
        data.drop_duplicates(subset=['CUST_CD']),
        resp.drop_duplicates(subset=['sap_id']),
        left_on=['CUST_CD'], right_on=['sap_id'],
        how='left', indicator=True
    )
    return len(resp[resp['_merge'] == 'both'])

def get_db_connection(params):
    """
    Establish a database connection
    Args:
        connection_string (str): Database connection string
    Returns:
        pyodbc connection
    """
    connection = mysql.connector.connect(
        host=params['host'],
        user=params['user'],
        passwd=params["password"],
        port=params["port"]
        #database=database
    )
    return connection

async def get_tar_analysis(condition):
    query = (f"SELECT DISTINCT ON (rosapcode) "
             f"rosapcode, "
             f"exposure, "
             f"CASE "
             f"WHEN exposure < 0 THEN 1 "
             f"WHEN exposure >= 0 AND exposure <= 5000000 THEN 2 "
             f"WHEN exposure > 5000000 AND exposure <= 7500000 THEN 3 "
             f"ELSE 4 "
             f"END AS category "
             f"""FROM "HPCL_HOS".customer_balance;""")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "cris", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    cust_resp = await function(
        query=query
    )
    cust_resp = pd.DataFrame(cust_resp)
    cust_resp['rosapcode'] = cust_resp['rosapcode'].astype(str)

    query = f"select distinct on (sap_id) sap_id, created_at from alerts where {condition} and progress_rate = '1' order by sap_id, created_at asc"
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    resp = await function(
        query=query
    )
    resp = pd.DataFrame(resp)
    resp['sap_id'] = resp['sap_id'].astype(str)

    resp = pd.merge(
        cust_resp.drop_duplicates(subset=['rosapcode']),
        resp.drop_duplicates(subset=['sap_id']),
        left_on=['rosapcode'], right_on=['sap_id'],
        how='left', indicator=True
    )

    _dict = {
        "less_1_cr": len(resp[(resp['_merge'] == 'both') & (resp['category'] == 1)]),
        "less_2_cr": len(resp[(resp['_merge'] == 'both') & (resp['category'] == 2)]),
        "less_5_cr": len(resp[(resp['_merge'] == 'both') & (resp['category'] == 3)]),
        "greater_5_cr": len(resp[(resp['_merge'] == 'both') & (resp['category'] == 4)])
    }
    return _dict

async def get_tt_counts(condition):
    query = f"""select truck_regnno, substr(dealer_code, 3, 8) as dealer_code from "IMS_SAP"."TRUCK_DETAILS" """
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    dealer_tt_resp = await function(
        query=query
    )
    dealer_tt_resp = pd.DataFrame(dealer_tt_resp)
    dealer_tt_resp['dealer_code'] = dealer_tt_resp['dealer_code'].fillna("")
    dealer_tt_resp['dealer_code'] = dealer_tt_resp['dealer_code'].astype(str)

    # query = f"select distinct on (sap_id) sap_id, created_at from alerts where {condition} and progress_rate = '1' order by sap_id, created_at asc"
    # dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
    #     "hpcl_ceg", "1")
    # dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    # function = await charts_actions.charts_connection_vault_routing(
    #     dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    # resp = await function(
    #     query=query
    # )
    # resp = pd.DataFrame(resp)
    # resp['sap_id'] = resp['sap_id'].astype(str)

    query = f"""WITH LatestR3 AS (
                SELECT 
                    "TRUCK_REGNO", 
                    MAX("LOADED_ON") AS last_r3_time
                FROM "IMS_SAP"."TRUCK_SWIPE_ENTRY_SAP"
                WHERE 
                    "CARD_STATUS" = 'O'
                    AND "LOADED_ON"::DATE = CURRENT_DATE
                GROUP BY "TRUCK_REGNO"
            ),
            FilteredR1 AS (
                SELECT 
                    "TRUCK_REGNO",
                    "CARD_STATUS",
                    "LOADED_ON",
                    ROW_NUMBER() OVER (
                        PARTITION BY "TRUCK_REGNO"
                        ORDER BY "LOADED_ON" DESC
                    ) AS rn
                FROM "IMS_SAP"."TRUCK_SWIPE_ENTRY_SAP" ts
                WHERE 
                    ts."CARD_STATUS" = 'R'
                    AND ts."LOADED_ON"::DATE = CURRENT_DATE
                    AND EXISTS (
                        SELECT 1 
                        FROM LatestR3 r3 
                        WHERE ts."TRUCK_REGNO" = r3."TRUCK_REGNO"
                          AND ts."LOADED_ON" > r3.last_r3_time
                    )
            )
            SELECT "TRUCK_REGNO", "CARD_STATUS", "LOADED_ON"
            FROM FilteredR1
            WHERE rn = 1;"""
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get(
        "hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    resp = await function(
        query=query
    )
    resp = pd.DataFrame(resp)
    if resp.empty:
        resp = pd.DataFrame({"TRUCK_REGNO": []})
    if dealer_tt_resp.empty:
        dealer_tt_resp = pd.DataFrame({"truck_regnno": [], "dealer_code": []})

    resp = pd.merge(
        dealer_tt_resp.drop_duplicates(subset=['truck_regnno']),
        resp.drop_duplicates(subset=['TRUCK_REGNO']),
        left_on=['truck_regnno'], right_on=['TRUCK_REGNO'],
        how='left', indicator=True
    )
    _dict = {
        "dealer_tt": len(resp[(resp['_merge'] == 'both') & (resp['dealer_code'] != '')]),
        "transport_tt": len(resp[(resp['_merge'] == 'both') & (resp['dealer_code'] == '')])
    }

    return _dict


async def retail_tar(filters, cross_filters, drill_state="", time_grain="", resp_format=""):
    # Removing extra keys like all/_empty/* to mak sure all results appear in api response
    # Filtering cross filters
    base_path = os.path.join(os.path.dirname(helpers.__file__), '..', 'orchestrator', 'masterdata')
    cross_filters = [cross_filter for cross_filter in cross_filters if not (cross_filter.get("cond") in ['=', 'equals']
                                                                            and cross_filter.get("value") and
                                                                            cross_filter["value"].lower() in ['*',
                                                                                                              '_empty',
                                                                                                              'all'])]
    # Filtering filters
    filters = [filter_cond for filter_cond in filters
               if not (filter_cond.get("cond") in ['=', 'equals'] and filter_cond.get("value") and
                       filter_cond["value"].lower() in ['*', '_empty', 'all'])]
    sales_area_df = pd.read_csv(f"{base_path}/Retail_SalesArea_mapping.csv").astype(str)
    region_df = pd.read_csv(f"{base_path}/Retail_Region_mapping.csv").astype(str)
    region_df['JDE_RO_CD'] = region_df['JDE_RO_CD'].apply(lambda x: x[0]+'0'+x[1:])
    drill_order = ["zone", "salesarea", "site_name"]

    cross_filters = cross_filters + filters
    for cond in cross_filters:
        cond['key'] = cond['key'].strip('"')
        if cond['key'] == 'region':
            df = region_df[region_df['JDE_RO_NM'] == cond['value']]
            cond['value'] = list(df['JDE_RO_CD'].values)
            cond['cond'] = 'one-off'
        elif cond['key'] == 'salesarea':
            df = sales_area_df[sales_area_df['ORG_RO_NM'] == cond['value']]
            cond['value'] = list(df['ORG_SA_CD'].values)
            cond['cond'] = 'one-off'

    clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters)
    group_by_key = "zone" if not drill_state else drill_order[drill_order.index(drill_state)+1]
    query = f''' select SUM(exposure) as amount, {group_by_key} from "HPCL_HOS".customer_balance '''
    if clause:
        if isinstance(clause, str):
            clause = [clause]
        query += f' where {" AND ".join(clause)}'
    if group_by_key:
        query += f" GROUP BY {group_by_key}"
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get("cris", "2")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    resp = await function(query=query)
    if not resp:
        return []
    df = pd.DataFrame(resp)
    df = df[df['amount'] != 0]
    if 'region' in df.columns:
        df = df.merge(region_df, how='left', left_on='region', right_on='JDE_RO_CD')
        df = df[['amount', 'JDE_RO_NM']]
        df = df.rename(columns={'JDE_RO_NM': 'region'})
        df = df.groupby("region", as_index=False).sum()
    if 'salesarea' in df.columns:
        df = df.merge(sales_area_df, how='left', left_on='salesarea', right_on='ORG_SA_CD')
        df = df[['amount', 'ORG_RO_NM']]
        df = df.rename(columns={'ORG_RO_NM': 'salesarea'})
        df = df.groupby("salesarea", as_index=False).sum()
    if not df.empty:
        df['amount'] = df['amount'].astype(int)
    return df.to_dict(orient='records')
