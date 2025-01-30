import urdhva_base
import json
import traceback
import pandas as pd
import polars as pl
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

async def calculate_market_share(df, segregate=False):
    try:
        df = df.copy()
        df_pl = pl.from_pandas(df)
        # Get unique values
        unique_companies = df_pl["CoName"].unique().to_list()
        unique_years = df_pl["fiscal_year"].unique().to_list()

        # Columns to include based on selection
        selected_columns = [col for key, col in MandateKeys.items() if col in df_pl.columns]

        # Debugging
        print("Available columns:", df_pl.columns)
        print("Selected columns:", selected_columns)

        # Compute overall market share
        overall_share = (
            df_pl.group_by("fiscal_year")
            .agg([pl.col(col).sum().alias(col) for col in selected_columns])
            .to_dicts()
        )
        overall_share = {
            rec["fiscal_year"]: {col: rec[col] for col in selected_columns} for rec in overall_share
        }

        # Compute PSU market share
        psu_share = (
            df_pl.filter(pl.col("CoName").is_in(["IOCL", "HPCL", "BPCL"]))
            .group_by("fiscal_year")
            .agg([pl.col(col).sum().alias(col) for col in selected_columns])
            .to_dicts()
        )
        psu_share = {
            rec["fiscal_year"]: {col: rec[col] for col in selected_columns} for rec in psu_share
        }

        # Calculate company share
        company_share = []
        for year in unique_years:
            for company in unique_companies:
                # Filter data for company and year
                company_data = df_pl.filter(
                    (pl.col("CoName") == company) & (pl.col("fiscal_year") == year)
                ).select([pl.col(col).sum().alias(col) for col in selected_columns])

                company_sales = {col: company_data[col][0] if len(company_data) > 0 else 0 for col in selected_columns}
                
                # Compute market share percentages
                market_share = {
                    col: round(100 * (company_sales[col] / overall_share[year][col]), 2)
                    if overall_share[year][col] != 0 else 0
                    for col in selected_columns
                }
                psu_share_per = {
                    col: round(100 * (company_sales[col] / psu_share[year][col]), 2)
                    if psu_share[year][col] != 0 else 0
                    for col in selected_columns
                }

                company_type = df_pl.filter(pl.col("CoName") == company).select("Company_Name").to_numpy()[0][0]
                # If segregate mode is off, use a combined dictionary
                if not segregate:
                    company_share.append({
                        "COMNAME": company,
                        "COMTYPE": company_type,
                        "FIN_YEAR": year,
                        "CompanySize": company_sales[MandateKeys["actual"]],
                        "Zone_Name": df_pl["Zone_Name"].unique().to_list(),
                        "fiscal_year": df_pl["fiscal_year"].unique().to_list(),
                        **{col: company_sales[col] for col in selected_columns},
                        "OverAllMarketSize": overall_share[year][MandateKeys["actual"]],
                        "PSUSize": psu_share[year][MandateKeys["actual"]],
                        "MarketSharePer": market_share[MandateKeys["actual"]],
                        "PSUSharePer": psu_share_per[MandateKeys["actual"]],
                    })
                else:
                    # Create separate records for each metric
                    company_share.append({
                        "COMNAME": company,
                        "FIN_YEAR": year,
                        "MODEL": "CompanySize",
                        "Value": company_sales[MandateKeys["actual"]]
                    })
                    company_share.append({
                        "COMNAME": company,
                        "FIN_YEAR": year,
                        "MODEL": "MarketSharePer",
                        "Value": market_share[MandateKeys["actual"]]
                    })
                    company_share.append({
                        "COMNAME": company,
                        "FIN_YEAR": year,
                        "MODEL": "PSUSharePer",
                        "Value": psu_share_per[MandateKeys["actual"]]
                    })
        for entry in company_share:
            for key, value in entry.items():
                if isinstance(value, (list, dict)):  # Convert lists/dicts to strings
                    entry[key] = str(value)
        df_company_share = pl.DataFrame(company_share)
        df_company_share.write_csv("company_share_data.csv")
        return company_share

    except Exception as e:
        print(traceback.format_exc())
        return {"status": False, "message": str(e), "data": []}

    # try:
    #     df = df.copy()
    #     df_pl = pl.from_pandas(df)

    #     # Get unique values
    #     unique_companies = df_pl["CoName"].unique().to_list()
    #     unique_years = df_pl["fiscal_year"].unique().to_list()

    #     # Columns to include based on selection
    #     selected_columns = [col for key, col in MandateKeys.items() if col in df_pl.columns]

    #     # Compute overall market share
    #     overall_share = (
    #         df_pl.group_by("fiscal_year")
    #         .agg([pl.col(col).sum().alias(col) for col in selected_columns])
    #         .to_dicts()
    #     )
    #     overall_share = {
    #         rec["fiscal_year"]: {col: rec[col] for col in selected_columns} for rec in overall_share
    #     }

    #     # Compute PSU market share
    #     psu_share = (
    #         df_pl.filter(pl.col("CoName").is_in(["IOCL", "HPCL", "BPCL"]))
    #         .group_by("fiscal_year")
    #         .agg([pl.col(col).sum().alias(col) for col in selected_columns])
    #         .to_dicts()
    #     )
    #     psu_share = {
    #         rec["fiscal_year"]: {col: rec[col] for col in selected_columns} for rec in psu_share
    #     }

    #     # Create a dictionary to store the final result
    #     company_share_dict = {}

    #     # Calculate company share
    #     for year in unique_years:
    #         for company in unique_companies:
    #             # Filter data for company and year
    #             company_data = df_pl.filter(
    #                 (pl.col("CoName") == company) & (pl.col("fiscal_year") == year)
    #             ).select([pl.col(col).sum().alias(col) for col in selected_columns])

    #             company_sales = {col: company_data[col][0] if len(company_data) > 0 else 0 for col in selected_columns}

    #             # Compute market share percentages
    #             market_share = {
    #                 col: round(100 * (company_sales[col] / overall_share[year][col]), 2)
    #                 if overall_share[year][col] != 0 else 0
    #                 for col in selected_columns
    #             }
    #             psu_share_per = {
    #                 col: round(100 * (company_sales[col] / psu_share[year][col]), 2)
    #                 if psu_share[year][col] != 0 else 0
    #                 for col in selected_columns
    #             }

    #             # Get the company type from the Company_Name column
    #             company_type = df_pl.filter(pl.col("CoName") == company).select("Company_Name").to_numpy()[0][0]
    #             zone_name = ", ".join(df_pl.filter(pl.col("CoName") == company).select("Zone_Name").unique().to_numpy().flatten())
    #             # Construct company share for the current year and company
    #             company_data_dict = {
    #                 "COMNAME": company,  # CoName from company
    #                 "COMTYPE": company_type,  # Company_Name from Company_Name
    #                 "FIN_YEAR": year,
    #                 "MarketSharePer": market_share[MandateKeys["actual"]],
    #                 "PSUSharePer": psu_share_per[MandateKeys["actual"]],
    #                 "OverAllMarketSize": overall_share[year][MandateKeys["actual"]],
    #                 "PSUSize": psu_share[year][MandateKeys["actual"]],
    #                 "Zone_Name": df_pl["Zone_Name"].unique().to_list(),
    #                 "Zone_Value": company_sales[MandateKeys["actual"]]
    #             }

    #             # Add to the dictionary for each company
    #             if company not in company_share_dict:
    #                 company_share_dict[company] = []

    #             company_share_dict[company].append(company_data_dict)

    #     # Format the output according to the desired structure
    #     final_result = {}
    #     for company, share_data in company_share_dict.items():
    #         company_data = []
    #         for data in share_data:
    #             company_data.append({
    #                 "zone_name": data["Zone_Name"],
    #                 "zone_value": data["Zone_Value"],
    #                 "COMNAME": data["COMNAME"],
    #                 "COMTYPE": data["COMTYPE"],  # Add COMTYPE to the final result
    #                 "market_share": data["MarketSharePer"]
    #             })
    #         final_result[company] = company_data

    #     return final_result

    # except Exception as e:
    #     print(traceback.format_exc())
    #     return {"status": False, "message": str(e), "data": []}


async def get_date_filters(start_date, end_date, resp_format='%Y-%m-%d', day_resp_format="%Y%m%d"):
    """
    Function to get multiple date filters for day level filter, month level filter
    :param start_date:
    :param end_date:
    :param resp_format:
    :return:
    """
    try:
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
    
    except Exception as e:
        print(f"Error in get_date_filters: {str(e)}")
        print(traceback.format_exc())


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
    try:
        if group_by_filter and not isinstance(group_by_filter, list):
            group_by_filter = [group_by_filter]
        print("group_by_filter", group_by_filter)
        # Flatten the group_by_filter list in case it has nested lists
        flattened_filters = []
        for item in group_by_filter:
            if isinstance(item, list):
                flattened_filters.extend(item)  # Add elements of the inner list
            else:
                flattened_filters.append(item)
        for grp_key in flattened_filters:
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
            query += f" GROUP BY {','.join(flattened_filters)}"
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        print("-" * 30)
        print(query)
        print("-" * 30)
        resp = await function(query=query)
        return resp

    except Exception as e:
        print(f"Error in collect_data: {e}")
        print(traceback.format_exc())

# def get_group_by_filter_key(cross_filters):
#     """
#     Getting group by filter key based on cross filters
#     :param cross_filters:
#     :return:
#     """
#     print("cross_filters --> ", cross_filters)
#     group_by_filter = '"month_name"', '"Company_Name"' # added Company_Name key for the company wise grouping
#     if cross_filters:
#         print(" if cross_filters --> ", cross_filters)
#         index = 0
#         if len([rec['value'] for rec in cross_filters if 'lubes' in rec['value'].lower()
#                                                          and rec['key'].strip('"') == "SBU_Name"]):
#             print(" into if cross_filters --> ", cross_filters)                                                         
#             for key in [rec['key'] for rec in cross_filters]:
#                 print(" into for key --> ", key)
#                 if key in Lubes_Filters and Lubes_Filters.index(key) > index:
#                     print(" into if key --> ", key)
#                     index = Lubes_Filters.index(key)
#                     print(" into if index --> ", index)
#             group_by_filter = Lubes_Filters[index + 1]
#             print(" into if group_by_filter --> ", group_by_filter)
#         else:
#             print(" into else cross_filters --> ", cross_filters)
#             for key in [rec['key'] for rec in cross_filters]:
#                 print(" into else key --> ", key)
#                 if key in Base_Filters and Base_Filters.index(key) > index:
#                     print(" into else key --> ", key)
#                     index = Base_Filters.index(key)
#                     print(" into else index --> ", index)
#             group_by_filter = Base_Filters[index + 1]
#             print(" into else group_by_filter --> ", group_by_filter)
#     return group_by_filter

def get_group_by_filter_key(cross_filters):
    try:
        print("cross_filters --> ", cross_filters)
        # group_by_filter = ['"month_name"', '"Company_Name"']  # Default grouping keys

        group_by_filter = ['"CoName"', '"Zone_Name"', '"Company_Name"', '"fiscal_year"']  # Default grouping keys        
        if cross_filters:
            print(" if cross_filters --> ", cross_filters)
            lubes_index = 0
            base_index = 0

            # Handle Lubes_Filters
            if len([rec['value'] for rec in cross_filters if 'lubes' in rec['value'].lower()
                                                            and rec['key'].strip('"') == "SBU_Name"]):
                print(" into if cross_filters (Lubes) --> ", cross_filters)
                for key in [rec['key'] for rec in cross_filters]:
                    print(" into for key (Lubes) --> ", key)
                    if key in Lubes_Filters and Lubes_Filters.index(key) > lubes_index:
                        print(" into if key (Lubes) --> ", key)
                        lubes_index = Lubes_Filters.lubes_index(key)
                        print(" into if lubes_index --> ", lubes_index)
                # Add next level filter for Lubes
                lubes_group_by = Lubes_Filters[lubes_index + 1] if lubes_index + 1 < len(Lubes_Filters) else None
                if lubes_group_by:
                    group_by_filter.append(lubes_group_by)
                    print("Lubes group_by_filter updated --> ", group_by_filter)

            # Handle Base_Filters
            for key in [rec['key'] for rec in cross_filters]:
                print(" into for key (Base) --> ", key)
                if key in Base_Filters and Base_Filters.index(key) > base_index:
                    print(" into if key (Base) --> ", key)
                    base_index = Base_Filters.index(key)
                    print(" into if base_index --> ", base_index)
            # Add next level filter for Base
            base_group_by = Base_Filters[base_index + 1] if base_index + 1 < len(Base_Filters) else None
            if base_group_by:
                group_by_filter.append(base_group_by)
                print("Base group_by_filter updated --> ", group_by_filter)

        return group_by_filter
    except Exception as e:
        print(f"Error in get_group_by_filter: {e}")
        print(traceback.format_exc())



async def industry_performance(filters, cross_filters, drill_state):
    try:
        if not cross_filters:
            cross_filters = []
        group_by_filter = get_group_by_filter_key(cross_filters)

        # Assigning empty variables
        # history = actual = target = start_date = end_date = start_date_history = end_date_history = ""
        history = actual = start_date = end_date = start_date_history = end_date_history = ""

        end_date = fiscal_year.FiscalYear.current().fiscal_year_end_date
        start_date = fiscal_year.FiscalYear.current().fiscal_year_start_date

        # For Current Year and History Year removed FY format for the query 
        curr_year = int(str(fiscal_year.FiscalYear.current()).strip('FY'))
        his_year = int(str(fiscal_year.FiscalYear.current().prev_fiscal_year).strip('FY'))
        
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
        print("get_group_by_filter_key actual", group_by_filter) 
        
        
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
                print("group_by_filter.strip", group_by_filter)
                print("actual_data ", actual_data)
                print("actual_data ", actual_data.columns)
                if isinstance(group_by_filter, list):
                    # If it's a list, process each item
                    group_by_filter_key = [col.strip('"') for col in group_by_filter]
                else:
                    # If it's a string, strip directly
                    group_by_filter_key = group_by_filter.strip('"')
                actual_data = actual_data.groupby(group_by_filter_key)['IND_ACTUAL_TMT_SALES'].sum().reset_index()
                actual_data['IND_ACTUAL_TMT_SALES'] = actual_data['IND_ACTUAL_TMT_SALES'].fillna(0)
                actual_data = actual_data.to_dict(orient='records')

        # Data Retrival for last financial year
        print("get_group_by_filter_key", group_by_filter)
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
                                                    where_conditions_history, his_year-1, his_year,
                                                    [group_by_filter]))
            if hist_data:
                hist_data = pd.DataFrame(hist_data)
                print("group_by_filter.strip", group_by_filter)
                print("hist_data ", hist_data)
                print("hist_data ", hist_data.columns)
                if isinstance(group_by_filter, list):
                    # If it's a list, process each item
                    group_by_filter_key = [col.strip('"') for col in group_by_filter]
                else:
                    # If it's a string, strip directly
                    group_by_filter_key = group_by_filter.strip('"')
                hist_data = hist_data.groupby(group_by_filter_key)['IND_ACTUAL_HISTORY_TMT_SALES'].sum().reset_index()
                hist_data['IND_ACTUAL_HISTORY_TMT_SALES'] = hist_data['IND_ACTUAL_HISTORY_TMT_SALES'].fillna(0)
                hist_data = hist_data.to_dict(orient='records')
        #df_ = [pd.DataFrame(d) for d in [actual_data, target_data, hist_data] if d]
        df_ = [pd.DataFrame(d) for d in [actual_data, hist_data] if d]
        merged_df = df_[0] if len(df_) else pd.DataFrame([])
        if len(df_) > 1:
            if isinstance(group_by_filter, list):
                # If it's a list, process each item
                group_by_filter_key = [col.strip('"') for col in group_by_filter]
            else:
                # If it's a string, strip directly
                group_by_filter_key = group_by_filter.strip('"')
            for df in df_[1:]:
                merged_df = pd.merge(merged_df, df, on=group_by_filter_key, how='outer')  # Outer merge with df2
        # Ordering Data for Month and SBU names
        if not merged_df.empty:
            if isinstance(group_by_filter, list):
                # Process the first element of the list for the logic
                group_key = group_by_filter[0].strip('"')  # Use the first key in the list
            else:
                # Process it directly as a string
                group_key = group_by_filter.strip('"')

            if group_key in ('month_name', 'SBU_Name'):
                # Determine the sort_key based on the group_key
                sort_key = months if group_key == 'month_name' else sbu_order

                # Add a temporary "data_order" column for sorting
                merged_df["data_order"] = merged_df[group_key].map({cond: i for i, cond in enumerate(sort_key)})

                # Sort values by "data_order" and clean up the column
                merged_df = merged_df.sort_values("data_order").drop(columns="data_order")

                # Filter rows based on the sort_key (case-insensitive match)
                merged_df = merged_df[merged_df[group_key].str.capitalize().isin(sort_key)]

                # Reset the index after sorting and filtering
                merged_df.reset_index(drop=True, inplace=True) 
        #If required keys not available keeping records with zero value
        # if target:
        #     if MandateKeys["target"] not in merged_df:
        #         merged_df[MandateKeys["target"]] = 0
        if actual:
            if MandateKeys["actual"] not in merged_df:
                merged_df[MandateKeys["actual"]] = 0
        if history:
            if MandateKeys["history"] not in merged_df:
                merged_df[MandateKeys["history"]] = 0
        if group_by_filter:
            # Handle case where group_by_filter is a list or a string
            if isinstance(group_by_filter, list):
                for filter_item in group_by_filter:
                    column_name = filter_item.strip('"')  # Strip quotes from the filter item
                    if column_name not in merged_df:
                        merged_df[column_name] = ""  # Add the column to merged_df if not present
            else:
                column_name = group_by_filter.strip('"')  # Strip quotes if group_by_filter is a string
                if column_name not in merged_df:
                    merged_df[column_name] = ""  # Add the column to merged_df if not present
        merged_df.fillna(0, inplace=True)
        resp = await calculate_market_share(merged_df)
        print("resp --> ", resp)
        # final_resp = {key: value.to_dict() for key, value in merged_df.to_dict(orient='series').items()}
        # final_resp = [dict(zip(merged_df.columns, row)) for row in merged_df.values]
        return {"status": True, "message": "Success", "data": resp}

    except Exception as e:
        print(traceback.format_exc())
        return {"status": False, "message": str(e), "data": []}
