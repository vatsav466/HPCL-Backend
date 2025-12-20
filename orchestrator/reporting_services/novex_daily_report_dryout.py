import urdhva_base
import os
import sys
import jinja2
import asyncio
import pandas as pd
import hpcl_ceg_model
import urdhva_base.utilities
from types import SimpleNamespace
import utilities.helpers as helpers
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
import orchestrator.notification_manager.notification_factory as notification_factory
from orchestrator.reporting_services.reporting_helpers import get_alert_data, reporting_helper_retail, reporting_helper_lpg, reporting_helper_sales, reporting_helper_sod



chart_path = ""
zone_wise_pdf_path = ""
last_30_days_chart_path = ""
WRITE_TO_DB = False
lpg_day_wise_trend_exl_path = ""
monthly_score_path = ""
plant_wise_score_path=""
lpg_va_path = ""
lpg_pq_path = ""

def dict_to_object(d):
    """Convert dictionary to object (recursively for nested dictionaries)."""
    if isinstance(d, list):
        return [dict_to_object(i) for i in d]
    if isinstance(d, dict):
        return SimpleNamespace(**{k: dict_to_object(v) for k, v in d.items()})
    return d

async def supply_terminal_wise_counts(by_ro=False):
    query = f"""SELECT DISTINCT
                    CASE 
                        WHEN a.zone = 'CEN' THEN 'CZ'
                        WHEN a.zone = 'NWF' THEN 'NWFZ'
                        ELSE a.zone
                    END AS zone,
                    a.terminal_plant_id AS plant_id,
                    COALESCE(NULLIF(lm.name, ''), a.terminal_plant_name) AS supply_location,
                    COALESCE(NULLIF(lm_ro.region, ''), a.region) AS region,
                    COALESCE(NULLIF(lm_ro.sales_area, ''), a.sales_area) AS sales_area,
                    COALESCE(NULLIF(lm_ro.zone, ''), a.zone) AS zones,
                    a.sap_id
                FROM alerts a
                LEFT JOIN location_master lm
                    ON a.terminal_plant_id = lm.sap_id
                LEFT JOIN location_master lm_ro
                    ON a.sap_id = lm_ro.sap_id
                WHERE
                    COALESCE(a.zone, '') <> ''        -- exclude empty or null zones
                    AND a.mark_as_false = 'true'
                    AND a.alert_status != 'Close'
                    AND a.dry_out_in_days = '1'
                    AND a.terminal_plant_name NOT ILIKE '%retail%'
                    AND a.product_code IN ('2811000', '2812000');"""
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    resp = await function(query=query)
    data_resp = pd.DataFrame(resp)
    data_resp = data_resp.drop(["sales_area", "zones"], axis=1)
    sap_ids = list(set(data_resp["sap_id"].tolist()))
    sap_ids = [str(sid).zfill(10) for sid in sap_ids]
    batch_size = 100
    all_batches = []
    carry_forward_bacthes = []
    for i in range(0, len(sap_ids), batch_size):
        batch = sap_ids[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1}: {len(batch)} items")
        batch_str = ",".join([f"'{str(s)}'" for s in batch])
        ims_query = f"""SELECT 
                            SUBSTR(a."DEALER_CODE", 1, 10) AS "SAP_ID",
                            COUNT(*) AS "VALID_COUNT"
                        FROM "IMS_SAP"."INDENT_REQUEST" a
                        WHERE a."BALANCE_AMOUNT" <= 0
                        AND a."TRUCK_REGNO" IS NULL
                        AND (a."CANCEL_INDENT" IS NULL OR a."CANCEL_INDENT" <> 'Y')
                        AND SUBSTR(a."DEALER_CODE", 1, 10) IN ({batch_str})
                        AND a."PROD_REQD_DT" <= TRUNC(SYSDATE)
                        GROUP BY SUBSTR(a."DEALER_CODE", 1, 10)
                        ORDER BY "SAP_ID" ASC
                        """
        carry_forward_query = f"""SELECT b."ZONECD",a."LOCN_CODE",SUBSTR(a."DEALER_CODE", 1, 10) AS "SAP_ID",
                                  count(a."INDENT_NO") AS "INDCNT" 
                                  FROM "IMS_SAP"."INDENT_REQUEST" a,"IMS_SAP"."LOCN_MASTER" b WHERE a."LOCN_CODE" = b."LOCN_CODE" AND
                                  TO_CHAR(a."PROD_REQD_DT",'yyyymmdd') < TO_CHAR(SYSDATE,'yyyymmdd') AND
                                  TO_CHAR(a."PROD_REQD_DT",'yyyymmdd') > TO_CHAR(SYSDATE-3,'yyyymmdd')
                                  AND SUBSTR(a."DEALER_CODE", 1, 10) IN ({batch_str})
                                  --and TO_CHAR(sysdate-7,'dd/mm/yyyy')
                                  AND a."TRUCK_REGNO" IS NULL AND (a."CANCEL_INDENT" IS NULL OR a."CANCEL_INDENT" <> 'Y')
                                  GROUP BY b."ZONECD", a."LOCN_CODE",SUBSTR(a."DEALER_CODE", 1, 10)
                                  ORDER BY b."ZONECD",a."LOCN_CODE"
                                  """
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        resp = await function(query=ims_query)
        batch_df = pd.DataFrame(resp)
        all_batches.append(batch_df)
        carry_resp = await function(query=carry_forward_query)
        carry_df = pd.DataFrame(carry_resp)
        carry_forward_bacthes.append(carry_df)

    # Combine all batches into one DataFrame
    # final_df = pd.concat(all_batches, ignore_index=True)
    # carry_forward_final_df = pd.concat(carry_forward_bacthes, ignore_index=True)
    # carry_forward_final_df.drop_duplicates(subset=["SAP_ID"], inplace=True)
    # carry_forward_final_df["SAP_ID"] = carry_forward_final_df["SAP_ID"].astype(str).str.lstrip("0")
    # # Optionally remove duplicates if needed
    # final_df.drop_duplicates(subset=["SAP_ID"], inplace=True)
    # final_df["SAP_ID"] = final_df["SAP_ID"].astype(str).str.lstrip("0")
    # Handle empty IMS batches safely
    valid_batches = [
        df for df in all_batches
        if not df.empty and "SAP_ID" in df.columns
    ]
    if valid_batches:
        final_df = pd.concat(valid_batches, ignore_index=True)
        final_df.drop_duplicates(subset=["SAP_ID"], inplace=True)
        final_df["SAP_ID"] = final_df["SAP_ID"].astype(str).str.lstrip("0")
    else:
        final_df = pd.DataFrame(columns=["SAP_ID", "VALID_COUNT"])
    
    valid_carry_batches = [
        df for df in carry_forward_bacthes
        if not df.empty and "SAP_ID" in df.columns
    ]
    if valid_carry_batches:
        carry_forward_final_df = pd.concat(valid_carry_batches, ignore_index=True)
        carry_forward_final_df.drop_duplicates(subset=["SAP_ID"], inplace=True)
        carry_forward_final_df["SAP_ID"] = carry_forward_final_df["SAP_ID"].astype(str).str.lstrip("0")
    else:
        carry_forward_final_df = pd.DataFrame(columns=["SAP_ID", "INDCNT"])

    # print(final_df)
    # print("Combined DataFrame created successfully with", len(final_df), "records.")
    merged_df = data_resp.merge(
        final_df,
        how="left",
        left_on="sap_id",
        right_on="SAP_ID"
    )
    merged_df["VALID_COUNT"] = merged_df["VALID_COUNT"].fillna(0).astype(int)
    # Drop the extra SAP_ID column (from IMS data)
    merged_df.drop(columns=["SAP_ID"], inplace=True)
    # Step 6: Final output
    # print(merged_df.head())
    # print(f"\n Combined DataFrame created successfully with {len(merged_df)} records.")
    # print(" VALID_COUNT column added successfully based on SAP_ID.")
    carry_merge_df = merged_df.merge(
        carry_forward_final_df,
        how="left",
        left_on="sap_id",
        right_on="SAP_ID"
    )
    carry_merge_df["INDCNT"] = carry_merge_df["INDCNT"].fillna(0).astype(int)
    carry_merge_df.drop(columns=["SAP_ID"], inplace=True)

    required_columns = ["zone", "supply_location", "region"]
    if by_ro:
        required_columns.append("sap_id")

    summary_df = (
        carry_merge_df.groupby(required_columns, dropna=False)
        .agg(
            **{
                "Count of Dryout ROs": ("sap_id", "nunique"),
                "Count of DryOut Outlets with Valid indent": ("VALID_COUNT", "sum"),
                "Avg. Pending Indents for last 3 days": ("INDCNT", "sum")
            }
        )
        .reset_index()
    )
    # Step 8: Rename columns
    summary_df.rename(
        columns={
            "zone": "Zone",
            "supply_location": "Supply Location (Terminal)",
            "region": "Region",
        },
        inplace=True,
    )
    # Sort by Count of Dryout ROs in descending order
    summary_df = summary_df.sort_values(
        by="Count of Dryout ROs", ascending=False, ignore_index=True
    )
    summary_df.insert(0, "Sl No", range(1, len(summary_df) + 1))
    # Step 8: Display results
    print(summary_df.head())
    #print(f"Summary DataFrame created successfully with {len(summary_df)} rows.")
    return summary_df

async def fetch_dryout_data():
    global zone_wise_pdf_path
    global WRITE_TO_DB
    query = """
                WITH dates AS (
                SELECT CURRENT_DATE::date AS report_date
                ),
                distinct_alerts AS (
                SELECT DISTINCT ON (a.sap_id)
                    a.id,
                    a.sap_id,
                    COALESCE(a.zone, lm.zone) AS raw_zone,
                    a.created_at::date AS created_date
                FROM alerts a
                LEFT JOIN location_master lm ON a.sap_id = lm.sap_id
                WHERE a.interlock_name = 'Dry Out Each Indent Wise MainFlow'
                    AND a.mark_as_false = true
                    AND a.product_code IN ('2811000','2812000','2822000')
                    AND a.dry_out_in_days = '1'
                    AND a.indent_status NOT IN ('Cancelled', 'Completed', 'TempClosed', 'ProductLowLevel', 'OfflineOrFalseAlarm', 'NotAvailable')
                ORDER BY a.sap_id, a.progress_rate ASC, a.id
                ),
                normalized AS (
                SELECT
                    id,
                    sap_id,
                    created_date,
                    CASE
                    WHEN raw_zone IN ('CEN','CZ') THEN 'CZ'
                    WHEN raw_zone = 'ECZ' THEN 'ECZ'
                    WHEN raw_zone = 'EZ' THEN 'EZ'
                    WHEN raw_zone IN ('NCR','NCZ') THEN 'NCZ'
                    WHEN raw_zone = 'NFZ' THEN 'NFZ'
                    WHEN raw_zone = 'NWF' THEN 'NWFZ'
                    WHEN raw_zone IN ('NWR','NWZ') THEN 'NWZ'
                    WHEN raw_zone = 'NZ' THEN 'NZ'
                    WHEN raw_zone IN ('SCR','SCZ') THEN 'SCZ'
                    WHEN raw_zone = 'SWZ' THEN 'SWZ'
                    WHEN raw_zone = 'SZ' THEN 'SZ'
                    WHEN raw_zone = 'WZ' THEN 'WZ'
                    ELSE 'OTHERS'
                    END AS zone
                FROM distinct_alerts
                )
                SELECT
                d.report_date AS "report_date",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'CZ')  AS "CZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'ECZ') AS "ECZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'EZ')  AS "EZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'NCZ') AS "NCZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'NFZ') AS "NFZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'NWFZ') AS "NWFZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'NWZ') AS "NWZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'NZ')  AS "NZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'SCZ') AS "SCZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'SWZ') AS "SWZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'SZ')  AS "SZ",
                COUNT(DISTINCT n.sap_id) FILTER (WHERE n.zone = 'WZ')  AS "WZ",
                COUNT(DISTINCT n.sap_id) AS "Grand Total",
                ARRAY_AGG(n.id) AS all_ids
                FROM dates d
                LEFT JOIN normalized n ON n.created_date <= d.report_date
                GROUP BY d.report_date
                ORDER BY d.report_date
            """
    dry_out_report_count = await hpcl_ceg_model.Alerts.get_aggr_data(query)
    if dry_out_report_count.get("data", []):
        report_data = dry_out_report_count["data"][0]
        report_date = str(report_data["report_date"])
        # Step 1: check if record exists
        check_query = f"""
            SELECT id
            FROM dry_out_daily_report
            WHERE dry_out_date = '{report_date}'
        """
        existing = await hpcl_ceg_model.DryOutDailyReport.get_aggr_data(check_query)
        all_ids_list = [str(i) for i in report_data["all_ids"]] if report_data["all_ids"] else []
        dry_out_zone = []
        for key, value in report_data.items():
            if key not in ["report_date", "Grand Total", "all_ids"]:
                dry_out_zone.append({
                    "zone": key,
                    "count": str(value or 0)
                })
        if not existing.get("data", []):
            data = {
                "dry_out_date": report_date,
                "dry_out_count": str(report_data["Grand Total"]),
                "dry_out_zone": dry_out_zone,
                "dry_out_alert_ids": all_ids_list,
            }
            await hpcl_ceg_model.DryOutDailyReportCreate(**data).create()
        else:
            if WRITE_TO_DB:
                alert_id = existing['data'][0]['id']
                await hpcl_ceg_model.DryOutDailyReport(**{"id": alert_id, 
                                                          "dry_out_count": str(report_data["Grand Total"]),
                                                          "dry_out_zone": dry_out_zone,
                                                          "dry_out_alert_ids": all_ids_list}).modify()
                print("Data Inserted Successfully")
            else:
                print("Cannot update already existing Data")
            

    payload_dict = {"filters": [{"key": "interlock_name", "cond": "=", "value": ["Dry Out Each Indent Wise MainFlow"]},
                                {"key": "zone", "cond": "=", "value": []}, {"key": "plant", "cond": "=", "value": []},
                                {"key": "dealer_id", "cond": "=", "value": []},
                                {"key": "product_code", "cond": "=", "value": ["2811000", "2812000", "2822000"]},
                                {"key": "region", "cond": "=", "value": []},
                                {"key": "sales_area", "cond": "=", "value": []},
                                {"key": "progress_rate", "cond": "=", "value": []},
                                {"key": "dry_out_in_days", "cond": "=", "value": ["1"]},
                                {"key": "category", "cond": "=", "value": []}],
                    "bu_type": "ro"}
    payload_obj = indentdryout_actions.Indentdryout_Get_Dried_Out_RoParams(**payload_dict)
    response = await indentdryout_actions.indentdryout_get_dried_out_ro(payload_obj)
    cat_a = carry_fwd_dry_out = carry_fwd_indent = indent_not_raised = indent_raised = 0
    dry_out_details = {stat['section']: int(stat['value']) for stat in response['stats']}
    for stat in response['stats']:
        if stat['section'] == "CATA Carry Fwd Indent":
            cat_a = stat['value']
        elif stat['section'] == "DryOut Carry Fwd Indent":
            carry_fwd_dry_out = stat['value']
        elif stat['section'] == "Carry Fwd Indent":
            carry_fwd_indent = stat['value']
        elif stat['section'] == 'Indent Not Raised':
            indent_not_raised = stat['value']
        elif stat['section'] == 'Indent Raised':
            indent_raised = stat['value']

    query = f"""
        SELECT dry_out_date, dry_out_zone, dry_out_count
        FROM dry_out_daily_report
        WHERE dry_out_date::DATE >= date_trunc('month', CURRENT_DATE)
        AND dry_out_date::DATE < (date_trunc('month', CURRENT_DATE) + interval '1 month')
    """
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    resp_target = await function(query=query)

    data = pd.DataFrame(resp_target)

    zones = ["CZ", "ECZ", "EZ", "NCZ", "NFZ", "NWFZ", "NWZ", "NZ", "SCZ", "SWZ", "SZ", "WZ"]

    # Parse dry_out_zone JSON
    data['dry_out_zone'] = data['dry_out_zone'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)

    # Prepare records for flattening
    records = []
    for _, row in data.iterrows():
        date = row['dry_out_date']
        for z in row['dry_out_zone']:
            records.append({
                'Date': date,
                'Zone': z['zone'],
                'Count': int(z['count'])
            })

    flat_df = pd.DataFrame(records)

    # Pivot to zone-wise columns
    pivot = flat_df.pivot_table(index='Date', columns='Zone', values='Count', fill_value=0)
    for zone in zones:
        if zone not in pivot.columns:
            pivot[zone] = 0
    pivot = pivot[zones]

    # Convert dry_out_date to datetime for merging
    data['dry_out_date'] = pd.to_datetime(data['dry_out_date'])

    # Map original dry_out_count per date (converted to int)
    dry_out_count_map = data.groupby('dry_out_date')['dry_out_count'].first().astype(int)

    # Prepare pivot for merge
    pivot = pivot.reset_index()
    pivot['Date'] = pd.to_datetime(pivot['Date'])

    # Merge dry_out_count into pivot by date, replacing 'Grand Total'
    pivot = pivot.merge(dry_out_count_map.rename('dry_out_count'), left_on='Date', right_index=True, how='left')

    # Rename pivot date column to match desired column name
    pivot.rename(columns={'Date': 'Day wise No. of Dryout ROs'}, inplace=True)

    # Set 'Grand Total' to dry_out_count from original query
    pivot['Grand Total'] = pivot['dry_out_count'].fillna(0).astype(int)

    # Drop helper column
    pivot.drop(columns=['dry_out_count'], inplace=True)

    # Convert zone counts to int
    pivot[zones] = pivot[zones].astype(int)

    # Summary row values (example values, modify if needed) Day wise No. of Dryout ROs
    default_ro_values_base = {
        'CZ': 2454,
        'ECZ': 1844,
        'EZ': 1151,
        'NCZ': 2912,
        'NFZ': 1522,
        'NWFZ': 1863,
        'NWZ': 1355,
        'NZ': 1419,
        'SCZ': 2800,
        'SWZ': 2487,
        'SZ': 1899,
        'WZ': 2628
    }

    default_ro_values = {
        'Day wise No. of Dryout ROs': 'Zone wise ROs',
        'Grand Total': sum(val for key, val in default_ro_values_base.items() if key in zones)
    }
    for col in zones:
        default_ro_values[col] = default_ro_values_base.get(col, 0)

    # Prepend summary row
    pivot = pd.concat([pd.DataFrame([default_ro_values]), pivot], ignore_index=True)

    pivot.loc[1:, 'Day wise No. of Dryout ROs'] = pd.to_datetime(pivot.loc[1:, 'Day wise No. of Dryout ROs']).dt.strftime('%Y-%m-%d')

    # Reorder columns to put Grand Total as last column
    cols = list(pivot.columns)
    cols.remove('Grand Total')
    cols.append('Grand Total')
    pivot = pivot[cols]

    # Print final pivot table without index
    print("\n===== Zone-wise Dryout ROs =====")
    print(pivot.to_string(index=False))


    # Prepare and print summary (date-wise dryout count)
    summary_df = pivot.copy()
    summary_df["Day wise No. of Dryout ROs"] = pd.to_datetime(summary_df["Day wise No. of Dryout ROs"], errors="coerce").dt.strftime("%b %-d").fillna(summary_df["Day wise No. of Dryout ROs"])
    summary_df = summary_df.rename(columns={"Day wise No. of Dryout ROs": "Date", "Grand Total": "Dry out Count"})[["Date", "Dry out Count"]]
    summary_df = summary_df[summary_df["Date"] != "Zone wise ROs"]
    summary_df["Dry out Count"] = summary_df["Dry out Count"].astype(int)
    summary_df = summary_df[~summary_df["Date"].str.contains("Day wise", na=False)]
    #summary_df = summary_df.iloc[:-1]

    print("\n===== Summary (Date vs Dry out Count) =====")
    print(summary_df.to_string(index=False))

    date = urdhva_base.utilities.get_present_time()
    date_yes = helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                               date_time_format=None)
    month_start = helpers.get_time_stamp_by_delta(date_yes, days=0, with_month_start_day=True,
                                               date_time_format="%Y-%m-%d")
    loss_query = f"""WITH financial_year_bounds AS (
                        SELECT
                            CASE
                                WHEN EXTRACT(MONTH FROM CURRENT_DATE) >= 4 THEN
                                    DATE_TRUNC('year', CURRENT_DATE) + INTERVAL '3 months'  -- April 1 current year
                                ELSE 
                                    DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '9 months'  -- April 1 last year
                            END AS fy_start
                    )
                    SELECT
                        TO_CHAR(stock_date, 'Mon''YY') AS "Month",
                        SUM(CASE WHEN product_name = 'MS' THEN loss_of_sale ELSE 0 END) AS "MS in KL",
                        SUM(CASE WHEN product_name = 'HSD' THEN loss_of_sale ELSE 0 END) AS "HSD in KL",
                        SUM(CASE WHEN product_name IN ('HSD', 'MS') THEN loss_of_sale ELSE 0 END) AS "TMF in KL"
                    FROM
                        daily_product_dry_out, financial_year_bounds
                    WHERE
                        stock_date >= fy_start
                        AND stock_date < fy_start + INTERVAL '1 year'
                        AND product_no in (1322000, 1683000)
                    GROUP BY
                        TO_CHAR(stock_date, 'Mon''YY'),
                        DATE_TRUNC('month', stock_date)
                    ORDER BY
                        DATE_TRUNC('month', stock_date)
                    """
    last_30_days_dry_out_trends_query = f"""SELECT dry_out_date, dry_out_count
                                            FROM dry_out_daily_report Where created_at::DATE > CURRENT_DATE - INTERVAL '30 days'
                                        """
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("cris", "2")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    zone_data = await function(query=loss_query)
    last_30_days_trends = await function(query=last_30_days_dry_out_trends_query)
    zone_fuel_df = pd.DataFrame(zone_data)
    last_30_days_trends_df = pd.DataFrame(last_30_days_trends)


    zone_wise_chart = await dry_out_trends_chart(last_30_days_trends_df)
    chart_path = await generate_chart(zone_fuel_df)

    supply_terminal_query_ro_count_df = await supply_terminal_wise_counts()

    bottom_3_per_zone_sorted = (
        supply_terminal_query_ro_count_df
        .groupby("Zone", group_keys=True)
        .apply(lambda x: x.nlargest(3, "Count of Dryout ROs")
                        .sort_values("Count of Dryout ROs", ascending=False))
        .reset_index(drop=True)
    )

    # Step 3: Reassign Sl No sequentially
    bottom_3_per_zone_sorted["Sl No"] = range(1, len(bottom_3_per_zone_sorted) + 1)

    # Step 4: Reorder columns for readability
    bottom_3_per_zone_sorted = bottom_3_per_zone_sorted[
        ["Sl No", "Zone", "Supply Location (Terminal)", "Region", "Count of Dryout ROs", "Count of DryOut Outlets with Valid indent", "Avg. Pending Indents for last 3 days"]
    ]
    print(bottom_3_per_zone_sorted)

    # Convert DataFrame to styled HTML
    supply_terminal_query_ro_count_df = supply_terminal_query_ro_count_df.sort_values(
        by=["Zone", "Count of Dryout ROs"],
        ascending=[True, False]
    )
    supply_terminal_query_ro_count_df["Sl No"] = range(1, len(supply_terminal_query_ro_count_df) + 1)
    html_table = supply_terminal_query_ro_count_df.to_html(
        index=False,
        classes="styled-table",
        border=0,
        justify="center"
    )

    retail_html_content = f"""  <html>
                                <head>
                                <style>
                                @page {{
                                    margin: 10px;  /* Reduce PDF margins */
                                }}
                                body {{
                                    font-family: Arial, sans-serif;
                                    margin: 5px;  /* Reduce white space around content */
                                    padding: 0;
                                }}
                                h2 {{
                                    text-align: center;
                                    color: #003366;
                                    margin-bottom: 10px;
                                    margin-top: 5px;
                                }}
                                table.styled-table {{
                                    border-collapse: collapse;
                                    width: 100%;
                                    margin: 5px auto;  /* Small margin around table */
                                }}
                                table.styled-table th {{
                                    background-color: #003366;
                                    color: white;
                                    text-align: center;
                                    padding: 8px;
                                    border: 1px solid #ddd;
                                }}
                                table.styled-table td {{
                                    text-align: center;
                                    padding: 6px;
                                    border: 1px solid #ddd;
                                }}
                                table.styled-table tr:nth-child(even) {{
                                    background-color: #f2f2f2;
                                }}
                                </style>
                                </head>
                                <body>
                                <h2>Location Wise RO Dryout Count</h2>
                                {html_table}
                                </body>
                                </html>
                                """

    pdf_path = "/tmp/Location Wise RO Dryout Count.pdf"

    zone_wise_pdf_path = pdf_path

    HTML(string=retail_html_content).write_pdf(pdf_path)

    retail_sales = await fetch_retail_sales()

    dry_out_cf = {
        'cat_a': cat_a,
        'dry_out': carry_fwd_dry_out,
        'others': carry_fwd_indent - carry_fwd_dry_out - cat_a,
        'total': carry_fwd_indent
    }
    dry_out = {
        "dry_out": indent_not_raised + indent_raised,
        'indent_not_raised': indent_not_raised,
        "indent_raised": indent_raised
    }

    print("dry_out_cf :", dry_out_cf)
    print("dry_out :", dry_out)
    return {"dry_out_cf": dry_out_cf, "dry_out": dry_out, 'dry_out_details': dry_out_details, 
            'dry_out_trends': summary_df.to_dict(orient='records'),
            'zone_wise_summary': pivot, 'zone_fuel_df':zone_fuel_df, 'supply_terminal_query_ro_count_df': bottom_3_per_zone_sorted, "retail_sales": retail_sales}


async def get_lpg_rejection():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    query = f""" SELECT count(interlock_name) as total_count FROM alerts where interlock_name in ('O-Ring Leak Rejection','Valve Leak Rejection','Check Scale Rejection') and created_at>='{today}' """
    rejections = await function(query=query)
    if rejections:
        return {"pq_critical_lpg": rejections[-1]["total_count"], "pq_high_lpg": 0}
    return {"pq_critical_lpg": 0, "pq_high_lpg": 0}


async def get_ro_alerts():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    query = f""" SELECT count(interlock_name) as total_count, severity FROM alerts where bu='RO' and 
    interlock_name != 'Dry Out Each Indent Wise MainFlow' and alert_section='RO' and 
    created_at>='{today}' and alert_status='Open' GROUP BY severity; """
    alerts = await function(query=query)
    data = {}
    if alerts:
        for alert in alerts:
            if alert["severity"] == "Critical":
                data = {"automation_critical_ro": alert["total_count"]}
            if alert["severity"] == "High":
                data = {"automation_high_ro": alert["total_count"]}
    for key in ["automation_critical_ro", "automation_high_ro"]:
        if key not in data.keys():
            data.update({key: 0})
    return data


async def get_tas_alerts():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    query = f""" SELECT count(interlock_name) as total_count, severity FROM alerts where bu='TAS' and created_at>='{today}' and alert_status='Open' GROUP BY severity; """
    alerts = await function(query=query)
    data = {}
    if alerts:
        for alert in alerts:
            if alert["severity"] == "Critical":
                data = {"tas_critical_sod": alert["total_count"]}
            if alert["severity"] == "High":
                data = {"tas_high_sod": alert["total_count"]}
    for key in ["tas_critical_sod", "tas_high_sod"]:
        if key not in data.keys():
            data.update({key: 0})
    return data

async def get_vts_route_deviation():
    date = urdhva_base.utilities.get_present_time()
    date_yes = helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                               date_time_format=None)
    month_start = helpers.get_time_stamp_by_delta(date_yes, days=0, with_month_start_day=True,
                                               date_time_format="%Y-%m-%d")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    date_filter = f"a.created_at::DATE <= '{date_yes.strftime('%Y-%m-%d')}'"
    tas_query = f"""SELECT 
                    COALESCE(lm.name, a.location_name) AS "Terminal Name",
                    a.sap_id AS "Terminal Id",
                    COALESCE(lm.zone, a.zone) AS "Zone",
                    COUNT(*) AS "Open Alerts"
                FROM alerts a
                LEFT JOIN location_master lm 
                    ON a.sap_id = lm.sap_id
                WHERE a.alert_status = 'Open'
                AND a.alert_section = 'VTS'
                AND a.violation_type = 'route_deviation_count'
                AND a.bu = 'TAS' AND {date_filter}
                AND COALESCE(lm.name, a.location_name) IS NOT NULL
                AND COALESCE(lm.name, a.location_name) <> ''
                GROUP BY COALESCE(lm.name, a.location_name), a.sap_id, COALESCE(lm.zone, a.zone)
                ORDER BY "Zone", "Terminal Name"
                """
    
    lpg_query = f"""SELECT 
                    COALESCE(lm.name, a.location_name) AS "Plant Name",
                    a.sap_id AS "Plant Id",
                    COALESCE(lm.zone, a.zone) AS "Zone",
                    COUNT(*) AS "Open Alerts"
                FROM alerts a
                LEFT JOIN location_master lm 
                    ON a.sap_id = lm.sap_id
                WHERE a.alert_status = 'Open'
                AND a.violation_type = 'route_deviation_count'
                AND a.alert_section = 'VTS'
                AND a.bu = 'LPG' AND {date_filter}
                AND COALESCE(lm.name, a.location_name) IS NOT NULL
                AND COALESCE(lm.name, a.location_name) <> ''
                GROUP BY COALESCE(lm.name, a.location_name), a.sap_id, COALESCE(lm.zone, a.zone)
                ORDER BY "Zone", "Plant Name"
            """
    tas_alerts = await function(query=tas_query)
    lpg_alerts = await function(query=lpg_query)

    tas_alerts = pd.DataFrame(tas_alerts)
    lpg_alerts = pd.DataFrame(lpg_alerts)
    return {"lpg_vts_data": lpg_alerts, "tas_vts_data": tas_alerts}



async def publish_daily_novex_status_email():
    date = urdhva_base.utilities.get_present_time()
    date_yes = helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                                       date_time_format=None)
    report_generated_time = date.strftime('%I:%M %p')
    if date.strftime('%Y-%m-%d').split('-')[-1] == '01' or date.strftime('%Y-%m-%d').split('-')[-1] == '1':
        print("datde inside if",date)
        status_yes_date = date
        tmp_date = urdhva_base.utilities.get_present_time()
        tmp_date_yes = helpers.get_time_stamp_by_delta(tmp_date, days=1, with_month_start_day=False,
                                               date_time_format=None)
        tmp_date_start = helpers.get_time_stamp_by_delta(tmp_date, days=1, with_month_start_day=True,
                                               date_time_format=None)

        status_data = {'today_date': date.strftime('%d-%B-%Y'), 'report_generated_time': report_generated_time,
                   'yesterday_date': helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                                                               date_time_format='%d-%B-%Y'),
                   'today_week': date.strftime('%A'), 'yesterday_week':
                       helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                                                 date_time_format='%A'),
                   'today': date.strftime('%d-%B-%Y'),
                   'yesterday': helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                                                          date_time_format='%d-%B-%Y'),
                   'present_month': f"01-{tmp_date_start.strftime('%b')} to {tmp_date_yes.strftime('%d')}-{tmp_date_yes.strftime('%b')}"}
                  # 'present_month': f"01-{date.strftime('%b')} to {date_yes.strftime('%d')}-{date_yes.strftime('%b')}"}
    else:
         status_data = {'today_date': date.strftime('%d-%B-%Y'), 'report_generated_time': report_generated_time,
                   'yesterday_date': helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                                                               date_time_format='%d-%B-%Y'),
                   'today_week': date.strftime('%A'), 'yesterday_week':
                       helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                                                 date_time_format='%A'),
                   'today': date.strftime('%d-%B-%Y'),
                   'yesterday': helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                                                          date_time_format='%d-%B-%Y'),
                  # 'present_month': f"01-{tmp_date_start.strftime('%b')} to {tmp_date_yes.strftime('%d')}-{tmp_date_yes.strftime('%b')}"}
                   'present_month': f"01-{date.strftime('%b')} to {date_yes.strftime('%d')}-{date_yes.strftime('%b')}"}

    status_data.update(await reporting_helper_sales.fetch_sales_data())
    # print("status_data before :", status_data)
    status_data.update(await reporting_helper_retail.fetch_dryout_data())
    status_data.update(await reporting_helper_lpg.get_lpg_rejection())
    status_data.update(await reporting_helper_retail.get_ro_alerts())
    status_data.update(await reporting_helper_sod.get_tas_alerts())
    #status_data.update(await get_vts_route_deviation())
    status_data.update(await reporting_helper_lpg.lpg_top_bottom_score_plants())
    status_data.update(await reporting_helper_lpg.get_vts_lpg_blocked_counts())
    status_data.update(await reporting_helper_sod.get_vts_tas_blocked_counts())

    for alert_section in ["VA", "VTS", "EMLock", "TAS"]:
        status_data.update(await get_alert_data.get_alert_data(alert_section))
    # print("-" * 50)
    # print("status_data :", json.dumps(status_data))
    # print("-" * 50)
    # print("-------->status_data",status_data)
    await send_notification(
        template_name="seg1.html",
        to_recipients=["sachinkwarghane@hpcl.in","purushm@hpcl.in","adityapandey@hpcl.in"],
        subject="Novex Daily Report",
        cc_recipients=["venu@algofusiontech.com", "santoshkumar.s@algofusiontech.com", "moufikali@algofusiontech.com", "aditya@algofusiontech.com"],
        bcc_recipients=["yesu.p@algofusiontech.com","manohar.v@algofusiontech.com","gayathri.m@algofusiontech.com","jayaprakash.v@algofusiontech.com"],
        notification_data=status_data,
        inline_images={
            "dry_out_lost": f"{chart_path}",
            "last_30_days_dry_out_trends": f"{last_30_days_chart_path}"
        },
        attachments = [zone_wise_pdf_path]
    )
    await send_notification(
        template_name="seg2.html",
        to_recipients=["sachinkwarghane@hpcl.in","purushm@hpcl.in","adityapandey@hpcl.in"],
        subject="Novex Daily Report: Retail",
        cc_recipients=["venu@algofusiontech.com", "santoshkumar.s@algofusiontech.com", "moufikali@algofusiontech.com", "aditya@algofusiontech.com"],
        bcc_recipients=["yesu.p@algofusiontech.com","manohar.v@algofusiontech.com","gayathri.m@algofusiontech.com","jayaprakash.v@algofusiontech.com"],
        notification_data=status_data,
        inline_images={
            "dry_out_lost": f"{chart_path}",
            "last_30_days_dry_out_trends": f"{last_30_days_chart_path}"
        },
        attachments = [zone_wise_pdf_path]
    )
    await send_notification(
        template_name="seg3.html",
        to_recipients=["sachinkwarghane@hpcl.in","purushm@hpcl.in","adityapandey@hpcl.in"],
        subject="Novex Daily Report: LPG",
        cc_recipients=["venu@algofusiontech.com", "santoshkumar.s@algofusiontech.com", "moufikali@algofusiontech.com", "aditya@algofusiontech.com"],
        bcc_recipients=["yesu.p@algofusiontech.com","manohar.v@algofusiontech.com","gayathri.m@algofusiontech.com","jayaprakash.v@algofusiontech.com"],
        notification_data=status_data,
        inline_images={
            "monthly_score_path": f"{monthly_score_path}",
            "plant_wise_score_path": f"{plant_wise_score_path}"
        },
        attachments= [lpg_day_wise_trend_exl_path,lpg_va_path,lpg_pq_path]
5    )
    await send_notification(
        template_name="seg4.html",
        to_recipients=["sachinkwarghane@hpcl.in","purushm@hpcl.in","adityapandey@hpcl.in"],
        subject="Novex Daily Report: SOD",
        cc_recipients=["venu@algofusiontech.com", "santoshkumar.s@algofusiontech.com", "moufikali@algofusiontech.com", "aditya@algofusiontech.com"],
        bcc_recipients=["yesu.p@algofusiontech.com","manohar.v@algofusiontech.com","gayathri.m@algofusiontech.com","jayaprakash.v@algofusiontech.com"],
        notification_data=status_data,
        attachments = [zone_wise_pdf_path]
    )
    await send_notification(
        template_name="seg5.html",
        to_recipients=["sreedhar.maddipati@algofusiontech.com"],
        subject="Novex Daily Report",
        cc_recipients=["venu@algofusiontech.com", "santoshkumar.s@algofusiontech.com", "moufikali@algofusiontech.com", "aditya@algofusiontech.com"],
        bcc_recipients=["yesu.p@algofusiontech.com","manohar.v@algofusiontech.com","gayathri.m@algofusiontech.com","jayaprakash.v@algofusiontech.com"],
        notification_data=status_data,
        inline_images={
            "dry_out_lost": f"{chart_path}",
            "last_30_days_dry_out_trends": f"{last_30_days_chart_path}",
            "monthly_score_path": f"{monthly_score_path}",
            "plant_wise_score_path": f"{plant_wise_score_path}"
        },
        attachments = [zone_wise_pdf_path,lpg_day_wise_trend_exl_path,lpg_va_path,lpg_pq_path]
    )


async def send_notification(template_name, to_recipients, subject, cc_recipients=None, bcc_recipients=None, notification_data=None, inline_images=None, attachments=None):
    template_path = os.path.join(
        os.path.dirname(hpcl_ceg_model.__file__),
        '..', 'orchestrator', 'reporting_services',
        'templates', template_name
        )
    with open(template_path, 'r') as f:
        template_data = jinja2.Template(f.read())
    final_data = template_data.render(**notification_data)

    tmp_file = f"/tmp/{template_name}"
    with open(tmp_file, 'w') as f:
        f.write(final_data)
    # Send email
    ins = await notification_factory.get_notification_module("email")
    await ins.publish_message(
        subject=subject,
        recipients=to_recipients,
        cc_recipients=cc_recipients or [],
        bcc_recipients=bcc_recipients or [],
        html_content=True,
        body=final_data,
        force_send=True,
        inline_images=inline_images or {},
        attachments=attachments or []
    )

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "true":
        WRITE_TO_DB = True
    asyncio.run(publish_daily_novex_status_email())
