import urdhva_base

# Todo:- import all widget action modules here
widget_mapping = {
    'lpg_production': {'module_name': '', 'func_name': ''},
    'tibco_lubes_production': {'module_name': '', 'func_name': ''},
    'lpg_ca_cdm': {'module_name': '', 'func_name': ''}
}


class WidgetActions:
    @staticmethod
    async def execute_widget_action(func_name, filters):
        if func_name not in widget_mapping:
            return False, "Not Supported"
        return await eval(f"{widget_mapping[func_name]['module_name']}."
                          f"{widget_mapping[func_name]['func_name']}")(filters)


