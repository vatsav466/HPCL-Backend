import urdhva_base
import datetime
import json
import pandas as pd
import urdhva_base.utilities
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

productOrders = {
    "Retail": ["MS", "HSD", "CNG", "SKO", "Compressed Bio Gas (CBG)", "LPG BLK"],
    "Aviation": ["ATF"],
    "I&C": ["HSD", "LDO", "LSHS", "FO", "Naptha", 'Bitumen Blk', "Bitumen Pkd", "Bitumen Modified", "Solvent 2445",
            "Solvent 1425", "JBO", "Sulphur", "Propylene"],
    "LPG": ["LPG PKD - Domestic", "LPG PKD - Non Domestic", "LPG BLK", "BULK PROPANE", "BULK BUTANE"],
    "PETCHEM": ["PETCHEM"],
    "Lubes": ["LUBES RETAIL", "Automotive Oils", "Automotive Greases", "Automotive Specialities", "Industrial oils",
              "Industrial Greases", "Industrial Specialities", "Base Oil"]
}
HistoryKeyMapping = {'SBU_Name': '"ORGSBUNAME"', 'Zone_Name': '"ORGZONENAME"', 'Region_Name': '"ORGRONAME"',
                     'SalesArea_Name': '"ORGSANAME"'}
# Base_Filters = ['"cumulative_level"','"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"','"month_name"','"ProductName"']
Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"', '"ProductName"',
                '"month_name"']
# Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"ProductName"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
#                '"month_name"']
APG_Filters = ['"cumulative_level"', '"ProductName"', '"month_name"']

# Base_Filters = ['"SBU_Name"', '"month_name"','"Zone_Name"', '"Region_Name"', '"SalesArea_Name"'"ProductName"'', '"ProductName"']
# Lubes_Filters = ['"month_name"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"', '"ProductName"']
Lubes_Filters = ['"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"', '"ProductName"', '"month_name"']
Default_Filters = [""""SBU_Name" != '0'""", """"Zone_Name" != '-'""",
                   """ "SBU_Name" not in ('Common','Mumbai Ref','Renewable Energy','Visakh Ref')"""]
# Default_Filters = [""""SBU_Name" != '0'""", """"Zone_Name" != '-'"""]
DBNames = {"m60_ta": "M60_LEVEL_METADATA", "m60_h": "MOM_LEVEL_FINAL_DATA"}
months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']

sbu_order = ['Retail', 'LPG', 'I&C', 'Lubes', 'Aviation', 'PETCHEM', 'GAS']

DefaultTable = 'Day'
MandateKeys = {"actual": "ACTUAL_TMT_SALES", "history": "ACTUAL_HISTORY_TMT_SALES", "target": "TARGET_TMT_SALES",
               "YTD": "YTD_TMT_SALES"}


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
    # print("filters",filters)
    # filters = [condition for condition in filters if condition['key'].strip('"') not in ['resp_format']]
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
    resp = await function(query=query)
    return resp


def get_group_by_filter_key(cross_filters, Base_Filters, resp_format_org, cumulative=False, drill_state='',
                            time_grain=''):
    """
    Getting group by filter key based on cross filters
    :param time_grain:
    :param drill_state:
    :param cumulative:
    :param cross_filters:
    :return:
    """
    if cumulative:
        Lubes_Filters = ['"SBU_Name"', '"ProductName"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
                         '"month_name"']
        group_by_filter = ['"SBU_Name"'] if not cumulative else []
        APG_Filters = ['"cumulative_level"', '"ProductName"', '"month_name"']
        APG_Filters = ['"cumulative_level"', '"SBU_Name"', '"ProductName"', '"month_name"']
        if time_grain == 'Monthly':
            Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
                            '"ProductName"', '"month_name"']
        else:
            print("resp_format_org", resp_format_org)
            if resp_format_org == 'summary':
                Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
                                '"ProductName"', '"month_name"']
            else:
                Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"ProductName"', '"Zone_Name"', '"Region_Name"',
                                '"SalesArea_Name"', '"month_name"']
            print("APG_Liters at group by filter ", APG_Filters)
    else:
        group_by_filter = ['"month_name"'] if not cumulative else []
        Lubes_Filters = ['"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"', '"ProductName"',
                         '"month_name"']
        print("len opf filters are ", cross_filters)
        if len(cross_filters) == 1:
            # if cross_filters[0]['key'].strip('"') = 'month_name' and cross_filters[0]['value'].strip('"') != '':
            if cross_filters[0]['key'].strip('"') != 'month_name':
                Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"ProductName"', '"Zone_Name"', '"Region_Name"',
                                '"SalesArea_Name"', '"month_name"']
        else:
            if len(cross_filters) > 1 and cross_filters[0]['key'].strip('"') == 'month_name':
                Base_Filters = ['"month_name"', '"SBU_Name"', '"ProductName"', '"Zone_Name"', '"Region_Name"',
                                '"SalesArea_Name"']
            elif resp_format_org == 'summary':
                Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
                                '"ProductName"', '"month_name"']
            else:
                Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"ProductName"', '"Zone_Name"', '"Region_Name"',
                                '"SalesArea_Name"', '"month_name"']

    # group_by_filter = ['"month_name"'] if not cumulative else []
    # group_by_filter = ['"SBU_Name"'] if cumulative else []
    if cross_filters:
        index = 0
        if len([rec['value'] for rec in cross_filters if 'lubes' in rec['value'].lower()
                                                         and rec['key'].strip('"') == "SBU_Name"]):
            for key in [rec['key'] for rec in cross_filters]:
                if key in Lubes_Filters and Lubes_Filters.index(key) > index:
                    index = Lubes_Filters.index(key)
            if index > len(Lubes_Filters):
                group_by_filter = [Lubes_Filters[index + 1]]
            elif index < len(Lubes_Filters) and cumulative:
                group_by_filter = [Lubes_Filters[index + 1]]
            else:
                group_by_filter = [Lubes_Filters[index - 1]]
            return group_by_filter
            # group_by_filter = [Lubes_Filters[index + 1]]

        if ('Aviation' in [x['value'].strip('"') for x in cross_filters] or 'PETCHEM' in [x['value'].strip('"') for x in
                                                                                          cross_filters] or 'GAS' in [
            x['value'].strip('"') for x in cross_filters]):
            for key in [rec['key'] for rec in cross_filters]:

                if key in APG_Filters and APG_Filters.index(key) > index:
                    index = APG_Filters.index(key)
            if index > len(APG_Filters):
                group_by_filter = [APG_Filters[index + 1]]
            else:
                group_by_filter = [APG_Filters[index - 1]]
                # this is f
                if cumulative:
                    group_by_filter = [APG_Filters[index + 1]]
            return group_by_filter

        else:
            for key in [rec['key'] for rec in cross_filters]:
                if (key in Base_Filters or key in [x.strip('"') for x in Base_Filters]) and Base_Filters.index(
                        key) > index:
                    index = Base_Filters.index(key)
            group_by_filter = [Base_Filters[index + 1]]
            # if index>len(Base_Filters):
            #    group_by_filter = [Base_Filters[index + 1]]
            # else:
            #    group_by_filter = [Base_Filters[index-1]]
    elif drill_state:
        if not drill_state.startswith('"'):
            drill_state = f'"{drill_state}"'
        group_by_filter = [Base_Filters[Base_Filters.index(drill_state) + 1]]
    if time_grain == 'Monthly' and '"month_name"' not in group_by_filter:
        group_by_filter.append('"month_name"')
    return group_by_filter


async def m60_performance(filters, cross_filters, drill_state="", time_grain="", resp_format=""):
    def get_fiscal_year(date_ui, todays_date, same_year=False, key='YTDPM'):

        end_date_ = fiscal_year.FiscalDate.fromtimestamp(int(urdhva_base.utilities.get_present_time().strftime('%s')))
        if key == 'YTDPM':
            end_date = helpers.get_time_stamp_by_delta(end_date_, years=0, days=1, with_month_start_day=True,
                                                       date_time_format="%Y-%m-%d")
        else:
            if same_year:
                end_date = helpers.get_time_stamp_by_delta(end_date_, days=1, with_month_start_day=False,
                                                           date_time_format="%Y-%m-%d")
            else:
                '''
                end_date = helpers.get_time_stamp_by_delta(end_date_, years=1, days=1, with_month_start_day=False,
                                                                    date_time_format=None)
                '''
                end_date_check = fiscal_year.FiscalYear.current().fiscal_year_end_date
                end_date = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date_check), years=1, days=0,
                                                           with_month_start_day=False,
                                                           date_time_format=None).strftime("%Y-%m-%d")

                print("end_date", end_date)
                '''
                end_date = helpers.get_time_stamp_by_delta(end_date_,years=1,days=1, with_month_start_day=False,
                                                        date_time_format="%Y-%m-%d")
                '''
        start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
        # For History
        start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime(
            "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
        if key == 'YTDPM':
            end_date_history = helpers.get_time_stamp_by_delta(end_date_, years=1, days=1, with_month_start_day=True,
                                                               date_time_format=None)
        else:
            if same_year:
                end_date_history = helpers.get_time_stamp_by_delta(end_date_, years=1, days=1,
                                                                   with_month_start_day=False,
                                                                   date_time_format=None)
            else:
                '''
                end_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.end
                
                '''
                end_date_check = fiscal_year.FiscalYear.current().fiscal_year_end_date
                print("end_date_check", end_date_check)
                end_date_history = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date_check), years=2, days=0,
                                                                   with_month_start_day=False,
                                                                   date_time_format=None)
                '''
                end_date = fiscal_year.FiscalYear.current().fiscal_year_end_date
                end_date_history = helpers.get_time_stamp_by_delta(end_date_, years=1, days=0, with_month_start_day=False,
                                                                    date_time_format=None)
                '''
        end_date_history = end_date_history.strftime("%Y%m%d" if DefaultTable == "Day" else "%Y%m")
        if same_year:
            return start_date, end_date, start_date_history, end_date_history

        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        start_date = start_date.replace(year=start_date.year - 1).strftime("%Y-%m-%d")
        end_date = end_date.replace(year=end_date.year).strftime("%Y-%m-%d")
        end_date_history = datetime.datetime.strptime(end_date_history, "%Y%m%d")
        end_date_history = end_date_history.replace(year=end_date_history.year).strftime("%Y-%m-%d")

        start_date_history = datetime.datetime.strptime(start_date_history, "%Y%m%d")
        start_date_history = start_date_history.replace(year=start_date_history.year - 1).strftime("%Y-%m-%d")
        print("came till returb")

        return start_date, end_date, start_date_history, end_date_history

    '''
    for the product drop-down present in the sbu wise pages we need the productname to be in payload.
    when the page is loaded for the first time 
    '''
    if 'ProductName' in [x['key'].strip('"') for x in filters]:
        product_name_values = [x['value'] for x in filters if x['key'].strip('"') == 'ProductName']
        if product_name_values and product_name_values[0] == '':
            cross_filters = [f for f in cross_filters if f.get("key", "").strip('"') != "ProductName"]

    '''
    if 'fiscal_year' in [x['key'].strip('"') for x in filters]:
        if 'YTD' in [x['key'].strip('"') for x in filters] or 'YTDPM' in [x['key'].strip('"') for x in filters]:
            if len(cross_filters) == 1:
                filters = [x for x in filters if x['key'].strip('"') != 'fiscal_year']
    '''
    resp_level = ''
    if resp_format == 'summary':
        resp_level = 'summary'
        resp_format_org = 'summary'
        resp_format = ''
    else:
        resp_format_org = ''
    # Removing extra keys like all/_empty/* to mak sure all results appear in api response
    # Filtering cross filters
    org_cross_filters = cross_filters.copy()
    cross_filters = [cross_filter for cross_filter in cross_filters if not (cross_filter.get("cond") in ['=', 'equals']
                                                                            and cross_filter.get("value") and
                                                                            cross_filter["value"].lower() in ['*',
                                                                                                              '_empty',
                                                                                                              'all'])]

    # Filtering filters
    filters = [filter_cond for filter_cond in filters
               if not (filter_cond.get("cond") in ['=', 'equals'] and filter_cond.get("value") and
                       filter_cond["value"].lower() in ['*', '_empty', 'all'])]
    sbuName_req = ''
    sbuWise = False
    if '"sbu_wise"' in [x['key'] for x in cross_filters]:
        sbuWise = True
        for eachfilter in cross_filters:
            if eachfilter['key'] == '"sbu_wise"':
                inx = cross_filters.index(eachfilter)
                cross_filters.pop(inx)
    if '"SBU_Name"' in [x['key'] for x in filters]:
        for each_filter in filters:
            if each_filter['key'] == '"SBU_Name"':
                sbuName_req = each_filter['value']
                break
    order = 'cumulative'
    if not cross_filters:
        cross_filters = []
    # Checking Cumulative enabled or not, On cumulative we should not group by month
    cumulative = False
    for condition in filters:
        if condition['key'].strip('"') == "C":
            cumulative = True
            break
    if not cross_filters and cumulative:
        cumulative = True
        order = 'cumulative'
    if cumulative:
        Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
                        '"month_name"', '"ProductName"']
        Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
                        '"ProductName"', '"month_name"']

        Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"ProductName"', '"Zone_Name"', '"Region_Name"',
                        '"SalesArea_Name"',
                        '"month_name"']
        Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"ProductName"', '"Zone_Name"', '"Region_Name"',
                        '"SalesArea_Name"',
                        '"month_name"']
        Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"ProductName"', '"Zone_Name"', '"Region_Name"',
                        '"SalesArea_Name"',
                        '"month_name"']
        '''
        APG_Filters = ['"cumulative_level"', '"SBU_Name"', '"ProductName"','"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
                         '"month_name"']
        '''
        APG_Filters = ['"cumulative_level"', '"SBU_Name"', '"ProductName"', '"month_name"']

        if resp_level == "summary" or resp_format == 'heat_map':
            Base_Filters = ['"cumulative_level"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
                            '"ProductName"', '"month_name"']
    else:
        Base_Filters = ['"month_name"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
                        '"ProductName"']
        # Base_Filters = ['"month_name"', '"SBU_Name"', '"ProductName"','"Zone_Name"', '"Region_Name"', '"SalesArea_Name"']
        if resp_level == "summary" or resp_format == 'heat_map':
            Base_Filters = ['"month_name"', '"SBU_Name"', '"Zone_Name"', '"Region_Name"', '"SalesArea_Name"',
                            '"ProductName"']
    # Fetching all group by filters, return should be a list always
    group_by_filter = get_group_by_filter_key(cross_filters, Base_Filters, resp_format_org, cumulative, drill_state,
                                              time_grain)
    # Assigning empty variables
    history = actual = target = start_date = end_date = start_date_history = end_date_history = ""
    if "fiscal_year" in [x['key'].strip('"') for x in filters]:
        fiscal_year_ui = [x['value'] for x in filters if x['key'].strip('"') == "fiscal_year"][0]
        print("str(datetime.date.today())", str(datetime.date.today()))
        todays_date = str(datetime.date.today())
        if todays_date.split('-')[0] == fiscal_year_ui.split('-')[0]:
            if "YTD" in [x['key'].strip('"') for x in filters]:
                print("YTD is present")
                start_date, end_date, start_date_history, end_date_history = get_fiscal_year(fiscal_year_ui,
                                                                                             todays_date,
                                                                                             same_year=True, key='YTD')
            else:
                end_date = fiscal_year.FiscalYear.current().fiscal_year_end_date
                start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
                # For History
                start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime("%Y%m%d")
                end_date_history = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date), years=1, days=0,
                                                                   with_month_start_day=False,
                                                                   date_time_format=None).strftime("%Y%m%d")
        elif todays_date.split('-')[0] != fiscal_year_ui.split('-')[0]:
            if "YTD" in [x['key'].strip('"') for x in filters]:
                print("YTD is present")
                start_date, end_date, start_date_history, end_date_history = get_fiscal_year(fiscal_year_ui,
                                                                                             todays_date,
                                                                                             same_year=False, key='YTD')
            else:
                # end_date = fiscal_year.FiscalYear.current().fiscal_year_end_date
                # start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
                # For History
                start_date = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime("%Y%m%d")
                end_date = fiscal_year.FiscalYear.current().prev_fiscal_year.end.strftime("%Y%m%d")

                start_date_history = helpers.get_time_stamp_by_delta(dt_parser.parse(start_date), years=1, days=0,
                                                                     with_month_start_day=False,
                                                                     date_time_format=None).strftime("%Y%m%d")

                end_date_history = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date), years=1, days=0,
                                                                   with_month_start_day=False,
                                                                   date_time_format=None).strftime("%Y%m%d")

        else:

            end_date = fiscal_year.FiscalYear.current().fiscal_year_end_date
            start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
            # For History
            start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime("%Y%m%d")
            end_date_history = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date), years=1, days=0,
                                                               with_month_start_day=False,
                                                               date_time_format=None).strftime("%Y%m%d")
    else:
        end_date = fiscal_year.FiscalYear.current().fiscal_year_end_date
        start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
        # For History
        start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime("%Y%m%d")
        end_date_history = helpers.get_time_stamp_by_delta(dt_parser.parse(end_date), years=1, days=0,
                                                           with_month_start_day=False,
                                                           date_time_format=None).strftime("%Y%m%d")

    todays_date = str(datetime.date.today())
    '''
    if todays_date.split('-')[1] == '04' or todays_date.split('-')[1] == '4':
                start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                start_date = start_date.replace(year=start_date.year - 1).strftime("%Y-%m-%d")
                end_date = end_date.replace(year=end_date.year-1).strftime("%Y-%m-%d")
                
                start_date_history = datetime.datetime.strptime(start_date_history, "%Y%m%d")
                start_date_history = start_date_history.replace(year=start_date_history.year - 1).strftime("%Y-%m-%d")
                end_date_history = datetime.datetime.strptime(end_date_history, "%Y%m%d")
                end_date_history = end_date_history.replace(year=end_date_history.year-1).strftime("%Y-%m-%d")
    
    '''
    for index, _ in enumerate(cross_filters):
        cross_filters[index]['key'] = cross_filters[index]['key'].strip('"')
    cross_filters = [rec for rec in cross_filters if not (rec['key'] == 'month_name' and not rec['value'].strip('"'))]
    # Modifying month name filter for cumulative
    for filter in cross_filters:
        if filter['key'].strip('"') == 'month_name' and ',' in filter['value']:
            filter['cond'] = 'in'
            filter['value'] = filter['value'].split(',')
        if 'cumulative' in [x['key'] for x in cross_filters] and len(cross_filters) == 1:
            cross_filters = []
        else:
            print('more filters are present')
    actual_data = []
    hist_data = []
    target_data = []
    actual_d = """ ROUND(SUM("MOM_DAY_LEVEL_DATA"."NETWEIGHT_TMT")::numeric,2) AS "ACTUAL_TMT_SALES" """
    history_d = """ ROUND(SUM("MOM_DAY_LEVEL_DATA"."NETWEIGHT_TMT")::numeric,2) AS "ACTUAL_HISTORY_TMT_SALES" """
    filters_req = [condition['key'].strip('"') for condition in filters if
                   condition['key'].strip('"') in ["A", "H", "T"]]
    if len(filters_req) == 0:
        filters.append({"key": '"A"', "cond": "equals", "value": "true"})
    # Generating filters
    for condition in filters:
        if condition['key'].strip('"') == "A":
            actual = f"""ROUND(SUM("{DBNames['m60_ta']}"."NETWEIGHT_TMT")::numeric,2) AS "ACTUAL_TMT_SALES" """
        elif condition['key'].strip('"') == "H":
            history = f"""ROUND(SUM("{DBNames['m60_h']}"."NETWEIGHT_TMT")::numeric,2) AS "ACTUAL_HISTORY_TMT_SALES" """
        elif condition['key'].strip('"') == "T":
            target = f""" ROUND(SUM("{DBNames['m60_ta']}"."TARGET_QTY_TMT")::numeric,2) AS "TARGET_TMT_SALES" """

        elif condition['key'].strip('"') == "C" and '"T"' not in [x['key'] for x in filters]:
            continue
        elif condition['key'].strip('"') == "YTD":
            # Calculating start and end dates for YTD for both actual and history
            # end_date_ = fiscal_year.FiscalDate.today()
            # end_date = helpers.get_time_stamp_by_delta(end_date_, days=1, with_month_start_day=False,
            #                                           date_time_format="%Y-%m-%d")
            # start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
            '''
            todays_date = str(datetime.date.today())
            if todays_date.split('-')[1] == '04' or todays_date.split('-')[1] == '4':
                start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                start_date = start_date.replace(year=start_date.year - 1).strftime("%Y-%m-%d")
                end_date = end_date.replace(year=end_date.year).strftime("%Y-%m-%d")
            
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
            '''
            '''
            if todays_date.split('-')[1] == '04' or todays_date.split('-')[1] == '4':
                end_date_history = datetime.datetime.strptime(end_date_history, "%Y%m%d")
                end_date_history = end_date_history.replace(year=end_date_history.year).strftime("%Y-%m-%d")
            
                start_date_history = datetime.datetime.strptime(start_date_history, "%Y%m%d")
                start_date_history = start_date_history.replace(year=start_date_history.year-1).strftime("%Y-%m-%d")
                
            '''

            if "fiscal_year" in [x['key'].strip('"') for x in filters]:
                fiscal_year_ui = [x['value'] for x in filters if x['key'].strip('"') == "fiscal_year"][0]

                todays_date == str(datetime.date.today())
                if todays_date.split('-')[0] == fiscal_year_ui.split('-')[0]:
                    start_date, end_date, start_date_history, end_date_history = get_fiscal_year(fiscal_year_ui,
                                                                                                 todays_date,
                                                                                                 same_year=True,
                                                                                                 key='YTD')
                else:
                    start_date, end_date, start_date_history, end_date_history = get_fiscal_year(fiscal_year_ui,
                                                                                                 todays_date,
                                                                                                 same_year=False,
                                                                                                 key='YTD')
        elif condition['key'].strip('"') == "FYC":
            condition = [x for x in filters if x['key'] == '"DATE"']
            # Calculating start and end dates for YTD for both actual and history
            start_date, end_date = condition[0]['value'].split(",")
            start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
            # end_date = dt_parser.parse(end_date)
            start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
            end_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.end.strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")

        elif condition['key'].strip('"') == "YTDPM":

            if "fiscal_year" in [x['key'].strip('"') for x in filters]:
                fiscal_year_ui = [x['value'] for x in filters if x['key'].strip('"') == "fiscal_year"][0]
                print("todays_date.split('-')[0]", todays_date.split('-')[0])
                print("fiscal_year_ui.split('-')[0]", fiscal_year_ui.split('-')[0])

                if (todays_date.split('-')[1] == '04' or todays_date.split('-')[1] == '4') and todays_date.split('-')[
                    0] == fiscal_year_ui.split('-')[0]:
                    print("in this data loop")
                    return {"status": False, "message": "No Data Present for the current selection",
                            "data": {'data': {'ACTUAL_TMT_SALES': {}, 'ACTUAL_HISTORY_TMT_SALES': {}, 'cumulative': {},
                                              'SBU_Name': {}}, 'level': {}, 'sales_unit': 'TMT'}}
                if todays_date.split('-')[0] == fiscal_year_ui.split('-')[0]:
                    start_date, end_date, start_date_history, end_date_history = get_fiscal_year(fiscal_year_ui,
                                                                                                 todays_date,
                                                                                                 same_year=True,
                                                                                                 key='YTDPM')
                else:
                    start_date, end_date, start_date_history, end_date_history = get_fiscal_year(fiscal_year_ui,
                                                                                                 todays_date,
                                                                                                 same_year=False,
                                                                                                 key='YTDPM')

            '''
            # Calculating start and end dates for YTD for both actual and history
            end_date_ = fiscal_year.FiscalDate.today()
            end_date = helpers.get_time_stamp_by_delta(end_date_, years=0, days=1, with_month_start_day=True,
                                                       date_time_format="%Y-%m-%d")
            print("came into YTDPM")
            start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date
            '''
            '''
            todays_date = str(datetime.date.today())
            if todays_date.split('-')[1] == '04' or todays_date.split('-')[1] == '4':
                start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                start_date = start_date.replace(year=start_date.year - 1).strftime("%Y-%m-%d")
                end_date = end_date.replace(year=end_date.year).strftime("%Y-%m-%d")
            '''

            '''
            # For History
            start_date_history = fiscal_year.FiscalYear.current().prev_fiscal_year.start.strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
            end_date_history = helpers.get_time_stamp_by_delta(end_date_, years=1, days=1, with_month_start_day=True,
                                                               date_time_format=None)
            end_date_history = end_date_history.strftime(
                "%Y%m%d" if DefaultTable == "Day" else "%Y%m")
            '''
            '''
            if todays_date.split('-')[1] == '04' or todays_date.split('-')[1] == '4':
                start_date_history = datetime.datetime.strptime(start_date_history, "%Y%m%d")
                start_date_history = start_date_history.replace(year=start_date_history.year-1).strftime("%Y-%m-%d")
            '''
        elif condition['key'].strip('"') == "DATE" and '"FYC"' not in [x['key'] for x in filters]:
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
            if condition['key'] != '"C"':
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
                    if condition['key'] == 'DATE':
                        if '"FYC"' not in [x['key'] for x in filters]:
                            cross_filters.append(condition)
                    else:
                        if ',' in condition['value']:
                            condition['cond'] = 'in'
                            condition['value'] = condition['value'].split(',')
                        if condition['key'].strip('"') == 'resp_format':
                            if condition['value'] != 'heat_map':
                                cross_filters.append(condition)
                        # commenting below lines on drop-down isue
                        print("resp_format", resp_format)
                        # if 'fiscal_year' in [x['key'].strip('"') for x in filters] and time_grain != 'drop-down':
                        # if 'fiscal_year' in [x['key'].strip('"') for x in filters]:
                        if 'fiscal_year' in condition['key'].strip('"'):
                            print("came here3", condition)
                            if 'YTD' in [x['key'].strip('"') for x in filters] or 'YTDPM' in [x['key'].strip('"') for x
                                                                                              in filters]:
                                continue
                        else:
                            cross_filters.append(condition)

    def get_group_by_columns(group_by_filter):
        if group_by_filter:
            return [rec.replace('"', '').strip() for rec in group_by_filter]
        else:
            return ""

    where_conditions = []
    clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters.copy())
    if clause:
        where_conditions = [clause]
    # For history table
    for rec in cross_filters:
        rec['key'] = rec['key'].strip('"')

    where_conditions_history = []
    clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters.copy())
    if clause:
        where_conditions_history = [clause]
    # Data Retrival for target data
    if target:
        group_keys = [key for key in group_by_filter]

        if '"month_name"' not in group_by_filter and '"C"' not in [x['key'] for x in filters]:
            group_keys.append("month_name")
        if '"C"' not in [x['key'] for x in filters]:
            target_data = await collect_data([target, 'month_name'], 'M60_LEVEL_METADATA',
                                             where_conditions + Default_Filters, start_date, end_date, group_keys)
        elif '"C"' in [x['key'] for x in filters] and '"YTD"' in [x['key'] for x in filters] and '"T"' in [x['key'] for
                                                                                                           x in
                                                                                                           filters] and (
                len(org_cross_filters) == 0 or (
                len(org_cross_filters) == 1 and org_cross_filters[0]['key'] == '"sbu_wise"')):
            group_keys.append('month_name')
            target_data = await collect_data([target, 'month_name'], 'M60_LEVEL_METADATA',
                                             where_conditions + Default_Filters, start_date, end_date, group_keys)

        elif '"C"' in [x['key'] for x in filters] and '"YTD"' not in [x['key'] for x in filters] and '"T"' in [x['key']
                                                                                                               for x in
                                                                                                               filters] and (
                len(org_cross_filters) == 0 or (
                len(org_cross_filters) == 1 and org_cross_filters[0]['key'] == '"sbu_wise"')):
            group_keys.append('month_name')
            target_data = await collect_data([target, 'month_name'], 'M60_LEVEL_METADATA',
                                             where_conditions + Default_Filters, start_date, end_date, group_keys)
        else:
            target_data = await collect_data([target], 'M60_LEVEL_METADATA',
                                             where_conditions + Default_Filters, start_date, end_date, group_keys)
        if target_data:
            # if '"C"'   in [x['key'] for x in filters] and '"YTD"'   in [x['key'] for x in filters] and '"T"'   in [x['key'] for x in filters] and len(org_cross_filters) == 0:
            if (('"YTD"' in [x['key'] for x in filters] and '"T"' in [x['key'] for x in filters]
                and (len(org_cross_filters) == 0) and '"C"' in [x['key'] for x in filters] and time_grain != 'Monthly')
                    or ('"DATE"' in [x['key'] for x in filters] and '"T"' in [x['key'] for x in filters])):

                '''
                if end_date:
                    end_month = fiscal_year.get_month_abbr(end_date)
                    print("end_mionth is ",end_month)
                    target_data = [x.update({'month_name': end_month}) or x for x in target_data]  
                '''
                target_data = pd.DataFrame(calculate_pro_rate(target_data, "TARGET_TMT_SALES", start_date, end_date))
                if "month_name" in target_data.columns.tolist():
                    del target_data['month_name']
                if "TARGET_TMT_SALES" in target_data.columns.tolist():
                    sample_data = pd.DataFrame(columns=['TARGET_TMT_SALES'])
                    sample_data['TARGET_TMT_SALES'] = target_data['TARGET_TMT_SALES'].sum()
                if not sample_data.empty:
                    target_data = sample_data
            elif '"C"' not in [x['key'] for x in filters]:
                target_data = pd.DataFrame(calculate_pro_rate(target_data, "TARGET_TMT_SALES", start_date, end_date))
            elif '"C"' in [x['key'] for x in filters] and len(org_cross_filters) == 1 and org_cross_filters[0][
                'key'] == '"sbu_wise"':
                target_data = pd.DataFrame(calculate_pro_rate(target_data, "TARGET_TMT_SALES", start_date, end_date))
            else:
                target_data = pd.DataFrame(target_data)
            if group_by_filter and not cumulative:
                target_data = target_data.groupby(get_group_by_columns(group_by_filter))[
                    'TARGET_TMT_SALES'].sum().reset_index()
            else:
                if not cumulative:
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
            if col not in "month_name":
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
            'IN' in where_conditions[0] and 'month_name' in merged_df.columns):
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
        sorted_cross_filters = sorted(cross_filters,
                                      key=lambda x: filter_order.index(x['key']) if x['key'] in filter_order else float(
                                          'inf'))
        req_key = sorted_cross_filters[-1]['key']
        req_key = f'"{req_key}"'
        # added if on drop-down isue
        # if req_key in Base_Filters:
        previous_keys = Base_Filters[:Base_Filters.index(req_key)]
        # added else on drop-down isue
        # else :
        #    previous_keys = ''
        # added if on drop-down isue
        # if previous_keys:
        if '"cumulative_level"' in previous_keys:
            previous_keys.remove('"cumulative_level"')
        previous_keys = [item.strip('"') for item in previous_keys]
        Charts_Get_Distinct_ValuesParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Get_Distinct_ValuesParams.action = 'get_distinct_values'
        Charts_Get_Distinct_ValuesParams.column = previous_keys

        if sorted_cross_filters[-1].get('cond') not in [' ', 'in', 'one-off']:
            sorted_cross_filters[-1]['cond'] = '='
        Charts_Get_Distinct_ValuesParams.where_cond = [sorted_cross_filters[-1]]
        function = await charts_connection_vault_routing(Charts_Get_Distinct_ValuesParams)
        resp = await function(schema_name='public', table_name="MOM_DAY_LEVEL_DATA",
                              column_name=Charts_Get_Distinct_ValuesParams.column,
                              where_clause=Charts_Get_Distinct_ValuesParams.where_cond)
        sorted_level = resp['data']
        if not sorted_level:
            sorted_level = {}

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

        if sorted_level and sorted_level.get("month_name") and not cumulative:
            if isinstance(sorted_level['month_name'][0], list):
                sorted_level['month_name'] = sorted_level['month_name'][0]
            month_keys = sorted_level['month_name'] = sorted(sorted_level['month_name'], key=months.index)
        if len(group_by_filter) > 1:
            '''
            if 'SalesArea_Name' in merged_df.columns.tolist() or 'Region_Name' in merged_df.columns.tolist():
                for column in list(MandateKeys.values()):
                    if column in merged_df.columns.tolist():
                        merged_df[column] = merged_df[column].fillna(0).astype(int) * 1000
            '''
            final_resp, hist_growth_details, tgt_growth_details = generate_stacked_data(drill_state, merged_df,
                                                                                        resp_format,
                                                                                        month_column='month_name')
        else:
            if not resp_format:
                final_resp = {key: value.to_dict() for key, value in merged_df.to_dict(orient='series').items()}
            else:
                final_resp, hist_growth_details, tgt_growth_details = generate_stacked_data(drill_state, merged_df,
                                                                                            resp_format,
                                                                                            month_column='month_name')
        measure_unit = 'TMT'
        """'if 'Zone_Name' in [x['key'] for x in cross_filters] or 'Region_Name' in [x['key'] for x in cross_filters] or 'SalesArea_Name' in [x['key'] for x in cross_filters]:
            measure_unit = 'MT'
        if sbuName_req =="GAS" :
            measure_unit = 'MT'"""
        if 'cumulative' not in final_resp and not drill_state:
            final_resp['cumulative'] = {}
        if isinstance(final_resp, dict) and len(final_resp.get('ACTUAL_TMT_SALES', [])) == 1 and not drill_state:
            # if '"SBU_Name"' in [x['key'] for x in filters] or 'SBU_Name' in [x['key'] for x in filters]:
            # if '"sbu_wise"' in [x['key'] for x in cross_filters] or 'sbu_wise' in [x['key'] for x in cross_filters]:
            # if resp_format == 'sbu_wise':
            if sbuWise:
                final_resp['cumulative']["0"] = sbuName_req.upper() + '_CUMMULATIVE_SALES'
            else:
                final_resp['cumulative']["0"] = 'CUMMULATIVE_SALES'

        else:
            if isinstance(final_resp, dict):
                for each_key in final_resp.get('ACTUAL_TMT_SALES', []):
                    # if 'cumulative' not in final_resp and not drill_state:
                    if 'cumulative' not in final_resp and not drill_state:
                        final_resp['cumulative'] = {}
                    if 'cumulative' not in final_resp and time_grain == 'Yearly':
                        final_resp['cumulative'] = {}
                    final_resp['cumulative'][each_key] = ''
        if resp_format == 'heat_map':
            hist_xaxis = []
            tgt_xaxis = []
            # xAxis.extend([x['title'].split('_')[0]+'_'+x['title'].split('_')[1] for x in growth_details if '_' in x else x.split()[0]])
            # hist_xaxis.extend(['_'.join(x['title'].split('_')[:2]) if '_' in x['title'] and 'hist' in x['title'].lower()  else x['title'].split()[0] if 'hist' in x['title'].lower() for x in growth_details if isinstance(x, dict) and 'title' in x])
            # hist_xaxis.extend(['_'.join(x['title'].split('_')[:2]) if '_' in x['title'] and 'hist' in x['title'].lower()  else x['title'].split()[0] if 'hist' in x['title'].lower()
            #                   else x for x in growth_details if isinstance(x, dict) and 'title' in x])
            hist_xaxis.extend(
                ['_'.join(x['title'].split('_')[:2]) for x in hist_growth_details if 'hist' in x['title'].lower()])
            if len(hist_xaxis) > 1:
                di = final_resp[0]
                li = merged_df['month_name'].unique().tolist()
                req_index = li.index(hist_xaxis[1].split('_')[0])
                li_req = li[:req_index]
                req_str = '(' + li_req[0] + '-' + li_req[-1] + ')'
                hist_xaxis[0] = hist_xaxis[0] + req_str
            if '"T"' in [x['key'] for x in filters]:
                tgt_xaxis.extend(
                    ['_'.join(x['title'].split('_')[:2]) for x in tgt_growth_details if 'tgt' in x['title'].lower()])
                req_index = li.index(tgt_xaxis[1].split('_')[0])
                li = li[:req_index]
                req_str = '(' + li[0] + '-' + li[-1] + ')'
                tgt_xaxis[0] = tgt_xaxis[0] + req_str
                # tgt_xaxis.extend(['_'.join(x['title'].split('_')[:2]) if '_' in x['title'] and 'tgt' in x['title'].lower() else x['title'].split()[0] if 'tgt' in x['title'].lower()
                #               else x for x in growth_details if isinstance(x, dict) and 'title' in x])
                # tgt_xaxis.extend(['_'.join(x['title'].split('_')[:2]) if '_' in x['title'] and 'tgt' in x['title'].lower() else x['title'].split()[0] if 'tgt' in x['title'].lower() for x in growth_details if isinstance(x, dict) and 'title' in x])
            # xAxis.extend(['YTD'])
            if len(tgt_xaxis) > 0:
                return {"status": True, "message": "Success",
                        "data": {'data': final_resp, 'hist_growth_details': hist_growth_details,
                                 'tgt_growth_details': tgt_growth_details, 'hist_xaxis': hist_xaxis,
                                 'tgt_xaxis': tgt_xaxis, 'level': sorted_level,
                                 'month_name': month_keys, 'sales_unit': measure_unit}}
            else:
                return {"status": True, "message": "Success",
                        "data": {'data': final_resp, 'hist_growth_details': hist_growth_details,
                                 'hist_xaxis': hist_xaxis, 'level': sorted_level,
                                 'month_name': month_keys, 'sales_unit': measure_unit}}

        print("final_resp", final_resp)
        if isinstance(final_resp, dict):
            if all(not v for v in final_resp.values()):
                return {"status": False, "message": "No Data Present for the current selection",
                        "data": {'data': final_resp, 'level': sorted_level,
                                 'month_name': month_keys, 'sales_unit': measure_unit}}
            else:
                print("final_resp is not empty")
                print("cross_filters", cross_filters)
                '''
                if len(cross_filters) >= 1:
                        if list(set([x['key'] for x in cross_filters]))[0].strip('"') == 'SBU_Name':
                            condition = cross_filters[0]
                            if condition['key'].strip('"') == 'SBU_Name':
                                sbu_name = condition['value']
                                if sbu_name in productOrders:
                                    sort_order = productOrders[sbu_name]
                                    
                                    # Get the product name map
                                    product_name_dict = final_resp.get("ProductName", {})
                                    
                                    # Build a list of indices sorted based on product order
                                    sorted_items = sorted(
                                        product_name_dict.items(),
                                        key=lambda x: sort_order.index(x[1]) if x[1] in sort_order else float("inf")
                                    )
                                    sorted_indices = [idx for idx, _ in sorted_items]

                                    # Reorder all columns in final_resp based on sorted indices
                                    sorted_final_resp = {}
                                    for col, col_data in final_resp.items():
                                        if isinstance(col_data, dict):
                                            sorted_final_resp[col] = {
                                                new_idx: col_data[old_idx]
                                                for new_idx, old_idx in enumerate(sorted_indices)
                                                if old_idx in col_data
                                            }
                                        else:
                                            sorted_final_resp[col] = col_data  # Keep as is if not a dict (e.g., string, list)

                                    final_resp = sorted_final_resp

                '''

                if len(cross_filters) == 1 or len(cross_filters) > 1:
                    print("insied 1st if")
                    print("cross_filters", cross_filters)
                    if list(set([x['key'] for x in cross_filters]))[0].strip('"') == 'SBU_Name' and cross_filters[0][
                        'value'] != '' and resp_format != 'stacked':
                        print("insied 2nd if")
                        condition = cross_filters[0]
                        if condition['key'].strip('"') == 'SBU_Name':
                            if condition['value'] in productOrders:
                                sort_order = productOrders[condition['value']]
                                print("final_resp", final_resp)
                                df = pd.DataFrame(final_resp)
                                if 'ProductName' in df.columns.tolist():
                                    df['sort_key'] = df['ProductName'].apply(
                                        lambda x: sort_order.index(x) if x in sort_order else float('inf'))
                                    df_sorted = df.sort_values(by='sort_key').drop(columns='sort_key').reset_index(
                                        drop=True)
                                    df_sorted = df_sorted.fillna('')
                                    final_resp = {col: df_sorted[col].to_dict() for col in df_sorted.columns}

        return {"status": True, "message": "Success", "data": {'data': final_resp, 'level': sorted_level,
                                                               'month_name': month_keys, 'sales_unit': measure_unit}}
    else:
        if resp_format:
            final_resp, hist_growth_details, tgt_growth_details = generate_stacked_data(drill_state, merged_df,
                                                                                        resp_format,
                                                                                        month_column='month_name')
        else:
            final_resp = {key: value.to_dict() for key, value in merged_df.to_dict(orient='series').items()}
        measure_unit = 'TMT'
        # if 'Zone_Name' in [x['key'] for x in cross_filters] or 'Region_Name' in [x['key'] for x in cross_filters] or 'SalesArea_Name' in [x['key'] for x in cross_filters]:
        #    measure_unit = 'MT'
        # if sbuName_req =="GAS" :
        #    measure_unit = 'MT'
        if 'cumulative' not in final_resp:
            final_resp['cumulative'] = {}
        if isinstance(final_resp, dict) and len(final_resp.get('ACTUAL_TMT_SALES', [])) == 1 and not drill_state:
            # if '"sbu_wise"' in [x['key'] for x in cross_filters] or 'sbu_wise' in [x['key'] for x in cross_filters]:
            # if resp_format == 'sbu_wise':
            if sbuWise:
                final_resp['cumulative']["0"] = sbuName_req.upper() + '_CUMMULATIVE_SALES'
            else:
                final_resp['cumulative']["0"] = 'CUMMULATIVE_SALES'
        else:
            if isinstance(final_resp, dict):
                for each_key in final_resp.get('ACTUAL_TMT_SALES', []):
                    if 'cumulative' not in final_resp:
                        final_resp['cumulative'] = {}
                    final_resp['cumulative'][each_key] = ''
        if all(not v for v in final_resp.values()):
            return {"status": False, "message": "No Data Present for the current selection",
                    "data": {'data': final_resp, 'level': {}, 'sales_unit': measure_unit}}

        return {"status": True, "message": "Success",
                "data": {'data': final_resp, 'level': {}, 'sales_unit': measure_unit}}


def generate_stacked_data(drill_state, df, resp_format='', month_column=''):
    hist_growth_details = []
    tgt_growth_details = []
    columns = df.columns.to_list()
    numeric_cols = [col for col in columns if col in list(MandateKeys.values())]
    if month_column:
        df[month_column] = pd.Categorical(df[month_column], categories=months, ordered=True)
        for column in numeric_cols:
            df[column].fillna(0, inplace=True)
        other_columns = list(set(columns) - set(numeric_cols + [month_column]))
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
            return df_pivot.to_dict(orient="records"), hist_growth_details, tgt_growth_details
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
                print("zone_data", zone_data.dtypes)
                for col in zone_data.columns:
                    if zone_data[col].dtype == 'int64' or zone_data[col].dtype == 'np.int64':
                        zone_data[col] = zone_data[col].astype(object)
                for column in numeric_cols:
                    # Creating series data
                    series_data.append({"name": f"{zone} {column.title()}", "stack": column.title(),
                                        "data": [zone_data.loc[m, column] if m in zone_data.index else 0
                                                 for m in unique_months]})
            return {"months": unique_months, "series": series_data}, hist_growth_details, tgt_growth_details
        elif resp_format == 'heat_map' and month_column:
            # making Cumulative sum of data for n-3
            present_month = datetime.datetime.now().strftime('%b')
            if present_month.lower() == 'apr':
                present_month = 'Mar'
            # Filtering cumulative_months
            cumulative_months = []
            if months.index(present_month) > 2:
                cumulative_months = months[0:months.index(present_month) - 1]
            # Summing data for cumulative data
            sum_cols = []
            for col in df.columns.tolist():
                # if df[col].dtype in ['float','np.float64','float64','int','int64','np.int64']:
                if 'SALES' in col:
                    df[col] = df[col].fillna(0).astype(float)
                    sum_cols.append(col)

            cumulative_data = {}
            if drill_state.strip('"') == 'SBU_Name':
                # cumulative_data = df[df['month_name'].isin(cumulative_months)].groupby('Zone_Name', as_index=False)[sum_cols].sum()
                if resp_format == "heat_map":
                    cumulative_data = df[df['month_name'].isin(cumulative_months)].groupby('Zone_Name', as_index=False)[
                        sum_cols].sum()
                else:
                    cumulative_data = \
                    df[df['month_name'].isin(cumulative_months)].groupby('ProductName', as_index=False)[sum_cols].sum()
            if drill_state.strip('"') == 'Zone_Name':
                # cumulative_data = df[df['month_name'].isin(cumulative_months)].groupby('Region_Name', as_index=False)[sum_cols].sum()
                cumulative_data = df[df['month_name'].isin(cumulative_months)].groupby('Region_Name', as_index=False)[
                    sum_cols].sum()
            if drill_state.strip('"') == 'Region_Name':
                cumulative_data = \
                df[df['month_name'].isin(cumulative_months)].groupby('SalesArea_Name', as_index=False)[sum_cols].sum()
            cumulative_data['month_name'] = 'Cum'
            non_cumulative_data = df[~df['month_name'].isin(cumulative_months)]
            df = pd.concat([cumulative_data, non_cumulative_data])
            # df.to_csv('/tmp/dfcum.csv', index=False)
            # making zonal summary above the exisiting heatmap
            if "month_name" in df.columns.tolist():
                # df['YTD_TMT_SALES'] =  df['ACTUAL_TMT_SALES'] +df['ACTUAL_HISTORY_TMT_SALES']
                # numeric_cols.append('YTD_TMT_SALES')
                df_cum = df_prev = df_pres = pd.DataFrame()
                curr_value = prev_value = tgt_value = cum_growth = tgt_growth = 0
                df_list = []
                for i in df['month_name'].unique().tolist():
                    df_cum = df[df['month_name'] == 'Cum']
                    if len(df['month_name'].unique().tolist()) > 1:
                        df_prev = df[df['month_name'] == df['month_name'].unique().tolist()[1]]
                    if len(df["month_name"].unique().tolist()) >= 3:
                        df_pres = df[df['month_name'] == df['month_name'].unique().tolist()[-1]]
                    # df_prev = df[df['month_name'] == df['month_name'].unique().tolist()[1]]
                    # df_pres = df[df['month_name'] == df['month_name'].unique().tolist()[-1]]
                if not df_cum.empty and not df_prev.empty and not df_pres.empty:
                    df_list = [df_cum, df_prev, df_pres]
                for idx, df_month in enumerate(df_list):
                    if 'ACTUAL_TMT_SALES' in df_month.columns.tolist():
                        df_month['ACTUAL_TMT_SALES'] = df_month['ACTUAL_TMT_SALES'].fillna(0).astype(float)
                        curr_value = df_month['ACTUAL_TMT_SALES'].sum()
                    if 'ACTUAL_HISTORY_TMT_SALES' in df_month.columns.tolist():
                        df_month['ACTUAL_HISTORY_TMT_SALES'] = df_month['ACTUAL_HISTORY_TMT_SALES'].fillna(0).astype(
                            float)
                        prev_value = df_month['ACTUAL_HISTORY_TMT_SALES'].sum()
                    if 'TARGET_TMT_SALES' in df_month.columns.tolist():
                        df_month['TARGET_TMT_SALES'] = df_month['TARGET_TMT_SALES'].fillna(0).astype(float)
                        tgt_value = df_month['TARGET_TMT_SALES'].sum()

                    if curr_value or prev_value:
                        if prev_value != 0:
                            cum_growth = ((curr_value - prev_value) / prev_value) * 100
                        if prev_value == 0:
                            cum_growth = 100
                        if 'TARGET_TMT_SALES' in df_month.columns.tolist():
                            if tgt_value != 0:
                                tgt_growth = ((curr_value - tgt_value) / tgt_value) * 100
                            else:
                                tgt_growth = 100

                        if idx == 0:
                            hist_growth_details.append({"title": "Cum_Hist_Growth", "value": cum_growth})
                            if 'TARGET_TMT_SALES' in df_month.columns.tolist():
                                tgt_growth_details.append({"title": "Cum_Tgt_Growth", "value": tgt_growth})
                        if idx == 1:
                            hist_growth_details.append(
                                {"title": f"{df['month_name'].unique().tolist()[1]}_Hist_Growth", "value": cum_growth})
                            if 'TARGET_TMT_SALES' in df_month.columns.tolist():
                                tgt_growth_details.append(
                                    {"title": f"{df['month_name'].unique().tolist()[1]}_Tgt_Growth",
                                     "value": tgt_growth})
                        if idx == 2:
                            hist_growth_details.append(
                                {"title": f"{df['month_name'].unique().tolist()[-1]}_Hist_Growth", "value": cum_growth})
                            if 'TARGET_TMT_SALES' in df_month.columns.tolist():
                                tgt_growth_details.append(
                                    {"title": f"{df['month_name'].unique().tolist()[-1]}_Tgt_Growth",
                                     "value": tgt_growth})

            # Renaming columns to lower case
            df.rename(columns={value: key for key, value in MandateKeys.items() if value in numeric_cols}, inplace=True)
            # Actual numeric columns
            numeric_cols = [key for key, value in MandateKeys.items() if value in numeric_cols]
            # Pivot Data - Creating separate columns for Actual, History, and Target
            df_pivot = df.pivot(index=other_columns[0], columns=month_column, values=numeric_cols)
            # Flatten MultiIndex Columns and rename them
            # df_pivot.columns = [f"{month}{metric.split('')[0]}" for metric, month in df_pivot.columns]
            df_pivot.columns = [f"{month}_{metric.split(',')[0]}" for metric, month in df_pivot.columns]
            # Reset Index to include 'Zone_Name'
            df_pivot.reset_index(inplace=True)
            # Keeping all nan's as zero's
            df_pivot.fillna(0, inplace=True)
            df_pivot.to_csv('/tmp/df_pivot.csv', index=False)
            df_pivot["YTD_actual"] = df_pivot.filter(like="_actual").sum(axis=1)
            df_pivot["YTD_history"] = df_pivot.filter(like="_history").sum(axis=1)
            df_pivot["YTD_target"] = df_pivot.filter(like="_target").sum(axis=1)
            df_pivot.to_csv('/tmp/df_pivot.csv', index=False)
            # df_pivot["YTD"] = df_pivot.select_dtypes(include="number").sum(axis=1)
            if 'YTD_actual' in df_pivot.columns.tolist() or 'YTD_history' in df_pivot.columns.tolist():
                if df_pivot['YTD_history'].sum() != 0:
                    ytd_hist_growth = ((df_pivot['YTD_actual'].sum() - df_pivot['YTD_history'].sum()) / df_pivot[
                        'YTD_history'].sum()) * 100
                elif df_pivot['YTD_history'].sum() == 0:
                    ytd_hist_growth = 100
                elif df_pivot['YTD_actual'].sum() == 0:
                    ytd_hist_growth = -100
                if 'YTD_target' in df_pivot.columns.tolist():
                    if df_pivot['YTD_target'].sum() != 0:
                        ytd_tgt_growth = ((df_pivot['YTD_actual'].sum() - df_pivot['YTD_target'].sum()) / df_pivot[
                            'YTD_target'].sum()) * 100
                    elif df_pivot['YTD_target'].sum() == 0:
                        ytd_tgt_growth = 100
                    elif df_pivot['YTD_actual'].sum() == 0:
                        ytd_tgt_growth = -100

                hist_growth_details.append({"title": "YTD_Hist_Growth", "value": ytd_hist_growth})
                if 'YTD_target' in df_pivot.columns.tolist():
                    tgt_growth_details.append({"title": "YTD_Tgt_Growth", "value": ytd_tgt_growth})

                    # Convert to Dictionary Format
            return df_pivot.to_dict(orient="records"), hist_growth_details, tgt_growth_details
        elif resp_format == 'cummulative' and month_column:
            df.iloc[:, 1:] = df.iloc[:, 1:].cumsum()
            return {key: value.to_dict() for key, value in
                    df.to_dict(orient='series').items()}, hist_growth_details, tgt_growth_details
        elif resp_format == 'grouped':
            # For Grouped data
            # Converting data to month wise report
            return [{"month_name": month, **{key: group[key].tolist() for key in numeric_cols + other_columns}}
                    for month, group in df.groupby("month_name")], hist_growth_details, tgt_growth_details
    else:
        if resp_format == 'cummulative' and month_column:
            df.iloc[:, 1:] = df.iloc[:, 1:].cumsum()

        # For regular drill down widgets
        return {key: value.to_dict() for key, value in
                df.to_dict(orient='series').items()}, hist_growth_details, tgt_growth_details
