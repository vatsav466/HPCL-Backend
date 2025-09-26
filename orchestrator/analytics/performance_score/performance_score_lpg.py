import os
import json
import datetime
import requests
import pandas as pd
import hpcl_ceg_model
from utilities.helpers import map_device_category
import orchestrator.analytics.va_analysis as va_analysis
from orchestrator.dbconnector.widget_actions import widget_actions
import orchestrator.analytics.performance_score.performance_score_factory as performance_score_factory


class LPGPerformanceScore(performance_score_factory.PerformanceIndex):
    def __init__(self):
        super().__init__()
        self.bu = "LPG"
        self.config = None  # Initialize as None
        self.va_data = {}

    async def initialize(self):
        """Async method to load performance index rules for LPG."""
        file_path = f"{os.path.dirname(performance_score_factory.__file__)}/pi_masters/lpg_performance_rules.json"
        with open(file_path) as f:
            self.config = json.load(f)

    async def configure_va(self, va_data):
        self.va_data = va_data

    async def generate_performance_index(self, location_id=None):
        module_scores = {}
        total_weight = sum(module["weightage"] for module in self.config.values())
        for module_name, module in self.config.items():
            mod = getattr(self, f'_compute_{module_name.lower()}_pi_score')
            module_score = await mod(module_name, module, location_id)
            module_scores[module_name] = module_score
        return module_scores, total_weight

    async def _compute_pq_pi_score(self, name, rules, location_id):
        """
        Compute PI score for PQ based Alerts
        :param rules:
        :param location_id:
        :return:
        """
        pi_score = []
        interlocks = list(set([rule['interlock_name'] for rule in rules['rules']]))
        in_clause_raw = ", ".join(f"'{value}'" for value in interlocks)
        query = (f"select interlock_name, device_name from alerts where interlock_name in ({in_clause_raw}) and "
                 f"sap_id = '{location_id}' and alert_status != 'Close' and alert_section = 'LPG' and bu = 'LPG'")
        data = await hpcl_ceg_model.Alerts.get_aggr_data(query)
        open_alerts = {data['interlock_name']: data['device_name'] for data in data['data']}
        # Todo:- if location was disconnected, Need to mark PI score as zero
        for rule in rules['rules']:
            rule_weightage = rule['weightage']
            score = 0
            # For open alerts
            if rule['model'] == 'open_alerts':
                if rule['interlock_name'] in open_alerts:
                    score = 0
                else:
                    score = 100
            # For percentage rejection
            elif rule['model'] == 'percentage_rejection':
                if rule['interlock_name'] in open_alerts:
                    for percentage_rule in rule['rules']:
                        value_rejection = float(open_alerts[rule['interlock_name']])
                        if float(percentage_rule['min']) > value_rejection <= float(percentage_rule['max']):
                            weightage = rule['weightage']
                            # For waterfall model diving the weightage based on difference between max and min
                            if weightage and percentage_rule.get('method') == 'waterfall':
                                diff_range = float(percentage_rule['max']) - float(percentage_rule['min'])
                                rejection_percentage = (float(open_alerts[rule['interlock_name']]) -
                                                        float(percentage_rule['max']))
                                score = (weightage / diff_range) * rejection_percentage
                            else:
                                score = 0
                            break
                else:
                    score = 100
            score = (score * rule_weightage) / 100
            pi_score.append({"name": rule['name'], "score": score, "weightage": rule_weightage,
                             'module': rules.get('name', name)})
        final_score = sum([score['score'] for score in pi_score])
        final_score = round((final_score * rules['weightage']) / 100, 2)
        for rec in pi_score:
            rec['score'] = round(rec['score'], 2)
        return {"name": rules.get('name', name), "score": final_score, "weightage": rules['weightage'],
                "results": pi_score}

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
                    f"bu = 'LPG' group by severity")
                data = await hpcl_ceg_model.Alerts.get_aggr_data(query_open)
                open_alerts = {data['severity']: data['count'] for data in data['data']}

                # For all closure alerts in last 24 hours
                query_close = (
                    f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                    f"sap_id = '{location_id}' and alert_status = 'Close' and alert_section = 'VA' and "
                    f"bu = 'LPG' and updated_at >= NOW() - INTERVAL '24 hours' group by severity")
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
                         f"sap_id = '{location_id}' and ({query_clause}) and bu='LPG' and alert_section='VTS' and "
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
                         f"bu='LPG' and alert_section='VTS' group by vehicle_number")
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
                    f"bu = 'LPG' group by severity")
                data = await hpcl_ceg_model.Alerts.get_aggr_data(query_open)
                open_alerts = {data['severity']: data['count'] for data in data['data']}

                # For all closure alerts in last 24 hours
                query_close = (
                    f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                    f"sap_id = '{location_id}' and alert_status = 'Close' and alert_section = 'VTS' and "
                    f"bu = 'LPG' and updated_at >= NOW() - INTERVAL '24 hours' group by severity")
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

    async def _compute_production_pi_score(self, name, rules, location_id):
        score = 0
        # query_week_sale = f"""SELECT 
        #                         DATE(process_date) AS date,
        #                         ROUND(SUM(productivity_normal_production)::NUMERIC, 2) AS avg_production
        #                     FROM lpg_operations_summary
        #                     WHERE process_date::DATE >= CURRENT_DATE - INTERVAL '8 days' and process_date::DATE < CURRENT_DATE - INTERVAL '1 day'  
        #                     and sap_id = '{location_id}' GROUP BY DATE(process_date) ORDER BY date DESC"""

        query_week_sale = f""" SELECT 
                                DATE(process_date) AS date,
                                ROUND(SUM(total_production)::NUMERIC, 2) AS avg_production
                            FROM lpg_plant_operations
                            WHERE process_date::DATE >= CURRENT_DATE - INTERVAL '8 days' and process_date::DATE < CURRENT_DATE - INTERVAL '1 day'  
                            and sap_id = '{location_id}' GROUP BY DATE(process_date) ORDER BY date desc """

        resp = await hpcl_ceg_model.Alerts.get_aggr_data(query_week_sale)
        production_data = [float(rec['avg_production']) for rec in resp['data'] if rec['avg_production']]
        production_avg = float(sum(production_data) / len(production_data) if production_data else 0)
        
        # query_yesterday_sale = f"""SELECT ROUND(SUM(productivity_normal_production)::NUMERIC, 2) 
        # as production_yesterday FROM lpg_operations_summary WHERE process_date::DATE = CURRENT_DATE - INTERVAL '1 day' 
        # and sap_id = '{location_id}'"""
        query_yesterday_sale = f"""SELECT ROUND(SUM(total_production)::NUMERIC, 2) 
        as production_yesterday FROM lpg_plant_operations WHERE process_date::DATE = CURRENT_DATE - INTERVAL '1 day' 
        and sap_id = '{location_id}' """


        production = await hpcl_ceg_model.Alerts.get_aggr_data(query_yesterday_sale)
        production_yesterday = float(production['data'][0]['production_yesterday'] if
                                     production['data'] and production['data'][0].get('production_yesterday') else 0)
        if production_yesterday < production_avg:
            score = (((production_yesterday / production_avg) * 100) * rules['weightage']) / 100
        else:
           score = rules['weightage']
        return {"name": rules.get('name', name), "score": round(score, 2), "weightage": rules['weightage'],
                "results": [{"name": rules['name'], "score": round(score, 2), "weightage": rules['weightage'],
                             'module': rules['name'], "msg": f"Last Week Production({production_avg}) is less than "
                                                             f"Yesterdays Production({production_yesterday})"}]}

    async def _compute_productivity_pi_score(self, name, rules, location_id):
        # query = f"""SELECT filling_heads, ROUND(AVG(productivity_normal_productivity)::NUMERIC, 2) as
        # productivity_yesterday FROM lpg_operations_summary WHERE process_date::DATE = CURRENT_DATE - INTERVAL '1 day'
        # and sap_id='{location_id}' group by filling_heads"""
        query = f""" SELECT filling_head, 
                    ROUND(SUM(total_production)/SUM(total_net_hours), 2) as productivity_yesterday
                    FROM lpg_plant_operations WHERE process_date::DATE = CURRENT_DATE - INTERVAL '1 day'
                    and sap_id='{location_id}' group by filling_head """

        resp = await hpcl_ceg_model.Alerts.get_aggr_data(query)
        productivity = {rec['filling_heads']: float(rec['productivity_yesterday']) for rec in resp['data']}
        pi_score = []

        for rule in rules['rules']:
            if rule['search_value'] not in productivity:
                continue

            carousel_productivity = productivity.get(rule['search_value'], 0)
            weightage = rule['weightage']
            score = 0

            for percentage_rule in rule['rules']:
                if percentage_rule.get('method') == 'waterfall':
                    if float(percentage_rule['min']) <= carousel_productivity < float(percentage_rule['max']):
                        diff_range = float(percentage_rule['max']) - float(percentage_rule['min'])
                        score = ((carousel_productivity - float(percentage_rule['min'])) / diff_range) * float(
                            percentage_rule['weightage'])
                        break  # break after finding the matching range

            # If productivity is above the last waterfall max, give full score
            if carousel_productivity >= float(rule['rules'][-1]['max']):
                score = weightage

            pi_score.append({
                "name": rule['name'],
                "score": round(score, 2),
                "weightage": weightage,
                'module': rules.get('name', 'Productivity')
            })

        final_score = round((sum([s['score'] for s in pi_score]) / len(pi_score) * rules['weightage'] / 100),
                            2) if pi_score else 0

        for rec in pi_score:
            rec['score'] = round(rec['score'], 2)

        return {
            "name": rules.get('name', 'Productivity'),
            "score": final_score,
            "weightage": rules['weightage'],
            "results": pi_score
        }

    async def _compute_break_down_pi_score(self, name, rules, location_id):
        file_path = f"{os.path.dirname(performance_score_factory.__file__)}/pi_masters/lpg_working_hours.xlsx"
        df_working_hours = pd.read_excel(file_path).fillna(0)
        df_working_hours['PlantID'] = df_working_hours['PlantID'].astype(str)
        
        distinct_carousels_query = f"""
        SELECT 
            DISTINCT carousel, filling_head as filling_heads FROM lpg_plant_operations
        WHERE process_date::DATE = CURRENT_DATE - INTERVAL '1 day' and sap_id='{location_id}' 
        group by carousel, filling_head
        """
        
        resp = await hpcl_ceg_model.Alerts.get_aggr_data(distinct_carousels_query)
        distinct_carousels = {rec['carousel']: rec['filling_heads'] for rec in resp['data']}

        query = f"""
        SELECT 
            DISTINCT carousel, filling_head as filling_heads, SUM(break_net_hours) as break_net_hours
        FROM lpg_plant_operations WHERE process_date::DATE = CURRENT_DATE - INTERVAL '1 day' and 
        sap_id='{location_id}' group by carousel, filling_heads
        """
        
        resp = await hpcl_ceg_model.Alerts.get_aggr_data(query)
        break_down = {}
        for rec in resp['data']:
            rec['carousel'] = int(rec['carousel'])
            if rec['carousel'] not in break_down:
                break_down[rec['carousel']] = []
            break_down[rec['carousel']].append(rec['break_net_hours'])
        # Todo:- need to fetch no of carousels and what was the max run time
        break_down = {key: max(value) for key, value in break_down.items()}
        total_hours = 0
        for carousel in distinct_carousels:
            total_hours += float(df_working_hours[df_working_hours['PlantID'] == f"{location_id}"][carousel].sum())
        if not total_hours:
            total_hours = 16
        uptime = 100 - ((sum([value for _, value in break_down.items()]) / total_hours) * 100)
        return {"name": rules.get('name', name), "score": round((uptime * rules['weightage']) / 100, 2),
                "weightage": rules['weightage'], "results": []}
