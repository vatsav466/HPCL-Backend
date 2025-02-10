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
from api_manager.charts_actions import charts_get_distinct_values
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
from dashboard_studio_model import Charts_Get_Distinct_ValuesParams
HistoryKeyMapping = {'SBU_Name': '"ORGSBUNAME"', 'Zone_Name': '"ORGZONENAME"', 'Region_Name': '"ORGRONAME"',
                     'SalesArea_Name': '"ORGSANAME"'}
Base_Filters = ['"month_name"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"', '"ProductName"']
Lubes_Filters = ['"month_name"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"', '"ProductName"']
Default_Filters = [""""SBU_Name" != '0'""", """"Zone_Name" != '-'""", """ "SBU_Name" not in ('Common','Mumbai Ref','Renewable Energy','Visakh Ref')"""]
#Default_Filters = [""""SBU_Name" != '0'""", """"Zone_Name" != '-'"""]
DBNames = {"m60_ta": "M60_LEVEL_METADATA", "m60_h": "MOM_LEVEL_FINAL_DATA"}
months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']

sbu_order = ['Retail', 'LPG', 'I&C', 'Lubes', 'Aviation', 'PETCHEM', 'GAS']

DefaultTable = 'Day'
MandateKeys = {"actual": "ACTUAL_TMT_SALES", "history": "ACTUAL_HISTORY_TMT_SALES", "target": "TARGET_TMT_SALES"}


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


def get_group_by_filter_key(cross_filters, cumulative=False, drill_state='', time_grain=''):
    """
    Getting group by filter key based on cross filters
    :param time_grain:
    :param drill_state:
    :param cumulative:
    :param cross_filters:
    :return:
    """
    group_by_filter = ['"month_name"'] if not cumulative else []
    if cross_filters:
        index = 0
        if len([rec['value'] for rec in cross_filters if 'lubes' in rec['value'].lower()
                                                         and rec['key'].strip('"') == "SBU_Name"]):
            for key in [rec['key'] for rec in cross_filters]:
                if key in Lubes_Filters and Lubes_Filters.index(key) > index:
                    index = Lubes_Filters.index(key)
            group_by_filter = [Lubes_Filters[index + 1]]
        else:
            for key in [rec['key'] for rec in cross_filters]:
                if key in Base_Filters and Base_Filters.index(key) > index:
                    index = Base_Filters.index(key)
            group_by_filter = [Base_Filters[index + 1]]
    elif drill_state:
        if not drill_state.startswith('"'):
            drill_state = f'"{drill_state}"'
        group_by_filter = [Base_Filters[Base_Filters.index(drill_state) + 1]]
    if time_grain == 'Monthly' and '"month_name"' not in group_by_filter:
        group_by_filter.append('"month_name"')
    return group_by_filter


async def m60_performance(filters, cross_filters, drill_state="", time_grain="", resp_format=""):
    if not cross_filters:
        cross_filters = []
    # Checking Cumulative enabled or not, On cumulative we should not group by month
    cumulative = False
    for condition in filters:
        if condition['key'].strip('"') == "C":
            cumulative = True
            break

    # Fetching all group by filters, return should be a list always
    group_by_filter = get_group_by_filter_key(cross_filters, cumulative, drill_state, time_grain)

    # Assigning empty variables
    history = actual = target = start_date = end_date = start_date_history = end_date_history = ""

    end_date = fiscal_year.FiscalYear.current().fiscal_year_end_date
    start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
    # For History
    start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime("%Y%m%d")
    end_date_history = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date), years=1, days=0,
                                                       with_month_start_day=False,
                                                       date_time_format=None).strftime("%Y%m%d")

    for index, _ in enumerate(cross_filters):
        cross_filters[index]['key'] = cross_filters[index]['key'].strip('"')
    cross_filters = [rec for rec in cross_filters if not (rec['key'] == 'month_name' and not rec['value'].strip('"'))]
    # Modifying month name filter for cumulative
    for filter in cross_filters:
        if filter['key'].strip('"') == 'month_name' and ',' in filter['value']:
            filter['cond'] = 'in'
            filter['value'] = filter['value'].split(',')
    actual_data = []
    hist_data = []
    target_data = []
    actual_d = """ ROUND(SUM("MOM_DAY_LEVEL_DATA"."NETWEIGHT_TMT")::numeric,0) AS "ACTUAL_TMT_SALES" """
    history_d = """ ROUND(SUM("MOM_DAY_LEVEL_DATA"."NETWEIGHT_TMT")::numeric,0) AS "ACTUAL_HISTORY_TMT_SALES" """
    filters_req = [condition['key'].strip('"') for condition in filters if
                   condition['key'].strip('"') in ["A", "H", "T"]]
    if len(filters_req) == 0:
        filters.append({"key": '"A"', "cond": "equals", "value": "true"})
    # Generating filters
    for condition in filters:
        if condition['key'].strip('"') == "A":
            actual = f"""ROUND(SUM("{DBNames['m60_ta']}"."NETWEIGHT_TMT")::numeric,0) AS "ACTUAL_TMT_SALES" """
        elif condition['key'].strip('"') == "H":
            history = f"""ROUND(SUM("{DBNames['m60_h']}"."NETWEIGHT_TMT")::numeric,0) AS "ACTUAL_HISTORY_TMT_SALES" """
        elif condition['key'].strip('"') == "T":
            target = f""" ROUND(SUM("{DBNames['m60_ta']}"."TARGET_QTY_TMT")::numeric,0) AS "TARGET_TMT_SALES" """
        elif condition['key'].strip('"') == "C":
            continue
        elif condition['key'].strip('"') == "YTD":
            # Calculating start and end dates for YTD for both actual and history
            end_date_ = fiscal_year.FiscalDate.today()
            end_date = helpers.get_time_stamp_by_delta(end_date_, days=1, with_month_start_day=False,
                                                       date_time_format="%Y-%m-%d")
            start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
            # For History
            start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
            end_date_history = helpers.get_time_stamp_by_delta(end_date_, years=1, days=1, with_month_start_day=False,
                                                               date_time_format=None)
            end_date_history = end_date_history.strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
        elif condition['key'].strip('"') == "YTDPM":

            # Calculating start and end dates for YTD for both actual and history
            end_date_ = fiscal_year.FiscalDate.today()
            end_date = helpers.get_time_stamp_by_delta(end_date_,years=0, days=1, with_month_start_day=True,
                                                               date_time_format="%Y-%m-%d")
            print("came into YTDPM")
            start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
            # For History
            start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
            end_date_history = helpers.get_time_stamp_by_delta(end_date_, years=1, days=1, with_month_start_day=True,
                                                               date_time_format=None)


            end_date_history = end_date_history.strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
           

        
        
        elif condition['key'].strip('"') == "DATE":
            # Calculating start and end dates
            start_date, end_date = condition['value'].split(",")
            start_date_history = dt_parser.parse(start_date)
            start_date_history = start_date_history.replace(year=start_date_history.year - 1).strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
            # For History
            end_date_history = dt_parser.parse(end_date)
            end_date_history = end_date_history.replace(year=end_date_history.year - 1).strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
        elif condition['key'] == '"FISCAL_YEAR"':
            # Not considering now
            ...
        else:
            # Clearing if value was an empty string
            if not condition["value"]:
                continue
            condition["key"] = condition["key"].strip('"')
            # Giving more preference for the month's provided in filters than cross filters on drill down
            if condition["key"] == "month_name":
                value = [mnt_name.strip() for mnt_name in condition["value"].split(",")]
                cross_filter_append = True
                for crs_rec in cross_filters:
                    if crs_rec["key"] == "month_name":
                        if len(value) == 1:
                            crs_rec["value"] = value[0]
                        else:
                            crs_rec["value"] = value
                            crs_rec["cond"] = 'one-off'
                        cross_filter_append = False
                if cross_filter_append:
                    if len(value) > 1:
                        condition["cond"] = 'one-off'
                        condition["value"] = value
                    cross_filters.append(condition)
            else:
                cross_filters.append(condition)

    def get_group_by_columns(group_by_filter):
        if group_by_filter:
            return [rec.replace('"', '').strip() for rec in group_by_filter]
        else:
            return ""

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
    # Data Retrival for target data
    if target:
        group_keys = [key for key in group_by_filter]
        if '"month_name"' not in group_by_filter:
            group_keys.append("month_name")
        target_data = await collect_data([target, 'month_name'], 'M60_LEVEL_METADATA',
                                         where_conditions + Default_Filters, start_date, end_date, group_keys)
        if target_data:
            target_data = pd.DataFrame(calculate_pro_rate(target_data, "TARGET_TMT_SALES", start_date, end_date))
            if group_by_filter:
                target_data = target_data.groupby(get_group_by_columns(group_by_filter))[
                    'TARGET_TMT_SALES'].sum().reset_index()
            else:
                target_data = pd.DataFrame([{'TARGET_TMT_SALES': target_data.sum()['TARGET_TMT_SALES']}])
            if '"month_name"' in group_by_filter:
                target_data['month_name'] = pd.CategoricalIndex(target_data['month_name'], ordered=True,
                                                                categories=months)
            target_data = target_data.to_dict(orient='records')

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
        for date_range in filter_dates:
            actual_data.extend(await collect_data([actual], 'M60_LEVEL_METADATA',
                                                  where_conditions + Default_Filters, date_range[0], date_range[1],
                                                  group_by_filter))
        # For Month level aggregations from day wise data table
        # Todo:- for optimization use single query for day filter with or condition
        for date_range in day_filter_dates:
            actual_data.extend(await collect_data([actual_d], 'MOM_DAY_LEVEL_DATA',
                                                  where_conditions + Default_Filters, date_range[0], date_range[1],
                                                  group_by_filter, '"DAY_ID"'))
        if actual_data:
            actual_data = pd.DataFrame(actual_data)
            if group_by_filter:
                actual_data = actual_data.groupby(get_group_by_columns(group_by_filter))[
                    'ACTUAL_TMT_SALES'].sum().reset_index()
            else:
                actual_data = pd.DataFrame([{'ACTUAL_TMT_SALES': actual_data.sum()['ACTUAL_TMT_SALES']}])
            actual_data['ACTUAL_TMT_SALES'] = actual_data['ACTUAL_TMT_SALES'].fillna(0)
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
        for date_range in filter_dates:
            hist_data.extend(await collect_data([history], 'MOM_LEVEL_FINAL_DATA',
                                                where_conditions_history + Default_Filters, date_range[0],
                                                date_range[1], group_by_filter, '"YEARMONTH"'))
        # Todo:- for optimization use single query for day filter with or condition
        for date_range in day_filter_dates:
            hist_data.extend(await collect_data([history_d], 'MOM_DAY_LEVEL_DATA',
                                                where_conditions_history + Default_Filters, date_range[0],
                                                date_range[1], group_by_filter, '"DAY_ID"'))
        if hist_data:
            hist_data = pd.DataFrame(hist_data)
            if group_by_filter:
                hist_data = hist_data.groupby(get_group_by_columns(group_by_filter))[
                    'ACTUAL_HISTORY_TMT_SALES'].sum().reset_index()
            else:
                hist_data = pd.DataFrame([{'ACTUAL_HISTORY_TMT_SALES': hist_data.sum()['ACTUAL_HISTORY_TMT_SALES']}])
            hist_data['ACTUAL_HISTORY_TMT_SALES'] = hist_data['ACTUAL_HISTORY_TMT_SALES'].fillna(0)
            hist_data = hist_data.to_dict(orient='records')

    df_ = [pd.DataFrame(d) for d in [actual_data, target_data, hist_data] if d]
    merged_df = df_[0] if len(df_) else pd.DataFrame([])
    if len(df_) > 1:
        for df in df_[1:]:
            if group_by_filter:
                merged_df = pd.merge(merged_df, df, on=get_group_by_columns(group_by_filter),
                                     how='outer')  # Outer merge with df2
            else:
                merged_df = pd.concat([merged_df, df], axis=0)
    # Creating a data frame from concated df if no group by
    if not group_by_filter:
        result_df = pd.DataFrame()
        for col in merged_df.columns:
            result_df[col] = [merged_df[col].sum()]
        merged_df = result_df
    # Ordering Data for Month and SBU names
    if not merged_df.empty and ('"month_name"' in group_by_filter or '"SBU_Name"' in group_by_filter):
        sort_key = sbu_order if '"SBU_Name"' in group_by_filter else months
        order_key = 'SBU_Name' if '"SBU_Name"' in group_by_filter else 'month_name'
        merged_df["data_order"] = merged_df[order_key].map({cond: i for i, cond in enumerate(sort_key)})
        merged_df = merged_df.sort_values("data_order").drop(columns="data_order")
        merged_df = merged_df[merged_df[order_key].isin(sort_key)]
        merged_df.reset_index(drop=True, inplace=True)
    # If required keys not available keeping records with zero value
    if target:
        if MandateKeys["target"] not in merged_df:
            merged_df[MandateKeys["target"]] = 0
    if actual:
        if MandateKeys["actual"] not in merged_df:
            merged_df[MandateKeys["actual"]] = 0
    if history:
        if MandateKeys["history"] not in merged_df:
            merged_df[MandateKeys["history"]] = 0
    if group_by_filter:
        for key in get_group_by_columns(group_by_filter):
            if key not in merged_df:
                merged_df[key] = ""
    merged_df.fillna(0, inplace=True)


    # This below if condition is to show the multi month selected cummulative values in the bar graph when multiple months is selected in drop-down
    # if len(where_conditions) ==1 and "month_name" in where_conditions[0] and 'IN' in where_conditions[0] and "month_df" in merged_df.columns:
    if (len(group_by_filter) <= 1 and len(where_conditions) == 1 and "month_name" in where_conditions[0] and
            'IN' in where_conditions[0] and 'month_name'  in merged_df.columns):
        amount_columns = merged_df.columns.difference(['month_name'])
        # Concatenate month names
        result_df = pd.DataFrame({
            'month_name': [','.join(merged_df['month_name'])],
                                 })
        for col in amount_columns:
            result_df[col] = [merged_df[col].sum()]
        merged_df = result_df

    if len(cross_filters) > 0:
        filter_order = [key.strip('"') for key in Base_Filters]
        sorted_cross_filters = sorted(cross_filters, key=lambda x: filter_order.index(x['key']) if x['key'] in filter_order else float('inf'))
        req_key = sorted_cross_filters[-1]['key']
        req_key = f'"{req_key}"'
        previous_keys = Base_Filters[:Base_Filters.index(req_key)]
        previous_keys = [item.strip('"') for item in previous_keys]
        Charts_Get_Distinct_ValuesParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Get_Distinct_ValuesParams.action = 'get_distinct_values'
        Charts_Get_Distinct_ValuesParams.column = previous_keys
        sorted_cross_filters[-1]['cond'] = '='
        Charts_Get_Distinct_ValuesParams.where_cond = [sorted_cross_filters[-1]]
        function = await charts_connection_vault_routing(Charts_Get_Distinct_ValuesParams)
        resp = await function(schema_name='public', table_name="MOM_DAY_LEVEL_DATA",
                              column_name=Charts_Get_Distinct_ValuesParams.column,
                              where_clause=Charts_Get_Distinct_ValuesParams.where_cond)
        print(resp)
        sorted_level = resp['data']
        for each_filter in sorted_cross_filters:
            if each_filter['key'] in sorted_level:
                if len(sorted_level[each_filter['key']]) == each_filter['value']:
                    sorted_level[each_filter['key']].append(each_filter['value'])
                else:
                    sorted_level[each_filter['key']] = [each_filter['value']]
            if sorted_cross_filters[-1]['key'] not in sorted_level:
                sorted_level[sorted_cross_filters[-1]['key']] = []
                sorted_level[sorted_cross_filters[-1]['key']].append(sorted_cross_filters[-1]['value'])
        month_keys = []
        if sorted_level and sorted_level.get("month_name"):
            if isinstance(sorted_level['month_name'][0], list):
                sorted_level['month_name'] = sorted_level['month_name'][0]
            month_keys = sorted_level['month_name'] = sorted(sorted_level['month_name'], key=months.index)
        if len(group_by_filter) > 1:
            if 'SalesArea_Name' in merged_df.columns.tolist() or 'Region_Name' in merged_df.columns.tolist():
                for column in list(MandateKeys.values()):
                    if column in merged_df.columns.tolist():
                        merged_df[column] = merged_df[column].fillna(0).astype(int)*1000
            final_resp = generate_stacked_data(merged_df, resp_format, month_column='month_name')
        else:
            if not resp_format:
                final_resp = {key: value.to_dict() for key, value in merged_df.to_dict(orient='series').items()}
            else:
                final_resp = generate_stacked_data(merged_df, resp_format)
        measure_unit = 'TMT'
        if 'Zone_Name' in [x['key'] for x in cross_filters] or 'Region_Name' in [x['key'] for x in cross_filters] or 'SalesArea_Name' in [x['key'] for x in cross_filters]:
            measure_unit = 'MT'
        return {"status": True, "message": "Success", "data": {'data': final_resp, 'level': sorted_level,
                                                               'month_name': month_keys,'sales_unit':measure_unit}}
    else:
        if resp_format:
            final_resp = generate_stacked_data(merged_df, resp_format, month_column='month_name')
        else:
            final_resp = {key: value.to_dict() for key, value in merged_df.to_dict(orient='series').items()}
        measure_unit = 'TMT'
        if 'Zone_Name' in [x['key'] for x in cross_filters] or 'Region_Name' in [x['key'] for x in cross_filters] or 'SalesArea_Name' in [x['key'] for x in cross_filters]:
            measure_unit = 'MT'
        return {"status": True, "message": "Success", "data": {'data': final_resp, 'level': {},'sales_unit':measure_unit}}


def generate_stacked_data(df, resp_format='', month_column=''):
    columns = df.columns.to_list()
    numeric_cols = [col for col in columns if col in list(MandateKeys.values())]
    if month_column:
        df[month_column] = pd.Categorical(df[month_column], categories=months, ordered=True)
        for column in numeric_cols:
            df[column].fillna(0, inplace=True)
        other_columns = list(set(columns) - set(numeric_cols+[month_column]))
    else:
        other_columns = list(set(columns) - set(numeric_cols))
    if other_columns:
        # For Non-Stacked for data table to display month wise AHT data
        if not resp_format:
            # Renaming columns to lower case
            df.rename(columns={value: key for key, value in MandateKeys.items() if value in numeric_cols}, inplace=True)

            # Actual numeric columns
            numeric_cols = [key for key, value in MandateKeys.items() if value in numeric_cols]

            # Pivot Data - Creating separate columns for Actual, History, and Target
            df_pivot = df.pivot(index=other_columns[0], columns=month_column, values=numeric_cols)

            # Flatten MultiIndex Columns and rename them
            df_pivot.columns = [f"{month}_{metric.split('_')[0]}" for metric, month in df_pivot.columns]

            # Reset Index to include 'Zone_Name'
            df_pivot.reset_index(inplace=True)

            # Keeping all nan's as zero's
            df_pivot.fillna(0, inplace=True)

            # Convert to Dictionary Format
            return df_pivot.to_dict(orient="records")
        elif resp_format == 'stacked' and month_column:
            # For sending data in stacked format
            # Renaming columns to lower case
            df.rename(columns={value: key for key, value in MandateKeys.items() if value in numeric_cols}, inplace=True)

            # Actual numeric columns
            numeric_cols = [key for key, value in MandateKeys.items() if value in numeric_cols]

            # Extract unique months from the dataset
            unique_months = sorted(df[month_column].unique(), key=lambda x: months.index(x))
            series_data = []
            for zone in df[other_columns[0]].unique():
                zone_data = df[df[other_columns[0]] == zone].set_index(month_column)
                for column in numeric_cols:
                    # Creating series data
                    series_data.append({"name": f"{zone} {column.title()}", "stack": column.title(),
                                        "data": [zone_data.loc[m, column] if m in zone_data.index else 0
                                                 for m in unique_months]})
            return {"months": unique_months, "series": series_data}
        elif resp_format == 'cummulative' and month_column:
            df.iloc[:, 1:] = df.iloc[:, 1:].cumsum()
            return {key: value.to_dict() for key, value in df.to_dict(orient='series').items()}
        elif resp_format == 'grouped':
            # For Grouped data
            # Converting data to month wise report
            return [{"month_name": month,  **{key: group[key].tolist() for key in numeric_cols+other_columns}}
                    for month, group in df.groupby("month_name")]
    else:
        if resp_format == 'cummulative' and month_column:
            df.iloc[:, 1:] = df.iloc[:, 1:].cumsum()
            
        # For regular drill down widgets
        return {key: value.to_dict() for key, value in df.to_dict(orient='series').items()}

