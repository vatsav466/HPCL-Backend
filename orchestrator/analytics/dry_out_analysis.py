import urdhva_base
import json
import pandas as pd
import hpcl_ceg_model
import charts_actions
import urdhva_base.redispool
import dashboard_studio_model
import utilities.helpers as helpers
from utilities.connection_mapping import product_code_mapping, connection_mapping

req_keys = {
    "TAS": ["zone", "sap_id", "name", "category"],
    "RO": ["zone", 'region', "sales_area", "terminal_plant_id", "terminal_plant_name", "category", "sap_id", "name"]
}


async def get_locations(bu, zone=[], region=[], sales_area=[], plant=[]):
    """
    This function is used to get the location information for a given BU.
    It fetches the location master data from Redis and filters based on the BU provided.
    If zone, region and sales_area are provided, then it filters based on those as well.
    :param bu:
    :param zone:
    :param region:
    :param sales_area:
    :param plant:
    :return:
    """
    bu = bu.upper()
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
            final_data["zone"][rec["zone"]] = {"name": rec["zone"], "id": rec["zone"]}
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
                final_data["plant"][rec["sap_id"]] = {"name": rec["name"], "id": rec["sap_id"]}
        bu_data_ro = [json.loads(helpers.normalize_string(rec)) for key, rec in location_data.items()
                      if helpers.normalize_string(key).startswith(f"RO_")]
        bu_data_ro = pd.DataFrame(bu_data_ro)
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
    data['DEALER_CODE'] = data['DEALER_CODE'] + '-' + data['INDENT_NO']

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
    query = f"""WITH INDENT_DATA AS (
                    SELECT DISTINCT 
                        SUBSTR("DEALER_CODE", 3, 8) AS sap_id, 
                        "PROD_REQD_DT" AS prod_reqd_dt,
                        "INDENT_NO" AS indent_no
                    FROM 
                        "IMS_SAP"."INDENT_REQUEST"
                    WHERE 
                        "PROD_REQD_DT" < NOW()
                        AND "TRUCK_REGNO" IS NULL
                        AND "CANCEL_INDENT" IS NULL
                        AND "VALID_INDENT" IN ('Y', 'H')
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
                        alert_status != 'Close' AND indent_status NOT IN ('Cancelled', 'Completed')
                ),
                COMBINED_DATA AS (
                    SELECT 
                        i.sap_id, 
                        a.terminal_plant_id, 
                        i.indent_no, 
                        i.prod_reqd_dt,
                        NOW() AS reported_date,
                        a.dry_out_in_days, 
                        a.dried_out
                    FROM 
                        INDENT_DATA i
                    LEFT JOIN 
                        ALERT_DATA a 
                    ON 
                        i.sap_id::TEXT = a.sap_id::TEXT AND TRIM(i.indent_no::TEXT) = TRIM(a.indent_no::TEXT)
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
                ORDER BY 
                    cd.sap_id;"""

    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.get("hpcl_ceg", "1")
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    data = await function(query=query)
    data = pd.DataFrame(data)

    if not insert_to_db:
        return data.to_dict(orient="records")

    for each_record in data.to_dict(orient="records"):
        await hpcl_ceg_model.CarryFwdIndentCreate(**each_record)
    return
