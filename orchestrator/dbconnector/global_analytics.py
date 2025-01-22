import urdhva_base
import json
import calendar
import psycopg2
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
import utilities.connection_mapping as connection_mapping
from orchestrator.dbconnector.widget_actions import widget_actions
import orchestrator.dbconnector.connector_factory as connector_factory
from api_manager.charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
import orchestrator.dbconnector.widget_actions.lpg_plant_queries as lpg_plant_queries
from collections import defaultdict

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
                    TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", 'Month'), 'Mon') AS "month_name",
                    "M60_LEVEL_METADATA"."FISCAL_YEAR" AS "FISCAL_YEAR"
                FROM
                    "M60_LEVEL_METADATA"
                WHERE
                    "M60_LEVEL_METADATA"."NETWEIGHT_TMT" != 0 and "M60_LEVEL_METADATA"."FISCAL_YEAR" = {fiscal_year_start}
                GROUP BY
                    "M60_LEVEL_METADATA"."fy_month",
                    TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", 'Month'), 'Mon'),
                    "M60_LEVEL_METADATA"."FISCAL_YEAR"
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
            "SalesArea_Name", "PRODUCT", "ProductName", "UOM", "FISCAL_YEAR", 
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
            

            if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'SBU_Name' in filter_keys:
                resp['SBU_Name'] = resp['SBU_Name'].map(sbu_mapping).fillna(resp['SBU_Name'])
                resp['SBU_Name'] = pd.Categorical(resp['SBU_Name'], categories=sbu_order, ordered=True)
                resp = resp.sort_values('SBU_Name')
                grouped_resp = resp.groupby(["SBU_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })
            if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'Zone_Name' in filter_keys:
                grouped_resp = resp.groupby(["Zone_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })
            if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'Region_Name' in filter_keys:
                grouped_resp = resp.groupby(["Region_Name"], as_index=False).agg({
                    "TARGET_QTY_TMT": "sum",
                    "NETWEIGHT_TMT": "sum"
                })
            if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'SalesArea_Name' in filter_keys:
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

            elif "FISCAL_YEAR" in filter_keys and "month_name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" not in filter_keys:
                resp['SBU_Name'] = resp['SBU_Name'].map(sbu_mapping).fillna(resp['SBU_Name'])
                resp['SBU_Name'] = pd.Categorical(resp['SBU_Name'], categories=sbu_order, ordered=True)
                resp = resp.sort_values('SBU_Name')
                grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
                if "DS" in filter_values or 'Lubes' in filter_values or 'DS Lubes' in filter_values:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name","Region_Name"], as_index=False).agg({
                        "TARGET_QTY_TMT": "sum",
                        "NETWEIGHT_TMT": "sum"
                    })
                else:    
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and "Region_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys \
                                    and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })

            elif "FISCAL_YEAR" in filter_keys and \
            "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and \
                                    "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys and "ProductName" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg({
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
    async def m60_performance(filters, cross_filters, drill_state):
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
                    "month_name"
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
            if "month_name" in filter_keys:
            # Convert full month names to short form (e.g., "January" -> "Jan")
                resp["month_name"] = resp["month_name"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )
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
    async def lpg_cdcms(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        lpg_cdcms_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms")
        yesterday = datetime.now() - relativedelta(days=1)
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
                lpg_cdcms_query_ += ' WHERE '
                lpg_cdcms_query_ += ' AND '.join(conditions)
            lpg_cdcms_query_ += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\''
            lpg_cdcms_query_ += ' GROUP BY "ZOName", "ROName", "SAName", "Execution_Date", "JDEDistributorCode", "ConsumerType", "CylType"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            lpg_cdcms_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_cdcms_query_, access_filters, drill_state)
            if "where" not in lpg_cdcms_query_.lower():
                lpg_cdcms_query_ += f' WHERE "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\''
            else:
                lpg_cdcms_query_ += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\''
            lpg_cdcms_query_ += ' GROUP BY "ZOName", "ROName", "SAName", "Execution_Date", "JDEDistributorCode", "ConsumerType", "CylType"'
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
            for each_float_col in [
                "Bookings", "Sales", "Pending"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0).round(2)

            # Fill missing values for string columns
            for each_str_col in [
                "ZOName"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        
        # Execute the query
        resp = await function(query=lpg_cdcms_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        resp = await filter_data(resp, _filters)
        resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
        # Filter rows where Execution_Date matches yesterday
        resp = resp[resp["Execution_Date"].dt.date == yesterday.date()]

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
    async def lpg_cdcms_month(filters, cross_filters, drill_state):
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
        lpg_cdcms_month_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms_month")
        
        today = datetime.now()
        if today.month < 4:
            start_year = today.year - 1
        else:
            start_year = today.year
        end_year = start_year + 1
        financial_year = f"{start_year}-{end_year}"
        
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
                if rec.key == '"Month"':  # Only handle the month_name case separately
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
        
        print("*"*50)
        print("BaseQuery :",lpg_cdcms_month_query_)
        print("*"*50)
        # Execute the query
        resp = await function(query=lpg_cdcms_month_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        resp = await filter_data(resp, _filters)

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
                    "Total Sales": lambda x: x.sum() / 10000000
                })
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["Month", "ZOName","ROName"], as_index=False).agg({
                    "Total Sales": lambda x: x.sum() / 10000000
                })
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["Month", "ZOName","ROName","SAName"], as_index=False).agg({
                    "Total Sales": lambda x: x.sum() / 10000000
                })            
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["Month", "ZOName","ROName","SAName","DistributorName"],
                as_index=False).agg({
                    "Total Sales": lambda x: x.sum() / 10000000
                    })
            if grouped_resp is not None:
                grouped_resp['Total Sales'] = grouped_resp['Total Sales'].round(2)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_cdcms_sales_comparision(filters, cross_filters, drill_state):
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
                if rec.key == '"Month"':  # Only handle the month_name case separately
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
            current_year = resp[resp['Financial_Year'] == financial_year].groupby('Month')['Total_Sales'].sum().reset_index()
            previous_year = resp[resp['Financial_Year'] == prev_financial_year].groupby('Month')['Total_Sales'].sum().reset_index()

            resp = pd.merge(current_year, previous_year, on='Month', how='outer', suffixes=('_current', '_previous'))
            final_data = []
            for _, row in resp.iterrows():
                comparison = {
                    "Month": row['Month'][:3],
                    "Current_Year": financial_year,
                    "Previous_Year": prev_financial_year,
                    "Current_Sales": round(float(row['Total_Sales_current'])/10000000, 2) if pd.notnull(row['Total_Sales_current']) else 0,
                    "Previous_Sale": round(float(row['Total_Sales_previous'])/10000000, 2) if pd.notnull(row['Total_Sales_previous']) else 0
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
                current_year = resp[resp['Financial_Year'] == financial_year].groupby(["Month", "ZOName"])['Total_Sales'].sum().reset_index()
                previous_year = resp[resp['Financial_Year'] == prev_financial_year].groupby(["Month", "ZOName"])['Total_Sales'].sum().reset_index()
                resp = pd.merge(current_year, previous_year, on=["Month", "ZOName"], how='outer', suffixes=('_current', '_previous'))
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                current_year = resp[resp['Financial_Year'] == financial_year].groupby(["Month", "ZOName", "ROName"])['Total_Sales'].sum().reset_index()
                previous_year = resp[resp['Financial_Year'] == prev_financial_year].groupby(["Month", "ZOName", "ROName"])['Total_Sales'].sum().reset_index()
                resp = pd.merge(current_year, previous_year, on=["Month", "ZOName", "ROName"], how='outer', suffixes=('_current', '_previous'))
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                current_year = resp[resp['Financial_Year'] == financial_year].groupby(["Month", "ZOName", "ROName","SAName"])['Total_Sales'].sum().reset_index()
                previous_year = resp[resp['Financial_Year'] == prev_financial_year].groupby(["Month", "ZOName", "ROName","SAName"])['Total_Sales'].sum().reset_index()
                resp = pd.merge(current_year, previous_year, on=["Month", "ZOName", "ROName", "SAName"], how='outer', suffixes=('_current', '_previous'))
            elif "Month" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                current_year = resp[resp['Financial_Year'] == financial_year].groupby(["Month", "ZOName", "ROName","SAName","DistributorName"])['Total_Sales'].sum().reset_index()
                previous_year = resp[resp['Financial_Year'] == prev_financial_year].groupby(["Month", "ZOName", "ROName","SAName","DistributorName"])['Total_Sales'].sum().reset_index()
                resp = pd.merge(current_year, previous_year, on=["Month", "ZOName", "ROName", "SAName", "DistributorName"], how='outer', suffixes=('_current', '_previous'))
            final_data = []
            for _, row in resp.iterrows():
                comparison = {
                    "Month": row['Month'][:3],
                    "Current_Year": financial_year,
                    "Previous_Year": prev_financial_year,
                    "Current_Sales": round(float(row['Total_Sales_current'])/10000000, 2) if pd.notnull(row['Total_Sales_current']) else 0,
                    "Previous_Sale": round(float(row['Total_Sales_previous'])/10000000, 2) if pd.notnull(row['Total_Sales_previous']) else 0
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
    async def cdcms_order_source(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        yesterday = datetime.now() - relativedelta(days=1)
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
            cdcms_order_source_query_ += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\''
            cdcms_order_source_query_ += ' GROUP BY "OrderSourceName", "ZOName", "ROName", "SAName", "Execution_Date", "JDEDistributorCode", "ConsumerType", "CylType"'
        else:      
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            cdcms_order_source_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(cdcms_order_source_query_, access_filters, drill_state)
            if "where" not in cdcms_order_source_query_.lower():
                cdcms_order_source_query_ += f' WHERE "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            else:
                cdcms_order_source_query_ += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            cdcms_order_source_query_ += ' GROUP BY "OrderSourceName", "ZOName", "ROName", "SAName", "Execution_Date", "JDEDistributorCode", "ConsumerType", "CylType"'

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
        resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
        # Filter rows where Execution_Date matches yesterday
        resp["Execution_Date"] = pd.to_datetime(resp["Execution_Date"], errors="coerce")
        resp = resp[resp["Execution_Date"].dt.date == yesterday.date()]

        for each_float_col in [
            "Total_Bookings"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "OrderSourceName","ZOName","ROName","SAName","JDEDistributorCode"
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
            elif "OrderSourceName" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "JDEDistributorCode" not in filter_keys:
                grouped_resp = resp.groupby(["OrderSourceName","ZOName","ROName","SAName","JDEDistributorCode"],
                as_index=False).agg({
                    "Total_Bookings": "sum"
                    })
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def overall_pending_pmuy_nmpuy(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        yesterday = datetime.now() - relativedelta(days=1)
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
            lpg_pending_query_  += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\''
            lpg_pending_query_  += ' GROUP BY "Execution_Date","ZOName" ,"ROName","SAName","ConsumerType" ,"JDEDistributorCode", "CylType"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            lpg_pending_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_pending_query_, access_filters, drill_state)
            if "where" not in lpg_pending_query_.lower():                
                lpg_pending_query_  += f' WHERE "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            else:
                lpg_pending_query_  += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            lpg_pending_query_  += ' GROUP BY "Execution_Date","ZOName" ,"ROName","SAName","ConsumerType" ,"JDEDistributorCode", "CylType"'
            print("*"*50)
            print("lpg_pending_query_ :", lpg_pending_query_)
            print("*"*50)
            resp = await function(query=lpg_pending_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["ConsumerType"], as_index=False).agg({
                        "Total_pending": "sum",
                    })
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
                "JDEDistributorCode"
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
            resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
            resp["Execution_Date"] = pd.to_datetime(resp["Execution_Date"], errors="coerce")            
            resp = resp[resp["Execution_Date"].dt.date == yesterday.date()]

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
                "JDEDistributorCode"
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
                    return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        else:
            return {"status": True, "message":"success", "data":[]}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_cdcms_ageing(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        lpg_pending_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms_ageing")
        yesterday = datetime.now() - relativedelta(days=1)
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
            lpg_pending_query_  += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN ( \'Null\')'
            lpg_pending_query_  += ' GROUP BY "Execution_Date", "ZOName" ,"ROName","SAName","ConsumerType" ,"JDEDistributorCode" '
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSalesSummaryData.get_clause_conditions(formated=True)]
            lpg_pending_query_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_pending_query_, access_filters, drill_state)
            if "where" not in lpg_pending_query_.lower():                
                lpg_pending_query_  += f' WHERE "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            else:
                lpg_pending_query_  += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            lpg_pending_query_  += ' GROUP BY "Execution_Date", "ZOName" ,"ROName","SAName","ConsumerType" ,"JDEDistributorCode" '
            print(lpg_pending_query_)
            resp = await function(query=lpg_pending_query_ )
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            resp = resp.groupby(["ConsumerType"], as_index=False).agg({
                    "Pending 1-3 days": "sum"
                })
            # Fill missing values for numerical columns
            for each_float_col in [
                "Ageing"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            # Fill missing values for string columns
            for each_str_col in [
                "ZOName" ,"ROName","SAName","ConsumerType" ,"JDEDistributorCode"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        # Execute the query
        print("*"*50)
        print("lpg_pending_query_ :", lpg_pending_query_)
        print("*"*50)
        resp = await function(query=lpg_pending_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
        # Filter rows where Execution_Date matches yesterday
        resp['Execution_Date'] = pd.to_datetime(resp['Execution_Date'])
        resp = resp[resp["Execution_Date"].dt.date == yesterday.date()]
        # Fill missing values for numerical columns
        for each_float_col in [
            "Pending 1-3 days"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)
        # Fill missing values for string columns
        for each_str_col in [
            "ZOName", "ROName", "SAName", "ConsumerType", "JDEDistributorCode"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "ConsumerType" in filter_keys and "ZOName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName"], as_index=False).agg({
                    "Pending 1-3 days": "sum"
                })
            elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName"], as_index=False).agg({
                    "Pending 1-3 days": "sum",
                })
            elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName", "SAName"],
                                            as_index=False).agg({
                    "Pending 1-3 days": "sum",
                })
            elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName"  in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType", "ZOName", "ROName", "SAName","DistributorName"],
                                            as_index=False).agg({
                    "Pending 1-3 days": "sum",
                })
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
        
    @staticmethod
    async def card_chart(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        card_query = lpg_plant_queries.lpg_plant_query.get(drill_state)
        resp = await function(query=card_query)
        resp = pd.DataFrame(resp)
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    
    @staticmethod
    async def total_consumers(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        total_consumers_query_ = lpg_plant_queries.lpg_plant_query.get("total_consumers")
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
                total_consumers_query_  += ' WHERE '
                total_consumers_query_  += ' AND '.join(conditions)
            total_consumers_query_ +=  ' AND "Category" NOT IN (\'Others\') AND "ZOName" IS NOT NULL '
            total_consumers_query_  += ' GROUP BY "ZOName" ,"ROName","SAName","Category","SubCategory" ,"JDEDistributorCode"'
        else:
            if not "where" in total_consumers_query_.lower():
                total_consumers_query_ +=  ' WHERE "Category" NOT IN (\'Others\') AND "ZOName" IS NOT NULL'
            else:
                total_consumers_query_ +=  ' AND "Category" NOT IN (\'Others\') AND "ZOName" IS NOT NULL'
            total_consumers_query_  += ' GROUP BY "ZOName" ,"ROName","SAName","Category","SubCategory" ,"JDEDistributorCode"'
            resp = await function(query=total_consumers_query_ )
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["Category"], as_index=False).agg({
                        "Total_Consumers": "sum",
                    })
            # Fill missing values for numerical columns
            for each_float_col in [
                "Total_Consumers"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            # Fill missing values for string columns
            for each_str_col in [
                "ZOName",
                "ROName",
                "SAName",
                "Category",
                "SubCategory",
                "JDEDistributorCode"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        resp = await function(query=total_consumers_query_ )
        if resp:
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
            for each_float_col in [
                "Total_Consumers"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            for each_str_col in [
                "ZOName",
                "ROName",
                "SAName",
                "Category",
                "SubCategory",
                "JDEDistributorCode"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            if filters:
                grouped_resp = None
                filter_keys = [rec.key.strip('"') for rec in filters]
                if "Category" in filter_keys and "SubCategory" not in filter_keys:
                    grouped_resp = resp.groupby(["Category", "SubCategory"], as_index=False).agg({
                        "Total_Consumers": "sum",
                    })
                if "Category" in filter_keys and "SubCategory" in filter_keys and "ZOName" not in filter_keys:
                    grouped_resp = resp.groupby(["Category", "SubCategory","ZOName"], as_index=False).agg({
                        "Total_Consumers": "sum",
                    })
                if "Category" in filter_keys and "SubCategory" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                    grouped_resp = resp.groupby(["Category","SubCategory", "ZOName", "ROName"], as_index=False).agg({
                        "Total_Consumers": "sum",
                    })
                elif "Category" in filter_keys and "SubCategory" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                    grouped_resp = resp.groupby(["Category","SubCategory","ZOName", "ROName", "SAName"], as_index=False).agg({
                        "Total_Consumers": "sum",
                    })
                elif "Category" in filter_keys and "SubCategory" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                    grouped_resp = resp.groupby(["Category","SubCategory","ZOName", "ROName", "SAName", "DistributorName"],
                                                as_index=False).agg({
                        "Total_Consumers": "sum",
                    })
                if grouped_resp is not None:
                    return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        else:
            return {"status": True, "message":"success", "data":[]}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def ekyc_statistics(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        ekyc_statistics_query_ = lpg_plant_queries.lpg_plant_query.get("ekyc_statistics")
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
                ekyc_statistics_query_ += ' WHERE '
                ekyc_statistics_query_ += ' AND '.join(conditions)
            ekyc_statistics_query_ += f'  AND "ZOName"  NOT IN ( \'Null\') '
            ekyc_statistics_query_ += ' GROUP BY   "ROName","SAName" ,"JDEDistributorCode","ZoneNames" '
        else:
            if not "where" in ekyc_statistics_query_.lower():
                ekyc_statistics_query_ += f' WHERE "ZOName"  NOT IN ( \'Null\')'
            else:
                ekyc_statistics_query_ += f' AND "ZOName"  NOT IN ( \'Null\')'
            ekyc_statistics_query_ += ' GROUP BY   "ROName","SAName" ,"JDEDistributorCode","ZoneNames"'
            resp = await function(query=ekyc_statistics_query_)
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["ZoneNames"], as_index=False).agg({
                    "Completed": "sum",
                    "Pending": "sum"
                })
            for each_float_col in [
                "Completed","Pending"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            for each_str_col in [
                "ROName", "SAName", "JDEDistributorCode","ZoneNames"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        # Execute the query
        print("*" * 50)
        print("ekyc_statistics_query_ :", ekyc_statistics_query_)
        print("*" * 50)
        resp = await function(query=ekyc_statistics_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
        for each_float_col in [
                "Completed","Pending"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)
        # Fill missing values for string columns
        for each_str_col in [
                 "ROName", "SAName", "JDEDistributorCode","ZoneNames"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "ZoneNames" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["ZoneNames", "ROName"], as_index=False).agg({
                    "Completed": "sum",
                    "Pending": "sum"
                })
            elif "ZoneNames" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["ZoneNames", "ROName", "SAName"], as_index=False).agg({
                    "Completed": "sum",
                    "Pending": "sum"                
                })
            elif "ZonesNames" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["ZoneNames", "ROName", "SAName", "DistributorName"],
                                            as_index=False).agg({"Completed": "sum", "Pending": "sum"})
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def total_suvidha(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        total_suvidha_query_ = lpg_plant_queries.lpg_plant_query.get("total_suvidha")
        _filters = []
        if cross_filters:
            for filter in cross_filters:
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
                total_suvidha_query_  += ' WHERE '
                total_suvidha_query_  += ' AND '.join(conditions)
            total_suvidha_query_ +=  ' AND "Category" = \'Domestic\' AND "ZOCode" NOT IN (\'Null\') AND "SubCategory" IN (\'NPMUY\',\'PMUY\')'
            total_suvidha_query_  += ' GROUP BY "ZOName", "ROName", "SAName", "SubCategory", "Category", "JDEDistributorCode"'
        else:
            if "where" not in total_suvidha_query_.lower():
                total_suvidha_query_ +=  ' WHERE "Category" = \'Domestic\''
            else:
                total_suvidha_query_ +=  ' AND "Category" = \'Domestic\''
            total_suvidha_query_  += ' GROUP BY "ZOName", "ROName", "SAName", "SubCategory", "Category", "JDEDistributorCode"'
            
            resp = await function(query=total_suvidha_query_)
            resp = pd.DataFrame(resp)
            resp = await filter_data(resp, _filters)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["SubCategory"], as_index=False).agg({
                        "SuvidhaClub": "sum",
                    })
            for each_float_col in [
                "SuvidhaClub"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "ZOName",
                "ROName",
                "SAName",
                "SubCategory",
                "Category"
                "JDEDistributorCode"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": resp}

        resp = await function(query=total_suvidha_query_)
        if resp:
            resp = pd.DataFrame(resp)
            resp = await filter_data(resp, _filters)
            resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
            
            for each_float_col in [
                "SuvidhaClub"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            for each_str_col in [
                "ZOName",
                "ROName",
                "SAName",
                "SubCategory",
                "Category",
                "JDEDistributorCode"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            if filters:
                grouped_resp = None
                filter_keys = [rec.key.strip('"') for rec in filters]
                if "SubCategory" in filter_keys and "ZOName" not in filter_keys:
                    grouped_resp = resp.groupby(["SubCategory", "ZOName"], as_index=False).agg({
                        "SuvidhaClub": "sum",
                    })
                if "SubCategory" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                    grouped_resp = resp.groupby(["SubCategory","ZOName", "ROName"], as_index=False).agg({
                        "SuvidhaClub": "sum",
                    })
                elif "SubCategory" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                    grouped_resp = resp.groupby(["SubCategory","ZOName", "ROName", "SAName"], as_index=False).agg({
                        "SuvidhaClub": "sum",
                    })  
                elif "SubCategory" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                    grouped_resp = resp.groupby(["SubCategory","ZOName", "ROName", "SAName", "DistributorName"],
                                                as_index=False).agg({
                        "SuvidhaClub": "sum",
                    })                    
                if grouped_resp is not None:
                    return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        else:
            return {"status": True, "message":"success", "data":[]}
        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    

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
        query += " GROUP BY execution_date"
        resp = await function(query=query)
        return resp
    
    
    @staticmethod
    async def cdcms_dropdown(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        _query = ''' select * from cdcms_masters '''
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
                    if key in ["Month", "CylType", "ConsumerType"]:
                        continue
                    filter_expr = filter_expr & (pl.col(key).fill_null("") == value)
            df = df.filter(filter_expr)
        months = [month for month in calendar.month_name if month]
        df = df.filter(pl.col("ZOName").fill_null("") != "NULL")
        df = df.filter(pl.col("DistributorName").fill_null("") != "NULL")
        data = {"Month": months, "ZOName": df['ZOName'].unique().to_list(),
                "ROName": df['ROName'].unique().to_list(), "SAName": df['SAName'].unique().to_list(), 
                "DistributorName": df["DistributorName"].unique().to_list(), "CylType": ['C142','C5'], 
                "ConsumerType": ['PMUY', 'NPMUY']}
        return data
    

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
    async def cumulative_sales_pmuy_npmuy(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})        
        today = datetime.now()
        if today.month < 4:
            start_year = today.year - 1
        else:
            start_year = today.year
        end_year = start_year + 1
        financial_year = f"{start_year}-{end_year}"
        
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
                    "Sales": lambda x: x.sum() / 10000000
                })
            # Fill missing values for numerical columns
            for each_float_col in [
                "Sales"
            ]:
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
        for each_float_col in [
            "Sales"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "ConsumerType","ZOName","ROName","SAName","DistributorName"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]

            if "ConsumerType" in filter_keys and "ZOName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType","ZOName"], as_index=False).agg({
                    "Sales": lambda x: x.sum() / 10000000
                })

            elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType","ZOName","ROName"], as_index=False).agg({
                    "Sales": lambda x: x.sum() / 10000000
                })
            
            elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType","ZOName","ROName","SAName"],
                as_index=False).agg({
                    "Sales": lambda x: x.sum() / 10000000
                    })
            
            elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType","ZOName","ROName","SAName","DistributorName"],
                as_index=False).agg({
                    "Sales": lambda x: x.sum() / 10000000
                    })

            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    @staticmethod
    async def overall_ctc_statistics(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        overall_ctc_statistics_query_ = lpg_plant_queries.lpg_plant_query.get("overall_ctc_statistics")
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
                overall_ctc_statistics_query_ += ' WHERE '
                overall_ctc_statistics_query_ += ' AND '.join(conditions)
            overall_ctc_statistics_query_  += f' AND "ZOName"  NOT IN ( \'Null\') AND "Category" NOT IN (\'Others\')'
            overall_ctc_statistics_query_ += ' GROUP BY "Category", "ZOName", "ROName", "SAName", "JDEDistributorCode"'
        else:
            if not "where" in overall_ctc_statistics_query_.lower():
                overall_ctc_statistics_query_  += f' WHERE "ZOName"  NOT IN ( \'Null\') AND "Category" NOT IN (\'Others\')'
            else:
                overall_ctc_statistics_query_  += f' AND "ZOName"  NOT IN ( \'Null\') AND "Category" NOT IN (\'Others\')'
            overall_ctc_statistics_query_ += ' GROUP BY "Category", "ZOName", "ROName", "SAName", "JDEDistributorCode"'
            resp = await function(query=overall_ctc_statistics_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            resp = resp.groupby(["Category"], as_index=False).agg({
                    "ACTC": "sum",
                    "BCTC": "sum",
                    "NCTC": "sum"
                })
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            # Fill missing values for numerical columns
            for each_float_col in [
                "ACTC","BCTC","NCTC"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "Category"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": resp}
        
        # Execute the query
        resp = await function(query=overall_ctc_statistics_query_)        
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
        # Fill missing values for numerical columns
        for each_float_col in [
            "ACTC","BCTC","NCTC"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "Category","ZOName","ROName","SAName","JDEDistributorCode"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]

            if "Category" in filter_keys and "ZOName" not in filter_keys:    
                grouped_resp = resp.groupby(["Category","ZOName"], as_index=False).agg({
                    "ACTC": "sum",
                    "BCTC": "sum",
                    "NCTC": "sum"
                })

            elif "Category" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["Category","ZOName","ROName"], as_index=False).agg({
                    "ACTC": "sum",
                    "BCTC": "sum",
                    "NCTC": "sum"
                })
            
            elif "Category" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["Category","ZOName","ROName","SAName"],
                as_index=False).agg({
                    "ACTC": "sum",
                    "BCTC": "sum",
                    "NCTC": "sum"
                    })
            
            elif "Category" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "JDEDistributorCode" not in filter_keys:
                grouped_resp = resp.groupby(["Category","ZOName","ROName","SAName","JDEDistributorCode"],
                as_index=False).agg({
                    "ACTC": "sum",
                    "BCTC": "sum",
                    "NCTC": "sum"
                    })
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    @staticmethod
    async def overall_safety_check_pending(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        overall_safety_check_pending_query_ = lpg_plant_queries.lpg_plant_query.get("overall_safety_check_pending")
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
                overall_safety_check_pending_query_ += ' WHERE '
                overall_safety_check_pending_query_ += ' AND '.join(conditions)
            overall_safety_check_pending_query_  += f' AND "ZOName"  NOT IN (\'Null\') AND "Category" IN (\'Domestic\')'
            overall_safety_check_pending_query_ += ' GROUP BY "SubCategory", "ZOName", "ROName", "SAName", "JDEDistributorCode"'
        else:
            if not "where" in overall_safety_check_pending_query_.lower():
                overall_safety_check_pending_query_  += f' WHERE "ZOName"  NOT IN (\'Null\') AND "Category" IN (\'Domestic\')'
            else:
                overall_safety_check_pending_query_  += f' AND "ZOName"  NOT IN (\'Null\') AND "Category" IN (\'Domestic\')'
            overall_safety_check_pending_query_ += ' GROUP BY "SubCategory", "ZOName", "ROName", "SAName", "JDEDistributorCode"'
            
            resp = await function(query=overall_safety_check_pending_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            resp = resp.groupby(["SubCategory"], as_index=False).agg({
                    "SafetyCheckPending": "sum"
                })
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            # Fill missing values for numerical columns
            for each_float_col in [
                "SafetyCheckPending"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "SubCategory"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        # Execute the query
        resp = await function(query=overall_safety_check_pending_query_)        
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
        # Fill missing values for numerical columns
        for each_float_col in [
            "SafetyCheckPending"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "SubCategory","ZOName","ROName","SAName","JDEDistributorCode"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "SubCategory" in filter_keys and "ZOName" not in filter_keys:    
                grouped_resp = resp.groupby(["SubCategory","ZOName"], as_index=False).agg({
                    "SafetyCheckPending": "sum"
                })
            elif "SubCategory" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["SubCategory","ZOName","ROName"], as_index=False).agg({
                    "SafetyCheckPending": "sum"
                })            
            elif "SubCategory" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["SubCategory","ZOName","ROName","SAName"],
                as_index=False).agg({
                    "SafetyCheckPending": "sum"
                    })            
            elif "SubCategory" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "JDEDistributorCode" not in filter_keys:
                grouped_resp = resp.groupby(["SubCategory","ZOName","ROName","SAName","JDEDistributorCode"],
                as_index=False).agg({
                    "SafetyCheckPending": "sum"
                    })
            if grouped_resp is not None:
                print("grouped_resp  -> ", grouped_resp)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
        
    
    @staticmethod
    async def cp_total_locations(filters, drill_state):
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
    async def cp_total_dus(filters, drill_state):
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
    async def cp_total_tanks(filters, drill_state):
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
    async def cp_avg_monthly_consumption(filters, drill_state):
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
    

    async def cp_avg_monthly_consumption_by_location(filters, drill_state):
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
    
    async def cp_total_volume_consumption(filters, drill_state):
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

    
    async def cp_total_volume_sales(filters, drill_state):
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
            productivity_zone_query_ += f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            productivity_zone_query_ += ' GROUP BY "zone", "name",  "process_date","carousel" '
        else:
            if not "where" in productivity_zone_query_.lower():
                productivity_zone_query_ += f' WHERE CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            else:
                productivity_zone_query_ += f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            productivity_zone_query_ += ' GROUP BY "zone", "name",  "process_date","carousel" '
            resp = await function(query=productivity_zone_query_)
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["zone", "carousel"], as_index=False).agg({
                        "productivity": "mean"
                    })
            for each_float_col in ["productivity"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            # Fill missing values for string columns
            for each_str_col in ["zone", "name", "carousel"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        resp = await function(query=productivity_zone_query_)
        if resp:
            resp = pd.DataFrame(resp)
            for each_float_col in ["productivity"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            for each_str_col in ["zone","name","carousel"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            if filters:
                grouped_resp = None
                filter_keys = [rec.key.strip('"') for rec in filters]
                if "zone" in filter_keys and "name" not in filter_keys:
                    grouped_resp = resp.groupby(["zone","name","carousel"], as_index=False).agg({
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
            production_zone_query_ +=  f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            production_zone_query_  += ' GROUP BY "zone", "name", "process_date", "carousel" '
        else:
            if not "where" in production_zone_query_.lower():
                production_zone_query_ +=  f' WHERE CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            else:
                production_zone_query_ +=  f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            production_zone_query_  += ' GROUP BY "zone", "name", "process_date", "carousel" '
            resp = await function(query=production_zone_query_)
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["zone", "carousel"], as_index=False).agg({
                        "Productions": "sum"
                    })
            for each_float_col in ["Productions"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            for each_str_col in ["zone", "name", "carousel"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}
        resp = await function(query=production_zone_query_)
        if resp:
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            for each_float_col in ["Productions"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            # Fill missing values for string columns
            for each_str_col in ["zone", "name", "carousel"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            if filters:
                grouped_resp = None
                filter_keys = [rec.key.strip('"') for rec in filters]
                if "zone" in filter_keys and "name" not in filter_keys:
                    grouped_resp = resp.groupby(["zone","name","carousel"], as_index=False).agg({
                        "Productions": "sum"
                    })
                if grouped_resp is not None:
                    return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        else:
            return {"status": True, "message":"success", "data":[]}
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    
    @staticmethod
    async def lpg_operations_filled_cylinder(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        current_date = datetime.now().strftime("%Y-%m-%d")
        handled_cylinder_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_operations_filled_cylinder")
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
            handled_cylinder_query_ += f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            handled_cylinder_query_ += ' GROUP BY  "zone" ,"plant", "process_date" '
        else:
            if not "where" in handled_cylinder_query_.lower():
                handled_cylinder_query_ += f' WHERE CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            else:
                handled_cylinder_query_ += f' AND CAST("process_date" AS DATE) = \'{current_date}\' AND "zone" IS NOT NULL'
            handled_cylinder_query_ += ' GROUP BY "zone", "plant", "process_date" '
            resp = await function(query=handled_cylinder_query_)
            resp = pd.DataFrame(resp)
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
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        resp = pd.DataFrame(resp)
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
    async def subsidy_exception_stats(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        yesterday = datetime.now() - relativedelta(days=1)
        lpg_exception_stats_ = lpg_plant_queries.lpg_plant_query.get("subsidy_exception_stats")
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSubsidyExceptionData.get_clause_conditions(formated=True)]
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
                lpg_exception_stats_  += ' WHERE '
                lpg_exception_stats_  += ' AND '.join(conditions)
            lpg_exception_stats_  += ' AND "ZOName" IS NOT NULL'
            lpg_exception_stats_  += ' GROUP BY  "ZOName" ,"ROName","SAName" ,"JDEDistributorCode","ExceptionName"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSubsidyExceptionData.get_clause_conditions(formated=True)]
            lpg_exception_stats_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_exception_stats_, access_filters, drill_state)
            lpg_exception_stats_  = f'''
                                    SELECT 
                                        "ExceptionName" AS "ExceptionName",
                                        SUM("Consumers") AS "Consumers",
                                        SUM("Refills")  AS "Refills"
                                        FROM
                                        "subsidy_exception_statistics_EC_data"
                                    GROUP BY
                                        "ExceptionName" '''
            resp = await function(query=lpg_exception_stats_ )
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["ExceptionName","ZOName"], as_index=False
                                ).agg({"Consumers": "sum","Refills": "sum" })
            for each_float_col in ["Consumers","Refills"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            for each_str_col in [
                "ZOName","ROName","SAName","JDEDistributorCode","ExceptionName"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}

        # Execute the query
        resp = await function(query=lpg_exception_stats_)
        if resp:
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
            for each_float_col in ["Consumers","Refills"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            for each_str_col in ["ZOName","ROName","SAName","JDEDistributorCode","ExceptionName"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            if filters:
                grouped_resp = None
                filter_keys = [rec.key.strip('"') for rec in filters]
                if "ExceptionName" in filter_keys  and "ZOName" not in filter_keys:
                    grouped_resp = resp.groupby(["ExceptionName","ZOName"], as_index=False).agg({
                        "Consumers": "sum","Refills": "sum" })
                if "ExceptionName" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                    grouped_resp = resp.groupby(["ExceptionName", "ZOName", "ROName"], as_index=False).agg({
                        "Consumers": "sum","Refills": "sum"})
                elif "ExceptionName" in filter_keys  and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                    grouped_resp = resp.groupby(["ExceptionName","ZOName", "ROName", "SAName"], as_index=False).agg({
                        "Consumers": "sum","Refills": "sum"})
                elif "ExceptionName" in filter_keys  and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                    grouped_resp = resp.groupby(["ExceptionName","ZOName", "ROName", "SAName", "DistributorName"],
                                                as_index=False).agg({"Consumers": "sum","Refills": "sum"})
                if grouped_resp is not None:
                    return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        else:
            return {"status": True, "message":"success", "data":[]}
        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    @staticmethod
    async def subsidy_failure_stats(filters, cross_filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        lpg_failure_stats_ = lpg_plant_queries.lpg_plant_query.get("subsidy_failure_stats")
        _filters = []
        if cross_filters:
            for filter in cross_filters:
                _filters.append({f"{filter.key}": f"{filter.value}"})
        if filters:
            filters += [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSubsidyFailureData.get_clause_conditions(formated=True)]
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
                lpg_failure_stats_  += ' WHERE '
                lpg_failure_stats_  += ' AND '.join(conditions)
            lpg_failure_stats_  += ' AND "ZOName" IS NOT NULL'
            lpg_failure_stats_  += ' GROUP BY  "ZOName" ,"ROName","SAName" ,"JDEDistributorCode","PaymentErrorName"'
        else:
            access_filters = [dashboard_studio_model.WidgetFiltersCreate(**rec)
                                      for rec in await hpcl_ceg_model.LpgSubsidyFailureData.get_clause_conditions(formated=True)]
            lpg_failure_stats_ =  await widget_actions.WidgetActions.apply_filter_drilldown(lpg_failure_stats_, access_filters, drill_state)

            resp = await function(query=lpg_failure_stats_ )
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            resp = resp.groupby(["PaymentErrorName"], as_index=False
                                ).agg({"Consumers": "sum","Refills": "sum" })
            for each_float_col in ["Consumers", "Refills"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)
            for each_str_col in [
                "ZOName", "ROName", "SAName", "JDEDistributorCode", "PaymentErrorName"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
            return {"status": True, "message": "success", "data": resp}

        # Execute the query
        resp = await function(query=lpg_failure_stats_ )
        if resp:
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')
            for each_float_col in ["Consumers","Refills"]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            for each_str_col in ["ZOName","ROName","SAName","JDEDistributorCode","PaymentErrorName"]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            if filters:
                grouped_resp = None
                filter_keys = [rec.key.strip('"') for rec in filters]
                if "PaymentErrorName" in filter_keys  and "ZOName" not in filter_keys:
                    grouped_resp = resp.groupby(["PaymentErrorName","ZOName"], as_index=False).agg({
                        "Consumers": "sum","Refills": "sum" })
                if "PaymentErrorName" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                    grouped_resp = resp.groupby(["PaymentErrorName", "ZOName", "ROName"], as_index=False).agg({
                        "Consumers": "sum","Refills": "sum"})
                elif "PaymentErrorName" in filter_keys  and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                    grouped_resp = resp.groupby(["PaymentErrorName","ZOName", "ROName", "SAName"], as_index=False).agg({
                        "Consumers": "sum","Refills": "sum"})
                elif "PaymentErrorName" in filter_keys  and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                    grouped_resp = resp.groupby(["PaymentErrorName","ZOName", "ROName", "SAName", "DistributorName"],
                                                as_index=False).agg({"Consumers": "sum","Refills": "sum"})
                if grouped_resp is not None:
                    return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        else:
            return {"status": True, "message":"success", "data":[]}
        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    @staticmethod
    async def lpg_operations_rejetions(filters, cross_filters, drill_state):
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
