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
           violation_types = payload.get("violation_type", [])
           if violation_types:
                results = []
                violation_type_query = vts_query.vts_query.get("vts_insite_violation_type")
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, violation_type_query)
                conditions = VTSAnalyticsActions.add_alert_type_conditions(conditions, alert_type)

                email_query = """SELECT transporter_code, transporter_name FROM email_master"""
                df_email = await VTSAnalyticsActions.execute_query(email_query)
                
                for v_type in violation_types:
                    formatted_query = violation_type_query.format(violation_type=v_type)
                    final_query = VTSAnalyticsActions.apply_conditions_to_query(formatted_query, conditions)
                    df_data = await VTSAnalyticsActions.execute_query(final_query)
                    merged_df = df_data.merge(df_email, on="transporter_code", how="left")
                    merged_df.drop(columns=["transporter_code"], inplace=True)
                    merged_df.dropna(inplace=True)
                    results.extend(merged_df.to_dict(orient="records"))

                return {"status": True, "message": "success", "data": results}
                                      
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