import urdhva_base
import json
import psycopg2
import polars as pl
import pandas as pd
import hpcl_ceg_model
import dashboard_studio_model
from datetime import datetime
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

class GlobalAnalytics:
    @staticmethod
    async def analytics(filters, drill_state):
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
    async def alert_ageing(filters, drill_state):
        """
        This method is used to fetch the alert ageing data for the given filters and drill state
        :param filters: The filter parameters
        :param drill_state: The drill down state
        :return: A dictionary containing the status, message and the alert ageing data
        """
        alert_ageing_query = lpg_plant_queries.lpg_plant_query.get("alert_ageing")
        alert_ageing_query_ = alert_ageing_query
        if filters:
            alert_ageing_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(alert_ageing_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(alert_ageing_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(alert_ageing_query)
        data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": data}
    
    @staticmethod
    async def day_wise_alerts(filters, drill_state):
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
        if filters:
            day_wise_alerts_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(day_wise_alerts_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(day_wise_alerts_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(day_wise_alerts_query)
        data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": data}
    
    @staticmethod
    async def location_severity_count(filters, drill_state):
        """
        Fetches the location severity count data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the location severity count data.
        """
        location_severity_count_query = lpg_plant_queries.lpg_plant_query.get("location_severity_count")
        location_severity_count_query_ = location_severity_count_query

        if filters:
            for filter_ in filters:
                if filter_.key == "bu":
                    # Explicitly qualify the column with the correct table alias
                    filter_key = f"a.{filter_.key}"  # Assuming "a" is the alias for the table containing "bu"
                    filter_condition = f" WHERE {filter_key} = '{filter_.value}'"
                    # Add the filter condition before GROUP BY
                    location_severity_count_query_ = location_severity_count_query_.replace("GROUP BY", f"{filter_condition} GROUP BY")
                    break

        try:
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(location_severity_count_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            # Retry with the original query if the column is undefined
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(location_severity_count_query)

        # Process the results
        data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": data}

    @staticmethod
    async def no_of_locations(filters, drill_state):
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
    async def severity_count(filters, drill_state):
        """
        Fetches the severity count data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the severity count data.
        """
        severity_count_query = lpg_plant_queries.lpg_plant_query.get("severity_count")
        severity_count_query_ = severity_count_query
        if filters:
            for filter_ in filters:
                if filter_.key:
                    # Update the key of the filter to include the alias 'a.'
                    filter_.key = f"lm.{filter_.key}"
            severity_count_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(severity_count_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(severity_count_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(severity_count_query)
        severity_count_data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        for item in severity_count_data:
            item['operability_index'] = 99
        return {"status": True, "message": "success", "data": severity_count_data}
    
    @staticmethod
    async def hourly_alerts(filters, drill_state):
        """
        Fetches the hourly alerts data for the given filters and drill state.

        Parameters:
            filters (list): List of filter objects to apply to the query.
            drill_state (dict): Current drill state for processing the query.

        Returns:
            dict: Contains the status, a success message, and the hourly alerts data.
        """
        hourly_alerts_query = lpg_plant_queries.lpg_plant_query.get("hourly_alerts")
        hourly_alerts_query_ = hourly_alerts_query
        if filters:
            hourly_alerts_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(hourly_alerts_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(hourly_alerts_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(hourly_alerts_query)
        hourly_alerts_data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": hourly_alerts_data}


    @staticmethod
    async def sales_performance(filters, drill_state):
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
                    ROUND(SUM("M60_LEVEL_METADATA"."NETWEIGHT_TMT")::numeric,2) AS "ACTUAL_TMT_SALES",
                    ROUND(SUM("M60_LEVEL_METADATA"."TARGET_QTY_TMT")::numeric,2) AS "TARGET_TMT_SALES",
                    "M60_LEVEL_METADATA"."fy_month" AS "fy_month",
                    TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", 'Month'), 'Mon') AS "month_name",
                    "M60_LEVEL_METADATA"."FISCAL_YEAR" AS "FISCAL_YEAR"
                FROM
                    "M60_LEVEL_METADATA"
                WHERE
                    "M60_LEVEL_METADATA"."NETWEIGHT_TMT" != 0 and   "M60_LEVEL_METADATA"."FISCAL_YEAR" = {fiscal_year_start}
                GROUP BY
                    "M60_LEVEL_METADATA"."fy_month",
                    TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", 'Month'), 'Mon'),
                    "M60_LEVEL_METADATA"."FISCAL_YEAR"
                ORDER BY
                    "M60_LEVEL_METADATA"."fy_month" ASC;
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
            if "month_name" in filter_keys:
            # Convert full month names to short form (e.g., "January" -> "Jan")
                resp["month_name"] = resp["month_name"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )

            if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'SBU_Name' in filter_keys:
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
                grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
                if "DS" in filters[-1].value[0] or 'Lubes' in filters[-1].value[0] or 'DS Lubes' in filters[-1].value[0]:
                        grouped_resp = resp.groupby(["month_name", "SBU_Name","Region_Name"], as_index=False).agg({
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
            grouped_resp["NETWEIGHT_TMT"] = grouped_resp["NETWEIGHT_TMT"].round(2)
            grouped_resp["TARGET_QTY_TMT"] = grouped_resp["TARGET_QTY_TMT"].round(2)
            # Return grouped response
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    @staticmethod
    async def m60_performance(filters, drill_state):
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

        if filters and any(rec.key not in ['"H"', '"T"', '"BE"', '"RI"', '"A"'] for rec in filters):
            print("into only filters")
            sales_performance_query = lpg_plant_queries.lpg_plant_query.get("sales_performance")
            sales_performance_query_ = sales_performance_query
            conditions = []

            # Define keys to exclude from the WHERE clause
            excluded_keys = {'"A"', '"H"', '"T"', '"BE"', '"RI"'}

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
            where_conditions = [f'"M60_LEVEL_METADATA"."FISCAL_YEAR" = {fiscal_year_start}']
            select_columns = [
                'SUM(ROUND("M60_LEVEL_METADATA"."NETWEIGHT_TMT")) AS "ACTUAL_TMT_SALES"',
                '"M60_LEVEL_METADATA"."fy_month" AS "fy_month"',
                'TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", \'Month\'), \'Mon\') AS "month_name"',
                '"M60_LEVEL_METADATA"."FISCAL_YEAR" AS "FISCAL_YEAR"',
            ]
            group_by_columns = [
                '"M60_LEVEL_METADATA"."fy_month"',
                'TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", \'Month\'), \'Mon\')',
                '"M60_LEVEL_METADATA"."FISCAL_YEAR"',
            ]

            # Build conditions based on selected keys
            if "H" in selected_keys:
                previous_year = current_year - 1
                where_conditions.append(f'"M60_LEVEL_METADATA"."FISCAL_YEAR" IN (\'FY {previous_year}-{current_year}\', \'FY {current_year}-{next_year}\')')

            if "T" in selected_keys:
                select_columns.append('SUM("M60_LEVEL_METADATA"."TARGET_QTY_TMT") AS "TARGET_QTY_TMT"')

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
                    ROUND(SUM("M60_LEVEL_METADATA"."NETWEIGHT_TMT")::numeric,2) AS "ACTUAL_TMT_SALES",
                    ROUND(SUM("M60_LEVEL_METADATA"."TARGET_QTY_TMT")::numeric,2) AS "TARGET_TMT_SALES",
                    "M60_LEVEL_METADATA"."fy_month" AS "fy_month",
                    TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", 'Month'), 'Mon') AS "month_name",
                    "M60_LEVEL_METADATA"."FISCAL_YEAR" AS "FISCAL_YEAR"
                FROM
                    "M60_LEVEL_METADATA"
                WHERE
                    "M60_LEVEL_METADATA"."NETWEIGHT_TMT" != 0 and   "M60_LEVEL_METADATA"."FISCAL_YEAR" = {fiscal_year_start}
                GROUP BY
                    "M60_LEVEL_METADATA"."fy_month",
                    TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", 'Month'), 'Mon'),
                    "M60_LEVEL_METADATA"."FISCAL_YEAR"
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
            "SalesArea_Name", "PRODUCT", "ProductName", "UOM", "FISCAL_YEAR", 
            "month_year", "month_name"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

        # Apply grouping logic based on filters
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "month_name" in filter_keys:
            # Convert full month names to short form (e.g., "January" -> "Jan")
                resp["month_name"] = resp["month_name"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )

            if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'SBU_Name' in filter_keys:
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["SBU_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["SBU_Name"], as_index=False).agg(agg_dict)
 
            if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'Zone_Name' in filter_keys:
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["Zone_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["Zone_Name"], as_index=False).agg(agg_dict)                    

            if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'Region_Name' in filter_keys:
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["Region_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["Region_Name"], as_index=False).agg(agg_dict)

            if "month_name" not in filter_keys and 'FISCAL_YEAR' not in filter_keys and 'SalesArea_Name' in filter_keys:
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["SalesArea_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["SalesArea_Name"], as_index=False).agg(agg_dict)

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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]

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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]

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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]
                
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]
                
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["month_name", "ProductName"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["month_name", "ProductName"], as_index=False).agg(agg_dict)

            elif "FISCAL_YEAR" in filter_keys and "month_name" not in filter_keys:
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name"], as_index=False).agg(agg_dict)  

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" not in filter_keys:
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]


                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name"], as_index=False).agg(agg_dict)

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name"], as_index=False).agg(agg_dict)

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and "Region_Name" not in filter_keys:
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]
                
                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg(agg_dict)

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys \
                                    and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys:
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg(agg_dict)

            elif "FISCAL_YEAR" in filter_keys and \
            "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and \
                                    "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys and "ProductName" not in filter_keys:
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
                        if rec.key == "FISCAL_YEAR":
                            # Ensure rec.value is a list of fiscal years
                            fiscal_year_values = rec.value if isinstance(rec.value, list) else [rec.value]
                            
                            # Check and add the previous fiscal year
                            if current_fiscal_year in fiscal_year_values:
                                if previous_fiscal_year not in fiscal_year_values:
                                    fiscal_year_values.append(previous_fiscal_year)
                            
                            # Assign the updated list back to rec.value
                            rec.value = fiscal_year_values
                
                    resp = resp[resp["FISCAL_YEAR"].isin([current_fiscal_year, previous_fiscal_year])]

                # If any valid keys are selected, group the data
                if selected_keys:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg(agg_dict)
                else:
                    grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg(agg_dict)

            grouped_resp["NETWEIGHT_TMT"] = grouped_resp["NETWEIGHT_TMT"].round(2)
            if "TARGET_QTY_TMT" in grouped_resp.columns:
                grouped_resp["TARGET_QTY_TMT"] = grouped_resp["TARGET_QTY_TMT"].round(2)
            # Return grouped response
            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    
    @staticmethod
    async def sales_growth(filters, drill_state):
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
    async def sales_yearly_performance(filters, drill_state):
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
    async def yearly_sales_performance(filters, drill_state):
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
    async def sales_yearly_growth(filters, drill_state):
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
    async def lpg_cdcms(filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        lpg_cdcms_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms")
        yesterday = datetime.now() - relativedelta(days=1)
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
                lpg_cdcms_query_ += ' WHERE '
                lpg_cdcms_query_ += ' AND '.join(conditions)
            lpg_cdcms_query_ += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\''
            lpg_cdcms_query_ += ' GROUP BY "ZOName", "ROName", "SAName", "Execution_Date", "JDEDistributorCode"'
        else:
            if "where" not in lpg_cdcms_query_.lower():
                lpg_cdcms_query_ += f' WHERE "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\''
            else:
                lpg_cdcms_query_ += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\''
            lpg_cdcms_query_ += ' GROUP BY "ZOName", "ROName", "SAName", "Execution_Date", "JDEDistributorCode"'
                                            
            resp = await function(query=lpg_cdcms_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
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
    async def lpg_cdcms_month(filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
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
        if filters:
            conditions = []
            for rec in filters:
                rec.value = rec.value.split(",")
                if rec.key == '"Execution_Month"':  # Only handle the month_name case separately
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
            lpg_cdcms_month_query_ += f' AND "ZOName"  NOT IN (\'Null\')'
            lpg_cdcms_month_query_ += ' GROUP BY "Month_No", "Execution_Month", "JDEDistributorCode", "ZOName", "ROName", "SAName"'
        else:
            if "where" not in lpg_cdcms_month_query_.lower():   
                lpg_cdcms_month_query_ += f' WHERE "ZOName"  NOT IN (\'Null\')'
            else:
                lpg_cdcms_month_query_ += f' AND "ZOName"  NOT IN (\'Null\')'
            lpg_cdcms_month_query_ += ' GROUP BY "Month_No", "Execution_Month", "JDEDistributorCode", "ZOName", "ROName", "SAName"'
            resp = await function(query=lpg_cdcms_month_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": resp}
            resp = resp.sort_values("Month_No")            
            resp = resp.groupby(["Execution_Month"], as_index=False).agg({
                    "Total Sales": lambda x: x.sum() / 10000000
                })
            # Fill missing values for numerical columns
            for each_float_col in [
                "Total Sales"
            ]:
                if each_float_col in resp.columns:
                    resp[each_float_col] = resp[each_float_col].fillna(0.0)

            # Fill missing values for string columns
            for each_str_col in [
                "Month_No", "Execution_Month", "ZOName"
            ]:
                if each_str_col in resp.columns:
                    resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

            return {"status": True, "message": "success", "data": resp}
        
        print("*"*50)
        print("BaseQuery :",lpg_cdcms_month_query_)
        print("*"*50)
        # Execute the query
        resp = await function(query=lpg_cdcms_month_query_)
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')

        # Fill missing values for numerical columns
        for each_float_col in [
            "Total Sales"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "Month_No", "Execution_Month", "ZOName"
        ]:
            if each_str_col in resp.columns:
                resp[each_str_col] = resp[each_str_col].fillna('').astype(str)

        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            if "Execution_Month" in filter_keys:
            # Convert full month names to short form (e.g., "January" -> "Jan")
                resp["Execution_Month"] = resp["Execution_Month"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )
            if "Execution_Month" in filter_keys and "ZOName" not in filter_keys:
                grouped_resp = resp.groupby(["Execution_Month", "ZOName"], as_index=False).agg({
                    "Total Sales": lambda x: x.sum() / 10000000
                })
            elif "Execution_Month" in filter_keys and "ZOName" in filter_keys and "ROName" not in filter_keys:
                grouped_resp = resp.groupby(["Execution_Month", "ZOName","ROName"], as_index=False).agg({
                    "Total Sales": lambda x: x.sum() / 10000000
                })
            elif "Execution_Month" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" not in filter_keys:
                grouped_resp = resp.groupby(["Execution_Month", "ZOName","ROName","SAName"], as_index=False).agg({
                    "Total Sales": lambda x: x.sum() / 10000000
                })            
            elif "Execution_Month" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "DistributorName" not in filter_keys:
                grouped_resp = resp.groupby(["Execution_Month", "ZOName","ROName","SAName","DistributorName"],
                as_index=False).agg({
                    "Total Sales": lambda x: x.sum() / 10000000
                    })
            if grouped_resp is not None:
                grouped_resp['Total Sales'] = grouped_resp['Total Sales'].round(2)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}
        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    @staticmethod
    async def cdcms_order_source(filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        yesterday = datetime.now() - relativedelta(days=1)
        cdcms_order_source_query_ = lpg_plant_queries.lpg_plant_query.get("cdcms_order_source")
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
                cdcms_order_source_query_ += ' WHERE '
                cdcms_order_source_query_ += ' AND '.join(conditions)
            cdcms_order_source_query_ += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\''
            cdcms_order_source_query_ += ' GROUP BY "OrderSourceName", "ZOName", "ROName", "SAName", "Execution_Date", "JDEDistributorCode"'
        else:      
            if "where" not in cdcms_order_source_query_.lower():
                cdcms_order_source_query_ += f' WHERE "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            else:
                cdcms_order_source_query_ += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            cdcms_order_source_query_ += ' GROUP BY "OrderSourceName", "ZOName", "ROName", "SAName", "Execution_Date", "JDEDistributorCode"'

            resp = await function(query=cdcms_order_source_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
            
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
    async def overall_pending_pmuy_nmpuy(filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        yesterday = datetime.now() - relativedelta(days=1)
        lpg_pending_query_ = lpg_plant_queries.lpg_plant_query.get("overall_pending_pmuy_nmpuy")
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
                lpg_pending_query_  += ' WHERE '
                lpg_pending_query_  += ' AND '.join(conditions)
            lpg_pending_query_  += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\''
            lpg_pending_query_  += ' GROUP BY "Execution_Date","ZOName" ,"ROName","SAName","ConsumerType" ,"JDEDistributorCode"'
        else:
            if "where" not in lpg_pending_query_.lower():                
                lpg_pending_query_  += f' WHERE "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            else:
                lpg_pending_query_  += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            lpg_pending_query_  += ' GROUP BY "Execution_Date","ZOName" ,"ROName","SAName","ConsumerType" ,"JDEDistributorCode"'
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
    async def lpg_cdcms_ageing(filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        lpg_pending_query_ = lpg_plant_queries.lpg_plant_query.get("lpg_cdcms_ageing")
        yesterday = datetime.now() - relativedelta(days=1)
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
                lpg_pending_query_  += ' WHERE '
                lpg_pending_query_  += ' AND '.join(conditions)
            lpg_pending_query_  += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN ( \'Null\')'
            lpg_pending_query_  += ' GROUP BY "Execution_Date", "ZOName" ,"ROName","SAName","ConsumerType" ,"JDEDistributorCode" '
        else:
            if "where" not in lpg_pending_query_.lower():                
                lpg_pending_query_  += f' WHERE "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
            else:
                lpg_pending_query_  += f' AND "Execution_Date"::DATE = \'{yesterday.strftime("%Y-%m-%d")}\' AND "ZOName"  NOT IN (\'Null\')'
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
    async def total_suvidha(filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        total_suvidha_query_ = lpg_plant_queries.lpg_plant_query.get("total_suvidha")
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
    async def carry_forward_analysis(filters, drill_state):
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
    async def location_wise_distribution(filters, drill_state):
        location_wise_distribution_query = lpg_plant_queries.lpg_plant_query.get("location_wise_distribution")
        location_wise_distribution_query_ = location_wise_distribution_query
        if filters:
            location_wise_distribution_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(location_wise_distribution_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(location_wise_distribution_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(location_wise_distribution_query)
        data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        return {"status": True, "message": "success", "data": data}
    
    @staticmethod
    async def cumulative_sales_pmuy_npmuy(filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        current_date = datetime.now()
        if current_date.month >= 4:  # If April or later, financial year starts this year
            start_year = current_date.year
            end_year = current_date.year + 1
        else:  # If before April, financial year started last year
            start_year = current_date.year - 1
            end_year = current_date.year
        # Define financial year start and end dates
        financial_year_start = f"{start_year}-04-01 00:00:00"
        financial_year_end = f"{end_year}-03-31 23:59:59"
        cumulative_sales_pmuy_npmuy_query_ = lpg_plant_queries.lpg_plant_query.get("cumulative_sales_pmuy_npmuy")
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
                cumulative_sales_pmuy_npmuy_query_ += ' WHERE '
                cumulative_sales_pmuy_npmuy_query_ += ' AND '.join(conditions)
            
            cumulative_sales_pmuy_npmuy_query_ += f' AND "Execution_Date"::TIMESTAMP BETWEEN \'{financial_year_start}\' AND \'{financial_year_end}\''
            cumulative_sales_pmuy_npmuy_query_ += ' GROUP BY "ConsumerType", "ZOName", "ROName", "SAName", "Execution_Date", "JDEDistributorCode"'
        else:
            if "where" in cumulative_sales_pmuy_npmuy_query_.lower():
                cumulative_sales_pmuy_npmuy_query_ += f' WHERE "Execution_Date"::TIMESTAMP BETWEEN \'{financial_year_start}\' AND \'{financial_year_end}\''
            else:
                cumulative_sales_pmuy_npmuy_query_ += f' AND "Execution_Date"::TIMESTAMP BETWEEN \'{financial_year_start}\' AND \'{financial_year_end}\''
            cumulative_sales_pmuy_npmuy_query_ += ' GROUP BY "ConsumerType", "ZOName", "ROName", "SAName", "Execution_Date", "JDEDistributorCode"'
                                 
            resp = await function(query=cumulative_sales_pmuy_npmuy_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)
            if resp.empty:
                return {"status": True, "message": "success", "data": []}
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
        if resp.empty:
            return {"status": True, "message": "success", "data": []}
        resp = pd.merge(resp, df, on='JDEDistributorCode', how='left')        
        resp["Execution_Date"] = pd.to_datetime(resp["Execution_Date"], errors="coerce")
        resp = resp[
            (resp["Execution_Date"] >= financial_year_start) &
            (resp["Execution_Date"] <= financial_year_end)
        ]
        # Fill missing values for numerical columns
        for each_float_col in [
            "Sales"
        ]:
            if each_float_col in resp.columns:
                resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "ConsumerType","ZOName","ROName","SAName","JDEDistributorCode"
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
            
            elif "ConsumerType" in filter_keys and "ZOName" in filter_keys and "ROName" in filter_keys and "SAName" in filter_keys and "JDEDistributorCode" not in filter_keys:
                grouped_resp = resp.groupby(["ConsumerType","ZOName","ROName","SAName","JDEDistributorCode"],
                as_index=False).agg({
                    "Sales": lambda x: x.sum() / 10000000
                    })

            if grouped_resp is not None:
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
    
    @staticmethod
    async def overall_ctc_statistics(filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")
        if filters:
            overall_ctc_statistics_query = lpg_plant_queries.lpg_plant_query.get("overall_ctc_statistics")
            overall_ctc_statistics_query_ = overall_ctc_statistics_query
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
            overall_ctc_statistics_query_  += f' AND "ZOName"  NOT IN ( \'Null\')'
            overall_ctc_statistics_query_ += ' GROUP BY "Category", "ZOName", "ROName", "SAName", "JDEDistributorCode"'
        else:
            overall_ctc_statistics_query_ = f'''
                select 
                    sum("ACTCCount") as "ACTC",
                    sum("BCTCCount") as "BCTC",
                    sum("NCTCCount") as "NCTC",
                    "Category" as "Category" 
                from
	                "LPG_CONSUMERS_SUMMARY" 
                where
	                "Category"  IN ('Domestic') AND "CategoryStatus"  IN ('Active') AND "ZOName"  NOT IN ('Null')
                group by
	                "Category"
            '''
            print("overall_ctc_statistics_query_",overall_ctc_statistics_query_)
            resp = await function(query=overall_ctc_statistics_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)

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
        print("overall_ctc_statistics_query_---->",overall_ctc_statistics_query_)
        resp = await function(query=overall_ctc_statistics_query_)        
        # Convert the response to a DataFrame for further processing
        resp = pd.DataFrame(resp)
        print("resp :", resp)
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
            
            print("grouped_resp --> ", grouped_resp)
            if grouped_resp is not None:
                print("grouped_resp  -> ", grouped_resp)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        # If no filters are applied, return the default response
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}

    @staticmethod
    async def overall_safety_check_pending(filters, drill_state):
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        df = pd.read_csv("/opt/ceg/algo/DistributorMappings.csv")

        if filters:
            overall_safety_check_pending_query = lpg_plant_queries.lpg_plant_query.get("overall_safety_check_pending")
            overall_safety_check_pending_query_ = overall_safety_check_pending_query
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
            overall_safety_check_pending_query_  += f' AND "ZOName"  NOT IN (\'Null\')'
            overall_safety_check_pending_query_ += ' GROUP BY "SubCategory", "ZOName", "ROName", "SAName", "JDEDistributorCode"'
        else:
            overall_safety_check_pending_query_ = f'''
                select 
                    sum("SafetyCheckPending") as "SafetyCheckPending",
                    "SubCategory"
                from
	                "LPG_CONSUMERS_SUMMARY" 
                where
	                "Category" IN ('Domestic') AND "ZOName"  NOT IN ('Null')
                group by
	                "SubCategory"
            '''
            resp = await function(query=overall_safety_check_pending_query_)
            # Convert the response to a DataFrame for further processing
            resp = pd.DataFrame(resp)

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
