import urdhva_base
import utilities.helpers as helpers
import orchestrator.dbconnector.connector_factory as connector_factory
import orchestrator.dbconnector.widget_actions.lpg_plant_queries as lpg_plant_queries
from orchestrator.dashboard.chart_factory import charts_functions as execution_helpers
from orchestrator.dbconnector.widget_actions import widget_actions
import psycopg2
from psycopg2 import sql, errors
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
        if filters:
            production_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(production_query, filters, drill_state )
        try:
            prod_keys, production_res = connector_factory.PostgreSQLConnector().execute_query(production_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            prod_keys, production_res = connector_factory.PostgreSQLConnector().execute_query(production_query)
        production_data = connector_factory.PostgreSQLConnector().process_recommendations(prod_keys, production_res)
        total_prod = production_data[0]["total_production"]
        avg_prod = production_data[0]["average_production"]

        rejection_query = lpg_plant_queries.lpg_plant_query.get("rejection_query")
        if filters:
            rejection_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(rejection_query, filters, drill_state )
        try:
            rej_keys, rejection_res = connector_factory.PostgreSQLConnector().execute_query(rejection_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            rej_keys, rejection_res = connector_factory.PostgreSQLConnector().execute_query(rejection_query)
        cs_rejection_data = connector_factory.PostgreSQLConnector().process_recommendations(rej_keys, rejection_res)
        cs_rejection_data = cs_rejection_data[0]["cs_rejections"]
        
        total_gd_rejection = lpg_plant_queries.lpg_plant_query.get("total_gd_rejection")
        if filters:
            total_gd_rejection_ = await widget_actions.WidgetActions.apply_filter_drilldown(total_gd_rejection, filters, drill_state )
        try:
            gd_rej_keys, gd_rejection_res = connector_factory.PostgreSQLConnector().execute_query(total_gd_rejection_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            gd_rej_keys, gd_rejection_res = connector_factory.PostgreSQLConnector().execute_query(total_gd_rejection)
        gd_rejection_data = connector_factory.PostgreSQLConnector().process_recommendations(gd_rej_keys, gd_rejection_res)
        gd_rejection_data = gd_rejection_data[0]["Percentage"]

        total_pt_rejection = lpg_plant_queries.lpg_plant_query.get("total_pt_rejection")
        if filters:
            total_pt_rejection_ = await widget_actions.WidgetActions.apply_filter_drilldown(total_pt_rejection, filters, drill_state )
        try:
            pt_rej_keys, pt_rejection_res = connector_factory.PostgreSQLConnector().execute_query(total_pt_rejection_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            pt_rej_keys, pt_rejection_res = connector_factory.PostgreSQLConnector().execute_query(total_pt_rejection)
        pt_rejection_data = connector_factory.PostgreSQLConnector().process_recommendations(pt_rej_keys, pt_rejection_res)
        pt_rejection_data = pt_rejection_data[0]["AVG(sortoutpercentage)/100"]

        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data":
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
        if filters:
            productivity_cyl_per_hour_ = await widget_actions.WidgetActions.apply_filter_drilldown(productivity_cyl_per_hour, filters, drill_state )
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(productivity_cyl_per_hour_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(productivity_cyl_per_hour)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}

    @staticmethod
    async def get_rejections_by_zones(filters, drill_state):
        rejections_by_zones_query = lpg_plant_queries.lpg_plant_query.get("rejections_by_zones")
        if filters:
            rejections_by_zones_query = await widget_actions.WidgetActions.apply_filter_drilldown(rejections_by_zones_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(daily_prod_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(daily_prod_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_daily_productivity_cyl_per_hour(filters, drill_state):
        daily_prod_query = lpg_plant_queries.lpg_plant_query.get("daily_productivity_cyl_per_hour")
        if filters:
            daily_prod_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(daily_prod_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(daily_prod_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(daily_prod_query)
        print(res)
        keys, res = connector_factory.PostgreSQLConnector().execute_query(daily_prod_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_cyl_rejection_in_check_scale(filters, drill_state):
        cyl_rej_query = lpg_plant_queries.lpg_plant_query.get("cyl_rejection_in_check_scale")
        if filters:
            cyl_rej_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(cyl_rej_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_rej_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_rej_query)
        print(res)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}

    @staticmethod
    async def get_cyl_rejection_in_gd(filters, drill_state):
        cyl_rej_query = lpg_plant_queries.lpg_plant_query.get("cyl_rejection_in_gd")
        print("*"*100)
        if filters:
            cyl_rej_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(cyl_rej_query, filters, drill_state)
        try:
            print("cyl_rej_query updated: ", cyl_rej_query_)
            print("-"*100)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_rej_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            print("cyl_rej_query original: ", cyl_rej_query)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_rej_query)
        print(res)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_cyl_rejection_in_pt(filters, drill_state):
        cyl_rej_query = lpg_plant_queries.lpg_plant_query.get("cyl_rejection_in_pt")
        if filters:
            cyl_rej_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(cyl_rej_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_rej_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_rej_query)
        print(res)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_cyl_count_by_carousel(filters, drill_state):
        cyl_carousel_query = lpg_plant_queries.lpg_plant_query.get("cyl_count_by_carousel")
        if filters:
            cyl_carousel_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(cyl_carousel_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_carousel_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_carousel_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_cyl_count_by_zone(filters, drill_state):
        cyl_zone_query = lpg_plant_queries.lpg_plant_query.get("cyl_count_by_zone")
        if filters:
            cyl_zone_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(cyl_zone_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_zone_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cyl_zone_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_bottom_cs_plants(filters, drill_state):
        cs_plants_query = lpg_plant_queries.lpg_plant_query.get("bottom_cs_plants")
        if filters:
            cs_plants_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(cs_plants_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cs_plants_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(cs_plants_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_bottom_gd_plants(filters, drill_state):
        gd_plants_query = lpg_plant_queries.lpg_plant_query.get("bottom_gd_plants")
        if filters:
            gd_plants_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(gd_plants_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(gd_plants_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(gd_plants_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_bottom_pt_plants(filters, drill_state):
        pt_plants_query = lpg_plant_queries.lpg_plant_query.get("bottom_pt_plants")
        if filters:
            pt_plants_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(pt_plants_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(pt_plants_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(pt_plants_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_bottom_productivity_plants(filters, drill_state):
        prod_plants_query = lpg_plant_queries.lpg_plant_query.get("bottom_productivity_plants")
        if filters:
            prod_plants_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(prod_plants_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(prod_plants_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(prod_plants_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_productivity_by_zone(filters, drill_state):
        prod_by_zone_query = lpg_plant_queries.lpg_plant_query.get("productivity_by_zone")
        if filters:
            prod_by_zone_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(prod_by_zone_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(prod_by_zone_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(prod_by_zone_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_productivity_by_location(filters, drill_state):
        prod_by_location_query = lpg_plant_queries.lpg_plant_query.get("productivity_by_location")
        if filters:
            prod_by_location_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(prod_by_location_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(prod_by_location_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(prod_by_location_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_consolidated_table(filters, drill_state):
        consolidated_tab_query = lpg_plant_queries.lpg_plant_query.get("consolidated_table")
        if filters:
            consolidated_tab_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(consolidated_tab_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(consolidated_tab_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(consolidated_tab_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}
    
    @staticmethod
    async def get_top_productivity_plants(filters, drill_state):
        top_prod_query = lpg_plant_queries.lpg_plant_query.get("top_productivity_plants")
        if filters:
            top_prod_query_ = await widget_actions.WidgetActions.apply_filter_drilldown(top_prod_query, filters, drill_state)
        try:
            keys, res = connector_factory.PostgreSQLConnector().execute_query(top_prod_query_)
        except psycopg2.errors.UndefinedColumn as e:
            print(e)
            keys, res = connector_factory.PostgreSQLConnector().execute_query(top_prod_query)
        data = connector_factory.PostgreSQLConnector().process_recommendations(keys, res)
        if not drill_state:
            drill_state = "column"
        drill_down_column = await LPGPlantActions.get_next_level_drill_params(drill_state)
        return {"status": True, "message": "success", "data": data,
                "drill_down_column": drill_down_column}