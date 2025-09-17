import urdhva_base
import traceback
import pandas as pd
from datetime import datetime
import orchestrator.dbconnector.widget_actions.vts_query as vts_query
from dateutil.relativedelta import relativedelta
from collections import defaultdict

class VTSAnalyticsActions:

    @staticmethod
    async def card_chart(filters, cross_filters, drill_state):
        try:
            # Get base query
            card_query = vts_query.vts_query.get(drill_state.split(",")[0])
            print("Base Query :", card_query)

            all_conditions = []  

            if filters:
                for rec in filters:
                    key = rec.key
                    val = rec.value

                    if drill_state == "total_trips" and key.lower() == "bu":
                        key = "location_type"

                    if isinstance(val, str):
                        condition = f"{key} = '{val}'"
                    elif isinstance(val, list):
                        if len(val) == 1:
                            condition = f"{key} = '{val[0]}'"
                        else:
                            condition = f"{key} IN {tuple(val)}"
                    else:
                        continue  # skip invalid types

                    all_conditions.append(condition)

            if cross_filters:
                for rec in cross_filters:
                    key = rec.key
                    val = rec.value

                    if "DATE" in key.upper():
                        start = val.split(",")[0]
                        end = (datetime.strptime(val.split(",")[-1], "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
                        condition = f"created_at BETWEEN '{start}' AND '{end}'"
                        all_conditions.append(condition)
                    else:
                        val = val.split(",")
                        if len(val) == 1:
                            condition = f"{key} = '{val[0]}'"
                        else:
                            condition = f"{key} IN {tuple(val)}"
                        all_conditions.append(condition)

            if all_conditions:
                if "group by" in card_query.lower():
                    idx = card_query.lower().index("group by")
                    base_query = card_query[:idx].strip()
                    group_by_query = card_query[idx:].strip()
                    if "where" not in base_query.lower():
                        card_query = base_query + " WHERE " + " AND ".join(all_conditions)
                    else:
                        card_query = base_query + " AND " +   " AND ".join(all_conditions)

                    card_query += " " + group_by_query

                else:
                    if "where" not in card_query.lower():
                        card_query += " WHERE "
                    else:
                        card_query += " AND "
                    card_query += " AND ".join(all_conditions)

            print("-" * 50)
            print("Final card_query ---->", card_query)

            resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=card_query, limit=0)
            resp = resp.get("data", [])
            resp = pd.DataFrame(resp)

            return {"status": True, "message": "success", "data": resp.to_dict(orient="records")}

        except Exception as e:
            print("Exception in BigNumber Chart:", str(e))
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
                
    @staticmethod     
    async def location_level_voilation_breakup(filters, cross_filters, drill_state):
        try:
            # Step 1: Determine the grouping column
            if drill_state and "location_name" in drill_state.lower():
                group_by_column = "location_name"
            elif drill_state and "zone" in drill_state.lower():
                group_by_column = "zone"
            
            all_conditions = []
            
            if filters:
                for rec in filters:
                    key = rec.key
                    val = rec.value

                    if isinstance(val, str):
                        condition = f"{key} = '{val}'"
                    elif isinstance(val, list):
                        if len(val) == 1:
                            condition = f"{key} = '{val[0]}'"
                        else:
                            condition = f"{key} IN {tuple(val)}"
                    else:
                        continue  # skip invalid types

                    all_conditions.append(condition)

            if cross_filters:
                for rec in cross_filters:
                    # Handle DATE range filter
                    if "DATE" in rec.key:
                        start = rec.value.split(",")[0]
                        end = (datetime.strptime(rec.value.split(",")[-1], "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
                        all_conditions.append(f"created_at BETWEEN '{start}' AND '{end}'")
                    else:
                        # Handle other filter types (e.g., 'bu', etc.)
                        values = rec.value.split(",") if isinstance(rec.value, str) else rec.value
                        if len(values) == 1:
                            all_conditions.append(f"{rec.key} = '{values[0]}'")
                        else:
                            all_conditions.append(f"{rec.key} IN {tuple(values)}")

            # Step 3: Build the `additional_where` clause from the combined conditions
            additional_where = ""
            if all_conditions:
                additional_where = " AND " + " AND ".join(all_conditions)

            base_query = vts_query.vts_query.get("location_level_voilation_breakup")
            if not base_query:
                # Handle the error, e.g., by logging a message or raising a specific exception
                print("Error: Query key 'location_level_voilation_breakup' not found.")
                return {"status": False, "message": "Query not found", "data": []}

        
            card_query = base_query.format(
                group_by_column=group_by_column,
                additional_where=additional_where
            )

            print("-" * 50)
            print("card_query ---->", card_query)
            
            resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=card_query, limit=0)
            resp = resp.get("data", [])
            resp = pd.DataFrame(resp)
            nested_data = defaultdict(list)
            for _, row in resp.iterrows():
                nested_data[row['group_key']].append({
                    "violation_type": row['violation_type'],
                    "count": row['count']
                })
            
            return {"status": True, "message": "success", "data": dict(nested_data)}

        except Exception as e:
            print("Exception in Location Level Violation Breakup:", str(e))
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
    