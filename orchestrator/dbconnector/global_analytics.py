import urdhva_base
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
        analytics_query = lpg_plant_queries.lpg_plant_query.get("analytics")
        analytics_query_ = analytics_query
        if filters:
            analytics_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(analytics_query, filters, drill_state)
            print("analytics_query_ --> ", analytics_query_)
        try:
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(analytics_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector('LPG_PLANT').execute_query(analytics_query)
        data = connector_factory.PostgreSQLConnector('LPG_PLANT').process_recommendations(keys, res)
        print("data --> ", data)
        # Initialize counters for alert distribution and top alerts
        critical_alerts = 0
        medium_alerts = 0
        low_alerts = 0
        top_alerts = {
            'Tank Level Critical': 0,
            'Pump Malfunction': 0,
            'Dispenser Error': 0,
            'Flow Rate Alert': 0,
            'Temperature Warning': 0,
            'Power Issue': 0,
            'Sensor Malfunction': 0,
            'Nozzle Error': 0,
            'Maintenance Alert': 0,
            'Overfill Prevention': 0
        }
        
        total_alerts = 0
        active_locations = 0
        inactive_locations = 0
        
        # Process the data to populate the counts
        for entry in data:
            alert_count = entry['alert_count']
            severity_count = entry['severity_count']
            severity = entry['severity']
            alert_status = entry['alert_status']  # Get the alert status
            location_name = entry['location_name']
            
            # Update the total alert count
            total_alerts += alert_count
            
            # Update the severity-based distribution
            if severity == 'Critical':
                critical_alerts += alert_count
            elif severity == 'Medium':
                medium_alerts += alert_count
            elif severity == 'Low':
                low_alerts += alert_count
            
            # Track active or inactive locations based on alert_status
            if alert_status == "Open":
                active_locations += alert_count
            elif alert_status == "Close":
                inactive_locations += alert_count
            
            # Track top alerts (alert_type can be empty, handle it safely)
            alert_type = entry.get("alert_type", "Unknown")  # Default to 'Unknown' if not present
            if alert_type in top_alerts:
                top_alerts[alert_type] += alert_count
        
        # Prepare the final result
        result = {
            "status": True,
            "message": "success",
            "data": {
                "activeLocations": active_locations,
                "inactiveLocations": inactive_locations,
                "totalAlerts": f"{total_alerts:,}",
                "alertDistribution": [
                    {"name": "Critical", "value": critical_alerts},
                    {"name": "Medium", "value": medium_alerts},
                    {"name": "Low", "value": low_alerts}
                ],
                "top10Alerts": [
                    {"name": name, "value": value} for name, value in sorted(top_alerts.items(), key=lambda x: x[1], reverse=True)[:10]
                ]
            }
        }
        
        return result
        