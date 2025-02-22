import urdhva_base
import re
import json
import pandas as pd
import numpy as np
from typing import List, Dict
from collections import defaultdict
import utilities.helpers as helpers
import dateutil.parser as dt_parser
import utilities.fiscal_year as fiscal_year
import orchestrator.analytics.m60_performance as m60
import utilities.connection_mapping as connection_mapping
from orchestrator.dbconnector.widget_actions import widget_actions
from dashboard_studio_model import Charts_Get_Distinct_ValuesParams
from api_manager.charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams



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


def generate_group_by_conditions(filters,cross_filters, cumulative=False, drill_state='', time_grain='', resp_level= ''):
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
    print("resp_level",resp_level)
    #if isinstance(resp_level,list):
    #    for x in resp_level:
    #        group_by_filter.append(x)
    if resp_level =='sbu_level':
        print("sbu_level",resp_level)
        group_by_filter.append("sbu_name")
    if resp_level =='product_level':
        print("productname",resp_level)
        group_by_filter.append("productname")
    if resp_level == "sbu_level,product_level":
        group_by_filter.extend(['sbu_name','productname'])
    if isinstance(resp_level,list):
        group_by_filter.extend(['sbu_name','productname'])
    print("group_by_filter1111",group_by_filter)
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
        elif condition['key'] == '"fiscal_year"':
            fiscal_year_pre = condition['value']
        elif condition["key"] == "month_name":
            months = [mnt_name.strip() for mnt_name in condition["value"].split(",")]
    filters = [condition for condition in filters if condition['key'].strip('"') not in ['YTM', 'DATE', 'month_name',
                                                                                     'ind_analytics','table_graph','fiscal_year','company_name', 'table','table_month','inc','OMC', 'A', 'H', 'C']]
    if not months:
        months = pd.date_range(start=start_date, end=end_date, freq='MS').strftime('%b').tolist()
    return filters, fiscal_year_pre, fiscal_year_last, [key.upper() for key in months]


def calculate_market_share(df, group_by, fiscal_year_pre, fiscal_year_last, drill_state, time_grain, resp_format,resp_level,
                           filters,resp_format_org,sales_key="sales"):
    # Convert Decimal to float for Pandas compatibility
    df["sales"] = df["sales"].astype(float)

    # Calculate total sales per fiscal year
    if 'sbu_name' in df.columns.tolist():
        df.loc[df['sbu_name'] =='','sbu_name'] = 'Unknown'
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
                        print("gp itrms else",group_items)
                        if key != 'productname':
                            break
    else:
        if not drill_state.startswith('"'):
            drill_state = f'"{drill_state}"'

        if time_grain == "Monthly":
                group_items = [Base_Filters[Base_Filters.index(drill_state) + 1].strip('"'), "month_name"]
        else:
                group_items = [Base_Filters[Base_Filters.index(drill_state) + 1].strip('"')]
    print("resp_level",resp_level)
    if '"ind_analytics"' in [x['key'] for x in filters]:
        final_output = []
        data = summary.to_dict(orient = 'records')
        summary.to_csv('/tmp/df_req.csv',index = False)
        transformed_data = defaultdict(lambda: defaultdict(dict))
        for entry in data:
            sbu = entry["sbu_name"]
            product = entry["productname"]
            year = entry["fiscal_year"]
            market_share = entry["market_share"]

            # Store sales data
            transformed_data[(sbu, product)][f"Total_Sales_{year}"] = market_share
            transformed_data[(sbu, product)][f"HPCL_Sales_{year}"] = entry["hpcl_share"]
            transformed_data[(sbu, product)][f"BPCL_Sales_{year}"] = entry["bpcl_share"]
            transformed_data[(sbu, product)][f"IOC_Sales_{year}"] = entry["iocl_share"]

            # Convert to list format
            final_output = []

            for (sbu, product), values in transformed_data.items():
                entry = {"SBU": sbu, "PROD": product}

                years = sorted([y.split("-")[1] for y in values.keys() if "Total_Sales" in y])

                for i in range(len(years)):
                    curr_year = years[i]
                    prev_year = str(int(curr_year) - 1)
                    fiscal_year = f"{prev_year}-{curr_year}"
                    prev_fiscal_year = f"{int(prev_year)-1}-{prev_year}"

                    total_sales = values.get(f"Total_Sales_{fiscal_year}", 0)
                    prev_total_sales = values.get(f"Total_Sales_{prev_fiscal_year}", 0)

                    for company in ["HPCL", "BPCL", "IOC"]:
                        sales = values.get(f"{company}_Sales_{fiscal_year}", 0)
                        prev_sales = values.get(f"{company}_Sales_{prev_fiscal_year}", 0)

                        growth = 100.0 if prev_sales == 0 else ((sales - prev_sales) / prev_sales) * 100
                        market_share = (sales / total_sales) * 100 if total_sales else 0

                        entry[f"{company}_Sales_{fiscal_year}"] = sales
                        entry[f"{company}_Gr_{fiscal_year}"] = round(growth, 1)
                        entry[f"{company}_MktSh_{fiscal_year}"] = round(market_share, 1)

                final_output.append(entry)
        return {'message': 'Industry Analytics', 'data': final_output, 'status':True, "company": unique_companies}
        # print("updated_dicts",data)
    if 'sbu_level' in resp_level or 'product_level' in resp_level:
        print("this is sbu level if")
        summary.to_csv('/tmp/summary_data.csv',index = False)
        # Transforming data
        summary = summary.fillna('0')
        #for item in summary.to_dict(orient= 'records'):
            
        li = summary.to_dict(orient='records')
        print("group_items",group_items)
        transformed_data = []
        if 'sbu_level' in resp_level:
         for item in li:
            
            transformed_data.append(
                    {
                f"{prefix_map[item['fiscal_year']]}_market_share": item["market_share"],
                **{f"{prefix_map[item['fiscal_year']]}_{company.lower()}_share":
                       item[f"{company.lower()}_share"] for company in unique_companies},
                **{grp_item: item[grp_item] for grp_item in group_items},
                f"sbu_name":item["sbu_name"]
            }
                    )
        if 'product_level' in resp_level:
          for item in li:
            
            transformed_data.append(
                    {
                f"{prefix_map[item['fiscal_year']]}_market_share": item["market_share"],
                **{f"{prefix_map[item['fiscal_year']]}_{company.lower()}_share":
                       item[f"{company.lower()}_share"] for company in unique_companies},
                **{grp_item: item[grp_item] for grp_item in group_items},
                f"productname":item["productname"]
            }
                    )
        print("transformed_data",transformed_data)
        if len(resp_level) ==2 :
         for item in li:

            transformed_data.append(
                    {
                f"{prefix_map[item['fiscal_year']]}_market_share": item["market_share"],
                **{f"{prefix_map[item['fiscal_year']]}_{company.lower()}_share":
                       item[f"{company.lower()}_share"] for company in unique_companies},
                **{grp_item: item[grp_item] for grp_item in group_items},
                f"sbu_name":item["sbu_name"],
                f"productname":item['productname']
            }
                    )
    else:
        transformed_data = [
            {
                f"{prefix_map[item['fiscal_year']]}_market_share": item["market_share"],
                **{f"{prefix_map[item['fiscal_year']]}_{company.lower()}_share":
                       item[f"{company.lower()}_share"] for company in unique_companies},
                **{grp_item: item[grp_item] for grp_item in group_items}
            }
            for item in summary.to_dict(orient='records')
        ]
    print("#"*100)
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
    if resp_level in ['sbu_level','product_level']:
        df = pd.DataFrame(transformed_data)
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
    if resp_format == 'company_level'  and time_grain == 'Monthly'and '"inc"' in [x['key'] for x in filters]:
            print("this is inside if")

            cols_to_cumsum = [col for col in df.columns if col != 'month_name']
            df[cols_to_cumsum] = df[cols_to_cumsum].cumsum()
            return {'message':'Industry_Performance','status':True,'data':{key: value.to_dict() for key, value in df.to_dict(orient='series').items()}}
    if resp_format == 'company_level' and (resp_level =='sbu_level' or resp_level =='product_level') and  resp_format_org == 'company_level_heatmap':
        com_name = [x['value'] for x in filters if x['key'] =='"company_name"'][0]
        cols = [col for col in df.columns if com_name in col or 'month_name' in col or 'sbu_name' in col or 'productname' in col]
        print("com_name",com_name)
        df = df[cols]
        for col in df.columns:
            if 'actual' in col or 'history' in col:
                
                #df[col] = df[col].fillna(0).astype(float)
                df[col] = df[col].astype(str).replace('nan', '0').astype(float)

        import json
        month_mapper = {m: m.capitalize() for m in ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]}
        list1 = df.to_dict(orient='records')
        output = {}
        if resp_level =='sbu_level':
         req_key = 'sbu_name'
         req_names = set(item['sbu_name'] for item in list1)
        if resp_level == 'product_level':
            req_names = set(item['productname'] for item in list1)
            req_key = 'productname'
        for entry in list1:
            req_name = entry[req_key].upper()  # Ensure consistent uppercase handling
            month = month_mapper[entry["month_name"]]
            actual = entry[f"actual_{com_name}_share"] if entry[f"actual_{com_name}_share"] is not None else 0.0
            history = entry[f"history_{com_name}_share"] if entry[f"history_{com_name}_share"] is not None else 0.0

            if req_name not in output and 'sbu_level' in resp_level:
                output[req_name] = {"sbu_name": req_name.capitalize()}  # Convert back to title case for output
            if req_name not in output and 'product_level' in resp_level:
                output[req_name] = {"productname": req_name.capitalize()}
            # Sum values if they exist already
            output[req_name][f"{month}_actual"] = output[req_name].get(f"{month}_actual", 0.0) + actual
            output[req_name][f"{month}_history"] = output[req_name].get(f"{month}_history", 0.0) + history
        return {'message':'Industry Cummulative company_level Data','data':list(output.values()),'status':True,'company':unique_companies}

    if resp_format == 'company_level' and (resp_level =='sbu_level' or resp_level =='product_level') and  resp_format == 'company_level':
        print("came into resp level")
        print("len(df)",len(df))
        print("filters",filters)
        df.to_csv('/tmp/df_resp.csv',index=False)
        months = df['month_name'].unique().tolist()
        company = [x['value'].strip('"') for x in filters if x['key'] == '"company_name"'][0].lower()
        for col in df.columns.tolist():
            if 'actual' in col or 'history' in col:
                df[col] = df[col].fillna(0)
        
        list1 = df.to_dict(orient='records')
        list2 = []
        
        # Define the months in order
        #months = ['APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', 'JAN', 'FEB', 'MAR']

        # Group by sbu_name
        if resp_level =='sbu_level':
         req_key = 'sbu_name'
         req_names = set(item['sbu_name'] for item in list1)
        if resp_level == 'product_level':
            req_names = set(item['productname'] for item in list1)
            req_key = 'productname'
        print("company",company)
        print("months",months)
        print("req_names",req_names)
        for req_name in req_names:
            req_data = {
                'name': req_name,
                'Data': []
            }

            for month in months:
                month_data = {
                    'name': month.capitalize(),
                    'actual': 0,
                    'history': 0
                }

                # Find the actual and history data for the current month and sbu_name
                for item in list1:
                    if item['month_name'] == month and item[req_key] == req_name:
                        # Extract data for the specified company
                        actual_key = f'actual_{company}_share'
                        history_key = f'history_{company}_share'

                        if actual_key in item:
                            month_data['actual'] = item[actual_key]
                        if history_key in item:
                            month_data['history'] = item[history_key]

                req_data['Data'].append(month_data)

            list2.append(req_data)
        print("list2",list2)
        return {'message':'Industry_Performance_SBU_Level_Graphs','status':True,'data':list2,'company':unique_companies}

    print("table_month data")
    df.to_csv('/tmp/tabledf.csv',index = False)
    if '"table_graph"' in [x['key'] for x in filters]:
        company_columns = [col for col in df.columns if col not in ['actual_market_share', 'month_name']]
        company_totals = df[company_columns].sum()
        total_market_share = df['actual_market_share'].sum()
        # Construct output list
        output = [
            {
                "company": company.upper().replace("ACTUAL_", "").replace("_SHARE", ""),
                "market_share": round((share / total_market_share) * 100, 2),
                "tmt": int(share)
            }
            for company, share in company_totals.items()
        ]
        return {'message':'Industry_Performance_SBU_Level_Graphs','status':True,'data':output,'company':unique_companies}

    if '"table_month"' in [x['key'] for x in filters]:
        req_month = [x['value'] for x in filters if x['key'] =='"table_month"'][0]
        if req_month:
            for col in df.columns.tolist():
                if 'actual' in col or 'history' in col:
                    df[col] = df[col].astype(np.float64).fillna(0) 
            print(df.dtypes) 
            df_filtered = df[df["month_name"] == req_month.strip('"')]
            print(df_filtered.dtypes)
            print(df)
            print(df_filtered)
            # Extract company names dynamically by removing prefix 'actual_' from column names
            company_columns = [col.replace("actual_", "").replace("_share","") for col in df.columns if col.startswith("actual_")]

            output = []
            for company in company_columns:
                # Fetch actual and historical values for the current company in APR
                actual_volume = df_filtered[f"actual_{company}_share"].sum()
                historical_volume = df_filtered[f"history_{company}_share"].sum()

                # Compute market share change
                market_share_change = historical_volume - actual_volume

                # Compute cumulative values from the full dataset
                cumulative_actual = df[f"actual_{company}_share"].sum()
                cumulative_historical = df[f"history_{company}_share"].sum()
                cumulative_market_share_change = cumulative_historical - cumulative_actual

                # Build output JSON structure
                output.append({
                    "company": company.upper(),  # Capitalizing company names
                    "monthly": {
                        "volume": {
                            "actual": round(actual_volume,2),
                            "historical": round(historical_volume,2)
                        },
                        "marketShare": {
                            "actual": round((actual_volume / historical_volume * 100),2) if historical_volume else 0,
                            "historical": round(historical_volume,2),
                            "change": round(market_share_change,2)
                        }
                    },
                    "cumulative": {
                        "volume": {
                            "actual": round(cumulative_actual,2),
                            "historical": round(cumulative_historical,2)
                        },
                        "marketShare": {
                            "actual": round((cumulative_actual / cumulative_historical * 100),2) if cumulative_historical else 0,
                            "historical": round((cumulative_historical / df["history_market_share"].sum() * 100),2) if "history_market_share" in df.columns else None,
                            "change": round(cumulative_market_share_change,2)
                        }
                    }
                })

            # Print or save output
            #list2 = json.dumps(output, indent=2)
            print("output type",type(output))
            for each in output:
                 for each_ele in each:
                    if each[each_ele] is None:
                        each[each_ele] = ''
            return {'message':'Industry_Performance__latest_TableData','status':True,'data':output}

    if '"table_month"' in [x['key'] for x in filters]:
        req_month = [x['value'] for x in filters if x['key'] =='"table_month"'][0]
        if req_month:
            df.to_csv('/tmp/df_full.csv',index = False)
            full_df = df
            df = df[df['month_name'] == req_month.strip('"')]
            for col in df.select_dtypes(include=['category']).columns:
                df[col] = df[col].astype(str).fillna('')

            df = df.fillna('')
            data = df.to_dict(orient='records')
            list1 =data
            cumulative_volumes = defaultdict(int)
            cumulative_market_shares = defaultdict(float)
            monthly_volumes = defaultdict(int)
            monthly_market_shares = defaultdict(float)
            # Iterate through list1 to calculate cumulative and monthly data
            for entry in list1:
                month_name = entry['month_name']
                actual_market_share = entry['actual_market_share']
                
                for company in ['bpcl', 'hpcl', 'iocl', 'ril', 'gail', 'hmel', 'mrpl', 'nel', 'nrl', 'oil', 'ongc', 'shell']:
                    actual_share = entry[f'actual_{company}_share']
                    historical_share = entry[f'history_{company}_share']
                    
                    # Calculate monthly volume
                    monthly_volumes[company] += actual_share
                    
                    # Calculate monthly market share (handle division by zero)
                    if actual_market_share != 0.0:
                        monthly_market_shares[company] = (actual_share / actual_market_share) * 100
                    else:
                        monthly_market_shares[company] = 0.0
                    
                    # Calculate cumulative volume
                    cumulative_volumes[company] += actual_share
                    
                    # Calculate cumulative market share (handle division by zero)
                    if sum(cumulative_volumes.values()) != 0.0:
                        cumulative_market_shares[company] = (cumulative_volumes[company] / sum(cumulative_volumes.values())) * 100
                    else:
                        cumulative_market_shares[company] = 0.0

            # Prepare the final list2 format
            list2 = []
            for company in monthly_volumes.keys():
                # Calculate historical market share for the company
                historical_market_share = (sum([entry[f'history_{company}_share'] for entry in list1]) / sum([entry['history_market_share'] for entry in list1])) * 100 if sum([entry['history_market_share'] for entry in list1]) != 0.0 else 0.0
                
                company_data = {
                    'company': company.upper(),
                    'monthly': {
                        'volume': {
                            'actual': monthly_volumes[company],
                            'historical': sum([entry[f'history_{company}_share'] for entry in list1])
                        },
                        'marketShare': {
                            'actual': monthly_market_shares[company],
                            'historical': historical_market_share,
                            'change': monthly_market_shares[company] - historical_market_share
                        }
                    },
                    'cumulative': {
                        'volume': {
                            'actual': cumulative_volumes[company],
                            'historical': sum([entry[f'history_{company}_share'] for entry in list1])
                        },
                        'marketShare': {
                            'actual': cumulative_market_shares[company],
                            'historical': historical_market_share,
                            'change': cumulative_market_shares[company] - historical_market_share
                        }
                    }
                }
                list2.append(company_data)

            # Add the industry summary
            industry_data = {
                'company': 'Industry',
                'monthly': {
                    'volume': {
                        'actual': sum(monthly_volumes.values()),
                        'historical': sum([entry['history_market_share'] for entry in list1])
                    },
                    'marketShare': {
                        'actual': 100,
                        'historical': 100,
                        'change': None
                    }
                },
                'cumulative': {
                    'volume': {
                        'actual': sum(cumulative_volumes.values()),
                        'historical': sum([entry['history_market_share'] for entry in list1])
                    },
                    'marketShare': {
                        'actual': 100,
                        'historical': 100,
                        'change': None
                    }
                }
            }
            list2.append(industry_data)
        return {'message':'Industry_Performance_TableData','status':True,'data':list2}


    # Print the transformed list2
    data = {key: value.to_dict() for key, value in df.to_dict(orient='series').items()}
    companies = sorted(set(key.split("_")[1] for key in data.keys() if "_" in key and key != "cumulative" and "actual" not in key and "month_name" not in key))
    data['company'] = companies
    return {'message':'Industry_Performance','status':True,'data':data}

    return {'message':'Industry_Performance','status':True,'data':{key: value.to_dict() for key, value in df.to_dict(orient='series').items()}}


def generate_stacked_data(df, resp_format='', month_column=''):
    columns = df.columns.to_list()
    numeric_cols = [col for col in columns if col.startswith('history') or col.startswith('actual')]
    if month_column and month_column in df.columns:
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
    df.fillna(0, inplace=True)
    return {key: value.to_dict() for key, value in df.to_dict(orient='series').items()}


async def industry_performance(filters, cross_filters, drill_state="", time_grain="", resp_format="",resp_level=""):
    resp_format_org=resp_format
    if resp_format =='company_level_heatmap':
        resp_format = 'company_level'
        resp_format_org = 'company_level_heatmap'
    print("resp_format_org",resp_format_org)
    print("resp_format",resp_format)
    if resp_format == 'growth_table':
        return await industry_performance_compare(filters, [])
    elif resp_format == 'omc_cumulative':
        return await get_category_wise_cumulative_data(filters)
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
    if ',' in resp_level:
        resp_level = resp_level.split(',')
    # Fetching all group by filters, return should be a list always
    group_by_filter = generate_group_by_conditions(filters,cross_filters, cumulative, drill_state, time_grain,resp_level)
    print("group_by_filter",group_by_filter)
    print("resp_level",resp_level)
    org_filters = filters
    # OMC comparing filters
    for filter in filters:
        if filter['key'].strip('"') == "OMC" and filter['value']:
            if OMC.get(filter['value']):
                omc_compare = list(set(OMC[filter['value']]+["HPCL"]))
            else:
                print("filter",filter)

                omc_compare = list(set([filter['value'].split(",")[0]] + ["HPCL"]))
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
    print("filters are",filters)
    print("cross_filters",cross_filters)
    clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters +filters)
    '''
    if '"ind_analytics"' in [x['key'] for x in filters]:
        print("inside ind") 
        key_mapping = {
            '"sbu_level"': 'sbu_name',
            '"product_level"': 'product_name'
        }
        where_filters = filters
        for item in where_filters:
            if item['key'] in key_mapping:
                item['key'] = key_mapping[item['key']]
        where_filters = [x for x in where_filters if x['key']!= '"ind_analytics"']
        clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters + where_filters)
    else:
        clause = await widget_actions.WidgetActions.generate_filter_clause(cross_filters + filters)
    '''
    if clause:
        where_conditions = [clause]
    group_keys = [key.strip('"') for key in group_by_filter]
    req_keys = f"""ROUND(SUM("netweight_tmt")::numeric,0) AS "sales" """
    resp_data = await m60.collect_data([req_keys], 'industry_performance', where_conditions,
                                       "", "", group_by_filter+["coname"], "")
    return calculate_market_share(pd.DataFrame(resp_data), group_keys, fiscal_year_pre, fiscal_year_last,
                                  drill_state, time_grain, resp_format,resp_level,org_filters,resp_format_org)


def generate_growth_query(
    table_name: str,
    companies: List[str],
    drop_company: str,
    growth_company: str,
    overall_growth_companies: List[str],
    filter_conditions: str,
    drop_threshold: float = 0.98,
    drop_threshold_cond: str = '<',
    growth_threshold: float = 1.00,
    growth_threshold_cond: str = '<',
    overall_growth_threshold: float = 1.10,
    overall_threshold_cond: str = '<'
):

    # Build CASE WHEN for each company
    company_cases = ",\n".join(
        [
            f"SUM(CASE WHEN coname = '{company}' THEN current_year_amount ELSE 0 END) AS {company.lower()}_current,\n"
            f"SUM(CASE WHEN coname = '{company}' THEN last_year_amount ELSE 0 END) AS {company.lower()}_last"
            for company in companies if company in [growth_company, drop_company]
        ]
    )
    company_cases += ",\n"
    company_cases += ",\n".join([f"SUM(CASE WHEN coname in {tuple(overall_growth_companies)} THEN current_year_amount ELSE 0 END) AS market_share_current",
                                 f"SUM(CASE WHEN coname in {tuple(overall_growth_companies)} THEN last_year_amount ELSE 0 END) AS market_share_last"])

    # Combined growth check for selected companies
    overall_condition = "(" + " + ".join(
        [f"{company.lower()}_current" for company in ['market_share']]
    ) + ")"
    overall_last_condition = "(" + " + ".join(
        [f"{company.lower()}_last" for company in ['market_share']]
    ) + ")"

    # Final Query
    query = f"""
WITH current_year_sales AS (
    SELECT
        sbu_name,
        coname,
        month_name,
        ROUND(SUM(netweight_tmt), 2) AS current_year_amount
    FROM {table_name}
    WHERE fiscal_year='2024-2025'
        {'AND ' + filter_conditions if filter_conditions else ''}
    GROUP BY sbu_name, coname, month_name
),
last_year_sales AS (
    SELECT
        sbu_name,
        coname,
        month_name,
        ROUND(SUM(netweight_tmt), 2) AS last_year_amount
    FROM {table_name}
    WHERE fiscal_year='2023-2024'
        {'AND ' + filter_conditions if filter_conditions else ''}
    GROUP BY sbu_name, coname, month_name
),
combined AS (
    SELECT
        c.sbu_name,
        c.coname,
        c.month_name,
        c.current_year_amount,
        l.last_year_amount
    FROM current_year_sales c
    LEFT JOIN last_year_sales l
        ON c.sbu_name = l.sbu_name
        AND c.coname = l.coname
        AND c.month_name = l.month_name
),
company_growth AS (
    SELECT
        sbu_name,
        month_name,
        {company_cases}
    FROM combined
    GROUP BY sbu_name, month_name
)
SELECT
    sbu_name,
    month_name,
    {', '.join([f"{c.lower()}_current, {c.lower()}_last" for c in companies if c in [drop_company, growth_company]])},
    market_share_last, market_share_current
FROM company_growth
WHERE
    {drop_company.lower()}_last > 0
    AND {growth_company.lower()}_last > 0
    AND ROUND((({drop_company.lower()}_current - {drop_company.lower()}_last / {drop_company.lower()}_last) * 100), 2) {drop_threshold_cond} {drop_threshold}
    AND ROUND(((({growth_company.lower()}_current - {growth_company.lower()}_last)/ {growth_company.lower()}_last) * 100), 2) {growth_threshold_cond} {growth_threshold}
    AND ROUND(((({overall_condition} - {overall_last_condition}) / {overall_last_condition}) * 100), 2) {overall_threshold_cond} {overall_growth_threshold}
ORDER BY sbu_name, month_name;
"""
    return query


async def industry_performance_compare(filters, cross_filters, drill_state="", time_grain="", resp_format=""):
    companies = []
    omcs = []
    all_companies = list(set([company for sublist in OMC.values() for company in sublist]))
    for cond_filter in filters:
        if cond_filter['key'].strip('"') in all_companies:
            companies.append(cond_filter)
        elif cond_filter['key'].strip('"') in OMC:
            omcs.append(cond_filter)
    drop_company = 'HPCL'
    growth_company = ''
    drop_threshold = 0
    drop_threshold_cond = '>'
    growth_threshold = 0
    growth_threshold_cond = '>'
    overall_growth_threshold = 0
    overall_threshold_cond = '>'
    print(omcs)
    print(companies)
    if len(omcs):
        overall_growth_threshold = omcs[0]['value']
        overall_threshold_cond = omcs[0]['cond']
    if not len(companies):
        companies = [{"key": "\"HPCL\"", "cond": ">", "value": 20}]
    if len(companies):
        drop_threshold = companies[0]['value']
        drop_threshold_cond = companies[0]['cond']
        drop_company = companies[0]['key'].strip('"')
    if len(companies) > 1:
        growth_threshold = companies[1]['value']
        growth_threshold_cond = companies[1]['cond']
        growth_company = companies[1]['key'].strip('"')
    print(overall_threshold_cond, overall_growth_threshold)
    print(drop_threshold_cond, drop_threshold)
    print(growth_threshold_cond, growth_threshold)

    # Removing all filters related to company
    filters = [cond_filter for cond_filter in filters if cond_filter['key'].strip('"') not in OMC and
               cond_filter['key'].strip('"') not in all_companies]

    # Getting filters and years to include or exclude
    omc_companies = list(set([company for cond_filter in omcs for company in OMC[cond_filter['key'].strip('"')]]))
    filters, fiscal_year_pre, fiscal_year_last, months = get_date_filters(filters)
    filters.append({"key": "coname", "cond": "one-off",
                    "value": list(set(omc_companies + [cond_filter['key'].strip('"') for cond_filter in companies]))})
    where_conditions = []
    clause = await widget_actions.WidgetActions.generate_filter_clause(filters)
    if clause:
        where_conditions = [clause]
    query = generate_growth_query("industry_performance",
                                  list(set([cond_filter['key'].strip('"') for cond_filter in companies])),
                                  drop_company, growth_company,
                                  list(set(omc_companies + [cond_filter['key'].strip('"') for cond_filter in companies])),
                                  " AND ".join(where_conditions), drop_threshold, drop_threshold_cond,
                                  growth_threshold, growth_threshold_cond, overall_growth_threshold,
                                  overall_threshold_cond)
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    resp = await function(query=query)
    df = pd.DataFrame(resp)
    # Convert Decimal to float for pandas compatibility
    df[[f'{drop_company.lower()}_current', f'{drop_company.lower()}_last',
        f'{growth_company.lower()}_current', f'{growth_company.lower()}_last',
        'market_share_last', 'market_share_current']] = df[
        [f'{drop_company.lower()}_current', f'{drop_company.lower()}_last',
         f'{growth_company.lower()}_current', f'{growth_company.lower()}_last',
         'market_share_last', 'market_share_current']
    ].astype(float)

    # Group by 'sbu_name'
    result = {}
    for sbu, group in df.groupby('sbu_name'):
        financials_drop = {}
        financials_growth = {}
        financials_market = {}

        for _, row in group.iterrows():
            month = row['month_name']

            financials_drop[month] = {
                'actual': row[f'{drop_company.lower()}_current'],
                'history': row[f'{drop_company.lower()}_last']
            }

            financials_growth[month] = {
                'actual': row[f'{growth_company.lower()}_current'],
                'history': row[f'{growth_company.lower()}_last']
            }

            financials_market[month] = {
                'actual': row['market_share_current'],
                'history': row['market_share_last']
            }

        result[sbu] = [
            {"company": f"{drop_company}", "sales": financials_drop},
            {"company": f"{growth_company}", "sales": financials_growth},
            {"company": "Market", "sales": financials_market},
        ]

    return result


async def get_category_wise_cumulative_data(filters):
    filters, fiscal_year_pre, fiscal_year_last, months = get_date_filters(filters)
    where_conditions = []
    filters.append({"key": "\"fiscal_year\"", "cond": "equals", "value": "2024-2025"})
    for filter_cond in filters:
        filter_cond['key'] = filter_cond['key'].strip('"')
    clause = await widget_actions.WidgetActions.generate_filter_clause(filters)
    if clause:
        where_conditions = [clause]
    group_by = ["coname", "company_name"]
    req_keys = [f"""ROUND(SUM("netweight_tmt")::numeric,0) AS "sales" """, "coname", "company_name"]
    resp_data = await m60.collect_data(req_keys, 'industry_performance', where_conditions, "", "",
                                       group_by, "")
    df = pd.DataFrame(resp_data)
    result = df.groupby('company_name').apply(lambda x: dict(zip(x['coname'], x['sales']))).to_dict()
    return result


async def generate_response(question):
    question = question.upper()  # Convert to lowercase
    extracted = {key: [] for key in KEYWORDS}  # Initialize output keys
    # Match keywords to fields
    for key, words in KEYWORDS.items():
        for word in words:
            if word in question:
                extracted[key].append(word)  # Assign the found keyword (or later a matched value)
    return extracted


async def generate_industry_recommendations():
    # Generating auto recommendations
    # Compare HPCL last year vs this year lower by state, district, product
    ...
