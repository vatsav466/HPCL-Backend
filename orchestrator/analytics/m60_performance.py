import urdhva_base
import json
import pandas as pd
from calendar import monthrange
import utilities.helpers as helpers
import dateutil.parser as dt_parser
import utilities.fiscal_year as fiscal_year
import utilities.connection_mapping as connection_mapping
from orchestrator.dbconnector.widget_actions import widget_actions
import orchestrator.dbconnector.connector_factory as connector_factory
from api_manager.charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams

HistoryKeyMapping = {'SBU_Name': '"ORGSBUNAME"', 'Zone_Name': '"ORGZONENAME"', 'Region_Name': '"ORGRONAME"',
                     'SalesArea_Name': '"ORGSANAME"'}
Base_Filters = ['"month_name"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"', '"ProductName"']
Default_Filters = [""""SBU_Name" != '0'""", """"Zone_Name" != '-'"""]
DBNames = {"m60_ta": "M60_LEVEL_METADATA", "m60_h": "MOM_LEVEL_FINAL_DATA"}
months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
sbu_order = ['Retail', 'LPG', 'I&C', 'Lubes', 'Aviation', 'PETCHEM', 'NG']


async def get_date_filters(start_date, end_date, resp_format='%Y-%m-%d', day_resp_format="%Y%m%d"):
    """
    Function to get multiple date filters for day level filter, month level filter
    :param start_date:
    :param end_date:
    :param resp_format:
    :return:
    """
    filter_dates = []
    day_filter_dates = []
    start_dt = dt_parser.parse(start_date)
    end_dt = dt_parser.parse(end_date)
    if start_dt.month == end_dt.month or (end_dt.month - start_dt.month) == 1:
        filter_dates.append([start_date, end_date])
    else:
        _, month_days = monthrange(start_dt.year, start_dt.month)
        day_filter_dates.append([start_dt.strftime(day_resp_format),
                                 start_dt.replace(day=month_days).strftime(day_resp_format)])
        _, month_days = monthrange(end_dt.year, end_dt.month)
        day_filter_dates.append([end_dt.replace(day=1).strftime(day_resp_format), end_dt.strftime(day_resp_format)])
        filter_dates.append([helpers.get_time_stamp_by_delta(start_dt, months=1, ascending=True,
                                                             date_time_format=None).strftime(resp_format),
                             helpers.get_time_stamp_by_delta(end_dt, months=1, ascending=False,
                                                             date_time_format=None).strftime(resp_format)])
    return filter_dates, day_filter_dates


def calculate_pro_rate(target_data, key, start_month=None, end_month=None):
    """
    Calculating YTD data for target
    :param target_data:
    :param key:
    :param start_month:
    :param end_month:
    :return:
    """
    if not start_month and not end_month:
        return target_data
    if start_month:
        # Calculate no of days the start month
        dt = dt_parser.parse(start_month)
        _, month_days = monthrange(dt.year, dt.month)
        pending_days = month_days - dt.day + 1
        for rec in target_data:
            if helpers.month_short_to_number(rec['month_name']) == dt.month:
                rec[key] = round((rec[key] / month_days) * pending_days)
    # validate month:
    if end_month:
        # Calculate no of days the end month
        dt = dt_parser.parse(end_month)
        _, month_days = monthrange(dt.year, dt.month)
        pending_days = dt.day
        for rec in target_data:
            if helpers.month_short_to_number(rec['month_name']) == dt.month:
                rec[key] = round((rec[key] / month_days) * pending_days)
    return target_data


async def collect_data(req_keys, table_name, where_conditions, start_date, end_date, group_by_filter,
                       date_key='"year_monthname"::DATE'):
    if group_by_filter and not isinstance(group_by_filter, list):
        group_by_filter = [group_by_filter]
    for grp_key in group_by_filter:
        if grp_key.strip('"') not in req_keys and grp_key not in req_keys:
            req_keys.append(grp_key)
    query = f"""SELECT {','.join(req_keys)} FROM "{table_name}" """
    conditions = [cond for cond in where_conditions]
    if start_date and end_date:
        if start_date == end_date:
            conditions.append(f""" {date_key}='{start_date}' """)
        else:
            conditions.append(f""" {date_key} BETWEEN '{start_date}' AND '{end_date}' """)
    if conditions:
        query += f' where {" AND ".join(conditions)}'
    if group_by_filter:
        query += f" GROUP BY {','.join(group_by_filter)}"
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    print("-" * 30)
    print(query)
    print("-" * 30)
    resp = await function(query=query)
    return resp


async def m60_performance(filters, cross_filters, drill_state):
    group_by_filter = '"month_name"'
    if not cross_filters:
        cross_filters = []
    if len(cross_filters):
        index = 0
        for key in [rec['key'] for rec in cross_filters]:
            if key in Base_Filters and Base_Filters.index(key) > index:
                index = Base_Filters.index(key)
        group_by_filter = Base_Filters[index + 1]
    # Assigning empty variables
    history = actual = target = start_date = end_date = start_date_history = end_date_history = ""
    for index, _ in enumerate(cross_filters):
        cross_filters[index]['key'] = cross_filters[index]['key'].strip('"')
    actual_data = []
    hist_data = []
    target_data = []
    actual_d = """ ROUND(SUM("MOM_DAY_LEVEL_DATA"."NETWEIGHT_TMT")::numeric,0) AS "ACTUAL_TMT_SALES" """
    history_d = """ ROUND(SUM("MOM_DAY_LEVEL_DATA"."NETWEIGHT_TMT")::numeric,0) AS "ACTUAL_HISTORY_TMT_SALES" """
    # Generating filters
    for condition in filters:
        if condition['key'].strip('"') == "A":
            actual = f"""ROUND(SUM("{DBNames['m60_ta']}"."NETWEIGHT_TMT")::numeric,0) AS "ACTUAL_TMT_SALES" """
        elif condition['key'].strip('"') == "H":
            history = f"""ROUND(SUM("{DBNames['m60_h']}"."NETWEIGHT_TMT")::numeric,0) AS "ACTUAL_HISTORY_TMT_SALES" """
        elif condition['key'].strip('"') == "T":
            target = f""" ROUND(SUM("{DBNames['m60_ta']}"."TARGET_QTY_TMT")::numeric,0) AS "TARGET_TMT_SALES" """
        elif condition['key'].strip('"') == "YTD":
            # Calculating start and end dates for YTD for both actual and history
            end_date_ = fiscal_year.FiscalDate.today()
            end_date = end_date_.replace(day=end_date_.day-1).strftime("%Y-%m-%d")
            start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
            # For History
            start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime("%Y%m%d")
            end_date_history = helpers.get_time_stamp_by_delta(end_date_, years=1, days=1, with_month_start_day=False,
                                                               date_time_format=None)
            end_date_history = end_date_history.strftime("%Y%m%d")
        elif condition['key'].strip('"') == "DATE":
            # Calculating start and end dates
            start_date, end_date = condition['value'].split(",")
            start_date_history = dt_parser.parse(start_date)
            start_date_history = start_date_history.replace(year=start_date_history.year-1).strftime("%Y%m")
            # For History
            end_date_history = dt_parser.parse(end_date)
            end_date_history = end_date_history.replace(year=end_date_history.year-1).strftime("%Y%m")
        elif condition['key'] == '"FISCAL_YEAR"':
            # Not considering now
            fis_year = condition['value']
        else:
            condition["key"] = condition["key"].strip('"')
            cross_filters.append(condition)
    m60_df = []
    where_conditions = []
    clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters)
    if clause:
        where_conditions = [clause]
    # For history table
    for rec in cross_filters:
        rec['key'] = rec['key'].strip('"')
        # rec['key'] = HistoryKeyMapping.get(rec['key'].strip(), rec['key'].strip()).strip('"')

    where_conditions_history = []
    clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters)
    if clause:
        where_conditions_history = [clause]

    if target:
        group_keys = [group_by_filter]
        if group_by_filter.strip('"') != "month_name":
            group_keys.append("month_name")
        target_data = await collect_data([target, 'month_name'], 'M60_LEVEL_METADATA',
                                         where_conditions+Default_Filters, start_date, end_date, group_keys)
        print(json.dumps(target_data, default=str))
        target_data = pd.DataFrame(calculate_pro_rate(target_data, "TARGET_TMT_SALES", start_date, end_date))
        target_data = target_data.groupby(group_by_filter.strip('"'))['TARGET_TMT_SALES'].sum().reset_index()
        if group_by_filter == 'month_name':
            target_data['month_name'] = pd.CategoricalIndex(target_data['month_name'], ordered=True, categories=months)
        target_data = target_data.to_dict(orient='records')
        print(json.dumps(target_data, default=str))
    if actual:
        # Checking whether start date and end date enabled
        filter_dates = []
        day_filter_dates = []
        if start_date and end_date:
            filter_dates, day_filter_dates = await get_date_filters(start_date, end_date)
        else:
            filter_dates.append([start_date, end_date])
        # For Month level aggregations from month data table
        for date_range in filter_dates:
            actual_data.extend(await collect_data([actual], 'M60_LEVEL_METADATA',
                                                  where_conditions+Default_Filters, date_range[0], date_range[1],
                                                  [group_by_filter]))
        # For Month level aggregations from day wise data table
        # Todo:- for optimization use single query for day filter with or condition
        for date_range in day_filter_dates:
            actual_data.extend(await collect_data([actual_d], 'MOM_DAY_LEVEL_DATA',
                                                  where_conditions + Default_Filters, date_range[0], date_range[1],
                                                  [group_by_filter], '"DAY_ID"'))
        print(" Actual Data")
        print("&" * 30)
        print(json.dumps(actual_data, default=str))
        print("&" * 30)
    if history:
        filter_dates = []
        day_filter_dates = []
        if start_date and end_date:
            filter_dates, day_filter_dates = await get_date_filters(start_date_history, end_date_history, "%Y%m")
        else:
            filter_dates.append([start_date_history, end_date_history])
        for date_range in filter_dates:
            hist_data.extend(await collect_data([history], 'MOM_LEVEL_FINAL_DATA',
                                                where_conditions_history, date_range[0], date_range[1],
                                                [group_by_filter], '"YEARMONTH"'))
        # Todo:- for optimization use single query for day filter with or condition
        for date_range in day_filter_dates:
            hist_data.extend(await collect_data([history_d], 'MOM_DAY_LEVEL_DATA',
                                                where_conditions_history, date_range[0], date_range[1],
                                                [group_by_filter], '"DAY_ID"'))
        print(" Historical Data")
        print("^" * 30)
        print(json.dumps(hist_data, default=str))
        print("^" * 30)
    # df = pd.concat([actual_data, target_data, hist_data])
    df_ = [pd.DataFrame(d) for d in [actual_data, target_data, hist_data] if d]
    merged_df = df_[0]
    if group_by_filter.strip('"') == 'month_name':
        if len(df_) > 1:
            for df in df_[1:]:
                merged_df = pd.merge(merged_df, df, on='month_name', how='outer')  # Outer merge with df2
        merged_df.fillna(0, inplace=True)
        merged_df["month_order"] = merged_df["month_name"].map({month: i for i, month in enumerate(months)})
        merged_df = merged_df.sort_values("month_order").drop(columns="month_order")
        merged_df.reset_index(drop=True, inplace=True)
    if group_by_filter.strip('"') == 'SBU_Name':
        if len(df_) > 1:
            for df in df_[1:]:
                merged_df = pd.merge(merged_df, df, on='SBU_Name', how='outer')  # Outer merge with df2
        merged_df["sbu_order"] = merged_df["SBU_Name"].map({month: i for i, month in enumerate(months)})
        merged_df = merged_df.sort_values("sbu_order").drop(columns="sbu_order")
        merged_df.reset_index(drop=True, inplace=True)
    return {key: value.to_dict() for key, value in merged_df.to_dict(orient='series').items()}
