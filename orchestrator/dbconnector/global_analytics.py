import urdhva_base
import csv
import json
import calendar
import psycopg2
import traceback
import polars as pl
import numpy as np
import pandas as pd
import hpcl_ceg_model
import dashboard_studio_model
from datetime import datetime,timedelta
from psycopg2 import sql, errors
from collections import defaultdict
import utilities.helpers as helpers
import utilities.drill_mapping as drill_mapping
from dateutil.relativedelta import relativedelta
from orchestrator.analytics import m60_performance
from orchestrator.analytics import dry_out_analysis
from orchestrator.analytics import industry_performance
import utilities.connection_mapping as connection_mapping
from orchestrator.dbconnector.widget_actions import widget_actions
import orchestrator.dbconnector.connector_factory as connector_factory
from api_manager.charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
import orchestrator.dbconnector.widget_actions.lpg_plant_queries as lpg_plant_queries
from collections import defaultdict
import utilities.analog_data_mapping as category_mapping

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


async def addFilterValue(rec):
    if ',' in rec.value:
        rec_values = rec.value.split(',')
        rec_value_tup = tuple([i.strip() for i in rec_values])
        condition = f"{rec.key} IN {rec_value_tup} "
    else:
        condition = f"{rec.key} = '{rec.value}'"
    return condition


class GlobalAnalytics:        
    @staticmethod
    async def analytics(filters, cross_filters, drill_state):
        """
        Retrieves analytics data for the given filters and drill state.

        Args:
            filters (list): List of filter objects with the following structure:
                {
                    "key": str,  # Column name
                    "value": str,  # Filter value
                    "operator": str,  # Filter operator (e.g. =, !=, LIKE)
                    "type": str  # Filter type (e.g. string, number, date)
                }
            drill_state (dict): Drill state with the following structure:
                {
                    "column": str,  # Column name
                    "value": str,  # Drill value
                    "type": str  # Drill type (e.g. string, number, date)
                }

        Returns:
            dict: Analytics data with the following structure:
                {
                    "activeLocations": int,  # Number of active locations
                    "inactiveLocations": int,  # Number of inactive locations
                    "totalAlerts": str,  # Total number of alerts (formatted with commas)
                    "alertDistribution": list,  # List of objects with the following structure:
                        {
                            "name": str,  # Interlock name
                            "value": int  # Number of alerts
                        }
                    "top10Alerts": list,  # List of objects with the following structure:
                        {
                            "name": str,  # Interlock name
                            "value": int  # Number of alerts
                        }
                    "no_of_locations": int  # Number of locations
                }
        """

        analytics_query = lpg_plant_queries.lpg_plant_query.get("analytics")
        analytics_query_ = analytics_query

        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
            for filter_ in filters:
                if filter_.key:
                    # Update the key of the filter to include the alias 'a.'
                    filter_.key = f"a.{filter_.key}"
                
            # After modifying the filters, send the updated filters to apply_filter_drilldown
            analytics_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(analytics_query, filters, drill_state)
        try:
            # Execute the query
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(analytics_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print("Error: ", e)
            # Retry with the base query in case of an error
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(analytics_query)

        # Process the results
        data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)

        active_locations = set()
        inactive_locations = set()
        total_alerts = 0
        alert_distribution = defaultdict(int)
        top_alerts = defaultdict(int)
        interlock_alerts = defaultdict(lambda: defaultdict(int))

        # Process each alert
        for alert in data:
            sap_id = alert['sap_id']
            alert_status = alert['alert_status']
            severity = alert['severity']
            severity_count = alert['severity_count']
            interlock_name = alert['interlock_name']

            # Update active and inactive locations
            if alert_status == "Close":
                inactive_locations.add(sap_id)
            # elif alert_status == "Open":
            #     active_locations.add(sap_id)
            else:
                active_locations.add(sap_id)

            # Update total alerts
            total_alerts += severity_count

            # Update alert distribution by severity
            alert_distribution[severity] += severity_count

            # Update top alerts by interlock name
            top_alerts[interlock_name] += severity_count

            interlock_alerts[interlock_name][severity] += severity_count


        # Format the output
        result = {
            "activeLocations": len(active_locations),
            "inactiveLocations": len(inactive_locations),
            "totalAlerts": f"{total_alerts:,}",
            "alertDistribution": [
                {"name": severity, "value": severity_count}
                for severity, severity_count in alert_distribution.items()
            ],
            "top10Alerts": [
                {"name": name, "value": value}
                for name, value in sorted(top_alerts.items(), key=lambda x: x[1], reverse=True)[:10]
            ],
            "interlock_alerts": [
        {
            "interlock_name": interlock_name,
            **{key: value for key, value in details.items() if key != "interlock_name"}
        }
        for interlock_name, details in interlock_alerts.items()
    ]

        }

        return {"status": True, "message": "Success", "data": result}

    
    @staticmethod
    async def alert_ageing(filters, cross_filters, drill_state):
        """
        This method is used to fetch the alert ageing data for the given filters and drill state
        :param filters: The filter parameters
        :param drill_state: The drill down state
        :return: A dictionary containing the status, message and the alert ageing data
        """
        alert_ageing_query = lpg_plant_queries.lpg_plant_query.get("alert_ageing")
        alert_ageing_query_ = alert_ageing_query
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            alert_ageing_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(alert_ageing_query, filters, drill_state)
            print(alert_ageing_query_)
        try:
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(alert_ageing_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(alert_ageing_query)
        data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": data}
    
    @staticmethod
    async def day_wise_alerts(filters, cross_filters, drill_state):
        """
        Fetches the day-wise alerts data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the day-wise alerts data.
        """
        day_wise_alerts_query = lpg_plant_queries.lpg_plant_query.get("day_wise_alerts")
        day_wise_alerts_query_ = day_wise_alerts_query
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            day_wise_alerts_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(day_wise_alerts_query, filters, drill_state)
            print(day_wise_alerts_query_)
        try:
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(day_wise_alerts_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(day_wise_alerts_query)
        data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": data}
    
    @staticmethod
    async def location_severity_count(filters, cross_filters, drill_state):
        """
        Fetches the location severity count data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the location severity count data.
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        location_severity_count_query = lpg_plant_queries.lpg_plant_query.get("location_severity_count")
        location_severity_count_query_ = location_severity_count_query

        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            for filter_ in filters:
                
                # Explicitly qualify the column with the correct table alias
                filter_.key = f"a.{filter_.key}"  # Assuming "a" is the alias for the table containing "bu"
                # filter_condition = f" WHERE {filter_key} = '{filter_.value}'"
                # Add the filter condition before GROUP BY
                # location_severity_count_query_ = location_severity_count_query_.replace("GROUP BY", f"{filter_condition} GROUP BY")
                # break
            location_severity_count_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(location_severity_count_query_, filters, drill_state)
        try:
            resp = await function(query=location_severity_count_query_)
            # keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(location_severity_count_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            # Retry with the original query if the column is undefined
            # keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(location_severity_count_query)

        # Process the results
        # data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": resp}

    @staticmethod
    async def no_of_locations(filters, cross_filters, drill_state):
        """
        Fetches the top interlocks data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the top interlocks data.
        """
        no_of_locations_query = lpg_plant_queries.lpg_plant_query.get("no_of_locations")
        no_of_locations_query_ = no_of_locations_query
        if filters:
            no_of_locations_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(no_of_locations_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(no_of_locations_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(no_of_locations_query)
        no_of_locations_data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": no_of_locations_data}

    @staticmethod
    async def severity_count(filters, cross_filters, drill_state):
        """
        Fetches the severity count data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the severity count data.
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        severity_count_query = lpg_plant_queries.lpg_plant_query.get("severity_count")
        severity_count_query_ = severity_count_query
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LocationMaster.get_clause_conditions(formated=True)]
        if filters:
            for filter_ in filters:
                if filter_.key:
                    # Update the key of the filter to include the alias 'a.'
                    filter_.key = f'lm.{filter_.key}'
            severity_count_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(severity_count_query, filters, drill_state)
        try:
            severity_count_data = await function(query=severity_count_query_)
            # keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(severity_count_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            # keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(severity_count_query)
        # severity_count_data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        for item in severity_count_data:
            item['operability_index'] = 99
        return {"status": True, "message": "success", "data": severity_count_data}
    
    @staticmethod
    async def hourly_alerts(filters, cross_filters, drill_state):
        """
        Fetches the hourly alerts data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the hourly alerts data.
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        hourly_alerts_query = lpg_plant_queries.lpg_plant_query.get("hourly_alerts")
        hourly_alerts_query_ = hourly_alerts_query
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            hourly_alerts_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(hourly_alerts_query, filters, drill_state)
        try:
            resp = await function(query=hourly_alerts_query_)
            # keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(hourly_alerts_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            # keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(hourly_alerts_query)
        # hourly_alerts_data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": resp}


    @staticmethod
    async def sales_performance(filters, cross_filters, drill_state):
        """
        Fetches the sales performance data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the sales performance data.
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
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

        # Reverse mapping (for returning the short form)
        reverse_month_mapping = {v: k for k, v in month_mapping.items()}

        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.M60LevelMetaData.get_clause_conditions(formated=True)]
            sales_performance_query = lpg_plant_queries.lpg_plant_query.get("sales_performance")
            sales_performance_query_ = sales_performance_query
            conditions = []

            for rec in filters:
                rec.value = rec.value.split(",")
                if rec.key == '"month_name"':  # Only handle the month_name case separately
                    # Check if any value in rec.value is in month_mapping
                    rec.value = [month_mapping.get(val.strip(), val.strip()) for val in rec.value]
                
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
                sales_performance_query_ += ' WHERE '
                sales_performance_query_ += ' AND '.join(conditions)
        else:
            current_date = datetime.now()
            current_year = current_date.year
            next_year = current_year + 1
            current_month = current_date.month
            # Determine the current financial year
            if current_month >= 4:  # April or later
                fiscal_year_start = f"'FY {current_year}-{next_year}'"
            else:  # January to March
                previous_year = current_year - 1
                fiscal_year_start = f"'FY {previous_year}-{current_year}'"
            # Fallback query if no filters are provided
            sales_performance_query_ = f'''
                SELECT
                    ROUND(SUM("M60_LEVEL_METADATA"."NETWEIGHT_TMT")::numeric,0) AS "ACTUAL_TMT_SALES",
                    ROUND(SUM("M60_LEVEL_METADATA"."TARGET_QTY_TMT")::numeric,0) AS "TARGET_TMT_SALES",
                    "M60_LEVEL_METADATA"."fy_month" AS "fy_month",
                    "M60_LEVEL_METADATA"."fiscal_year" AS "fiscal_year"
                FROM
                    "M60_LEVEL_METADATA"
                WHERE
                    "M60_LEVEL_METADATA"."NETWEIGHT_TMT" != 0 and "M60_LEVEL_METADATA"."fiscal_year" = {fiscal_year_start}
                GROUP BY
                    "M60_LEVEL_METADATA"."fy_month",
                    "M60_LEVEL_METADATA"."fiscal_year"
                ORDER BY
                    "M60_LEVEL_METADATA"."fy_month" ASC;
            '''
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.M60LevelMetaData.get_clause_conditions(formated=True)]
            sales_performance_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(sales_performance_query_, access_filters, drill_state)
            print("sales_performance_query_: ",sales_performance_query_)
            resp = await function(query=sales_performance_query_)

            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)

            # Fill missing values for numerical columns
            for each_float_col in [
                "ACTUAL_TMT_SALES", "TARGET_TMT_SALES"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "fy_month", "month_name"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": resp}

        # Execute the query
        resp = await function(query=sales_performance_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)

        # Fill missing values for numerical columns
        for each_float_col in [
            "TARGET_QTY_TMT", "Prediction_Value", "Product_Achievement", 
            "Zone_Region_Achievement", "Rate_Per_Day_Required_MMT", 
            "Rate_per_day_current_MMT", "FinalSum", "FinalActualSum", "NETWEIGHT_TMT"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "SBU", "SBU_Name", "ZONE", "Zone_Name", "REGION", "Region_Name", "SA", 
            "SalesArea_Name", "PRODUCT", "ProductName", "UOM", "fiscal_year", 
            "month_year", "month_name"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

        # Apply grouping logic based on filters
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            filter_values = [rec.value[0].strip('"') for rec in filters]
            if "month_name" in filter_keys:
            # Convert full month names to short form (e.g., "January" -> "Jan")
                resp["month_name"] = resp["month_name"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )
            sbu_order = ['Retail', 'LPG', 'I&C', 'Lubes', 'Aviation', 'PETCHEM', 'NG']

            # Create a mapping dictionary for SBU_Name replacements
            sbu_mapping = {
                "PETROCHEMICALS SBU": "PETCHEM",  # Map PETROCHEMICALS SBU to PETCHEM
                "GAS HQO": "NG",  # Map GAS HQO to NG
            }
            resp = resp[resp["SBU_Name"] != "0"]
            resp = resp[resp["Zone_Name"] != "-"]
            

            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'SBU_Name' in filter_keys:
                resp['SBU_Name'] = resp['SBU_Name'].map(sbu_mapping).fillna(resp['SBU_Name'])
                resp['SBU_Name'] = pd.Categorical(resp['SBU_Name'], categories=sbu_order, ordered=True)
                resp = resp.sort_values('SBU_Name')
                grouped_resp = resp.groupby(["SBU_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'Zone_Name' in filter_keys:
                grouped_resp = resp.groupby(["Zone_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'Region_Name' in filter_keys:
                grouped_resp = resp.groupby(["Region_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'SalesArea_Name' in filter_keys:
                grouped_resp = resp.groupby(["SalesArea_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })

            if len(filters) == 2 and "month_name" in filter_keys and "SBU_Name" in filter_keys:
                grouped_resp = resp.groupby(["month_name", "SBU_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })
            
            elif len(filters) == 2 and "month_name" in filter_keys and "Zone_Name" in filter_keys:
                grouped_resp = resp.groupby(["month_name", "Zone_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })
            
            elif len(filters) == 2 and "month_name" in filter_keys and "Region_Name" in filter_keys:
                grouped_resp = resp.groupby(["month_name", "Region_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })
            
            elif len(filters) == 2 and "month_name" in filter_keys and "SalesArea_Name" in filter_keys:
                grouped_resp = resp.groupby(["month_name", "SalesArea_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })
            
            elif len(filters) == 2 and "month_name" in filter_keys and "ProductName" in filter_keys:
                grouped_resp = resp.groupby(["month_name", "ProductName"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })

            elif "fiscal_year" in filter_keys and "month_name" not in filter_keys:
                grouped_resp = resp.groupby(["fiscal_year"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "fiscal_year" in filter_keys and "month_name" in filter_keys and "SBU_Name" not in filter_keys:
                resp['SBU_Name'] = resp['SBU_Name'].map(sbu_mapping).fillna(resp['SBU_Name'])
                resp['SBU_Name'] = pd.Categorical(resp['SBU_Name'], categories=sbu_order, ordered=True)
                resp = resp.sort_values('SBU_Name')
                grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "fiscal_year" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
                if "DS" in filter_values or 'Lubes' in filter_values or 'DS Lubes' in filter_values:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name","Region_Name"], as_index=False).agg({
                        "TARGET_QTY_TMT": "sum",
                        "NETWEIGHT_TMT": "sum"
                    })
                else:    
                    grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name", "Zone_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "fiscal_year" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and "Region_Name" not in filter_keys:
                grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "fiscal_year" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys \
                                    and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys:
                grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })

            elif "fiscal_year" in filter_keys and \
            "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and \
                                    "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys and "ProductName" not in filter_keys:
                grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })
            grouped_resp["NETWEIGHT_TMT"] = grouped_resp["NETWEIGHT_TMT"].round(0)
            grouped_resp["TARGET_QTY_TMT"] = grouped_resp["TARGET_QTY_TMT"].round(0)
            # Return grouped response
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    # @staticmethod
    # async def sales_performance(filters, drill_state):
    #     """
    #     Fetches the sales performance data for the given filters and drill state.

    #     Parameters:
    #         filters (list): List of filter objects to apply to the query.
    #         drill_state (dict): Current drill state for processing the query.

    #     Returns:
    #         dict: Contains the status, a success message, and the sales performance data.
    #     """
    #     Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    #     Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    #     function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    #     month_mapping = {
    #                         "Jan": "January",
    #                         "Feb": "February",
    #                         "Mar": "March",
    #                         "Apr": "April",
    #                         "May": "May",
    #                         "Jun": "June",
    #                         "Jul": "July",
    #                         "Aug": "August",
    #                         "Sep": "September",
    #                         "Oct": "October",
    #                         "Nov": "November",
    #                         "Dec": "December"
    #                 }

    #     # Reverse mapping (for returning the short form)
    #     reverse_month_mapping = {v: k for k, v in month_mapping.items()}
    #     sales_performance_query_ = lpg_plant_queries.lpg_plant_query.get("sales_performance")
    #     if filters:
    #         conditions = []
    #         for rec in filters:
    #             rec.value = rec.value.split(",")
    #             if rec.key == '"month_name"':  # Only handle the month_name case separately
    #                 # Check if any value in rec.value is in month_mapping
    #                 rec.value = [month_mapping.get(val.strip(), val.strip()) for val in rec.value]
    #             # Now handle other cases
    #             if isinstance(rec.value, str):
    #                 condition = f"{rec.key} = '{rec.value}'"
    #             else:
    #                 if len(rec.value) == 1:
    #                     condition = f"{rec.key} = '{rec.value[0]}'"
    #                 else:
    #                     condition = f"{rec.key} in {tuple(rec.value)}"
    #             conditions.append(condition)

    #         if conditions:
    #             sales_performance_query_ += ' WHERE '
    #             sales_performance_query_ += ' AND '.join(conditions)
    #         # sales_performance_query_ += ' GROUP BY "SBU", "SBU_Name", "ZONE", "Zone_Name", "REGION", "Region_Name", "SA", ' \
    #         #                         '"SalesArea_Name", "PRODUCT", "ProductName", "UOM", "INVOICE_DT", ' \
    #         #                         '"TARGET_QTY_TMT", "FISCAL_YEAR", "NETWEIGHT_TMT", "FinalSum", ' \
    #         #                         '"FinalActualSum", "Rate_Per_Day_Required_MMT", "Rate_per_day_current_MMT", ' \
    #         #                         '"month_year", "month_name", "Prediction_Value", "Zone_Region_Achievement", ' \
    #         #                         '"Product_Achievement","fy_month"'
    #     else:
    #         current_date = datetime.now()
    #         current_year = current_date.year
    #         next_year = current_year + 1
    #         current_month = current_date.month
    #         # Determine the current financial year
    #         if current_month >= 4:  # April or later
    #             fiscal_year_start = f"'FY {current_year}-{next_year}'"
    #         else:  # January to March
    #             previous_year = current_year - 1
    #             fiscal_year_start = f"'FY {previous_year}-{current_year}'"

    #         if "WHERE" not in sales_performance_query_.lower():
    #             sales_performance_query_ += f' WHERE "M60_LEVEL_METADATA"."NETWEIGHT_TMT" != 0 AND "M60_LEVEL_METADATA"."FISCAL_YEAR" = {fiscal_year_start}'
    #         else:
    #             sales_performance_query_ += f' AND "M60_LEVEL_METADATA"."NETWEIGHT_TMT" != 0'
    #         if "GROUP BY" not in sales_performance_query_:
    #             print("into grp if")
    #             sales_performance_query_ += ' GROUP BY "M60_LEVEL_METADATA"."SBU", "M60_LEVEL_METADATA"."SBU_Name", "M60_LEVEL_METADATA"."ZONE", "M60_LEVEL_METADATA"."Zone_Name", "M60_LEVEL_METADATA"."REGION", "M60_LEVEL_METADATA"."Region_Name", "M60_LEVEL_METADATA"."SA", \
    #                                 "M60_LEVEL_METADATA"."SalesArea_Name", "M60_LEVEL_METADATA"."PRODUCT", "M60_LEVEL_METADATA"."ProductName", "M60_LEVEL_METADATA"."UOM", "M60_LEVEL_METADATA"."INVOICE_DT", \
    #                                 "M60_LEVEL_METADATA"."TARGET_QTY_TMT", "M60_LEVEL_METADATA"."FISCAL_YEAR", "M60_LEVEL_METADATA"."NETWEIGHT_TMT", "M60_LEVEL_METADATA"."FinalSum", \
    #                                 "M60_LEVEL_METADATA"."FinalActualSum", "M60_LEVEL_METADATA"."Rate_Per_Day_Required_MMT", "M60_LEVEL_METADATA"."Rate_per_day_current_MMT", \
    #                                 "M60_LEVEL_METADATA"."month_year", "M60_LEVEL_METADATA"."month_name", "M60_LEVEL_METADATA"."Prediction_Value", "M60_LEVEL_METADATA"."Zone_Region_Achievement", \
    #                                 "M60_LEVEL_METADATA"."Product_Achievement", "M60_LEVEL_METADATA"."fy_month", \
    #                                 TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", \'Month\'), \'Mon\'), \
    #                                 "M60_LEVEL_METADATA"."FISCAL_YEAR"'

    #         sales_performance_query_ += ' ORDER BY "M60_LEVEL_METADATA"."fy_month" ASC;'

    #         resp = await function(query=sales_performance_query_)
    #         # Convert the response to a DataFrame for further processing
    #         resp = pd.DataFrame(resp)
    #         if resp.empty:
    #             return {"status": True, "message": "success", "data": []}

    #         # Fill missing values for numerical columns
    #         for each_float_col in [
    #             "ACTUAL_TMT_SALES", "TARGET_TMT_SALES"
    #         ]:
    #             if each_float_col in resp.columns:
    #                 resp[each_float_col] = resp[each_float_col].fillna(0.0)

    #         # Fill missing values for string columns
    #         for each_str_col in [
    #             "fy_month", "month_name"
    #         ]:
    #             if each_str_col in resp.columns:
    #                 resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
    #         resp = resp.groupby(["fy_month", "month_name", "FISCAL_YEAR"], as_index=False).agg({
    #             "NETWEIGHT_TMT": "sum",
    #             "TARGET_QTY_TMT": "sum"
    #         })
    #         resp["NETWEIGHT_TMT"] = resp["NETWEIGHT_TMT"].round(2)
    #         resp["TARGET_QTY_TMT"] = resp["TARGET_QTY_TMT"].round(2)

    #         return {"status": True, "message": "success", "data": resp}

    #     # Execute the query
    #     resp = await function(query=sales_performance_query_)
    #     # Convert the response to a DataFrame for further processing
    #     resp = pd.DataFrame(resp)
    #     if resp.empty:
    #         return {"status": True, "message": "success", "data": []}

    #     # Fill missing values for numerical columns
    #     for each_float_col in [
    #         "TARGET_QTY_TMT", "Prediction_Value", "Product_Achievement", 
    #         "Zone_Region_Achievement", "Rate_Per_Day_Required_MMT", 
    #         "Rate_per_day_current_MMT", "FinalSum", "FinalActualSum", "NETWEIGHT_TMT"
    #     ]:
    #         if each_float_col in resp.columns:
    #             resp[each_float_col] = resp[each_float_col].fillna(0.0)

    #     # Fill missing values for string columns
    #     for each_str_col in [
    #         "SBU", "SBU_Name", "ZONE", "Zone_Name", "REGION", "Region_Name", "SA", 
    #         "SalesArea_Name", "PRODUCT", "ProductName", "UOM", "FISCAL_YEAR", 
    #         "month_year", "month_name"
    #     ]:
    #         if each_str_col in resp.columns:
    #             resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

    #     # Apply grouping logic based on filters
    #     if filters:
    #         grouped_resp = None
    #         filter_keys = [rec.key.strip('"') for rec in filters]
    #         if "month_name" in filter_keys:
    #         # Convert full month names to short form (e.g., "January" -> "Jan")
    #             resp["month_name"] = resp["month_name"].apply(
    #             lambda x: reverse_month_mapping.get(x, x)
    #         )

    #         if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'SBU_Name' in filter_keys:
    #             grouped_resp = resp.groupby(["SBU_Name"], as_index=False).agg({
    #                 "TARGET_QTY_TMT": "sum",
    #                 "NETWEIGHT_TMT": "sum"
    #             })
    #         if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'Zone_Name' in filter_keys:
    #             grouped_resp = resp.groupby(["Zone_Name"], as_index=False).agg({
    #                 "TARGET_QTY_TMT": "sum",
    #                 "NETWEIGHT_TMT": "sum"
    #             })
    #         if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'Region_Name' in filter_keys:
    #             grouped_resp = resp.groupby(["Region_Name"], as_index=False).agg({
    #                 "TARGET_QTY_TMT": "sum",
    #                 "NETWEIGHT_TMT": "sum"
    #             })
    #         if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'SalesArea_Name' in filter_keys:
    #             grouped_resp = resp.groupby(["SalesArea_Name"], as_index=False).agg({
    #                 "TARGET_QTY_TMT": "sum",
    #                 "NETWEIGHT_TMT": "sum"
    #             })

    #         if len(filters) == 2 and "month_name" in filter_keys and "SBU_Name" in filter_keys:
    #             grouped_resp = resp.groupby(["month_name", "SBU_Name"], as_index=False).agg({
    #                 "TARGET_QTY_TMT": "sum",
    #                 "NETWEIGHT_TMT": "sum"
    #             })
            
    #         elif len(filters) == 2 and "month_name" in filter_keys and "Zone_Name" in filter_keys:
    #             grouped_resp = resp.groupby(["month_name", "Zone_Name"], as_index=False).agg({
    #                 "TARGET_QTY_TMT": "sum",
    #                 "NETWEIGHT_TMT": "sum"
    #             })
            
    #         elif len(filters) == 2 and "month_name" in filter_keys and "Region_Name" in filter_keys:
    #             grouped_resp = resp.groupby(["month_name", "Region_Name"], as_index=False).agg({
    #                 "TARGET_QTY_TMT": "sum",
    #                 "NETWEIGHT_TMT": "sum"
    #             })
            
    #         elif len(filters) == 2 and "month_name" in filter_keys and "SalesArea_Name" in filter_keys:
    #             grouped_resp = resp.groupby(["month_name", "SalesArea_Name"], as_index=False).agg({
    #                 "TARGET_QTY_TMT": "sum",
    #                 "NETWEIGHT_TMT": "sum"
    #             })
            
    #         elif len(filters) == 2 and "month_name" in filter_keys and "ProductName" in filter_keys:
    #             grouped_resp = resp.groupby(["month_name", "ProductName"], as_index=False).agg({
    #                 "TARGET_QTY_TMT": "sum",
    #                 "NETWEIGHT_TMT": "sum"
    #             })

    #         elif "FISCAL_YEAR" in filter_keys and "month_name" not in filter_keys:
    #             grouped_resp = resp.groupby(["FISCAL_YEAR"], as_index=False).agg({
    #                 "NETWEIGHT_TMT": "sum",
    #                 "TARGET_QTY_TMT": "sum"
    #             })

    #         elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" not in filter_keys:
    #             grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name"], as_index=False).agg({
    #                 "NETWEIGHT_TMT": "sum",
    #                 "TARGET_QTY_TMT": "sum"
    #             })

    #         elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
    #             if "DS" in filters[-1].value[0] or 'Lubes' in filters[-1].value[0] or 'DS Lubes' in filters[-1].value[0]:
    #                     grouped_resp = resp.groupby(["month_name", "SBU_Name","Region_Name"], as_index=False).agg({
    #                     "TARGET_QTY_TMT": "sum",
    #                     "NETWEIGHT_TMT": "sum"
    #                 })
    #             else:    
    #                 grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name"], as_index=False).agg({
    #                 "NETWEIGHT_TMT": "sum",
    #                 "TARGET_QTY_TMT": "sum"
    #             })

    #         elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and "Region_Name" not in filter_keys:
    #             grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg({
    #                 "NETWEIGHT_TMT": "sum",
    #                 "TARGET_QTY_TMT": "sum"
    #             })

    #         elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys \
    #                                 and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys:
    #             grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg({
    #                 "NETWEIGHT_TMT": "sum",
    #                 "TARGET_QTY_TMT": "sum",
    #             })

    #         elif "FISCAL_YEAR" in filter_keys and \
    #         "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and \
    #                                 "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys and "ProductName" not in filter_keys:
    #             grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg({
    #                 "NETWEIGHT_TMT": "sum",
    #                 "TARGET_QTY_TMT": "sum",
    #             })
    #         grouped_resp["NETWEIGHT_TMT"] = grouped_resp["NETWEIGHT_TMT"].round(2)
    #         grouped_resp["TARGET_QTY_TMT"] = grouped_resp["TARGET_QTY_TMT"].round(2)
    #         # Return grouped response
    #         if grouped_resp is not None:
    #             return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

    #     # If no filters are applied, return the default response
    #     return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    @staticmethod
    async def calculate_ytd(current_date,df,cols,current_month=False):
        current_month_name = current_date.strftime('%B')[:3]
        today = current_date.today()
        #total_days_in_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        total_days_in_month = (current_date.today().replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        total_days_in_month = total_days_in_month.day
        days_left_in_month = total_days_in_month - today.day
        if current_month == False:
            current_month_name = df['month_name'].unique().tolist()[0]
        for col in cols:
            df[col] = df[col].fillna(0).astype(np.float64).round(0)
            df[col] = df.apply(
                            lambda row: round(row[col] / (total_days_in_month - days_left_in_month))
                            if row["month_name"] == current_month_name
                            else row[col],  # Leave other rows unchanged
                            axis=1
                    )
        return df
    
    @staticmethod
    async def calculate_date(from_date, to_date, df, col):
        # Convert from_date and to_date to datetime objects
        # Extract abbreviated month names for comparison
        from_month_name = from_date.strftime('%b')  # 'Jan'
        to_month_name = to_date.strftime('%b')      # 'Jan'

        # Define an ordered list of abbreviated month names for proper comparison
        month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        # Filter rows within the date range based on month_name
        df[col] = df.apply(
            lambda row: round(row[col])
            if month_order.index(from_month_name) <= month_order.index(row["month_name"]) <= month_order.index(to_month_name)
            else row[col],  # Leave other rows unchanged
            axis=1,
        )
        return df
    
    @staticmethod
    async def calculate_actual_history_tmt(from_date_obj, to_date_obj, resp, column_name):
        """
        Calculate the adjusted ACTUAL_HISTORY_TMT for the specified date range based on 
        the number of days in each month within the range.

        Args:
            from_date_obj (datetime): The start date of the range.
            to_date_obj (datetime): The end date of the range.
            resp (pd.DataFrame): The response DataFrame containing the ACTUAL_HISTORY_TMT column.
            column_name (str): The column name to be adjusted.

        Returns:
            pd.DataFrame: The adjusted DataFrame with a new column.
        """
        # Calculate total days in the range
        total_days = (to_date_obj - from_date_obj).days + 1
        
        # Initialize a dictionary to store days for each month
        days_per_month = {}

        # Iterate through all months in the range
        current_date = from_date_obj
        while current_date <= to_date_obj:
            year = current_date.year
            month = current_date.month
            _, days_in_month = calendar.monthrange(year, month)
            
            # Determine the actual start and end days for the current month
            if current_date.month == from_date_obj.month and current_date.year == from_date_obj.year:
                # Start from the given day in the first month
                start_day = from_date_obj.day
            else:
                start_day = 1
            
            if current_date.month == to_date_obj.month and current_date.year == to_date_obj.year:
                # End at the given day in the last month
                end_day = to_date_obj.day
            else:
                end_day = days_in_month
            
            # Calculate days in the current month within the range
            days_in_range = end_day - start_day + 1
            days_per_month[(year, month)] = days_in_range

            # Move to the next month
            next_month = month % 12 + 1
            next_year = year + (month // 12)
            current_date = datetime(next_year, next_month, 1)
        
        # Calculate the fraction of days for each month
        days_per_month_fraction = {key: days / total_days for key, days in days_per_month.items()}

        # Adjust the ACTUAL_HISTORY_TMT values in resp
        resp[column_name] = resp[column_name].fillna(0).astype(int)
        resp[f"{column_name}_adjusted"] = resp[column_name].apply(
            lambda value: sum(value * days_per_month_fraction.get((year, month), 0) 
                            for (year, month) in days_per_month_fraction.keys())
        )

        return resp

    @staticmethod
    async def retail_tar(filters, cross_filters, drill_state, time_grain='', resp_format='',resp_level = ''):
        """
        Fetches the retail tar data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the sales performance data.
            :param resp_format:
            :param filters:
            :param drill_state:
            :param cross_filters:
            :param time_grain:
        """
        return await dry_out_analysis.retail_tar([rec.dict() for rec in filters],
                                                     [rec.dict() for rec in cross_filters], drill_state, time_grain,
                                                     resp_format)

    @staticmethod
    async def m60_performance(filters, cross_filters, drill_state, time_grain='', resp_format='',resp_level = ''):
        """
        Fetches the sales performance data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the sales performance data.
            :param resp_format:
            :param filters:
            :param drill_state:
            :param cross_filters:
            :param time_grain:
        """
        return await m60_performance.m60_performance([rec.dict() for rec in filters],
                                                     [rec.dict() for rec in cross_filters], drill_state, time_grain,
                                                     resp_format)
    @staticmethod
    async def industry_performance(filters, cross_filters, drill_state, time_grain='', resp_format='',resp_level=''):
        """
        Fetches the sales performance data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the sales performance data.
            :param filters:
            :param cross_filters:
            :param drill_state:
            :param resp_format:
            :param time_grain:
        """
        return await industry_performance.industry_performance([rec.dict() for rec in filters],
                                                               [rec.dict() for rec in cross_filters], drill_state,
                                                               time_grain, resp_format,resp_level)

    @staticmethod
    async def m60_performance_old(filters, cross_filters, drill_state):
        """
        Fetches the sales performance data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the sales performance data.
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        '''
        df_pl = pl.read_excel("/opt/ceg/algo/Y2NE_Dec 24 FY2024-25_06.01.25.xlsx", sheet_name="Results", engine='xlsx2csv', engine_options={"skip_rows": 2})
        df = df_pl.to_pandas()    
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

        # Reverse mapping (for returning the short form)
        reverse_month_mapping = {v: k for k, v in month_mapping.items()}
        '''
        month_to_num = {
                "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
                "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
                "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
            }
        if filters and any(rec.key not in ['"H"', '"T"', '"BE"', '"RI"', '"A"', '"I"', '"YTD"', '"DATE"'] for rec in filters):
            print("into only filters")
            sales_performance_query = lpg_plant_queries.lpg_plant_query.get("sales_performance")
            sales_performance_query_ = sales_performance_query
            conditions = []

            # Define keys to exclude from the WHERE clause
            excluded_keys = {'"A"', '"H"', '"T"', '"BE"', '"RI"', '"I"', '"YTD"', '"DATE"'}

            for rec in filters:
                rec.value = rec.value.split(",")
                #if rec.key == '"month_name"':  # Only handle the month_name case separately
                # Check if any value in rec.value is in month_mapping
                #    rec.value = [month_mapping.get(val.strip(), val.strip()) for val in rec.value]

                # Skip keys that should not be added to the WHERE clause
                if rec.key in excluded_keys:
                    continue
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
                sales_performance_query_ += ' WHERE '
                sales_performance_query_ += ' AND '.join(conditions)

        elif len(filters) >= 1 and any(rec.key in ['"H"', '"T"', '"BE"', '"RI"', '"A"', '"I"', '"YTD"', '"DATE'] for rec in filters):
            print("into elif")
            selected_keys = [rec.key.strip('"') for rec in filters]
            #current_date = datetime.now()
            current_date = helpers.get_time_stamp_by_delta(days=0,with_month_start_day=False,date_time_format=None)
            print("current_date",)
            current_year = current_date.year
            next_year = current_year + 1
            current_month = current_date.month
            # Determine the current financial year
            if current_month >= 4:  # April or later
                fiscal_year_start = f"'FY {current_year}-{next_year}'"
            else:  # January to March
                previous_year = current_year - 1
                fiscal_year_start = f"'FY {previous_year}-{current_year}'"
            pres_year_date_filters = ""
            hist_year_date_filters = ""
            
            '''
            removed the below line from the query because we having data directly in DB as  January
            'TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", \'Month\'), \'Mon\') AS "month_name"'
            
            'TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", \'Month\'), \'Mon\')',
            '''
            # Initialize the dynamic parts of the query
            #where_conditions = [f'"M60_LEVEL_METADATA"."fiscal_year" = {fiscal_year_start} and "M60_LEVEL_METADATA"."NETWEIGHT_TMT" != 0']
            where_conditions = [f'"M60_LEVEL_METADATA"."fiscal_year" = {fiscal_year_start}']
            select_columns = [
                'ROUND(SUM("M60_LEVEL_METADATA"."NETWEIGHT_TMT")::numeric, 0) AS "ACTUAL_TMT_SALES"',
                '"M60_LEVEL_METADATA"."fy_month" AS "fy_month"',
                '"month_name"',
                '"M60_LEVEL_METADATA"."fiscal_year" AS "fiscal_year"',
            ]
            group_by_columns = [
                '"M60_LEVEL_METADATA"."fy_month"',
                '"month_name"',
                '"M60_LEVEL_METADATA"."fiscal_year"',
            ]

            #Build conditions based on selected keys
            if "H" in selected_keys:
                previous_year = current_year - 1
                where_conditions.append(f'"M60_LEVEL_METADATA"."fiscal_year" IN (\'FY {previous_year}-{current_year}\', \'FY {current_year-2}-{previous_year}\')')

            if "T" in selected_keys:
                select_columns.append('ROUND(SUM("M60_LEVEL_METADATA"."TARGET_QTY_TMT")::numeric,0) AS "TARGET_QTY_TMT"')
            
            # Construct the query dynamically
            sales_performance_query_ = f'''
                SELECT
                    {', '.join(select_columns)}
                FROM
                    "M60_LEVEL_METADATA"
                WHERE
                    {" AND ".join(where_conditions)}
                GROUP BY
                    {', '.join(group_by_columns)}
                ORDER BY
                    "M60_LEVEL_METADATA"."fy_month" ASC;
            '''

            print("Generated Query:", sales_performance_query_)  # Debugging: Print the generated query

            resp = await function(query=sales_performance_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if 'H' in selected_keys:
                year_required = str(current_year-2)+'-'+str(previous_year)
                sales_his_query = f"""
                select "fiscal_year","month_name","NETWEIGHT_TMT" FROM "MOM_LEVEL_FINAL_DATA" where "FISCALYEAR" = 'FY {year_required}'

                """
                his_data = await function(query=sales_his_query)
                his_data = pd.DataFrame(his_data)
                his_data = his_data.groupby(['fiscal_year','month_name'],as_index = False)['NETWEIGHT_TMT'].sum().round(0)
                his_data.to_csv('/tmp/datahis.csv',index = False)
                resp = resp.merge(his_data[['month_name','NETWEIGHT_TMT','fiscal_year']],how='left',on='month_name')
                resp['fiscal_year'] = resp['fiscal_year'].bfill()
            
            # Fill missing values for numerical columns
            for each_float_col in ["NETWEIGHT_TMT","ACTUAL_TMT_SALES", "TARGET_QTY_TMT", 'BPCL', 'CPCL', 'GAIL',
                                    'HMEL', 'HPCL', 'IOCL', 'MRPL', 'NEL', 'NRL','OIL INDIA LIMITED', 'ONGC',
                                    'RBML', 'RIL', 'RSIL', 'SEIPL', 'SIMPL','SMAFSL']:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0).astype(np.float64)
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            if "NETWEIGHT_TMT" in resp.columns.tolist():
                resp = resp.rename(columns={'NETWEIGHT_TMT':'ACTUAL_HISTORY_TMT'})
            # Fill missing values for string columns
            for each_str_col in ["fy_month", "month_name"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            
            if 'DATE' in selected_keys:
                print("into date")
                year_required = str(current_year-1)+'-'+str(current_year)
                from_date, to_date = [
                        rec.value for rec in filters if rec.key == '"DATE"'
                    ][0].split(",")
                # Convert strings to datetime objects
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
                to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')

                # Get abbreviated month names
                from_date_month = from_date_obj.strftime('%b')  # 'Jan'
                to_date_month = to_date_obj.strftime('%b')      # 'Jan'

                print(f"From Date Month: {from_date_month}, To Date Month: {to_date_month}")
                from_date = from_date.replace("-", "")  # Strip hyphens
                to_date = to_date.replace("-", "")  # Strip hyphens
                date_day_query = f"""
                select "fiscal_year","month_name","NETWEIGHT_TMT" FROM "MOM_DAY_LEVEL_DATA" where "FISCALYEAR" = 'FY {year_required}' and "DAY_ID" between '{from_date}' and '{to_date}'
                """
                print("date_day_query --> ", date_day_query)
                day_data = await function(query=date_day_query)
                day_data = pd.DataFrame(day_data)
                day_data = day_data.groupby(['fiscal_year','month_name'],as_index = False)['NETWEIGHT_TMT'].sum().round(0)
                day_data.to_csv('/tmp/dataday.csv',index = False)
                day_data['NETWEIGHT_TMT'] = day_data['NETWEIGHT_TMT'].fillna(0).astype(int)
                resp["month_num"] = resp["month_name"].map(month_to_num)
                # Filter based on the fiscal year boundary
                from_month_num = month_to_num[from_date_month]  # e.g., Apr -> 4
                to_month_num = month_to_num[to_date_month]      # e.g., Jan -> 1
                
                if from_month_num <= to_month_num:
                    # No year boundary (e.g., Apr to Aug)
                    resp = resp[(resp["month_num"] >= from_month_num) & (resp["month_num"] <= to_month_num)]
                else:
                    # Year boundary (e.g., Apr to Jan)
                    resp = resp[(resp["month_num"] >= from_month_num) | (resp["month_num"] <= to_month_num)]

                # Drop the temporary column after filtering
                resp = resp.drop(columns=["month_num"])

                # Merge day_data with resp
                resp = resp.merge(day_data[['month_name', 'NETWEIGHT_TMT', 'fiscal_year']], how='left', on='month_name')
                
                # Rename column and fill NaN values
                resp = resp.rename(columns={"NETWEIGHT_TMT": "ACTUAL_TMT_SALES"})
                resp["ACTUAL_TMT_SALES"] = resp["ACTUAL_TMT_SALES"].fillna(0).astype(int)
                
                # Convert result to dictionary format
                resp = resp.to_dict("records")
            
            if 'T' in selected_keys  and "DATE" in selected_keys:
                print("into date")
                year_required = str(current_year)+'-'+str(current_year+1)
                from_date, to_date = [
                        rec.value for rec in filters if rec.key == '"DATE"'
                    ][0].split(",")
                # Convert strings to datetime objects
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
                to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')

                # Get abbreviated month names
                from_date_month = from_date_obj.strftime('%b')  # 'Jan'
                to_date_month = to_date_obj.strftime('%b')      # 'Jan'

                print(f"From Date Month: {from_date_month}, To Date Month: {to_date_month}")
                from_date = from_date.replace("-", "")  # Strip hyphens
                to_date = to_date.replace("-", "")  # Strip hyphens
                print("resp", resp)
                resp = pd.DataFrame(resp)
                resp = await GlobalAnalytics.calculate_date(from_date_obj, to_date_obj, resp, 'TARGET_QTY_TMT')
                resp["TARGET_QTY_TMT"] = resp["TARGET_QTY_TMT"].fillna(0).astype(int)
                resp = resp.to_dict("records")
               
            if 'H' in selected_keys and "DATE" in selected_keys:
                print("into date")
                year_required = str(current_year)+'-'+str(current_year+1)
                from_date, to_date = [
                        rec.value for rec in filters if rec.key == '"DATE"'
                    ][0].split(",")
                # Convert strings to datetime objects
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
                to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')

                # Get abbreviated month names
                from_date_month = from_date_obj.strftime('%b')  # 'Jan'
                to_date_month = to_date_obj.strftime('%b')      # 'Jan'

                print(f"From Date Month: {from_date_month}, To Date Month: {to_date_month}")
                from_date = from_date.replace("-", "")  # Strip hyphens
                to_date = to_date.replace("-", "")  # Strip hyphens
                print("resp", resp)
                resp = pd.DataFrame(resp)
                resp = await GlobalAnalytics.calculate_actual_history_tmt(from_date_obj, to_date_obj, resp, 'ACTUAL_HISTORY_TMT')
                resp["ACTUAL_HISTORY_TMT"] = resp["ACTUAL_HISTORY_TMT"].fillna(0).astype(int)
                resp = resp.to_dict("records")
            # added for ytd
            resultCols = []
            if 'YTD' in selected_keys:
                # resp = await GlobalAnalytics.calculate_ytd(current_date,resp,['ACTUAL_TMT_SALES'])
                resp = resp
            
            if 'T' in selected_keys  and "YTD" in selected_keys:
                resultCols.append('TARGET_QTY_TMT')
                
               
            if 'H' in selected_keys and "YTD" in selected_keys:
                resultCols.append('ACTUAL_HISTORY_TMT')
            
            if len(resultCols) >0:
                resp = await GlobalAnalytics.calculate_ytd(current_date,resp,resultCols,current_month=True)
            resp = resp.to_dict(orient = 'series')
            for each_key in resp:
                print(each_key)
                if each_key in ['ACTUAL_TMT_SALES']:
                    zero_value_keys = [k for k, v in resp[each_key].items() if v == 0.0]
                    resp[each_key] = {k: v for k, v in resp[each_key].items() if v != 0.0}

                if len(selected_keys) == 1 and 'A' in selected_keys:
                    resp['month_name'] = {k: v for k, v in resp['month_name'].items() if k not in zero_value_keys}

            return {"status": True, "message": "success", "data": resp}

        else:
            current_date = datetime.now()
            current_year = current_date.year
            next_year = current_year + 1
            current_month = current_date.month
            # Determine the current financial year
            if current_month >= 4:  # April or later
                fiscal_year_start = f"'FY {current_year}-{next_year}'"
            else:  # January to March
                previous_year = current_year - 1
                fiscal_year_start = f"'FY {previous_year}-{current_year}'"
                
            '''
            TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", 'Month'), 'Mon') AS "month_name",
            removed the above line from the below query as the data is directly available as January etc
            TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", 'Month'), 'Mon'),
            '''
            # Fallback query if no filters are provided
            sales_performance_query_ = f'''
                SELECT
                    ROUND(SUM("M60_LEVEL_METADATA"."NETWEIGHT_TMT")::numeric,0) AS "ACTUAL_TMT_SALES",
                    ROUND(SUM("M60_LEVEL_METADATA"."TARGET_QTY_TMT")::numeric,0) AS "TARGET_TMT_SALES",
                    "M60_LEVEL_METADATA"."fy_month" AS "fy_month",
                    "month_name",
                    "M60_LEVEL_METADATA"."fiscal_year" AS "fiscal_year"
                FROM
                    "M60_LEVEL_METADATA"
                WHERE
                    "M60_LEVEL_METADATA"."NETWEIGHT_TMT" != 0 and   "M60_LEVEL_METADATA"."fiscal_year" = {fiscal_year_start}
                GROUP BY
                    "M60_LEVEL_METADATA"."fy_month",
                    "month_name",
                    "M60_LEVEL_METADATA"."fiscal_year"
                ORDER BY
                    "M60_LEVEL_METADATA"."fy_month" ASC;
            '''
            resp = await function(query=sales_performance_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)

            # Fill missing values for numerical columns
            for each_float_col in [
                "ACTUAL_TMT_SALES"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "fy_month", "month_name"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": resp}

        # Execute the query
        resp = await function(query=sales_performance_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)

        # Fill missing values for numerical columns
        for each_float_col in [
            "TARGET_QTY_TMT", "Prediction_Value", "Product_Achievement", 
            "Zone_Region_Achievement", "Rate_Per_Day_Required_MMT", 
            "Rate_per_day_current_MMT", "FinalSum", "FinalActualSum", "NETWEIGHT_TMT"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "SBU", "SBU_Name", "ZONE", "Zone_Name", "REGION", "Region_Name", "SA", 
            "SalesArea_Name", "PRODUCT", "ProductName", "UOM", "fiscal_year", 
            "month_year", "month_name"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        if not filters:
            filters = []

        filters = filters + cross_filters  
        # Apply grouping logic based on filters
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            filter_values = [rec.value[0].strip('') for rec in filters]
            '''
            if "month_name" in filter_keys:
            # Convert full month names to short form (e.g., "January" -> "Jan")
                resp["month_name"] = resp["month_name"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )
            '''
            if 'NG' in resp['SBU_Name'].unique().tolist():
                sbu_order = ['Retail', 'LPG', 'I&C', 'Lubes', 'Aviation', 'PETCHEM', 'NG']
                # Create a mapping dictionary for SBU_Name replacements
                sbu_mapping = {"Retail":"Retail", "LPG":"LPG","Lubes":"Lubes","I&C":"I&C", "Aviation":"Aviation", "PETROCHEMICALS SBU": "PETCHEM", "GAS HQO": "NG"}
            else:
                sbu_order = ['Retail', 'LPG', 'I&C', 'Lubes', 'Aviation', 'PETCHEM']
                # Create a mapping dictionary for SBU_Name replacements
                sbu_mapping = {"Retail":"Retail", "LPG":"LPG","Lubes":"Lubes","I&C":"I&C", "Aviation":"Aviation", "PETROCHEMICALS SBU": "PETCHEM"}
            
            resp = resp[resp["SBU_Name"] != "0"]
            resp = resp[resp["Zone_Name"] != "-"]

            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'SBU_Name' in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]

                # resp['SBU_Name'] = resp['SBU_Name'].map(sbu_mapping).fillna(resp['SBU_Name'])
                # resp['SBU_Name'] = pd.Categorical(resp['SBU_Name'], categories=sbu_order, ordered=True)
                # resp = resp.sort_values('SBU_Name')

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["SBU_Name", "Zone_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["SBU_Name", "Zone_Name"], as_index=False).agg(agg_dict)
 
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'Zone_Name' in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI' ,'YTD','DATE'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg(agg_dict)                    

            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'Region_Name' in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg(agg_dict)

            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'SalesArea_Name' in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg(agg_dict)
                
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'ProductName' in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg(agg_dict)

            if len(filters) == 2 and "month_name" in filter_keys and "SBU_Name" in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]

                resp['SBU_Name'] = resp['SBU_Name'].map(sbu_mapping).fillna(resp['SBU_Name'])
                resp['SBU_Name'] = pd.Categorical(resp['SBU_Name'], categories=sbu_order, ordered=True)
                resp = resp.sort_values('SBU_Name')

                if selected_keys:
                    grouped_resp = resp.groupby(["month_name", "SBU_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["month_name", "SBU_Name"], as_index=False).agg(agg_dict)
            
            elif len(filters) == 2 and "month_name" in filter_keys and "Zone_Name" in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]

                if selected_keys:
                    grouped_resp = resp.groupby(["month_name", "Zone_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["month_name", "Zone_Name"], as_index=False).agg(agg_dict)
            
            elif len(filters) == 2 and "month_name" in filter_keys and "Region_Name" in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["month_name", "Region_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["month_name", "Region_Name"], as_index=False).agg(agg_dict)
            
            elif len(filters) == 2 and "month_name" in filter_keys and "SalesArea_Name" in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["month_name", "SalesArea_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["month_name", "SalesArea_Name"], as_index=False).agg(agg_dict)
            
            elif len(filters) == 2 and "month_name" in filter_keys and "ProductName" in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["month_name", "ProductName"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["month_name", "ProductName"], as_index=False).agg(agg_dict)

            elif "fiscal_year" in filter_keys and "month_name" not in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI','YTD'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)
            
                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]
                    year_required = str(current_year-2)+'-'+str(current_year-1)
                    sales_his_query = f"""
                    select "fiscal_year","month_name","NETWEIGHT_TMT" FROM "MOM_LEVEL_FINAL_DATA" where "FISCALYEAR" = 'FY {year_required}'

                    """

                    his_data = await function(query=sales_his_query)
                    his_data = pd.DataFrame(his_data)
                    his_data = his_data.groupby(['fiscal_year','month_name'],as_index = False)['NETWEIGHT_TMT'].sum().round(0)
                    his_data = his_data.rename(columns = {'NETWEIGHT_TMT':'ACTUAL_HISTORY_TMT'})
                    resp['month_name'] = resp['month_name'].apply(lambda x:x[:3] if len(x)>=3 else x)
                    resp = resp.merge(his_data[['month_name','ACTUAL_HISTORY_TMT','fiscal_year']],how='left',on='month_name')
                    resp['fiscal_year'] = resp['fiscal_year'].bfill()
                    if "ACTUAL_HISTORY_TMT" in resp.columns.tolist():
                        resp['ACTUAL_HISTORY_TMT'] = resp['ACTUAL_HISTORY_TMT'].fillna(0).astype(int)
                    agg_dict["ACTUAL_HISTORY_TMT"] = "max"
                    
                    
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name"], as_index=False).agg(agg_dict)  
                resultCols = []
                
                if "H" in selected_keys and "YTD" in selected_keys:
                        resultCols.append("ACTUAL_HISTORY_TMT")
                        
                if "T" in selected_keys and "YTD" in selected_keys:
                    resultCols.append("TARGET_QTY_TMT")
                    
                if len(resultCols)>0:
                    current_date = helpers.get_time_stamp_by_delta(days=0,with_month_start_day=False,date_time_format=None)
                    grouped_resp = await GlobalAnalytics.calculate_ytd(current_date,grouped_resp,resultCols,current_month=False)

                    
            elif "fiscal_year" in filter_keys and "month_name" in filter_keys and "SBU_Name" not in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI','YTD','DATE'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)
                
                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]
                    year_required = str(current_year-2)+'-'+str(current_year-1)
                    sales_his_query = f"""
                                        SELECT "fiscal_year","month_name","ORGSBUNAME","NETWEIGHT_TMT" 
                                        FROM "MOM_LEVEL_FINAL_DATA" 
                                        WHERE "FISCALYEAR" = 'FY {year_required}'
                    """
                    if "month_name" in filter_keys:
                        ## Find the filter with key "month_name"
                        month_filter = next((rec for rec in filters if rec.key.strip('"') == "month_name"), None)
                        if month_filter:
                            # Extract the month name value (handle string or list values)
                            month_name = month_filter.value if isinstance(month_filter.value, str) else month_filter.value[0]
                            sales_his_query += f""" and "month_name" = '{month_name[:3]}'"""
                    print("sales_his_query",sales_his_query)
                    his_data = await function(query=sales_his_query)
                    his_data = pd.DataFrame(his_data)
                    his_data['ORGSBUNAME'] = his_data['ORGSBUNAME'].str.strip("DS").str.strip()
                    his_data = his_data.groupby(['fiscal_year','month_name','ORGSBUNAME'],as_index = False)['NETWEIGHT_TMT'].sum().round(0)
                    his_data['ORGSBUNAME'] = his_data['ORGSBUNAME'].fillna('').astype(str)
                    his_data = his_data.rename(columns = {'NETWEIGHT_TMT':'ACTUAL_HISTORY_TMT'})
                    resp['month_name'] = resp['month_name'].apply(lambda x:x[:3] if len(x)>=3 else x)
                    resp = resp.merge(his_data[['month_name','ACTUAL_HISTORY_TMT','fiscal_year','ORGSBUNAME']],how='left',left_on=['month_name','SBU_Name'],right_on = ['month_name','ORGSBUNAME'])
                    resp['fiscal_year'] = resp['fiscal_year'].bfill()
                    if "ACTUAL_HISTORY_TMT" in resp.columns.tolist():
                        resp['ACTUAL_HISTORY_TMT'] = resp['ACTUAL_HISTORY_TMT'].fillna(0).astype(int)
                    agg_dict["ACTUAL_HISTORY_TMT"] = lambda x: ', '.join(map(str, x.unique()))

                resp['SBU_Name'] = resp['SBU_Name'].map(sbu_mapping).fillna(resp['SBU_Name'])
                resp['SBU_Name'] = pd.Categorical(resp['SBU_Name'], categories=sbu_order, ordered=True)
                resp = resp.sort_values('SBU_Name')
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name"], as_index=False).agg(agg_dict)
                
                resultCols = []
                
                if "H" in selected_keys and "YTD" in selected_keys:
                        resultCols.append("ACTUAL_HISTORY_TMT")
                        
                if "T" in selected_keys and "YTD" in selected_keys:
                    resultCols.append("TARGET_QTY_TMT")
                        
                if len(resultCols)>0:
                    current_date = helpers.get_time_stamp_by_delta(days=0,with_month_start_day=False,date_time_format=None)
                    grouped_resp = await GlobalAnalytics.calculate_ytd(current_date,grouped_resp,resultCols,current_month=False)
            
            elif "fiscal_year" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI','YTD','DATE'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]
                    year_required = str(current_year-2)+'-'+str(current_year-1)
                    sales_his_query = f"""
                    select "fiscal_year","month_name","ORGSBUNAME","ORGZONENAME","NETWEIGHT_TMT" FROM "MOM_LEVEL_FINAL_DATA" where "FISCALYEAR" = 'FY {year_required}'
                    """
                    if "month_name" in filter_keys:
                        sales_his_query += f""" and "month_name" = '{filter_values[1][:3]}'"""
                    his_data = await function(query=sales_his_query)
                    his_data = pd.DataFrame(his_data)
                    his_data['ORGSBUNAME'] = his_data['ORGSBUNAME'].str.strip("DS").str.strip()
                    his_data = his_data.groupby(['fiscal_year','month_name','ORGSBUNAME','ORGZONENAME'],as_index = False)['NETWEIGHT_TMT'].sum().round(0)
                    his_data['ORGSBUNAME'] = his_data['ORGSBUNAME'].fillna('').astype(str)
                    his_data['ORGZONENAME'] = his_data['ORGZONENAME'].fillna('').astype(str)
                    his_data = his_data.rename(columns = {'NETWEIGHT_TMT':'ACTUAL_HISTORY_TMT'})
                    resp['month_name'] = resp['month_name'].apply(lambda x:x[:3] if len(x)>=3 else x)
                    resp = resp.merge(his_data[['month_name','ACTUAL_HISTORY_TMT','fiscal_year','ORGSBUNAME','ORGZONENAME']],
                                      how='left',left_on=['month_name','SBU_Name','Zone_Name'],
                                      right_on = ['month_name','ORGSBUNAME','ORGZONENAME'])
                    resp['fiscal_year'] = resp['fiscal_year'].bfill()
                    if "ACTUAL_HISTORY_TMT" in resp.columns.tolist():
                        resp['ACTUAL_HISTORY_TMT'] = resp['ACTUAL_HISTORY_TMT'].fillna(0).astype(int)
                    agg_dict["ACTUAL_HISTORY_TMT"] = lambda x: ', '.join(map(str, x.unique()))

                # resp['SBU_Name'] = resp['SBU_Name'].map(sbu_mapping).fillna(resp['SBU_Name'])
                # resp['SBU_Name'] = pd.Categorical(resp['SBU_Name'], categories=sbu_order, ordered=True)
                # resp = resp.sort_values('SBU_Name')

                # If any valid keys are selected, group the data
                grouped_keys = ["fiscal_year", "month_name", "SBU_Name"]

                # If valid keys are selected, apply conditional grouping
                if selected_keys:
                    # Check the last filter's value for specific keywords
                    if "DS Lubes" in filter_values or "DS" in filter_values or "Lubes" in filter_values:
                        print("DS Lubes selected")
                        grouped_keys.extend(["Region_Name"])
                    else:
                        print("No DS Lubes selected")
                        grouped_keys.extend(["Zone_Name"])
                else:
                    print("No keys selected")
                    if "DS Lubes" in filter_values or "DS" in filter_values or "Lubes" in filter_values:
                        print("DS Lubes selected")
                        grouped_keys.extend(["Region_Name"])
                    else:
                        # If no valid keys are selected, group by all keys
                        grouped_keys.extend(["Zone_Name"])

                # Add grouping logic based on the updated grouped_keys
                grouped_resp = resp.groupby(grouped_keys, as_index=False).agg(agg_dict)
                resultCols= []
                
                if "H" in selected_keys and "YTD" in selected_keys:
                        resultCols.append("ACTUAL_HISTORY_TMT")
                        
                if "T" in selected_keys and "YTD" in selected_keys:
                    resultCols.append("TARGET_QTY_TMT")
                        
                if len(resultCols)>0:
                    current_date = helpers.get_time_stamp_by_delta(days=0,with_month_start_day=False,date_time_format=None)
                    grouped_resp = await GlobalAnalytics.calculate_ytd(current_date,grouped_resp,resultCols,current_month=False)

            elif "fiscal_year" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and "Region_Name" not in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI','YTD','DATE'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)

                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]
                    year_required = str(current_year-2)+'-'+str(current_year-1)
                    sales_his_query = f"""
                    select "fiscal_year","month_name","ORGSBUNAME","ORGZONENAME","ORGRONAME","NETWEIGHT_TMT" FROM "MOM_LEVEL_FINAL_DATA" where "FISCALYEAR" = 'FY {year_required}'

                    """
                    if "month_name" in filter_keys:
                        sales_his_query += f""" and "month_name" = '{filter_values[1][:3]}'"""
                    his_data = await function(query=sales_his_query)
                    his_data = pd.DataFrame(his_data)
                    his_data['ORGSBUNAME'] = his_data['ORGSBUNAME'].str.strip("DS").str.strip()
                    his_data = his_data.groupby(['fiscal_year','month_name','ORGSBUNAME','ORGZONENAME','ORGRONAME'],as_index = False)['NETWEIGHT_TMT'].sum().round(0)
                    his_data['ORGSBUNAME'] = his_data['ORGSBUNAME'].fillna('').astype(str)
                    his_data['ORGZONENAME'] = his_data['ORGZONENAME'].fillna('').astype(str)
                    his_data['ORGRONAME'] = his_data['ORGRONAME'].fillna('').astype(str)
                    his_data = his_data.rename(columns = {'NETWEIGHT_TMT':'ACTUAL_HISTORY_TMT'})
                    resp['month_name'] = resp['month_name'].apply(lambda x:x[:3] if len(x)>=3 else x)
                    resp = resp.merge(his_data[['month_name','ACTUAL_HISTORY_TMT','fiscal_year','ORGSBUNAME','ORGZONENAME','ORGRONAME']],
                                      how='left',left_on=['month_name','SBU_Name','Zone_Name','Region_Name'],
                                      right_on = ['month_name','ORGSBUNAME','ORGZONENAME','ORGRONAME'])
                    resp['fiscal_year'] = resp['fiscal_year'].bfill()
                    if "ACTUAL_HISTORY_TMT" in resp.columns.tolist():
                        resp['ACTUAL_HISTORY_TMT'] = resp['ACTUAL_HISTORY_TMT'].fillna(0).astype(int)
                    agg_dict["ACTUAL_HISTORY_TMT"] = lambda x: ', '.join(map(str, x.unique()))
                
                # resp['SBU_Name'] = resp['SBU_Name'].map(sbu_mapping).fillna(resp['SBU_Name'])
                # resp['SBU_Name'] = pd.Categorical(resp['SBU_Name'], categories=sbu_order, ordered=True)
                # resp = resp.sort_values('SBU_Name')

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg(agg_dict)

                resultCols=[]
                if "H" in selected_keys and "YTD" in selected_keys:
                        resultCols.append("ACTUAL_HISTORY_TMT")
                        
                if "T" in selected_keys and "YTD" in selected_keys:
                    resultCols.append("TARGET_QTY_TMT")
                        
                if len(resultCols)>0:
                    current_date = helpers.get_time_stamp_by_delta(days=0,with_month_start_day=False,date_time_format=None)
                    grouped_resp = await GlobalAnalytics.calculate_ytd(current_date,grouped_resp,resultCols,current_month=False)
                    
            elif "fiscal_year" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys \
                                    and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI','YTD','DATE'}
                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()
                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)
                
                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]
                    year_required = str(current_year-2)+'-'+str(current_year-1)
                    sales_his_query = f"""
                                        SELECT "fiscal_year","month_name","ORGSBUNAME","ORGZONENAME","ORGRONAME","ORGSANAME","NETWEIGHT_TMT" 
                                        FROM "MOM_LEVEL_FINAL_DATA" 
                                        WHERE "FISCALYEAR" = 'FY {year_required}'
                    """
                    if "month_name" in filter_keys:
                        sales_his_query += f""" and "month_name" = '{filter_values[1][:3]}'"""
                    his_data = await function(query=sales_his_query)
                    his_data = pd.DataFrame(his_data)
                    his_data['ORGSBUNAME'] = his_data['ORGSBUNAME'].str.strip("DS").str.strip()
                    his_data = his_data.groupby(['fiscal_year','month_name','ORGSBUNAME','ORGZONENAME','ORGRONAME','ORGSANAME'],as_index = False)['NETWEIGHT_TMT'].sum().round(0)
                    his_data['ORGSBUNAME'] = his_data['ORGSBUNAME'].fillna('').astype(str)
                    his_data['ORGZONENAME'] = his_data['ORGZONENAME'].fillna('').astype(str)
                    his_data['ORGRONAME'] = his_data['ORGRONAME'].fillna('').astype(str)
                    his_data['ORGSANAME'] = his_data['ORGSANAME'].fillna('').astype(str)
                    his_data = his_data.rename(columns = {'NETWEIGHT_TMT':'ACTUAL_HISTORY_TMT'})
                    resp['month_name'] = resp['month_name'].apply(lambda x:x[:3] if len(x)>=3 else x)
                    resp = resp.merge(his_data[['month_name','ACTUAL_HISTORY_TMT','fiscal_year','ORGSBUNAME','ORGZONENAME','ORGRONAME','ORGSANAME']],
                                      how='left',left_on=['month_name','SBU_Name','Zone_Name','Region_Name','SalesArea_Name'],
                                      right_on = ['month_name','ORGSBUNAME','ORGZONENAME','ORGRONAME','ORGSANAME'])
                    resp['fiscal_year'] = resp['fiscal_year'].bfill()
                    if "ACTUAL_HISTORY_TMT" in resp.columns.tolist():
                        resp['ACTUAL_HISTORY_TMT'] = resp['ACTUAL_HISTORY_TMT'].fillna(0).astype(int)
                    agg_dict["ACTUAL_HISTORY_TMT"] = lambda x: ', '.join(map(str, x.unique()))
                
                # resp['SBU_Name'] = resp['SBU_Name'].map(sbu_mapping).fillna(resp['SBU_Name'])
                # resp['SBU_Name'] = pd.Categorical(resp['SBU_Name'], categories=sbu_order, ordered=True)
                # resp = resp.sort_values('SBU_Name')

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg(agg_dict)

                resultCols = []
                if "H" in selected_keys and "YTD" in selected_keys:
                        resultCols.append("ACTUAL_HISTORY_TMT")
                        
                if "T" in selected_keys and "YTD" in selected_keys:
                    resultCols.append("TARGET_QTY_TMT")
                        
                if len(resultCols)>0:
                    current_date = helpers.get_time_stamp_by_delta(days=0,with_month_start_day=False,date_time_format=None)
                    grouped_resp = await GlobalAnalytics.calculate_ytd(current_date,grouped_resp,resultCols,current_month=False)
                    
            elif "fiscal_year" in filter_keys and \
            "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and \
                                    "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys and "ProductName" not in filter_keys:
                # Define the set of valid keys without the quotes
                valid_keys = {'A', 'H', 'T', 'BE', 'RI','YTD'}

                # Extract user-selected keys with `value == 'true'`
                selected_keys = set()

                for rec in filters:
                    print(f"rec.key: {rec.key}, rec.value: {rec.value}")  # Debugging: Print key and value
                    if rec.key.strip('"') in valid_keys and 'true' in rec.value:
                        selected_keys.add(rec.key.strip('"'))  # Add the stripped key if valid and value is 'true'
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}

                # Group the response by the selected keys and apply the aggregation functions
                if 'T' in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                print("selected keys ", selected_keys)
                
                # Check if 'H' is in selected keys and update fiscal year values
                if 'H' in selected_keys:
                    current_date = datetime.now()
                    current_year = current_date.year
                    current_month = current_date.month
                    
                    if current_month >= 4:  # April or later
                        current_fiscal_year = f"FY {current_year}-{current_year + 1}"
                        previous_fiscal_year = f"FY {current_year - 1}-{current_year}"
                    else:  # January to March
                        current_fiscal_year = f"FY {current_year - 1}-{current_year}"
                        previous_fiscal_year = f"FY {current_year - 2}-{current_year - 1}"

                    for rec in filters:
                        if rec.key == "fiscal_year":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["fiscal_year"].isin([current_fiscal_year, previous_fiscal_year])]
                    year_required = str(current_year-2)+'-'+str(current_year-1)
                    sales_his_query = f"""
                                        SELECT "fiscal_year","month_name","ORGSBUNAME","ORGZONENAME","ORGRONAME","ORGSANAME","NETWEIGHT_TMT" 
                                        FROM "MOM_LEVEL_FINAL_DATA" 
                                        WHERE "FISCALYEAR" = 'FY {year_required}'
                    """
                    if "month_name" in filter_keys:
                        sales_his_query += f""" and "month_name" = '{filter_values[1][:3]}'"""
                    his_data = await function(query=sales_his_query)
                    his_data = pd.DataFrame(his_data)
                    his_data['ORGSBUNAME'] = his_data['ORGSBUNAME'].str.strip("DS").str.strip()
                    his_data = his_data.groupby(['fiscal_year','month_name','ORGSBUNAME','ORGZONENAME','ORGRONAME','ORGSANAME'],as_index = False)['NETWEIGHT_TMT'].sum().round(0)
                    his_data['ORGSBUNAME'] = his_data['ORGSBUNAME'].fillna('').astype(str)
                    his_data['ORGZONENAME'] = his_data['ORGZONENAME'].fillna('').astype(str)
                    his_data['ORGRONAME'] = his_data['ORGRONAME'].fillna('').astype(str)
                    his_data['ORGSANAME'] = his_data['ORGSANAME'].fillna('').astype(str)
                    his_data = his_data.rename(columns = {'NETWEIGHT_TMT':'ACTUAL_HISTORY_TMT'})
                    resp['month_name'] = resp['month_name'].apply(lambda x:x[:3] if len(x)>=3 else x)
                    resp = resp.merge(his_data[['month_name','ACTUAL_HISTORY_TMT','fiscal_year','ORGSBUNAME','ORGZONENAME','ORGRONAME','ORGSANAME']],
                                      how='left',left_on=['month_name','SBU_Name','Zone_Name','Region_Name','SalesArea_Name'],
                                      right_on = ['month_name','ORGSBUNAME','ORGZONENAME','ORGRONAME','ORGSANAME'])
                    resp['fiscal_year'] = resp['fiscal_year'].bfill()
                    if "ACTUAL_HISTORY_TMT" in resp.columns.tolist():
                        resp['ACTUAL_HISTORY_TMT'] = resp['ACTUAL_HISTORY_TMT'].fillna(0).astype(int)
                    agg_dict["ACTUAL_HISTORY_TMT"] = lambda x: ', '.join(map(str, x.unique()))
                

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg(agg_dict)
                resultCols = []
                
                if "H" in selected_keys and "YTD" in selected_keys:
                        resultCols.append("ACTUAL_HISTORY_TMT")
                        
                if "T" in selected_keys and "YTD" in selected_keys:
                    resultCols.append("TARGET_QTY_TMT")
                        
                if len(resultCols)>0:
                    current_date = helpers.get_time_stamp_by_delta(days=0,with_month_start_day=False,date_time_format=None)
                    grouped_resp = await GlobalAnalytics.calculate_ytd(current_date,grouped_resp,resultCols,current_month=False)
            if "NETWEIGHT_TMT" in  grouped_resp.columns:   
                grouped_resp["NETWEIGHT_TMT"] = grouped_resp["NETWEIGHT_TMT"].round(0)
            if "TARGET_QTY_TMT" in grouped_resp.columns:
                grouped_resp["TARGET_QTY_TMT"] = grouped_resp["TARGET_QTY_TMT"].round(0)
            # Return grouped response
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    
    @staticmethod
    async def sales_growth(filters, cross_filters, drill_state):
        """
        Fetches the sales performance data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the sales performance data.
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
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

        # Reverse mapping (for returning the short form)
        reverse_month_mapping = {v: k for k, v in month_mapping.items()}

        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.MomLevelFinalMetaData.get_clause_conditions(formated=True)]
            sales_growth_query = lpg_plant_queries.lpg_plant_query.get("sales_growth")
            sales_growth_query_ = sales_growth_query
            print("sales_growth_query_",sales_growth_query_)
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                #commenting this as the lastest table is having month_name as Jan,Feb etc
                #if rec.key == '"month_name"':  # Only handle the month_name case separately
                    # Check if any value in rec.value is in month_mapping
                #    rec.value = [month_mapping.get(val.strip(), val.strip()) for val in rec.value]

                # result = [value.strip() for value in rec.value.split(",")]

                if isinstance(rec.value, str):
                    print("in if ")
                    condition = f" and {rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        print("if in else")
                        if rec.key =='"SBU_Name"':
                            rec.key = '"ORGSBUNAME"'
                        elif rec.key == '"Zone_Name"':
                            rec.key = '"ORGZONENAME"'
                        elif rec.key == '"SalesArea_Name"':
                            rec.key = '"ORGSANAME"'
                        elif rec.key == '"Region_Name"':
                            rec.key = '"ORGRONAME"'

                        condition = f" and {rec.key} = '{rec.value[0]}'"
                    else:
                        print("else in else")
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)

            if conditions:
                #sales_growth_query_ += ' WHERE '
                sales_growth_query_ += ''.join(conditions)
        else:
            # Fallback query if no filters are provided
            sales_growth_query_ = """  
                SELECT
                    ROUND(SUM("MOM_LEVEL_FINAL_DATA"."NETWEIGHT_TMT")) AS "total_sales",
                    "MOM_LEVEL_FINAL_DATA"."fiscal_year" AS "fiscal_year",
                    "MOM_LEVEL_FINAL_DATA"."month_name"
                FROM
                    "hpcl_ceg"."public"."MOM_LEVEL_FINAL_DATA"
                WHERE
                    "MOM_LEVEL_FINAL_DATA"."fiscal_year" in ('2023-2024','2024-2025')
                GROUP BY
                  "MOM_LEVEL_FINAL_DATA"."fiscal_year","MOM_LEVEL_FINAL_DATA"."month_name"
                ORDER BY
                    "MOM_LEVEL_FINAL_DATA"."fiscal_year" ASC

            """
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.MomLevelFinalMetaData.get_clause_conditions(formated=True)]
            sales_growth_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(sales_growth_query_, access_filters, drill_state)
            print("sales_growth_query_: ", sales_growth_query_)
            resp = await function(query=sales_growth_query_)
            month_map = {'Apr': '0', 'May': '1', 'Jun': '2', 'Jul': '3', 'Aug': '4', 'Sep': '5', 'Oct': '6', 'Nov': '7',
                         'Dec': '8', 'Jan': '9', 'Feb': '10', 'Mar': '11'}
            d = {"2023-2024": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0,
                               "11": 0},
                 "2024-2025": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0,
                               "11": 0},
                 "fy_month": {"0": "1", "1": "2", "2": "3", "3": "4", "4": "5", "5": "6", "6": "7", "7": "8", "8": "9",
                              "9": "10", "10": "11", "11": "12"},
                 "month_name": {"0": "Apr", "1": "May", "2": "Jun", "3": "Jul", "4": "Aug", "5": "Sep", "6": "Oct",
                                "7": "Nov", "8": "Dec", "9": "Jan", "10": "Feb", "11": "Mar"}}

            for rec in resp:
                if rec['fiscal_year'] == "2024-2025":
                    d['2024-2025'][month_map[rec['month_name']]] = rec['total_sales']
                else:
                    d['2023-2024'][month_map[rec['month_name']]] = rec['total_sales']
            return {"status": True, "message": "success", "data": d}
        
        resp = await function(query=sales_growth_query_)
        resp = pd.DataFrame(resp)
        resp =resp.rename(columns = {'ORGSBUCD':'SBU','ORGSBUNAME':'SBU_Name','ORGZONECD':'ZONE','ORGZONENAME':'Zone_Name','ORGRONAME':'Region_Name',
            'NETWEIGHT_TMT':'total_sales', 'ORGSANAME':'SalesArea_Name',"ORGSACD":"SA","ORGROCD":"REGION"})

        # Fill missing values for numeric columns
        for each_float_col in ["sum_total_sales", "total_sales"]:
            if each_float_col in resp.columns.tolist():
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
             "month_name", "SBU", "ZONE", "REGION", "SA",

            "Zone_Name", "Region_Name", "SalesArea_Name", "fiscal_year",
            "month_name"
        ]:
            resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        
        if filters:
            filter_keys = [rec.key.strip('"') for rec in filters]
            filter_keys = [x.replace('ORGSBUNAME', 'SBU_Name') if 'ORGSBUNAME' in x else x.replace('ORGZONENAME', 'Zone_Name') if 'ORGZONENAME' in x else x.replace('ORGSANAME','SalesArea_Name') if 'ORGSANAME'in x else x.replace('ORGRONAME','Region_Name') if 'ORGRONAME' in x else x for x in filter_keys]
            resp["month_name"] = resp["month_name"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )
            grouped_keys = ["fiscal_year", "month_name"]
            # this is for getting all the months data for the specific SBU and fiscal year
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'SBU_Name' in filter_keys:
                grouped_keys.extend(["SBU_Name"])
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'Zone_Name' in filter_keys:
                grouped_keys.extend(["Zone_Name"])
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'Region_Name' in filter_keys:
                grouped_keys.extend(["Region_Name"])
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'SalesArea_Name' in filter_keys:
                grouped_keys.extend(["SalesArea_Name"])
            
            if "month_name" in filter_keys and "SBU_Name" not in filter_keys:
                grouped_keys.append("SBU_Name")
            elif "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
                if "DS Lubes" in filters[-1].value[0] or 'DS' in filters[-1].value[0] or 'Lubes' in filters[-1].value[0]:
                    grouped_keys.extend(["SBU_Name", "Region_Name"])
                else:
                    grouped_keys.extend(["SBU_Name", "Zone_Name"])
            elif ("month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and
                  "Region_Name" not in filter_keys):
                grouped_keys.extend(["SBU_Name", "Zone_Name", "Region_Name"])
            elif ("month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys
                  and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys):
                grouped_keys.extend(["SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"])
            elif ("month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and
                  "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys):
                grouped_keys.extend(["SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name","MATERIALGROUPNAME"])
            grouped_resp = resp.groupby(grouped_keys, as_index=False).agg({
                "total_sales": lambda x: round(sum(x),2),
            })
            print("grouped_keys->>",grouped_keys)
            if grouped_resp is not None:
                if "sbu_name" in resp.columns.tolist():
                    sub_name = list(set(rec['SBU_Name'] for rec in grouped_resp.to_dict(orient='records')))
                transformed_data = []
                data = grouped_resp.to_dict(orient='records')
                print("data-->>",data)
                '''
                for sbu_name in sub_name:
                    entry = {
                        "month_name": "Jan",
                        "SBU_Name": sbu_name,
                        "2024-2025": next((item['total_sales'] for item in data if
                                           item['SBU_Name'] == sbu_name and item['fiscal_year'] == '2024-2025'), 0),
                        "2023-2024": next((item['total_sales'] for item in data if
                                           item['SBU_Name'] == sbu_name and item['fiscal_year'] == '2023-2024'), 0)
                    }
                    for key in ["Zone_Name", "Region_Name", "SalesArea_Name"]:
                        if key in grouped_keys:
                            if key in data[0]:
                            entry[key] = next((item[key] for item in data if item['SBU_Name'] == sbu_name), None)
                    
                    transformed_data.append(entry)
                return {"status": True, "message": "success", "data": transformed_data}
                '''
                # added the below lines from 685 to 696 for dorrect drill data from backend 
                '''
                for record in data:
                    entry = {
                        "month_name": record["month_name"],
                        "SBU_Name": record["SBU_Name"],
                        "2024-2025": record["total_sales"] if record["fiscal_year"] == "2024-2025" else 0,
                        "2023-2024": record["total_sales"] if record["fiscal_year"] == "2023-2024" else 0,
                        "fiscal_year": record["fiscal_year"]
                    }
                    for key in grouped_keys:
                        if key in record:
                            entry[key] = record[key]
                    transformed_data.append(entry)
                '''
                if "sbu_name" in resp.columns.tolist():
                    grouped_data = defaultdict(lambda: {'2023-2024': 0, '2024-2025': 0, 'month_name': '', 'SBU_Name': ''})
                else:
                    grouped_data = defaultdict(lambda: {'2023-2024': 0, '2024-2025': 0, 'month_name': ''})
                #grouped_keys =  ['fiscal_year', 'month_name', 'SBU_Name']
                key_fields = [key for key in grouped_keys if key != 'fiscal_year']  # Exclude 'fiscal_year'

                for record in data:
                    key = tuple(record[field] for field in key_fields)    
                    #key = (record['month_name'], record['SBU_Name'],record['Zone_Name'])
                    for field in key_fields:
                        grouped_data[key][field] = record.get(field, '')
                    grouped_data[key][record['fiscal_year']] = record['total_sales']
                result = list(grouped_data.values())
                return {"status": True, "message": "success", "data": result}

        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    @staticmethod
    async def sales_yearly_performance(filters, cross_filters, drill_state):
        """
        Fetches the sales performance data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the sales performance data.
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        # Get the filter keys from the filters list
        filter_keys = [rec.key.strip('"') for rec in filters]

        sales_yearly_preformance_query = lpg_plant_queries.lpg_plant_query.get("sales_performance")
        sales_yearly_preformance_query_ = sales_yearly_preformance_query
        
        if filters:
            sales_performance_query = lpg_plant_queries.lpg_plant_query.get("sales_performance")
            sales_performance_query_ = sales_performance_query
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                # result = [value.strip() for value in rec.value.split(",")]

                if isinstance(rec.value, str):
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)

            if conditions:
                sales_performance_query_ += ' WHERE '
                sales_performance_query_ += ' AND '.join(conditions)
        
        else:
            sales_performance_query_ = f'''
                SELECT
                    ROUND(SUM("M60_LEVEL_METADATA"."NETWEIGHT_TMT")::NUMERIC, 2) AS "ACTUAL_TMT_SALES",
                    ROUND(SUM("M60_LEVEL_METADATA"."TARGET_QTY_TMT")::NUMERIC, 2) AS "TARGET_TMT_SALES",
                    "M60_LEVEL_METADATA"."FISCAL_YEAR" AS "FISCAL_YEAR"
                FROM
                    "hpcl_ceg"."public"."M60_LEVEL_METADATA"
                GROUP BY
                    "M60_LEVEL_METADATA"."FISCAL_YEAR"
                ORDER BY
                    "M60_LEVEL_METADATA"."FISCAL_YEAR" ASC

            '''

            resp = await function(query=sales_performance_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)

            # Fill missing values for numerical columns
            for each_float_col in [
                "ACTUAL_TMT_SALES", "TARGET_TMT_SALES"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "FISCAL_YEAR"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": resp}
        
        # Execute the query
        resp = await function(query=sales_performance_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)

        # Fill missing values for numerical columns
        for each_float_col in [
            "TARGET_QTY_TMT", "Prediction_Value", "Product_Achievement", 
            "Zone_Region_Achievement", "Rate_Per_Day_Required_MMT", 
            "Rate_per_day_current_MMT", "FinalSum", "FinalActualSum", "NETWEIGHT_TMT"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "SBU", "SBU_Name", "ZONE", "Zone_Name", "REGION", "Region_Name", "SA", 
            "SalesArea_Name", "PRODUCT", "ProductName", "UOM", "FISCAL_YEAR", 
            "month_year", "month_name"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

        # Apply grouping logic based on filters
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]

            if "FISCAL_YEAR" in filter_keys and "SBU_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and "Region_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name","Region_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys \
                    and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name","Region_Name","SalesArea_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and \
                    "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys and "ProductName" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name","Region_Name","SalesArea_Name","ProductName"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })


            # Return grouped response
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}


        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    @staticmethod
    async def yearly_sales_performance(filters, cross_filters, drill_state):
        """
        Fetches the sales performance data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the sales performance data.
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        # Get the filter keys from the filters list
        filter_keys = [rec.key.strip('"') for rec in filters]

        sales_yearly_preformance_query = lpg_plant_queries.lpg_plant_query.get("sales_performance")
        sales_yearly_preformance_query_ = sales_yearly_preformance_query
        
        if filters and any(rec.key not in ['"H"', '"T"', '"BE"', '"RI"', '"A"'] for rec in filters):
            sales_performance_query = lpg_plant_queries.lpg_plant_query.get("sales_performance")
            sales_performance_query_ = sales_performance_query
            conditions = []
            
            # Define keys to exclude from the WHERE clause
            excluded_keys = {"A", "H", "T", "BE", "RI"}
            
            for rec in filters:
                rec.value = rec.value.split(",")
                if rec.key == '"month_name"':  # Only handle the month_name case separately
                    # Check if any value in rec.value is in month_mapping
                    rec.value = [month_mapping.get(val.strip(), val.strip()) for val in rec.value]
                
                # Skip keys that should not be added to the WHERE clause
                if rec.key in excluded_keys:
                    continue
                
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
                sales_performance_query_ += ' WHERE '
                sales_performance_query_ += ' AND '.join(conditions) 

        elif len(filters) >= 1 and (filters[0].key in ['"H"', '"T"', '"BE"', '"RI"', '"A"']):
            print("into elif")
            selected_keys = [rec.key.strip('"') for rec in filters]
            current_date = datetime.now()
            current_year = current_date.year
            next_year = current_year + 1
            current_month = current_date.month
            # Determine the current financial year
            if current_month >= 4:  # April or later
                fiscal_year_start = f"'FY {current_year}-{next_year}'"
            else:  # January to March
                previous_year = current_year - 1
                fiscal_year_start = f"'FY {previous_year}-{current_year}'"

            # Initialize the dynamic parts of the query
            where_conditions = []
            select_columns = [
                'ROUND(SUM("M60_LEVEL_METADATA"."NETWEIGHT_TMT")::NUMERIC, 2) AS "ACTUAL_TMT_SALES"',
                '"M60_LEVEL_METADATA"."FISCAL_YEAR" AS "FISCAL_YEAR"',
            ]
            group_by_columns = [
                '"M60_LEVEL_METADATA"."FISCAL_YEAR"',
            ]

            # Build conditions based on selected keys
            if "H" in selected_keys:
                previous_year = current_year - 1
                where_conditions.append(f'"M60_LEVEL_METADATA"."FISCAL_YEAR" IN (\'FY {previous_year}-{current_year}\', \'FY {current_year}-{next_year}\')')

            if "T" in selected_keys:
                select_columns.append('ROUND(SUM("M60_LEVEL_METADATA"."TARGET_QTY_TMT")::NUMERIC, 2) AS "TARGET_TMT_SALES"')

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
            # Construct the query dynamically
            sales_performance_query_ = f'''
                SELECT
                    {', '.join(select_columns)}
                FROM
                    "M60_LEVEL_METADATA"
                {where_clause}
                GROUP BY
                    {', '.join(group_by_columns)}
                ORDER BY
                    "M60_LEVEL_METADATA"."FISCAL_YEAR" ASC
            '''
            
            print("Generated Query:", sales_performance_query_)  # Debugging: Print the generated query

            resp = await function(query=sales_performance_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)

            # Fill missing values for numerical columns
            for each_float_col in ["ACTUAL_TMT_SALES", "TARGET_QTY_TMT"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in ["fy_month", "month_name"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            
            return {"status": True, "message": "success", "data": resp}
            
        else:
            sales_performance_query_ = f'''
                SELECT
                    ROUND(SUM("M60_LEVEL_METADATA"."NETWEIGHT_TMT")::NUMERIC, 2) AS "ACTUAL_TMT_SALES",
                    "M60_LEVEL_METADATA"."FISCAL_YEAR" AS "FISCAL_YEAR"
                FROM
                    "hpcl_ceg"."public"."M60_LEVEL_METADATA"
                GROUP BY
                    "M60_LEVEL_METADATA"."FISCAL_YEAR"
                ORDER BY
                    "M60_LEVEL_METADATA"."FISCAL_YEAR" ASC
            '''

            resp = await function(query=sales_performance_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)

            # Fill missing values for numerical columns
            for each_float_col in [
                "ACTUAL_TMT_SALES"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "FISCAL_YEAR"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": resp}
        
        # Execute the query
        resp = await function(query=sales_performance_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)

        # Fill missing values for numerical columns
        for each_float_col in [
            "TARGET_QTY_TMT", "Prediction_Value", "Product_Achievement", 
            "Zone_Region_Achievement", "Rate_Per_Day_Required_MMT", 
            "Rate_per_day_current_MMT", "FinalSum", "FinalActualSum", "NETWEIGHT_TMT"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "SBU", "SBU_Name", "ZONE", "Zone_Name", "REGION", "Region_Name", "SA", 
            "SalesArea_Name", "PRODUCT", "ProductName", "UOM", "FISCAL_YEAR", 
            "month_year", "month_name"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

        # Apply grouping logic based on filters
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]

            if "FISCAL_YEAR" in filter_keys and "SBU_Name" not in filter_keys:
                # Define the set of valid keys
                valid_keys = {"A", "H", "T", "BE", "RI"}
                
                # Extract user-selected keys with `value == 'true'`
                selected_keys = {rec.key for rec in filters if rec.key in valid_keys and rec.value == 'true'}
                
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}
                
                if "T" in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name"], as_index=False).agg(agg_dict)

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
                # Define the set of valid keys
                valid_keys = {"A", "H", "T", "BE", "RI"}
                
                # Extract user-selected keys with `value == 'true'`
                selected_keys = {rec.key for rec in filters if rec.key in valid_keys and rec.value == 'true'}
                
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}
                
                if "T" in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name", "Zone_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name", "Zone_Name"], as_index=False).agg(agg_dict)

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and "Region_Name" not in filter_keys:
                # Define the set of valid keys
                valid_keys = {"A", "H", "T", "BE", "RI"}
                
                # Extract user-selected keys with `value == 'true'`
                selected_keys = {rec.key for rec in filters if rec.key in valid_keys and rec.value == 'true'}
                
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}
                
                if "T" in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg(agg_dict)

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys \
                    and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys:
                # Define the set of valid keys
                valid_keys = {"A", "H", "T", "BE", "RI"}
                
                # Extract user-selected keys with `value == 'true'`
                selected_keys = {rec.key for rec in filters if rec.key in valid_keys and rec.value == 'true'}
                
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}
                
                if "T" in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg(agg_dict)

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and \
                    "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys and "ProductName" not in filter_keys:
                # Define the set of valid keys
                valid_keys = {"A", "H", "T", "BE", "RI"}
                
                # Extract user-selected keys with `value == 'true'`
                selected_keys = {rec.key for rec in filters if rec.key in valid_keys and rec.value == 'true'}
                
                # Define the aggregation dictionary dynamically
                agg_dict = {"NETWEIGHT_TMT": "sum"}
                
                if "T" in selected_keys:
                    agg_dict["TARGET_QTY_TMT"] = "sum"
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg(agg_dict)

            # Return grouped response
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}


        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    @staticmethod
    async def sales_yearly_growth(filters, cross_filters, drill_state):
        """
        Fetches the sales performance data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the sales performance data.
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        # Get the filter keys from the filters list
        filter_keys = [rec.key.strip('"') for rec in filters]

        sales_yearly_growth_query = lpg_plant_queries.lpg_plant_query.get("sales_growth")
        sales_yearly_growth_query_ = sales_yearly_growth_query
        
        if filters:
            sales_yearly_growth_query = lpg_plant_queries.lpg_plant_query.get("sales_growth")
            sales_yearly_growth_query_ = sales_yearly_growth_query
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                # result = [value.strip() for value in rec.value.split(",")]

                if isinstance(rec.value, str):
                    condition = f" and {rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f" and {rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)

            if conditions:
                #sales_performance_query_ += ' WHERE '
                sales_yearly_growth_query_ += ' AND '.join(conditions)
        
        else:
            sales_yearly_growth_query_ = f'''
                SELECT
                    ROUND(SUM("MOM_LEVEL_SALES_TEST1"."total_sales")::NUMERIC, 2) AS "ACTUAL_TMT_SALES",
                    
                    "MOM_LEVEL_SALES_TEST1"."fiscal_year" AS "fiscal_year"
                FROM
                    "hpcl_ceg"."public"."MOM_LEVEL_SALES_TEST1"
                WHERE 
                    "fiscal_year" in ('2023-2024','2024-2025')
                GROUP BY
                    "MOM_LEVEL_SALES_TEST1"."fiscal_year"
                ORDER BY
                    "MOM_LEVEL_SALES_TEST1"."fiscal_year" ASC

            '''
            
            resp = await function(query=sales_yearly_growth_query_)
            return {"status": True, "message": "success", "data": resp}
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)

            # Fill missing values for numerical columns
            for each_float_col in [
                "ACTUAL_TMT_SALES", "TARGET_TMT_SALES"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "FISCAL_YEAR"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": resp}
        
        # Execute the query
        resp = await function(query=sales_yearly_growth_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)

        # Fill missing values for numerical columns
        for each_float_col in [
            "TARGET_QTY_TMT", "Prediction_Value", "Product_Achievement", 
            "Zone_Region_Achievement", "Rate_Per_Day_Required_MMT", 
            "Rate_per_day_current_MMT", "FinalSum", "FinalActualSum", "NETWEIGHT_TMT"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "SBU", "SBU_Name", "ZONE", "Zone_Name", "REGION", "Region_Name", "SA", 
            "SalesArea_Name", "PRODUCT", "ProductName", "UOM", "FISCAL_YEAR", 
            "month_year", "month_name"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

        # Apply grouping logic based on filters
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]

            if "FISCAL_YEAR" in filter_keys and "SBU_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })
                grouped_resp = resp.groupby(["fiscal_year", "month_name", "SBU_Name"], as_index=False).agg({
                    "total_sales": lambda x: sum(round(x)),
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and "Region_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name","Region_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys \
                    and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name","Region_Name","SalesArea_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and \
                    "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys and "ProductName" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name","Region_Name","SalesArea_Name","ProductName"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })


            # Return grouped response
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}


        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
                            
        
    @staticmethod
    async def card_chart(filters, cross_filters, drill_state):
        try:
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'
            function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
            card_query = lpg_plant_queries.lpg_plant_query.get(drill_state)
            resp = await function(query=card_query)
            resp = pd.DataFrame(resp)
            return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
        except Exception as e:
            print("Exception in BigNumber Chart :", str(e))
            return {"status": True, "message": "success", "data": []}
            

    @staticmethod
    async def carry_forward_analysis(filters, cross_filters, drill_state):
        """
        For Dry Out and Indent Carry Forward Analysis
        :param filters:
        :param drill_state:
        :return:
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        query = lpg_plant_queries.lpg_plant_query.get("carry_forward_analysis")
        query = lpg_plant_queries.lpg_plant_query.get("carry_fwd_indent")
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
            query += f" WHERE {' AND '.join(conditions)}"
        query += " GROUP BY execution_date::DATE"
        resp = await function(query=query)
        return resp

    @staticmethod
    async def location_wise_distribution(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        location_wise_distribution_query = lpg_plant_queries.lpg_plant_query.get("location_wise_distribution")
        location_wise_distribution_query_ = location_wise_distribution_query
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            location_wise_distribution_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(location_wise_distribution_query, filters, drill_state)
        try:
            resp = await function(query=location_wise_distribution_query_)
            # keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(location_wise_distribution_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            # keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(location_wise_distribution_query)
        # data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": resp}            
        
    
    @staticmethod
    async def cp_total_locations(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        cp_locations_query = lpg_plant_queries.lpg_plant_query.get('cp_total_locations')
        
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.ConsumerPumpTankDelivery.get_clause_conditions(formated=True)]
        if filters:
            cp_locations_query = await widget_actions.WidgetActions.apply_filter_drilldown(cp_locations_query, filters, drill_state)
        
        print("query before execution: ", cp_locations_query)
        resp = await function(query=cp_locations_query)

        return {"status": True, "message": "success", "data": resp}
    
    @staticmethod
    async def cp_total_dus(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        cp_dus_query = lpg_plant_queries.lpg_plant_query.get('cp_total_dus')
        
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.ConsumperPumpTransaction.get_clause_conditions(formated=True)]
        if filters:
            cp_dus_query = await widget_actions.WidgetActions.apply_filter_drilldown(cp_dus_query, filters, drill_state)
        
        print("query before execution: ", cp_dus_query)
        resp = await function(query=cp_dus_query)

        return {"status": True, "message": "success", "data": resp}
    

    @staticmethod
    async def cp_total_tanks(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        cp_dus_query = lpg_plant_queries.lpg_plant_query.get('cp_total_tanks')
        
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.ConsumerPumpTankDelivery.get_clause_conditions(formated=True)]
        if filters:
            cp_dus_query = await widget_actions.WidgetActions.apply_filter_drilldown(cp_dus_query, filters, drill_state)
        
        print("query before execution: ", cp_dus_query)
        resp = await function(query=cp_dus_query)

        return {"status": True, "message": "success", "data": resp}

    @staticmethod
    async def cp_avg_monthly_consumption(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        cp_query = lpg_plant_queries.lpg_plant_query.get('cp_avg_monthly_consumption')
        
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.ConsumerPumpTankDelivery.get_clause_conditions(formated=True)]
        if filters:
            cp_query = await widget_actions.WidgetActions.apply_filter_drilldown(cp_query, filters, drill_state)
        
        print("query before execution: ", cp_query)
        resp = await function(query=cp_query)

        return {"status": True, "message": "success", "data": resp}

    @staticmethod
    async def cp_avg_monthly_consumption_by_location(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        cp_query = lpg_plant_queries.lpg_plant_query.get('cp_avg_monthly_consumption_by_location')
        
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.ConsumerPumpTankDelivery.get_clause_conditions(formated=True)]
        if filters:
            cp_query = await widget_actions.WidgetActions.apply_filter_drilldown(cp_query, filters, drill_state)
        
        print("query before execution: ", cp_query)
        resp = await function(query=cp_query)

        return {"status": True, "message": "success", "data": resp}

    @staticmethod
    async def cp_total_volume_consumption(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        cp_query = lpg_plant_queries.lpg_plant_query.get('cp_total_volume_consumption')
        
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.ConsumerPumpTankDelivery.get_clause_conditions(formated=True)]
        if filters:
            cp_query = await widget_actions.WidgetActions.apply_filter_drilldown(cp_query, filters, drill_state)
        
        print("query before execution: ", cp_query)
        resp = await function(query=cp_query)

        return {"status": True, "message": "success", "data": resp}

    @staticmethod
    async def cp_total_volume_sales(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        cp_query = lpg_plant_queries.lpg_plant_query.get('cp_total_volume_sales')
        
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.ConsumperPumpTransaction.get_clause_conditions(formated=True)]
        if filters:
            cp_query = await widget_actions.WidgetActions.apply_filter_drilldown(cp_query, filters, drill_state)
        
        print("query before execution: ", cp_query)
        resp = await function(query=cp_query)
        return {"status": True, "message": "success", "data": resp}
    
    
    @staticmethod
    async def lpg_operations_productivity_zone(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        current_date = datetime.now().strftime("%Y-%m-%d")
        productivity_zone_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_operations_productivity_zone")
        _filters = []
        daterange = None
        if cross_filters:
            for filter in cross_filters:
                if "DATE" in filter.key:
                    daterange = f" '{filter.value.split(",")[0]}' AND '{filter.value.split(",")[-1]}' "
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
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
                productivity_zone_query_  += ' WHERE '
                productivity_zone_query_  += ' AND '.join(conditions)
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)]
            productivity_zone_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(productivity_zone_query_, access_filters, drill_state)
            if not daterange:
                productivity_zone_query_ += f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            elif daterange:
                productivity_zone_query_ += f' AND "process_date" BETWEEN {daterange} AND "zone" IS NOT NULL'
            productivity_zone_query_ += ' GROUP BY "zone", "name", "process_date", "filling_heads", "site_area" '
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)]
            productivity_zone_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(productivity_zone_query_, access_filters, drill_state)
            if not "where" in productivity_zone_query_.lower() and not daterange:
                productivity_zone_query_ += f' WHERE CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            elif not "where" in productivity_zone_query_.lower() and daterange:
                productivity_zone_query_ += f' WHERE "process_date" BETWEEN {daterange} AND "zone" IS NOT NULL'
            elif not daterange:
                productivity_zone_query_ += f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            elif daterange:
                productivity_zone_query_ += f' AND "process_date" BETWEEN {daterange} AND "zone" IS NOT NULL'
            productivity_zone_query_ += ' GROUP BY "zone", "name", "process_date", "filling_heads", "site_area" '
            
            resp = await function(query=productivity_zone_query_)
            resp = pd.DataFrame(resp)
            resp = await filter_data(resp, _filters)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["zone", "carousel_type"], as_index=False).agg({
                        "productivity": "mean"
                    })
            for each_float_col in ["productivity"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0).round()
            # Fill missing values for string columns
            for each_str_col in ["zone", "name", "carousel_type"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        resp = await function(query=productivity_zone_query_)
        if resp:
            resp = pd.DataFrame(resp)
            resp = await filter_data(resp, _filters)
            for each_float_col in ["productivity"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0).round()
            for each_str_col in ["zone","name","carousel_type"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            if filters:
                grouped_resp = None
                filter_keys = [rec.key.strip('"') for rec in filters]
                if "zone" in filter_keys and "name" not in filter_keys:
                    grouped_resp = resp.groupby(["zone","name","carousel_type"], as_index=False).agg({
                        "productivity": "mean"
                    })
                if grouped_resp is not None:
                    return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        else:
            return {"status": True, "message":"success", "data":[]}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_operations_production_zone(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        _filters = []
        daterange = None
        if cross_filters:
            for filter in cross_filters:
                if "DATE" in filter.key:
                    daterange = f" '{filter.value.split(",")[0]}' AND '{filter.value.split(",")[-1]}' "
                _filters.append({f"{filter.key}": f"{filter.value}"})
        current_date = datetime.now().strftime("%Y-%m-%d")
        production_zone_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_operations_production_zone")
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
                production_zone_query_  += ' WHERE '
                production_zone_query_  += ' AND '.join(conditions)
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)]
            production_zone_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(production_zone_query_, access_filters, drill_state)
            if not daterange:
                production_zone_query_ +=  f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            elif daterange:
                production_zone_query_ +=  f' AND "process_date" BETWEEN {daterange} AND "zone" IS NOT NULL '
            production_zone_query_  += ' GROUP BY "zone", "name", "site_area" '
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)]
            production_zone_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(production_zone_query_, access_filters, drill_state)
            if not "where" in production_zone_query_.lower() and not daterange:
                production_zone_query_ +=  f' WHERE CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            elif not "where" in production_zone_query_.lower() and daterange:
                production_zone_query_ +=  f' WHERE "process_date" BETWEEN {daterange} AND "zone" IS NOT NULL'
            elif not daterange:
                production_zone_query_ +=  f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            elif daterange:
                production_zone_query_ +=  f' AND "process_date" BETWEEN {daterange} AND "zone" IS NOT NULL'
            production_zone_query_  += ' GROUP BY "zone", "name", "site_area" '
            
            print("production_zone_query_ :", production_zone_query_)
            resp = await function(query=production_zone_query_)
            resp = pd.DataFrame(resp)
            resp = await filter_data(resp, _filters)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["zone"], as_index=False).agg({
                        "Productions": "sum"
                    })
            for each_float_col in ["Productions"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0).round(2)
            for each_str_col in ["zone", "name"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        resp = await function(query=production_zone_query_)
        if resp:
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            resp = await filter_data(resp, _filters)
            for each_float_col in ["Productions"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0).round(2)
            # Fill missing values for string columns
            for each_str_col in ["zone", "name"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            if filters:
                grouped_resp = None
                filter_keys = [rec.key.strip('"') for rec in filters]
                if "zone" in filter_keys and "name" not in filter_keys:
                    grouped_resp = resp.groupby(["zone","name"], as_index=False).agg({
                        "Productions": "sum"
                    })
                    grouped_resp["Productions"] = grouped_resp["Productions"].fillna(0.0).round(2)
                if grouped_resp is not None:
                    return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        else:
            return {"status": True, "message":"success", "data":[]}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def plants_connected(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        try:
            lpg_query = "SELECT DISTINCT(short_name) as plant_name FROM lpg_operations_summary"
            master_query = "SELECT DISTINCT(short_name) as plant_name FROM lpg_operations_masters"
            df = await function(query=lpg_query)
            master_df = await function(query=master_query)
            df = pl.DataFrame(df)
            master_df = pl.DataFrame(master_df)
            master_df = master_df.with_columns(
                pl.when(pl.col("plant_name").is_in(df["plant_name"])
                ).then(pl.lit("Connected")).otherwise(pl.lit("Not Connected")).alias("status"))
            return {"status": True, "message": "success", "data": master_df.to_dicts()}
        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {e}"}
    
    
    @staticmethod
    async def lpg_operations_filled_cylinder(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        current_date = datetime.now().strftime("%Y-%m-%d")
        handled_cylinder_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_operations_filled_cylinder")
        _filters = []
        daterange = None
        if cross_filters:
            for filter in cross_filters:
                if "DATE" in filter.key:
                    daterange = f" '{filter.value.split(",")[0]}' AND '{filter.value.split(",")[-1]}' "
                    continue
                _filters.append({f"{filter.key}": f"{filter.value}"})
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
                handled_cylinder_query_ += ' WHERE '
                handled_cylinder_query_ += ' AND '.join(conditions)
            if not daterange:
                handled_cylinder_query_ += f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            elif daterange:
                handled_cylinder_query_ += f' AND "process_date" BETWEEN {daterange} AND "zone" IS NOT NULL'
            handled_cylinder_query_ += ' GROUP BY  "zone" ,"plant" '
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgCsRejections.get_clause_conditions(formated=True)]
            handled_cylinder_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(handled_cylinder_query_, access_filters, drill_state)
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgCsRejections.get_clause_conditions(formated=True)]
            handled_cylinder_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(handled_cylinder_query_, access_filters, drill_state)
            if not "where" in handled_cylinder_query_.lower() and not daterange:
                handled_cylinder_query_ += f' WHERE CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            elif not "where" in handled_cylinder_query_.lower() and daterange:
                handled_cylinder_query_ += f' WHERE "process_date" BETWEEN {daterange} AND "zone" IS NOT NULL'
            elif not daterange:
                handled_cylinder_query_ += f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'            
            elif daterange:
                handled_cylinder_query_ += f' AND "process_date" BETWEEN {daterange} AND "zone" IS NOT NULL'
            handled_cylinder_query_ += ' GROUP BY "zone", "plant" '
            print("handled_cylinder_query_ :", handled_cylinder_query_)
            resp = await function(query=handled_cylinder_query_)
            resp = pd.DataFrame(resp)
            resp = await filter_data(resp, _filters)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["zone"], as_index=False).agg({
                    "Cylinder_Filled": "sum"
                })
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            for each_float_col in ["Cylinder_Filled"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)            
            for each_str_col in ["zone", "plant"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        # Execute the query
        resp = await function(query=handled_cylinder_query_)
        resp = pd.DataFrame(resp)
        resp = await filter_data(resp, _filters)
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        for each_float_col in ["Cylinder_Filled"]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)
        # Fill missing values for string columns
        for each_str_col in ["zone", "plant"]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "zone" in filter_keys and "plant" not in filter_keys:
                grouped_resp = resp.groupby(["zone", "plant"], as_index=False).agg({
                    "Cylinder_Filled": "sum"
                })
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def productivity_overtime_vs_break_production(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        productivity_overtime_query_ = lpg_plant_queries.lpg_plant_query.get("productivity_overtime_vs_break_production")        
        current_date = datetime.now().strftime("%Y-%m-%d")
        _filters = []
        daterange = None
        if cross_filters:
            for filter in cross_filters:
                if "DATE" in filter.key:
                    daterange = f" '{filter.value.split(",")[0]}' AND '{filter.value.split(",")[-1]}' "
                    continue
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                if rec.value:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} IN {tuple(rec.value)}"
                    conditions.append(condition)
            if conditions:
                productivity_overtime_query_ += ' WHERE ' + ' AND '.join(conditions)
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)]
            productivity_overtime_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(productivity_overtime_query_, access_filters, drill_state)
            if not daterange:
                productivity_overtime_query_ += f' AND CAST("process_date" AS DATE) = \'{current_date}\' '
            elif daterange:
                productivity_overtime_query_ += f' AND "process_date" BETWEEN {daterange} '
            productivity_overtime_query_ += ' GROUP BY "zone", "plant"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)]
            productivity_overtime_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(productivity_overtime_query_, access_filters, drill_state)
            if not "where" in productivity_overtime_query_.lower() and not daterange:
                productivity_overtime_query_ += f' WHERE CAST("process_date" AS DATE) = \'{current_date}\' '
            elif not "where" in productivity_overtime_query_.lower() and daterange:
                productivity_overtime_query_ += f' WHERE "process_date" BETWEEN {daterange} '
            elif not daterange:
                productivity_overtime_query_ += f' AND CAST("process_date" AS DATE) = \'{current_date}\' '
            elif daterange:
                productivity_overtime_query_ += f' AND "process_date" BETWEEN {daterange} '
            productivity_overtime_query_ += ' GROUP BY "zone", "plant"'
            resp = await function(query=productivity_overtime_query_)
            resp = pl.DataFrame(resp)
            resp = await filter_data(resp.to_pandas(), _filters)
            resp = pl.from_pandas(resp)
            resp = resp.group_by(["zone"]).agg([
                        pl.sum("break_production").round(1).alias("break_production"),
                        pl.sum("overtime_production").round(1).alias("overtime_prouction"),
                    ])
            return {"status": True, "message": "success", "data": resp.to_dicts()}
        try:
            resp = await function(query=productivity_overtime_query_)
            resp = pl.DataFrame(resp)
            resp = await filter_data(resp.to_pandas(), _filters)
            resp = pl.from_pandas(resp)
            # Fill missing values
            numerical_columns = ["break_production", "overtime_production"]
            string_columns = ["process_date", "zone", "plant"]

            for col in numerical_columns:
                if col in resp.columns:
                    resp = resp.with_columns(pl.col(col).fill_null(0.0))
            for col in string_columns:
                if col in resp.columns:
                    resp = resp.with_columns(pl.col(col).fill_null("").cast(pl.Utf8))
            # Grouping and filtering based on provided filters
            if filters:
                grouped_resp = None
                filter_keys = [rec.key.strip('"') for rec in filters]

                if "zone" in filter_keys and "plant" not in filter_keys:
                    grouped_resp = resp.group_by(["zone", "plant"]).agg([
                        pl.sum("break_production").round(1).alias("break_production"),
                        pl.sum("overtime_production").round(1).alias("overtime_prouction"),
                    ])                
                if grouped_resp is not None:
                    return {"status": True, "message": "success", "data": grouped_resp.to_dicts()}

            return {"status": True, "message": "success", "data": resp.to_dicts()}
        except Exception as e:
            print(traceback.format_exc())
            print(f"Error executing query: {e}")
            return {"status": False, "message": f"Error: {e}"}
    
    
    @staticmethod
    async def lpg_operations_daywise_productivity(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        daywise_productivity_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_operations_daywise_productivity")
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                if isinstance(rec.value, str):  # Use dot notation instead of subscription
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)
            if conditions:
                daywise_productivity_query_ += ' WHERE ' 
                daywise_productivity_query_ += ' AND '.join(conditions)
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)]
            daywise_productivity_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(daywise_productivity_query_, access_filters, drill_state)
            daywise_productivity_query_ += ' AND "process_date" >= CURRENT_DATE - INTERVAL \'30 day\' AND "process_date" <= NOW() '
            daywise_productivity_query_ += ' GROUP BY DATE("process_date"), "zone", "site_area" '
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)]
            daywise_productivity_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(daywise_productivity_query_, access_filters, drill_state)
            if not "where" in daywise_productivity_query_.lower():
                daywise_productivity_query_ += ' WHERE "process_date" >= CURRENT_DATE - INTERVAL \'30 day\' AND "process_date" <= NOW() '
            else:
                daywise_productivity_query_ += ' AND "process_date" >= CURRENT_DATE - INTERVAL \'30 day\' AND "process_date" <= NOW() '
            daywise_productivity_query_ += ' GROUP BY DATE("process_date"), "zone", "site_area" '
        try:
            query_resp = await function(query=daywise_productivity_query_)
            resp = pl.DataFrame(query_resp)
            resp = await filter_data(resp.to_pandas(), _filters)
            resp = pl.from_pandas(resp)
            resp = resp.group_by(["process_date"]).agg([
                    pl.mean("avg_productivity").round(2).alias("avg_productivity"),
                ])
                        
            numerical_columns = ["productivity_normal_productivity"]
            for col in numerical_columns:
                if col in resp.columns:
                    resp = resp.with_columns(pl.col(col).fill_null(0.0))
            resp = resp.sort("process_date")
            resp = resp.with_columns(pl.col("process_date").dt.strftime("%Y-%m-%d").alias("process_date"))
            return {"status": True, "message": "success", "data": resp.to_dicts()}
        except Exception as e:
            print(traceback.format_exc())
            print(f"Error executing query: {e}")
            return {"status": False, "message": f"Error: {e}"}
    
    
    @staticmethod
    async def lpg_operations_daywise_production(filters ,cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        daywise_production_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_operations_daywise_production")        
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                if isinstance(rec.value, str):  # Use dot notation instead of subscription
                    condition = f"{rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        condition = f"{rec.key} = '{rec.value[0]}'"
                    else:
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)
            if conditions:
                daywise_production_query_ += ' WHERE ' 
                daywise_production_query_ += ' AND '.join(conditions)
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)]
            daywise_production_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(daywise_production_query_, access_filters, drill_state)
            daywise_production_query_ += ' AND "process_date" >= CURRENT_DATE - INTERVAL \'30 day\' AND "process_date" <= NOW() '
            daywise_production_query_ += ' GROUP BY DATE("process_date"), "zone", "site_area" '
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)]
            daywise_production_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(daywise_production_query_, access_filters, drill_state)
            if not "where" in daywise_production_query_.lower():
                daywise_production_query_ += ' WHERE "process_date" >= CURRENT_DATE - INTERVAL \'30 day\' AND "process_date" <= NOW() '
            else:
                daywise_production_query_ += ' AND "process_date" >= CURRENT_DATE - INTERVAL \'30 day\' AND "process_date" <= NOW() '
            daywise_production_query_ += ' GROUP BY DATE("process_date"), "zone", "site_area" '
        try:
            query_resp = await function(query=daywise_production_query_)
            resp = pl.DataFrame(query_resp)
            resp = await filter_data(resp.to_pandas(), _filters)
            resp = pl.from_pandas(resp)
            resp = resp.group_by(["process_date"]).agg([
                    pl.sum("sum_production").round(2).alias("sum_production"),
                ])
            numerical_columns = ["sum_production"]
            for col in numerical_columns:
                if col in resp.columns:
                    resp = resp.with_columns(pl.col(col).fill_null(0.0))
            resp = resp.sort("process_date")
            resp = resp.with_columns(pl.col("process_date").dt.strftime("%Y-%m-%d").alias("process_date"))
            return {"status": True, "message": "success", "data": resp.to_dicts()}
        except Exception as e:
            print(traceback.format_exc())
            print(f"Error executing query: {e}")
            return {"status": False, "message": f"Error: {e}"}

    

    @staticmethod
    async def sales_growth_ytd(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        sales_growth_ytd_query_ = lpg_plant_queries.lpg_plant_query.get("sales_growth_ytd")
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

        # Reverse mapping (for returning the short form)
        reverse_month_mapping = {v: k for k, v in month_mapping.items()}
        conditions = []
        if filters:
            for rec in filters:
                rec.value = rec.value.split(",")
                if isinstance(rec.value, str):
                    print("in if")
                    condition = f" and {rec.key} = '{rec.value}'"
                else:
                    if len(rec.value) == 1:
                        print("if in else")
                        if rec.key =='"SBU_Name"':
                            rec.key = '"ORGSBUNAME"'
                        elif rec.key == '"Zone_Name"':
                            rec.key = '"ORGZONENAME"'
                        elif rec.key == '"SalesArea_Name"':
                            rec.key = '"ORGSANAME"'
                        elif rec.key == '"Region_Name"':
                            rec.key = '"ORGRONAME"'
                        condition = f" and {rec.key} = '{rec.value[0]}'"
                    else:
                        print("else in else")
                        condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)

            if conditions:
                #sales_growth_query_ += ' WHERE '
                sales_growth_ytd_query_ += ''.join(conditions)
            sales_growth_ytd_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(sales_growth_ytd_query_, filters, drill_state)
        else:
            # Fallback query if no filters are provided
            sales_growth_ytd_query_ = """  
                SELECT
                    ROUND(SUM("MOM_DAY_LEVEL_DATA"."NETWEIGHT_TMT")) AS "total_sales",
                    "MOM_DAY_LEVEL_DATA"."fiscal_year" AS "fiscal_year",
                    "MOM_DAY_LEVEL_DATA"."month_name"
                FROM
                    "hpcl_ceg"."public"."MOM_DAY_LEVEL_DATA"
                WHERE
                    "MOM_DAY_LEVEL_DATA"."fiscal_year" in ('2023-2024','2024-2025')
                GROUP BY
                  "MOM_DAY_LEVEL_DATA"."fiscal_year","MOM_DAY_LEVEL_DATA"."month_name"
                ORDER BY
                    "MOM_DAY_LEVEL_DATA"."fiscal_year" ASC;
            """

            resp = await function(query=sales_growth_ytd_query_)
            month_map = {'Apr': '0', 'May': '1', 'Jun': '2', 'Jul': '3', 'Aug': '4', 'Sep': '5', 'Oct': '6', 'Nov': '7',
                         'Dec': '8', 'Jan': '9', 'Feb': '10', 'Mar': '11'}
            d = {"2023-2024": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0,
                               "11": 0},
                 "2024-2025": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "10": 0,
                               "11": 0},
                 "fy_month": {"0": "1", "1": "2", "2": "3", "3": "4", "4": "5", "5": "6", "6": "7", "7": "8", "8": "9",
                              "9": "10", "10": "11", "11": "12"},
                 "month_name": {"0": "Apr", "1": "May", "2": "Jun", "3": "Jul", "4": "Aug", "5": "Sep", "6": "Oct",
                                "7": "Nov", "8": "Dec", "9": "Jan", "10": "Feb", "11": "Mar"}}

            for rec in resp:
                if rec['fiscal_year'] == "2024-2025":
                    d['2024-2025'][month_map[rec['month_name']]] = rec['total_sales']
                else:
                    d['2023-2024'][month_map[rec['month_name']]] = rec['total_sales']
            return {"status": True, "message": "success", "data": d}
        
        resp = await function(query=sales_growth_ytd_query_)
        resp = pd.DataFrame(resp)
        resp =resp.rename(columns = {'ORGSBUCD':'SBU','ORGSBUNAME':'SBU_Name','ORGZONECD':'ZONE','ORGZONENAME':'Zone_Name','ORGRONAME':'Region_Name',
            'NETWEIGHT_TMT':'total_sales', 'ORGSANAME':'SalesArea_Name',"ORGSACD":"SA","ORGROCD":"REGION"})

        # Fill missing values for numeric columns
        for each_float_col in ["sum_total_sales", "total_sales"]:
            if each_float_col in resp.columns.tolist():
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
             "month_name", "SBU", "ZONE", "REGION", "SA",

            "Zone_Name", "Region_Name", "SalesArea_Name", "fiscal_year",
            "month_name"
        ]:
            resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        
        if filters:
            filter_keys = [rec.key.strip('"') for rec in filters]
            filter_keys = [x.replace('ORGSBUNAME', 'SBU_Name') if 'ORGSBUNAME' in x else x.replace('ORGZONENAME', 'Zone_Name') if 'ORGZONENAME' in x else x.replace('ORGSANAME','SalesArea_Name') if 'ORGSANAME'in x else x.replace('ORGRONAME','Region_Name') if 'ORGRONAME' in x else x for x in filter_keys]
            resp["month_name"] = resp["month_name"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )
            grouped_keys = ["fiscal_year", "month_name"]
            # this is for getting all the months data for the specific SBU and fiscal year
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'SBU_Name' in filter_keys:
                grouped_keys.extend(["SBU_Name"])
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'Zone_Name' in filter_keys:
                grouped_keys.extend(["Zone_Name"])
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'Region_Name' in filter_keys:
                grouped_keys.extend(["Region_Name"])
            if "month_name" not in filter_keys and 'fiscal_year' not in filter_keys and 'SalesArea_Name' in filter_keys:
                grouped_keys.extend(["SalesArea_Name"])
            
            if "month_name" in filter_keys and "SBU_Name" not in filter_keys:
                grouped_keys.append("SBU_Name")
            elif "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
                if "DS Lubes" in filters[-1].value[0] or 'DS' in filters[-1].value[0] or 'Lubes' in filters[-1].value[0]:
                    grouped_keys.extend(["SBU_Name", "Region_Name"])
                else:
                    grouped_keys.extend(["SBU_Name", "Zone_Name"])
            elif ("month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and
                  "Region_Name" not in filter_keys):
                grouped_keys.extend(["SBU_Name", "Zone_Name", "Region_Name"])
            elif ("month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys
                  and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys):
                grouped_keys.extend(["SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"])
            elif ("month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and
                  "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys):
                grouped_keys.extend(["SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name","MATERIALGROUPNAME"])
            grouped_resp = resp.groupby(grouped_keys, as_index=False).agg({
                "total_sales": lambda x: round(sum(x),2),
            })
            print("grouped_keys->>",grouped_keys)
            if grouped_resp is not None:
                if "sbu_name" in resp.columns.tolist():
                    sub_name = list(set(rec['SBU_Name'] for rec in grouped_resp.to_dict(orient='records')))
                transformed_data = []
                data = grouped_resp.to_dict(orient='records')
                print("data-->>",data)
                '''
                for sbu_name in sub_name:
                    entry = {
                        "month_name": "Jan",
                        "SBU_Name": sbu_name,
                        "2024-2025": next((item['total_sales'] for item in data if
                                           item['SBU_Name'] == sbu_name and item['fiscal_year'] == '2024-2025'), 0),
                        "2023-2024": next((item['total_sales'] for item in data if
                                           item['SBU_Name'] == sbu_name and item['fiscal_year'] == '2023-2024'), 0)
                    }
                    for key in ["Zone_Name", "Region_Name", "SalesArea_Name"]:
                        if key in grouped_keys:
                            if key in data[0]:
                            entry[key] = next((item[key] for item in data if item['SBU_Name'] == sbu_name), None)
                    
                    transformed_data.append(entry)
                return {"status": True, "message": "success", "data": transformed_data}
                '''
                # added the below lines from 685 to 696 for dorrect drill data from backend 
                '''
                for record in data:
                    entry = {
                        "month_name": record["month_name"],
                        "SBU_Name": record["SBU_Name"],
                        "2024-2025": record["total_sales"] if record["fiscal_year"] == "2024-2025" else 0,
                        "2023-2024": record["total_sales"] if record["fiscal_year"] == "2023-2024" else 0,
                        "fiscal_year": record["fiscal_year"]
                    }
                    for key in grouped_keys:
                        if key in record:
                            entry[key] = record[key]
                    transformed_data.append(entry)
                '''
                if "sbu_name" in resp.columns.tolist():
                    grouped_data = defaultdict(lambda: {'2023-2024': 0, '2024-2025': 0, 'month_name': '', 'SBU_Name': ''})
                else:
                    grouped_data = defaultdict(lambda: {'2023-2024': 0, '2024-2025': 0, 'month_name': ''})
                #grouped_keys =  ['fiscal_year', 'month_name', 'SBU_Name']
                key_fields = [key for key in grouped_keys if key != 'fiscal_year']  # Exclude 'fiscal_year'

                for record in data:
                    key = tuple(record[field] for field in key_fields)    
                    #key = (record['month_name'], record['SBU_Name'],record['Zone_Name'])
                    for field in key_fields:
                        grouped_data[key][field] = record.get(field, '')
                    grouped_data[key][record['fiscal_year']] = record['total_sales']
                result = list(grouped_data.values())
                return {"status": True, "message": "success", "data": result}

        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_operations_rejections(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        current_month = datetime.now().strftime("%Y-%m")
        current_month = current_month + "-01"

        cs_resp_ = lpg_plant_queries.lpg_plant_query.get("cs_query")
        pt_resp_ = lpg_plant_queries.lpg_plant_query.get("pt_query")
        gd_resp_ = lpg_plant_queries.lpg_plant_query.get("gd_query")

        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsRejections.get_clause_conditions(formated=True)]
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                if rec.key == '"rejection_type"':
                    rejection_filter = rec
                    continue
                if len(rec.value) == 1:
                    condition = f"{rec.key} = '{rec.value[0]}'"
                else:
                    condition = f"{rec.key} in {tuple(rec.value)}"
                conditions.append(condition)

            if conditions:
                cs_resp_ += ' WHERE ' + ' AND '.join(conditions)
                pt_resp_ += ' WHERE ' + ' AND '.join(conditions)
                gd_resp_ += ' WHERE ' + ' AND '.join(conditions)
                if "process_date" in conditions:
                    common_filter = f''' AND "zone" IS NOT NULL '''                    
                else:
                    common_filter = f''' AND CAST("process_date" AS DATE) >= '{current_month}' AND "zone" IS NOT NULL '''
            else:
                cs_resp_ += 'WHERE '
                pt_resp_ += ' WHERE '
                gd_resp_ += ' WHERE '
                common_filter = f''' CAST("process_date" AS DATE) >= '{current_month}' AND "zone" IS NOT NULL '''

            cs_resp_ += common_filter + ' GROUP BY "zone", "plant", "process_date","rejection_type"'
            pt_resp_ += common_filter + ' GROUP BY "zone", "plant", "process_date","rejection_type"'
            gd_resp_ += common_filter + ' GROUP BY "zone", "plant", "process_date","rejection_type"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgOperationsRejections.get_clause_conditions(formated=True)]
            cs_resp_ =  await widget_actions.WidgetActions.apply_filter_drilldown(cs_resp_, access_filters, drill_state)
            pt_resp_ =  await widget_actions.WidgetActions.apply_filter_drilldown(pt_resp_, access_filters, drill_state)
            gd_resp_ =  await widget_actions.WidgetActions.apply_filter_drilldown(gd_resp_, access_filters, drill_state)
            if not "where" in cs_resp_.lower():
                common_filter = f''' WHERE CAST("process_date" AS DATE) >= '{current_month}' AND "zone" IS NOT NULL '''
            else:
                common_filter = f''' AND CAST("process_date" AS DATE) >= '{current_month}' AND "zone" IS NOT NULL '''
            cs_resp_ += common_filter + ' GROUP BY "zone", "plant", "process_date"'
            pt_resp_ += common_filter + ' GROUP BY "zone", "plant", "process_date"'
            gd_resp_ += common_filter + ' GROUP BY "zone", "plant", "process_date"'

            cs_resp = await function(query=cs_resp_)
            pt_resp = await function(query=pt_resp_)
            gd_resp = await function(query=gd_resp_)

            cs_df = pd.DataFrame(cs_resp)
            pt_df = pd.DataFrame(pt_resp)
            gd_df = pd.DataFrame(gd_resp)
            combined_df = pd.concat([cs_df, pt_df, gd_df], ignore_index=True)
            combined_df = combined_df.groupby(["rejection_type"], as_index=False).agg({
                    "Rejections": "mean"
                })
            combined_df["Rejections"] = combined_df["Rejections"].round(1)

            combined_df["Rejections"] = combined_df["Rejections"].fillna(0.0)
            for each_str_col in ["zone", "plant", "rejection_type"]:
                if each_str_col in combined_df.columns:
                    combined_df[each_str_col] = combined_df[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": combined_df.to_dict(orient="records")}

        cs_resp = await function(query=cs_resp_)
        pt_resp = await function(query=pt_resp_)
        gd_resp = await function(query=gd_resp_)
        
        # Convert the responses to DataFrames
        cs_df = pd.DataFrame(cs_resp)
        pt_df = pd.DataFrame(pt_resp)
        gd_df = pd.DataFrame(gd_resp)

        # Combine DataFrames
        combined_df = pd.concat([cs_df, pt_df, gd_df], ignore_index=True)
        if rejection_filter:
            combined_df = combined_df[combined_df['rejection_type'] == rejection_filter.value[0]]
        # Fill missing values
        combined_df["Rejections"] = combined_df["Rejections"].fillna(0.0)
        for each_str_col in ["zone", "plant", "rejection_type"]:
            if each_str_col in combined_df.columns:
                combined_df[each_str_col] = combined_df[each_str_col].fillna('').astype(str)

        # Group data based on filters if required
        if filters:
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "rejection_type" in filter_keys and "zone" not in filter_keys:
                grouped_resp = combined_df.groupby(["rejection_type","zone"], as_index=False).agg({
                    "Rejections": "mean"
                })
            elif "rejection_type" in filter_keys and "zone"  in filter_keys and "plant" not in filter_keys:
                grouped_resp = combined_df.groupby(["rejection_type","zone", "plant"], as_index=False).agg({
                    "Rejections": "mean"
                })
            if grouped_resp is not None:
                grouped_resp["Rejections"] = grouped_resp["Rejections"].round(1)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        # Final response
        return {"status": True, "message": "success", "data": combined_df.to_dict(orient="records")}

    @staticmethod
    async def sales_drop_down(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        _query = ''' select * from alerts '''
        resp = await function(query=_query)
        df = pl.from_pandas(pd.DataFrame(resp))
        _filters = []
        if filters:
            for filter in filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if _filters:
            filter_expr = pl.lit(True)
            for _filter in _filters:
                for key, value in _filter.items():
                    key = key.replace('"', '')
                    filter_expr = filter_expr & (pl.col(key).fill_null("") == value)
            df = df.filter(filter_expr)
        df = df.filter(pl.col("zone").fill_null("") != "")
        df = df.filter(pl.col("region").fill_null("") != "")
        df = df.filter(pl.col("sales_area").fill_null("")!="")

        data = {"zone": df['zone'].unique().to_list(),
                "region": df['region'].unique().to_list(), "sales_area": df['sales_area'].unique().to_list()}
        return data

    @staticmethod
    async def present_previous_month_sales_by_product(filters, cross_filters, drill_state, limit, time_grain):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        present_month_sales = lpg_plant_queries.lpg_plant_query.get('i_previous_current_month_sales_by_product')
        cross_filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                          for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if cross_filters:
            conditions = [await addFilterValue(rec) for rec in cross_filters]
            # for rec in cross_filters:
            #     if ',' in rec.value:
            #         rec.value = rec.value.split(",")
            #     if len(rec.value) == 1:
            #         condition = f"a.{rec.key} = '{rec.value[0]}'"
            #     else:
            #         condition = f"a.{rec.key} in {tuple(rec.value)}"
            #     conditions.append(condition)
            if conditions:
                present_month_sales_query = present_month_sales.split("'Completed')")
                present_month_sales = present_month_sales_query[0] + "'Completed')" + ' AND ' + ' AND '.join(
                    conditions) + present_month_sales_query[1]
            # present_month_sales += f' {sort_by}'
            if limit:
                present_month_sales += f' LIMIT {limit}'
            print(present_month_sales)

        # else:
        #     access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
        #                       for rec in
        #                       await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        #     present_month_sales = await widget_actions.WidgetActions.apply_filter_drilldown(present_month_sales, access_filters, drill_state)
        #
        #     if limit:
        #         present_month_sales += f' LIMIT {limit}'

        pres_mon_sales_query = present_month_sales.format(time_grain=time_grain.lower())
        pres_mon_sales_resp = await function(query=pres_mon_sales_query)
        distinct_periods = list(set(item['period'] for item in pres_mon_sales_resp))
        print("distinct_periods--> ", distinct_periods)
        formatted_results = {}

        # Iterate over the response and group the data by product_name
        for row in pres_mon_sales_resp:
            product_name = row["product_name"]
            period = row["period"]
            avg_total_sales = row["avg_total_sales"]

            if product_name not in formatted_results:
                formatted_results[product_name] = {"product_name": product_name}

            # Add the period and its corresponding average sales value to the dictionary
            formatted_results[product_name][period] = avg_total_sales

        # Convert the dictionary to a list of results
        final_result = list(formatted_results.values())
        for res in final_result:
            for p_ in distinct_periods:
                res.setdefault(p_, 0)

        return {"status": True, "message": "success", "data": final_result}

    
    @staticmethod
    async def maintenance_fault(filters, cross_filters, drill_state):
        """
        This method is used to fetch the alert ageing data for the given filters and drill state
        :param filters: The filter parameters
        :param drill_state: The drill down state
        :return: A dictionary containing the status, message and the alert ageing data
        """
        alert_status = drill_state
        daterange = None

        if cross_filters:
            for filter in cross_filters:
                if "DATE" in filter.key:
                    daterange = f" '{filter.value.split(',')[0]}' AND '{filter.value.split(',')[-1]}' "
        
        if daterange:
            query = f""" 
                SELECT 
                    DATE(created_at) AS created_date,
                    alert_category,
                    COUNT(*) AS alert_count,
                    CASE 
                        WHEN interlock_name LIKE '%Under Maintenance%' THEN 'maintenance'
                        ELSE 'fault'
                    END AS interlock_status
                FROM alerts
                WHERE alert_section = 'TAS' 
                    AND created_at BETWEEN {daterange} 
                    AND alert_status = '{alert_status}'
                    AND alert_category IS NOT NULL
                GROUP BY created_date, alert_category, interlock_status
                ORDER BY created_date DESC, alert_count DESC;
            """
        else:
            query = f""" 
                SELECT 
                    DATE(created_at) AS created_date,
                    alert_category,
                    COUNT(*) AS alert_count,
                    CASE 
                        WHEN interlock_name LIKE '%Under Maintenance%' THEN 'maintenance'
                        ELSE 'fault'
                    END AS interlock_status
                FROM alerts
                WHERE alert_section = 'TAS' 
                    AND created_at::DATE >= CURRENT_DATE - INTERVAL '7 days' 
                    AND alert_status = '{alert_status}'
                    AND alert_category IS NOT NULL
                GROUP BY created_date, alert_category, interlock_status
                ORDER BY created_date DESC, alert_count DESC;
            """

        # Execute query
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        
        resp = await function(query=query)
        print("resp :", resp)
        resp = pl.DataFrame(resp)
        
        if resp.is_empty():
            return []

        result = {}

        # Process data and create category-specific keys
        for created_date in resp["created_date"].unique().to_list():
            filtered_resp = resp.filter(pl.col("created_date") == created_date)
            date_result = {}

            for category in filtered_resp["alert_category"].unique().to_list():
                category_resp = filtered_resp.filter(pl.col("alert_category") == category)
                
                for status in ["maintenance", "fault"]:
                    key = f"{category.lower()}_{status}"
                    date_result[key] = category_resp.filter(pl.col("interlock_status") == status)["alert_count"].sum()

            result[created_date] = date_result

        return result
    

    @staticmethod
    async def indent_dryout_counts(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        dryout_query = lpg_plant_queries.lpg_plant_query.get('i_dryout_ro_count')
        intraday_query = lpg_plant_queries.lpg_plant_query.get('i_intraday_dryout_ro_count')
        potential_query = lpg_plant_queries.lpg_plant_query.get('i_potential_dryout_ro_count')

        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                        for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
            conditions = [await addFilterValue(rec) for rec in filters]

            for rec in filters:
                if ',' in rec.value:
                    rec_values = rec.value.split(',')
                    rec_value_tup = tuple([i.strip() for i in rec_values])
                    condition = f''' "alerts_view"."{rec.key}" IN {rec_value_tup} '''
                else:
                    condition = f''' "alerts_view"."{rec.key}" = '{rec.value}' '''
                conditions.append(condition)
            dryout_query += ' AND '+' AND '.join(conditions)
            intraday_query += ' AND '+' AND '.join(conditions)
            potential_query += ' AND '+' AND '.join(conditions)
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                              for rec in
                              await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
            dryout_query = await widget_actions.WidgetActions.apply_filter_drilldown(
                dryout_query, access_filters, drill_state)

            intraday_query = await widget_actions.WidgetActions.apply_filter_drilldown(
                intraday_query, access_filters, drill_state)

            potential_query = await widget_actions.WidgetActions.apply_filter_drilldown(
                potential_query, access_filters, drill_state)

        print("dryout_resp: ", dryout_query)
        print("intraday_resp: ", intraday_query)
        print("potential_resp: ", potential_query)

        dryout_resp = await function(query=dryout_query)
        intraday_resp = await function(query=intraday_query)
        potential_resp = await function(query=potential_query)
        print("dryout_resp: ", dryout_resp)
        print("intraday_resp: ", intraday_resp)
        print("potential_resp: ", potential_resp)

        return {"status": True, "message": "success", "data": [
            {
                "dryout_count": dryout_resp[0]['total_count'] or 0,
                "intraday_count": intraday_resp[0]['total_count'] or 0,
                "potential_count": potential_resp[0]['total_count'] or 0
            }
        ]}

    @staticmethod
    async def indent_status_summary(filters, cross_filters, drill_state):
        """
        Args:
            filters:
            cross_filters:
            drill_state:

        Returns:
            [
                {
                    "indent_status": "status of the indent",
                    "dryout_status": "total_ro"
                }
            ]
        """

        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        indent_status_query = lpg_plant_queries.lpg_plant_query.get('i_indent_status_summary')

        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                        for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
            indent_status_query = await widget_actions.WidgetActions.apply_filter_drilldown(
                indent_status_query, filters, drill_state)

        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                              for rec in
                              await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
            indent_status_query = await widget_actions.WidgetActions.apply_filter_drilldown(
                indent_status_query, access_filters, drill_state)
        print("indent_status_query: ", indent_status_query)
        indent_status_resp = await function(query=indent_status_query)
        transformed_response = [
            {
                'indent_status': item['indent_status'],
                item['dryout_status']: item['total_ro']
            }
            for item in indent_status_resp
        ]
        print(transformed_response)
        return {"status": True, "message": "success", "data": transformed_response}

    @staticmethod
    async def dryout_summary_by_product(filters, cross_filters, drill_state):
        """
        Args:
            filters:
            cross_filters:
            drill_state:

        Returns:
            [
                {
                    "indent_status": "status of the indent",
                    "dryout_status": "total_ro"
                }
            ]
        """

        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        dryout_by_prod_query = lpg_plant_queries.lpg_plant_query.get('i_dryout_summary_by_product')

        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                    for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            conditions = [await addFilterValue(rec) for rec in filters]

            splitted_query = dryout_by_prod_query.split("MainFlow')")
            dryout_by_prod_query = splitted_query[0] + "MainFlow') AND " + ' AND '.join(conditions) + splitted_query[1]


        # else:
        #     access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
        #                       for rec in
        #                       await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        #     dryout_by_prod_query = await widget_actions.WidgetActions.apply_filter_drilldown(
        #         dryout_by_prod_query, access_filters, drill_state)
        print("dryout_by_prod_query: ", dryout_by_prod_query)
        dryout_by_prod_resp = await function(query=dryout_by_prod_query)
        # transformed_response = [
        #     {
        #         'product': item['product'],
        #         item['dryout_status']: item['total_ro']
        #     }
        #     for item in dryout_by_prod_resp
        # ]
        grouped_data = defaultdict(dict)

        for item in dryout_by_prod_resp:
            product = item['product']
            grouped_data[product]['product'] = product
            grouped_data[product][item['dryout_status']] = item['total_ro']

        transformed_response = list(grouped_data.values())
        print(transformed_response)
        return {"status": True, "message": "success", "data": transformed_response}

    @staticmethod
    async def detailed_dryout_summary(filters, cross_filters, drill_state):
        """
        Args:
            filters:
            cross_filters:
            drill_state:

        Returns:

        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        detailed_dryout_query = lpg_plant_queries.lpg_plant_query.get('i_detailed_dryout_summary')
        conditions = []
        display_col = f''' "View 1"."zone" as "zone" '''
        grp_col = f''' "View 1"."zone" '''
        col_ = 'zone'
        if cross_filters:
            col = cross_filters[-1].key
            print("col---> ", col)
            if col == 'zone':
                display_col = f''' "View 1"."region" as "region" '''
                grp_col = f''' "View 1"."region" '''
                col_ = 'region'
            elif col == 'region':
                display_col = f''' "View 1"."sales_area" as "sales_area" '''
                grp_col = f''' "View 1"."sales_area" '''
                col_ = 'sales_area'
            elif col == 'sales_area':
                display_col = f''' "View 1"."location_name" as "location_name" '''
                grp_col = f''' "View 1"."location_name" '''
                col_ = 'location_name'
            conditions.extend([await addFilterValue(cr_filter) for cr_filter in cross_filters])

        detailed_dryout_query = detailed_dryout_query.format(display_col=display_col, grp_col= grp_col)

        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                    for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            conditions.extend([await addFilterValue(rec) for rec in filters])
        if conditions:
            splitted_query = detailed_dryout_query.split("MainFlow')")
            detailed_dryout_query = splitted_query[0] + "MainFlow') AND " + ' AND '.join(conditions) + splitted_query[1]

        print("detailed_dryout_query: ", detailed_dryout_query)
        detailed_dryout_resp = await function(query=detailed_dryout_query)
        print("col_ value:", col_)
        # transformed_response = [
        #     {
        #         col_: item[col_],
        #         item['dryout_status']: item['total_ro']
        #     }
        #     for item in detailed_dryout_resp
        # ]
        grouped_data = defaultdict(dict)

        for item in detailed_dryout_resp:
            product = item[col_]
            grouped_data[product][col_] = product
            grouped_data[product][item['dryout_status']] = item['total_ro']

        transformed_response = list(grouped_data.values())
        print(transformed_response)
        return {"status": True, "message": "success", "data": transformed_response}

    @staticmethod
    async def detailed_indent_status_summary(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        detailed_indent_status_query = lpg_plant_queries.lpg_plant_query.get('i_detailed_indent_status_summary')

        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                    for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            conditions = []
            for rec in filters:
                condition = f"{rec.key} = '{rec.value}' "
                conditions.append(condition)

            splitted_query = detailed_indent_status_query.split("MainFlow')")
            detailed_indent_status_query = splitted_query[0] + "MainFlow') AND " + ' AND '.join(conditions) + splitted_query[1]

        print("detailed_indent_status_query: ", detailed_indent_status_query)
        detailed_indent_status_resp = await function(query=detailed_indent_status_query)
        transformed_response = [
            {
                'zone': item['zone'],
                'region': item['region'],
                'sales_area': item['sales_area'],
                'product_name': item['product_name'],
                item['indent_status']: item['total_ro']
            }
            for item in detailed_indent_status_resp
        ]
        print(transformed_response)
        return {"status": True, "message": "success", "data": transformed_response}

    @staticmethod
    async def dryout_product_report(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        detailed_indent_status_query = lpg_plant_queries.lpg_plant_query.get('i_product_report')

        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                    for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            conditions = []
            for rec in filters:
                condition = f"{rec.key} = '{rec.value}' "
                conditions.append(condition)

            splitted_query = detailed_indent_status_query.split("MainFlow'")
            detailed_indent_status_query = splitted_query[0] + "MainFlow' AND " + ' AND '.join(conditions) + \
                                           splitted_query[1]

        print("detailed_indent_status_query: ", detailed_indent_status_query)
        detailed_indent_status_resp = await function(query=detailed_indent_status_query)
        df = pd.DataFrame(detailed_indent_status_resp)
        return {"status": True, "message": "success", "data": df.to_dict(orient='records')}

    @staticmethod
    async def dryout_indent_report(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        detailed_indent_status_query = lpg_plant_queries.lpg_plant_query.get('i_indent_report')
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                    for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            conditions = []
            for rec in filters:
                condition = f"{rec.key} = '{rec.value}' "
                conditions.append(condition)

            splitted_query = detailed_indent_status_query.split("MainFlow'")
            detailed_indent_status_query = splitted_query[0] + "MainFlow' AND " + ' AND '.join(conditions) + \
                                           splitted_query[1]

        print("detailed_indent_status_query: ", detailed_indent_status_query)
        detailed_indent_status_resp = await function(query=detailed_indent_status_query)
        df = pd.DataFrame(detailed_indent_status_resp)
        return {"status": True, "message": "success", "data": df.to_dict(orient='records')}

    @staticmethod
    async def product_quantity_by_location(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        prod_qty_query = lpg_plant_queries.lpg_plant_query.get('i_product_wise_quantity_by_location')
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                    for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            conditions = [await addFilterValue(rec) for rec in filters]
            splitted_query = prod_qty_query.split("MainFlow'")
            prod_qty_query = splitted_query[0] + "MainFlow' AND " + ' AND '.join(conditions) + splitted_query[1]

        print("prod_qty_query: ", prod_qty_query)
        prod_qty_resp = await function(query=prod_qty_query)
        df = pl.DataFrame(prod_qty_resp)
        if not df.is_empty():
            result = df.pivot(
                values="Quantity",
                index="Location Name",
                columns="Product Name"
            )
            return {"status": True, "message": "success", "data": result.to_dicts()}
        return {"status": False, "message": "No data", "data": []}

    @staticmethod
    async def ims_report(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        ims_report_query = lpg_plant_queries.lpg_plant_query.get('i_ims_report')
        filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                    for rec in await hpcl_ceg_model.Alerts.get_clause_conditions(formated=True)]
        if filters:
            conditions = []
            for rec in filters:
                condition = f"{rec.key} = '{rec.value}' "
                conditions.append(condition)

            splitted_query = ims_report_query.split("MainFlow'")
            ims_report_query = splitted_query[0] + "MainFlow' AND " + ' AND '.join(conditions) + splitted_query[1]

        print("ims_report_query: ", ims_report_query)
        ims_report_resp = await function(query=ims_report_query)
        df = pl.DataFrame(ims_report_resp)
        if not df.is_empty():
            return {"status": True, "message": "success", "data": df.to_dicts()}
        return {"status": False, "message": "No data", "data": []}
    
    @staticmethod
    async def operations_dropdown(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        _query = ''' select * from lpg_operations_masters '''
        resp = await function(query=_query)
        df = pl.from_pandas(pd.DataFrame(resp))
        _filters = []
        if filters:
            for filter in filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if _filters:
            filter_expr = pl.lit(True)
            for _filter in _filters:
                for key, value in _filter.items():
                    key = key.replace('"','')
                    filter_expr = filter_expr & (pl.col(key).fill_null("") == value)
            df = df.filter(filter_expr)
        months = [month for month in calendar.month_name if month]
        data = {"zone": df["zone"].unique().to_list(), "plant": df["SiteArea"].unique().to_list(),
                "carousel_type": ["12H", "24H", "48H", "72H"]}
        return data


    @staticmethod
    async def interlock_name_count(filters, cross_filters, drill_state):
        """
        This method is used to fetch the alert ageing data for the given filters and drill state
        :param filters: The filter parameters
        :param drill_state: The drill down state
        :return: A dictionary containing the status, message and the alert ageing data
        """
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)

            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            bcu_number = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
                    if "bcu_number" in filter.key:
                        bcu_number = filter.value
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None

            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True

            normal_interlocks = {item["interlock_name"]: {"alert_category": item["alert_category"],
                                "equipment_name": item.get("equipment_name", item["interlock_name"])}
                                for item in category_mapping.Normal}
            # Construct base SQL Query
            query = f"""
                SELECT
                    DATE(created_at) AS created_date,
                    sap_id,
                    zone,
                    interlock_name,
                    location_name,
                    device_name,
                    COUNT(*) AS alert_count
                FROM alerts
                WHERE bu = 'TAS' AND alert_section = 'TAS'
            """

            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"

            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"

            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN ('{start_date.strftime('%Y-%m-%d')}') AND ('{end_date.strftime('%Y-%m-%d')}')"

            
            # Complete the query
            query += """
                GROUP BY created_date, zone, interlock_name, sap_id, location_name, device_name
                ORDER BY created_date DESC, alert_count DESC;
            """

            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))
            resp_df = resp_df.filter(pl.col("interlock_name").is_in(list(normal_interlocks.keys())))

            # Filter for interlocks where equipment_name is "Loading Point" AND alert_category is "Gantry"
            filtered_interlocks = [
                interlock_name for interlock_name, details in normal_interlocks.items()
                if (details.get("equipment_name") == "Loading Point" and
                    details.get("alert_category") == "Gantry")
            ]

            # Filter to keep only the interlocks that match both criteria
            resp_df = resp_df.filter(pl.col("interlock_name").is_in(filtered_interlocks))

            # Add the alert_category and alert_type columns
            resp_df = resp_df.with_columns([
                pl.col("interlock_name").map_elements(
                    lambda name: normal_interlocks.get(name)["alert_category"]
                ).alias("alert_category"),
                pl.lit("Normal").alias("alert_type")
            ])
            resp_df = resp_df.filter(pl.col("alert_category").is_not_null())
            # Extract the middle part of device_name
            def extract_middle_part(device_name):
                if isinstance(device_name, str) and '_' in device_name and '-' in device_name:
                    try:
                        # Split by _ and get the second part
                        second_part = device_name.split('_')[1]
                        # Get the first two parts of the split by -
                        parts = second_part.split('-')
                        if len(parts) >= 2:
                            return f"{parts[0]}-{parts[1]}"
                    except:
                        pass
                return ""

            # Apply the function using map_elements
            resp_df = resp_df.with_columns([
                pl.col("device_name").map_elements(lambda x: extract_middle_part(x)).alias("device_name")
            ])
            resp_df.write_csv("/tmp/normal_alerts_data.csv")

            # Apply date filtering at DataFrame level if not already applied in SQL
            if date and not date_filter_applied:
                # If 'date' is true but no date filter applied, filter last 30 days
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            if bcu_number:
                resp_df = resp_df.filter(pl.col("device_name") == bcu_number)
            # Handle daily data
            if date:
                # Determine grouping level based on filters
                if zone_filter or plant_filter:
                    # Group by zone/plant level if those filters are present
                    group_cols = ["sap_id", "zone", "location_name", "interlock_name", "created_date", "alert_category", "alert_type", "device_name"]

                    grouped = resp_df.group_by(group_cols).agg(
                        pl.sum("alert_count").alias("total")
                    )
                else:
                    # Group by interlock level (default) without sap_id and location_name
                    grouped = resp_df.group_by(["sap_id", "zone", "location_name", "interlock_name", "created_date", "alert_category", "alert_type", "device_name"]).agg(
                        pl.sum("alert_count").alias("total")
                    )

                result = {}
                total_alert_count = grouped.select(pl.sum("total")).item()
                for row in grouped.iter_rows(named=True):
                    category = row["alert_category"].lower()

                    result.setdefault(category, {}).setdefault(str(row["created_date"]), {}).setdefault(row["alert_type"], {
                        "details": [],
                        "total": 0
                    })

                    detail_item = {}

                    if zone_filter or plant_filter:
                        # For zone or plant filters, include sap_id and other details
                        if "zone" in row:
                            detail_item["zone"] = row["zone"]

                        if "location_name" in row:
                            detail_item["location_name"] = row["location_name"]

                        if "sap_id" in row:
                            detail_item["sap_id"] = row["sap_id"]

                        if "interlock_name" in row:
                            detail_item["interlock_name"] = row["interlock_name"]

                        if "device_name" in row:
                            detail_item["bcu_number"] = row["device_name"]
                    else:
                        if "sap_id" in row:
                            detail_item["sap_id"] = row["sap_id"]

                        if "zone" in row:
                            detail_item["zone"] = row["zone"]

                        if "location_name" in row:
                            detail_item["location_name"] = row["location_name"]

                        if "device_name" in row:
                            detail_item["bcu_number"] = row["device_name"]
                        # For interlock level, only include the interlock name
                        detail_item["interlock_name"] = row["interlock_name"]
                                                
                    detail_item["count"] = row["total"]
                    result[category][str(row["created_date"])][row["alert_type"]]["details"].append(detail_item)
                    # Update total count for this category, date, and alert_type
                    result[category][str(row["created_date"])][row["alert_type"]]["total"] += row["total"]
                return {"status": True, "message": "success", "daily_data": result}

            else:
                # Monthly aggregation
                resp_df = resp_df.with_columns(pl.col("created_date").dt.strftime("%b-%Y").alias("month_year"))

                # Determine grouping level based on filters
                if zone_filter or plant_filter:
                    # Group by zone/plant level if those filters are present
                    group_cols = ["sap_id", "zone", "location_name", "interlock_name", "month_year", "alert_category", "alert_type", "device_name"]

                    grouped = resp_df.group_by(group_cols).agg(
                        pl.sum("alert_count").alias("total")
                    )
                else:
                    # Group by interlock level (default) without sap_id and location_name
                    grouped = resp_df.group_by(["sap_id", "zone", "location_name", "interlock_name", "month_year", "alert_category", "alert_type", "device_name"]).agg(
                        pl.sum("alert_count").alias("total")
                    )

                result = {}
                total_alert_count = grouped.select(pl.sum("total")).item()
                for row in grouped.iter_rows(named=True):
                    category = row["alert_category"].lower()

                    result.setdefault(category, {}).setdefault(row["month_year"], {}).setdefault(row["alert_type"], {
                        "details": [],
                        "total": 0
                    })


                    detail_item = {}

                    if zone_filter or plant_filter:
                        # For zone or plant filters, include sap_id and other details
                        if "zone" in row:
                            detail_item["zone"] = row["zone"]

                        if "location_name" in row:
                            detail_item["location_name"] = row["location_name"]

                        if "sap_id" in row:
                            detail_item["sap_id"] = row["sap_id"]

                        if "sop_id" in row:
                            detail_item["sop_id"] = row["sop_id"]

                        if "interlock_name" in row:
                            detail_item["interlock_name"] = row["interlock_name"]

                        if "device_name" in row:
                            detail_item["bcu_number"] = row["device_name"]
                    else:
                        if "sap_id" in row:
                            detail_item["sap_id"] = row["sap_id"]

                        if "zone" in row:
                            detail_item["zone"] = row["zone"]

                        if "location_name" in row:
                            detail_item["location_name"] = row["location_name"]

                        if "device_name" in row:
                            detail_item["bcu_number"] = row["device_name"]
                        # For interlock level, only include the interlock name
                        detail_item["interlock_name"] = row["interlock_name"]

                    detail_item["count"] = row["total"]
                    result[category][row["month_year"]][row["alert_type"]]["details"].append(detail_item)
                    # Update total count for this category, date, and alert_type
                    result[category][row["month_year"]][row["alert_type"]]["total"] += row["total"]
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            print(e)

    
    @staticmethod
    async def tas_maintenance_fault(filters, cross_filters, drill_state):
        """
        Asynchronously retrieves and processes alert data for TAS maintenance and fault interlocks based on provided filters.

        This function constructs and executes a SQL query to fetch alert data from a database. It filters the data
        based on zone, plant, and date filters specified in the input parameters. The results are then processed
        to aggregate either daily or monthly data, which is returned as a structured dictionary.

        Parameters:
        - filters (list): A list of filters to apply, typically including zone and plant filters.
        - cross_filters (list): A list of additional filters, primarily used for date filtering.
        - drill_state (dict): A dictionary indicating the state of the data drill-down, specifically if date-based
        data aggregation is required.

        Returns:
        - dict: A dictionary with the status of the operation, a message, and the aggregated alert data structured
        as either daily or monthly data, depending on the drill_state.

        Raises:
        - Exception: If there is an error during query execution or data processing, an exception is caught and
        returned within the result dictionary.
        """
        try:
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)

            # Lookup dictionaries for interlock categories - modified to map to equipment_name instead of interlock_name
            maintenance_interlocks = {item["interlock_name"]: {"alert_category": item["alert_category"], "equipment_name": item.get("equipment_name", item["interlock_name"])} for item in category_mapping.Maintenance}
            fault_interlocks = {item["interlock_name"]: {"alert_category": item["alert_category"], "equipment_name": item.get("equipment_name", item["interlock_name"])} for item in category_mapping.Fault}
            # normal_interlocks = {item["interlock_name"]: {"alert_category": item["alert_category"], "equipment_name": item.get("equipment_name", item["interlock_name"])} for item in category_mapping.Normal}

            # Default date range: last 1 year
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            date_filter_applied = False  # Ensure this is initialized

            zone_filter = ''
            plant_filter = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value

            # Handle cross_filters for date range
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True

            # Apply date range filter
            date_condition = f"AND created_at BETWEEN '{start_date.date()}' AND '{end_date.date()}'" if date_filter_applied else ""
            # Construct SQL Query
            query = f"""
                SELECT
                    DATE(created_at) AS created_date,
                    sap_id,
                    zone,
                    interlock_name,
                    location_name,
                    COUNT(*) AS alert_count
                FROM alerts
                WHERE bu = 'TAS' AND alert_section = 'TAS'
                {date_condition}
            """

            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"

            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"

            # Complete the query
            query += """
                GROUP BY created_date, zone, interlock_name, sap_id, location_name
                ORDER BY created_date DESC, alert_count DESC;
            """

            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))
            print("resp_df", resp_df)
            # Add alert_type and alert_category columns
            matches = pl.col("interlock_name").is_in(
                    list(maintenance_interlocks.keys()) + 
                    list(fault_interlocks.keys()) 
                    #+ list(normal_interlocks.keys())
            )

            resp_df = resp_df.filter(matches)
            
            # Modified to use equipment_name instead of interlock_name
            resp_df = resp_df.with_columns([
                pl.col("interlock_name").map_elements(
                    lambda name: maintenance_interlocks.get(name, fault_interlocks.get(name, {})).get("alert_category")
                ).alias("alert_category"),
                
                # Changed to always return "Equipment" instead of "Maintenance" or "Fault"
                pl.lit("Equipment").alias("alert_type"),
                
                # Add equipment_name column
                pl.col("interlock_name").map_elements(
                    lambda name: maintenance_interlocks.get(name, fault_interlocks.get(name, {})).get("equipment_name", name)
                ).alias("equipment_name")
            ])
            
            resp_df = resp_df.filter(pl.col("alert_category").is_not_null())
            resp_df.write_csv("/tmp/analog_data.csv")

            # Apply date filtering at DataFrame level if not already applied in SQL
            if date and not date_filter_applied:
                # If 'date' is true but no date filter applied, filter last 30 days
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            result = {}
            if not date:
                resp_df = resp_df.with_columns(pl.col("created_date").dt.strftime("%b-%Y").alias("month_year"))
                # Determine grouping level based on filters
                if zone_filter or plant_filter:
                    # Group by zone/plant level if those filters are present
                    group_cols = ["sap_id", "zone", "location_name", "equipment_name", "month_year", "alert_category", "alert_type"]  # Use equipment_name instead of interlock_name
                    
                    # if zone_filter:
                    #     group_cols.append("zone")
                    
                    # if plant_filter:
                    #     group_cols.append("location_name")
                    
                    # if zone_filter or plant_filter:
                    #     group_cols.extend(["sap_id"])
                        
                    grouped = resp_df.group_by(group_cols).agg(
                        pl.sum("alert_count").alias("total")
                    )
                else:
                    # Group by equipment level (default) without sap_id and location_name
                    grouped = resp_df.group_by(["sap_id", "zone", "location_name", "equipment_name", "month_year", "alert_category", "alert_type"]).agg(  # Use equipment_name instead of interlock_name
                        pl.sum("alert_count").alias("total")
                    )

                for row in grouped.iter_rows(named=True):
                    category = row["alert_category"].lower()
                    # if category == "gantry":
                    #     category = "process"

                    result.setdefault(category, {}).setdefault(row["month_year"], {}).setdefault(row["alert_type"], {
                        "total": 0,
                        "details": []
                    })

                    detail_item = {}
                    
                    if zone_filter or plant_filter:
                        # For zone or plant filters, include sap_id and other details
                        if "zone" in row:
                            detail_item["zone"] = row["zone"]
                        
                        if "location_name" in row:
                            detail_item["location_name"] = row["location_name"]
                        
                        if "sap_id" in row:
                            detail_item["sap_id"] = row["sap_id"]
                        
                        # Use equipment_name instead of interlock_name
                        if "equipment_name" in row:
                            detail_item["equipment_name"] = row["equipment_name"]
                    else:
                        if "sap_id" in row:
                            detail_item["sap_id"] = row["sap_id"]
                        
                        if "zone" in row:
                            detail_item["zone"] = row["zone"]
                        
                        if "location_name" in row:
                            detail_item["location_name"] = row["location_name"]
                        # Use equipment_name instead of interlock_name
                        detail_item["equipment_name"] = row["equipment_name"]
                    
                    detail_item["count"] = row["total"]
                    result[category][row["month_year"]][row["alert_type"]]["total"] += row["total"]
                    result[category][row["month_year"]][row["alert_type"]]["details"].append(detail_item)
                
                return {"status": True, "message": "success", "monthly_data": result}
            else:
                # Determine grouping level based on filters
                if zone_filter or plant_filter:
                    # Group by zone/plant level if those filters are present
                    group_cols = ["sap_id", "zone", "location_name", "equipment_name", "created_date", "alert_category", "alert_type"]  # Use equipment_name instead of interlock_name
                    
                    # if zone_filter:
                    #     group_cols.append("zone")
                    
                    # if plant_filter:
                    #     group_cols.append("location_name")
                    
                    # if zone_filter or plant_filter:
                    #     group_cols.extend(["sap_id"])
                        
                    grouped = resp_df.group_by(group_cols).agg(
                        pl.sum("alert_count").alias("total")
                    )
                else:
                    # Group by equipment level (default) without sap_id and location_name
                    grouped = resp_df.group_by(["sap_id", "zone", "location_name", "equipment_name", "created_date", "alert_category", "alert_type"]).agg(  # Use equipment_name instead of interlock_name
                        pl.sum("alert_count").alias("total")
                    )

                result = {}
                for row in grouped.iter_rows(named=True):
                    category = row["alert_category"].lower()
                    # if category == "gantry":
                    #     category = "process"

                    result.setdefault(category, {}).setdefault(str(row["created_date"]), {}).setdefault(row["alert_type"], {
                        "total": 0,
                        "details": []
                    })

                    detail_item = {}
                    
                    if zone_filter or plant_filter:
                        # For zone or plant filters, include sap_id and other details
                        if "zone" in row:
                            detail_item["zone"] = row["zone"]
                        
                        if "location_name" in row:
                            detail_item["location_name"] = row["location_name"]
                        
                        if "sap_id" in row:
                            detail_item["sap_id"] = row["sap_id"]
                        
                        # Use equipment_name instead of interlock_name
                        if "equipment_name" in row:
                            detail_item["equipment_name"] = row["equipment_name"]
                    else:
                        if "sap_id" in row:
                            detail_item["sap_id"] = row["sap_id"]
                        
                        if "zone" in row:
                            detail_item["zone"] = row["zone"]
                        
                        if "location_name" in row:
                            detail_item["location_name"] = row["location_name"]
                        # Use equipment_name instead of interlock_name
                        detail_item["equipment_name"] = row["equipment_name"]
                        
                    detail_item["count"] = row["total"]
                    result[category][str(row["created_date"])][row["alert_type"]]["total"] += row["total"]
                    result[category][str(row["created_date"])][row["alert_type"]]["details"].append(detail_item)

                return {"status": True, "message": "success", "daily_data": result}
        except Exception as e:
            print(traceback.format_exc())
    
    @staticmethod
    async def tas_maintenance_fault_dropdown(filters, cross_filters, drill_state):
        """
        Asynchronously retrieves and filters data from the location master for TAS maintenance and fault dropdowns.

        This function constructs and executes a SQL query to fetch location data from a database. 
        It filters the data based on the provided filters and returns a list of unique zones 
        and plant names for use in dropdown menus.

        Parameters:
        - filters (list): A list of filters to apply, typically including zone and plant filters.
        - cross_filters (list): A list of additional filters, although not utilized in this function.
        - drill_state (dict): A dictionary indicating the state of the data drill-down, not used in this function.

        Returns:
        - dict: A dictionary containing the status, a success message, and the filtered data 
        including unique zones and plant names.

        Raises:
        - Exception: If there is an error during query execution, the function will raise an exception 
        which should be handled by the caller.
        """
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        _query = ''' select * from location_master where bu = 'TAS' '''
        resp = await function(query=_query)
        df = pl.from_pandas(pd.DataFrame(resp))
        _filters = []
        if filters:
            for filter in filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if _filters:
            filter_expr = pl.lit(True)
            for _filter in _filters:
                for key, value in _filter.items():
                    key = key.replace('"','')
                    filter_expr = filter_expr & (pl.col(key).fill_null("") == value)
            df = df.filter(filter_expr)
        months = [month for month in calendar.month_name if month]
        data = {"zone": df["zone"].unique().to_list(), "plant": df["name"].unique().to_list()}
        return {"status": True, "message": "Success","data": data}
    
    @staticmethod
    async def tas_normal_count(filters, cross_filters, drill_state):
        """
        Asynchronously retrieves and processes alert data for TAS normal interlocks, based on provided filters.

        This function constructs and executes a SQL query to fetch alert data from a database. 
        It filters the data based on zone, plant, and date filters specified in the input parameters. 
        The results are then processed to either aggregate daily or monthly data, which is returned 
        as a structured dictionary.

        Parameters:
        - filters (list): A list of filters to apply, typically including zone and plant filters.
        - cross_filters (list): A list of additional filters, primarily used for date filtering.
        - drill_state (dict): A dictionary indicating the state of the data drill-down, 
        specifically if date-based data aggregation is required.

        Returns:
        - dict: A dictionary with the status of the operation, a message, and the aggregated alert data 
        structured as either daily or monthly data, depending on the drill_state.

        Raises:
        - Exception: If there is an error during query execution or data processing, an exception is caught 
        and returned within the result dictionary.
        """
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)
            
            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None
            
            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True
            
            # Modified to store equipment_name alongside alert_category
            normal_interlocks = {item["interlock_name"]: {"alert_category": item["alert_category"], "equipment_name": item.get("equipment_name", item["interlock_name"])} for item in category_mapping.Normal}
            
            # Construct base SQL Query
            query = f"""
                SELECT
                    DATE(created_at) AS created_date,
                    sap_id,
                    zone,
                    interlock_name,
                    location_name,
                    COUNT(*) AS alert_count
                FROM alerts
                WHERE bu = 'TAS' AND alert_section = 'TAS'
            """
            
            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            
            # Add plant/location filter if present
            if plant_filter:
                query += f" AND location_name IN ('{plant_filter}')"
            
            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN ('{start_date.strftime('%Y-%m-%d')}') AND ('{end_date.strftime('%Y-%m-%d')}')"
            
            # Complete the query
            query += """
                GROUP BY created_date, zone, interlock_name, sap_id, location_name
                ORDER BY created_date DESC, alert_count DESC;
            """

            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                return {"status": True, "data": {}}
            
            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))
            resp_df = resp_df.filter(pl.col("interlock_name").is_in(list(normal_interlocks.keys())))
            
            # Modified to add both alert_category and equipment_name
            resp_df = resp_df.with_columns([
                pl.col("interlock_name").map_elements(lambda name: normal_interlocks.get(name, {}).get("alert_category")).alias("alert_category"),
                pl.lit("Normal").alias("alert_type"),  # Since we're only keeping "normal" interlocks
                # Add equipment_name column
                pl.col("interlock_name").map_elements(lambda name: normal_interlocks.get(name, {}).get("equipment_name", name)).alias("equipment_name")
            ])
            
            resp_df = resp_df.filter(pl.col("alert_category").is_not_null())
            resp_df.write_csv("/tmp/normal_alerts_data.csv")

            # Apply date filtering at DataFrame level if not already applied in SQL
            if date and not date_filter_applied:
                # If 'date' is true but no date filter applied, filter last 30 days
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())
            
            # Handle daily data
            if date:
                # Determine grouping level based on filters
                if zone_filter or plant_filter:
                    # Group by zone/plant level if those filters are present
                    group_cols = ["sap_id", "zone", "location_name", "equipment_name", "created_date", "alert_category", "alert_type"]
                    
                    # if zone_filter:
                    #     group_cols.append("zone")
                    
                    # if plant_filter:
                    #     group_cols.append("location_name")
                    
                    # if zone_filter or plant_filter:
                    #     group_cols.extend(["sap_id"])
                        
                    grouped = resp_df.group_by(group_cols).agg(
                        pl.sum("alert_count").alias("total")
                    )
                else:
                    # Group by equipment level (default)
                    grouped = resp_df.group_by(["sap_id", "zone", "location_name", "equipment_name", "created_date", "alert_category", "alert_type"]).agg(
                        pl.sum("alert_count").alias("total")
                    )

                # NEW RESPONSE FORMAT FOR DAILY DATA
                result = {}
                for row in grouped.iter_rows(named=True):
                    # Get the equipment name
                    equipment_name = row["equipment_name"] if row["equipment_name"] else "Unknown"
                    
                    # Initialize the equipment entry if it doesn't exist
                    if equipment_name not in result:
                        result[equipment_name] = []
                    
                    # Create a detail item with all the relevant fields
                    detail_item = {
                        "date": str(row["created_date"]),
                        "alert_category": row["alert_category"],
                        "alert_type": row["alert_type"],
                        "count": row["total"]
                    }
                    
                    # Add optional fields if they exist in the row
                    if "zone" in row:
                        detail_item["zone"] = row["zone"]
                    if "location_name" in row:
                        detail_item["location_name"] = row["location_name"]
                    if "sap_id" in row:
                        detail_item["sap_id"] = row["sap_id"]
                    
                    # Add the detail item to the equipment's array
                    result[equipment_name].append(detail_item)

                return {"status": True, "message": "success", "daily_data": result}

            else:
                # Monthly aggregation
                resp_df = resp_df.with_columns(pl.col("created_date").dt.strftime("%b-%Y").alias("month_year"))
                
                # Determine grouping level based on filters
                if zone_filter or plant_filter:
                    # Group by zone/plant level if those filters are present
                    group_cols = ["sap_id", "zone", "location_name", "equipment_name", "month_year", "alert_category", "alert_type"]
                    
                    # if zone_filter:
                    #     group_cols.append("zone")
                    
                    # if plant_filter:
                    #     group_cols.append("location_name")
                    
                    # if zone_filter or plant_filter:
                    #     group_cols.extend(["sap_id"])
                        
                    grouped = resp_df.group_by(group_cols).agg(
                        pl.sum("alert_count").alias("total")
                    )
                else:
                    # Group by equipment level (default)
                    grouped = resp_df.group_by(["sap_id", "zone", "location_name", "equipment_name", "month_year", "alert_category", "alert_type"]).agg(
                        pl.sum("alert_count").alias("total")
                    )

                # NEW RESPONSE FORMAT FOR MONTHLY DATA
                result = {}
                for row in grouped.iter_rows(named=True):
                    # Get the equipment name
                    equipment_name = row["equipment_name"] if row["equipment_name"] else "Unknown"
                    
                    # Initialize the equipment entry if it doesn't exist
                    if equipment_name not in result:
                        result[equipment_name] = []
                    
                    # Create a detail item with all the relevant fields
                    detail_item = {
                        "month": row["month_year"],
                        "alert_category": row["alert_category"],
                        "alert_type": row["alert_type"],
                        "count": row["total"]
                    }
                    
                    # Add optional fields if they exist in the row
                    if "zone" in row:
                        detail_item["zone"] = row["zone"]
                    if "location_name" in row:
                        detail_item["location_name"] = row["location_name"]
                    if "sap_id" in row:
                        detail_item["sap_id"] = row["sap_id"]
                    
                    # Add the detail item to the equipment's array
                    result[equipment_name].append(detail_item)

                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            print(e)
            return {"status": False, "message": f"An error occurred: {str(e)}", "data": {}}

    @staticmethod
    async def tas_analog_count(filters, cross_filters, drill_state):        
        """
        Fetches TAS Analog alert count data.

        Args:
            filters (list): List of filters, each being a dictionary with keys "key" and "value".
            cross_filters (list): List of cross filters, each being a dictionary with keys "key" and "value".
            drill_state (dict): Dictionary containing the date filter state.

        Returns:
            dict: Dictionary containing the response status, message and data.
        """
        try:
            date = "date" in drill_state  # Check if date filtering is required
            print("date --> ", date)

            # Extract filters dynamically
            zone_filter, plant_filter, interlock_filter = '', '', ''
            for filter in (filters or []):
                if filter.key == "zone":
                    zone_filter = filter.value
                elif filter.key == "plant":
                    plant_filter = filter.value

            # Extract date and interlock filters
            date_filter_applied = False
            start_date, end_date = None, None
            for filter in (cross_filters or []):
                if filter.key == "DATE":
                    date_parts = filter.value.split(',')
                    start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                    end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                    date_filter_applied = True
                elif filter.key == "interlock_name":
                    interlock_filter = filter.value  # Assuming single or multiple values comma-separated

            # Base Query
            query = """
                SELECT DATE(created_at) AS created_date, interlock_name, sap_id, sop_id, COUNT(*) AS alert_count
            """

            # Conditionally include `zone` and `plant`
            if zone_filter:
                query += ", zone"
            if plant_filter:
                query += ", location_name AS plant"

            query += " FROM alerts WHERE bu = 'TAS' AND alert_section = 'TAS'"

            # Apply filters
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            if plant_filter:
                query += f" AND location_name IN ('{plant_filter}')"
            if interlock_filter:
                interlock_values = "','".join(interlock_filter.split(','))  # Handling multiple values
                query += f" AND interlock_name IN ('{interlock_values}')"
            if date_filter_applied:
                query += f" AND DATE(created_at) BETWEEN ('{start_date.strftime('%Y-%m-%d')}') AND ('{end_date.strftime('%Y-%m-%d')}')"

            # Group By clause
            query += " GROUP BY created_date, interlock_name, sap_id, sop_id"
            if zone_filter:
                query += ", zone"
            if plant_filter:
                query += ", location_name"

            query += " ORDER BY created_date DESC, alert_count DESC;"

            # Execute Query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))

            # Date filtering if not applied in SQL
            if date and not date_filter_applied:
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            # Columns for grouping
            group_cols = ["created_date", "interlock_name", "sap_id", "sop_id"]
            if zone_filter:
                group_cols.append("zone")
            if plant_filter:
                group_cols.append("plant")

            if date:
                # **Daily Data Aggregation**
                grouped = resp_df.group_by(group_cols).agg(pl.sum("alert_count").alias("total"))

                result = {}
                for row in grouped.iter_rows(named=True):
                    created_date = str(row["created_date"])
                    entry = {
                        "interlock_name": row["interlock_name"],
                        "sap_id": row["sap_id"],
                        "sop_id": row["sop_id"],
                        "total_alerts": row["total"]
                    }
                    if zone_filter:
                        entry["zone"] = row["zone"]
                    if plant_filter:
                        entry["plant"] = row["plant"]

                    result.setdefault(created_date, []).append(entry)

                # # Sort results
                # sorted_daily_data = {
                #     date: result[date] for date in sorted(
                #         result.keys(), key=lambda x: datetime.strptime(x, "%Y-%m-%d"), reverse=True
                #     )
                # }
                return {"status": True, "message": "success", "daily_data": result}

            else:
                # **Monthly Data Aggregation**
                resp_df = resp_df.with_columns(pl.col("created_date").dt.strftime("%b-%Y").alias("month_year"))

                grouped = resp_df.group_by(["month_year"] + group_cols[1:]).agg(pl.sum("alert_count").alias("total"))

                result = {}
                for row in grouped.iter_rows(named=True):
                    month = row["month_year"]
                    entry = {
                        "interlock_name": row["interlock_name"],
                        "sap_id": row["sap_id"],
                        "sop_id": row["sop_id"],
                        "total_alerts": row["total"]
                    }
                    if zone_filter:
                        entry["zone"] = row["zone"]
                    if plant_filter:
                        entry["plant"] = row["plant"]

                    result.setdefault(month, []).append(entry)

                # Sort results
                # sorted_monthly_data = {
                #     month: result[month] for month in sorted(
                #         result.keys(), key=lambda x: datetime.strptime(x, "%b-%Y"), reverse=True
                #     )
                # }
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {str(e)}", "data": {}}
    
    @staticmethod
    async def local_loaded(filters, cross_filters, drill_state):
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)
            
            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            bcu_number = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
                    if "bcu_number" in filter.key:
                        bcu_number = filter.value
            
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None
            
            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True
            
            # Construct base SQL Query with WHERE clause
            query = """
                WITH localloaded AS (
                    SELECT 
                        DATE(created_at) AS created_date,
                        zone,
                        location_name,
                        sap_id,
                        bcu_number,
                        SUM(loaded_qty) AS total_loaded_qty
                    FROM 
                        host_local_loaded_tts
                    WHERE 1=1
            """
            
            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            
            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"
            
            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'"
            
            # Complete the query with proper GROUP BY
            query += """
                    GROUP BY 
                        DATE(created_at), zone, location_name, sap_id, bcu_number
                )
                SELECT 
                    h.created_date,
                    h.zone,
                    h.location_name,
                    h.sap_id,
                    h.bcu_number,
                    (SELECT COUNT(*) 
                    FROM alerts a 
                    WHERE a.device_name = h.bcu_number 
                    AND a.interlock_name = 'BCU Local Loading'
                    AND DATE(a.created_at) = h.created_date) AS alert_count,
                    total_loaded_qty
                FROM 
                    localloaded h
                ORDER BY 
                    h.created_date DESC, alert_count DESC
            """
            
            print("query --> ", query)
            
            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                    return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))

            # Date filtering if not applied in SQL - default to last 30 days
            if not date_filter_applied:
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            if bcu_number:
                resp_df = resp_df.filter(pl.col("bcu_number") == bcu_number)
            # Generate appropriate result format based on date flag
            if date:
                # Daily Data Aggregation
                group_cols = ["created_date", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_loaded_qty").alias("total_loaded")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    created_date = str(row["created_date"])
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"],
                        "total_loaded_qty": row["total_loaded"]
                    }
                    result.setdefault(created_date, []).append(entry)
                return {"status": True, "message": "success", "daily_data": result}
            else:
                # Monthly Data Aggregation
                resp_df = resp_df.with_columns(
                    pl.col("created_date").dt.strftime("%Y-%m").alias("month_year")
                )

                group_cols = ["month_year", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_loaded_qty").alias("total_loaded")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    month = row["month_year"]
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"],
                        "total_loaded_qty": row["total_loaded"]
                    }
                    result.setdefault(month, []).append(entry)
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {str(e)}", "data": {}}

    @staticmethod
    async def unauthorised_flow(filters, cross_filters, drill_state):
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)
            
            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            bcu_number = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
                    if "bcu_number" in filter.key:
                        bcu_number = filter.value
            
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None
            
            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True
            
            # Construct base SQL Query with WHERE clause
            query = """
                WITH unauthorized AS (
                    SELECT 
                        DATE(created_at) AS created_date,
                        zone,
                        location_name,
                        sap_id,
                        bcu_number,
                        CAST(SUM(net_totalizer) AS FLOAT) AS total_net_totalizer
                    FROM 
                        host_unauthorised_flow
                    WHERE 1=1
            """

            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            
            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"
            
            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'"
            
            # Complete the query with proper GROUP BY
            query += """
                    GROUP BY 
                        DATE(created_at), zone, location_name, sap_id, bcu_number
                )
                SELECT 
                    h.created_date,
                    h.zone,
                    h.location_name,
                    h.sap_id,
                    h.bcu_number,
                    (SELECT COUNT(*) 
                    FROM alerts a 
                    WHERE a.device_name = h.bcu_number 
                    AND a.interlock_name = 'Unauthorized flow_BCU'
                    AND DATE(a.created_at) = h.created_date) AS alert_count,
                    total_net_totalizer
                FROM 
                    unauthorized h
                ORDER BY 
                    h.created_date DESC, alert_count DESC
            """
            
            print("query --> ", query)
            
            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                    return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))
            
            if bcu_number:
                resp_df = resp_df.filter(pl.col("bcu_number") == bcu_number)
            # Date filtering if not applied in SQL - default to last 30 days
            if not date_filter_applied:
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            # Generate appropriate result format based on date flag
            if date:
                # Daily Data Aggregation
                group_cols = ["created_date", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_net_totalizer").alias("total_nettotalizer")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    created_date = str(row["created_date"])
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"],
                        "total_net_totalizer": row["total_nettotalizer"]
                    }
                    result.setdefault(created_date, []).append(entry)
                return {"status": True, "message": "success", "daily_data": result}
            else:
                # Monthly Data Aggregation
                resp_df = resp_df.with_columns(
                    pl.col("created_date").dt.strftime("%Y-%m").alias("month_year")
                )

                group_cols = ["month_year", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_net_totalizer").alias("total_nettotalizer")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    month = row["month_year"]
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"],
                        "total_net_totalizer": row["total_nettotalizer"]
                    }
                    result.setdefault(month, []).append(entry)
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {str(e)}", "data": {}}
    
    @staticmethod
    async def sick_tts(filters, cross_filters, drill_state):
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)
            
            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            bcu_number = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
                    if "bcu_number" in filter.key:
                        bcu_number = filter.value
            
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None
            
            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True
            
            # Construct base SQL Query with WHERE clause
            query = """
                WITH sicktts AS (
                    SELECT 
                        DATE(created_at) AS created_date,
                        zone,
                        location_name,
                        sap_id,
                        bcu_number,
                        SUM(required_qty) AS total_required_qty,
                        SUM(loaded_qty) AS total_loaded_qty
                    FROM 
                        host_sick_tts
                    WHERE 1=1
            """
            
            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            
            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"
            
            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'"
            
            # Complete the query with proper GROUP BY
            query += """
                    GROUP BY 
                        DATE(created_at), zone, location_name, sap_id, bcu_number
                )
                SELECT 
                    h.created_date,
                    h.zone,
                    h.location_name,
                    h.sap_id,
                    h.bcu_number,
                    (SELECT COUNT(*) 
                    FROM alerts a 
                    WHERE a.device_name = h.bcu_number 
                    AND a.interlock_name = 'SickTT Reported'
                    AND DATE(a.created_at) = h.created_date) AS alert_count,
                    h.total_required_qty,
                    h.total_loaded_qty
                FROM 
                    sicktts h
                ORDER BY 
                    h.created_date DESC, alert_count DESC
            """
            
            print("query --> ", query)
            
            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                    return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))

            # Date filtering if not applied in SQL - default to last 30 days
            if not date_filter_applied:
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            if bcu_number:
                resp_df = resp_df.filter(pl.col("bcu_number") == bcu_number)
            # Generate appropriate result format based on date flag
            if date:
                # Daily Data Aggregation
                group_cols = ["created_date", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_required_qty").alias("total_required_quantity"),
                    pl.sum("total_loaded_qty").alias("total_loaded_quantity")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    created_date = str(row["created_date"])
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"],
                        "total_required_qty": row["total_required_quantity"],
                        "total_loaded_qty": row["total_loaded_quantity"]
                    }
                    result.setdefault(created_date, []).append(entry)
                return {"status": True, "message": "success", "daily_data": result}
            else:
                # Monthly Data Aggregation
                resp_df = resp_df.with_columns(
                    pl.col("created_date").dt.strftime("%Y-%m").alias("month_year")
                )

                group_cols = ["month_year", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_required_qty").alias("total_required_quantity"),
                    pl.sum("total_loaded_qty").alias("total_loaded_quantity")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    month = row["month_year"]
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"],
                        "total_required_qty": row["total_required_quantity"],
                        "total_loaded_qty": row["total_loaded_quantity"]
                    }
                    result.setdefault(month, []).append(entry)
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {str(e)}", "data": {}}
    
    @staticmethod
    async def cancelled_tts(filters, cross_filters, drill_state):
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)
            
            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            truck_number = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
                    if "truck_number" in filter.key:
                        truck_number = filter.value
            
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None
            
            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True
            
            # Construct base SQL Query with WHERE clause
            query = """
                WITH cancelled_tts AS (
                    SELECT 
                        DATE(created_at) AS created_date,
                        zone,
                        location_name,
                        sap_id,
                        truck_number,
                        SUM(required_qty) AS total_required_qty
                    FROM 
                        host_cancelled_tts
                    WHERE 1=1
            """
            
            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            
            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"
            
            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'"
            
            # Complete the query with proper GROUP BY
            query += """
                    GROUP BY 
                        DATE(created_at), zone, location_name, sap_id, truck_number
                )
                SELECT 
                    k.created_date,
                    k.zone,
                    k.location_name,
                    k.sap_id,
                    k.truck_number,
                    (SELECT COUNT(*) 
                    FROM alerts a 
                    WHERE a.vehicle_number = k.truck_number 
                    AND a.interlock_name = 'Cancel TT Reported'
                    AND DATE(a.created_at) = k.created_date) AS alert_count,
                    k.total_required_qty
                FROM 
                    cancelled_tts k
                ORDER BY 
                    k.created_date DESC, alert_count DESC
            """
            
            print("query --> ", query)
            
            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                    return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))

            # Date filtering if not applied in SQL - default to last 30 days
            if not date_filter_applied:
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            if truck_number:
                resp_df = resp_df.filter(pl.col("truck_number") == truck_number)
            # Generate appropriate result format based on date flag
            if date:
                # Daily Data Aggregation
                group_cols = ["created_date", "zone", "sap_id", "location_name", "truck_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_required_qty").alias("total_required_quantity")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    created_date = str(row["created_date"])
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "truck_number": row["truck_number"],
                        "total_alerts": row["total_alerts"],
                        "total_required_qty": row["total_required_quantity"]
                    }
                    result.setdefault(created_date, []).append(entry)
                return {"status": True, "message": "success", "daily_data": result}
            else:
                # Monthly Data Aggregation
                resp_df = resp_df.with_columns(
                    pl.col("created_date").dt.strftime("%Y-%m").alias("month_year")
                )

                group_cols = ["month_year", "zone", "sap_id", "location_name", "truck_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_required_qty").alias("total_required_quantity")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    month = row["month_year"]
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "truck_number": row["truck_number"],
                        "total_alerts": row["total_alerts"],
                        "total_required_qty": row["total_required_quantity"]
                    }
                    result.setdefault(month, []).append(entry)
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {str(e)}", "data": {}}
    
    @staticmethod
    async def kfactor(filters, cross_filters, drill_state):
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)
            
            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            bcu_number = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
                    if "bcu_number" in filter.key:
                        bcu_number = filter.value
            
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None
            
            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True
            
            # Construct base SQL Query with CTE for better performance
            query = """
                WITH k_factor_data AS (
                    SELECT 
                        DATE(created_at) AS created_date,
                        zone,
                        location_name,
                        sap_id,
                        bcu_number
                    FROM 
                        host_k_factor_changes
                    WHERE 1=1
            """
            
            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            
            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"
            
            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'"
            
            # Complete the CTE and main query
            query += """
                    GROUP BY 
                        DATE(created_at), zone, location_name, sap_id, bcu_number
                )
                SELECT 
                    k.created_date,
                    k.zone,
                    k.location_name,
                    k.sap_id,
                    k.bcu_number,
                    (SELECT COUNT(*) 
                    FROM alerts a 
                    WHERE a.device_name = k.bcu_number 
                    AND a.interlock_name = 'K - Factor Data Changed'
                    AND DATE(a.created_at) = k.created_date) AS alert_count
                FROM 
                    k_factor_data k
                ORDER BY 
                    k.created_date DESC, alert_count DESC
            """
            
            print("query --> ", query)
            
            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                    return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))

            # Date filtering if not applied in SQL - default to last 30 days
            if not date_filter_applied:
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            if bcu_number:
                resp_df = resp_df.filter(pl.col("bcu_number") == bcu_number)
            # Generate appropriate result format based on date flag
            if date:
                # Daily Data Aggregation
                group_cols = ["created_date", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    created_date = str(row["created_date"])
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"]
                    }
                    result.setdefault(created_date, []).append(entry)
                return {"status": True, "message": "success", "daily_data": result}
            else:
                # Monthly Data Aggregation
                resp_df = resp_df.with_columns(
                    pl.col("created_date").dt.strftime("%Y-%m").alias("month_year")
                )

                group_cols = ["month_year", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    month = row["month_year"]
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"]
                    }
                    result.setdefault(month, []).append(entry)
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {str(e)}", "data": {}}
    
    @staticmethod
    async def manualfanprinted(filters, cross_filters, drill_state):
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)
            
            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
            
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None
            
            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True
            
            # Construct base SQL Query using CTE for better performance and readability
            query = """
                WITH manual_fan_data AS (
                    SELECT 
                        DATE(created_at) AS created_date,
                        zone,
                        location_name,
                        sap_id,
                        SUM(manual_fan_count) AS total_manual_fan_count
                    FROM 
                        host_manual_fan_printed
                    WHERE 1=1
            """
            
            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            
            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"
            
            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'"
            
            # Complete the CTE with GROUP BY
            query += """
                    GROUP BY 
                        DATE(created_at), zone, location_name, sap_id
                )
                SELECT 
                    m.created_date,
                    m.zone,
                    m.location_name,
                    m.sap_id,
                    (SELECT COUNT(*) 
                    FROM alerts a 
                    WHERE a.interlock_name = 'Manual FAN printed more 5% of total TT loaded'
                    AND DATE(a.created_at) = m.created_date
                    AND a.location_name = m.location_name) AS alert_count,
                    m.total_manual_fan_count
                FROM 
                    manual_fan_data m
                ORDER BY 
                    m.created_date DESC, alert_count DESC
            """
            
            print("query --> ", query)
            
            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                    return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))

            # Date filtering if not applied in SQL - default to last 30 days
            if not date_filter_applied:
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            # Generate appropriate result format based on date flag
            if date:
                # Daily Data Aggregation
                group_cols = ["created_date", "zone", "sap_id", "location_name"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_manual_fan_count").alias("manualfan_count")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    created_date = str(row["created_date"])
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "total_alerts": row["total_alerts"],
                        "total_manual_fan_count": row["manualfan_count"]
                    }
                    result.setdefault(created_date, []).append(entry)
                return {"status": True, "message": "success", "daily_data": result}
            else:
                # Monthly Data Aggregation
                resp_df = resp_df.with_columns(
                    pl.col("created_date").dt.strftime("%Y-%m").alias("month_year")
                )

                group_cols = ["month_year", "zone", "sap_id", "location_name"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_manual_fan_count").alias("manualfan_count")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    month = row["month_year"]
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "total_alerts": row["total_alerts"],
                        "total_manual_fan_count": row["manualfan_count"]
                    }
                    result.setdefault(month, []).append(entry)
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {str(e)}", "data": {}}

    @staticmethod
    async def overloaded_tts(filters, cross_filters, drill_state):
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)
            
            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            bcu_number = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
                    if "bcu_number" in filter.key:
                        bcu_number = filter.value
            
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None
            
            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True
            
            # Construct base SQL Query with Common Table Expression (CTE)
            query = """
                WITH host_data AS (
                    SELECT 
                        DATE(created_at) AS created_date,
                        zone,
                        location_name,
                        sap_id,
                        bcu_number,
                        SUM(required_qty) AS total_required_qty,
                        SUM(loaded_qty) AS total_loaded_qty,
                        SUM(loaded_qty - required_qty) AS qty_difference
                    FROM 
                        host_over_loaded_tts
                    WHERE 1=1
            """
            
            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            
            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"
            
            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'"
            
            # Complete the CTE with GROUP BY
            query += """
                    GROUP BY 
                        DATE(created_at), zone, location_name, sap_id, bcu_number
                )
                SELECT 
                    h.created_date,
                    h.zone,
                    h.location_name,
                    h.sap_id,
                    h.bcu_number,
                    (SELECT COUNT(*) 
                    FROM alerts a 
                    WHERE a.device_name = h.bcu_number 
                    AND a.interlock_name = 'TT Overloaded'
                    AND DATE(a.created_at) = h.created_date) AS alert_count,
                    h.total_required_qty,
                    h.total_loaded_qty,
                    h.qty_difference
                FROM 
                    host_data h
                ORDER BY 
                    h.created_date DESC, alert_count DESC
            """
            
            print("query --> ", query)
            
            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                    return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))

            # Date filtering if not applied in SQL - default to last 30 days
            if not date_filter_applied:
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            if bcu_number:
                resp_df = resp_df.filter(pl.col("bcu_number") == bcu_number)
            # Generate appropriate result format based on date flag
            if date:
                # Daily Data Aggregation
                group_cols = ["created_date", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_required_qty").alias("total_required_quantity"),
                    pl.sum("total_loaded_qty").alias("total_loaded_quantity"),
                    pl.sum("qty_difference").alias("total_quantity_difference")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    created_date = str(row["created_date"])
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"],
                        "total_required_qty": row["total_required_quantity"],
                        "total_loaded_qty": row["total_loaded_quantity"],
                        "total_quantity_difference": row["total_quantity_difference"]
                    }
                    result.setdefault(created_date, []).append(entry)
                return {"status": True, "message": "success", "daily_data": result}
            else:
                # Monthly Data Aggregation
                resp_df = resp_df.with_columns(
                    pl.col("created_date").dt.strftime("%Y-%m").alias("month_year")
                )

                group_cols = ["month_year", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts"),
                    pl.sum("total_required_qty").alias("total_required_quantity"),
                    pl.sum("total_loaded_qty").alias("total_loaded_quantity"),
                    pl.sum("qty_difference").alias("total_quantity_difference")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    month = row["month_year"]
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"],
                        "total_required_qty": row["total_required_quantity"],
                        "total_loaded_qty": row["total_loaded_quantity"],
                        "total_quantity_difference": row["total_quantity_difference"]
                    }
                    result.setdefault(month, []).append(entry)
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {str(e)}", "data": {}}
    

    @staticmethod
    async def mfmkfactor(filters, cross_filters, drill_state):
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)
            
            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            bcu_number = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
                    if "bcu_number" in filter.key:
                        bcu_number = filter.value
            
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None
            
            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True
            
            # Construct base SQL Query with Common Table Expression (CTE)
            query = """
                WITH mfmfactor AS (
                    SELECT 
                        DATE(created_at) AS created_date,
                        zone,
                        location_name,
                        sap_id,
                        bcu_number
                    FROM 
                        host_mfm_factor
                    WHERE 1=1
            """
            
            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            
            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"
            
            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'"
            
            # Complete the CTE with GROUP BY
            query += """
                    GROUP BY 
                        DATE(created_at), zone, location_name, sap_id, bcu_number
                )
                SELECT 
                    h.created_date,
                    h.zone,
                    h.location_name,
                    h.sap_id,
                    h.bcu_number,
                    (SELECT COUNT(*) 
                    FROM alerts a 
                    WHERE a.device_name = h.bcu_number 
                    AND a.interlock_name = 'MFM Data Changed'
                    AND DATE(a.created_at) = h.created_date) AS alert_count
                FROM 
                    mfmfactor h
                ORDER BY 
                    h.created_date DESC, alert_count DESC
            """
            
            print("query --> ", query)
            
            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                    return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))

            # Date filtering if not applied in SQL - default to last 30 days
            if not date_filter_applied:
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            if bcu_number:
                resp_df = resp_df.filter(pl.col("bcu_number") == bcu_number)
            # Generate appropriate result format based on date flag
            if date:
                # Daily Data Aggregation
                group_cols = ["created_date", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    created_date = str(row["created_date"])
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"]
                    }
                    result.setdefault(created_date, []).append(entry)
                return {"status": True, "message": "success", "daily_data": result}
            else:
                # Monthly Data Aggregation
                resp_df = resp_df.with_columns(
                    pl.col("created_date").dt.strftime("%Y-%m").alias("month_year")
                )

                group_cols = ["month_year", "zone", "sap_id", "location_name", "bcu_number"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    month = row["month_year"]
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "bcu_number": row["bcu_number"],
                        "total_alerts": row["total_alerts"]
                    }
                    result.setdefault(month, []).append(entry)
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {str(e)}", "data": {}}
    
    
    @staticmethod
    async def bay_reassignment(filters, cross_filters, drill_state):
        try:
            # Initialize date flag
            date = False
            if "date" in drill_state:
                date = True
            print("date --> ", date)
            
            # Check if zone or plant filters are present
            zone_filter = ''
            plant_filter = ''
            if filters:
                for filter in filters:
                    if "zone" in filter.key:
                        zone_filter = filter.value
                    if "plant" in filter.key:
                        plant_filter = filter.value
            
            # Initialize date filter variables
            date_filter_applied = False
            start_date = None
            end_date = None
            
            # Process cross filters for date
            if cross_filters:
                for filter in cross_filters:
                    if "DATE" in filter.key:
                        date_parts = filter.value.split(',')
                        start_date = datetime.strptime(date_parts[0].strip("'"), '%Y-%m-%d')
                        end_date = datetime.strptime(date_parts[-1].strip("'"), '%Y-%m-%d')
                        date_filter_applied = True
            
            # Construct base SQL Query with CTE for better performance
            query = """
                WITH bay_reassignment AS (
                    SELECT 
                        DATE(created_at) AS created_date,
                        zone,
                        location_name,
                        sap_id,
                        reassigned_bay
                    FROM 
                        host_bay_re_assignment
                    WHERE 1=1
            """
            
            # Add zone filter if present
            if zone_filter:
                query += f" AND zone IN ('{zone_filter}')"
            
            # Add plant/location filter if present
            if plant_filter:
                query += f" AND sap_id IN ('{plant_filter}')"
            
            # Add date filter directly to SQL if applied
            if date_filter_applied and start_date and end_date:
                query += f" AND DATE(created_at) BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'"
            
            # Complete the CTE and main query
            query += """
                GROUP BY 
                        DATE(created_at), zone, location_name, sap_id, reassigned_bay
                )
                SELECT 
                    k.created_date,
                    k.zone,
                    k.location_name,
                    k.sap_id,
                    k.reassigned_bay,
                    (SELECT COUNT(*) 
                    FROM alerts a 
                    WHERE a.interlock_name = 'Bay reasignment'
                    AND DATE(a.created_at) = k.created_date) AS alert_count
                FROM 
                    bay_reassignment k
                ORDER BY 
                    k.created_date DESC, alert_count DESC
            """
            
            print("query --> ", query)
            
            # Execute query
            Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
            Charts_Connection_Vault_RoutingParams.action = 'execute_query'

            try:
                function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
            except Exception as e:
                return {"status": False, "message": f"Query execution failed: {str(e)}", "data": {}}

            if not resp:
                return {"status": False, "message": "Data Not found", "data": {}}

            # Convert response to Polars DataFrame
            resp_df = pl.DataFrame(resp)
            if resp_df.is_empty():
                    return {"status": True, "data": {}}

            resp_df = resp_df.with_columns(pl.col("created_date").cast(pl.Date))

            # Date filtering if not applied in SQL - default to last 30 days
            if not date_filter_applied:
                last_30_days = datetime.now() - timedelta(days=30)
                resp_df = resp_df.filter(pl.col("created_date") >= last_30_days.date())

            # Generate appropriate result format based on date flag
            if date:
                # Daily Data Aggregation
                group_cols = ["created_date", "zone", "sap_id", "location_name", "reassigned_bay"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    created_date = str(row["created_date"])
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "reassigned_bay": row["reassigned_bay"],
                        "total_alerts": row["total_alerts"]
                    }
                    result.setdefault(created_date, []).append(entry)
                return {"status": True, "message": "success", "daily_data": result}
            else:
                # Monthly Data Aggregation
                resp_df = resp_df.with_columns(
                    pl.col("created_date").dt.strftime("%Y-%m").alias("month_year")
                )

                group_cols = ["month_year", "zone", "sap_id", "location_name", "reassigned_bay"]
                grouped = resp_df.group_by(group_cols).agg(
                    pl.sum("alert_count").alias("total_alerts")
                )

                result = {}
                for row in grouped.iter_rows(named=True):
                    month = row["month_year"]
                    entry = {
                        "zone": row["zone"],
                        "sap_id": row["sap_id"],
                        "location_name": row["location_name"],
                        "reassigned_bay": row["reassigned_bay"],
                        "total_alerts": row["total_alerts"]
                    }
                    result.setdefault(month, []).append(entry)
                return {"status": True, "message": "success", "monthly_data": result}

        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {str(e)}", "data": {}}
    
