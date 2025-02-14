import urdhva_base
import re
import pandas as pd
from collections import defaultdict
import utilities.helpers as helpers
import dateutil.parser as dt_parser
import utilities.fiscal_year as fiscal_year
import orchestrator.analytics.m60_performance as m60
from orchestrator.dbconnector.widget_actions import widget_actions
import json
Base_Filters = ['"cumulative_level"', '"sbu_name"', '"region_name"', '"statename"', '"distname"',
                '"month_name"', '"productname"']
OMC = {
    "PSU": ["HPCL", "BPCL", "IOCL", "CPCL", "ONGC", "NRL", "GAIL", "MRPL", "OIL"],
    "PVT": ["BORL", "HMEL", "RIL", "NEL", "SHELL", "SMA", "RIL"],
    "OtherPSU": ["NRL", "CPCL", "GAIL", "ONGC", "MRPL", "OIL"],
    "MPSU": ["HPCL", "BPCL", "IOCL"]
}

# Define keyword mapping for key extraction
KEYWORDS = {'sbu_name': ['SBU', 'BUSINESS UNIT'],
            'coname': ['COMPANY', 'HPCL', 'BPCL', 'IOCL'],
            'region_name': ['ZONE', 'REGION'],
            'statename': ['STATE', 'STATENAME'],
            'distname': ['DISTRICT', 'DISTNAME'],
            'month_name': ['MONTH', 'MONTH NAME'],
            'productname': ['PRODUCT', 'FUEL', 'PETROL', 'DIESEL']
            }


async def generate_industry_recommendations():
    # Generating auto recommendations
    ...


def generate_group_by_conditions(cross_filters, cumulative=False, drill_state='', time_grain=''):
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
    if "fiscal_year" not in group_by_filter:
        group_by_filter.append("fiscal_year")
    return group_by_filter


def get_date_filters(filters, resp_type="months"):
    """
    Creates actual, history fiscal years and selected months
    :param filters:
    :param resp_type:
    :return:
    """
    fiscal_year_pre = ''
    fiscal_year_last = ''

    end_date = fiscal_year.FiscalYear.current().fiscal_year_end_date
    start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date

    # For History
    start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime("%Y-%m-%d")
    end_date_history = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date), years=1, days=0,
                                                       with_month_start_day=False)
    months = []
    for condition in filters:
        if condition['key'].strip('"') == "A":
            fiscal_year_pre = (f"{fiscal_year.FiscalYear.current().start.year}-"
                               f"{fiscal_year.FiscalYear.current().end.year}")
        elif condition['key'].strip('"') == "H":
            fiscal_year_last = (f"{fiscal_year.FiscalYear.current().prev_fiscal_year.start.year}-"
                                f"{fiscal_year.FiscalYear.current().prev_fiscal_year.end.year}")
        elif condition['key'].strip('"') == "YTM":
            end_date = helpers.get_time_stamp_by_delta(months=1, with_month_start_day=False, with_month_end_day=True)
            end_date_history = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date), years=1, days=0,
                                                               with_month_start_day=False)
        elif condition['key'].strip('"') == "DATE":
            start_date, end_date = condition['value'].split(",")
            start_date = helpers.get_time_stamp_by_delta(dt_parser.parse(start_date))
            end_date = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date), with_month_start_day=False,
                                                       with_month_end_day=True)
            start_date_history = dt_parser.parse(start_date)
            start_date_history = start_date_history.replace(year=start_date_history.year - 1).strftime("%Y-%m-%d")

            # For History
            end_date_history = dt_parser.parse(end_date)
            # Handling for february
            end_date_history = end_date_history.replace(day=end_date_history.day-1, year=end_date_history.year - 1)
            end_date_history = helpers.get_time_stamp_by_delta(end_date_history, with_month_start_day=False,
                                                               with_month_end_day=True)
        elif condition["key"] == "month_name":
            months = [mnt_name.strip() for mnt_name in condition["value"].split(",")]
    filters = [condition for condition in filters if condition['key'].strip('"') not in ['YTM', 'DATE', 'month_name',
                                                                                         'OMC', 'A', 'H', 'C']]
    if not months:
        months = pd.date_range(start=start_date, end=end_date, freq='MS').strftime('%b').tolist()
    return filters, fiscal_year_pre, fiscal_year_last, [key.upper() for key in months]


def calculate_market_share(df, group_by, fiscal_year_pre, fiscal_year_last, drill_state, time_grain, resp_format,
                           sales_key="sales"):
    # Convert Decimal to float for Pandas compatibility
    df["sales"] = df["sales"].astype(float)

    # Calculate total sales per fiscal year
    total_sales = df.groupby(group_by)["sales"].sum().reset_index()
    total_sales.rename(columns={"sales": "market_share"}, inplace=True)
    unique_companies = list(df['coname'].unique()) if resp_format == "company_level" else ["HPCL"]
    summary = total_sales
    if resp_format == "company_level":
        for company in unique_companies:
            company_share = df[df["coname"] == company].groupby(group_by)["sales"].sum().reset_index()
            company_share.rename(columns={"sales": f"{company.lower()}_share"}, inplace=True)
            # Merge results
            summary = summary.merge(company_share, on=group_by, how="left").fillna(0)
    else:
        # Calculate HPCL's total sales per fiscal year
        hpcl_sales_per_year = df[df["coname"] == "HPCL"].groupby(group_by)["sales"].sum().reset_index()
        hpcl_sales_per_year.rename(columns={"sales": "hpcl_share"}, inplace=True)

        # Merge results
        summary = summary.merge(hpcl_sales_per_year, on=group_by, how="left").fillna(0)

    # Mapping fiscal years to prefixes
    prefix_map = {}
    if fiscal_year_pre:
        prefix_map[fiscal_year_pre] = "actual"
    if fiscal_year_last:
        prefix_map[fiscal_year_last] = "history"

    # if group by was less than sending an extra key  cumulative
    if not drill_state:
        if len(group_by) <= 1:
            summary['cumulative'] = "CUMMULATIVE_SALES"
            group_items = ["cumulative"]
        else:
            group_items = []
            for key in Base_Filters[::-1]:
                key = key.strip('"')
                if key in group_by:
                    group_items = [key]
                    break
    else:
        if not drill_state.startswith('"'):
            drill_state = f'"{drill_state}"'

        if time_grain == "Monthly":
            group_items = [Base_Filters[Base_Filters.index(drill_state) + 1].strip('"'), "month_name"]
        else:
            group_items = [Base_Filters[Base_Filters.index(drill_state) + 1].strip('"')]

    # Transforming data
    transformed_data = [
        {
            f"{prefix_map[item['fiscal_year']]}_market_share": item["market_share"],
            **{f"{prefix_map[item['fiscal_year']]}_{company.lower()}_share":
                   item[f"{company.lower()}_share"] for company in unique_companies},
            **{grp_item: item[grp_item] for grp_item in group_items}
        }
        for item in summary.to_dict(orient='records')
    ]

    # Merging records based on 'group_item'
    merged_data = defaultdict(dict)

    for item in transformed_data:
        if len(group_items) == 1:
            sbu = item[group_items[0]]
            merged_data[sbu].update(item)
            merged_data[sbu][group_items[0]] = sbu  # Ensure group_item is retained
        else:
            base_key = group_items[0]
            for grp_item in group_items[1:]:
                sbu = item[grp_item]
                merged_data[f"{sbu}_{item[base_key]}"].update(item)
                merged_data[f"{sbu}_{item[base_key]}"][grp_item] = sbu  # Ensure group_item is retained
    if drill_state:
        return generate_stacked_data(pd.DataFrame(list(merged_data.values())), resp_format, "month_name")
    # Convert back to list of dictionaries
    df = pd.DataFrame(list(merged_data.values())).fillna(0)
    
    if resp_format == 'company_level' and time_grain != 'Monthly':
            data = df.to_dict(orient='records')
            input_dict = data[0]
            companies = sorted(set(
                re.sub(r'^(history|actual)_|_share$', '', key)
                for key in input_dict.keys()
                if key.startswith(('history_', 'actual_'))  # Only process valid keys
            ))
            history_shares = {str(i): input_dict.get(f'history_{company}_share', 0.0) for i, company in enumerate(companies)}
            actual_shares = {str(i): input_dict.get(f'actual_{company}_share', 0.0) for i, company in enumerate(companies)}

            # Construct final output dictionary
            output_dict = {
                "history_share": history_shares,
                "company": {str(i): company for i, company in enumerate(companies)},
                "actual_share": actual_shares
            }
            #transformed_data = json.dumps(output_dict, indent=4, ensure_ascii=False)
            transformed_data = output_dict
            return {'message':'Industry Cummulative company_level Data','data':transformed_data,'status':True}
    if "month_name" in df.columns:
       
        df["month_name"] = pd.Categorical(df["month_name"], categories=[m.upper() for m in m60.months], ordered=True)
        df = df.sort_values('month_name').reset_index(drop=True)
    if resp_format == 'cumulative'  and time_grain == 'Monthly':
            cols_to_cumsum = [col for col in df.columns if col != 'month_name']
            df[cols_to_cumsum] = df[cols_to_cumsum].cumsum()
            return {key: value.to_dict() for key, value in df.to_dict(orient='series').items()}
    
    return {'message':'Industry_Performance','status':True,'data':{key: value.to_dict() for key, value in df.to_dict(orient='series').items()}}
    


def generate_stacked_data(df, resp_format='', month_column=''):
    columns = df.columns.to_list()
    numeric_cols = [col for col in columns if col.startswith('history') or col.startswith('actual')]
    if month_column:
        df[month_column] = pd.Categorical(df[month_column], categories=[month.upper() for month in m60.months],
                                          ordered=True)
        for column in numeric_cols:
            df[column].fillna(0, inplace=True)
        other_columns = list(set(columns) - set(numeric_cols + [month_column]))
    else:
        other_columns = list(set(columns) - set(numeric_cols))
    if other_columns:
        # For Non-Stacked for data table to display month wise AHT data
        if not resp_format:

            # Pivot Data - Creating separate columns for Actual, History, and Target
            df_pivot = df.pivot(index=other_columns[0], columns=month_column, values=numeric_cols)

            # Flatten MultiIndex Columns and rename them
            df_pivot.columns = [f"{month}_{metric}" if metric in numeric_cols else metric for metric, month in df_pivot.columns]

            # Reset Index to include 'Zone_Name'
            df_pivot.reset_index(inplace=True)

            # Keeping all nan's as zero's
            df_pivot.fillna(0, inplace=True)

            # Convert to Dictionary Format
            return df_pivot.to_dict(orient="records")
        elif resp_format == 'stacked' and month_column:
            # For sending data in stacked format

            # Extract unique months from the dataset
            unique_months = sorted(df[month_column].unique(), key=lambda x: m60.months.index(x))
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
            return [{"month_name": month, **{key: group[key].tolist() for key in numeric_cols + other_columns}}
                    for month, group in df.groupby("month_name")]
    else:
        if resp_format == 'cummulative' and month_column:
            df.iloc[:, 1:] = df.iloc[:, 1:].cumsum()

        # For regular drill down widgets
        return {key: value.to_dict() for key, value in df.to_dict(orient='series').items()}


async def industry_performance(filters, cross_filters, drill_state="", time_grain="", resp_format=""):
    if not cross_filters:
        cross_filters = []
    # Checking Cumulative enabled or not, On cumulative we should not group by month
    cumulative = False
    for condition in filters:
        if condition['key'].strip('"') == "C":
            cumulative = True
            break
    # omc_compare = ["BPCL", "HPCL"]
    omc_compare = list(set([company for sublist in OMC.values() for company in sublist]))

    # Fetching all group by filters, return should be a list always
    group_by_filter = generate_group_by_conditions(cross_filters, cumulative, drill_state, time_grain)
    print(group_by_filter)

    # OMC comparing filters
    for filter in filters:
        if filter['key'].strip('"') == "OMC" and filter['value']:
            if OMC.get(filter['value']):
                omc_compare = OMC[filter['value']]
            else:
                omc_compare = list(set([filter['value'].split(",")] + ["HPCL"]))
            break

    # Assigning empty variables
    history = actual = target = start_date = end_date = start_date_history = end_date_history = ""
    filters, fiscal_year_pre, fiscal_year_last, months = get_date_filters(filters)
    if fiscal_year_pre and not fiscal_year_last:
        filters.append({"key": "fiscal_year", "cond": "equals", "value": fiscal_year_pre})
    elif not fiscal_year_pre and fiscal_year_last:
        filters.append({"key": "fiscal_year", "cond": "equals", "value": fiscal_year_last})
    elif fiscal_year_pre and fiscal_year_last:
        filters.append({"key": "fiscal_year", "cond": "one-off", "value": [fiscal_year_pre, fiscal_year_last]})

    for index, _ in enumerate(cross_filters):
        cross_filters[index]['key'] = cross_filters[index]['key'].strip('"')

    cross_filters = [rec for rec in cross_filters if rec['key'].strip('"') not in ["C", "cumulative"] and
                     not (rec['key'] == 'month_name' and not rec['value'].strip('"'))]
    print(cross_filters)

    # Modifying month name filter for cumulative
    month_filter = False
    for cond in cross_filters:
        if cond['key'].strip('"') == 'month_name' and ',' in cond['value']:
            cond['cond'] = 'in'
            cond['value'] = cond['value'].split(',')
            month_filter = True
    if not month_filter and months:
        filters.append({"key": "month_name", "cond": "one-off", "value": months})
    filters.append({"key": "coname", "cond": "one-off", "value": omc_compare})

    where_conditions = []
    clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters + filters)
    if clause:
        where_conditions = [clause]
    group_keys = [key.strip('"') for key in group_by_filter]
    req_keys = f"""ROUND(SUM("netweight_tmt")::numeric,0) AS "sales" """
    resp_data = await m60.collect_data([req_keys], 'industry_performance', where_conditions,
                                       "", "", group_by_filter+["coname"], "")
    return calculate_market_share(pd.DataFrame(resp_data), group_keys, fiscal_year_pre, fiscal_year_last,
                                  drill_state, time_grain, resp_format)



async def generate_response(question):
    question = question.upper()  # Convert to lowercase
    extracted = {key: [] for key in KEYWORDS}  # Initialize output keys
    # Match keywords to fields
    for key, words in KEYWORDS.items():
        for word in words:
            if word in question:
                extracted[key].append(word)  # Assign the found keyword (or later a matched value)
    return extracted
