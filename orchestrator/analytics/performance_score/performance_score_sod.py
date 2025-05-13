import urdhva_base
import os
import json
import datetime
import requests
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
        pi_score = []

        # Extract all interlock names from rules
        all_interlocks = []
        for rule in rules['rules']:
            if rule['model'] != 'open_alerts':
                continue
            if isinstance(rule['interlock_name'], list):
                all_interlocks.extend(rule['interlock_name'])
            else:
                all_interlocks.append(rule['interlock_name'])

        # Remove duplicates
        interlocks = list(set(all_interlocks))

        if not interlocks:
            return {"name": rules.get('name', name), "score": 0,
                     "weightage": rules['weightage'], "results": []}

        # Build SQL query for alert data
        in_clause_raw = ", ".join(f"'{value}'" for value in interlocks)
        query = (
            f"SELECT interlock_name, tas_device_name FROM alerts WHERE interlock_name IN ({in_clause_raw}) "
            f"AND sap_id = '{location_id}' AND alert_status != 'Close' "
            f"AND alert_section = 'TAS' AND bu = 'TAS'"
        )
        # Fetch open alerts
        data = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=100000)
        print("data --> ", data)
        open_alerts = defaultdict(list)
        for item in data.get('data', []):
            print("item --> ", item)
            open_alerts[item['interlock_name']].append(item['tas_device_name'])

        for rule in rules['rules']:
            if rule['model'] != 'open_alerts':
                continue

            rule_weightage = rule['weightage']
            equipment_name = rule['equipment_name']
            interlock_names = rule['interlock_name'] if isinstance(rule['interlock_name'], list) else [rule['interlock_name']]

            # Get parameter count from architecture_data
            special_interlocks = {
                "As Power ESD Activation in Main PMCC Panel after 120 Sec"
                # "SafetyPLC_Communication fail"
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
                print("query --> ", query)
                architecture_data = await hpcl_ceg_model.ArchitectureData.get_aggr_data(query)
                print("architecture_data", architecture_data)
                parameter_count = architecture_data['data'][0].get('count', 0) if architecture_data.get('data') else 100
                parameter_count = int(parameter_count) if isinstance(parameter_count, str) and parameter_count.isdigit() else int(parameter_count or 0)
            
            if not parameter_count or parameter_count == 0:
                weightage = None
                score = 0
            else:
                weightage = round(rule_weightage / parameter_count, 2)
                print("weightage", weightage)
                unique_devices = set()
                print("interlock_names", interlock_names)
                print("open_alerts", open_alerts)

                # Collect all affected device names
                for interlock_name in interlock_names:
                    if interlock_name in open_alerts:
                        if interlock_name == "As Power ESD Activation in Main PMCC Panel after 120 Sec":
                            unique_devices.add("SPECIAL_CASE_DEVICE")  # Use a dummy placeholder
                            break  # No need to process further, as we only want one count
                        else:
                            for device_name in open_alerts[interlock_name]:
                                print("device_name", device_name)
                                unique_devices.add(device_name)

                print("unique_devices", unique_devices)

                asset_unhealthy_count = len(unique_devices)
                print("asset_unhealthy_count", asset_unhealthy_count)
                score = ((parameter_count - asset_unhealthy_count) / parameter_count) * (rule_weightage / 100)
                print("score", score)
            pi_score.append({
                "name": rule['name'],
                "score": round(score, 4),
                "weightage": rule_weightage,
                "module": rules.get('name', name)
            })

        print("pi_score", pi_score)

        final_score = sum([score['score'] for score in pi_score])
        final_score = round((final_score * rules['weightage']) / 100, 2)
        for rec in pi_score:
            rec['score'] = round(rec['score'], 2)
        print("final_score    ----->   ", final_score)
        return {"name": rules.get('name', name), "score": final_score, "weightage": rules['weightage'], "results": pi_score}


    async def _compute_process_interlocks_pi_score(self, name, rules, location_id):
        """
        Compute Process Interlocks PI Score.

        :param name: The name of the rule set as provided in the configuration.
        :param rules: The rule set as provided in the configuration.
        :param location_id: The location identifier for filtering alerts.

        :return: A dictionary containing the module's name, calculated score, weightage, 
            and detailed results of each rule evaluation.
        """
        # monthly_oi_cache = {}
        pi_score = []

        # Extract all interlock names from rules
        all_interlocks = []
        for rule in rules['rules']:
            if rule['model'] != 'open_alerts':
                continue
            if isinstance(rule['interlock_name'], list):
                all_interlocks.extend(rule['interlock_name'])
            else:
                all_interlocks.append(rule['interlock_name'])

        # Remove duplicates
        interlocks = list(set(all_interlocks))

        if not interlocks:
            return {
                "name": rules.get('name', name),
                "score": 0,
                "weightage": rules['weightage'],
                "results": []
            }

        # Build SQL query for alert data
        in_clause_raw = ", ".join(f"'{value}'" for value in interlocks)

        current_date = datetime.datetime.now()
        first_day_of_month = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        if rule['month_calendar']:
            # For month_calendar=True, get all alerts (open and closed) for the current month
            query = (
                f"SELECT interlock_name, tas_device_name, alert_status, alert_date FROM alerts "
                f"WHERE interlock_name IN ({in_clause_raw}) "
                f"AND sap_id = '{location_id}' "
                f"AND alert_section = 'TAS' AND bu = 'TAS' "
                f"AND alert_date >= '{first_day_of_month.strftime('%Y-%m-%d')}' "
                f"AND alert_date <= '{current_date.strftime('%Y-%m-%d')}'"
            )
        else:
            # For month_calendar=False, only get currently open alerts
            query = (
                f"SELECT interlock_name, tas_device_name FROM alerts "
                f"WHERE interlock_name IN ({in_clause_raw}) "
                f"AND sap_id = '{location_id}' AND alert_status != 'Close' "
                f"AND alert_section = 'TAS' AND bu = 'TAS'"
            )

        # Fetch alerts
        data = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=100000)
        open_alerts = defaultdict(list)

        for item in data.get('data', []):
            open_alerts[item['interlock_name']].append(item['tas_device_name'])

        # month_key = (location_id, rules.get('name', name), current_date.year, current_date.month)

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
                unique_devices = set()

                if rules.get('name') == "BCU Parameters Analysis":
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

                else:
                    for interlock_name in interlock_names:
                        if interlock_name in open_alerts:
                            for device_name in open_alerts[interlock_name]:
                                unique_devices.add(device_name)

                    asset_unhealthy_count = len(unique_devices)
                    score = ((parameter_count - asset_unhealthy_count) / parameter_count) * (rule_weightage / 100)

            final_rule_score = score
            # Uncomment if you want to use monthly caching logic
            # if rules['month_calendar']:
            #     # Save and use the minimum score for the month
            #     if month_key not in monthly_oi_cache:
            #         monthly_oi_cache[month_key] = {}
            #
            #     previous_score = monthly_oi_cache[month_key].get(rule['name'], score)
            #     monthly_oi_cache[month_key][rule['name']] = min(previous_score, score)
            #
            #     final_rule_score = monthly_oi_cache[month_key][rule['name']]

            pi_score.append({
                "name": rule['name'],
                "score": round(final_rule_score, 4),
                "weightage": rule_weightage,
                "module": rules.get('name', name)
            })

            # Uncomment to save score to PostgreSQL
            # await hpcl_ceg_model.TASMonthlyOIScoresCreate(
            #     location_id=location_id,
            #     module_name=rules.get('name', name),
            #     rule_name=rule['name'],
            #     year=current_date.year,
            #     month=current_date.month,
            #     score=final_rule_score,
            #     weightage=rule_weightage
            # ).create()

        # Final score scaled to 0–2000 (as per original logic)
        final_score = sum([score['score'] for score in pi_score])
        final_score = round((final_score * rules['weightage']) / 100, 2)
        for rec in pi_score:
            rec['score'] = round(rec['score'], 2)
        print("final_score    ----->   ", final_score)
        return {"name": rules.get('name', name), "score": final_score, "weightage": rules['weightage'], "results": pi_score}


    async def _compute_va_pi_score(self, name, rules, location_id):
        pi_score = []
        for rule in rules['rules']:
            score = 0
            rule_weightage = rule['weightage']
            if rule['model'] == 'va_portal':
                if self.va_data:
                    score = round((float(self.va_data['OVERALL_SCORE']) * 10 * rules['weightage']) / 100, 2)
                else:
                    score = 0
            elif rule['model'] == 'va_alerts':
                severity = list(set([rule_['interlock_name'] for rule_ in rule['rules']]))
                in_clause_raw = ", ".join(f"'{value}'" for value in severity)
                # For all open alerts
                query_open = (
                    f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                    f"sap_id = '{location_id}' and alert_status != 'Close' and alert_section = 'VA' and "
                    f"bu = 'TAS' group by severity")
                data = await hpcl_ceg_model.Alerts.get_aggr_data(query_open)
                open_alerts = {data['severity']: data['count'] for data in data['data']}

                # For all closure alerts in last 24 hours
                query_close = (
                    f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                    f"sap_id = '{location_id}' and alert_status = 'Close' and alert_section = 'VA' and "
                    f"bu = 'TAS' and updated_at >= NOW() - INTERVAL '24 hours' group by severity")
                data = await hpcl_ceg_model.Alerts.get_aggr_data(query_close)
                close_alerts = {data['severity']: data['count'] for data in data['data']}
                alert_score = []

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
                score = round((sum(alert_score) * rules['weightage']) / 100, 2)
            else:
                ...
            pi_score.append({"name": rule['name'], "score": score, "weightage": rule['weightage'],
                             'module': rules.get('name', name)})
        final_score = sum([score['score'] for score in pi_score])
        final_score = round((final_score * rules['weightage']) / 100, 2)
        for rec in pi_score:
            rec['score'] = round(rec['score'], 2)
        return {"name": rules.get('name', name), "score": final_score, "weightage": rules['weightage'], "results": pi_score}


    async def _compute_vts_pi_score(self, name, rules, location_id):
        pi_score = []
        total_vehicles = 190
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
                        score = round(score * (rule_['weightage'] / 100), 2)
                        alert_score.append(score)
                    else:
                        alert_score.append(rule_['weightage'])
            # Generating score by comparing number of active vehicles with no of open alerts
            elif rule['model'] == 'vts_active_vehicles':
                query = (f"select DISTINCT(vehicle_number), count(vehicle_number) as count from alerts "
                         f"where sap_id = '{location_id}' and alert_status != 'Close' and "
                         f"bu='TAS' and alert_section='VTS' group by vehicle_number")
                data = await hpcl_ceg_model.VTS.get_aggr_data(query)
                alert_data = {}
                for record in data['data']:
                    for rule_ in rule.get('rules', []):
                        if rule_['search_value'] in record['interlock_name']:
                            if rule_['search_value'] not in alert_data:
                                alert_data[rule_['search_value']] = 0
                            alert_data[rule_['search_value']] += record['count']
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
        all_devices = fetch_oi_devices(self, page_size=0, page=0)
        pi_score = []

        for device in all_devices:
            if device.get("type") == "OI":
                try:
                    device_id = device['id']['id']
                    required_kls, target_volume, available_water = fetch_device_data(self, device_id, key="water")

                    percentage = 0 if available_water < required_kls else (available_water / target_volume) * 100
                    for rule in rules['rules']:
                        weightage = rule.get('weightage', 0)
                        score = round((percentage * weightage) / 100, 2)
                        pi_score.append({
                            "name": rule['name'],
                            "score": score,
                            "weightage": weightage,
                            "module": rules.get('name', name)
                        })
                except Exception as e:
                    print(f"Error processing device {device.get('name')}: {e}")
                    continue

        final_score = round((sum(r['score'] for r in pi_score) * rules['weightage']) / 100, 2)
        return {
            "name": rules.get('name', name),
            "score": final_score,
            "weightage": rules['weightage'],
            "results": pi_score
        }


    async def _compute_foam_quantity_pi_score(self, name, rules, location_id):
        all_devices = fetch_oi_devices(self, page_size=0, page=0)
        pi_score = []

        for device in all_devices:
            if device.get("type") == "OI":
                try:
                    device_id = device['id']['id']
                    required_foam, target_foam, available_foam = fetch_device_data(self, device_id, key="foam")

                    percentage = 0 if available_foam < required_foam else (available_foam / target_foam) * 100
                    for rule in rules['rules']:
                        weightage = rule.get('weightage', 0)
                        score = round((percentage * weightage) / 100, 2)
                        pi_score.append({
                            "name": rule['name'],
                            "score": score,
                            "weightage": weightage,
                            "module": rules.get('name', name)
                        })
                except Exception as e:
                    print(f"Error processing device {device.get('name')}: {e}")
                    continue

        final_score = round((sum(r['score'] for r in pi_score) * rules['weightage']) / 100, 2)
        return {
            "name": rules.get('name', name),
            "score": final_score,
            "weightage": rules['weightage'],
            "results": pi_score
        }



    async def _compute_fire_engines_in_auto_mode_pi_score(self, name, rules, location_id):
        all_devices = fetch_oi_devices(self, page_size=0, page=0)
        pi_score = []

        for device in all_devices:
            if device.get("type") == "OI":
                try:
                    device_id = device['id']['id']
                    alarms_data = fetch_alarm_data(self, device_id)
                    score_percentage = 100.0

                    for alarm in alarms_data.get('data', []):
                        interlock_name = alarm.get('details', {}).get('additionalInfo', {}).get('interlockName')
                        status = alarm.get('status', '')
                        if interlock_name == 'Fire engine in local' and status == 'ACTIVE_UNACK':
                            score_percentage = 0.0
                            break

                    for rule in rules['rules']:
                        weightage = rule['weightage']
                        score = round((score_percentage * weightage) / 100, 2)
                        pi_score.append({
                            "name": rule['name'],
                            "score": score,
                            "weightage": weightage,
                            "module": rules.get('name', name)
                        })

                except Exception as e:
                    print(f"Error processing device {device.get('name', 'Unknown')}: {e}")
                    continue

        final_score = round((sum(r['score'] for r in pi_score) * rules['weightage']) / 100, 2)
        return {
            "name": rules.get('name', name),
            "score": final_score,
            "weightage": rules['weightage'],
            "results": pi_score
        }



    async def _compute_hydrant_line_pi_score(self, name, rules, location_id):
        all_devices = fetch_oi_devices(self, page_size=0, page=0)
        pi_score = []

        for device in all_devices:
            if device.get("type") == "OI":
                try:
                    device_id = device['id']['id']
                    alarms_data = fetch_alarm_data(self, device_id)

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

                    pi_score.extend([
                        {
                            'name': 'Pressurized Hydrant Line',
                            'score': pressure_score,
                            'weightage': 2.5,
                            'module': rules.get('name', name)
                        },
                        {
                            'name': 'Jockey Pump',
                            'score': jockey_score,
                            'weightage': 2.5,
                            'module': rules.get('name', name)
                        }
                    ])
                except Exception as e:
                    print(f"Error processing device {device.get('name')}: {e}")
                    continue

        final_score = round((sum(r['score'] for r in pi_score) * rules['weightage']) / 100, 2)
        return {
            "name": rules.get('name', name),
            "score": final_score,
            "weightage": rules['weightage'],
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
        pi_score = []
        for rule in rules['rules']:
            if rule['model'] != 'open_alerts':
                continue

            # 1. Get all open alerts at location
            query = (
                f"SELECT DISTINCT(vehicle_number), interlock_name, severity "
                f"FROM alerts "
                f"WHERE sap_id = '{location_id}' "
                f"AND alert_status != 'Close' "
                f"AND bu = 'TAS' "
                f"AND alert_section = 'EMLock'"
            )
            data = await hpcl_ceg_model.Alerts.get_aggr_data(query)

            all_vehicle_numbers = set()
            vehicles_with_critical_or_high = set()
            alert_data = {}

            for record in data['data']:
                vehicle_number = record.get('vehicle_number')
                interlock_name = record.get('interlock_name')
                severity = record.get('severity', '').lower()

                if vehicle_number:
                    all_vehicle_numbers.add(vehicle_number)

                # Count only matching interlocks per rule
                for rule_ in rule.get('rules', []):
                    if rule_['search_value'] in interlock_name:
                        alert_data[rule_['search_value']] = alert_data.get(rule_['search_value'], 0) + 1

                        # Add vehicle to critical/high set if matched
                        if severity in ['Critical', 'High']:
                            vehicles_with_critical_or_high.add(vehicle_number)

            total_vehicles = len(all_vehicle_numbers)
            affected_vehicles = len(vehicles_with_critical_or_high)

            # Avoid division by zero
            if total_vehicles > 0:
                score_val = (total_vehicles - affected_vehicles) / total_vehicles
                score = round(score_val * 100, 2)
            else:
                score = 5.0

            # Add score for each rule element
            for rule_ in rule.get('rules', []):
                pi_score.append({
                    "name": rule_['name'],
                    "score": score,
                    "weightage": rule_['weightage'],
                    "module": rules.get('name', name)
                })

        # Final score aggregation
        final_score = round((sum(r['score'] for r in pi_score) * rules['weightage']) / 100, 2)

        return {
            "name": rules.get('name', name),
            "score": final_score,
            "weightage": rules['weightage'],
            "results": pi_score
        }


    async def _compute_dryout_pi_score(self, name, rules, location_id):
        query = f"""
            SELECT 
                type,
                category,
                COUNT(*) FILTER (WHERE status = 'Placed' AND is_valid) AS total_placed,
                COUNT(*) FILTER (WHERE status = 'Executed' AND is_valid) AS total_executed
            FROM indents
            WHERE type IN ('CarryForward', 'Dryout')
            AND category = 'Cat A'
            AND sap_id = '{location_id}'
            GROUP BY type, category;
            """

        try:
            data = await hpcl_ceg_model.Indents.get_aggr_data(query)
            records = data.get('data', [])

            carry_forward_score = 0.0
            dryout_score = 0.0

            for row in records:
                type_ = row.get('type')
                placed = row.get('total_placed', 0)
                executed = row.get('total_executed', 0)

                if placed == 0:
                    continue

                if type_ == 'CarryForward':
                    carry_forward_score = (executed / placed) * 50.0
                elif type_ == 'Dryout':
                    dryout_score = (executed / placed) * 50.0

            total_score = round(carry_forward_score + dryout_score, 2)

            return {
                "name": "Dryouts and Carry forward",
                "score": total_score,
                "weightage": 100,
                "results": [
                    {
                        "name": "Carry Forward",
                        "score": round(carry_forward_score, 2),
                        "weightage": 50,
                        "module": "Dryouts"
                    },
                    {
                        "name": "Cat A Dryout",
                        "score": round(dryout_score, 2),
                        "weightage": 50,
                        "module": "Dryouts"
                    }
                ]
            }

        except Exception as e:
            print(f"Error calculating dryout/carry forward score: {e}")
            return {
                "name": "Dryouts and Carry forward",
                "score": 0.0,
                "weightage": 100,
                "results": []
            }