import urdhva_base
import utilities.helpers as helpers
import orchestrator.dbconnector.connector_factory as connector_factory
import orchestrator.dbconnector.widget_actions.lpg_plant_queries as lpg_plant_queries
from orchestrator.dashboard.chart_factory import charts_functions as execution_helpers

class LPGPlantActions:

    @staticmethod
    async def get_next_level_drill_params(present_group):
        next_level_drill_params = {
                                   "column": "zone",
                                   "zone": "short_name",
                                   "short_name": "name",
                                   "name": "carousel",
                                   "carousel": ""}
        return next_level_drill_params.get(present_group, "")

    @staticmethod
    async def get_production_details(filters, drill_state):
        production_query = lpg_plant_queries.lpg_plant_query.get("production_query")
        print(production_query)
        prod_keys, production_res = connector_factory.PostgreSQLConnector().execute_query(production_query)
        production_data = connector_factory.PostgreSQLConnector().process_recommendations(prod_keys, production_res)
        total_prod = production_data[0]["total_production"]
        avg_prod = production_data[0]["average_production"]

        rejection_query = lpg_plant_queries.lpg_plant_query.get("rejection_query")
        rej_keys, rejection_res = connector_factory.PostgreSQLConnector().execute_query(rejection_query)
        cs_rejection_data = connector_factory.PostgreSQLConnector().process_recommendations(rej_keys, rejection_res)
        cs_rejection_data = cs_rejection_data[0]["cs_rejections"]
        
        total_gd_rejection = lpg_plant_queries.lpg_plant_query.get("total_gd_rejection")
        gd_rej_keys, gd_rejection_res = connector_factory.PostgreSQLConnector().execute_query(total_gd_rejection)
        gd_rejection_data = connector_factory.PostgreSQLConnector().process_recommendations(gd_rej_keys, gd_rejection_res)
        gd_rejection_data = gd_rejection_data[0]["Percentage"]

        total_pt_rejection = lpg_plant_queries.lpg_plant_query.get("total_pt_rejection")
        pt_rej_keys, pt_rejection_res = connector_factory.PostgreSQLConnector().execute_query(total_pt_rejection)
        pt_rejection_data = connector_factory.PostgreSQLConnector().process_recommendations(pt_rej_keys, pt_rejection_res)
        pt_rejection_data = pt_rejection_data[0]["AVG(sortoutpercentage)/100"]

        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data":
                    {
                      "Total Production (MT)": total_prod,
                      "Total Productivity (Cyl/Hr)": avg_prod,
                      "Total CS Rejection": cs_rejection_data,
                      "Total GD Rejection": gd_rejection_data,
                      "Total PT Rejection": pt_rejection_data
                    },
                "drill_down_column": drill_down_column
              }
    
    @staticmethod
    async def get_productivity_cyl_per_hour(filters, drill_state):
        productivity_cyl_per_hour = lpg_plant_queries.lpg_plant_query.get("productivity_cyl_per_hour")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(productivity_cyl_per_hour)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}

    @staticmethod
    async def get_rejections_by_zones(filters, drill_state):
        rejections_by_zones_query = lpg_plant_queries.lpg_plant_query.get("rejections_by_zones")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(rejections_by_zones_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_daily_productivity_cyl_per_hour(filters, drill_state):
        daily_prod_query = lpg_plant_queries.lpg_plant_query.get("daily_productivity_cyl_per_hour")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(daily_prod_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_cyl_rejection_in_check_scale(filters, drill_state):
        cyl_rej_query = lpg_plant_queries.lpg_plant_query.get("cyl_rejection_in_check_scale")
        print(cyl_rej_query)
        keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_rej_query)
        print(res)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}

    @staticmethod
    async def get_cyl_rejection_in_gd(filters, drill_state):
        cyl_rej_query = lpg_plant_queries.lpg_plant_query.get("cyl_rejection_in_gd")
        print(cyl_rej_query)
        keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_rej_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_cyl_rejection_in_pt(filters, drill_state):
        cyl_rej_query = lpg_plant_queries.lpg_plant_query.get("cyl_rejection_in_pt")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_rej_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_cyl_count_by_carousel(filters, drill_state):
        cyl_carousel_query = lpg_plant_queries.lpg_plant_query.get("cyl_count_by_carousel")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_carousel_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_cyl_count_by_zone(filters, drill_state):
        cyl_zone_query = lpg_plant_queries.lpg_plant_query.get("cyl_count_by_zone")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_zone_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_bottom_cs_plants(filters, drill_state):
        cs_plants_query = lpg_plant_queries.lpg_plant_query.get("bottom_cs_plants")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(cs_plants_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_bottom_gd_plants(filters, drill_state):
        gd_plants_query = lpg_plant_queries.lpg_plant_query.get("bottom_gd_plants")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(gd_plants_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_bottom_pt_plants(filters, drill_state):
        pt_plants_query = lpg_plant_queries.lpg_plant_query.get("bottom_pt_plants")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(pt_plants_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_bottom_productivity_plants(filters, drill_state):
        prod_plants_query = lpg_plant_queries.lpg_plant_query.get("bottom_productivity_plants")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(prod_plants_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_productivity_by_zone(filters, drill_state):
        prod_by_zone_query = lpg_plant_queries.lpg_plant_query.get("productivity_by_zone")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(prod_by_zone_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_productivity_by_location(filters, drill_state):
        prod_by_location_query = lpg_plant_queries.lpg_plant_query.get("productivity_by_location")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(prod_by_location_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_consolidated_table(filters, drill_state):
        consolidated_tab_query = lpg_plant_queries.lpg_plant_query.get("consolidated_table")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(consolidated_tab_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_top_productivity_plants(filters, drill_state):
        top_prod_query = lpg_plant_queries.lpg_plant_query.get("top_productivity_plants")
        keys, res = connector_factory.PostgreSQLConnector().execute_query(top_prod_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"data": data,
                "drill_down_column": drill_down_column}