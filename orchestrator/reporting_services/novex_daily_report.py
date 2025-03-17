import urdhva_base
import os
import ast
import json
import jinja2
import asyncio
import datetime
import hpcl_ceg_model
import urdhva_base.utilities
from types import SimpleNamespace
import utilities.helpers as helpers
import dateutil.parser as dt_parser
import utilities.fiscal_year as fiscal_year
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
import orchestrator.analytics.m60_performance as m60_performance
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
from api_manager.indentdryout_actions import indentdryout_get_dried_out_ro
import orchestrator.notification_manager.notification_factory as notification_factory

actual = {"key": "\"A\"", "cond": "equals", "value": "true"}
history = {"key": "\"H\"", "cond": "equals", "value": "true"}
target = {"key": "\"T\"", "cond": "equals", "value": "true"}
ytd = {"key": "\"YTD\"", "cond": "equals", "value": "true"}
ytpm = {"key": "\"YTDPM\"", "cond": "equals", "value": "true"}
cumulative = {"key": "\"C\"", "cond": "equals", "value": "true"}


def get_growth_percentage(current, hist):
    """
    Function to calculate growth percentage
    :param current:
    :param hist:
    :return:
    """
    if current and hist:
        return round(((current - hist) / hist) * 100, 1)
    elif current and not hist:
        return 100
    elif not current and hist:
        return -100
    else:
        return 0


async def fetch_sales_data():
    sales_data = {}
    # Filter for YTD
    filters = {"filters": [actual, history, cumulative, ytd, target], "cross_filters": [],
               "drill_state": ""}
    resp = await m60_performance.m60_performance(**filters)
    sales_data['current_sales'] = round(float(resp['data']['data']['ACTUAL_TMT_SALES'][0]), 1)
    sales_data['pro_rate_sales'] = round(float(resp['data']['data']['TARGET_TMT_SALES'][0]), 1)

    # Filter for yesterday's data
    yesterday_date = helpers.get_time_stamp_by_delta(datetime.datetime.now(datetime.timezone.utc), days=1,
                                                     with_month_start_day=False, date_time_format="%Y-%m-%d")
    filters = {"filters": [actual, history, cumulative,
                           {"key": "\"DATE\"", "cond": "equals", "value": f"{yesterday_date},{yesterday_date}"}],
               "cross_filters": [], "drill_state": ""}
    resp = await m60_performance.m60_performance(**filters)
    yesterday_act = float(resp['data']['data']['ACTUAL_TMT_SALES'][0])
    yesterday_hist = float(resp['data']['data']['ACTUAL_HISTORY_TMT_SALES'][0])
    sales_data['yesterday_growth_loss'] = round(yesterday_act - yesterday_hist, 1)
    # ((CY sales-PY sales)/PY sales)*100
    sales_data['yesterday_growth_loss_percentage'] = get_growth_percentage(yesterday_act, yesterday_hist)
    final_data = {"sales_data": sales_data}

    sbu_mapping = {'': '', "Retail": 'retail', 'LPG': 'lpg', 'I&C': 'i_c', 'Lubes': 'lubes', 'Aviation': 'aviation',
                   'PETCHEM': 'petchem', 'GAS': 'gas'}
    for sbu_name, map_key in sbu_mapping.items():
        sbu_filter = {}
        if sbu_name:
            sbu_filter = {"key": "\"SBU_Name\"", "cond": "equals", "value": f"{sbu_name}"}
        sbu_sales_data = {}
        # Filter for today's data
        today_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        filters = {"filters": [actual, history, cumulative,
                               {"key": "\"DATE\"", "cond": "equals", "value": f"{today_date},{today_date}"}],
                   "cross_filters": [], "drill_state": ""}
        if sbu_filter:
            filters['filters'].append(sbu_filter)
        resp = await m60_performance.m60_performance(**filters)
        print(filters)
        print(resp)
        current = float(resp['data']['data']['ACTUAL_TMT_SALES'][0])
        hist = float(resp['data']['data']['ACTUAL_HISTORY_TMT_SALES'][0])
        sbu_sales_data['today_current'] = round(current, 1)
        sbu_sales_data['today_historical'] = round(hist, 1)
        sbu_sales_data['today_growth'] = get_growth_percentage(current, hist)

        # For current month data
        month_start = helpers.get_time_stamp_by_delta(with_month_start_day=True)
        filters = {"filters": [actual, history, cumulative,
                               {"key": "\"DATE\"", "cond": "equals", "value": f"{month_start},{today_date}"}],
                   "cross_filters": [], "drill_state": ""}
        if sbu_filter:
            filters['filters'].append(sbu_filter)
        resp = await m60_performance.m60_performance(**filters)
        present_month_act = float(resp['data']['data']['ACTUAL_TMT_SALES'][0])
        present_month_hist = float(resp['data']['data']['ACTUAL_HISTORY_TMT_SALES'][0])
        sbu_sales_data['present_month_historical'] = round(present_month_hist, 1)
        sbu_sales_data['present_month_current'] = round(present_month_act, 1)
        sbu_sales_data['present_month_growth'] = get_growth_percentage(present_month_act, present_month_hist)

        # For ytpm data
        filters = {"filters": [actual, history, ytpm, cumulative], "cross_filters": [], "drill_state": ""}
        if sbu_filter:
            filters['filters'].append(sbu_filter)
        resp = await m60_performance.m60_performance(**filters)
        ytpm_act = float(resp['data']['data']['ACTUAL_TMT_SALES'][0])
        ytpm_hist = float(resp['data']['data']['ACTUAL_HISTORY_TMT_SALES'][0])
        sbu_sales_data['ytpm_historical'] = round(ytpm_hist, 1)
        sbu_sales_data['ytpm_current'] = round(ytpm_act, 1)
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


async def fetch_dryout_data():
    payload_dict = {
        "filters": [
            {"key": "interlock_name", "cond": "=", "value": ["Dry Out Each Indent Wise MainFlow"]}
        ]
    }
    payload_obj = dict_to_object(payload_dict)
    response = await indentdryout_get_dried_out_ro(payload_obj)
    for stat in response['stats']:
        if stat['section'] == "CATA Carry Fwd Indent":
            cat_a = stat['value']
        if stat['section'] == "DryOut Carry Fwd Indent":
            carry_fwd_dry_out = stat['value']
        if stat['section'] == "Carry Fwd Indent":
            carry_fwd_indent = stat['value']
        if stat['section'] == 'Indent Not Raised':
            indent_not_raised = stat['value']
        if stat['section'] == 'Indent Raised':
            indent_raised = stat['value']

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
    return {"dry_out_cf": dry_out_cf, "dry_out": dry_out}


async def get_lpg_rejection():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    query = f""" SELECT count(interlock_name) as total_count FROM alerts where interlock_name in ('O-Ring Leak Rejection','Valve Leak Rejection','Check Scale Rejection') and created_at>='{today}' """
    rejections = await function(query=query)
    if rejections:
        return {"lpg_critical": rejections[-1]["total_count"], "lpg_high": 0}
    return {"lpg_critical": 0, "lpg_high": 0}


async def get_ro_alerts():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    query = f""" SELECT count(interlock_name) as total_count, severity FROM alerts where bu='RO' and created_at>='{today}' and alert_status='Open' GROUP BY severity; """
    alerts = await function(query=query)
    data = {}
    if alerts:
        for alert in alerts:
            if alert["severity"] == "Critical":
                data = {"ro_critical": alert["total_count"]}
            if alert["severity"] == "High":
                data = {"ro_high": alert["total_count"]}
    for key in ["ro_critical", "ro_high"]:
        if key not in data.keys():
            data.update({key: 0})
    return data


async def get_tas_alerts():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    query = f""" SELECT count(interlock_name) as total_count, severity FROM alerts where bu='TAS' and created_at>='{today}' and alert_status='Open' GROUP BY severity; """
    alerts = await function(query=query)
    data = {}
    if alerts:
        for alert in alerts:
            if alert["severity"] == "Critical":
                data = {"tas_critical": alert["total_count"]}
            if alert["severity"] == "High":
                data = {"tas_high": alert["total_count"]}
    for key in ["tas_critical", "tas_high"]:
        if key not in data.keys():
            data.update({key: 0})
    return data


async def get_alert_data(alert_section):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    query = f""" SELECT count(alert_section), bu, alert_section, severity FROM alerts where alert_status='Open' and alert_section='{alert_section}' and created_at>='{today}' GROUP BY bu, alert_section, severity; """
    alerts = await function(query=query)
    data = {}
    for alert in alerts:
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
    template_path = os.path.join(os.path.dirname(hpcl_ceg_model.__file__), '..', 'orchestrator', 'masterdata',
                                 'novex_daily_email.html')
    date = urdhva_base.utilities.get_present_time()
    status_data = {'today_date': date.strftime('%d-%B-%Y'),
                   'today_week': date.strftime('%A'),
                   'today': date.strftime('%d-%B-%Y'),
                   'present_month': f"01-{date.strftime('%b')} to {date.strftime('%d')}-{date.strftime('%b')}"}
    status_data.update(await fetch_sales_data())
    print("status_data before :", status_data)
    status_data.update(await fetch_dryout_data())
    status_data.update(await get_lpg_rejection())
    status_data.update(await get_ro_alerts())
    status_data.update(await get_tas_alerts())

    for alert_section in ["VA", "VTS", "EMLock"]:
        status_data.update(await get_alert_data(alert_section))
    print("-" * 50)
    print("status_data :", json.dumps(status_data))
    print("-" * 50)

    with open(template_path, 'r') as f:
        template_data = jinja2.Template(f.read())
    final_data = template_data.render(**status_data)
    with open(f'/tmp/novex_daily_email.html', 'w') as f:
        f.write(final_data)
    # Send email
    ins = notification_factory.get_notification_module("email")
    resp = await ins.publish_message(
        subject="Novex Daily Report",
        recipients=["venualgofusiontech.com"],
        html_content=True,
        body=final_data,
        force_send=True
    )
    print(resp)


if __name__ == "__main__":
    asyncio.run(publish_daily_novex_status_email())
