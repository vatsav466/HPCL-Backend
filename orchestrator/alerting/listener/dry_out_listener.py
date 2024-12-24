import urdhva_base
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from orchestrator.alerting.alert_manager import create_alert
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams


class DryoutCollector:
    @classmethod
    async def get_dry_out_data(cls):
        # Query to fetch dry out locations, intraday dry-out and potential dry out location
        query = """SELECT 
    site_id, 
    fcc_code, 
    item_name, 
    COUNT(DISTINCT tank_no) AS tank_cnt, 
    CASE 
        -- Already Dried-Out locations
        WHEN SUM(pumpable_stock) <= 0 THEN 1 
        -- Intraday locations
        WHEN SUM(pumpable_stock) < (SUM(sch.avgsales_7days) / 7) THEN 2 
        -- Will get dried out in 3 days
        WHEN SUM(pumpable_stock) BETWEEN (SUM(sch.avgsales_7days) / 7) AND (SUM(sch.avgsales_7days) / 7) * 3 THEN 3 
        -- Will get dried out in 3 to 6 days
        WHEN SUM(pumpable_stock) BETWEEN (SUM(sch.avgsales_7days) / 7) * 3 AND (SUM(sch.avgsales_7days) / 7) * 6 THEN 4 
        -- Dried out in greater than 6 days
        ELSE 6 
    END AS status 
FROM 
    sch_inventory_forecast_dashboard sch 
WHERE 
    sch.volume > 0 
GROUP BY 
    site_id, 
    fcc_code, 
    item_name 
ORDER BY 
    site_id, 
    fcc_code, 
    item_name;
"""

        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("cris", "3")
        Charts_Connection_Vault_RoutingParams.action = 'get_data'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        schema = connection_mapping.schema_mapping.get("cris", "HPCL_HOS")
        table = connection_mapping.table_mapping.get("dry_out", "sch_inventory_forecast_dashboard")
        records = await function(schema_name=schema, table_name=table, query=query)
        return records
