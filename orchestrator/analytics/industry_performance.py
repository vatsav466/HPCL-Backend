import urdhva_base
import json
import pandas as pd
from collections import defaultdict
import utilities.helpers as helpers
import dateutil.parser as dt_parser
import utilities.fiscal_year as fiscal_year
import orchestrator.analytics.m60_performance as m60
from orchestrator.dbconnector.widget_actions import widget_actions


Base_Filters = ['"cumulative_level"', '"sbu_name"', '"region_name"', '"statename"', '"distname"',
                '"month_name"', '"productname"']
OMC = {
    "PSU": ["HPCL", "BPCL", "IOCL", "CPCL", "ONGC", "NRL", "GAIL", "MRPL", "OIL"],
    "PVT": ["BORL", "HMEL", "RIL", "NEL", "SHELL", "SMA", "RIL"],
    "OtherPSU": ["NRL", "CPCL", "GAIL", "ONGC", "MRPL", "OIL"],
    "MPSU": ["HPCL", "BPCL", "IOCL"]
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
    filters = [condition for condition in filters if condition['key'].strip('"') in ['YTM', 'DATE', 'month_name',
                                                                                     'OMC']]
    if not months:
        months = pd.date_range(start=start_date, end=end_date, freq='MS').strftime('%b').tolist()
    return filters, fiscal_year_pre, fiscal_year_last, [key.upper() for key in months]


def calculate_market_share(df, group_by, sales_key="sales"):
    # Convert Decimal to float for Pandas compatibility
    df["sales"] = df["sales"].astype(float)

    # Calculate total sales per fiscal year
    total_sales = df.groupby(group_by)["sales"].sum().reset_index()
    total_sales.rename(columns={"sales": "market_share"}, inplace=True)

    # Calculate HPCL's total sales per fiscal year
    hpcl_sales_per_year = df[df["coname"] == "HPCL"].groupby(group_by)["sales"].sum().reset_index()
    hpcl_sales_per_year.rename(columns={"sales": "hpcl_share"}, inplace=True)

    # Merge results
    summary = total_sales.merge(hpcl_sales_per_year, on=group_by, how="left").fillna(0)

    # Mapping fiscal years to prefixes
    prefix_map = {
        "2023-2024": "history",
        "2024-2025": "actual"
    }
    if len(group_by) <= 1:
        summary['cumulative'] = "CUMMULATIVE_SALES"
        group_item = "cumulative"
    else:
        group_item = ""
        for key in Base_Filters[::-1]:
            key = key.strip('"')
            if key in group_by:
                group_item = key
                break

    # Transforming data
    transformed_data = [
        {
            f"{prefix_map[item['fiscal_year']]}_market_share": item["market_share"],
            f"{prefix_map[item['fiscal_year']]}_hpcl_share": item["hpcl_share"],
            group_item: item[group_item]
        }
        for item in summary.to_dict(orient='records')
    ]
    # Merging records based on 'group_item'
    merged_data = defaultdict(dict)

    for item in transformed_data:
        sbu = item[group_item]
        merged_data[sbu].update(item)
        merged_data[sbu][group_item] = sbu  # Ensure group_item is retained

    # Convert back to list of dictionaries
    return list(merged_data.values())


async def industry_performance(filters, cross_filters, drill_state="", time_grain="", resp_format=""):
    if not cross_filters:
        cross_filters = []
    # Checking Cumulative enabled or not, On cumulative we should not group by month
    cumulative = False
    for condition in filters:
        if condition['key'].strip('"') == "C":
            cumulative = True
            break
    omc_compare = ["BPCL", "HPCL"]

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
    resp_data = calculate_market_share(pd.DataFrame(resp_data), group_keys)
    df = pd.DataFrame(resp_data).fillna(0)
    return {key: value.to_dict() for key, value in df.to_dict(orient='series').items()}
