import urdhva_base
import os
import json
import datetime
import traceback
import pandas as pd
import hpcl_ceg_model
from collections import defaultdict
import orchestrator.analytics.va_analysis as va_analysis
from orchestrator.dbconnector.widget_actions import widget_actions
import orchestrator.analytics.performance_score.performance_score_factory as performance_score_factory
from utilities.helpers import map_device_category, fetch_oi_devices, fetch_device_data, fetch_alarm_data


class SODPerformanceScore(performance_score_factory.PerformanceIndex):
    def __init__(self):
        """
        Initialize an instance of the SODPerformanceScore class.

        This method initializes an instance of the SODPerformanceScore class. It
        sets the business unit to "TAS", initializes the `config` instance
        variable to `None`, and the `va_data` instance variable to an empty
        dictionary.

        Parameters:
            None

        Returns:
            None
        """
        super().__init__()
        self.bu = "TAS"
        self.config = None  # Initialize as None
        self.va_data = {}

    async def initialize(self):
        """
        Asynchronously load performance index rules for SOD.

        This method loads the performance index rules from
        `sod_performance_rules.json` file located in the
        `pi_masters` directory of the `performance_score_factory`
        module. The rules are loaded into the instance variable
        `config`.

        The rules are used to calculate the performance score for
        SOD.

        Returns:
            None
        """
        file_path = f"{os.path.dirname(performance_score_factory.__file__)}/pi_masters/sod_performance_rules.json"
        with open(file_path) as f:
            self.config = json.load(f)

    async def configure_va(self, va_data):
        """
        Asynchronously configure VA data for SODPerformanceScore.

        This method assigns the provided VA data to the instance variable `va_data`.
        It is intended to be used to set up the necessary VA data required for
        performance score calculations for SOD.

        Args:
            va_data (dict): A dictionary containing VA data to be configured.
        """
        self.va_data = va_data

    async def generate_performance_index(self, location_id=None):
        """
        Async method to generate Performance Index score for SOD.

        :param location_id: Unique identifier of location
        :return: A tuple containing a dictionary of module scores and total weightage
        """
        module_scores = {}
        total_weight = sum(module["weightage"] for module in self.config.values())
        for module_name, module in self.config.items():
            mod = getattr(self, f'_compute_{module_name.lower()}_pi_score')
            module_score = await mod(module_name, module, location_id)
            module_scores[module_name] = module_score
        return module_scores, total_weight

    async def _compute_safety_interlocks_pi_score(self, name, rules, location_id):
        """
        Computes the Performance Index (PI) score for safety interlocks based on the given rules.

        This function evaluates the performance of safety interlocks by analyzing open alerts 
        from the database and calculating scores based on the configured rules. It considers 
        the weightage of each rule and the number of alerts that match the interlocks specified 
        in the rules. The score reflects the health of the system by comparing the number of 
        affected devices to the total expected parameter count.

        Args:
            name (str): The name of the module or rule being processed.
            rules (dict): A dictionary containing the rules for safety interlocks, including 
                        interlock names, weightage, and model.
            location_id (str): The location identifier for filtering alerts.

        Returns:
            dict: A dictionary containing the module's name, calculated score, weightage, 
                and detailed results of each rule evaluation.
        """
        # Flatten interlock names
        interlocks = []
        equipment_names = []

        for rule in rules['rules']:
            if 'rules' in rule:  # Nested rules (e.g., Hooter)
                for sub_rule in rule['rules']:
                    name = sub_rule.get('interlock_name', "")
                    eq_name = sub_rule.get('equipment_name', "")
                    if isinstance(name, list):
                        interlocks.extend(name)
                        equipment_names.append(eq_name)
                    elif name:
                        interlocks.append(name)
                        equipment_names.append(eq_name)
            else:
                name = rule.get('interlock_name', "")
                eq_name = rule.get('equipment_name', "")
                if isinstance(name, list):
                    interlocks.extend(name)
                    equipment_names.append(eq_name)
                elif name:
                    interlocks.append(name)
                    equipment_names.append(eq_name)

        interlocks = list(set(filter(None, interlocks)))  # Remove empty
        equipment_names = list(set(filter(None, equipment_names)))

        # Get open alerts
        in_clause_raw = ", ".join(f"'{val}'" for val in interlocks)
        in_clause_eq = ", ".join(f"'{val}'" for val in equipment_names)

        query = f"""
        SELECT interlock_name, tas_device_name FROM alerts 
        WHERE interlock_name IN ({in_clause_raw}) 
        AND sap_id = '{location_id}' AND alert_status != 'Close' 
        AND alert_section = 'TAS' AND bu = 'TAS' AND equipment_name in ({in_clause_eq})
        """
        print("safety query --> ", query)
        data = await hpcl_ceg_model.Alerts.get_aggr_data(query)

        open_alerts = defaultdict(list)
        for item in data.get('data', []):
            open_alerts[item['interlock_name']].append(item['tas_device_name'])

        # Map device to interlocks
        device_to_interlocks = defaultdict(set)
        for interlock, devices in open_alerts.items():
            for dev in devices:
                device_to_interlocks[dev].add(interlock)

        # Calculate rule scores
        pi_score = []
        for rule in rules['rules']:
            if 'rules' in rule:  # Nested (e.g., Hooter)
                hooter_sub_scores = []
                for sub_rule in rule['rules']:
                    interlocks = sub_rule.get('interlock_name', "")
                    if not interlocks:
                        hooter_sub_scores.append(sub_rule['weightage'] / 100)
                        continue

                    interlocks = interlocks if isinstance(interlocks, list) else [interlocks]
                    param_query = f"""
                        SELECT count FROM architecture_data 
                        WHERE device_type = '{sub_rule['equipment_name']}' AND sap_id = '{location_id}'
                    """
                    arch_data = await hpcl_ceg_model.ArchitectureData.get_aggr_data(param_query)
                    parameter_count = int(arch_data['data'][0].get('count', 0) if arch_data.get('data') else 100)

                    # Separate Tank_Under Maintenance and other alerts by device
                    tank_maintenance_devices = set()
                    other_alert_devices = set()
                    for interlock in interlocks:
                        devices = open_alerts.get(interlock, [])
                        for dev in devices:
                            if interlock == "Tank_Under Maintenance":
                                tank_maintenance_devices.add(dev)
                            else:
                                other_alert_devices.add(dev)

                    only_other_devices = other_alert_devices - tank_maintenance_devices
                    unhealthy_devices = tank_maintenance_devices.union(only_other_devices)

                    score = ((parameter_count - len(unhealthy_devices)) / parameter_count) * (sub_rule['weightage'] / 100)
                    hooter_sub_scores.append(score)

                combined_score = sum(hooter_sub_scores)
                pi_score.append({
                    "name": rule['name'],
                    "score": round(combined_score, 2),
                    "weightage": rule['weightage'],
                    "module": rules.get('name', rule['name'])
                })
            else:  # Regular rule
                interlocks = rule.get('interlock_name', "")
                if not interlocks:
                    pi_score.append({
                        "name": rule['name'],
                        "score": round(rule['weightage'] / 100, 2),
                        "weightage": rule['weightage'],
                        "module": rules.get('name', rule['name'])
                    })
                    continue

                interlocks = interlocks if isinstance(interlocks, list) else [interlocks]
                param_query = f"""
                    SELECT count FROM architecture_data 
                    WHERE device_type = '{rule['equipment_name']}' AND sap_id = '{location_id}'
                """
                arch_data = await hpcl_ceg_model.ArchitectureData.get_aggr_data(param_query)
                parameter_count = int(arch_data['data'][0].get('count', 0) if arch_data.get('data') else 100)

                # Separate Tank_Under Maintenance and other alerts by device
                tank_maintenance_devices = set()
                other_alert_devices = set()
                for interlock in interlocks:
                    devices = open_alerts.get(interlock, [])
                    for dev in devices:
                        if interlock == "Tank_Under Maintenance":
                            tank_maintenance_devices.add(dev)
                        else:
                            other_alert_devices.add(dev)

                only_other_devices = other_alert_devices - tank_maintenance_devices
                unhealthy_devices = tank_maintenance_devices.union(only_other_devices)

                score = ((parameter_count - len(unhealthy_devices)) / parameter_count) * (rule['weightage'] / 100)
                pi_score.append({
                    "name": rule['name'],
                    "score": round(score, 2),
                    "weightage": rule['weightage'],
                    "module": rules.get('name', rule['name'])
                })
        print("safety pi score --> ", pi_score)
        # Final score calculation
        final_score = round(sum([r['score'] for r in pi_score]) * rules['weightage'] / 100, 2)
        print("safety final_score --> ", final_score)
        return {
            "name": rules.get('name', ""),
            "score": final_score * 100,
            "weightage": rules['weightage'],
            "results": pi_score
        }


    async def _compute_gantry_interlocks_pi_score(self, name, rules, location_id):
        """
        Compute Gantry Interlocks Score.

        :param name: The name of the rule set as provided in the configuration.
        :param rules: The rule set as provided in the configuration.
        :param location_id: The location identifier for filtering alerts.

        :return: A dictionary containing the module's name, calculated score, weightage, 
            and detailed results of each rule evaluation.
        """
        gantry_score = []

        # Extract all interlock names from rules
        all_interlocks = []
        equipment_names = []
        for rule in rules['rules']:
            if rule['model'] != 'open_alerts':
                continue
            if isinstance(rule['interlock_name'], list):
                all_interlocks.extend(rule['interlock_name'])
                equipment_names.append(rule['equipment_name'])
            else:
                all_interlocks.append(rule['interlock_name'])
                equipment_names.append(rule['equipment_name'])
                

        # Remove duplicates
        interlocks = list(set(all_interlocks))
        equipment_set = list(set(equipment_names))

        if not interlocks:
            return {
                "name": rules.get('name', name),
                "score": 0,
                "weightage": rules['weightage'],
                "results": []
            }

        # Build SQL query for alert data
        in_clause_raw = ", ".join(f"'{value}'" for value in interlocks)
        in_clause_equipment = ", ".join(f"'{value}'" for value in equipment_set)

        current_date = datetime.datetime.now()
        first_day_of_month = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # For Gantry, most rules use month_calendar=True
        query = (
            f"SELECT interlock_name, tas_device_name, alert_status, DATE(created_at), alert_history FROM alerts "
            f"WHERE interlock_name IN ({in_clause_raw}) "
            f"AND equipment_name IN ({in_clause_equipment}) "
            f"AND sap_id = '{location_id}' "
            f"AND alert_section = 'TAS' AND bu = 'TAS' "
            f"AND created_at::DATE >= '{first_day_of_month.strftime('%Y-%m-%d')}' "
            f"AND created_at::DATE <= '{current_date.strftime('%Y-%m-%d')}'"
        )

        # Fetch alerts
        data = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=100000)
        open_alerts = defaultdict(list)
        lrc_alerts_info = {}  # To store LRC alerts with their history information

        for item in data.get('data', []):
            interlock_name = item['interlock_name']
            device_name = item['tas_device_name']
            open_alerts[interlock_name].append(device_name)
            
            # Store LRC alert history information for special handling
            if interlock_name == "LRC Master Switchover required in 30 days":
                alert_history = item.get('alert_history', [])
                if isinstance(alert_history, str):
                    try:
                        # Try to parse JSON if it's a string
                        alert_history = json.loads(alert_history)
                    except (json.JSONDecodeError, TypeError):
                        alert_history = []
                
                lrc_alerts_info[device_name] = {
                    'has_analog_input': any(
                        isinstance(entry, dict) and 
                        entry.get('action_msg') == "Alert due to Analog input" 
                        for entry in alert_history if isinstance(alert_history, list)
                    )
                }

        for rule in rules['rules']:
            if rule['model'] != 'open_alerts':
                continue

            rule_weightage = rule['weightage']
            equipment_name = rule['equipment_name']
            interlock_names = rule['interlock_name'] if isinstance(rule['interlock_name'], list) else [rule['interlock_name']]

            # Get parameter count from architecture_data
            special_interlocks = {
                "Manual FAN printed more than 5% of total TT loaded"
            }

            if any(interlock in special_interlocks for interlock in interlock_names):
                parameter_count = 1
            else:
                if isinstance(equipment_name, list):
                    device_types = ", ".join(f"'{item}'" for item in equipment_name)
                    query = f"""
                        SELECT count FROM architecture_data 
                        WHERE device_type IN ({device_types}) 
                        AND sap_id = '{location_id}'
                    """
                else:
                    query = f"""
                        SELECT count FROM architecture_data 
                        WHERE device_type = '{equipment_name}' 
                        AND sap_id = '{location_id}'
                    """
                architecture_data = await hpcl_ceg_model.ArchitectureData.get_aggr_data(query)
                parameter_count = architecture_data['data'][0].get('count', 0) if architecture_data.get('data') else 100
                parameter_count = int(parameter_count) if isinstance(parameter_count, str) and parameter_count.isdigit() else int(parameter_count or 0)

            if not parameter_count or parameter_count == 0:
                weightage = None
                score = 0
            else:
                weightage = round(rule_weightage / parameter_count, 2)

                # Special case for BCU Parameters Analysis
                if rule['name'] == "BCU Parameters Analysis":
                    device_frequency = defaultdict(int)
                    for interlock_name in interlock_names:
                        if interlock_name in open_alerts:
                            for device_name in open_alerts[interlock_name]:
                                device_frequency[device_name] += 1

                    asset_unhealthy_score = 0
                    for device, count in device_frequency.items():
                        if count < 5:
                            asset_unhealthy_score += 100
                        elif 5 <= count <= 15:
                            asset_unhealthy_score += 50
                        else:
                            asset_unhealthy_score += 0

                    score = (asset_unhealthy_score / (parameter_count * 100)) * (rule_weightage / 100)
                
                # Special case for LRC Master
                elif rule['name'] == "LRC Master":
                    # Check for "LRC Master Switchover required in 30 days" alert
                    lrc_interlock = "LRC Master Switchover required in 30 days"
                    
                    if lrc_interlock in open_alerts and any(open_alerts[lrc_interlock]):
                        # We have LRC alerts - check if any has "Alert due to Analog input"
                        has_analog_input_devices = [
                            device for device in open_alerts[lrc_interlock] 
                            if device in lrc_alerts_info and lrc_alerts_info[device]['has_analog_input']
                        ]
                        
                        if has_analog_input_devices:
                            # If alerts with "Alert due to Analog input" exist, no unhealthy count
                            asset_unhealthy_count = 0
                        else:
                            # If alerts without "Alert due to Analog input" exist, no unhealthy count
                            asset_unhealthy_count = 0
                    else:
                        # No LRC alert found, consider 1 device unhealthy
                        asset_unhealthy_count = 1
                    
                    score = ((parameter_count - asset_unhealthy_count) / parameter_count) * (rule_weightage / 100)
                    
                else:
                    # Standard calculation for other Gantry rules
                    unique_devices = set()
                    for interlock_name in interlock_names:
                        if interlock_name in open_alerts:
                            for device_name in open_alerts[interlock_name]:
                                unique_devices.add(device_name)

                    asset_unhealthy_count = len(unique_devices)
                    score = ((parameter_count - asset_unhealthy_count) / parameter_count) * (rule_weightage / 100)

            final_rule_score = score

            gantry_score.append({
                "name": rule['name'],
                "score": round(final_rule_score, 4),
                "weightage": rule_weightage,
                "module": rules.get('name', name)
            })

        # Final score scaled by weightage
        final_score = sum([score['score'] for score in gantry_score])
        final_score = round((final_score * rules['weightage']) / 100, 2)
        
        for rec in gantry_score:
            rec['score'] = round(rec['score'], 2)
        
        print("Gantry final_score ----->", final_score)
        return {
            "name": rules.get('name', name), 
            "score": final_score * 100, 
            "weightage": rules['weightage'], 
            "results": gantry_score
        }


    async def _compute_process_interlocks_pi_score(self, name, rules, location_id):
        """
        Compute Process Interlocks Score specifically handling maintenance checks.

        :param name: The name of the rule set as provided in the configuration.
        :param rules: The rule set as provided in the configuration.
        :param location_id: The location identifier for filtering alerts.

        :return: A dictionary containing the module's name, calculated score, weightage, 
            and detailed results of each rule evaluation.
        """
        process_score = []

        # Extract all interlock names and equipment names
        all_interlocks = []
        all_equipment_names = []
        for rule in rules['rules']:
            if rule['model'] != 'open_alerts' or not rule['interlock_name']:
                continue
            if isinstance(rule['interlock_name'], list):
                all_interlocks.extend(rule['interlock_name'])
                all_equipment_names.append(rule['equipment_name'])
            else:
                all_interlocks.append(rule['interlock_name'])
                all_equipment_names.append(rule['equipment_name'])

        # Remove duplicates
        interlocks = list(set(all_interlocks))
        equipment_set = list(set(all_equipment_names))

        in_clause_raw = ", ".join(f"'{value}'" for value in interlocks)
        in_clause_eq = ", ".join(f"'{value}'" for value in equipment_set)

        query = (
            f"SELECT interlock_name, tas_device_name FROM alerts "
            f"WHERE interlock_name IN ({in_clause_raw}) "
            f"AND equipment_name IN ({in_clause_eq}) "
            f"AND sap_id = '{location_id}' AND alert_status != 'Close' "
            f"AND alert_section = 'TAS' AND bu = 'TAS'"
        )
        print("process query --> ", query)

        # Fetch alerts
        data = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=100000)
        maintenance_alerts = defaultdict(list)
        for item in data.get('data', []):
            maintenance_alerts[item['interlock_name']].append(item['tas_device_name'])

        for rule in rules['rules']:
            if rule['model'] != 'open_alerts':
                continue

            rule_weightage = rule['weightage']
            equipment_name = rule['equipment_name']

            if not rule['interlock_name']:
                process_score.append({
                    "name": rule['name'],
                    "score": round(rule_weightage / 100, 2),
                    "weightage": rule_weightage,
                    "module": rules.get('name')
                })
                continue

            interlock_names = rule['interlock_name'] if isinstance(rule['interlock_name'], list) else [rule['interlock_name']]

            if isinstance(equipment_name, list):
                device_types = ", ".join(f"'{item}'" for item in equipment_name)
                query = f"""
                    SELECT count FROM architecture_data 
                    WHERE device_type IN ({device_types}) 
                    AND sap_id = '{location_id}'
                """
            else:
                query = f"""
                    SELECT count FROM architecture_data 
                    WHERE device_type = '{equipment_name}' 
                    AND sap_id = '{location_id}'
                """

            architecture_data = await hpcl_ceg_model.ArchitectureData.get_aggr_data(query)
            parameter_count = architecture_data['data'][0].get('count', 0) if architecture_data.get('data') else 100
            parameter_count = int(parameter_count) if isinstance(parameter_count, str) and parameter_count.isdigit() else int(parameter_count or 0)

            if not parameter_count:
                score = 0
            else:
                under_maintenance_devices = {
                    device_name
                    for interlock_name in interlock_names
                    for device_name in maintenance_alerts.get(interlock_name, [])
                }
                maintenance_count = len(under_maintenance_devices)
                score = ((parameter_count - maintenance_count) / parameter_count) * (rule_weightage / 100)

            process_score.append({
                "name": rule['name'],
                "score": round(score, 2),
                "weightage": rule_weightage,
                "module": rules.get('name')
            })

        # Final score
        final_score = sum([score['score'] for score in process_score])
        final_score = round((final_score * rules['weightage']) / 100, 2)

        return {
            "name": rules.get('name'),
            "score": final_score * 100,
            "weightage": rules['weightage'],
            "results": process_score
        }

    async def _compute_va_pi_score(self, name, rules, location_id):
        pi_score = []

        for rule in rules['rules']:
            score = 0
            rule_weightage = rule['weightage']
            
            if rule['model'] == 'va_portal':
                if self.va_data:
                    raw_score = float(self.va_data.get('OVERALL_SCORE', 0))
                    if raw_score == 0:
                        score = round(rule_weightage, 2)  # full score if portal score is 0
                    else:
                        score = round((raw_score * 10 * rule_weightage) / 100, 2)
                else:
                    score = round(rule_weightage, 2)  # assume full score if data is missing
            # elif rule['model'] == 'va_alerts':
            #     severity = list(set([rule_['interlock_name'] for rule_ in rule['rules']]))
            #     in_clause_raw = ", ".join(f"'{value}'" for value in severity)
            #     # For all open alerts
            #     query_open = (
            #         f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
            #         f"sap_id = '{location_id}' and alert_status != 'Close' and alert_section = 'VA' and "
            #         f"bu = 'TAS' group by severity")
            #     data = await hpcl_ceg_model.Alerts.get_aggr_data(query_open)
            #     open_alerts = {data['severity']: data['count'] for data in data['data']}

            #     # For all closure alerts in last 24 hours
            #     query_close = (
            #         f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
            #         f"sap_id = '{location_id}' and alert_status = 'Close' and alert_section = 'VA' and "
            #         f"bu = 'TAS' and updated_at >= NOW() - INTERVAL '24 hours' group by severity")
            #     data = await hpcl_ceg_model.Alerts.get_aggr_data(query_close)
            #     close_alerts = {data['severity']: data['count'] for data in data['data']}
            #     alert_score = []

            #     for rule_ in rule['rules']:
            #         int_name = rule_['interlock_name']
            #         if int_name in open_alerts or int_name in close_alerts:
            #             close_percentage = rule_['weightage'] * (close_alerts.get(int_name, 0) /
            #                                                      (close_alerts.get(int_name, 0) +
            #                                                       open_alerts.get(int_name, 0)))
            #             alert_score.append(close_percentage)
            #         else:
            #             alert_score.append(rule_['weightage'])
            #     print(alert_score, rules['weightage'])
            #     score = round((sum(alert_score) * rules['weightage']) / 100, 2)
            # else:
            #     ...
            pi_score.append({"name": rule['name'], "score": score, "weightage": rule['weightage'],
                             'module': rules.get('name', name)})
        print(" vts pi score -----> ", pi_score)
        final_score = sum([score['score'] for score in pi_score])
        final_score = round((final_score * rules['weightage']) / 100, 2)
        for rec in pi_score:
            rec['score'] = round(rec['score'], 2)
        print("final_score    ----->   ", final_score)
        return {"name": rules.get('name', name), "score": final_score, "weightage": rules['weightage'], "results": pi_score}


    async def _compute_vts_pi_score(self, name, rules, location_id):
        pi_score = []
        total_vehicles = 190
        df = pd.read_csv('/opt/ceg/algo/orchestrator/reporting_services/vehicle_master_count_of_tt_no.csv')
        df = df[df['sap_id'] == int(location_id)]
        
        if not df.empty:
            total_vehicles = df['count_of_tt_no'].sum()

        for rule in rules['rules']:
            alert_score = []
            if rule['model'] == 'vts_interlock':
                search_values = [rec['search_value'] for rec in rule['rules']]
                query_clause = " or ".join([f"interlock_name like '%{value}%'" for value in search_values])
                query = (f"select interlock_name, count(vehicle_number) as count from alerts where "
                         f"sap_id = '{location_id}' and ({query_clause}) and bu='TAS' and alert_section='VTS' and "
                         f"alert_status != 'Close' group by interlock_name")
                data = await hpcl_ceg_model.VTS.get_aggr_data(query)
                alert_data = {}
                for record in data['data']:
                    for rule_ in rule['rules']:
                        if rule_['search_value'] in record['interlock_name']:
                            if rule_['search_value'] not in alert_data:
                                alert_data[rule_['search_value']] = 0
                            alert_data[rule_['search_value']] += record['count']
                # Todo:- Need to calculate total no of vehicles

                for rule_ in rule['rules']:
                    if rule_['search_value'] in alert_data:
                        score = ((total_vehicles - alert_data[rule_['search_value']]) / total_vehicles)
                        score = round(score * (rule_['weightage']), 2)
                        alert_score.append(float(score))
                    else:
                        alert_score.append(rule_['weightage'])
            # Generating score by comparing number of active vehicles with no of open alerts
            elif rule['model'] == 'vts_active_vehicles':
                query = (f"select DISTINCT(vehicle_number), count(vehicle_number) as count from alerts "
                         f"where sap_id = '{location_id}' and alert_status != 'Close' and "
                         f"bu='TAS' and alert_section='VTS' group by vehicle_number")
                data = await hpcl_ceg_model.VTS.get_aggr_data(query)
                alert_data = {}

                inactive_vehicles = len(data['data'])
                active_vehicles = total_vehicles - inactive_vehicles
                resp = active_vehicles / total_vehicles if total_vehicles else 0
                resp = round(resp * rule['weightage'], 2)
                alert_score.append(resp)
            # Generating PI score base don total open and total close alerts
            elif rule['model'] == 'vts_alerts':
                severity = list(set([rule_['interlock_name'] for rule_ in rule['rules']]))
                in_clause_raw = ", ".join(f"'{value}'" for value in severity)
                # For all open alerts
                query_open = (
                    f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                    f"sap_id = '{location_id}' and alert_status != 'Close' and alert_section = 'VTS' and "
                    f"bu = 'TAS' group by severity")
                data = await hpcl_ceg_model.Alerts.get_aggr_data(query_open)
                open_alerts = {data['severity']: data['count'] for data in data['data']}

                # For all closure alerts in last 24 hours
                query_close = (
                    f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                    f"sap_id = '{location_id}' and alert_status = 'Close' and alert_section = 'VTS' and "
                    f"bu = 'TAS' and updated_at >= NOW() - INTERVAL '24 hours' group by severity")
                data = await hpcl_ceg_model.Alerts.get_aggr_data(query_close)
                close_alerts = {data['severity']: data['count'] for data in data['data']}

                for rule_ in rule['rules']:
                    int_name = rule_['interlock_name']
                    if int_name in open_alerts or int_name in close_alerts:
                        close_percentage = rule_['weightage'] * (close_alerts.get(int_name, 0) /
                                                                 (close_alerts.get(int_name, 0) +
                                                                  open_alerts.get(int_name, 0)))
                        alert_score.append(close_percentage)
                    else:
                        alert_score.append(rule_['weightage'])
                print(alert_score, rules['weightage'])
            score = round((sum(alert_score) * rule['weightage']) / 100, 2)
            pi_score.append({"name": rule['name'], "score": score, "weightage": rule['weightage'],
                             'module': rules.get('name', name)})
        final_score = sum([score['score'] for score in pi_score])
        final_score = round((final_score * rules['weightage']) / 100, 2)
        for rec in pi_score:
            rec['score'] = round(rec['score'], 2)
        return {"name": rules.get('name', name), "score": final_score, "weightage": rules['weightage'], "results": pi_score}


    async def _compute_water_quantity_pi_score(self, name, rules, location_id):
        """
        Computes the Performance Index (PI) score for water quantity based on device data.

        This function assesses the water availability in devices by comparing the available
        water against the required and target volumes. It calculates a percentage score
        based on water availability and applies the specified rules to compute the weighted
        PI score.

        Args:
            name (str): The name of the module or rule being processed.
            rules (dict): A dictionary containing the rules for water quantity, including 
                        rule names and weightage.
            location_id (str): The location identifier for filtering devices.

        Returns:
            dict: A dictionary containing the module's name, calculated score, weightage,
                and detailed results of each rule evaluation.

        Raises:
            Exception: If an error occurs during data fetching for a device.
        """
        WATER_THRESHOLD = 0
        all_devices = fetch_oi_devices(page_size=1000)

        #Filter only devices matching the location_id
        location_devices = [
            d for d in all_devices
            if d.get("type") == "OI" and d.get("additionalInfo", {}).get("location_id") == location_id
        ]

        pi_score = []

        if not location_devices:
            # ⚠️ No devices found for location → assign full score
            percentage = 100
            for rule in rules.get('rules', []):
                weightage = rule.get('weightage', 0)
                score = round((percentage * weightage) / 100, 2)
                pi_score.append({
                    "name": rule.get('name', ''),
                    "score": score,
                    "weightage": weightage,
                    "module": rules.get('name', '')
                })
        else:
            for device in location_devices:
                try:
                    device_id = device.get('id', {}).get('id')
                    required_kls, target_volume, available_water = fetch_device_data(device_id, key="Water Volume")
                    WATER_THRESHOLD = required_kls
                    if available_water < WATER_THRESHOLD:
                        percentage = 0
                    else:
                        percentage = (available_water / target_volume) * 100

                    for rule in rules.get('rules', []):
                        weightage = rule.get('weightage', 0)
                        score = round((percentage * weightage) / 100, 2)
                        pi_score.append({
                            "name": rule.get('name', ''),
                            "score": score,
                            "weightage": weightage,
                            "module": rules.get('name', '')
                        })
                    break  # Only process the first matching device
                except Exception as e:
                    print(f"Error processing device {device.get('name', '')}: {e}")
                    continue

        # Final score
        final_score = round(sum(r['score'] for r in pi_score), 2)
        print("final_score --->", final_score)

        return {
            "name": rules.get('name', ''),
            "score": final_score,
            "weightage": rules.get('weightage', 100),
            "results": pi_score
        }


    async def _compute_foam_quantity_pi_score(self, name, rules, location_id):
        """
        Computes the Performance Index (PI) score for foam quantity based on device data.

        This function evaluates the foam quantity in devices by comparing the available 
        foam against the required and target foam levels. It calculates a percentage 
        score based on the foam availability and applies the given rules to determine 
        the weighted PI score.

        Args:
            name (str): The name of the module or rule being processed.
            rules (dict): A dictionary containing the rules for foam quantity, including 
                        rule names and weightage.
            location_id (str): The location identifier for filtering devices.

        Returns:
            dict: A dictionary containing the module's name, calculated score, weightage, 
                and detailed results of each rule evaluation.

        Raises:
            Exception: If an error occurs during data fetching for a device.
        """
        FOAM_THRESHOLD = 0
        all_devices = fetch_oi_devices(page_size=1000)
        location_devices = [d for d in all_devices if d.get("type") == "OI" and d.get("additionalInfo").get("location_id") == location_id]
        pi_score = []

        if not location_devices:
            # ⚠️ No devices found for location → assign full score
            percentage = 100
            for rule in rules.get('rules', []):
                weightage = rule.get('weightage', 0)
                score = round((percentage * weightage) / 100, 2)
                pi_score.append({
                    "name": rule.get('name', ''),
                    "score": score,
                    "weightage": weightage,
                    "module": rules.get('name', '')
                })
        else:
            for device in location_devices:
                if device.get("type") == "OI":
                    try:
                        device_id = device['id']['id']
                        required_kls, target_volume, available_water = fetch_device_data(device_id, key="Foam Volume")
                        FOAM_THRESHOLD = required_kls
                        if available_water < FOAM_THRESHOLD:
                            percentage = 100
                        else:
                            percentage = (available_water / target_volume) * 100

                        for rule in rules['rules']:
                            weightage = rule.get('weightage', 0)
                            score = round((percentage * weightage) / 100 , 2)

                            pi_score.append({
                                "name": rule['name'],
                                "score": score,
                                "weightage": weightage,
                                "module": rules.get('name', '')
                            })
                        break
                    except Exception as e:
                        print(f"Error processing device {device.get('name')}: {e}")
                        continue

        final_score = round(sum(r['score'] for r in pi_score), 2)

        print("final_score ---> ", final_score)
        return {
            "name": rules.get('name', ''),
            "score": final_score,
            "weightage": rules['weightage'],
            "results": pi_score
        }


    async def _compute_fire_engines_in_auto_mode_pi_score(self, name, rules, location_id):
        """
        Computes the Performance Index (PI) score for fire engines in auto mode.

        This function evaluates the performance of fire engines by analyzing alarm data 
        from devices. It checks if any fire engine is in local mode with an active unacknowledged 
        alarm and adjusts the score accordingly. The score is calculated based on the configured 
        rules and their weightages. 

        Args:
            name (str): The name of the module or rule being processed.
            rules (dict): A dictionary containing the rules for fire engines, including 
                        rule names and weightages.
            location_id (str): The location identifier for filtering device data.

        Returns:
            dict: A dictionary containing the module's name, calculated score, weightage, 
                and detailed results of each rule evaluation.
        """
        all_devices = fetch_oi_devices(page_size=1000)
        pi_score = []

        # Filter devices for the given location
        location_devices = [
            d for d in all_devices
            if d.get("type") == "OI" and d.get("additionalInfo", {}).get("location_id") == location_id
        ]

        if not location_devices:
            # No devices found → assign full score
            score_percentage = 100
            for rule in rules.get('rules', []):
                weightage = rule.get('weightage', 0)
                score = round((score_percentage * weightage) / 100, 2)
                pi_score.append({
                    "name": rule.get('name', ''),
                    "score": score,
                    "weightage": weightage,
                    "module": rules.get('name', '')
                })
        else:
            for device in location_devices:
                try:
                    device_id = device.get('id', {}).get('id')
                    score_percentage = 100  # Start with full score

                    if not device_id:
                        # If no device ID, still give full score
                        pass
                    else:
                        alarms_data = fetch_alarm_data(device_id)

                        for alarm in alarms_data.get('data', []):
                            interlock_name = alarm.get('details', {}).get('additionalInfo', {}).get('interlockName')
                            status = alarm.get('status', '')

                            if interlock_name == 'Fire engine in local' and status == 'ACTIVE_UNACK':
                                score_percentage = 0
                                break

                    # Apply all rules using score_percentage
                    for rule in rules.get('rules', []):
                        weightage = rule.get('weightage', 0)
                        score = round((score_percentage * weightage) / 100, 2)
                        pi_score.append({
                            "name": rule.get('name', ''),
                            "score": score,
                            "weightage": weightage,
                            "module": rules.get('name', '')
                        })

                    break  # Process only the first matching device

                except Exception as e:
                    print(f"Error processing device {device.get('name', '')}: {e}")
                    continue

        # ✅ Final score calculation
        final_score = round(sum(r['score'] for r in pi_score), 2)
        print("final_score ---> ", final_score)

        return {
            "name": rules.get('name', ''),
            "score": final_score,
            "weightage": rules.get('weightage', 100),
            "results": pi_score
        }


    async def _compute_hydrant_line_pi_score(self, name, rules, location_id):
        """
        Compute the Performance Index (PI) score for hydrant line and jockey pump systems.

        This function evaluates the performance of hydrant line and jockey pump systems by
        analyzing alarm data and calculating scores based on configured rules. It checks
        for active alarms indicating issues with the hydrant line pressure and jockey pump
        status and adjusts scores accordingly. The function aggregates scores for each rule
        and computes a final weighted score.

        Args:
            name (str): The name of the module or rule being processed.
            rules (dict): A dictionary containing the rules with names, weightages, and module data.
            location_id (str): The location identifier for filtering device data.

        Returns:
            dict: A dictionary containing the module's name, calculated score, weightage,
                and detailed results of each rule evaluation.
        """
        all_devices = fetch_oi_devices(page_size=1000)
        pi_score = []

        # Filter devices for given location_id
        location_devices = [
            d for d in all_devices 
            if d.get("type") == "OI" and d.get("additionalInfo", {}).get("location_id") == location_id
        ]
        if not location_devices:
            # No devices found — assign full scores manually
            module_name = rules.get('name', '')
            pi_score.extend([
                {
                    'name': 'Pressurized Hydrant Line',
                    'score': 2.5,
                    'weightage': 2.5,
                    'module': module_name
                },
                {
                    'name': 'Jockey Pump',
                    'score': 2.5,
                    'weightage': 2.5,
                    'module': module_name
                }
            ])
        else:
            for device in location_devices:
                if device.get("type") == "OI":
                    try:
                        device_id = device.get('id', {}).get('id')  # Safely get device_id

                        if not device_id:
                            # No device_id, assign full scores
                            pressure_score = 2.5
                            jockey_score = 2.5
                        else:
                            alarms_data = fetch_alarm_data(device_id)

                            hydrant_alarm_active = False
                            jockey_alarm_active = False

                            for alarm in alarms_data.get('data', []):
                                interlock_name = alarm.get('details', {}).get('additionalInfo', {}).get('interlockName')
                                status = alarm.get('status', '')
                                device_type = alarm.get('type', '')

                                if device_type == 'PT Alarm' and interlock_name == 'Hydrant Line PT is below 7 Kg' and status == 'ACTIVE_UNACK':
                                    hydrant_alarm_active = True
                                elif device_type == 'Jockey Alarm' and interlock_name == 'Jockey Pump not in Auto Remote' and status == 'ACTIVE_UNACK':
                                    jockey_alarm_active = True

                            pressure_score = 0.0 if hydrant_alarm_active else 2.5
                            jockey_score = 0.0 if jockey_alarm_active else 2.5

                        module_name = rules.get('name', '')

                        pi_score.extend([
                            {
                                'name': 'Pressurized Hydrant Line',
                                'score': pressure_score,
                                'weightage': 2.5,
                                'module': module_name
                            },
                            {
                                'name': 'Jockey Pump',
                                'score': jockey_score,
                                'weightage': 2.5,
                                'module': module_name
                            }
                        ])
                        break  # Only the first matching device
                    except Exception as e:
                        print(f"Error processing device {device.get('name', '')}: {e}")
                        continue

        final_score = round(sum(r['score'] for r in pi_score), 2)
        print("final_score ---> ", final_score)

        return {
            "name": rules.get('name', ''),
            "score": final_score,
            "weightage": rules.get('weightage', 100),
            "results": pi_score
        }


    async def _compute_emlock_pi_score(self, name, rules, location_id):
        """
        Computes the Performance Index (PI) score for EMLock based on open alerts.

        This function evaluates the performance of EMLock by analyzing open alerts
        from the database and calculating scores based on the configured rules.
        It considers the weightage of each rule and the number of alerts that match
        the interlocks specified in the rules. The score reflects the health of the
        system by comparing the number of affected vehicles to the total number of
        vehicles.

        Args:
            name (str): The name of the module or rule being processed.
            rules (dict): A dictionary containing the rules for EMLock, including 
                        interlock names, weightage, and model.
            location_id (str): The location identifier for filtering alerts.

        Returns:
            list: A list containing a dictionary with the module's name, calculated
                score, weightage, and detailed results of each rule evaluation.
        """
        print("Inside _compute_emlock_pi_score")
        pi_score = []

        for rule in rules['rules']:
            if rule['model'] != 'EMLock':
                continue

            query = (
                f"SELECT DISTINCT(vehicle_number), interlock_name, severity "
                f"FROM alerts "
                f"WHERE sap_id = '{location_id}' "
                f"AND alert_status != 'Close' "
                f"AND bu = 'TAS' "
                f"AND alert_section = 'EMLock' "
                f"AND severity IN ('Critical', 'High')"
            )
            data = await hpcl_ceg_model.Alerts.get_aggr_data(query)

            vehicles_with_critical_or_high = {
                record['vehicle_number'] for record in data.get('data', [])
                if record.get('vehicle_number')
            }

            total_vehicles = 190  # Hardcoded total
            df = pd.read_csv('/opt/ceg/algo/orchestrator/reporting_services/vehicle_master_count_of_tt_no.csv')
            df = df[df['sap_id'] == int(location_id)]
            
            if not df.empty:
                total_vehicles = df['count_of_tt_no'].sum()
            affected_vehicles = len(vehicles_with_critical_or_high)
            print("total_vehicles -->", total_vehicles)
            print("affected_vehicles -->", affected_vehicles)

            # Compute percentage
            if total_vehicles > 0:
                percentage_score = round(((total_vehicles - affected_vehicles) / total_vehicles) * 100, 2)
            else:
                percentage_score = 100.0

            scaled_score = round((percentage_score * rule['weightage']) / 100, 2)
            print("percentage_score -->", percentage_score)
            print("scaled_score -->", scaled_score)

            pi_score.append({
                "name": rule['name'],
                "score": scaled_score,
                "weightage": rule['weightage'],
                "module": rules.get('name', '')
            })

        print("emlock pi_score -->", pi_score)

        final_score = round(sum(r['score'] for r in pi_score), 2)
        print("emlock final_score -->", final_score)

        return {
            "name": rules.get('name', ''),
            "score": final_score,
            "weightage": rules['weightage'],
            "results": pi_score
        }


    async def _compute_dryout_pi_score(self, name, rules, location_id):
        """
        Computes the Performance Index (PI) score for Dryouts and Carry forward based on open alerts.

        This function evaluates the performance of Dryouts and Carry forward by analyzing open alerts
        from the database and calculating scores based on the number of placed and executed carry
        forwards and dryouts. The score reflects the health of the system by comparing the number of
        placed carry forwards and dryouts to the number of executed ones.

        Args:
            name (str): The name of the module or rule being processed.
            rules (dict): A dictionary containing the rules for Dryouts and Carry forward, including 
                        interlock names, weightage, and model.
            location_id (str): The location identifier for filtering alerts.

        Returns:
            list: A list containing a dictionary with the module's name, calculated score, weightage, 
                and detailed results of each rule evaluation.
        """
        try:
            rule_list = rules['rules']  # Get the list inside the 'rules' key

            carry_forward_weight = [r['weightage'] for r in rule_list if r['name'] == 'Carry Forward']
            carry_forward_weight = carry_forward_weight[0] if carry_forward_weight else 0

            dryout_weight = [r['weightage'] for r in rule_list if r['name'] == 'Cat A Dryout']
            dryout_weight = dryout_weight[0] if dryout_weight else 0

            today_str = datetime.datetime.now().strftime('%Y-%m-%d')
            placed_carry_forward_count = 0
            placed_dryout_score = 0

            # Query for placed alerts (open and relevant conditions)
            query = """
                SELECT * FROM alerts 
                WHERE alert_status != 'Close' AND indent_status != 'Cancelled' 
                AND interlock_name = 'Dry Out Each Indent Wise MainFlow'
                AND progress_rate < 2 AND dry_out_in_days = '1'
            """
            data = await hpcl_ceg_model.Alerts.get_aggr_data(query)
            records = data.get('data', [])

            for record in records:
                alert_history = record.get('alert_history', [])

                if isinstance(alert_history, list):
                    for alert in alert_history:
                        if isinstance(alert, dict):
                            prod_reqd_dt = alert.get('prod_reqd_dt')

                            # Carry forward: prod_reqd_dt not today & category != R01
                            if prod_reqd_dt != today_str and record.get('category') != 'R01':
                                placed_carry_forward_count += 1

                # Cat A Dryout count
                if record.get('category') == 'R01':
                    placed_dryout_score += 1

            executed_carry_forward_count = 0
            executed_dryout_score = 0

            # Query for executed alerts (closed recently)
            query = """
                SELECT a.*, c.sap_id as c_sap_id, c.indent_no as c_indent_no
                FROM alerts a
                INNER JOIN carry_fwd_indent c
                    ON a.sap_id = c.sap_id AND a.indent_no = c.indent_no
                WHERE a.indent_status = 'Completed'
                AND a.interlock_name = 'Dry Out Each Indent Wise MainFlow'
                AND c.created_at >= CURRENT_DATE - INTERVAL '2 days'
                AND a.alert_status = 'Close' AND a.updated_at::date = NOW()::date
            """
            data = await hpcl_ceg_model.Alerts.get_aggr_data(query)
            records = data.get('data', [])

            for record in records:
                if record.get('category') != 'R01':
                    executed_carry_forward_count += 1

                if record.get('category') == 'R01':
                    executed_dryout_score += 1

            # Each part contributes 50 to total 100
            carry_forward_score = (
                (executed_carry_forward_count / placed_carry_forward_count) * 50
                if placed_carry_forward_count > 0 and executed_carry_forward_count > 0 else carry_forward_weight
            )

            dryout_score = (
                (executed_dryout_score / placed_dryout_score) * 50
                if placed_dryout_score > 0 and executed_dryout_score > 0 else dryout_weight
            )

            total_score = round(carry_forward_score + dryout_score, 2)
            print("Dryouts and Carry forward score -->", total_score)

            return {
                "name": "Dryouts and Carry forward",
                "score": total_score,       # out of 100%
                "weightage": rules['weightage'],  # total weightage from DRYOUT
                "results": [
                    {
                        "name": "Carry Forward",
                        "score": carry_forward_score,  # out of 50%
                        "weightage": carry_forward_weight,
                        "module": "Dryouts"
                    },
                    {
                        "name": "Cat A Dryout",
                        "score": dryout_score,         # out of 50%
                        "weightage": dryout_weight,
                        "module": "Dryouts"
                    }
                ]
            }

        except Exception as e:
            print(traceback.format_exc())
            print(f"Error calculating dryout/carry forward score: {e}")
            return {
                "name": "Dryouts and Carry forward",
                "score": 0.0,
                "weightage": rules['weightage'],
                "results": []
            }