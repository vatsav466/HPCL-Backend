import urdhva_base
import re
from orchestrator.dbconnector import global_analytics
from orchestrator.dbconnector.widget_actions import lpg_plant

lpg_dashboard_actions = [
    'get_production_details',
    'get_productivity_cyl_per_hour',
    'get_rejections_by_zones',
    'get_daily_productivity_cyl_per_hour',
    'get_cyl_rejection_in_check_scale',
    'get_cyl_rejection_in_gd',
    'get_cyl_rejection_in_pt',
    'get_cyl_count_by_carousel',
    'get_cyl_count_by_zone',
    'get_bottom_cs_plants',
    'get_bottom_gd_plants',
    'get_bottom_pt_plants',
    'get_bottom_productivity_plants',
    'get_productivity_by_zone',
    'get_productivity_by_location',
    'get_consolidated_table',
    'get_top_productivity_plants',
    'high_alert_locations',
    'critical_alert_locations',
    'sod_terminal',
    'alert_categories',
    'tas_alerts',
    'non_tas_alerts',
    'no_of_terminals',
    'alert_ageing',
    'alert_distributions',
    'analytics',
    'no_of_locations',
    'day_wise_alerts',
    'location_severity_count'
]

# Todo:- import all widget action modules here
widget_mapping = {
    'lpg_production': {'module_name': 'lpg_plant', 'func_name': 'LPGPlantActions.get_production_details'},
    'lpg_productivity_cyl_per_hour':{'module_name': 'lpg_plant', 'func_name': 'LPGPlantActions.get_productivity_cyl_per_hour'},
    'get_production_details': {},
    'get_productivity_cyl_per_hour': {},
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
    'high_alert_locations': {},
    'critical_alert_locations': {},
    'sod_terminal': {},
    'alert_categories': {},
    'tas_alerts': {},
    'non_tas_alerts':{},
    'no_of_terminals':{},
    'alert_ageing': {},
    'alert_distributions': {},
    'analytics': {},
    'no_of_locations': {},
    'day_wise_alerts': {},
    'location_severity_count': {},
    'tibco_lubes_production': {'module_name': '', 'func_name': ''},
    'lpg_ca_cdm': {'module_name': '', 'func_name': ''}
}


class WidgetActions:
    @staticmethod
    # Safely resolve the module and function
    async def execute_widget_action(func_name, filters, drill_state):
        try:
            # Debugging: Log the input function name
            print(f"Received func_name: {func_name}")

            # Determine the module containing the function
            if hasattr(lpg_plant.LPGPlantActions, func_name):
                module = lpg_plant.LPGPlantActions
                print(f"Function {func_name} found in LPGPlantActions.")
            elif hasattr(global_analytics.GlobalAnalytics, func_name):
                module = global_analytics.GlobalAnalytics
                print(f"Function {func_name} found in GlobalAnalytics.")
            else:
                # List available functions in each module for debugging
                print(f"Available functions in LPGPlantActions: {dir(lpg_plant.LPGPlantActions)}")
                print(f"Available functions in GlobalAnalytics: {dir(global_analytics.GlobalAnalytics)}")
                raise AttributeError(f"Function {func_name} not found in either module.")

            # Retrieve the function from the resolved module
            func = getattr(module, func_name)
            print(f"Resolved function: {dir(func)}")

            # Execute the function asynchronously
            return await func(filters, drill_state)
        
        except AttributeError as e:
            # Handle case where the function name is invalid
            raise RuntimeError(
                f"Error resolving function: {func_name} not found. "
                f"Checked in LPGPlantActions: {hasattr(lpg_plant.LPGPlantActions, func_name)}, "
                f"and GlobalAnalytics: {hasattr(global_analytics.GlobalAnalytics, func_name)}. "
                f"Original error: {e}"
            )


    @staticmethod
    async def execute_cross_filters(filters):
        final_data = []
        for func in lpg_dashboard_actions:
            final_data.append({func: await eval(f"lpg_plant.LPGPlantActions.{func}")(filters, "")})
        return {"status": True, "message": "success", "data": final_data}
    
    @staticmethod
    async def generate_filter_clause(filters):
        conditions = []
        for filter_item in filters:
            filter_item = filter_item.dict()
            key = filter_item['key']
            condition = filter_item['cond']
            value = filter_item['value']

            if condition == 'equals':
                conditions.append(f"{key} = '{value}'")
            elif condition == 'prefix':
                conditions.append(f"{key} LIKE '{value}%'")
            elif condition == 'contains':
                conditions.append(f"{key} LIKE '%{value}%'")
            elif condition == 'suffix':
                conditions.append(f"{key} LIKE '%{value}'")
            elif condition == 'oneof' and isinstance(value, list):
                values = "', '".join(map(str, value))
                conditions.append(f"{key} IN ('{values}')")
            elif condition == 'pattern':
                conditions.append(f"{key} ILIKE '%{value}%'")
            elif condition == 'date_filter':
                if value == '1d':
                    conditions.append(f"{key}::DATE = CURRENT_DATE - INTERVAL '1 DAY'")
                elif value == '1w':
                    conditions.append(f"{key}::DATE >= CURRENT_DATE - INTERVAL '7 DAY'")
                elif value == '15d':
                    conditions.append(f"{key}::DATE >= CURRENT_DATE - INTERVAL '15 DAY'")
                elif value == '1m':
                    conditions.append(f"{key}::DATE >= CURRENT_DATE - INTERVAL '1 MONTH'")
            else:
                raise ValueError(f"Unsupported condition: {condition}")
        conditions_ = " AND ".join(conditions)
        print("conditions_: ", conditions_)
        return conditions_
    
    @staticmethod
    async def get_not_join_query(user_query, filters, drill_column):
        # query contains where clause, add organization id directly in the where clause
        filter_conditions = await WidgetActions.generate_filter_clause(filters)
        if re.search(r'\bwhere\b', user_query, re.IGNORECASE):
            splitted_query = re.split(r'\bwhere\b', user_query, flags=re.IGNORECASE)
            splitted_query[1] = filter_conditions + " AND " + splitted_query[1]
            user_query_ = f"{splitted_query[0]} WHERE {splitted_query[1]}"
            return user_query_

        # query doesn't contain where clause, check for group by clause or order by clause or limit
        #   -> to place the where condition of organization id before the group by or order by or limit

        elif not re.search(r'\bwhere\b', user_query, re.IGNORECASE):
            where_cond = f" WHERE {filter_conditions}"
            user_query = user_query.strip().rstrip(';')

            if re.search(r'\bgroup by\b', user_query, re.IGNORECASE):
                clause_split = re.split(r'\bgroup by\b', user_query, flags=re.IGNORECASE)
                user_q = f"{clause_split[0]}{where_cond} GROUP BY {clause_split[1]}"

            elif re.search(r'\border by\b', user_query, re.IGNORECASE):
                clause_split = re.split(r'\border by\b', user_query, flags=re.IGNORECASE)
                user_q = f"{clause_split[0]}{where_cond} ORDER BY {clause_split[1]}"

            elif re.search(r'\blimit\b', user_query, re.IGNORECASE):
                clause_split = re.split(r'\blimit\b', user_query, flags=re.IGNORECASE)
                user_q = f"{clause_split[0]}{where_cond} LIMIT {clause_split[1]}"

            else:
                user_query += where_cond
                user_q = user_query
            return user_q
    
    @staticmethod
    async def get_join_query(user_query, filters, drill_column):
        aliases = re.findall(r'\bFROM\s+\w+\s+as\s+(\w+)|\bJOIN\s+\w+\s+as\s+(\w+)', user_query, re.IGNORECASE)
        table_aliases = [alias for group in aliases for alias in group if alias]
        # org_id_condition = " AND".join(f" {alias}.organization_id = {organization_id}" for alias in table_aliases)
        # print("org_id_condition: ",org_id_condition)
        filter_conditions = await WidgetActions.generate_filter_clause(filters)

        # query contains where clause, add organization id directly in the where clause
        if re.search(r'\bwhere\b', user_query, re.IGNORECASE):
            splitted_query = re.split(r'\bwhere\b', user_query, flags=re.IGNORECASE, maxsplit=1)
            splitted_query[1] = f"{filter_conditions} AND " + splitted_query[1]
            user_query_ = f"{splitted_query[0]} WHERE {splitted_query[1]}"
            
            return user_query_

        # query doesn't contain where clause, check for group by clause or order by clause or limit
        #   -> to place the where condition of organization id before the group by or order by or limit

        elif not re.search(r'\bwhere\b', user_query, re.IGNORECASE):
            where_cond = f" WHERE {filter_conditions}"
            if re.search(r'\bgroup by\b', user_query, re.IGNORECASE):
                clause_split = re.split(r'\bgroup by\b', user_query, flags=re.IGNORECASE)
                user_q = f"{clause_split[0]}{where_cond} GROUP BY {clause_split[1]}"

            elif re.search(r'\border by\b', user_query, re.IGNORECASE):
                clause_split = re.split(r'\border by\b', user_query, flags=re.IGNORECASE)
                user_q = f"{clause_split[0]}{where_cond} ORDER BY {clause_split[1]}"

            elif re.search(r'\blimit\b', user_query, re.IGNORECASE):
                clause_split = re.split(r'\blimit\b', user_query, flags=re.IGNORECASE)
                user_q = f"{clause_split[0]}{where_cond} LIMIT {clause_split[1]}"

            else:
                user_query += where_cond
                user_q = user_query
            return user_q
        
    @staticmethod
    async def apply_filter_drilldown(query, filters, drilldown):
        if 'join' in query.lower():
            updated_query = await WidgetActions.get_join_query(query, filters, drilldown)
        else:
            updated_query = await WidgetActions.get_not_join_query(query, filters,drilldown)
        return updated_query
        
