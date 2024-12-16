import urdhva_base
from collections import defaultdict
import utilities.helpers as helpers
import orchestrator.dbconnector.connector_factory as connector_factory
import orchestrator.dbconnector.widget_actions.lpg_plant_queries as lpg_plant_queries
from orchestrator.dashboard.chart_factory import charts_functions as execution_helpers
from orchestrator.dbconnector.widget_actions import widget_actions
import psycopg2
from psycopg2 import sql, errors

class GlobalAnalytics:
    @staticmethod
    async def analytics(filters, drill_state):
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
        # return {"status": True, "message": "success", "data": data}


        analytics_query = lpg_plant_queries.lpg_plant_query.get("analytics")
        analytics_query_ = analytics_query

        # Apply filters if provided
        if filters:
            # Ensure filters are qualified with the correct table alias
            for filter_ in filters:
                if filter_.key == "bu":
                    filter_key = f"a.{filter_.key}"  # Qualify with the table alias
                    filter_condition = f" WHERE {filter_key} = '{filter_.value}'"
                    analytics_query_ = analytics_query.replace("GROUP BY", f"{filter_condition} GROUP BY")
                    break

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
        print("data --> ", data)

        active_locations = set()
        inactive_locations = set()
        total_alerts = 0
        alert_distribution = defaultdict(int)
        top_alerts = defaultdict(int)

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
            alert_distribution[interlock_name] += severity_count

            # Update top alerts by interlock name
            top_alerts[interlock_name] += severity_count

        # Format the output
        result = {
            "activeLocations": len(active_locations),
            "inactiveLocations": len(inactive_locations),
            "totalAlerts": f"{total_alerts:,}",
            "alertDistribution": [
                {"name": interlock_name, "value": severity_count}
                for interlock_name, severity_count in alert_distribution.items()
            ],
            "top10Alerts": [
                {"name": name, "value": value}
                for name, value in sorted(top_alerts.items(), key=lambda x: x[1], reverse=True)[:10]
            ],
            "no_of_locations": no_of_locations_data
        }

        return {"status": True, "message": "Success", "data": result}
    
    @staticmethod
    async def alert_ageing(filters, drill_state):
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
                    