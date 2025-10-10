import os
import json
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
        Compute PI score for PQ based Alerts & Percentage Rejections.
        """
        pi_score = []

        interlocks = list(set([rule['interlock_name'] for rule in rules['rules']]))
        in_clause_raw = ", ".join(f"'{value}'" for value in interlocks)
        query = (
            f"SELECT interlock_name, device_name "
            f"FROM alerts "
            f"WHERE interlock_name IN ({in_clause_raw}) "
            f"AND sap_id = '{location_id}' "
            f"AND alert_status != 'Close' "
            f"AND alert_section = 'LPG' "
            f"AND bu = 'LPG'"
        )
        data = await hpcl_ceg_model.Alerts.get_aggr_data(query)
        open_alerts = {rec['interlock_name']: rec['device_name'] for rec in data['data']}

        rejection_query = (
            f"SELECT "
            f"ROUND((SUM(cs_sortout) / NULLIF(SUM(cs_handled), 0)) * 100, 2) AS cs_rejection, "
            f"ROUND((SUM(gd_sortout) / NULLIF(SUM(gd_handled), 0)) * 100, 2) AS gd_rejection, "
            f"ROUND((SUM(pt_sortout) / NULLIF(SUM(pt_handled), 0)) * 100, 2) AS pt_rejection "
            f"FROM lpg_plant_operations "
            f"WHERE sap_id = '{location_id}' and process_date::DATE = CURRENT_DATE - INTERVAL '1 day'"
        )
        rej_data = await hpcl_ceg_model.LpgPlantOperations.get_aggr_data(rejection_query)
        rejection_values = rej_data["data"][0] if rej_data["data"] else {}

        for rule in rules["rules"]:
            rule_weightage = rule["weightage"]
            score = 0

            # Open Alerts
            if rule["model"] == "open_alerts":
                if rule["interlock_name"] in open_alerts:
                    score = 0
                else:
                    score = 100

            # Percentage Rejection
            elif rule["model"] == "percentage_rejection":
                # mapping interlock to correct column in lpg_plant_operations
                if "Check Scale" in rule["interlock_name"]:
                    value_rejection = rejection_values.get("cs_rejection", 0) or 0
                elif "Valve Leak" in rule["interlock_name"]:
                    value_rejection = rejection_values.get("gd_rejection", 0) or 0
                elif "O-Ring" in rule["interlock_name"]:
                    value_rejection = rejection_values.get("pt_rejection", 0) or 0
                else:
                    value_rejection = 0

                if value_rejection is None:
                    value_rejection = 0

                # Apply thresholds
                score = 0
                for percentage_rule in rule.get("rules", []):
                    min_val = float(percentage_rule["min"])
                    max_val = float(percentage_rule["max"])
                    base = rule_weightage  # base = weightage

                    if value_rejection < min_val:
                        score = base  # full score
                        break
                    elif value_rejection > max_val:
                        score = 0
                        continue
                    else:
                        score = ((float(max_val) - float(value_rejection)) / (float(max_val) - float(min_val))) * float(base)
                        break

                # Convert to percentage of rule weightage
                score = (score / base) * 100 if base > 0 else 0

            # Weightage scaling
            score = (score * rule_weightage) / 100

            pi_score.append(
                {
                    "name": rule["name"],
                    "score": round(score, 2),
                    "weightage": rule_weightage,
                    "module": rules.get("name", name),
                }
            )

        # Final PI Score
        final_score = sum([s["score"] for s in pi_score])
        final_score = round((final_score * rules["weightage"]) / 100, 2)

        return {
            "name": rules.get("name", name),
            "score": final_score,
            "weightage": rules["weightage"],
            "results": pi_score,
        }

    async def _compute_va_pi_score(self, name, rules, location_id):
        pi_score = []
        for rule in rules['rules']:
            score = 0
            if rule['model'] == 'va_portal':
                if self.va_data:
                    score = round((float(self.va_data['OVERALL_SCORE']) * 10 * rule['weightage']) / 100, 2)
                else:
                    score = 0
            elif rule['model'] == 'va_alerts':
                severity = list(set([rule_['interlock_name'] for rule_ in rule['rules']]))
                in_clause_raw = ", ".join(f"'{value}'" for value in severity)
                # For all open alerts
                query_open = (
                    f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                    f"sap_id = '{location_id}' and alert_status != 'Close' and alert_section = 'VA' and "
                    f"bu = 'LPG' and created_at >= NOW() - INTERVAL '30 days ' group by severity")
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
                    if not open_alerts and not close_alerts:
                        alert_score.append(rule_['weightage'])
                        print("alert_score:",alert_score)
                    elif int_name in open_alerts or int_name in close_alerts:
                        close_percentage = rule_['weightage'] * (close_alerts.get(int_name, 0) /
                                                                 (close_alerts.get(int_name, 0) +
                                                                  open_alerts.get(int_name, 0)))
                        alert_score.append(close_percentage)
                    else:
                        alert_score.append(rule_['weightage'])
                print(alert_score, rule['weightage'])
                if all(s == 0 for s in alert_score):
                    # If perfect compliance is achieved, force the module score to 100.0
                    score = 100 # rules['weightage']
                else:
                    score = round((sum(alert_score) * rule['weightage']) / 100, 2)
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
        query = f"""
            SELECT filling_head as filling_heads,
                COALESCE(ROUND(SUM(total_production) / NULLIF(SUM(total_net_hours), 0), 2), 0) AS productivity_yesterday
            FROM lpg_plant_operations
            WHERE
                process_date::DATE = CURRENT_DATE - INTERVAL '1 day'
                AND sap_id='{location_id}'
            GROUP BY filling_head
        """

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
                method = percentage_rule.get('method', 'waterfall')

                if method == 'excel_like':
                    min_val = float(percentage_rule['min'])
                    max_val = float(percentage_rule['max'])
                    w = float(percentage_rule['weightage'])

                    if carousel_productivity >= max_val:
                        score = w
                    elif carousel_productivity <= min_val:
                        score = 0
                    else:
                        diff_range = max_val - min_val
                        score = ((carousel_productivity - min_val) / diff_range) * w

                    break  # stop once matched

                elif method == 'waterfall':
                    if float(percentage_rule['min']) <= carousel_productivity < float(percentage_rule['max']):
                        diff_range = float(percentage_rule['max']) - float(percentage_rule['min'])
                        # If full weightage, give it directly; else interpolate
                        if percentage_rule['weightage'] in (0, 100):
                            score = float(percentage_rule['weightage'])
                        else:
                            score = ((carousel_productivity - float(percentage_rule['min'])) / diff_range) * float(
                                percentage_rule['weightage'])
                        break

            # If productivity is above the last max → full score
            if carousel_productivity >= float(rule['rules'][-1]['max']):
                score = weightage

            pi_score.append({
                "name": rule['name'],
                "score": round(score, 2),
                "weightage": weightage,
                'module': rules.get('name', 'Productivity')
            })

        final_score = round(
            (sum([s['score'] for s in pi_score]) / len(pi_score) * rules['weightage'] / 100),
            2
        ) if pi_score else 0

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
            total_hours += float(df_working_hours[df_working_hours['PlantID'] == f"{location_id}"][int(carousel)].sum())
        if not total_hours:
            total_hours = 16
        uptime = 100 - (float(float((sum([value for _, value in break_down.items()]))) / float(total_hours)) * 100)
        return {"name": rules.get('name', name), "score": round((uptime * rules['weightage']) / 100, 2),
                "weightage": rules['weightage'], "results": []}
