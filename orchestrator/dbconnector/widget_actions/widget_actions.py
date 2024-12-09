import urdhva_base
from orchestrator.dbconnector.widget_actions import lpg_plant

# Todo:- import all widget action modules here
widget_mapping = {
    'lpg_production': {'module_name': 'lpg_plant', 'func_name': 'LPGPlantActions.get_production_details'},
    'lpg_productivity_cyl_per_hour':{'module_name': 'lpg_plant', 'func_name': 'LPGPlantActions.get_productivity_cyl_per_hour'},
    'get_rejections_by_zones':{},
    'get_daily_productivity_cyl_per_hour': {},
    'get_cyl_rejection_in_check_scale': {},
    'get_cyl_rejection_in_gd': {},
    'get_cyl_rejection_in_pt': {},
    'get_cyl_count_by_carousel': {},
    'get_cyl_count_by_zone': {},
    'get_bottom_cs_plants': {},
    'get_bottom_gd_plants': {},
    'get_bottom_pt_plants': {},
    'get_bottom_productivity_plants': {},
    'get_productivity_by_zone': {},
    'get_productivity_by_location': {},
    'get_consolidated_table': {},
    'get_top_productivity_plants': {},
    'tibco_lubes_production': {'module_name': '', 'func_name': ''},
    'lpg_ca_cdm': {'module_name': '', 'func_name': ''}
}


class WidgetActions:
    @staticmethod
    async def execute_widget_action(func_name, filters, drill_state):
        if func_name not in widget_mapping:
            return False, "Not Supported"
        return await eval(f"lpg_plant.LPGPlantActions.{func_name}")(filters, drill_state)
        # return await eval(f"{widget_mapping[func_name]['module_name']}."
        #                   f"{widget_mapping[func_name]['func_name']}")(filters, drill_state)


