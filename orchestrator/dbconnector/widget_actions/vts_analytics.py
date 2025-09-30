import urdhva_base
import traceback
import pandas as pd
from datetime import datetime
import orchestrator.dbconnector.widget_actions.vts_query as vts_query
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import orchestrator.dbconnector.credential_loader as credential_loader
import asyncio
import mysql.connector


class VTSAnalyticsActions:
    
    @staticmethod
    def transform_key(key, query=None):
        """Transform keys based on query context"""
        if query and "vts_alert_history" in query.lower() and key.lower() == "bu":
            return "location_type"
        return key
    
    @staticmethod
    def build_filter_conditions(filters, cross_filters, query=None):
        """Build WHERE conditions from filters and cross_filters"""
        all_conditions = []
        
        # Process regular filters
        if filters:
            for rec in filters:
                key = VTSAnalyticsActions.transform_key(rec.key, query)
                val = rec.value
                
                condition = VTSAnalyticsActions.create_condition(key, val)
                if condition:
                    all_conditions.append(condition)

        # Process cross filters
        if cross_filters:
            for rec in cross_filters:
                key = rec.key
                val = rec.value
                
                if "DATE" in key.upper():
                    condition = VTSAnalyticsActions.create_date_condition(val)
                else:
                    condition = VTSAnalyticsActions.create_condition(key, val)
                
                if condition:
                    all_conditions.append(condition)
        
        return all_conditions

    @staticmethod
    def create_condition(key, val):
        """Create a single condition based on key and value"""
        if isinstance(val, str):
            if "," in val:  # Handle comma-separated values in string
                values = val.split(",")
                if len(values) == 1:
                    return f"{key} = '{values[0]}'"
                else:
                    return f"{key} IN {tuple(values)}"
            return f"{key} = '{val}'"
        elif isinstance(val, list):
            if len(val) == 1:
                return f"{key} = '{val[0]}'"
            else:
                return f"{key} IN {tuple(val)}"
        return None

    @staticmethod
    def create_date_condition(val):
        """Create date range condition"""
        start = val.split(",")[0]
        end = (datetime.strptime(val.split(",")[-1], "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
        return f"created_at BETWEEN '{start}' AND '{end}'"

    @staticmethod
    def apply_conditions_to_query(query, conditions):
        """Apply WHERE conditions to query while preserving GROUP BY and ORDER BY"""
        if not conditions:
            return query
        
        conditions_str = " AND ".join(conditions)
        query_lower = query.lower()

        if ") as history_data" in query_lower:
            # Split into two parts: before and after the subquery alias
            idx = query_lower.index(") as history_data")
            subquery_part = query[:idx]  # everything inside the subquery
            rest_part = query[idx:]      # the alias + group by etc.

            # Insert conditions inside the subquery WHERE clause
            if "where" in subquery_part.lower():
                subquery_part = subquery_part.rstrip() + f" AND {conditions_str}"
            else:
                subquery_part = subquery_part.rstrip() + f" WHERE {conditions_str}"

            return subquery_part + rest_part
        
        # Handle queries with GROUP BY
        if "group by" in query_lower:
            idx = query_lower.index("group by")
            base_part = query[:idx].strip()
            group_by_part = query[idx:].strip()
            
            if "where" not in base_part.lower():
                return f"{base_part} WHERE {conditions_str} {group_by_part}"
            else:
                return f"{base_part} AND {conditions_str} {group_by_part}"
        
        # Handle queries with ORDER BY (no GROUP BY)
        elif "order by" in query_lower:
            idx = query_lower.index("order by")
            base_part = query[:idx].strip()
            order_by_part = query[idx:].strip()
            
            if "where" not in base_part.lower():
                return f"{base_part} WHERE {conditions_str} {order_by_part}"
            else:
                return f"{base_part} AND {conditions_str} {order_by_part}"
        
        # Simple query without GROUP BY or ORDER BY
        else:
            if "where" not in query_lower:
                return f"{query} WHERE {conditions_str}"
            else:
                return f"{query} AND {conditions_str}"

    @staticmethod
    def add_alert_type_conditions(conditions, alert_type):
        """Add alert type specific conditions"""
        if not alert_type:
            return conditions
            
        if alert_type.lower() == "blocked":
            conditions.append("alert_status = 'Open'")
        elif alert_type.lower() == "auto_unblock":
            conditions.append("alert_status = 'Close' AND mark_as_false = false")
        elif alert_type.lower() == "manual_unblock":
            conditions.append("alert_status = 'Close' AND mark_as_false = true")
        # 'all_alerts' -> no extra conditions
        
        return conditions

    @staticmethod
    def get_period_expression(drill_state):
        """Get period expression based on drill state"""
        if drill_state and drill_state.lower() == "day_wise":
            return "DATE(created_at)"
        elif drill_state and drill_state.lower() == "month_wise":
            return "DATE_TRUNC('month', created_at)"
        return ""

    @staticmethod
    def get_group_by_column(drill_state):
        """Get group by column based on drill state"""
        if drill_state and "location" in drill_state.lower():
            return "location_name"
        elif drill_state and "zone" in drill_state.lower():
            return "zone"
        return None

    @staticmethod
    def format_date(period, drill_state):
        """Format date based on drill state"""
        if drill_state and drill_state.lower() in ["day_wise", "month_wise"]:
            return pd.to_datetime(period).strftime("%b-%d-%Y")
        return str(period)

    @staticmethod
    async def execute_query(query, limit=0):
        """Execute query and return DataFrame"""
        try:
            resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=limit)
            data = resp.get("data", [])
            return pd.DataFrame(data) if data else pd.DataFrame()
        except Exception as e:
            print(f"Query execution error: {e}")
            return pd.DataFrame()

    @staticmethod
    async def vts_card_chart(filters, cross_filters, drill_state, payload):    
        try:
            # Get base query           
            card_query = vts_query.vts_query.get(drill_state.split(",")[0])
            print("Base Query:", card_query)

            # Build and apply conditions (pass the query for key transformation)
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, card_query)
            final_query = VTSAnalyticsActions.apply_conditions_to_query(card_query, conditions)
            
            print("-" * 50)
            print("Final card_query ---->", final_query)

            # Execute query
            df = await VTSAnalyticsActions.execute_query(final_query)
            return {"status": True, "message": "success", "data": df.to_dict(orient="records")}

        except Exception as e:
            print("Exception in BigNumber Chart:", str(e))
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
    
    @staticmethod
    async def vts_insite(filters, cross_filters, drill_state, payload):
        try:
           query = vts_query.vts_query.get(drill_state.split(",")[0])
           alert_type = payload.get("alert_type") if payload else None
           all_violations = vts_query.vts_query.get("all_violations", [])
           violation_types = payload.get("violation_type", [])
           if violation_types:
                violation_type_query = vts_query.vts_query.get("vts_insite_violation_type")
                if not violation_type_query:
                    return {"status": False, "message": "Query template not found", "data": []}
                    
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, violation_type_query)
                conditions = VTSAnalyticsActions.add_alert_type_conditions(conditions, alert_type)

                select_parts = []
                for v_type in all_violations:
                    select_parts.append(f"SUM(CASE WHEN violation_type = '{v_type}' THEN 1 ELSE 0 END) AS {v_type}")
                having_parts = []
                for v_type in violation_types:
                    having_parts.append(f"SUM(CASE WHEN violation_type = '{v_type}' THEN 1 ELSE 0 END) > 0")
                
                select_clause = ",\n        ".join(select_parts)
                having_clause = " AND ".join(having_parts)
  
                final_query = violation_type_query.format(select_clause=select_clause, having_clause=having_clause)
                final_query = VTSAnalyticsActions.apply_conditions_to_query(final_query, conditions)
                print(final_query)

                df_data = await VTSAnalyticsActions.execute_query(final_query)

                email_query = """SELECT transporter_code, transporter_name FROM email_master"""
                df_email = await VTSAnalyticsActions.execute_query(email_query)
                
                merged_df = df_data.merge(df_email, on="transporter_code", how="left")
                merged_df.drop(columns=["transporter_code"], inplace=True)
                merged_df.dropna(inplace=True)

                return {"status": True, "message": "success", "data": merged_df.to_dict(orient="records")}

                                      
           # Build and apply conditions (pass the query for key transformation)
           conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
           conditions = VTSAnalyticsActions.add_alert_type_conditions(conditions, alert_type)
           
           vts_insite_query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
           print(vts_insite_query)
           df1 = await VTSAnalyticsActions.execute_query(vts_insite_query)

           email_query = """select transporter_code,transporter_name from email_master"""

           df2 = await VTSAnalyticsActions.execute_query(email_query)
           merged_df = df1.merge(df2, on="transporter_code", how="left")
           merged_df.drop(columns=["transporter_code"], inplace=True)
           merged_df.dropna(inplace=True)

           return {"status": True, "message": "success", "data": merged_df.to_dict(orient="records")}
        
        
        except Exception as e:
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
    
    @staticmethod
    async def vts_insite_violation(filters, cross_filters, drill_state, payload):
        try:
            query = vts_query.vts_query.get(drill_state.split(",")[0])
            all_violations = vts_query.vts_query.get("all_violations", [])
            violation_types = payload.get("violation_type", []) if payload else []
            truck_number = payload.get("view", "")
            if truck_number:
                all_violations = vts_query.vts_query.get("all_violations", [])
                select_parts = []
                for v_type in all_violations:
                    select_parts.append(
                    f"SUM(CASE WHEN {v_type} != 0 THEN 1 ELSE 0 END) AS {v_type}"
                )
                select_clause = ",\n        ".join(select_parts)
                view_query = f"""
                SELECT 
                    tl_number,
                    invoice_number,
                    DATE(created_at) as violation_date,
                    {select_clause}
                FROM vts_alert_history
                WHERE tl_number = '{truck_number}'
                GROUP BY tl_number, invoice_number, DATE(created_at)
                ORDER BY violation_date DESC, invoice_number
                """
                print("View Query:", view_query)
                df_view = await VTSAnalyticsActions.execute_query(view_query)
                if df_view.empty:
                    return {"status": True, "message": "No violation history found for this vehicle", "data": []}
                alerts_query = f"""SELECT DISTINCT location_name, vehicle_number, transporter_code, zone 
                              FROM alerts 
                              WHERE vehicle_number = '{truck_number}' 
                              AND transporter_code != '' AND location_name != ''"""
                print("Alerts Query:", alerts_query)
                df_alerts = await VTSAnalyticsActions.execute_query(alerts_query)
                
                if df_alerts.empty:
                    return {"status": False, "message": "No matching vehicle details found in alerts", "data": []}
                
                # Merge with alerts data
                merged_df = df_view.merge(df_alerts, left_on="tl_number", right_on="vehicle_number", how="left")
                
                # Get transporter names
                email_query = """SELECT transporter_code, transporter_name FROM email_master"""
                print("Email Query:", email_query)
                df_email = await VTSAnalyticsActions.execute_query(email_query)
                
                # Final merge with email master
                final_df = merged_df.merge(df_email, on="transporter_code", how="left")
                final_df.drop(columns=["transporter_code"], inplace=True)
                final_df.dropna(inplace=True)
                
                if final_df.empty:
                    return {"status": False, "message": "No valid data after filtering transporter details", "data": []}
                
                cleaned_records = []
                for _, row in final_df.iterrows():
                    record = row.to_dict()
                    if all(record.get(v_type, 0) == 0 for v_type in all_violations):
                        continue 
                    cleaned_records.append(record)
                    if not cleaned_records:
                        return {"status": True, "message": "No non-zero violations found", "data": []}
                
                return {"status": True, "message": "success", "data": cleaned_records}
            if violation_types:
                violation_type_query = vts_query.vts_query.get("vts_insite_history_type")
                if not violation_type_query:
                    return {"status": False, "message": "Query template not found", "data": []}
                
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, violation_type_query)
                select_parts = []
                for v_type in all_violations:
                    select_parts.append(f"COUNT(DISTINCT CASE WHEN {v_type} != 0 THEN invoice_number END) AS {v_type}")
                having_parts = []
                for v_type in violation_types:
                    having_parts.append(f"COUNT(DISTINCT CASE WHEN {v_type} != 0 THEN invoice_number END) > 0")
                
                select_clause = ",\n        ".join(select_parts)
                having_clause = " AND ".join(having_parts)

                final_query = violation_type_query.format(select_clause=select_clause, having_clause=having_clause)
                final_query = VTSAnalyticsActions.apply_conditions_to_query(final_query, conditions)
                print(final_query)
                
                df_history = await VTSAnalyticsActions.execute_query(final_query)
                if df_history.empty:
                     return {"status": True, "message": "No history data found", "data": []}
                
               
                tl_numbers_list = df_history['tl_number'].tolist()
                tl_numbers_str = "', '".join(map(str, tl_numbers_list))
                alerts_query = f"""SELECT DISTINCT  location_name, vehicle_number, transporter_code, zone 
                                  FROM alerts 
                                  WHERE vehicle_number IN ('{tl_numbers_str}') 
                                  AND transporter_code != '' AND location_name != ''"""
                print(alerts_query)
                df_alerts = await VTSAnalyticsActions.execute_query(alerts_query)

                # Check if alerts data exists
                if df_alerts.empty:
                      return {"status": False, "message": "No matching vehicle details found in alerts", "data": []}
                
                # Merge history with alerts data
                merged_df = df_history.merge(df_alerts, left_on="tl_number", right_on="vehicle_number", how="left")
                    
                    
                email_query = """SELECT transporter_code, transporter_name FROM email_master"""
                print(email_query)
                df_email = await VTSAnalyticsActions.execute_query(email_query)
                # Final merge with email master
                final_df = merged_df.merge(df_email, on="transporter_code", how="left")
                final_df.drop(columns=["transporter_code"], inplace=True)
                final_df.dropna(inplace=True)

                return {"status": True, "message": "success", "data": final_df.to_dict(orient="records")}
                
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            print(query)
            df_history = await VTSAnalyticsActions.execute_query(query)
            if df_history.empty:
                 return {"status": True, "message": "No history data found", "data": []}

            # Get vehicle details from alerts table using tl_numbers from history data
            tl_numbers_list = df_history['tl_number'].tolist()
            tl_numbers_str = "', '".join(map(str, tl_numbers_list))
            alerts_query = f"""SELECT DISTINCT  location_name, vehicle_number, transporter_code, zone 
                              FROM alerts 
                              WHERE vehicle_number IN ('{tl_numbers_str}') 
                              AND transporter_code != '' AND location_name != ''"""
            df_alerts = await VTSAnalyticsActions.execute_query(alerts_query)

            # Check if alerts data exists
            if df_alerts.empty:
                return {"status": False, "message": "No matching vehicle details found in alerts", "data": []}
            
            # Merge history with alerts data
            merged_df = df_history.merge(df_alerts, left_on="tl_number", right_on="vehicle_number", how="left")

            # Get transporter names
            email_query = """SELECT transporter_code, transporter_name FROM email_master"""
            df_email = await VTSAnalyticsActions.execute_query(email_query)
            
            # Final merge with email master
            final_df = merged_df.merge(df_email, on="transporter_code", how="left")
            final_df.drop(columns=["transporter_code"], inplace=True)
            final_df.dropna(inplace=True)

            return {"status": True, "message": "success", "data": final_df.to_dict(orient="records")}
        
       
            
        except Exception as e:
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}



    @staticmethod
    async def location_level_voilation_breakup(filters, cross_filters, drill_state, payload):
        try:
            # Get query from payload
            query_type = payload.get("query_type") if payload else None
            query = vts_query.vts_query.get(query_type)
            if not query:
                return {"status": False, "message": "Query not found", "data": []}

            # Build and apply conditions (pass the query for key transformation)
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            final_query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)

            # Execute main query
            df = await VTSAnalyticsActions.execute_query(final_query)
            if df.empty:
                return {"status": True, "message": "no data", "data": {}}

            # Fetch location master data
            loc_master_query = "SELECT sap_id, name, zone FROM location_master"
            loc_master_df = await VTSAnalyticsActions.execute_query(loc_master_query)

            # Create location mapping
            loc_map = {}
            for _, row in loc_master_df.iterrows():
                loc_map[row["sap_id"]] = {
                    "zone": row["zone"],
                    "name": row["name"]
                }

            # Build nested data
            nested_data = defaultdict(lambda: defaultdict(int))

            for _, row in df.iterrows():
                location_id = row["location_id"]
                
                # Determine group key
                group_key = None
                if location_id in loc_map:
                    if drill_state and "location" in drill_state.lower():
                        group_key = loc_map[location_id]["name"]
                    elif drill_state and "zone" in drill_state.lower():
                        group_key = loc_map[location_id]["zone"]

                if not group_key:
                    continue

                # Aggregate violation counts
                for col in df.columns:
                    if col != "location_id" and row[col] > 0:
                        nested_data[group_key][col] += row[col]

            # Format final data
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

            # Build conditions with alert type (pass base_query for key transformation)
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, base_query)
            conditions = VTSAnalyticsActions.add_alert_type_conditions(conditions, alert_type)
            
            # Apply conditions to alerts query
            alerts_query = VTSAnalyticsActions.apply_conditions_to_query(base_query, conditions)

            # Execute queries
            alerts_df = await VTSAnalyticsActions.execute_query(alerts_query)
            history_df = await VTSAnalyticsActions.execute_query(history_query)
            
            if alerts_df.empty or history_df.empty:
                return {"status": True, "message": "success", "data": [], "percentages": []}

            # Merge dataframes
            merged_df = pd.merge(
                alerts_df, history_df,
                left_on="vehicle_number", right_on="tl_number",
                how="inner"
            )

            # Get group by column
            group_by_column = VTSAnalyticsActions.get_group_by_column(drill_state)
            if not group_by_column or group_by_column not in merged_df.columns:
                return {"status": False, "message": f"Column '{group_by_column}' not found", "data": [], "percentages": []}
            
            # Filter out null/empty values
            merged_df = merged_df[
                merged_df[group_by_column].notnull() & 
                (merged_df[group_by_column] != "")
            ]
            
            if merged_df.empty:
                return {"status": True, "message": "success", "data": [], "percentages": []}
            
            # Get violation columns and filter non-zero violations
            violation_columns = [col for col in history_df.columns if col not in ["invoice_number", "tl_number"]]
            existing_violation_columns = [col for col in violation_columns if col in merged_df.columns]
            
            if not existing_violation_columns:
                return {"status": True, "message": "success", "data": [], "percentages": []}
            
            merged_df = merged_df[merged_df[existing_violation_columns].sum(axis=1) != 0]
            
            if merged_df.empty:
                return {"status": True, "message": "success", "data": [], "percentages": []}

            # Group and aggregate
            grouped = merged_df.groupby(group_by_column)[existing_violation_columns].sum().reset_index()

            # Prepare response data
            data_response = []
            for _, row in grouped.iterrows():
                violations_list = [
                    {"violation_type": col, "count": int(row[col])}
                    for col in existing_violation_columns
                    if row[col] != 0
                ]
                
                if violations_list:
                    data_response.append({row[group_by_column]: violations_list})

            # Calculate percentages
            totals = grouped[existing_violation_columns].sum().to_dict()
            grand_total = sum(totals.values())
            percentages = []
            if grand_total > 0:
                percentages = [
                    {"violation_type": vtype, "percentage": round((count / grand_total) * 100, 2)}
                    for vtype, count in totals.items()
                    if count > 0
                ]

            return {
                "status": True, "message": "success",
                "data": data_response, "percentages": percentages
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
                return {"status": False, "message": "Query not found", "data": []}

            # Build conditions with alert type (pass base_query for key transformation)
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, base_query)
            conditions = VTSAnalyticsActions.add_alert_type_conditions(conditions, alert_type)

            # Get period expression and format query
            period_expr = VTSAnalyticsActions.get_period_expression(drill_state)
            alerts_query = base_query.format(period_expr=period_expr)
            alerts_query = VTSAnalyticsActions.apply_conditions_to_query(alerts_query, conditions)

            # Execute queries
            alerts_df = await VTSAnalyticsActions.execute_query(alerts_query)
            history_df = await VTSAnalyticsActions.execute_query(history_query)
            
            if alerts_df.empty or history_df.empty:
                return {"status": True, "message": "success", "data": []}

            # Merge and process data
            merged_df = pd.merge(
                alerts_df, history_df,
                left_on="vehicle_number", right_on="tl_number",
                how="inner"
            )

            violation_columns = [col for col in history_df.columns 
                               if col not in ["period", "invoice_number", "tl_number"]]
            
            merged_df = merged_df[
                (merged_df[violation_columns].sum(axis=1) != 0) &
                (merged_df["period"].notna()) &                      
                (merged_df["period"].astype(str).str.strip() != "")
            ]

            # Group by period and format results
            result = []
            for period, group_df in merged_df.groupby("period"):
                formatted_date = VTSAnalyticsActions.format_date(period, drill_state)
                period_totals = group_df[violation_columns].sum()
                
                values = [
                    {"violation_type": col, "count": int(period_totals[col])}
                    for col in violation_columns
                    if period_totals[col] != 0
                ]

                result.append({"date": formatted_date, "records": values})
            
            return {"status": True, "message": "success", "data": result}

        except Exception as e:
            print("Exception in violation_trends_over_time:", str(e))
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
        


    @staticmethod
    async def violation_details(filters, cross_filters, drill_state, payload):
        try:
            query_type = payload.get("query_type") if payload else None
            violation_type = payload.get("violation_type")
            base_query = vts_query.vts_query.get(query_type)
            
            if not base_query:
                return {"status": False, "message": "Query not found", "data": []}

            # Build conditions and format query (pass base_query for key transformation)
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, base_query)
            period_expr = VTSAnalyticsActions.get_period_expression(drill_state)
            
            query = base_query.format(period_expr=period_expr, violation_type=violation_type)
            final_query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)

            # Execute query
            df = await VTSAnalyticsActions.execute_query(final_query)
            if df.empty:
                return {"status": True, "message": "success", "data": []}

            # Process numeric columns
            numeric_cols = [col for col in df.columns if col != "period"]
            for col in numeric_cols:
                df[col] = df[col].astype(int)
            
            # Split columns into summary and instance
            summary_cols = numeric_cols[:4] 
            instance_cols = numeric_cols[4:]
            
            # Calculate summaries
            summary_counts = [{col: int(df[col].sum()) for col in summary_cols}]
            
            overall_instance_totals = {col: int(df[col].sum()) for col in instance_cols}
            grand_total = sum(overall_instance_totals.values())

            instance_breakup = {}
            for col, total_count in overall_instance_totals.items():
                instance_breakup[col] = {
                    "total_count": total_count,
                    "percentage": round((total_count / grand_total) * 100, 2) if grand_total > 0 else 0
                }

            # Format period data
            period_data = []
            for _, row in df.iterrows():
                counts = {col: int(row[col]) for col in instance_cols}
                formatted_date = VTSAnalyticsActions.format_date(row["period"], drill_state)
                
                period_data.append({
                    "date": formatted_date,
                    "value": {"counts": counts}
                })
        
            return {
                "status": True, "message": "success",
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
    async def alert_summary(filters, cross_filters, drill_state, payload):
        try:
            query_type = payload.get("query_type") if payload else None
            violation_type = payload.get("violation_type")
            query = vts_query.vts_query.get(query_type)
            
            if not query:
                return {"status": False, "message": "Query not found", "data": []}
            
            # Get group by column and build conditions (pass query for key transformation)
            group_by_column = VTSAnalyticsActions.get_group_by_column(drill_state)
            if not group_by_column:
                return {"status": False, "message": "Invalid drill state", "data": []}
                
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            
            # Format and execute query
            formatted_query = query.format(group_by_column=group_by_column, violation_type=violation_type)
            final_query = VTSAnalyticsActions.apply_conditions_to_query(formatted_query, conditions)

            df = await VTSAnalyticsActions.execute_query(final_query)
            
            # Filter out null/empty values
            df = df[df[group_by_column].notna()]
            df = df[df[group_by_column].astype(str).str.strip() != ""]

            if df.empty:
                return {"status": True, "message": "no data", "data": {}}
           
            # Format results
            final_result = {}
            for _, row in df.iterrows():
                group_val = row[group_by_column] 
                instance = row["instance_level"]

                if group_val not in final_result:
                    final_result[group_val] = []

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

    @staticmethod
    async def card_chart_shortage(filters, cross_filters, drill_state, payload):
        try:
            card_query = vts_query.vts_query.get(drill_state.split(",")[0])
            query = vts_query.vts_query.get(card_query)
            
            if not query:
                return {"status": False, "message": "Query not found", "data": []}

            # Build and apply conditions (pass query for key transformation)
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            final_query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
            
            # Execute VTS history query
            vts_history = await VTSAnalyticsActions.execute_query(final_query)

            # Execute Tibco query
            conn = await VTSAnalyticsActions.tibco_connection()
            if not conn:
                return {"status": False, "message": "Database connection failed", "data": {}}
                
            shortage_tibco_query = vts_query.vts_query.get("shortage_tibco")
            shortage_resp = await VTSAnalyticsActions.execute_tibco_query(conn, shortage_tibco_query)
            shortage_data = pd.DataFrame(shortage_resp.get("data", []))
            
            # Process and merge data
            vts_history = vts_history[
                pd.notnull(vts_history["invoice_number"]) & 
                (vts_history["invoice_number"] != "")
            ]
            vts_history["invoice_prefix"] = vts_history["invoice_number"].apply(lambda x: x.split("-")[0])

            merged_df = pd.merge(
                vts_history, shortage_data,
                left_on="invoice_prefix", right_on="INVOICE_NO",
                how="inner"
            )
            
            total_qty_shortage = int(merged_df["QTY_SHORTAGE"].sum())
            
            # Calculate total violations
            violation_cols = [col for col in vts_history.columns if col not in ["invoice_number", "invoice_prefix"]]
            total_violation_count = vts_history[violation_cols].sum().sum()

            shortage_percentage = round((total_qty_shortage / total_violation_count) * 100, 2) if total_violation_count > 0 else 0

            conn.close()

            return {
                "status": True, "message": "success",
                "data": {"shortage_percentage": shortage_percentage}
            }

        except Exception as e:
            return {"status": False, "message": str(e), "data": {}}
    
    

    @staticmethod
    async def tibco_connection():
        try:
            creds = credential_loader.get_credentials('TIBCO')
            print("creds --->", creds)
            
            params = {
                "host": creds['host'],
                "database": creds['database'],
                "user": creds['user'],
                "password": creds['password'],
                "port": creds['port']
            }
            
            conn = mysql.connector.connect(**params)
            return conn
        except Exception as e:
            print(f"DB connection failed: {e}")
            return None
    
    @staticmethod
    async def execute_tibco_query(conn, query):
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            return {"data": rows}
        except mysql.connector.Error as e:
            print("Query execution failed:", e)
            return {"data": []}
        
    @staticmethod
    async def integrate_shortage_trips(filters, cross_filters, drill_state, payload):
        alerts_query = """SELECT location_name, bu, vehicle_number, transporter_code FROM alerts where alert_section = 'VTS'"""
        conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, alerts_query)
        final_query = VTSAnalyticsActions.apply_conditions_to_query(alerts_query, conditions)
        print("final_query --->", final_query)
        alerts_df = await VTSAnalyticsActions.execute_query(final_query)
        print(alerts_df.head(5))
        # Extract parameters from filters/payload
        # bu = filters.get("bu") if filters else None
        # violation_type = filters.get("violation_type") if filters else None
        # sap_id = filters.get("sap_id") if filters else None

        print("=== Starting shortage_trips logic ===")
       # print(f"Parameters: BU={bu}, Violation={violation_type}, SAP_ID={sap_id}")

       # alerts_result = await hpcl_ceg_model.Alerts.get_aggr_data(final_query, limit=0)
        #alerts_df = pd.DataFrame(alerts_result['data'])
        

        # Step 2: Fetch trips
        trips_query = "SELECT * FROM sales_trips_till_date"
        trips_df = await VTSAnalyticsActions.execute_query(trips_query)
        #trips_df = pd.DataFrame(trips_result['data'])
        print(f"Trips fetched: {len(trips_df)} rows")

        # Step 3: Assign BU based on plant_nm
        plant_bu_mapping = alerts_df[['location_name', 'bu']].drop_duplicates()
        trips_df = trips_df.merge(
            plant_bu_mapping,
            how='left',
            left_on='plant_nm',
            right_on='location_name'
        ).drop(columns=['location_name'], errors='ignore')
        print(f"Trips after BU mapping: {len(trips_df)}")

        # Step 4: Filter by BU
        # if bu:
        #     trips_df = trips_df[trips_df['bu'] == bu]
        #     print(f"Trips after BU filter: {len(trips_df)}")

        # Step 5: Assign transporter_code based on plant_nm + vehicle_id
        alerts_vehicle_mapping = alerts_df[['location_name', 'vehicle_number', 'transporter_code']].drop_duplicates()
        trips_df = trips_df.merge(
            alerts_vehicle_mapping,
            how='left',
            left_on=['plant_nm', 'vehicle_id'],
            right_on=['location_name', 'vehicle_number']
        ).drop(columns=['vehicle_number', 'location_name'], errors='ignore')
        print(f"Trips after transporter_code mapping: {len(trips_df)}")

        # Step 6: Fetch transporter_name from email_master
        email_query = "SELECT transporter_code, transporter_name FROM email_master"
        email_df = await VTSAnalyticsActions.execute_query(email_query)
        #email_df = pd.DataFrame(email_result['data'])

        # Step 7: Merge transporter_name
        trips_df = trips_df.merge(email_df, how='left', on='transporter_code')
        print(f"Trips after transporter_name merge: {len(trips_df)}")

        # Step 8: Count unique invoices
        invoice_count = trips_df['invoice_no'].nunique() if 'invoice_no' in trips_df.columns else 0
        print(f"Unique invoices: {invoice_count}")

        # Step 9: Prepare final trips list
        trips_list = trips_df[['plant_nm', 'vehicle_id', 'qty_shortage', 'transporter_name']].rename(
            columns={
                "plant_nm": "Plant Name",
                "vehicle_id": "Vehicle No",
                "qty_shortage": "Shortage",
                "transporter_name": "Transporter Name"
            }
        )
        trips_list = trips_list.where(pd.notnull(trips_list), None).to_dict(orient="records")
        print(f"Prepared trips list with {len(trips_list)} records")

        # Step 10: Write final DataFrame to CSV (optional, for debugging)
        trips_df.to_csv("shortage_trips_output.csv", index=False)
        print("CSV write complete.")

        response_data = {
            "status": "success",
            "invoice_count": invoice_count,
            "trips": trips_list
        }

        print("=== Finished shortage_trips logic ===\n")
        return response_data