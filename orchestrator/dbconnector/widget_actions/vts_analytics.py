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
                    
                    vts_alert_history_queries = ["total_trips", 
                                                 "violations_each_count", 
                                                 "total_violations_product", 
                                                 "total_violations_trip",
                                                 "route_violation_percentage",
                                                  "speed_violation_percentage",
                                                  "night_driving_percentage",
                                                  "unauthorized_stoppage_percentage",
                                                  "device_tampering_percentage"]
                    if drill_state in vts_alert_history_queries and key.lower() == "bu":
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
            # 1. Get query type from payload
            query_type = payload.get("query_type") if payload else None
            query = vts_query.vts_query.get(query_type)
            if not query:
                return {"status": False, "message": "Query not found", "data": []}

            
            # 2. Build conditions (same logic as before)
            all_conditions = []
            if filters:
                for rec in filters:
                    key, val = rec.key, rec.value
                    if key == "bu":
                        key = "location_type"
                    if isinstance(val, str):
                        all_conditions.append(f"{key} = '{val}'")
                    elif isinstance(val, list):
                        all_conditions.append(f"{key} IN {tuple(val)}")

            if cross_filters:
                for rec in cross_filters:
                    if "DATE" in rec.key:
                        start = rec.value.split(",")[0]
                        end = (datetime.strptime(rec.value.split(",")[-1], "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
                        all_conditions.append(f"created_at BETWEEN '{start}' AND '{end}'")
                    else:
                        values = rec.value.split(",") if isinstance(rec.value, str) else rec.value
                        if len(values) == 1:
                            all_conditions.append(f"{rec.key} = '{values[0]}'")
                        else:
                            all_conditions.append(f"{rec.key} IN {tuple(values)}")

            if all_conditions:
                if "group by" in query.lower():
                    idx = query.lower().index("group by")
                    query = query[:idx] + " WHERE " + " AND ".join(all_conditions) + " " + query[idx:]
                else:
                    query += " WHERE " + " AND ".join(all_conditions)

            # 3. Execute main query (location_id + violation counts)
            resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=0)
            resp = pd.DataFrame(resp.get("data", []))

            if resp.empty:
                return {"status": True, "message": "no data", "data": {}}

            # 4. Fetch location_master for mapping
            loc_master_query = "SELECT sap_id, name, zone FROM location_master"
            loc_master_resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=loc_master_query, limit=0)
            loc_master = pd.DataFrame(loc_master_resp.get("data", []))

            # Map sap_id → zone/name
            loc_map = {}
            for _, row in loc_master.iterrows():
                loc_map[row["sap_id"]] = {
                    "zone": row["zone"],
                    "name": row["name"]
                }

            # 5. Build final nested_data
            nested_data = defaultdict(lambda: defaultdict(int))

            for _, row in resp.iterrows():
                location_id = row["location_id"]

                # map location_id → group key (zone or location)
                group_key = None
                if location_id in loc_map:
                    if drill_state and "location" in drill_state.lower():
                        group_key = loc_map[location_id]["name"]
                    elif drill_state and "zone" in drill_state.lower():
                        group_key = loc_map[location_id]["zone"]

                if not group_key:
                    continue

                # aggregate counts per violation_type
                for col in resp.columns:
                    if col != "location_id" and row[col] > 0:  # skip zero counts
                        nested_data[group_key][col] += row[col]

            # 6. Convert to required format
            final_data = {}
            for group_key, violations in nested_data.items():
                final_data[group_key] = [
                    {"violation_type": vtype, "count": count}
                    for vtype, count in violations.items()
                ]

            return {"status": True, "message": "success", "data": final_data}

        except Exception as e:
            print("Exception:", str(e))
            return {"status": False, "message": str(e), "data": []}


    @staticmethod
    async def vts_alerts_violations(filters, cross_filters, drill_state, payload):
        try:
            query_type = payload.get("query_type") if payload else None
            alert_type = payload.get("alert_type") if payload else None
            base_query = vts_query.vts_query.get(query_type)
            history_query = vts_query.vts_query.get("vts_history_query")
            
            if not base_query or not history_query:
                return {"status": False, "message": "Query not found", "data": [], "percentages": []}

            # Build WHERE conditions dynamically
            all_conditions = []
            if alert_type:
                if alert_type.lower() == "blocked":
                    all_conditions.append("alert_status = 'Open'")
                elif alert_type.lower() == "auto_unblock":
                    all_conditions.append("alert_status = 'Close' AND mark_as_false = false")
                elif alert_type.lower() == "manual_unblock":
                    all_conditions.append("alert_status = 'Close' AND mark_as_false = true")
                # 'all_alerts' -> no extra conditions

            # Filters
            if filters:
                for rec in filters:
                    key, val = rec.key, rec.value
                    if isinstance(val, str):
                        all_conditions.append(f"{key} = '{val}'")
                    elif isinstance(val, list):
                        all_conditions.append(f"{key} IN {tuple(val)}")

            # Cross filters
            if cross_filters:
                for rec in cross_filters:
                    if "DATE" in rec.key.upper():
                        start = rec.value.split(",")[0]
                        end = (datetime.strptime(rec.value.split(",")[-1], "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
                        all_conditions.append(f"created_at BETWEEN '{start}' AND '{end}'")
                    else:
                        values = rec.value.split(",") if isinstance(rec.value, str) else rec.value
                        if len(values) == 1:
                            all_conditions.append(f"{rec.key} = '{values[0]}'")
                        else:
                            all_conditions.append(f"{rec.key} IN {tuple(values)}")

            # Apply conditions to alerts query
            query = base_query  # Initialize with base query
            if all_conditions:
                if "group by" in query.lower():
                    idx = query.lower().index("group by")
                    base_part = query[:idx].strip()
                    group_by_part = query[idx:].strip()
                    if "where" not in base_part.lower():
                        query = base_part + " WHERE " + " AND ".join(all_conditions) + " " + group_by_part
                    else:
                        query = base_part + " AND " + " AND ".join(all_conditions) + " " + group_by_part
                else:
                    if "where" not in query.lower():
                        query += " WHERE "
                    else:
                        query += " AND "
                    query += " AND ".join(all_conditions)

            # FIX: Use the filtered query instead of base_query
            alerts_resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=0)
            alerts_data = alerts_resp.get("data", [])
            if not alerts_data:
                return {"status": True, "message": "success", "data": [], "percentages": []}
            alerts_df = pd.DataFrame(alerts_data)

            history_resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=history_query, limit=0)
            history_data = history_resp.get("data", [])
            if not history_data:
                return {"status": True, "message": "success", "data": [], "percentages": []}
            history_df = pd.DataFrame(history_data)

            merged_df = pd.merge(
                alerts_df,
                history_df,
                left_on="vehicle_number",
                right_on="tl_number",
                how="inner"
            )

            # FIX: Initialize group_by_column properly
            group_by_column = None
            if drill_state.lower() == "zone":
                group_by_column = "zone"
            elif drill_state.lower() == "location":
                group_by_column = "location_name"
                
            if not group_by_column:
                return {"status": False, "message": "No valid group column found", "data": [], "percentages": []}
            
            # Check if the group column exists in merged dataframe
            if group_by_column not in merged_df.columns:
                return {"status": False, "message": f"Column '{group_by_column}' not found in data", "data": [], "percentages": []}
            
            merged_df = merged_df[merged_df[group_by_column].notnull() & (merged_df[group_by_column] != "")]
            
            # Check if we have any data after filtering
            if merged_df.empty:
                return {"status": True, "message": "success", "data": [], "percentages": []}
            
            violation_columns = [col for col in history_df.columns if col not in ["invoice_number", "tl_number"]]
            
            # Check if violation columns exist
            if not violation_columns:
                return {"status": True, "message": "success", "data": [], "percentages": []}
            
            # Filter existing violation columns only
            existing_violation_columns = [col for col in violation_columns if col in merged_df.columns]
            if not existing_violation_columns:
                return {"status": True, "message": "success", "data": [], "percentages": []}
            
            merged_df = merged_df[(merged_df[existing_violation_columns].sum(axis=1) != 0)]
            
            # Check if we have any data after removing zero-violation rows
            if merged_df.empty:
                return {"status": True, "message": "success", "data": [], "percentages": []}

            # Group by dynamically
            grouped = merged_df.groupby(group_by_column)[existing_violation_columns].sum().reset_index()

            # Prepare final response
            data_response = []
            for _, row in grouped.iterrows():
                violations_list = []
                for col in existing_violation_columns:
                    if row[col] != 0:
                        violations_list.append({"violation_type": col, "count": int(row[col])})
                
                # Only add to response if there are violations
                if violations_list:
                    data_response.append({row[group_by_column]: violations_list})

            # Calculate percentages
            totals = grouped[existing_violation_columns].sum().to_dict()
            grand_total = sum(totals.values())
            percentages = []
            if grand_total > 0:
                for vtype, count in totals.items():
                    if count > 0:
                        percentages.append({
                            "violation_type": vtype,
                            "percentage": round((count / grand_total) * 100, 2)
                        })

            return {
                "status": True,
                "message": "success",
                "data": data_response,
                "percentages": percentages
            }

        except Exception as e:
            print("Exception in vts_alerts_violations:", str(e))
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": [], "percentages": []}
        
    @staticmethod
    async def violation_trends_over_time(filters, cross_filters, drill_state, payload):
        try:
            query_type = payload.get("query_type") if payload else None
            alert_type = payload.get("alert_type") if payload else None
            base_query = vts_query.vts_query.get(query_type)
            history_query = vts_query.vts_query.get("vts_history_query")
            
            if not base_query or not history_query:
                return {"status": False, "message": "Query not found", "data": [], "percentages": []}

            # Build WHERE conditions dynamically
            all_conditions = []
            if alert_type:
                if alert_type.lower() == "blocked":
                    all_conditions.append("alert_status = 'Open'")
                elif alert_type.lower() == "auto_unblock":
                    all_conditions.append("alert_status = 'Close' AND mark_as_false = false")
                elif alert_type.lower() == "manual_unblock":
                    all_conditions.append("alert_status = 'Close' AND mark_as_false = true")
                # 'all_alerts' -> no extra conditions

            # Filters
            if filters:
                for rec in filters:
                    key, val = rec.key, rec.value
                    if isinstance(val, str):
                        all_conditions.append(f"{key} = '{val}'")
                    elif isinstance(val, list):
                        all_conditions.append(f"{key} IN {tuple(val)}")

            # Cross filters
            if cross_filters:
                for rec in cross_filters:
                    if "DATE" in rec.key.upper():
                        start = rec.value.split(",")[0]
                        end = (datetime.strptime(rec.value.split(",")[-1], "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
                        all_conditions.append(f"created_at BETWEEN '{start}' AND '{end}'")
                    else:
                        values = rec.value.split(",") if isinstance(rec.value, str) else rec.value
                        if len(values) == 1:
                            all_conditions.append(f"{rec.key} = '{values[0]}'")
                        else:
                            all_conditions.append(f"{rec.key} IN {tuple(values)}")
            
            period_expr = ""
            if drill_state.lower() == "day_wise":
                period_expr = "DATE(created_at)"
            elif drill_state.lower() == "month_wise":
                period_expr = "DATE_TRUNC('month', created_at)"
           
            # Construct query dynamically
            query = base_query.format(period_expr=period_expr)

            if all_conditions:
                if "order by" in query.lower():
                    idx = query.lower().index("order by")
                    base_part = query[:idx].strip()
                    order_by_part = query[idx:].strip()
                    if "where" not in base_part.lower():
                        query = base_part + " WHERE " + " AND ".join(all_conditions) + " " + order_by_part
                    else:
                        query = base_part + " AND " + " AND ".join(all_conditions) + " " + order_by_part
                else:
                    if "where" not in query.lower():
                        query += " WHERE "
                    else:
                        query += " AND "
                    query += " AND ".join(all_conditions)
               
            alerts_resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=0)
            alerts_data = alerts_resp.get("data", [])
            if not alerts_data:
                return {"status": True, "message": "success", "data": []}
            alerts_df = pd.DataFrame(alerts_data)

            history_resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=history_query, limit=0)
            history_data = history_resp.get("data", [])
            if not history_data:
                return {"status": True, "message": "success", "data": []}
            history_df = pd.DataFrame(history_data)

            merged_df = pd.merge(
                alerts_df,
                history_df,
                left_on="vehicle_number",
                right_on="tl_number",
                how="inner"
            )

            violation_columns = [col for col in history_df.columns if col not in ["period","invoice_number", "tl_number"]]
            merged_df = merged_df[(merged_df[violation_columns].sum(axis=1) != 0)&
                                  (merged_df["period"].notna()) &                      
                                  (merged_df["period"].astype(str).str.strip() != "")]


            result = []
            for period, group_df in merged_df.groupby("period"):
                if drill_state and drill_state.lower() == "day_wise":
                    formatted_date = pd.to_datetime(period).strftime("%b-%d-%Y")
                elif drill_state and drill_state.lower() == "month_wise":
                    formatted_date = pd.to_datetime(period).strftime("%b-%d-%Y")
                
                period_totals = group_df[violation_columns].sum()
                
                values = [
                    {"violation_type": col, "count": int(period_totals[col])}
                    for col in violation_columns
                    if period_totals[col] != 0
                ]

                result.append({"date": formatted_date, "records": values})
            
            return {"status": True, "message": "success", "data": result}


        except Exception as e:
            print("Exception in vts_alerts_violations:", str(e))
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
        
    @staticmethod
    async def violation_details(filters, cross_filters,drill_state,payload):
        try:
            query_type = payload.get("query_type") if payload else None
            violation_type = payload.get("violation_type")
            base_query = vts_query.vts_query.get(query_type)
            if not base_query:
                return {"status": False, "message": "Query not found", "data": []}

            # Build WHERE conditions dynamically
            all_conditions = []

            if filters:
                for rec in filters:
                    key, val = rec.key, rec.value
                    if isinstance(val, str):
                        all_conditions.append(f"{key} = '{val}'")
                    elif isinstance(val, list):
                        all_conditions.append(f"{key} IN {tuple(val)}")

            if cross_filters:
                for rec in cross_filters:
                    if "DATE" in rec.key.upper():
                        start = rec.value.split(",")[0]
                        end = (datetime.strptime(rec.value.split(",")[-1], "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
                        all_conditions.append(f"created_at BETWEEN '{start}' AND '{end}'")
                    else:
                        values = rec.value.split(",") if isinstance(rec.value, str) else rec.value
                        if len(values) == 1:
                            all_conditions.append(f"{rec.key} = '{values[0]}'")
                        else:
                            all_conditions.append(f"{rec.key} IN {tuple(values)}")

            # Determine period expression based on drill_state
            period_expr = ""
            if drill_state.lower() == "day_wise":
                period_expr = "DATE(created_at)"
            elif drill_state.lower() == "month_wise":
                period_expr = "DATE_TRUNC('month', created_at)"
           
            # Construct query dynamically
            query = base_query.format(period_expr=period_expr, violation_type = violation_type)

            if all_conditions:
                if "group by" in query.lower():
                    idx = query.lower().index("group by")
                    base_part = query[:idx].strip()
                    group_by_part = query[idx:].strip()
                    if "where" not in base_part.lower():
                        query = base_part + " WHERE " + " AND ".join(all_conditions) + " " + group_by_part
                    else:
                        query = base_part + " AND " + " AND ".join(all_conditions) + " " + group_by_part
                else:
                    if "where" not in query.lower():
                        query += " WHERE "
                    else:
                        query += " AND "
                    query += " AND ".join(all_conditions)

            # Execute query
            resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=0)
            data = resp.get("data", [])
            if not data:
                return {"status": True, "message": "success", "data": []}

            # Format response as list of dicts
            df = pd.DataFrame(data)

            numeric_cols = [col for col in df.columns if col != "period"]
            
            for col in numeric_cols:
                 df[col] = df[col].astype(int)
            
            summary_cols = numeric_cols[:4] 
            instance_cols = numeric_cols[4:]
            summary_counts = [{col: int(df[col].sum()) for col in summary_cols}]
            
            overall_instance_totals = {}
            for col in instance_cols:
                overall_instance_totals[col] = int(df[col].sum())
                
            grand_total = sum(overall_instance_totals.values())

            instance_breakup = {}
            for col, total_count in overall_instance_totals.items():
                instance_breakup[col] = {
                    "total_count": total_count,
                    "percentage": round((total_count / grand_total) * 100, 2) if grand_total > 0 else 0
                }

            period_data = []
            for _, row in df.iterrows():
                # Collect counts for this date
                counts = {col: int(row[col]) for col in instance_cols}

                if drill_state and drill_state.lower() == "day_wise":
                        formatted_date = pd.to_datetime(row["period"]).strftime("%b-%d-%Y")
                elif drill_state and drill_state.lower() == "month_wise":
                        formatted_date = pd.to_datetime(row["period"]).strftime("%b-%d-%Y")
              
              
                period_data.append({
                "date": formatted_date,
                "value": {
                    "counts": counts
                }
              })
        
            return {
            "status": True,
            "message": "success",
            "data": {
                violation_type: summary_counts,
                "period_wise": period_data,
                "instance_breakup": instance_breakup
            }
          }
        
        except Exception as e:
            print("Exception:", str(e))
            print(traceback.format_exc())
            return {"status": False, "message": str(e), "data": {}}
        
    @staticmethod
    async def alert_summary(filters,cross_filters,drill_state,payload):
        try:
            # 1. Get query type from payload
            query_type = payload.get("query_type") if payload else None
            violation_type = payload.get("violation_type")
            query = vts_query.vts_query.get(query_type)
            if not query:
                return {"status": False, "message": "Query not found", "data": []}
            
            if drill_state and "location" in drill_state.lower():
                group_by_column = "location_name"
            elif drill_state and "zone" in drill_state.lower():
                group_by_column = "zone"

            
            # 2. Build conditions (same logic as before)
            all_conditions = []
            if filters:
                for rec in filters:
                    key, val = rec.key, rec.value
                    if isinstance(val, str):
                        all_conditions.append(f"{key} = '{val}'")
                    elif isinstance(val, list):
                        all_conditions.append(f"{key} IN {tuple(val)}")

            if cross_filters:
                for rec in cross_filters:
                    if "DATE" in rec.key:
                        start = rec.value.split(",")[0]
                        end = (datetime.strptime(rec.value.split(",")[-1], "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
                        all_conditions.append(f"created_at BETWEEN '{start}' AND '{end}'")
                    else:
                        values = rec.value.split(",") if isinstance(rec.value, str) else rec.value
                        if len(values) == 1:
                            all_conditions.append(f"{rec.key} = '{values[0]}'")
                        else:
                            all_conditions.append(f"{rec.key} IN {tuple(values)}")
            
            query = query.format(group_by_column=group_by_column, violation_type = violation_type)

            if all_conditions:
                if "group by" in query.lower():
                    idx = query.lower().index("group by")
                    base_part = query[:idx].strip()
                    group_by_part = query[idx:].strip()
                    if "where" not in base_part.lower():
                        query = base_part + " WHERE " + " AND ".join(all_conditions) + " " + group_by_part
                    else:
                        query = base_part + " AND " + " AND ".join(all_conditions) + " " + group_by_part
                else:
                    if "where" not in query.lower():
                        query += " WHERE "
                    else:
                        query += " AND "
                    query += " AND ".join(all_conditions)
               

            # 3. Execute main query (location_id + violation counts)
            resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=0)
            resp = pd.DataFrame(resp.get("data", []))
            resp = resp[resp[group_by_column].notna()]
            resp = resp[resp[group_by_column].astype(str).str.strip() != ""]

            if resp.empty:
                return {"status": True, "message": "no data", "data": {}}
           
            final_result = {}
            for _, row in resp.iterrows():
                group_val = row[group_by_column] 
                instance = row["instance_level"]

                if group_val not in final_result:
                    final_result[group_val] = []

                # Wrap instance as key → list → dict
                final_result[group_val].append({
                    instance: [{
                        "Blocked": row["Blocked"],
                        "Auto Unblock": row["Auto Unblock"],
                        "Manual Unblock": row["Manual Unblock"],
                        "Total": row["Total"]
                    }]
                })

            return {"status": True, "message": "success", "data": final_result}

        except Exception as e:
            return {"status": False, "message": str(e), "data": {}}
        
