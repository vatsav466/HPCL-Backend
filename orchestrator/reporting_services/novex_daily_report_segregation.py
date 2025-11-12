import urdhva_base
import os
import ast
import json
import jinja2
import decimal
import asyncio
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
from types import SimpleNamespace
import utilities.helpers as helpers
import dateutil.parser as dt_parser
import utilities.fiscal_year as fiscal_year
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
import orchestrator.analytics.m60_performance as m60_performance
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
import orchestrator.notification_manager.notification_factory as notification_factory
import orchestrator.dbconnector.credential_loader as credential_loader
# from datetime import datetime, timedelta

actual = {"key": "\"A\"", "cond": "equals", "value": "true"}
history = {"key": "\"H\"", "cond": "equals", "value": "true"}
target = {"key": "\"T\"", "cond": "equals", "value": "true"}
ytd = {"key": "\"YTD\"", "cond": "equals", "value": "true"}
ytpm = {"key": "\"YTDPM\"", "cond": "equals", "value": "true"}
cumulative = {"key": "\"C\"", "cond": "equals", "value": "true"}

chart_path = ""
zone_wise_pdf_path = ""

creds = credential_loader.get_credentials('APP_DB')

DB_CONFIG = {
    "host": creds["host"],
    "port": creds["port"],
    "database": creds["database"],
    "user": creds["user"],
    "password": creds["password"]
}

def round_off(value, input_type='growth'):
    """Round off functionality with rules"""
    # For growth it should be one decimal point
    # For value if > 10 no decimal, < 10 one decimal and < 1 two decimals if round to one was 0
    if (isinstance(value, decimal.Decimal) or isinstance(value, float) or isinstance(value, int) or
            (isinstance(value, str) and value.isdigit())):
        if input_type == 'growth':
            return round(float(value), 1)
        if float(value) > 10:
            return round(float(value))
        elif 1 > float(value) > 0:
            return round(float(value), 2) if round(float(value), 1) == 0 else round(float(value), 1)
        return round(float(value), 1)
    return value


def get_growth_percentage(current, hist):
    """
    Function to calculate growth percentage
    :param current:
    :param hist:
    :return:
    """
    if current and hist:
        return round_off(((current - hist) / hist) * 100)
    elif current and not hist:
        return round_off(100)
    elif not current and hist:
        return round_off(-100)
    else:
        return round_off(0)

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
        ax.text(bar.get_x() + bar.get_width()/2, height + 0.01, f'{height:.2f}', 
                ha='center', va='bottom', fontsize=8)

    # Add value labels on top of bars for HSD
    for bar in hsd_bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height + 0.01, f'{height:.2f}', 
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

def get_zones_by_performance(actual, target, by_sbu=False, req_key='Zone_Name'):
    # Getting top and least performing zones
    if not by_sbu:
        resp_actual = {f"{rec['SBU_Name']}_{rec[req_key]}": float(rec['ACTUAL_TMT_SALES']) for rec in actual}
        resp_target = {f"{rec['SBU_Name']}_{rec[req_key]}": float(rec['TARGET_TMT_SALES']) for rec in target}
        # Calculate percentage achieved
        percentage_achieved = {}
        for key in resp_target:
            actual_value = resp_actual.get(key, 0)  # Get actual value, default to 0 if missing
            target_value = resp_target[key]
            if target_value == 0:
                percentage_achieved[key] = 0 if not actual_value else 100# Avoid division by zero
            else:
                percentage_achieved[key] = round(float(((actual_value - target_value) /
                                                        target_value) * 100), 1)
        sorted_zones = sorted(percentage_achieved.items(), key=lambda x: x[1], reverse=True)

        return sorted_zones
    sbu_level_data = {}
    resp_actual = {}
    resp_target = {}
    for rec in actual:
        sbu = rec['SBU_Name']
        zone = rec[req_key]
        value = rec['ACTUAL_TMT_SALES']
        if sbu not in resp_actual:
            resp_actual[sbu] = {}
        resp_actual[sbu][zone] = value

    for rec in target:
        sbu = rec['SBU_Name']
        zone = rec[req_key]
        value = rec['TARGET_TMT_SALES']
        if sbu not in resp_target:
            resp_target[sbu] = {}
        resp_target[sbu][zone] = value

    # Calculate percentage achieved
    for sbu in resp_target:
        percentage_achieved = {}
        for zone in resp_target[sbu]:
            actual_value = resp_actual.get(sbu, {}).get(zone, 0)  # Get actual value, default to 0 if missing
            target_value = resp_target.get(sbu, {}).get(zone, 0)  # Get actual value, default to 0 if missing
            if target_value == 0:
                percentage_achieved[zone] = 0 if not actual_value else 100# Avoid division by zero
            else:
                percentage_achieved[zone] = round(float(((actual_value - target_value) /
                                                        target_value) * 100), 1)
        sorted_zones = sorted(percentage_achieved.items(), key=lambda x: x[1], reverse=True)
        sbu_level_data[sbu] = sorted_zones
    return sbu_level_data


async def get_m60_sales_data():
    current = fiscal_year.FiscalYear.current()
    if int(datetime.datetime.now(datetime.timezone.utc).month) == 4:
        current = current.prev_fiscal_year
    prev = current.prev_fiscal_year
    pres_year = f"FY {current.start.strftime('%Y')}-{current.end.strftime('%Y')}"
    prev_year = f"FY {prev.start.strftime('%Y')}-{prev.end.strftime('%Y')}"

    # target = f"""select ROUND(SUM("TARGET_QTY_TMT")::numeric,2)
    # AS "TARGET_TMT_SALES", "Zone_Name","SBU_Name" from "M60_LEVEL_METADATA"
    # where fiscal_year='{pres_year}' AND "Zone_Name" not in ('-', '')  AND "SBU_Name" in ('Retail', 'LPG', 'Lubes')
    # group by "Zone_Name","SBU_Name" """
    dt = datetime.datetime.today()
    yesterday = helpers.get_time_stamp_by_delta(dt, days=1, ascending=False,
                                                with_month_start_day=False,
                                                date_time_format="%Y%m%d")
    yesterday_last_year = helpers.get_time_stamp_by_delta(dt, days=1, years=1,
                                                         ascending=False,
                                                         with_month_start_day=False,
                                                         date_time_format="%Y%m%d")

    target = f""" select ROUND(SUM("NETWEIGHT_TMT")::numeric,2) 
    AS "TARGET_TMT_SALES", "Zone_Name","SBU_Name" from "MOM_DAY_LEVEL_DATA" 
    where "FISCALYEAR"='{prev_year}' AND "Zone_Name" not in ('-', '') AND "SBU_Name" in ('Retail', 'LPG', 'Lubes') 
    AND "DAY_ID" <= '{yesterday_last_year}'
    group by "Zone_Name","SBU_Name" """

    actual = f""" select ROUND(SUM("NETWEIGHT_TMT")::numeric,2) 
    AS "ACTUAL_TMT_SALES", "Zone_Name","SBU_Name" from "MOM_DAY_LEVEL_DATA" 
    where "FISCALYEAR"='{pres_year}' AND "Zone_Name" not in ('-', '') AND "SBU_Name" in ('Retail', 'LPG', 'Lubes') 
    AND "DAY_ID" <= '{yesterday}'
    group by "Zone_Name","SBU_Name" """

    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    resp_target = await function(query=target)
    resp_actual = await function(query=actual)
    sbu_level_zones = get_zones_by_performance(resp_actual, resp_target, by_sbu=True, req_key='Zone_Name')

    # By Region
    target = f""" select ROUND(SUM("NETWEIGHT_TMT")::numeric,2) 
            AS "TARGET_TMT_SALES", "Region_Name","SBU_Name" from "MOM_DAY_LEVEL_DATA" 
            where "FISCALYEAR"='{prev_year}' AND "Region_Name" not in ('-', '') 
            AND "DAY_ID" <= '{yesterday_last_year}' group by "Region_Name","SBU_Name" """

    actual = f""" select ROUND(SUM("NETWEIGHT_TMT")::numeric,2) 
        AS "ACTUAL_TMT_SALES", "Region_Name","SBU_Name" from "MOM_DAY_LEVEL_DATA" 
        where "FISCALYEAR"='{pres_year}' AND "Region_Name" not in ('-', '') 
        AND "DAY_ID" <= '{yesterday}' group by "Region_Name","SBU_Name" """

    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    resp_target = await function(query=target)
    resp_actual = await function(query=actual)
    sbu_level_regions = get_zones_by_performance(resp_actual, resp_target, by_sbu=True, req_key='Region_Name')

    return sbu_level_zones, sbu_level_regions


def process_performance_data(data, limit=3):
    """
    Process data to find top performers (>0) and bottom performers (<0)
    Returns both in descending order
    """

    # Convert to list of tuples if needed
    if isinstance(data[0], dict):
        # Handle dictionary format
        items = []
        for item in data:
            for key, value in item.items():
                items.append((key, value))
    else:
        # Handle list format
        items = [(item[0], item[1]) for item in data]

    # Separate positive and negative values
    positive_items = [(key, value) for key, value in items if value >= 0]
    negative_items = [(key, value) for key, value in items if value < 0]

    # Sort in descending order
    top_performers = sorted(positive_items, key=lambda x: x[1], reverse=True)
    bottom_performers = sorted(negative_items, key=lambda x: x[1], reverse=True)

    # Get top 2/3 and bottom 2/3
    top_x = top_performers[:limit]
    bottom_x = bottom_performers[:limit]

    return top_x, bottom_x

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
        "year_historical": query_template.format(condition=base_condition.format(product=product_name), start=year_historical_start, end=year_historical_end),
        "projected_sales": f"""
            SELECT ROUND(SUM("M60_LEVEL_METADATA"."TARGET_QTY_TMT")::numeric,2)
            FROM "M60_LEVEL_METADATA"
            WHERE "SBU_Name" != '0'
            AND "SBU_Name" IN ('Retail')
            AND "ProductName" = '{product_name}'
            AND "year_monthname"::DATE BETWEEN '{month_start_date}' AND '{yesterday.strftime("%Y-%m-%d")}';"""
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

async def fetch_sales_data():
    present_month = int(datetime.datetime.now(datetime.timezone.utc).strftime("%m"))
    sales_data = {}

    # Filter for yesterday's data
    yesterday_date = helpers.get_time_stamp_by_delta(datetime.datetime.now(datetime.timezone.utc), days=1,
                                                     with_month_start_day=False, date_time_format="%Y-%m-%d")

    final_data = {"sales_data": sales_data}

    sbu_mapping = {'': '', "Retail": 'retail', 'LPG': 'lpg', 'I&C': 'i_c', 'Lubes': 'lubes', 'Aviation': 'aviation',
                   'PETCHEM': 'petchem', 'GAS': 'gas'}
    today_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    for sbu_name, map_key in sbu_mapping.items():
        sbu_filter = {}
        if sbu_name:
            sbu_filter = {"key": "\"SBU_Name\"", "cond": "equals", "value": f"{sbu_name}"}
        sbu_sales_data = {}
        # Filter for today's data
        filters = {"filters": [actual, history, cumulative,
                               {"key": "\"DATE\"", "cond": "equals", "value": f"{yesterday_date},{yesterday_date}"}],
                   "cross_filters": [], "drill_state": ""}
        if sbu_filter:
            filters['filters'].append(sbu_filter)
        resp = await m60_performance.m60_performance(**filters)
        print(resp)
        current = float(resp['data']['data']['ACTUAL_TMT_SALES'][0])
        hist = float(resp['data']['data']['ACTUAL_HISTORY_TMT_SALES'][0])
        sbu_sales_data['yesterday_current'] = round_off(current, "")
        sbu_sales_data['yesterday_historical'] = round_off(hist, "")
        sbu_sales_data['yesterday_growth'] = get_growth_percentage(current, hist)
        

        # For current month data
       # month_start = helpers.get_time_stamp_by_delta(with_month_start_day=True)

        date = urdhva_base.utilities.get_present_time()
        date_yes = helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                                   date_time_format=None)
        month_start = helpers.get_time_stamp_by_delta(date_yes, days=0, with_month_start_day=True,
                                                   date_time_format="%Y-%m-%d")
        #if month_start.split('-')[-1] == '01' and( datetime.datetime.today().strftime('%d-%m-%Y').split('-')[0] == '01' or datetime.datetime.today().strftime('%d-%m-%Y').split('-')[0] == '1'): 
        #    yesterday_temp_date = month_start
        #print("yesterday_date",yesterday_temp_date)
        filters = {"filters": [actual, history, cumulative,
                               {"key": "\"DATE\"", "cond": "equals", "value": f"{month_start},{date_yes}"}],
                   "cross_filters": [], "drill_state": ""}
        
        if sbu_filter:
            filters['filters'].append(sbu_filter)
            
        resp = await m60_performance.m60_performance(**filters)

        present_month_act = float(resp['data']['data']['ACTUAL_TMT_SALES'][0])
        present_month_hist = float(resp['data']['data']['ACTUAL_HISTORY_TMT_SALES'][0])
        sbu_sales_data['present_month_historical'] = round_off(present_month_hist, "")
        sbu_sales_data['present_month_current'] = round_off(present_month_act, "")
        sbu_sales_data['present_month_growth'] = get_growth_percentage(present_month_act, present_month_hist)
        sbu_sales_data['ytpm_historical'] = sbu_sales_data['ytpm_current'] = sbu_sales_data['ytpm_growth'] = 'NA'
        
        today = datetime.datetime.today()
        first_day_current_month = today.replace(day=1)
        last_day_prev_month = first_day_current_month - datetime.timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)

        prev_month_start = first_day_prev_month.strftime("%Y-%m-%d")
        prev_month_end = last_day_prev_month.strftime("%Y-%m-%d")

        filters = {
            "filters": [actual, history, cumulative,
                        {"key": "\"DATE\"", "cond": "equals", "value": f"{prev_month_start},{prev_month_end}"}],
            "cross_filters": [],
            "drill_state": ""
        }
        
        
        # For ytpm data
        if present_month != 4:
            filters = {"filters": [actual, history, ytpm, cumulative], "cross_filters": [], "drill_state": ""}
            if ytpm:
                # filters['filters'].append({"key": "\"fiscal_year\"", "cond": "equals", "value": "2025-2026"})
                dyn_fis_year=f"{fiscal_year.FiscalYear.current().start.year}-{fiscal_year.FiscalYear.current().end.year}"
                print("fiscal_year---------------->>>>>",dyn_fis_year)
                filters['filters'].append({"key": "\"fiscal_year\"", "cond": "equals", "value": dyn_fis_year})
                
            if sbu_filter:
                filters['filters'].append(sbu_filter)
            print("checking ytpm --------------------------->filters",filters)

            resp = await m60_performance.m60_performance(**filters)
            print("resp",resp)
    
            ytpm_act = float(resp['data']['data']['ACTUAL_TMT_SALES'][0])
            ytpm_hist = float(resp['data']['data']['ACTUAL_HISTORY_TMT_SALES'][0])
            sbu_sales_data['ytpm_historical'] = round_off(ytpm_hist, "")
            sbu_sales_data['ytpm_current'] = round_off(ytpm_act, "")
            sbu_sales_data['ytpm_growth'] = get_growth_percentage(ytpm_act, ytpm_hist)
        if sbu_name:
            final_data[f"sales_data_{map_key}"] = sbu_sales_data
        else:
            final_data["sales_data"].update(sbu_sales_data)
    return final_data
    

def dict_to_object(d):
    """Convert dictionary to object (recursively for nested dictionaries)."""
    if isinstance(d, list):
        return [dict_to_object(i) for i in d]
    if isinstance(d, dict):
        return SimpleNamespace(**{k: dict_to_object(v) for k, v in d.items()})
    return d

async def supply_terminal_wise_counts():
    query = f"""SELECT DISTINCT
                    CASE 
                        WHEN zone = 'CEN' THEN 'CZ'
                        WHEN zone = 'NWF' THEN 'NWFZ'
                        ELSE zone
                    END AS zone,
                    terminal_plant_name AS supply_location,
                    region,
                    sap_id
                FROM alerts
                WHERE
                    COALESCE(zone, '') <> ''  -- exclude empty or null zones
                    AND mark_as_false = 'true'
                    AND alert_status != 'Close'
                    AND dry_out_in_days = '1'
                    AND product_code IN ('2811000', '2812000');"""
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
    resp = await function(query=query)
    data_resp = pd.DataFrame(resp)
    sap_ids = list(set(data_resp["sap_id"].tolist()))
    sap_ids = [str(sid).zfill(10) for sid in sap_ids]
    batch_size = 100
    all_batches = []
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
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 3
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        resp = await function(query=ims_query)
        batch_df = pd.DataFrame(resp)
        all_batches.append(batch_df)
    
    # Combine all batches into one DataFrame
    final_df = pd.concat(all_batches, ignore_index=True)
    # Optionally remove duplicates if needed
    final_df.drop_duplicates(subset=["SAP_ID"], inplace=True)
    final_df["SAP_ID"] = final_df["SAP_ID"].astype(str).str.lstrip("0")
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
    summary_df = (
        merged_df.groupby(["zone", "supply_location", "region"], dropna=False)
        .agg(
            **{
                "Count of Dryout ROs": ("sap_id", "nunique"),
                "Count of DryOut Outlets with Valid indent": ("VALID_COUNT", "sum"),
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
                    AND a.indent_status NOT IN ('Cancelled', 'Completed', 'TempClosed', 'ProductLowLevel', 'OfflineOrFalseAlarm')
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
            alert_id = existing['data'][0]['id']
            await hpcl_ceg_model.DryOutDailyReport(**{"id": alert_id, 
                                           "dry_out_count": str(report_data["Grand Total"]),
                                           "dry_out_zone": dry_out_zone,
                                           "dry_out_alert_ids": all_ids_list}).modify()

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
        'CZ': 2441,
        'ECZ': 1837,
        'EZ': 1147,
        'NCZ': 2906,
        'NFZ': 1518,
        'NWFZ': 1852,
        'NWZ': 1350,
        'NZ': 1417,
        'SCZ': 2794,
        'SWZ': 2476,
        'SZ': 1895,
        'WZ': 2619
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
    summary_df = summary_df.iloc[:-1]

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
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("cris", "2")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    zone_data = await function(query=loss_query)
    zone_fuel_df = pd.DataFrame(zone_data)
    chart_path = await generate_chart(zone_fuel_df)

    supply_terminal_query_ro_count_df = await supply_terminal_wise_counts()

    bottom_3_per_zone = (
        supply_terminal_query_ro_count_df.groupby("Zone", group_keys=False)
        .apply(lambda x: x.nsmallest(3, "Count of Dryout ROs"))
        .reset_index(drop=True)
    )
    # Step 2: Sort the 36 records in descending order based on Count of Dryout ROs
    bottom_3_per_zone_sorted = bottom_3_per_zone.sort_values(
        by="Count of Dryout ROs", ascending=False
    ).reset_index(drop=True)

    # Step 3: Reassign Sl No sequentially
    bottom_3_per_zone_sorted["Sl No"] = range(1, len(bottom_3_per_zone_sorted) + 1)

    # Step 4: Reorder columns for readability
    bottom_3_per_zone_sorted = bottom_3_per_zone_sorted[
        ["Sl No", "Zone", "Supply Location (Terminal)", "Region", "Count of Dryout ROs", "Count of DryOut Outlets with Valid indent"]
    ]
    print(bottom_3_per_zone_sorted)

    # Convert DataFrame to styled HTML
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

async def lpg_top_bottom_score_plants():
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    sap_ids = [
        "2662", "2693", "2241", "2935", "2371", "2121", "2520", "2401", "2324", "2811",
        "2435", "2891", "2663", "2314", "2844", "2402", "2455", "2203", "2892", "2504",
        "2248", "2171", "2262", "2655", "2215", "2623", "2204", "2472", "2959", "2921",
        "2330", "2126", "2947", "2539", "2777", "2507", "2829", "2779", "2373", "2657",
        "2949", "2173", "2707", "2568", "2659", "2792", "2660", "2692", "2471", "2731",
        "2630", "2408", "2316", "2117", "2732"
    ]
    sap_ids_str = ", ".join([f"'{sid}'" for sid in sap_ids])
    top_query = f"""WITH plant_avg_scores AS (
                        SELECT
                            sap_id,
                            name AS "Plant Name",
                            zone AS "Zone",
                            region AS "Region",
                            AVG(score) AS avg_score
                        FROM public.performance_score_history
                        WHERE
                            bu = 'LPG'
                            AND zone != ''
                            AND region != ''
                            AND timestamp::DATE >= CASE
                                WHEN date_trunc('day', CURRENT_DATE) = date_trunc('month', CURRENT_DATE)
                                    THEN date_trunc('month', CURRENT_DATE - INTERVAL '1 month')
                                ELSE date_trunc('month', CURRENT_DATE)
                            END
                            AND timestamp::DATE < CURRENT_DATE
                            AND sap_id IN ({sap_ids_str})
                            AND name NOT ILIKE '%RO%'
                        GROUP BY sap_id, name, zone, region
                    ),
                    previous_day_scores AS (
                        SELECT
                            sap_id,
                            ROUND(AVG(score)::numeric, 2) AS prev_day_score
                        FROM public.performance_score_history
                        WHERE
                            bu = 'LPG'
                            AND timestamp::DATE = CURRENT_DATE - INTERVAL '1 day'
                        GROUP BY sap_id
                    )
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY p.avg_score DESC) AS "Sl No",
                        p."Plant Name",
                        p."Zone",
                        p."Region",
                        ROUND(p.avg_score::numeric, 2) AS "Average Score from Month start",
                        COALESCE(pd.prev_day_score, 0) AS "Previous days score"
                    FROM plant_avg_scores p
                    LEFT JOIN previous_day_scores pd
                        ON p.sap_id = pd.sap_id
                    ORDER BY p.avg_score DESC
                    LIMIT 3"""
    
    bottom_query = f"""WITH plant_avg_scores AS (
                        SELECT
                            sap_id,
                            name AS "Plant Name",
                            zone AS "Zone",
                            region AS "Region",
                            AVG(score) AS avg_score
                        FROM public.performance_score_history
                        WHERE
                            bu = 'LPG'
                            AND zone != ''
                            AND region != ''
                            AND timestamp::DATE >= CASE
                                WHEN date_trunc('day', CURRENT_DATE) = date_trunc('month', CURRENT_DATE)
                                    THEN date_trunc('month', CURRENT_DATE - INTERVAL '1 month')
                                ELSE date_trunc('month', CURRENT_DATE)
                            END
                            AND timestamp::DATE < CURRENT_DATE
                            AND sap_id IN ({sap_ids_str})
                            AND name NOT ILIKE '%RO%'
                        GROUP BY sap_id, name, zone, region
                    ),
                    previous_day_scores AS (
                        SELECT
                            sap_id,
                            ROUND(AVG(score)::numeric, 2) AS prev_day_score
                        FROM public.performance_score_history
                        WHERE
                            bu = 'LPG'
                            AND timestamp::DATE = CURRENT_DATE - INTERVAL '1 day'
                        GROUP BY sap_id
                    )
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY p.avg_score ASC) AS "Sl No",
                        p."Plant Name",
                        p."Zone",
                        p."Region",
                        ROUND(p.avg_score::numeric, 2) AS "Average Score from Month start",
                        COALESCE(pd.prev_day_score, 0) AS "Previous days score"
                    FROM plant_avg_scores p
                    LEFT JOIN previous_day_scores pd
                        ON p.sap_id = pd.sap_id
                    ORDER BY p.avg_score ASC
                    LIMIT 3"""
    lpg_avg_score_query = f"""SELECT
                            ROUND(AVG(score)::numeric, 2) AS lpg_average_score
                        FROM public.performance_score_history
                        WHERE sap_id IN ({sap_ids_str})
                        AND timestamp::DATE = CURRENT_DATE - INTERVAL '1 day'"""
    lpg_avg_score_resp = await function(query=lpg_avg_score_query)
    top_resp = await function(query=top_query)
    bottom_resp = await function(query=bottom_query)
    lpg_avg_score_resp = pd.DataFrame(lpg_avg_score_resp)
    if not lpg_avg_score_resp.empty:
        lpg_avg_score_value = lpg_avg_score_resp['lpg_average_score'].iloc[0]
    else:
        lpg_avg_score_value = None  # or 0 or 'N/A'
    top_resp = pd.DataFrame(top_resp)
    bottom_resp = pd.DataFrame(bottom_resp)
    return {"lpg_top_data": top_resp, "lpg_bottom_data": bottom_resp, "lpg_avg_score_resp": lpg_avg_score_value}

async def get_alert_data(alert_section):
    # Making sure alerts considering only after May 31st in prod
    date = urdhva_base.utilities.get_present_time()
    date_yes = helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                               date_time_format=None)
    month_start = helpers.get_time_stamp_by_delta(date_yes, days=0, with_month_start_day=True,
                                               date_time_format="%Y-%m-%d")
    date_filter = f"created_at::DATE >= '{month_start}' AND created_at::DATE <= '{date_yes.strftime('%Y-%m-%d')}'" # As per HPCL request changed the date to be in the present month
    query = f"""SELECT count(alert_section), bu, alert_section, severity FROM alerts where alert_status='Open' and 
    alert_section='{alert_section}' and {date_filter} GROUP BY bu, alert_section, severity"""
    if alert_section in ["VTS"]:
        query = f"""SELECT count(alert_section), bu, alert_section, severity FROM alerts where vehicle_unblocked_date is null and 
                    alert_section='{alert_section}' and {date_filter} GROUP BY bu, alert_section, severity"""
    alerts = await hpcl_ceg_model.Alerts.get_aggr_data(query)
    data = {}
    for alert in alerts['data']:
        if alert["severity"] == "Critical":
            data.update({f"{alert_section.lower()}_critical_{alert['bu'].lower()}": alert["count"]})
        if alert["severity"] == "High":
            data.update({f"{alert_section.lower()}_high_{alert['bu'].lower()}": alert["count"]})
    for severity in ["critical", "high"]:
        for bu in ["lpg", "ro", "tas"]:
            if f"{alert_section.lower()}_{severity}_{bu}" not in data.keys():
                data.update({f"{alert_section.lower()}_{severity}_{bu}": 0})
    return data


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

    status_data.update(await fetch_sales_data())
    # print("status_data before :", status_data)
    status_data.update(await fetch_dryout_data())
    status_data.update(await get_lpg_rejection())
    status_data.update(await get_ro_alerts())
    status_data.update(await get_tas_alerts())
    #status_data.update(await get_vts_route_deviation())
    status_data.update(await lpg_top_bottom_score_plants())

    for alert_section in ["VA", "VTS", "EMLock", "TAS"]:
        status_data.update(await get_alert_data(alert_section))
    # print("-" * 50)
    # print("status_data :", json.dumps(status_data))
    # print("-" * 50)
    # print("-------->status_data",status_data)
    await send_notification(
        template_name="seg1.html",
        to_recipients=["debeshp@hpcl.in","sanjayk@hpcl.in"],
        subject="Novex Daily Report: LPG/SOD/Retail",
        cc_recipients=["gargam@hpcl.in","vikas.kaushal@hpcl.in","amitra@hpcl.in","arvindsingh@hpcl.in"],
        bcc_recipients=["cvmallinath@hpcl.in"],
        notification_data=status_data,
        inline_images={
            "dry_out_lost": f"{chart_path}"
        },
        attachments = [zone_wise_pdf_path]
    )
    await send_notification(
        template_name="seg2.html",
        to_recipients=["abalaji@hpcl.in"],
        subject="Novex Daily Report: Retail",
        cc_recipients=["anujjain@hpcl.in","shubhra.Narayan@hpcl.in"],
        bcc_recipients=["sachinkwarghane@hpcl.in","purushm@hpcl.in","debeshp@hpcl.in","adityapandey@hpcl.in"],
        notification_data=status_data,
        inline_images={
            "dry_out_lost": f"{chart_path}"
        },
        attachments = [zone_wise_pdf_path]
    )
    await send_notification(
        template_name="seg3.html",
        to_recipients=["adsul@hpcl.in","gbala@hpcl.in"],
        subject="Novex Daily Report: LPG",
        cc_recipients=["kapild@hpcl.in","sanjayk@hpcl.in","gargam@hpcl.in"],
        bcc_recipients=["sachinkwarghane@hpcl.in","purushm@hpcl.in","debeshp@hpcl.in","adityapandey@hpcl.in"],
        notification_data=status_data
    )
    await send_notification(
        template_name="seg4.html",
        to_recipients=["dramarao@hpcl.in"],
        subject="Novex Daily Report: SOD",
        cc_recipients=["subodh@hpcl.in"],
        bcc_recipients=["sachinkwarghane@hpcl.in","purushm@hpcl.in","debeshp@hpcl.in","adityapandey@hpcl.in"],
        notification_data=status_data,
        attachments = [zone_wise_pdf_path]
    )
    await send_notification(
        template_name="seg5.html",
        to_recipients=["sreedhar.maddipati@algofusiontech.com"],
        subject="Novex Daily Report: LPG/SOD/Retail",
        cc_recipients=["venu@algofusiontech.com", "santoshkumar.s@algofusiontech.com", "moufikali@algofusiontech.com", "aditya@algofusiontech.com"],
        bcc_recipients=["yesu.p@algofusiontech.com"],
        notification_data=status_data,
        inline_images={
            "dry_out_lost": f"{chart_path}"
        },
        attachments = [zone_wise_pdf_path]
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
    asyncio.run(publish_daily_novex_status_email())
