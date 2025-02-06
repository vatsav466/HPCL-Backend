import urdhva_base
import json
import datetime
import pandas as pd
import polars as pl
import hpcl_ceg_model
import charts_actions
import urdhva_base.redispool
import dashboard_studio_model
import utilities.helpers as helpers
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
    if bu == "TAS":
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
        bu_data_ro['name'] = bu_data_ro['name'].fillna("")
        bu_data_ro['category'] = bu_data_ro['category'].fillna("")
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
            if skip_record or not rec["region"]:
                continue
            if rec["region"]:
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
            if skip_record or not rec["sales_area"]:
                continue
            if rec["sales_area"]:
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
                        a.dried_out
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
                    d."CATEGORY1" AS category
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

async def _get_dry_out_ims_report(dry_out_in_days=['1']):
    dry_out_in_days = "', '".join(x for x in dry_out_in_days)
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
                        tse."CARD_STATUS",
                        ROW_NUMBER() OVER (
                            PARTITION BY COALESCE(ir."LOCN_CODE"::TEXT, ''), 
                                         COALESCE(ir."INDENT_NO"::TEXT, ''), 
                                         COALESCE(ir."DEALER_CODE"::TEXT, ''), 
                                         COALESCE(ip."PROD"::TEXT, '') 
                            ORDER BY tse."LOADED_ON" ASC
                        ) AS rn
                    FROM 
                        "IMS_SAP"."INDENT_REQUEST" ir
                    LEFT JOIN 
                        "IMS_SAP"."INDENT_PRODUCTS" ip
                    ON 
                        COALESCE(ir."LOCN_CODE"::TEXT, '') = COALESCE(ip."LOCN_CODE"::TEXT, '')
                        AND COALESCE(ir."DEALER_CODE"::TEXT, '') = COALESCE(ip."DEALER_CODE"::TEXT, '')
                        AND COALESCE(ir."INDENT_NO"::TEXT, '') = COALESCE(ip."INDENT_NO"::TEXT, '')
                    LEFT JOIN 
                        "IMS_SAP"."TRUCK_SWIPE_ENTRY_SAP" tse
                    ON 
                        COALESCE(ir."LOCN_CODE"::TEXT, '') = COALESCE(tse."LOCN_CODE"::TEXT, '')
                        AND COALESCE(ir."TRUCK_REGNO"::TEXT, '') = COALESCE(tse."TRUCK_REGNO"::TEXT, '')
                        AND tse."CARD_STATUS" = 'O'
                        AND tse."LOADED_ON" >= ir."PROD_REQD_DT"
                        AND tse."LOADED_ON" <= ir."PROD_REQD_DT" + INTERVAL '1 day'
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
                    WHERE run_id = TO_CHAR(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata', 'YYMMDD-HH00')
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
--                     cd."INDENT_NO",
--                     cd."INDENT_DATE",
                    cd."PROD_REQD_DT",
--                     cd."DEALER_CODE",
--                     cd."BATCH_FLAG",
                    cd."TRUCK_REGNO",
                    cd."VALID_INDENT",
                    cd."SEND_TO_JDE_TIME",
                    cd."DELIVERY_DATE",
                    cd."INDENT_HOLD_RELEASE_TIME",
                    cd."INDENT_EXECUTABLE_TIME",
--                     cd."PRODUCT_CODE",
                    cd."QTY",
                    cd."PROD_ALLOT_TIME",
                    cd."SALES_ORDERNO",
                    cd."INVOICE_NO",
--                     cd."JDE_TRUCK_NO",
                    cd."LOADED_ON",
                    cd."CARD_STATUS",
                    sd.avgsales_7days as "AVGSALES_7DAYS"
                FROM 
                    (SELECT * 
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
