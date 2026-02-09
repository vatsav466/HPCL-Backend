import urdhva_base
import os
import json
import psycopg2
import datetime
import pandas as pd
import numpy as np
import hpcl_ceg_model
from weasyprint import HTML
import charts_actions
import dashboard_studio_model
import indentdryout_actions
import urdhva_base.utilities
import matplotlib.pyplot as plt
import utilities.helpers as helpers
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
import orchestrator.dbconnector.credential_loader as credential_loader


creds = credential_loader.get_credentials('APP_DB')

chart_path = ""
zone_wise_pdf_path = ""
last_30_days_chart_path = ""

DB_CONFIG = {
    "host": creds["host"],
    "port": creds["port"],
    "database": creds["database"],
    "user": creds["user"],
    "password": creds["password"]
}


async def dry_out_trends_chart(last_30_days_trends_df, output_path='/tmp/dry_out_trends.png'):
    global last_30_days_chart_path
    last_30_days_chart_path = output_path

    # If Polars DF → convert to Pandas
    if not isinstance(last_30_days_trends_df, pd.DataFrame):
        last_30_days_trends_df = last_30_days_trends_df.to_pandas()
    
    # Fix types
    last_30_days_trends_df['dry_out_count'] = pd.to_numeric(
        last_30_days_trends_df['dry_out_count'], errors='coerce'
    )
    
    last_30_days_trends_df['dry_out_date'] = pd.to_datetime(
        last_30_days_trends_df['dry_out_date'], errors='coerce'
    )

    # Format date label: Nov-21
    last_30_days_trends_df['x_label'] = last_30_days_trends_df['dry_out_date'].dt.strftime('%b-%d')

    plt.figure(figsize=(17, 9))

    bars = plt.bar(
        last_30_days_trends_df['x_label'],
        last_30_days_trends_df['dry_out_count'],
        width=0.45,
        color="#A9A9A9"
    )

    # Add labels above bars
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            height + 30,
            f'{int(height)}',
            ha='center',
            va='bottom',
            rotation=90,        
            fontsize=14,
            fontweight='bold'
        )
    
    # Y-axis ticks → 0, 200, 400, ...
    max_val = last_30_days_trends_df['dry_out_count'].max()
    upper_limit = int(np.ceil(max_val / 200.0) * 200)
    plt.yticks(np.arange(0, upper_limit + 1, 200), fontsize=14)

    # Add top space so text doesn’t touch border
    plt.ylim(0, upper_limit + 300)

    # Add vertical grid lines (like image)
    plt.grid(axis='y', linestyle='--', linewidth=0.6, alpha=0.5)

    plt.xlabel("Day Wise Count", fontsize=16, labelpad=20)
    plt.xticks(rotation=45, ha='right', fontsize=14)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    return output_path


async def generate_chart(zone_fuel_df, out_path='/tmp/monthly_loss_chart.png'):
    global chart_path
    chart_path = out_path
    df = zone_fuel_df.copy()
    df['Month'] = df['Month'].astype(str)
    df['MS in KL'] = pd.to_numeric(df['MS in KL'], errors='coerce').fillna(0)
    df['HSD in KL'] = pd.to_numeric(df['HSD in KL'], errors='coerce').fillna(0)

    df['MS in KL'] = df['MS in KL'] / 1000.0
    df['HSD in KL'] = df['HSD in KL'] / 1000.0

    try:
        order_key = pd.to_datetime(df['Month'], format="%b'%y")
        df = df.assign(_order=order_key).sort_values('_order')
    except Exception:
        df = df.reset_index(drop=True)

    months = df['Month'].tolist()
    ms_vals = df['MS in KL'].to_numpy()
    hsd_vals = df['HSD in KL'].to_numpy()

    x = np.arange(len(months))
    width = 0.32   # Reduced for gap
    bar_gap = 0.10 # Small gap between bars

    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ms_color = '#ff0000'
    hsd_color = '#00008B'

    # Add bars
    ms_bars = ax.bar(x - width/2 - bar_gap/2, ms_vals, width, label='MS', color=ms_color)
    hsd_bars = ax.bar(x + width/2 + bar_gap/2, hsd_vals, width, label='HSD', color=hsd_color)

    # Add value labels on top of bars for MS
    for bar in ms_bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height + 0.01, f'{int(height)}', 
                ha='center', va='bottom', fontsize=8)

    # Add value labels on top of bars for HSD
    for bar in hsd_bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height + 0.01, f'{int(height)}', 
                ha='center', va='bottom', fontsize=8)

    ax.set_title('Monthly Loss of Sales Due to Partial Dryouts (KL)', fontsize=14, pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(months, fontsize=10)
    ax.yaxis.grid(True, linestyle='-', linewidth=0.6, alpha=0.35)
    ax.set_axisbelow(True)
    ax.margins(x=0.02)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False)

    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return out_path


async def generate_nozzel_sales_chart(nozzel_sales_df, out_path="/tmp/grouped_nozzel_sales_chart.png"):
    global chart_path
    chart_path = out_path

    df = nozzel_sales_df.copy()

    df["transaction_date"] = pd.to_datetime(df["transaction_date"]).dt.tz_localize(None)
    df = df.sort_values("transaction_date")


    days = df["transaction_date"].dt.strftime("%b-%d").tolist()
    ms_vals = df["MS_TMT"].tolist()
    hsd_vals = df["HSD_TMT"].tolist()


    x = np.arange(len(days))       
    width = 0.35                    

    fig, ax = plt.subplots(figsize=(12, 5))
    ms_color = '#ff0000'
    hsd_color = '#00008B'

    ms_bars = ax.bar(x - width/2,ms_vals,width,label="MS",color=ms_color)

    hsd_bars = ax.bar(x + width/2,hsd_vals,width,label="HSD",color=hsd_color)

    for bars in (ms_bars, hsd_bars):
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.5,
                f"{int(height)}",
                ha="center",
                va="bottom",
                fontsize=8
            )


    ax.set_title("Daily Product Wise Nozzle Sales (in TMT)", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(days, rotation=45, ha="right")
    ax.yaxis.grid(True, alpha=0.35)
    ax.set_axisbelow(True)

    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15),ncol=2,frameon=False)

    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    # print(f"Grouped bar chart saved at: {os.path.abspath(out_path)}")
    return out_path


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

    valid_ims_dfs = [
        df for df in all_batches
        if not df.empty and "SAP_ID" in df.columns
    ]

    if valid_ims_dfs:
        final_df = pd.concat(valid_ims_dfs, ignore_index=True)
        final_df.drop_duplicates(subset=["SAP_ID"], inplace=True)
        final_df["SAP_ID"] = final_df["SAP_ID"].astype(str).str.lstrip("0")
    else:
        final_df = pd.DataFrame(columns=["SAP_ID", "VALID_COUNT"])
    
    valid_carry_dfs = [
        df for df in carry_forward_bacthes
        if not df.empty and "SAP_ID" in df.columns
    ]

    if valid_carry_dfs:
        carry_forward_final_df = pd.concat(valid_carry_dfs, ignore_index=True)
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


async def generate_sales_queries(product_name):
    """Generates the set of SQL queries needed for the sales report metrics."""
    today = datetime.datetime.now() 
    yesterday = today - datetime.timedelta(days=1)
    # Day
    day_current_start = day_current_end = yesterday.strftime('%Y%m%d')

    day_historical_start = day_historical_end = (yesterday - datetime.timedelta(days=365)).strftime('%Y%m%d')

    # Month
    month_start = yesterday.replace(day=1)
    month_current_start = month_start.strftime('%Y%m%d')
    month_current_end = yesterday.strftime('%Y%m%d')

    month_historical_start = (month_start - datetime.timedelta(days=365)).strftime('%Y%m%d')
    month_historical_end = (yesterday - datetime.timedelta(days=365)).strftime('%Y%m%d')
    
    # Year (Financial Year = April 1)
    fy_start_year = yesterday.year if yesterday.month >= 4 else yesterday.year - 1
    year_current_start = datetime.datetime(fy_start_year, 4, 1).strftime('%Y%m%d')
    year_current_end = yesterday.strftime('%Y%m%d')
    month_start_date = month_start.strftime("%Y-%m-%d")

    year_historical_start = datetime.datetime(fy_start_year - 1, 4, 1).strftime('%Y%m%d')
    year_historical_end = (yesterday - datetime.timedelta(days=365)).strftime('%Y%m%d')

    last_year_same_month_start = datetime.datetime(yesterday.year - 1, yesterday.month, 1)
    if yesterday.month == 12:
        last_year_same_month_end = datetime.datetime(yesterday.year, 1, 1) - datetime.timedelta(days=1)
    else:
        next_month = datetime.datetime(yesterday.year - 1, yesterday.month + 1, 1)
        last_year_same_month_end = next_month - datetime.timedelta(days=1)

    month_total_historical_start = last_year_same_month_start.strftime('%Y%m%d')
    month_total_historical_end = last_year_same_month_end.strftime('%Y%m%d')
    
    base_condition = """
        "SBU_Name" != '0' 
        AND "SBU_Name" IN ('Retail') 
        AND "ProductName" = '{product}'
    """

    query_template = """
        SELECT ROUND(SUM("MOM_DAY_LEVEL_DATA"."NETWEIGHT_TMT")::numeric,2)
        FROM "MOM_DAY_LEVEL_DATA"
        WHERE {condition} 
        AND "DAY_ID" BETWEEN '{start}' AND '{end}';
    """

    queries = {
        "day_current": query_template.format(condition=base_condition.format(product=product_name), start=day_current_start, end=day_current_end),
        "day_historical": query_template.format(condition=base_condition.format(product=product_name), start=day_historical_start, end=day_historical_end),
        "month_current": query_template.format(condition=base_condition.format(product=product_name), start=month_current_start, end=month_current_end),
        "month_historical": query_template.format(condition=base_condition.format(product=product_name), start=month_historical_start, end=month_historical_end),
        "year_current": query_template.format(condition=base_condition.format(product=product_name), start=year_current_start, end=year_current_end),
        "month_total_historical": query_template.format(
        condition=base_condition.format(product=product_name),
        start=month_total_historical_start,
        end=month_total_historical_end
        ),
        "year_historical": query_template.format(condition=base_condition.format(product=product_name), start=year_historical_start, end=year_historical_end)
    }
    print("queries",queries)
    return queries


async def fetch_value(conn, query):
    """Executes a single query and returns the float result, or 0.0 if None."""
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            result = cur.fetchone()
            return float(result[0]) if result and result[0] is not None else 0.0
    except Exception as e:
        # print(f"Error fetching data: {e}") # Suppress verbose printing on failure
        return 0.0


async def calculate_growth(current, historical):
    """Calculates percentage growth, returns 0.0 if historical is zero."""
    if historical == 0 or historical is None:
        return 0.0
    # Returns percentage growth rounded to two decimal places
    return round(((current - historical) / historical) * 100, 2)


async def generate_report(product_name):
    """Fetches all data and calculates growth metrics for a single product."""
    queries = await generate_sales_queries(product_name)
    report = {}

    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            for key, query in queries.items():
                report[key] = await fetch_value(conn, query)

    except Exception as e:
        print(f"Database connection error: {e}")
        # Initialize report dictionary with zero/empty values on DB failure
        keys = ["day_current", "month_current", "projected_sales", "year_current"]
        for key in keys:
            report[key] = 0.0
    
    # Calculate growths
    report["day_growth"] = await calculate_growth(report.get("day_current", 0), report.get("day_historical", 0))
    report["month_growth"] = await calculate_growth(report.get("month_current", 0), report.get("month_historical", 0))
    report["year_growth"] = await calculate_growth(report.get("year_current", 0), report.get("year_historical", 0))
    month_growth = report["month_growth"]
    month_total_historical = report["month_total_historical"]
    projected_sales = month_total_historical + (month_total_historical * month_growth) / 100
    report["projected_sales"] = round(projected_sales, 2)
    report["month_target_growth"] = await calculate_growth(report.get("projected_sales", 0), report.get("month_total_historical", 0))

    # Structure the data for the final DataFrame row
    excel_report_data = {
        # FINAL FIX: Set SBU column to empty string in the data rows 
        "Product Group": product_name, # 'MS' or 'HSD'
        
        "Day's Sales (Current)": report["day_current"],
        "% Growth (Day)": report["day_growth"],
        
        "Month's Cumulative Sales Till Date (Current)": report["month_current"],
        "% Growth (Month MTD)": report["month_growth"],
        
        "Projected Sales for The Month": report["projected_sales"],
        "% Growth (Full Month)": report["month_target_growth"],
        
        "Year Cumulative Sales Till Date (Current)": report["year_current"],
        "% Growth (Year YTD)": report["year_growth"],
    }
    return excel_report_data


async def fetch_retail_sales():
    all_data = []
    for product in ["MS", "HSD"]:
        result = await generate_report(product)
        all_data.append(result)
    return all_data


async def fetch_dryout_data(WRITE_TO_DB=False):
    global zone_wise_pdf_path
    # global WRITE_TO_DB
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
        'CZ': 2487,
        'ECZ': 1878,
        'EZ': 1178,
        'NCZ': 2979,
        'NFZ': 1538,
        'NWFZ': 1888,
        'NWZ': 1377,
        'NZ': 1437,
        'SCZ': 2827,
        'SWZ': 2530,
        'SZ': 1923,
        'WZ': 2657
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
    nozzle_sales_query = f"""SELECT
                                "transaction_date",

                                ROUND(
                                    (
                                        (
                                            SUM("sales_volume") FILTER (WHERE product_grp in ('MS','POWER 99','POWER 95','POWER 100'))
                                            / 1411.0
                                        ) / 1000.0
                                    ) / 0.89
                                )::BIGINT AS "MS_TMT",

                                ROUND(
                                    (
                                        (
                                            SUM("sales_volume") FILTER (WHERE product_grp in ('HSD','TURBO'))
                                            / 1210.0
                                        ) / 1000.0
                                    ) / 0.89
                                )::BIGINT AS "HSD_TMT"

                            FROM "public".nozzle_sales
                            WHERE "transaction_date" >= CURRENT_DATE - INTERVAL '31 days'
                            GROUP BY "transaction_date"
                            ORDER BY "transaction_date";
                        """
    nozzel_previous_day_query = f"""select count(distinct(site_id)) from nozzle_sales where transaction_date::DATE=CURRENT_DATE - INTERVAL '1 day' """
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("cris", "2")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    zone_data = await function(query=loss_query)
    zone_fuel_df = pd.DataFrame(zone_data)


    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    last_30_days_trends = await function(query=last_30_days_dry_out_trends_query)
    last_30_days_trends_df = pd.DataFrame(last_30_days_trends)

    nozzel_sales= await function(query= nozzle_sales_query)
    nozzel_sales_df = pd.DataFrame(nozzel_sales)
    print("nozzel_sales_df = pd.DataFrame(nozzel_sales) ---->\n", nozzel_sales_df)
    nozzel_previous_day = await function(query= nozzel_previous_day_query)
    print("nozzel_previous_day ---->\n", nozzel_previous_day)

    nozzle_sales_percentage = round(
        (nozzel_previous_day[0]['count'] / 24699) * 100,
        1
    )
    print("nozzle_sales_percentage ---->\n", nozzle_sales_percentage)
    
    zone_wise_chart = await dry_out_trends_chart(last_30_days_trends_df)
    chart_path = await generate_chart(zone_fuel_df)
    nozzel_sales_chart = await generate_nozzel_sales_chart(nozzel_sales_df)

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
            'zone_wise_summary': pivot, 'zone_fuel_df':zone_fuel_df, 'supply_terminal_query_ro_count_df': bottom_3_per_zone_sorted, "retail_sales": retail_sales,
            'zone_wise_chart': zone_wise_chart, 'chart_path': chart_path, 'zone_wise_pdf_path': zone_wise_pdf_path, 'nozzel_sales_chart': nozzel_sales_chart,
            'nozzel_previous_day': nozzel_previous_day, 'nozzle_sales_percentage': nozzle_sales_percentage}


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