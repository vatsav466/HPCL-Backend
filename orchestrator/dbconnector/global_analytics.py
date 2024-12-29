import urdhva_base
import json
import psycopg2
import polars as pl
import pandas as pd
from datetime import datetime
from psycopg2 import sql, errors
from collections import defaultdict
import utilities.helpers as helpers
import utilities.connection_mapping as connection_mapping
from orchestrator.dbconnector.widget_actions import widget_actions
import orchestrator.dbconnector.connector_factory as connector_factory
from api_manager.charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
import orchestrator.dbconnector.widget_actions.lpg_plant_queries as lpg_plant_queries

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
            for filter_ in filters:
                if filter_.key:
                    # Update the key of the filter to include the alias 'a.'
                    filter_.key = f"a.{filter_.key}"
                
            # After modifying the filters, send the updated filters to apply_filter_drilldown
            print("Updated filters --> ", filters)
            analytics_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(analytics_query, filters, drill_state)

            print("analytics_query_ --> ", analytics_query_)

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
                print("filter_ --> ", filter_)
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
        print("no_of_locations_query_ -> ", no_of_locations_query_)
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
        print("severity_count_query_ -> ", severity_count_query_)
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
        print("hourly_alerts_data -> ", hourly_alerts_data)
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
                    SUM(ROUND("M60_LEVEL_METADATA"."NETWEIGHT_TMT")) AS "ACTUAL_TMT_SALES",
                    SUM(ROUND("M60_LEVEL_METADATA"."TARGET_QTY_TMT")) AS "TARGET_TMT_SALES",
                    "M60_LEVEL_METADATA"."fy_month" AS "fy_month",
                    TO_CHAR(TO_DATE("M60_LEVEL_METADATA"."month_name", 'Month'), 'Mon') AS "month_name",
                    "M60_LEVEL_METADATA"."FISCAL_YEAR" AS "FISCAL_YEAR"
                FROM
                    "M60_LEVEL_METADATA"
                WHERE
                    "M60_LEVEL_METADATA"."FISCAL_YEAR" = {fiscal_year_start}
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
        print("resp df", resp)

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

        print("resp.columns --> ", resp.columns)
        # Apply grouping logic based on filters
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            print("Filter Keys:", filter_keys)  # Debugginkg
            if "month_name" in filter_keys:
            # Convert full month names to short form (e.g., "January" -> "Jan")
                resp["month_name"] = resp["month_name"].apply(
                lambda x: reverse_month_mapping.get(x, x)
            )

            if "FISCAL_YEAR" in filter_keys and "month_name" not in filter_keys:
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
                print("Group by Zone")
                grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and "Region_Name" not in filter_keys:
                print("Group by Region")
                grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys \
                                    and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys:
                print("Condition: Grouping by mzr")
                grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })

            elif "FISCAL_YEAR" in filter_keys and \
            "month_name" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and \
                                    "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys and "ProductName" not in filter_keys:
                print("Group by Product")
                grouped_resp = resp.groupby(["FISCAL_YEAR", "month_name", "SBU_Name", "Zone_Name", "Region_Name", "SalesArea_Name", "ProductName"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })

            # Return grouped response
            if grouped_resp is not None:
                print("Grouped Response -->", grouped_resp)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}


        # If no filters are applied, return the default response
        print("Default Response -->", resp)
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

        if filters:
            sales_growth_query = lpg_plant_queries.lpg_plant_query.get("sales_growth")
            sales_growth_query_ = sales_growth_query

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
            # Fallback query if no filters are provided
            sales_growth_query_ = """
                SELECT 
                    MAX(ROUND("MOM_LEVEL_FINAL_SALES"."sum_total_sales")) AS "total_sales",
                    "MOM_LEVEL_FINAL_SALES"."fiscal_year" AS "fiscal_year",
                    "MOM_LEVEL_FINAL_SALES"."month_name" AS "month_name"
                FROM
                    "hpcl_ceg"."public"."MOM_LEVEL_FINAL_SALES"
                GROUP BY
                    "MOM_LEVEL_FINAL_SALES"."fiscal_year", "MOM_LEVEL_FINAL_SALES"."month_name"
                ORDER BY
                    "MOM_LEVEL_FINAL_SALES"."fiscal_year" ASC
            """

            resp = await function(query=sales_growth_query_)
            return {"status": True, "message": "success", "data": resp}
        resp = await function(query=sales_growth_query_)
        resp = pd.DataFrame(resp)

        # Fill missing values for numeric columns
        for each_float_col in ["sum_total_sales", "total_sales"]:
            resp[each_float_col] = resp[each_float_col].fillna(0.0)

        # Fill missing values for string columns
        for each_str_col in [
            "month_name", "fiscal_month", "SBU_CD", "ZONE_CD", "RO_CD", "SA_CD", 
            "MATERIAL_CD", "fiscal_year", "month_year", "percentage_change"
        ]:
            resp[each_str_col] = resp[each_str_col].fillna('').astype(str)
        
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            print("Filter Keys:", filter_keys)  # Debugginkg

            if "month_name" in filter_keys and "ZONE_CD" not in filter_keys:
                print("Group by fiscal_year and ZONE_CD")
                grouped_resp = resp.groupby(["fiscal_year", "ZONE_CD"], as_index=False).agg({
                    "sum_total_sales": lambda x: round(x.max()),
                })
            
            elif "month_name" in filter_keys and "ZONE_CD" in filter_keys and "RO_CD" not in filter_keys:
                print("Group by fiscal_year and RO_CD")
                grouped_resp = resp.groupby(["fiscal_year", "RO_CD"], as_index=False).agg({
                    "sum_total_sales": lambda x: round(x.max()),
                })
            
            if grouped_resp is not None:
                print("Grouped Response -->", grouped_resp)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}

        print("resp -->  ", resp)
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
        print("Filter Keys:", filter_keys)  # Debugginkg

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
        print("resp df", resp)

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

        print("resp.columns --> ", resp.columns)
        # Apply grouping logic based on filters
        if filters:
            grouped_resp = None
            filter_keys = [rec.key.strip('"') for rec in filters]
            print("Filter Keys:", filter_keys)  # Debugginkg

            if "FISCAL_YEAR" in filter_keys and "SBU_Name" not in filter_keys:
                grouped_resp = resp.groupby(["FISCAL_YEAR", "SBU_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" not in filter_keys:
                print("Group by Zone")
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and "Region_Name" not in filter_keys:
                print("Group by Region")
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name","Region_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum"
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys \
                    and "Region_Name" in filter_keys and "SalesArea_Name" not in filter_keys:
                print("Condition: Grouping by mzr")
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name","Region_Name","SalesArea_Name"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })

            elif "FISCAL_YEAR" in filter_keys and "SBU_Name" in filter_keys and "Zone_Name" in filter_keys and \
                    "Region_Name" in filter_keys and "SalesArea_Name" in filter_keys and "ProductName" not in filter_keys:
                print("Group by Product")
                grouped_resp = resp.groupby(["FISCAL_YEAR","SBU_Name","Zone_Name","Region_Name","SalesArea_Name","ProductName"], as_index=False).agg({
                    "NETWEIGHT_TMT": "sum",
                    "TARGET_QTY_TMT": "sum",
                })


            # Return grouped response
            if grouped_resp is not None:
                print("Grouped Response -->", grouped_resp)
                return {"status": True, "message": "success", "data": grouped_resp.to_dict(orient='records')}


        # If no filters are applied, return the default response
        print("Default Response -->", resp)
        return {"status": True, "message": "success", "data": resp.to_dict(orient='records')}
