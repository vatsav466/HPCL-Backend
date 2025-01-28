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

# HistoryKeyMapping = {'SBU_Name': '"ORGSBUNAME"', 'Zone_Name': '"ORGZONENAME"', 'Region_Name': '"ORGRONAME"',
#                      'SalesArea_Name': '"ORGSANAME"'}
# Base_Filters = ['"month_name"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"', '"ProductName"']
Base_Filters = ['"month_name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"', '"ProductName"']
Lubes_Filters = ['"month_name"', '"SBU_Name"', '"Region_Name"', '"SalesArea_Name"', '"ProductName"']
Default_Filters = [""""SBU_Name" != '0'""", """"Zone_Name" != '-'"""]
DBNames = {"m60_ta": "M60_LEVEL_METADATA", "ind_h": "industry_performance","ind_act": "industry_performance"}
months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
sbu_order = ['Retail', 'LPG', 'I&C', 'Lubes', 'Aviation', 'PETCHEM', 'NG']
DefaultTable = 'Day'
# MandateKeys = {"actual": "ACTUAL_TMT_SALES", "history": "IND_ACTUAL_HISTORY_TMT_SALES", "target": "TARGET_TMT_SALES"}
MandateKeys = {"actual": "IND_ACTUAL_TMT_SALES", "history": "IND_ACTUAL_HISTORY_TMT_SALES"}



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
    if DefaultTable == "Day":
        return [], [[dt_parser.parse(start_date).strftime(day_resp_format),
                     dt_parser.parse(end_date).strftime(day_resp_format)]]
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
        dt = helpers.get_time_stamp_by_delta(end_dt, months=1, ascending=False, date_time_format=None)
        _, month_days = monthrange(dt.year, dt.month)
        dt = dt.replace(day=month_days)
        filter_dates.append([helpers.get_time_stamp_by_delta(start_dt, months=1, ascending=True,
                                                             date_time_format=None).strftime(resp_format),
                             dt.strftime(resp_format)])
    return filter_dates, day_filter_dates


# def calculate_pro_rate(target_data, key, start_month=None, end_month=None):
#     """
#     Calculating YTD data for target
#     :param target_data:
#     :param key:
#     :param start_month:
#     :param end_month:
#     :return:
#     """
#     if not start_month and not end_month:
#         return target_data
#     if start_month:
#         # Calculate no of days the start month
#         dt = dt_parser.parse(start_month)
#         _, month_days = monthrange(dt.year, dt.month)
#         pending_days = month_days - dt.day + 1
#         for rec in target_data:
#             if helpers.month_short_to_number(rec['month_name']) == dt.month:
#                 rec[key] = round((rec[key] / month_days) * pending_days)
#     # validate month:
#     if end_month:
#         # Calculate no of days the end month
#         dt = dt_parser.parse(end_month)
#         _, month_days = monthrange(dt.year, dt.month)
#         pending_days = dt.day
#         for rec in target_data:
#             if helpers.month_short_to_number(rec['month_name']) == dt.month:
#                 rec[key] = round((rec[key] / month_days) * pending_days)
#     return target_data


async def collect_data(req_keys, table_name, where_conditions, start_date, end_date, group_by_filter,
                       date_key='"year_monthname"::DATE', year_key='"fiscal_year"'): # added year_key
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
        # else:
        #     conditions.append(f""" {date_key} BETWEEN '{start_date}' AND '{end_date}' """)
        else:
            conditions.append(f""" {year_key} = '{start_date}-{end_date}' """)
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


def get_group_by_filter_key(cross_filters):
    """
    Getting group by filter key based on cross filters
    :param cross_filters:
    :return:
    """
    print("cross_filters --> ", cross_filters)
    group_by_filter = '"month_name"' # added Company_Name key for the company wise grouping
    if cross_filters:
        print(" if cross_filters --> ", cross_filters)
        index = 0
        if len([rec['value'] for rec in cross_filters if 'lubes' in rec['value'].lower()
                                                         and rec['key'].strip('"') == "SBU_Name"]):
            print(" into if cross_filters --> ", cross_filters)                                                         
            for key in [rec['key'] for rec in cross_filters]:
                print(" into for key --> ", key)
                if key in Lubes_Filters and Lubes_Filters.index(key) > index:
                    print(" into if key --> ", key)
                    index = Lubes_Filters.index(key)
                    print(" into if index --> ", index)
            group_by_filter = Lubes_Filters[index + 1]
            print(" into if group_by_filter --> ", group_by_filter)
        else:
            print(" into else cross_filters --> ", cross_filters)
            for key in [rec['key'] for rec in cross_filters]:
                print(" into else key --> ", key)
                if key in Base_Filters and Base_Filters.index(key) > index:
                    print(" into else key --> ", key)
                    index = Base_Filters.index(key)
                    print(" into else index --> ", index)
            group_by_filter = Base_Filters[index + 1]
            print(" into else group_by_filter --> ", group_by_filter)
    return group_by_filter


async def industry_performance(filters, cross_filters, drill_state):
    if not cross_filters:
        cross_filters = []
    group_by_filter = get_group_by_filter_key(cross_filters)

    # Assigning empty variables
    # history = actual = target = start_date = end_date = start_date_history = end_date_history = ""
    history = actual = start_date = end_date = start_date_history = end_date_history = ""

    end_date = fiscal_year.FiscalYear.current().fiscal_year_end_date
    start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date

    # For Current Year and History Year removed FY format for the query 
    curr_year = str(fiscal_year.FiscalYear.current()).strip('FY')
    his_year = str(fiscal_year.FiscalYear.current().prev_fiscal_year).strip('FY')
    
    # For History
    start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime("%Y%m%d")
    end_date_history = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date), years=1, days=0,
                                                       with_month_start_day=False,
                                                       date_time_format=None).strftime("%Y%m%d")

    for index, _ in enumerate(cross_filters):
        cross_filters[index]['key'] = cross_filters[index]['key'].strip('"')
    cross_filters = [rec for rec in cross_filters if not (rec['key'] == 'month_name' and not rec['value'].strip('"'))]
    actual_data = []
    hist_data = []
    #target_data = []
    actual_d = """ ROUND(SUM("industry_performance"."NETWEIGHT_TMT")::numeric,0) AS "IND_ACTUAL_TMT_SALES" """
    history_d = """ ROUND(SUM("industry_performance"."NETWEIGHT_TMT")::numeric,0) AS "IND_HISTORY_TMT_SALES" """
    filters_req = [condition['key'].strip('"') for condition in filters if condition['key'].strip('"') in ["A", "H", "T"]]
    if len(filters_req) == 0:
        filters.append({"key": '"A"', "cond": "equals", "value": "true"})
    # Generating filters
    for condition in filters:
        if condition['key'].strip('"') == "A":
            actual = f"""ROUND(SUM("{DBNames['ind_act']}"."NETWEIGHT_TMT")::numeric,0) AS "IND_ACTUAL_TMT_SALES" """
        elif condition['key'].strip('"') == "H":
            history = f"""ROUND(SUM("{DBNames['ind_h']}"."NETWEIGHT_TMT")::numeric,0) AS "IND_ACTUAL_HISTORY_TMT_SALES" """
        #elif condition['key'].strip('"') == "T":
        #    target = f""" ROUND(SUM("{DBNames['m60_ta']}"."TARGET_QTY_TMT")::numeric,0) AS "TARGET_TMT_SALES" """
        elif condition['key'].strip('"') == "YTD":
            # Calculating start and end dates for YTD for both actual and history
            end_date_ = fiscal_year.FiscalDate.today()
            end_date = end_date_.replace(day=end_date_.day-1).strftime("%Y-%m-%d")
            start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
            # For History
            start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
            end_date_history = helpers.get_time_stamp_by_delta(end_date_, years=1, days=1, with_month_start_day=False,
                                                               date_time_format=None)
            end_date_history = end_date_history.strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
        elif condition['key'].strip('"') == "DATE":
            # Calculating start and end dates
            start_date, end_date = condition['value'].split(",")
            start_date_history = dt_parser.parse(start_date)
            start_date_history = start_date_history.replace(year=start_date_history.year-1).strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
            # For History
            end_date_history = dt_parser.parse(end_date)
            end_date_history = end_date_history.replace(year=end_date_history.year-1).strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
        elif condition['key'] == '"FISCAL_YEAR"':
            # Not considering now
            ...
        else:
            # Clearing if value was an empty string
            if not condition["value"]:
                continue
            condition["key"] = condition["key"].strip('"')
            if condition["key"] == "month_name":
                value = [mnt_name.strip() for mnt_name in condition["value"].split(",")]
                cross_filter_append = True
                for crs_rec in cross_filters:
                    if crs_rec["key"] == "month_name":
                        if len(value) == 1:
                            crs_rec["value"] = value[0]
                        else:
                            crs_rec["value"] = value
                            crs_rec["cond"] = ' '
                        cross_filter_append = False
                if cross_filter_append:
                    if len(value) > 1:
                        condition["cond"] = ' '
                        condition["value"] = value
                    cross_filters.append(condition)
            else:
                cross_filters.append(condition)
    where_conditions = []
    clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters)
    if clause:
        where_conditions = [clause]
    # For history table
    for rec in cross_filters:
        rec['key'] = rec['key'].strip('"')

    where_conditions_history = []
    clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters)
    if clause:
        where_conditions_history = [clause]
    '''
    # Data Retrival for target data
    if target:
        group_keys = [group_by_filter]
        if group_by_filter.strip('"') != "month_name":
            group_keys.append("month_name")
        target_data = await collect_data([target, 'month_name'], 'M60_LEVEL_METADATA',
                                         where_conditions+Default_Filters, start_date, end_date, group_keys)
        # print(json.dumps(target_data, default=str))
        if target_data:
            target_data = pd.DataFrame(calculate_pro_rate(target_data, "TARGET_TMT_SALES", start_date, end_date))
            target_data = target_data.groupby(group_by_filter.strip('"'))['TARGET_TMT_SALES'].sum().reset_index()
            if group_by_filter == 'month_name':
                target_data['month_name'] = pd.CategoricalIndex(target_data['month_name'], ordered=True, categories=months)
            target_data = target_data.to_dict(orient='records')
    '''
    
    
    
    # Data Retrival for current financial year
    if actual:
        # Checking whether start date and end date enabled
        filter_dates = []
        day_filter_dates = []
        if start_date and end_date:
            filter_dates, day_filter_dates = await get_date_filters(start_date, end_date)
        else:
            if DefaultTable == "Day":
                day_filter_dates.append([start_date, end_date])
            else:
                filter_dates.append([start_date, end_date])
        # For Month level aggregations from month data table
        # for date_range in filter_dates:
        #     actual_data.extend(await collect_data([actual], 'industry_performance',
        #                                           where_conditions+Default_Filters, date_range[0], date_range[1],
        #                                           [group_by_filter]))

        # # For Month level aggregations from day wise data table
        # # Todo:- for optimization use single query for day filter with or condition
        # for date_range in day_filter_dates:
        #     actual_data.extend(await collect_data([actual_d], 'industry_performance',
        #                                           where_conditions + Default_Filters, date_range[0], date_range[1],
        #                                           [group_by_filter], '"DAY_ID"'))
        
        # For Year level aggregations                                                   
        actual_data.extend(await collect_data([actual], 'industry_performance',
                                                  where_conditions, his_year, curr_year,
                                                  [group_by_filter]))

        if actual_data:
            actual_data = pd.DataFrame(actual_data)
            actual_data = actual_data.groupby(group_by_filter.strip('"'))['IND_ACTUAL_TMT_SALES'].sum().reset_index()
            actual_data['IND_ACTUAL_TMT_SALES'] = actual_data['IND_ACTUAL_TMT_SALES'].fillna(0)
            actual_data = actual_data.to_dict(orient='records')

    # Data Retrival for last financial year
    if history:
        filter_dates = []
        day_filter_dates = []
        if start_date and end_date:
            filter_dates, day_filter_dates = await get_date_filters(start_date_history, end_date_history, "%Y%m")
        else:
            if DefaultTable == "Day":
                day_filter_dates.append([start_date_history, end_date_history])
            else:
                filter_dates.append([start_date_history, end_date_history])
        # for date_range in filter_dates:
        #     hist_data.extend(await collect_data([history], 'industry_performance',
        #                                         where_conditions_history + Default_Filters, date_range[0],
        #                                         date_range[1], [group_by_filter], '"YEARMONTH"'))
        '''
        # Todo:- for optimization use single query for day filter with or condition
        for date_range in day_filter_dates:
            hist_data.extend(await collect_data([history_d], 'industry_performance',
                                                where_conditions_history + Default_Filters, date_range[0],
                                                date_range[1], [group_by_filter], '"DAY_ID"'))
        '''
        hist_data.extend(await collect_data([history], 'industry_performance',
                                                  where_conditions_history, his_year, curr_year,
                                                  [group_by_filter]))
        if hist_data:
            hist_data = pd.DataFrame(hist_data)
            hist_data = hist_data.groupby(group_by_filter.strip('"'))['IND_ACTUAL_HISTORY_TMT_SALES'].sum().reset_index()
            hist_data['IND_ACTUAL_HISTORY_TMT_SALES'] = hist_data['IND_ACTUAL_HISTORY_TMT_SALES'].fillna(0)
            hist_data = hist_data.to_dict(orient='records')

    #df_ = [pd.DataFrame(d) for d in [actual_data, target_data, hist_data] if d]
    df_ = [pd.DataFrame(d) for d in [actual_data, hist_data] if d]
    merged_df = df_[0] if len(df_) else pd.DataFrame([])
    if len(df_) > 1:
        for df in df_[1:]:
            merged_df = pd.merge(merged_df, df, on=group_by_filter.strip('"'), how='outer')  # Outer merge with df2
    # Ordering Data for Month and SBU names
    if not merged_df.empty and group_by_filter.strip('"') in ('month_name', 'SBU_Name'):
        sort_key = months if group_by_filter.strip('"') == 'month_name' else sbu_order
        merged_df["data_order"] = merged_df[group_by_filter.strip('"')].map({cond: i for i, cond in enumerate(sort_key)})
        merged_df = merged_df.sort_values("data_order").drop(columns="data_order")
        merged_df = merged_df[merged_df[group_by_filter.strip('"')].isin(sort_key)]
        merged_df.reset_index(drop=True, inplace=True)
    # If required keys not available keeping records with zero value
    # if target:
    #     if MandateKeys["target"] not in merged_df:
    #         merged_df[MandateKeys["target"]] = 0
    if actual:
        if MandateKeys["actual"] not in merged_df:
            merged_df[MandateKeys["actual"]] = 0
    if history:
        if MandateKeys["history"] not in merged_df:
            merged_df[MandateKeys["history"]] = 0
    if group_by_filter and group_by_filter.strip('"') not in merged_df:
        merged_df[group_by_filter.strip('"')] = ""
    merged_df.fillna(0, inplace=True)
    final_resp = {key: value.to_dict() for key, value in merged_df.to_dict(orient='series').items()}
    return {"status": True, "message": "Success", "data": final_resp}
