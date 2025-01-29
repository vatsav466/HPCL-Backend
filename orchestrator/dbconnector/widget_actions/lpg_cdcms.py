import urdhva_base
import polars as pl
import numpy as np
import pandas as pd
import hpcl_ceg_model
import dashboard_studio_model
from datetime import datetime
from dateutil.relativedelta import relativedelta
import utilities.connection_mapping as connection_mapping
from orchestrator.dbconnector.widget_actions import widget_actions
from api_manager.charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
import orchestrator.dbconnector.widget_actions.lpg_plant_queries as lpg_plant_queries

month_mapping = {
            "Jan": "January",
            "Feb": "February",
            "Mar": "March",
            "Apr": "April",
            "May": "May",
            "Jun": "June",
            "Jul": "July",
            "Aug": "August",
            "Sep": "September",
            "Oct": "October",
            "Nov": "November",
            "Dec": "December"
    }

async def filter_data(df, _filters):
        try:
            if _filters:
                mask = pd.Series(True, index=df.index)
                for _filter in _filters:
                    for key, value in _filter.items():
                        key = key.replace('"','')
                        mask = mask & (df[key].fillna('') == value)
                df = df[mask]
                return df
        except Exception as e:
            print("Exception in filtering data :", str(e))
        return df
    
async def get_financial_year():
    today = datetime.now()
    if today.month < 4:
        start_year = today.year - 1
    else:
        start_year = today.year
    end_year = start_year + 1
    financial_year = f"{start_year}-{end_year}"
    return financial_year


class LPGCDCMSActions:        

    @staticmethod
    def get_next_level_drill_params(present_group):
        ...
        
    
    @staticmethod
    async def lpg_cdcms_actual_vs_historic_sales(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        # Reverse mapping (for returning the short form)
        reverse_month_mapping = {v: k for k, v in month_mapping.items()}
        lpg_cdcms_sales_comparision_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms_sales_comparision")
        today = datetime.now()
        if today.month < 4:
            start_year = today.year - 1
            prev_start_year = today.year - 2
        else:
            start_year = today.year
            prev_start_year = today.year - 1
        end_year = start_year + 1
        prev_end_year = prev_start_year + 1
        financial_year = f"{start_year}-{end_year}"
        prev_financial_year = f"{prev_start_year}-{prev_end_year}"
        
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                if rec.key == '"Month"':
                    rec.value = [month_mapping.get(val.strip(), val.strip()) for val in rec.value]
                if isinstance(rec.value, str):
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)
            if conditions:
                lpg_cdcms_sales_comparision_query_ += ' WHERE '
                lpg_cdcms_sales_comparision_query_ += ' AND '.join(conditions)
            lpg_cdcms_sales_comparision_query_ += f' AND "ZOName"  NOT IN (\'Null\') AND "Financial_Year" IN (\'{str(financial_year)}\', \'{str(prev_financial_year)}\')'
            lpg_cdcms_sales_comparision_query_ += ' GROUP BY "Month", "Month_Number", "Financial_Year", "ZOName", "ROName", "SAName", "ConsumerType", "CylType", "DistributorName"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            lpg_cdcms_sales_comparision_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_cdcms_sales_comparision_query_, access_filters, drill_state)
            if "where" not in lpg_cdcms_sales_comparision_query_.lower():   
                lpg_cdcms_sales_comparision_query_ += f' WHERE "ZOName"  NOT IN (\'Null\') AND "Financial_Year" IN (\'{str(financial_year)}\', \'{str(prev_financial_year)}\')'
            else:
                lpg_cdcms_sales_comparision_query_ += f' AND "ZOName"  NOT IN (\'Null\') AND "Financial_Year" IN (\'{str(financial_year)}\', \'{str(prev_financial_year)}\')'
            lpg_cdcms_sales_comparision_query_ += ' GROUP BY "Month", "Month_Number", "Financial_Year", "ZOName", "ROName", "SAName", "ConsumerType", "CylType", "DistributorName"'
            resp = await function(query=lpg_cdcms_sales_comparision_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            resp = await filter_data(resp, _filters)
            if resp.empty:
                return {"status": True, "message": "success", "data": resp}
            current_year = resp[resp['Financial_Year'] == financial_year].groupby('Month')['sales_volume'].sum().reset_index()
            previous_year = resp[resp['Financial_Year'] == prev_financial_year].groupby('Month')['sales_volume'].sum().reset_index()
            resp = pd.merge(current_year, previous_year, on='Month', how='outer', suffixes=('_current', '_previous'))
            
            final_data = []
            for _, row in resp.iterrows():
                comparison = {
                    "Month": row['Month'][:3],
                    "Current_Year": financial_year,
                    "Previous_Year": prev_financial_year,
                    "Current_Sales": round(float(row['sales_volume_current'])/1000000, 2) if pd.notnull(row['sales_volume_current']) else 0,
                    "Previous_Sale": round(float(row['sales_volume_previous'])/1000000, 2) if pd.notnull(row['sales_volume_previous']) else 0
                }
                final_data.append(comparison)
            month_order = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
            final_data.sort(key=lambda x: month_order.index(x['Month']))
            return {"status": True, "message": "success", "data": final_data}
        # Execute the query
        resp = await function(query=lpg_cdcms_sales_comparision_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        resp = await filter_data(resp, _filters)
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "Month" in filter_keys:
            # Convert full month names to short form (e.g., "January" -> "Jan")
                resp["Month"] = resp["Month"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )
            if "Month" in filter_keys and "ZOName" not in filter_keys:
                current_year = resp[resp['Financial_Year'] == financial_year].groupby(["Month", "ZOName"])['sales_volume'].sum().reset_index()
                previous_year = resp[resp['Financial_Year'] == prev_financial_year].groupby(["Month", "ZOName"])['sales_volume'].sum().reset_index()
                resp = pd.merge(current_year, previous_year, on=["Month", "ZOName"], how='outer', suffixes=('_current', '_previous'))
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                current_year = resp[resp['Financial_Year'] == financial_year].groupby(["Month", "ZOName", "ROName"])['sales_volume'].sum().reset_index()
                previous_year = resp[resp['Financial_Year'] == prev_financial_year].groupby(["Month", "ZOName", "ROName"])['sales_volume'].sum().reset_index()
                resp = pd.merge(current_year, previous_year, on=["Month", "ZOName", "ROName"], how='outer', suffixes=('_current', '_previous'))
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                current_year = resp[resp['Financial_Year'] == financial_year].groupby(["Month", "ZOName", "ROName","SAName"])['sales_volume'].sum().reset_index()
                previous_year = resp[resp['Financial_Year'] == prev_financial_year].groupby(["Month", "ZOName", "ROName","SAName"])['sales_volume'].sum().reset_index()
                resp = pd.merge(current_year, previous_year, on=["Month", "ZOName", "ROName", "SAName"], how='outer', suffixes=('_current', '_previous'))
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                current_year = resp[resp['Financial_Year'] == financial_year].groupby(["Month", "ZOName", "ROName","SAName","DistributorName"])['sales_volume'].sum().reset_index()
                previous_year = resp[resp['Financial_Year'] == prev_financial_year].groupby(["Month", "ZOName", "ROName","SAName","DistributorName"])['sales_volume'].sum().reset_index()
                resp = pd.merge(current_year, previous_year, on=["Month", "ZOName", "ROName", "SAName", "DistributorName"], how='outer', suffixes=('_current', '_previous'))
            final_data = []
            for _, row in resp.iterrows():
                comparison = {
                    "Month": row['Month'][:3],
                    "Current_Year": financial_year,
                    "Previous_Year": prev_financial_year,
                    "Current_Sales": round(float(row['sales_volume_current'])/1000000, 2) if pd.notnull(row['sales_volume_current']) else 0,
                    "Previous_Sale": round(float(row['sales_volume_previous'])/1000000, 2) if pd.notnull(row['sales_volume_previous']) else 0
                }
                if "ZOName" in row:
                    comparison.update({"ZOName": row["ZOName"]})
                if "ROName" in row.keys():
                    comparison.update({"ROName": row["ROName"]})
                if "SAName" in row.keys():
                    comparison.update({"SAName": row["SAName"]})
                if "DistributorName" in row.keys():
                    comparison.update({"DistributorName": row["DistributorName"]})
                final_data.append(comparison)
            month_order = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
            final_data.sort(key=lambda x: month_order.index(x['Month']))
            return {"status": True, "message": "success", "data": final_data}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    
    @staticmethod
    async def lpg_cdcms_monthly_sales(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        # Reverse mapping (for returning the short form)
        reverse_month_mapping = {v: k for k, v in month_mapping.items()}
        lpg_cdcms_month_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms_month")

        financial_year = await get_financial_year()
        
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                if rec.key == '"Month"':
                    rec.value = [month_mapping.get(val.strip(), val.strip()) for val in rec.value]
                if isinstance(rec.value, str):
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)

            if conditions:
                lpg_cdcms_month_query_ += ' WHERE '
                lpg_cdcms_month_query_ += ' AND '.join(conditions)
            lpg_cdcms_month_query_ += f' AND "ZOName"  NOT IN (\'Null\') AND "Financial_Year"=\'{str(financial_year)}\''
            lpg_cdcms_month_query_ += ' GROUP BY "Month_Number", "Month", "ZOName", "ROName", "SAName", "ConsumerType", "CylType", "DistributorName"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            lpg_cdcms_month_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_cdcms_month_query_, access_filters, drill_state)
            if "where" not in lpg_cdcms_month_query_.lower():   
                lpg_cdcms_month_query_ += f' WHERE "ZOName"  NOT IN (\'Null\') AND "Financial_Year"=\'{str(financial_year)}\''
            else:
                lpg_cdcms_month_query_ += f' AND "ZOName"  NOT IN (\'Null\') AND "Financial_Year"=\'{str(financial_year)}\''
            lpg_cdcms_month_query_ += ' GROUP BY "Month_Number", "Month", "ZOName", "ROName", "SAName", "ConsumerType", "CylType", "DistributorName"'
            resp = await function(query=lpg_cdcms_month_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            resp = await filter_data(resp, _filters)
            if resp.empty:
                return {"status": True, "message": "success", "data": resp}
            resp['Month_Number'] = resp['Month_Number'].astype(str)
            resp = resp.groupby(["Month", "Month_Number"], as_index=False).agg({
                    "Total Sales": "sum"
                })
            resp['Total Sales'] = resp['Total Sales']/1000000
            resp['Total Sales'] = resp['Total Sales'].round(2)
            
            resp['Month_Number'] = resp['Month_Number'].astype(int)
            resp = resp.sort_values(by="Month_Number")
            del resp["Month_Number"]
            # Fill missing values for numerical columns
            for each_float_col in [
                "Total Sales"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "Month", "ZOName"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
                
        resp = await function(query=lpg_cdcms_month_query_)
        resp = pd.DataFrame(resp)
        resp = await filter_data(resp, _filters)
        
        for each_float_col in [
            "Total Sales"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)
        for each_str_col in [
            "Month", "ZOName"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "Month" in filter_keys:
            # Convert full month names to short form (e.g., "January" -> "Jan")
                resp["Month"] = resp["Month"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )
            if "Month" in filter_keys and "ZOName" not in filter_keys:
                grouped_resp = resp.groupby(["Month", "ZOName"], as_index=False).agg({
                    "Total Sales": "sum"
                })
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["Month", "ZOName","ROName"], as_index=False).agg({
                    "Total Sales": "sum"
                })
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["Month", "ZOName","ROName","SAName"], as_index=False).agg({
                    "Total Sales": "sum"
                })            
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["Month", "ZOName","ROName","SAName","DistributorName"],
                as_index=False).agg({
                    "Total Sales": "sum"
                    })
            if grouped_resp is not None:
                grouped_resp['Total Sales'] = grouped_resp['Total Sales']/10000000
                grouped_resp['Total Sales'] = grouped_resp['Total Sales'].round(2)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_cdcms_booking_vs_sales_vs_pending(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        lpg_cdcms_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms")
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                if isinstance(rec.value, str):
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)

            if conditions:
                lpg_cdcms_query_ += ' WHERE '
                lpg_cdcms_query_ += ' AND '.join(conditions)
            lpg_cdcms_query_ += ' GROUP BY "ZOName", "ROName", "SAName", "DistributorName", "ConsumerType", "CylType"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            lpg_cdcms_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_cdcms_query_, access_filters, drill_state)
            lpg_cdcms_query_ += ' GROUP BY "ZOName", "ROName", "SAName", "DistributorName", "ConsumerType", "CylType"'
            resp = await function(query=lpg_cdcms_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = await filter_data(resp, _filters)
            resp = resp.groupby(["ZOName"], as_index=False).agg({
                    "Bookings": "sum",
                    "Sales": "sum",
                    "Pending": "sum"
                })
            # Fill missing values for numerical columns
            for each_float_col in ["Bookings", "Sales", "Pending"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col]/1000000
                    resp[each_float_col] = resp[each_float_col].fillna(0.0).round(2)
            for each_str_col in ["ZOName"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        
        resp = await function(query=lpg_cdcms_query_)
        resp = pd.DataFrame(resp)
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        resp = await filter_data(resp, _filters)
        for each_str_col in ["ZOName"]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["ZOName","ROName"], as_index=False).agg({
                    "Bookings": "sum",
                    "Sales": "sum",
                    "Pending": "sum"
                })
            elif "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["ZOName","ROName","SAName"], as_index=False).agg({
                    "Bookings": "sum",
                    "Sales": "sum",
                    "Pending": "sum"
                })        
            elif "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["ZOName","ROName","SAName","DistributorName"],
                as_index=False).agg({
                    "Bookings": "sum",
                    "Sales": "sum",
                    "Pending": "sum"
                    })
            if grouped_resp is not None:
                for each_float_col in ["Bookings", "Sales", "Pending"]:
                    if each_float_col in grouped_resp.columns:
                        grouped_resp[each_float_col] = grouped_resp[each_float_col]/1000000
                        grouped_resp[each_float_col] = grouped_resp[each_float_col].fillna(0.0).round(2)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_cdcms_bookings_order_source_wise(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        cdcms_order_source_query_ = lpg_plant_queries.lpg_plant_query.get("cdcms_order_source")
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                # Now handle other cases
                if isinstance(rec.value, str):
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)
            if conditions:
                cdcms_order_source_query_ += ' WHERE '
                cdcms_order_source_query_ += ' AND '.join(conditions)
            cdcms_order_source_query_ += ' GROUP BY "OrderSourceName", "ZOName", "ROName", "SAName", "Execution_Date", "DistributorName", "ConsumerType", "CylType"'
        else:      
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            cdcms_order_source_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(cdcms_order_source_query_, access_filters, drill_state)
            if "where" not in cdcms_order_source_query_.lower():
                cdcms_order_source_query_ += f' WHERE "ZOName"  NOT IN (\'Null\')'
            else:
                cdcms_order_source_query_ += f' AND "ZOName"  NOT IN (\'Null\')'
            cdcms_order_source_query_ += ' GROUP BY "OrderSourceName", "ZOName", "ROName", "SAName", "Execution_Date", "DistributorName", "ConsumerType", "CylType"'

            resp = await function(query=cdcms_order_source_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = await filter_data(resp, _filters)
            resp = resp.groupby(["OrderSourceName"], as_index=False).agg({
                    "Total_Bookings": "sum"
                })
            # Fill missing values for numerical columns
            for each_float_col in [
                "Total_Bookings"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "OrderSourceName"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        resp = await function(query=cdcms_order_source_query_)        
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        resp = await filter_data(resp, _filters)
        for each_float_col in [
            "Total_Bookings"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)
        for each_str_col in [
            "OrderSourceName","ZOName","ROName","SAName","DistributorName"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "OrderSourceName" in filter_keys and "ZOName" not in filter_keys:    
                grouped_resp = resp.groupby(["OrderSourceName","ZOName"], as_index=False).agg({
                    "Total_Bookings": "sum"
                })
            elif "OrderSourceName" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["OrderSourceName","ZOName","ROName"], as_index=False).agg({
                    "Total_Bookings": "sum"
                })
            elif "OrderSourceName" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["OrderSourceName","ZOName","ROName","SAName"],
                as_index=False).agg({
                    "Total_Bookings": "sum"
                    })
            elif "OrderSourceName" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["OrderSourceName","ZOName","ROName","SAName","DistributorName"],
                as_index=False).agg({
                    "Total_Bookings": "sum"
                    })
            if grouped_resp is not None:
                grouped_resp["Total_Bookings"] = grouped_resp["Total_Bookings"]/1000000
                grouped_resp["Total_Bookings"] = grouped_resp["Total_Bookings"].round(2)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_cdcms_pending_cosumer_type_wise(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        lpg_pending_query_ = lpg_plant_queries.lpg_plant_query.get("overall_pending_pmuy_nmpuy")
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                # Now handle other cases
                if isinstance(rec.value, str):
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)

            if conditions:
                lpg_pending_query_  += ' WHERE '
                lpg_pending_query_  += ' AND '.join(conditions)
                lpg_pending_query_  += f' AND "ZOName"  NOT IN (\'Null\')'
            lpg_pending_query_  += ' GROUP BY "ZOName" ,"ROName","SAName","ConsumerType" ,"DistributorName", "CylType"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            lpg_pending_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_pending_query_, access_filters, drill_state)
            if "where" not in lpg_pending_query_.lower():                
                lpg_pending_query_  += f' WHERE "ZOName"  NOT IN (\'Null\')'
            else:
                lpg_pending_query_  += f' AND "ZOName"  NOT IN (\'Null\')'
            lpg_pending_query_  += ' GROUP BY "ZOName", "ROName", "SAName", "ConsumerType", "DistributorName", "CylType"'
            
            resp = await function(query=lpg_pending_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = await filter_data(resp, _filters)
            resp = resp.groupby(["ConsumerType"], as_index=False).agg({
                        "Total_pending": "sum",
                    })
            # Fill missing values for numerical columns
            for each_float_col in ["Total_pending"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)/1000000
                    resp[each_float_col] = resp[each_float_col].round(2)
            # Fill missing values for string columns
            for each_str_col in [
                "ZOName",
                "ROName",
                "SAName",
                "ConsumerType",
                "DistributorName"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": resp}

        # Execute the query
        resp = await function(query=lpg_pending_query_ )
        if resp:
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = await filter_data(resp, _filters)
            # Fill missing values for numerical columns
            for each_float_col in [
                "Total_pending"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "ZOName",
                "ROName",
                "SAName",
                "ConsumerType",
                "DistributorName"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            if filters:
                grouped_resp = None
                filter_keys = [rec.key.strip('"') for rec in filters]
                if "ConsumerType" in filter_keys and "ZOName" not in filter_keys:
                    grouped_resp = resp.groupby(["ConsumerType", "ZOName"], as_index=False).agg({
                        "Total_pending": "sum",
                    })
                if "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                    grouped_resp = resp.groupby(["ConsumerType","ZOName", "ROName"], as_index=False).agg({
                        "Total_pending": "sum",
                    })
                elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                    grouped_resp = resp.groupby(["ConsumerType","ZOName", "ROName", "SAName"], as_index=False).agg({
                        "Total_pending": "sum",
                    })
                elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                    grouped_resp = resp.groupby(["ConsumerType","ZOName", "ROName", "SAName", "DistributorName"],
                                                as_index=False).agg({
                        "Total_pending": "sum",
                    })
                if grouped_resp is not None:
                    grouped_resp["Total_pending"] = grouped_resp["Total_pending"]/1000000
                    grouped_resp["Total_pending"] = grouped_resp["Total_pending"].round(2)
                    return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        else:
            return {"status": True, "message":"success", "data":[]}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_cdcms_ageing(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        lpg_pending_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms_ageing")
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            conditions = []
            for rec in filters:
                if rec.key.replace('"', '') in ["pending_1_3_days", "pending_4_7_days", "pending_8_15_days", "pending_beyond_15_days"]:
                    continue
                rec.value = rec.value.split(",")
                if isinstance(rec.value, str):
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)
            if conditions:
                lpg_pending_query_  += ' WHERE '
                lpg_pending_query_  += ' AND '.join(conditions)
            if not conditions:
                lpg_pending_query_  += f' WHERE "ZOName" NOT IN ( \'Null\')'
            else:
                lpg_pending_query_  += f' AND "ZOName" NOT IN ( \'Null\')'
            lpg_pending_query_  += ' GROUP BY "ZOName", "ROName", "SAName", "ConsumerType", "DistributorName", "CylType" '
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            lpg_pending_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_pending_query_, access_filters, drill_state)
            if "where" not in lpg_pending_query_.lower():
                lpg_pending_query_ += f' WHERE "ZOName"  NOT IN (\'Null\')'
            else:
                lpg_pending_query_ += f' AND "ZOName"  NOT IN (\'Null\')'
            lpg_pending_query_  += ' GROUP BY "ZOName", "ROName", "SAName", "ConsumerType", "DistributorName", "CylType" '
            resp = await function(query=lpg_pending_query_ )
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = await filter_data(resp, _filters)
            
            for col in ["pending_1_3_days", "pending_4_7_days", "pending_8_15_days", "pending_beyond_15_days"]:
                if col in resp.columns:
                    resp[col] = resp[col].fillna(0).astype(np.float64)
                    resp[col] = np.where(
                                    resp['CylType'].fillna('') == 'C142',
                                    resp[col] * 14.2,
                                    np.where(
                                        resp['CylType'].fillna('') == 'C5',
                                        resp[col] * 5,
                                        resp[col]
                                    )
                                )
            resp = resp.groupby(["ConsumerType"], as_index=False).agg({
                    "pending_1_3_days": "sum",
                    "pending_4_7_days": "sum",
                    "pending_8_15_days": "sum",
                    "pending_beyond_15_days": "sum"
                })
            for col in ["pending_1_3_days", "pending_4_7_days", "pending_8_15_days", "pending_beyond_15_days"]:
                resp[col] = resp[col]/1000000
                resp[col] = resp[col].round(2)
            return {"status": True, "message": "success", "data": resp}

        resp = await function(query=lpg_pending_query_)
        resp = pd.DataFrame(resp)
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        resp = await filter_data(resp, _filters)
        
        for col in ["pending_1_3_days", "pending_4_7_days", "pending_8_15_days", "pending_beyond_15_days"]:
            if col in resp.columns:
                resp[col] = resp[col].fillna(0).astype(np.float64)
                resp[col] = np.where(
                                resp['CylType'].fillna('') == 'C142',
                                resp[col] * 14.2,
                                np.where(
                                    resp['CylType'].fillna('') == 'C5',
                                    resp[col] * 5,
                                    resp[col]
                                )
                            )
        for each_str_col in ["ZOName", "ROName", "SAName", "ConsumerType", "DistributorName"]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "pending_1_3_days" in filter_keys and "ZOName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName"], as_index=False).agg({
                    "pending_1_3_days": "sum"
                })
                grouped_resp = grouped_resp.pivot(index="ZOName", columns="ConsumerType", values="pending_1_3_days").fillna(0)
                _index = "ZOName"
            elif "pending_1_3_days" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName"], as_index=False).agg({
                    "pending_1_3_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="ROName", columns="ConsumerType", values="pending_1_3_days").fillna(0)
                _index = "ROName"
            elif "pending_1_3_days" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName", "SAName"],
                                            as_index=False).agg({
                    "pending_1_3_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="SAName", columns="ConsumerType", values="pending_1_3_days").fillna(0)
                _index = "SAName"
            elif "pending_1_3_days" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName"  in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName", "SAName","DistributorName"],
                                            as_index=False).agg({
                    "pending_1_3_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="DistributorName", columns="ConsumerType", values="pending_1_3_days").fillna(0)
                _index = "DistributorName"
            elif "pending_4_7_days" in filter_keys and "ZOName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName"], as_index=False).agg({
                    "pending_4_7_days": "sum"
                })
                grouped_resp = grouped_resp.pivot(index="ZOName", columns="ConsumerType", values="pending_4_7_days").fillna(0)
                _index = "ZOName"
            elif "pending_4_7_days" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName"], as_index=False).agg({
                    "pending_4_7_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="ROName", columns="ConsumerType", values="pending_4_7_days").fillna(0)
                _index = "ROName"
            elif "pending_4_7_days" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName", "SAName"],
                                            as_index=False).agg({
                    "pending_4_7_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="SAName", columns="ConsumerType", values="pending_4_7_days").fillna(0)
                _index = "SAName"
            elif "pending_4_7_days" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName"  in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName", "SAName","DistributorName"],
                                            as_index=False).agg({
                    "pending_4_7_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="DistributorName", columns="ConsumerType", values="pending_4_7_days").fillna(0)
                _index = "DistributorName"
            elif "pending_8_15_days" in filter_keys and "ZOName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName"], as_index=False).agg({
                    "pending_8_15_days": "sum"
                })
                grouped_resp = grouped_resp.pivot(index="ZOName", columns="ConsumerType", values="pending_8_15_days").fillna(0)
                _index = "ZOName"
            elif "pending_8_15_days" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName"], as_index=False).agg({
                    "pending_8_15_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="ROName", columns="ConsumerType", values="pending_8_15_days").fillna(0)
                _index = "ROName"
            elif "pending_8_15_days" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName", "SAName"],
                                            as_index=False).agg({
                    "pending_8_15_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="SAName", columns="ConsumerType", values="pending_8_15_days").fillna(0)
                _index = "SAName"
            elif "pending_8_15_days" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName"  in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName", "SAName","DistributorName"],
                                            as_index=False).agg({
                    "pending_8_15_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="DistributorName", columns="ConsumerType", values="pending_8_15_days").fillna(0)
                _index = "DistributorName"
            elif "pending_beyond_15_days" in filter_keys and "ZOName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName"], as_index=False).agg({
                    "pending_beyond_15_days": "sum"
                })
                grouped_resp = grouped_resp.pivot(index="ZOName", columns="ConsumerType", values="pending_beyond_15_days").fillna(0)
                _index = "ZOName"
            elif "pending_beyond_15_days" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName"], as_index=False).agg({
                    "pending_beyond_15_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="ROName", columns="ConsumerType", values="pending_beyond_15_days").fillna(0)
                _index = "ROName"
            elif "pending_beyond_15_days" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName", "SAName"],
                                            as_index=False).agg({
                    "pending_beyond_15_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="SAName", columns="ConsumerType", values="pending_beyond_15_days").fillna(0)
                _index = "SAName"
            elif "pending_beyond_15_days" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName"  in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName", "SAName","DistributorName"],
                                            as_index=False).agg({
                    "pending_beyond_15_days": "sum",
                })
                grouped_resp = grouped_resp.pivot(index="DistributorName", columns="ConsumerType", values="pending_beyond_15_days").fillna(0)
                _index = "DistributorName"

            grouped_resp[col] = grouped_resp[col]/1000000
            grouped_resp[col] = grouped_resp[col].round(2)
            result = [
                        {
                            "PMUY": row.get("PMUY", 0),
                            "NPMUY": row.get("NPMUY", 0),
                            _index: index
                        }
                        for index, row in grouped_resp.iterrows()
                    ]
            return {"status": True, "message": "success", "data": result}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_cdcms_domestic_sales_table(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        lpg_sale_table_ = lpg_plant_queries.lpg_plant_query.get("lpg_domestic_sale_table")
        
        access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
        lpg_sale_table_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_sale_table_, access_filters, drill_state)
        
        if not filters and not cross_filters:
            lpg_sale_table_ += f' WHERE "ZOName" IS NOT NULL'
            lpg_sale_table_ += ' GROUP BY "ZOName", "CylType", "ConsumerType" '
        
        resp = await function(query=lpg_sale_table_)
        if not resp:
            return {"status": True, "message": "No data available", "data": []}
        
        resp = pd.DataFrame(resp)
        for each_float_col in ["Total_Booking", "Total_Sales", "Total_Pending"]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)
        for each_str_col in ["ZOName", "CylType", "ConsumerType"]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna("").astype(str)
        resp = resp.groupby(["ZOName", "CylType", "ConsumerType"], as_index=False).agg({
            "Total_Booking": "sum",
            "Total_Sales": "sum",
            "Total_Pending": "sum"
        })
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_cdcms_current_financial_year_sales(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        financial_year = await get_financial_year()
        cumulative_sales_pmuy_npmuy_query_ = lpg_plant_queries.lpg_plant_query.get("cumulative_sales_pmuy_npmuy")
        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            cumulative_sales_pmuy_npmuy_query = lpg_plant_queries.lpg_plant_query.get("cumulative_sales_pmuy_npmuy")
            cumulative_sales_pmuy_npmuy_query_ = cumulative_sales_pmuy_npmuy_query
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                # Now handle other cases
                if isinstance(rec.value, str):
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)

            if conditions:
                cumulative_sales_pmuy_npmuy_query_ += ' WHERE '
                cumulative_sales_pmuy_npmuy_query_ += ' AND '.join(conditions)
            
            cumulative_sales_pmuy_npmuy_query_ += f' AND "ZOName"  NOT IN (\'Null\') AND "Financial_Year"=\'{str(financial_year)}\''
            cumulative_sales_pmuy_npmuy_query_ += ' GROUP BY "ZOName", "ROName", "SAName", "ConsumerType", "CylType", "DistributorName"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            cumulative_sales_pmuy_npmuy_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(cumulative_sales_pmuy_npmuy_query_, access_filters, drill_state)

            if not "where" in cumulative_sales_pmuy_npmuy_query_.lower():
                cumulative_sales_pmuy_npmuy_query_ += f' WHERE "ZOName"  NOT IN (\'Null\') AND "Financial_Year"=\'{str(financial_year)}\''
            else:
                cumulative_sales_pmuy_npmuy_query_ += f' AND "ZOName"  NOT IN (\'Null\') AND "Financial_Year"=\'{str(financial_year)}\''
            cumulative_sales_pmuy_npmuy_query_ += ' GROUP BY "ZOName", "ROName", "SAName", "ConsumerType", "CylType", "DistributorName"'
                                 
            resp = await function(query=cumulative_sales_pmuy_npmuy_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = await filter_data(resp, _filters)
            resp = resp.groupby(["ConsumerType"], as_index=False).agg({
                    "Sales": lambda x: x.sum() / 1000000
                })
            resp["Sales"] = resp["Sales"].round(2)
            # Fill missing values for numerical columns
            for each_float_col in ["Sales"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            # Fill missing values for string columns
            for each_str_col in [
                "ConsumerType"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": resp}
        
        # Execute the query
        resp = await function(query=cumulative_sales_pmuy_npmuy_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        resp = await filter_data(resp, _filters)
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        # Fill missing values for numerical columns
        for each_float_col in ["Sales"]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)
        for each_str_col in ["ConsumerType", "ZOName", "ROName", "SAName", "DistributorName"]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "ConsumerType" in filter_keys and "ZOName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType","ZOName"], 
                as_index=False).agg({"Sales": "sum"})
            elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType","ZOName","ROName"], 
                as_index=False).agg({"Sales": "sum"})
            elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType","ZOName","ROName","SAName"],
                as_index=False).agg({"Sales": "sum"})
            elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType","ZOName","ROName","SAName","DistributorName"],
                as_index=False).agg({"Sales": "sum"})
            if grouped_resp is not None:
                grouped_resp["Sales"] = grouped_resp["Sales"]/1000000
                grouped_resp["Sales"] = grouped_resp["Sales"].round(2)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_cdcms_sakhi_registrations(filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        financial_year = await get_financial_year()
        sakhi_registrations_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms_sakhi_registrations")
        if filters:
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                if isinstance(rec.value, str):
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)
            if conditions:
                sakhi_registrations_query_  += ' WHERE '
                sakhi_registrations_query_  += ' AND '.join(conditions)
            sakhi_registrations_query_  += f' AND "Financial_Year" IN (\'{financial_year}\')'
            sakhi_registrations_query_  += ' GROUP BY "Month", "Month_Number", "ZoneNames", "ROName", "SAName", "DistributorName" '
        else:
            if "where" not in sakhi_registrations_query_:
                sakhi_registrations_query_  += f' WHERE "Financial_Year" IN (\'{financial_year}\')'
            else:
                sakhi_registrations_query_  += f' AND "Financial_Year" IN (\'{financial_year}\')'
            sakhi_registrations_query_  += ' GROUP BY "Month", "Month_Number", "ZoneNames", "ROName", "SAName", "DistributorName" '
            
        resp = await function(query=sakhi_registrations_query_)
        resp = pl.DataFrame(resp)

        # Fill missing values
        numerical_columns = ["Month_Number", "SakhiRegistered"]
        string_columns = ["Month", "ZoneNames", "ROName", "SAName"]

        for col in numerical_columns:
            if col in resp.columns:
                resp = resp.with_columns(pl.col(col).fill_null(0.0))

        for col in string_columns:
            if col in resp.columns:
                resp = resp.with_columns(pl.col(col).fill_null("").cast(pl.Utf8))

        # Grouping and filtering
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]

            if "Month" in filter_keys and "ZoneNames" not in filter_keys:
                grouped_resp = resp.groupby(["Month", "ZoneNames"]).agg([
                    pl.sum("SakhiRegistered").alias("SakhiRegistered"),
                    pl.sum("Month_Number").alias("Month_Number"),
                ])
            elif "Month" in filter_keys and "ZoneNames" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["Month", "ZoneNames", "ROName"]).agg([
                    pl.sum("SakhiRegistered").alias("SakhiRegistered"),
                    pl.sum("Month_Number").alias("Month_Number"),
                ])
            elif "Month" in filter_keys and "ZoneNames" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["Month", "ZoneNames", "ROName", "SAName"]).agg([
                    pl.sum("SakhiRegistered").alias("SakhiRegistered"),
                    pl.sum("Month_Number").alias("Month_Number"),
                ])
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dicts()}
        # Convert the result to a dictionary for the response
        return {"status": True, "message": "success", "data": resp.to_dicts()}
