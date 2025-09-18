import urdhva_base
import traceback
import pandas as pd
from datetime import datetime
import orchestrator.dbconnector.widget_actions.vts_query as vts_query
from dateutil.relativedelta import relativedelta
from collections import defaultdict

class VTSAnalyticsActions:

    @staticmethod
    async def vts_card_chart(filters, cross_filters, drill_state, payload):    

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
    async def location_level_voilation_breakup(filters, cross_filters, drill_state, payload):
        try:
            # Get query type from payload, default to original query
            if payload and payload.get("query_type", None):
                query_type = payload["query_type"]  
            # Get the base query from vts_query
            base_query = vts_query.vts_query.get(query_type)
            if not base_query:
                print(f"Error: Query key '{query_type}' not found.")
                return {"status": False, "message": "Query not found", "data": []}
            
            # Step 1: Determine the grouping column
            if drill_state and "location_name" in drill_state.lower():
                group_by_column = "location_name"
            elif drill_state and "zone" in drill_state.lower():
                group_by_column = "zone"
            
            
            # Step 2: Format the base query with group_by_column first
            query = base_query.format(group_by_column=group_by_column)
            
            # Step 3: Build conditions
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

            # Step 4: Add WHERE conditions to the formatted query
            if all_conditions:
                if "group by" in query.lower():
                    idx = query.lower().index("group by")
                    base_part = query[:idx].strip()
                    group_by_part = query[idx:].strip()

                    if "where" not in base_part.lower():
                        query = base_part + " WHERE " + " AND ".join(all_conditions)
                    else:
                        query = base_part + " AND " + " AND ".join(all_conditions)

                    query += " " + group_by_part
                else:
                    if "where" not in query.lower():
                        query += " WHERE "
                    else:
                        query += " AND "
                    query += " AND ".join(all_conditions)

            print("-" * 50)
            print("Final query ---->", query)
            
            # Step 5: Execute query
            resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=0)
            resp = resp.get("data", [])
            resp = pd.DataFrame(resp)
            
            nested_data = defaultdict(list)
            for _, row in resp.iterrows():
                group_key = row[group_by_column]
                if not group_key or str(group_key).strip() == "":
                    continue
        
                for col in resp.columns:
                    if col != group_by_column:
                            
                        nested_data[group_key].append({
                            "violation_type": col,
                            "count" : row[col]
                        })            
                    
            return {"status": True, "message": "success", "data": dict(nested_data)}
      
        except Exception as e:
            print("Exception in Location Level Violation Breakup:", str(e))
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
        