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

class LPGCDCMSActions:
    def __init__(self):
        ...
        
    async def filter_data(self, df, _filters):
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
    
    async def get_financial_year(self):
        today = datetime.now()
        if today.month < 4:
            start_year = today.year - 1
        else:
            start_year = today.year
        end_year = start_year + 1
        financial_year = f"{start_year}-{end_year}"
        return financial_year
    

    @staticmethod
    def get_next_level_drill_params(present_group):
        ...

    
    @staticmethod
    async def lpg_cdcms_monthly_sales(self, filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        # Reverse mapping (for returning the short form)
        reverse_month_mapping = {v: k for k, v in month_mapping.items()}
        lpg_cdcms_month_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms_month")

        financial_year = await self.get_financial_year()
        
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
            resp = await self.filter_data(resp, _filters)
            if resp.empty:
                return {"status": True, "message": "success", "data": resp}
            resp['Month_Number'] = resp['Month_Number'].astype(str)
            resp = resp.groupby(["Month", "Month_Number"], as_index=False).agg({
                    "Total Sales": lambda x: x.sum() / 10000000
                })
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
        resp = await self.filter_data(resp, _filters)
        
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
    async def lpg_cdcms_booking_vs_sales_vs_pending(self, filters, cross_filters, drill_state):
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
            lpg_cdcms_query_ += ' GROUP BY "ZOName", "ROName", "SAName", "Execution_Date", "DistributorName", "ConsumerType", "CylType"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            lpg_cdcms_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_cdcms_query_, access_filters, drill_state)
            lpg_cdcms_query_ += ' GROUP BY "ZOName", "ROName", "SAName", "Execution_Date", "DistributorName", "ConsumerType", "CylType"'
            resp = await function(query=lpg_cdcms_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = await self.filter_data(resp, _filters)
            resp = resp.groupby(["ZOName"], as_index=False).agg({
                    "Bookings": "sum",
                    "Sales": "sum",
                    "Pending": "sum"
                })
            # Fill missing values for numerical columns
            for each_float_col in [
                "Bookings", "Sales", "Pending"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0).round(2)
            for each_str_col in [
                "ZOName"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        
        resp = await function(query=lpg_cdcms_query_)
        resp = pd.DataFrame(resp)
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        resp = await self.filter_data(resp, _filters)
        # Fill missing values for numerical columns
        for each_float_col in [
            "Bookings", "Sales", "Pending"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "ZOName"
        ]:
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
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_cdcms_sakhi_registrations(self, filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        financial_year = await self.get_financial_year()
        if filters:
            sakhi_registrations_query = lpg_plant_queries.lpg_plant_query.get("sakhi_registrations")
            sakhi_registrations_query_ = sakhi_registrations_query
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
            sakhi_registrations_query_  += ' GROUP BY "Month", "Month_Number", "ZoneNames", "ROName", "SAName" '
        else:
            sakhi_registrations_query_ = '''
                SELECT 
                    "Month",
                    "Month_Number",
                    SUM("SakhiRegisteredCount") AS "SakhiRegistered",
                    "ZoneNames", "ROName", "SAName", "DistributorName"
                FROM
                    "sakhi_registrations_data"
                WHERE
                    "Financial_Year" IN ('2024-2025')
                GROUP BY "Month", "Month_Number"
            '''
            
        print(sakhi_registrations_query_)
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
