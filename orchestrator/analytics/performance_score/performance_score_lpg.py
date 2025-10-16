import os
import json
import pandas as pd
import hpcl_ceg_model
from collections import defaultdict
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
            f"SELECT interlock_name, device_name, count(device_name) as alert_count "
            f"FROM alerts "
            f"WHERE interlock_name IN ({in_clause_raw}) "
            f"AND sap_id = '{location_id}' "
            f"AND alert_status != 'Close' "
            f"AND alert_section = 'LPG' "
            f"AND bu = 'LPG' "
            f"AND created_at::DATE >= '2025-09-01' "
            f"GROUP BY interlock_name, device_name"
        )
        data = await hpcl_ceg_model.Alerts.get_aggr_data(query)
        open_alerts = {rec['interlock_name']: rec['device_name'] for rec in data['data']}
        alert_count = defaultdict(int)
        for x in data['data']:
            alert_count[f"{x['interlock_name']}_count"] += x['alert_count']
        alert_count = dict(alert_count)
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
        msg = ""
        for rule in rules["rules"]:
            rule_weightage = rule["weightage"]
            score = 0

            # Open Alerts
            if rule["model"] == "open_alerts":
                if rule["interlock_name"] in open_alerts:
                    score = 0
                    interlock_name_count = f"{rule['interlock_name']}_count"
                    count_value = alert_count.get(interlock_name_count, 0)
                    verb = "is" if count_value == 1 else "are"
                    verb_alert = "alert" if count_value == 1 else "alerts"
                    msg = f"There {verb} {count_value} open {verb_alert} for {rule['interlock_name']}"
                else:
                    score = 100
                    msg = f"No open alert found for {rule['interlock_name']}"

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
                if rule["interlock_name"] == "O-Ring Leak Rejection":
                    if value_rejection == 0:
                        extra_score = 0
                        msg_extra = f"{rule['interlock_name']} rejection is 0. Score = 0"
                    elif value_rejection >= 6:
                        extra_score = rule_weightage
                        msg_extra = f"{rule['interlock_name']} rejection >= 6. Full score = {extra_score}"
                    else:
                        min_val = 0
                        max_val = 6
                        extra_score = float(rule_weightage) if value_rejection > 5.99 else (float(value_rejection) / 6) * float(rule_weightage)
                        msg_extra = f"{rule['interlock_name']} is {value_rejection}; Formula: ({value_rejection} / 6) * {rule_weightage} = {extra_score}"
                else:
                    extra_score = 0
                    msg_extra = ""
                # Apply thresholds
                score = 0
                for percentage_rule in rule.get("rules", []):
                    min_val = float(percentage_rule["min"])
                    max_val = float(percentage_rule["max"])
                    base = rule_weightage  # base = weightage

                    if value_rejection < min_val:
                        score = base  # full score
                        msg = f"{rule['interlock_name']} is less than {min_val}. Current rejection is {value_rejection}"
                        break
                    elif value_rejection > max_val:
                        score = 0
                        msg = f"{rule['interlock_name']} is more than {max_val}. Current rejection is {value_rejection}"
                        continue
                    else:
                        score = ((float(max_val) - float(value_rejection)) / (float(max_val) - float(min_val))) * float(base)
                        msg = f"Current rejection rate is {float(value_rejection)}, Calculation : (({float(max_val)} - {float(value_rejection)}) / ({float(max_val)} - {float(min_val)})) * {float(base)}"
                        break
                if rule["interlock_name"] == "O-Ring Leak Rejection":
                    score = extra_score
                    if msg_extra:
                        msg = msg_extra 

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
                    "msg": msg
                }
            )

        # Final PI Score
        # final_score = sum([s["score"] for s in pi_score])
        alert_score = sum(
            s["score"] for s in pi_score
            if "alert" in s["name"].lower()  
        )

        rej_score = sum(
            s["score"] for s in pi_score
            if "alert" not in s["name"].lower()  
        )

        alert_score = round((alert_score * 10) / 100, 2)
        rej_score = round((rej_score * 90) / 100, 2)

        final_score = alert_score + rej_score
        final_score = round((final_score * rules["weightage"]) / 100, 2)

        return {
            "name": rules.get("name", name),
            "score": final_score,
            "weightage": rules["weightage"],
            "results": pi_score
        }

    async def _compute_va_pi_score(self, name, rules, location_id):
        pi_score = []
        msg = ""
        for rule in rules['rules']:
            score = 0
            if rule['model'] == 'va_portal':
                if self.va_data:
                    score = round((float(self.va_data['OVERALL_SCORE']) * 10 * rule['weightage']) / 100, 2)
                    msg = f"VA Portal overall score: {self.va_data['OVERALL_SCORE']} * 10 * {rule['weightage']} / 100"
                else:
                    score = 0
                    msg = "VA Portal data not available, score set to 0"
            elif rule['model'] == 'va_alerts':
                severity = list(set([rule_['interlock_name'] for rule_ in rule['rules']]))
                in_clause_raw = ", ".join(f"'{value}'" for value in severity)
                # For all open alerts
                query_open = (
                    f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                    f"sap_id = '{location_id}' and alert_status != 'Close' and alert_section = 'VA' and "
                    f"bu = 'LPG' and created_at::DATE >= '2025-09-01' and created_at >= NOW() - INTERVAL '30 days ' group by severity")
                data = await hpcl_ceg_model.Alerts.get_aggr_data(query_open)
                open_alerts = {data['severity']: data['count'] for data in data['data']}

                # For all closure alerts in last 24 hours
                query_close = (
                    f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                    f"sap_id = '{location_id}' and alert_status = 'Close' and alert_section = 'VA' and "
                    f"bu = 'LPG'and created_at::DATE >= '2025-09-01' and updated_at >= NOW() - INTERVAL '24 hours' group by severity")
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
                total_alerts = sum(open_alerts.values()) + sum(close_alerts.values())
                closed_alerts = sum(close_alerts.values())
                if all(s == 0 for s in alert_score):
                    # If perfect compliance is achieved, force the module score to 100.0
                    score = 100 # rules['weightage']
                else:
                    score = round((sum(alert_score) * rule['weightage']) / 100, 2)
                msg = f"Total alerts: {total_alerts}. closed_alerts :{closed_alerts} .Calculation: ({round(sum(alert_score), 2)}) * ({rule['weightage']}) / 100"
            else:
                ...
            pi_score.append({
                "name": rule['name'], 
                "score": score, 
                "weightage": rule['weightage'],
                'module': rules.get('name', name),
                "msg": msg
                })
        # final_score = sum([score['score'] for score in pi_score])
        alert_score = sum(
            s["score"] for s in pi_score
            if "alert" in s["name"].lower()  
        )

        rej_score = sum(
            s["score"] for s in pi_score
            if "alert" not in s["name"].lower()  
        )

        alert_score = round((alert_score * 10) / 100, 2)
        rej_score = round((rej_score * 90) / 100, 2)

        final_score = alert_score + rej_score
        final_score = round((final_score * rules['weightage']) / 100, 2)
        for rec in pi_score:
            rec['score'] = round(rec['score'], 2)
        return {"name": rules.get('name', name), "score": final_score, "weightage": rules['weightage'], "results": pi_score}

    async def _compute_vts_pi_score(self, name, rules, location_id):
        pi_score = []
        total_vehicles = 190
        msg = ""
        for rule in rules['rules']:
            alert_score = []
            if rule['model'] == 'vts_interlock':
                continue
                search_values = [rec['search_value'] for rec in rule['rules']]
                query_clause = " or ".join([f"interlock_name like '%{value}%'" for value in search_values])
                query = (f"select interlock_name, count(vehicle_number) as count from alerts where "
                         f"sap_id = '{location_id}' and ({query_clause}) and bu='LPG' and alert_section='VTS' and "
                         f"alert_status != 'Close'and  created_at::DATE >= '2025-09-01' group by interlock_name")
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
                        msg = f"(({total_vehicles} - {alert_data[rule_['search_value']]}) / {total_vehicles})"
                        alert_score.append(score)
                    else:
                        msg = "Provided full score"
                        alert_score.append(rule_['weightage'])
            # Generating score by comparing number of active vehicles with no of open alerts
            elif rule['model'] == 'vts_active_vehicles':
                continue
                query = (f"select DISTINCT(vehicle_number), count(vehicle_number) as count from alerts "
                         f"where sap_id = '{location_id}' and alert_status != 'Close' and "
                         f"bu='LPG' and alert_section='VTS' and  created_at::DATE >= '2025-09-01' group by vehicle_number")
                data = await hpcl_ceg_model.VTS.get_aggr_data(query)
                alert_data = {}
                for record in data['data']:
                    for rule_ in rule.get('rules', []):
                        if rule_['search_value'] in record['interlock_name']:
                            if rule_['search_value'] not in alert_data:
                                alert_data[rule_['search_value']] = 0
                            alert_data[rule_['search_value']] += record['count']
                if rule['weightage'] == 0:
                    msg = "Not applicable for Bulk"
                else:
                    msg = f"Total active vehicles found: {len(data['data'])}"

            # Generating PI score base don total open and total close alerts
            elif rule['model'] == 'vts_alerts':
                severity = list(set([rule_['interlock_name'] for rule_ in rule['rules']]))
                in_clause_raw = ", ".join(f"'{value}'" for value in severity)
                # For all open alerts
                query_open = (
                    f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                    f"sap_id = '{location_id}' and alert_status != 'Close' and alert_section = 'VTS' and "
                    f"bu = 'LPG' and  created_at::DATE >= '2025-09-01' group by severity")
                data = await hpcl_ceg_model.Alerts.get_aggr_data(query_open)
                if not data.get("data", None):
                    msg = f"No Open alerts found"
                    alert_score.append(rule['weightage'])
                else:
                    open_alerts = {data['severity']: data['count'] for data in data['data']}
                    ta = sum(open_alerts[key] for key in open_alerts.keys())

                    # For all closure alerts in last 24 hours
                    query_close = (
                        f"select severity, count(device_name) as count from alerts where severity in ({in_clause_raw}) and "
                        f"sap_id = '{location_id}' and alert_status = 'Close' and alert_section = 'VTS' and "
                        f"bu = 'LPG' and  created_at::DATE >= '2025-09-01' and updated_at >= NOW() - INTERVAL '24 hours' group by severity")
                    data = await hpcl_ceg_model.Alerts.get_aggr_data(query_close)
                    close_alerts = {data['severity']: data['count'] for data in data['data']}
                    cl = sum(close_alerts[key] for key in close_alerts.keys())

                    for rule_ in rule['rules']:
                        int_name = rule_['interlock_name']
                        if int_name in open_alerts or int_name in close_alerts:
                            close_percentage = rule_['weightage'] * (close_alerts.get(int_name, 0) /
                                                                    (close_alerts.get(int_name, 0) +
                                                                    open_alerts.get(int_name, 0)))
                            msg = f"Calculation : weightage: {rule_['weightage']} * (closed_alert: {close_alerts.get(int_name, 0)} / (closed_alert: {close_alerts.get(int_name, 0)} + open_alerts: {open_alerts.get(int_name, 0)}))"
                            alert_score.append(close_percentage)
                        else:   
                            msg = f"Open alerts: {ta}  .closed_alerts :{cl}"
                            
                            alert_score.append(0)
                    print(alert_score, rules['weightage'])
            score = round((sum(alert_score) * rule['weightage']) / 100, 2)            
            pi_score.append({"name": rule['name'], 
                             "score": score, 
                             "weightage": rule['weightage'],
                             'module': rules.get('name', name),
                             "msg": msg
                             })
        final_score = sum([score['score'] for score in pi_score])
        final_score = round((final_score * rules['weightage']) / 100, 2)
        for rec in pi_score:
            rec['score'] = round(rec['score'], 2)
        return {"name": rules.get('name', name), "score": final_score, "weightage": rules['weightage'], "results": pi_score}

    async def _compute_production_pi_score(self, name, rules, location_id):
        score = 0
        query_week_sale = f""" SELECT
                                DATE(process_date) AS date,
                                ROUND(SUM(total_production)::NUMERIC, 2) AS avg_production
                            FROM lpg_plant_operations
                            WHERE process_date::DATE >= CURRENT_DATE - INTERVAL '8 days' and process_date::DATE < CURRENT_DATE - INTERVAL '1 day'
                            and sap_id = '{location_id}' GROUP BY DATE(process_date) ORDER BY date desc """

        resp = await hpcl_ceg_model.Alerts.get_aggr_data(query_week_sale)
        production_data = [float(rec['avg_production']) for rec in resp['data'] if rec['avg_production']]
        production_avg = round(float(sum(production_data) / len(production_data) if production_data else 0), 2)

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
        if production_yesterday < production_avg:
            msg = f"Yesterday's Production ({production_yesterday}) is less than Last Week Avg Production ({production_avg})"
        else:
            msg = f"Yesterday's Production ({production_yesterday}) is greater than or equal to Last Week Avg Production ({production_avg})"
        return {"name": rules.get('name', name), "score": round(score, 2), "weightage": rules['weightage'],
                "results": [{"name": rules['name'], "score": round(score, 2), "weightage": rules['weightage'],
                             'module': rules['name'], "msg": msg}]}

    async def _compute_productivity_pi_score(self, name, rules, location_id):
        query = f"""
            SELECT filling_head AS filling_heads,
                COALESCE(ROUND(SUM(total_production) / NULLIF(SUM(total_net_hours), 0), 2), 0) AS productivity_yesterday
            FROM lpg_plant_operations
            WHERE
                process_date::DATE = CURRENT_DATE - INTERVAL '1 day'
                AND sap_id = '{location_id}'
            GROUP BY filling_head
        """

        resp = await hpcl_ceg_model.Alerts.get_aggr_data(query)
        productivity = {rec['filling_heads']: float(rec['productivity_yesterday']) for rec in resp['data']}
        pi_score = []
        msg = ""
        for rule in rules['rules']:
            head = rule['search_value']
            if head not in productivity:
                continue

            val = float(productivity[head])
            weightage = float(rule['weightage'])
            subrules = rule['rules']
            score = 0.0

            for r in subrules:
                min_val = float(r['min'])
                max_val = float(r['max'])

                # Interpolation
                if val < min_val:
                    score = 0
                    msg = f"Productivity of {head} is {val} which is less than {min_val}"
                    break
                elif val > max_val:
                    score = 100
                    msg = f"Productivity of {head} is {val} which is more than {max_val}"
                    continue
                else:
                    score = 100 - ((max_val - val) / (max_val - min_val) * 100)
                    msg = f"Productivity of {head} is {val}. Calculation : ((max_value: {max_val} - productivity: {val}) / (max_value: {max_val} - min_value: {min_val}) * 100)"
                    break
            
            # If scores goes more than 100
            score = max(0, min(100, score))

            pi_score.append({
                "name": rule['name'],
                "score": round(score, 2),
                "weightage": weightage,
                "module": rules.get('name', 'Productivity'),
                "msg": msg
            })
            
        if pi_score:
            total_weight = sum(s['weightage'] for s in pi_score)
            weighted_sum = sum(s['score'] * s['weightage'] for s in pi_score)
            avg_score = weighted_sum / total_weight
            final_score = round(avg_score * (rules['weightage'] / 100), 2)
        else:
            final_score = 0

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