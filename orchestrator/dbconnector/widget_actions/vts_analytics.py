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
        if query and any(x in query.lower() for x in ["vts_alert_history", "vts_ongoing_trips"]) and key.lower() == "bu":
            return "location_type"
        if query and "vts_alert_history" in query.lower() and key.lower() == "sap_id":
            return "location_id"
        return key
    
    @staticmethod
    def build_filter_conditions(filters, cross_filters, query):
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
                    condition = VTSAnalyticsActions.create_date_condition(query,val)
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
    def create_date_condition(query,val):
        """Create date range condition"""
        start = val.split(",")[0]
        end = (datetime.strptime(val.split(",")[-1], "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
        if "vts_alert_history" in query.lower():
            return f"vts_end_datetime BETWEEN '{start}' AND '{end}'"
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
            conditions.append("alert_status = 'Close' AND mark_as_false = false AND vehicle_unblocked_date is not null")
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
                if not df_data.empty:
                    df_data['transporter_code'] = df_data['transporter_code'].astype(str).str.lstrip("0")


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
           if not df1.empty:
               df1['transporter_code'] = df1['transporter_code'].astype(str).str.lstrip("0")

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
                        f"COUNT(CASE WHEN {v_type} != 0 THEN 1 ELSE 0 END) AS {v_type}"
                    )
                select_clause = ",\n        ".join(select_parts)
                view_query = f"""
                SELECT 
                    tl_number,
                    invoice_number,
                    DATE(vts_end_datetime) as violation_date,
                    {select_clause}
                FROM vts_alert_history
                WHERE tl_number = '{truck_number}'
                GROUP BY tl_number, invoice_number, DATE(vts_end_datetime)
                ORDER BY violation_date DESC, invoice_number
                """
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, view_query)
                view_query = VTSAnalyticsActions.apply_conditions_to_query(view_query, conditions)

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
                if not df_alerts.empty:
                    df_alerts['transporter_code'] = df_alerts['transporter_code'].astype(str).str.lstrip("0")
                
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
                if not df_alerts.empty:
                    df_alerts['transporter_code'] = df_alerts['transporter_code'].astype(str).str.lstrip("0")
                
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

                cleaned_records = []
                for _, row in final_df.iterrows():
                    record = row.to_dict()
                    if all(record.get(v_type, 0) == 0 for v_type in all_violations):
                        continue 
                    cleaned_records.append(record)
                
                if not cleaned_records:
                    return {"status": True, "message": "No non-zero violations found", "data": []}
                
                return {"status": True, "message": "success", "data": cleaned_records}
                
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
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
            if not df_alerts.empty:
                df_alerts['transporter_code'] = df_alerts['transporter_code'].astype(str).str.lstrip("0")

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

            group_by_col = payload.get("group_by")
            if group_by_col and group_by_col in final_df.columns:
                violation_cols = [v for v in all_violations if v in final_df.columns]
                agg_df = final_df.groupby(group_by_col)[violation_cols].sum().reset_index()
                agg_df['total_count'] = agg_df[violation_cols].sum(axis=1)
                cleaned_records = agg_df.to_dict(orient='records')
                return {"status": True, "message": "success", "data": cleaned_records}
            
            qlick_view = payload.get("qlick_view")
            click_value = payload.get("click_value")
            location_name = payload.get("location_name")
            violation_cols = [v for v in all_violations if v in final_df.columns]

            if qlick_view == "zone" and not click_value:
                agg_df = final_df.groupby("zone")[violation_cols].sum().reset_index()
                agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                return {"status": True, "message": "Zone-wise violations", "data": agg_df.to_dict(orient="records")}
            
            if qlick_view == "zone" and click_value:
                zone_df = final_df[final_df[qlick_view] == click_value]
                if zone_df.empty:
                    return {"status": True, "message": f"No Data found for zone {click_value}", "data": []}
                
                agg_df = zone_df.groupby("location_name")[violation_cols].sum().reset_index()
                agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                cleaned_records = agg_df.to_dict(orient="records")
                return {"status": True, "message": f"Violations for all plants in zone {click_value}", "data": cleaned_records}
                    
            elif qlick_view == "location_name" and click_value:
                location_df = final_df[final_df[qlick_view] == click_value]
                if location_df.empty:
                    return {"status": True, "message": f"No Data found for location {click_value}", "data": []}
            
                agg_df = location_df.groupby("transporter_name")[violation_cols].sum().reset_index()
                agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                cleaned_records = agg_df.to_dict(orient="records")
                return {"status": True, "message": f"violations for all transporter in location {click_value}", "data": cleaned_records}

            elif qlick_view == "transporter_name" and click_value and location_name:
                df = final_df[final_df[qlick_view] == click_value]
                df = df[df["location_name"] == location_name]
                if df.empty:
                    return {"status": True, "message": f"No Data found for transporters {click_value}", "data": []}
                
                agg_df = df.groupby("tl_number")[violation_cols].sum().reset_index()
                agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                agg_df = agg_df[agg_df["total_count"] > 0]
                cleaned_records = agg_df.to_dict(orient="records")
                return {"status": True, "message": f"Date-wise violations for transporter {click_value}", "data": cleaned_records}
            
            elif qlick_view == "tl_number" and click_value:
                df = final_df[final_df[qlick_view] == click_value]
                if df.empty:
                    return {"status": True, "message": f"No Data found for vehicle {click_value}", "data": []}
                
                agg_df = df.groupby(["invoice_number", "created_at"])[violation_cols].sum().reset_index()
                agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                agg_df = agg_df[agg_df["total_count"] > 0]
                cleaned_records = agg_df.to_dict(orient="records")
                return {"status": True, "message": f"Date-wise violations for vehicle {click_value}", "data": cleaned_records}
                
            
            # Default case: return all records with non-zero violations
            cleaned_records = []
            for _, row in final_df.iterrows():
                record = row.to_dict()
                if all(record.get(v_type, 0) == 0 for v_type in all_violations):
                    continue 
                cleaned_records.append(record)
            
            if not cleaned_records:
                return {"status": True, "message": "No non-zero violations found", "data": []}
                
            return {"status": True, "message": "success", "data": cleaned_records}
            
        except Exception as e:
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
    
    @staticmethod
    async def violation_percentages(filters, cross_filters, drill_state, payload):
        try:
            # Step 1: Get base query and apply filters
            query = vts_query.vts_query.get(drill_state.split(",")[0])
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
            print(query)
            
            df = await VTSAnalyticsActions.execute_query(query)
            if df.empty:
                return {"status": True, "message": "No data found", "data": []}

            # Step 2: Select violation columns
            violation_cols = [
                "route_deviation_count",
                "stoppage_violations_count",
                "device_tamper_count",
                "speed_violation_count",
                "night_driving_count"
            ]

            df_viol = df[["invoice_number"] + violation_cols].copy()
            df_viol.dropna(subset=["invoice_number"], inplace=True)

            # Step 3: Mark each count >0 as 1
            for col in violation_cols:
                df_viol[col] = df_viol[col].apply(lambda x: 1 if x and x != 0 else 0)

            # Step 4: Assign each invoice to its first violation type
            def first_violation(row):
                for col in violation_cols:
                    if row[col] == 1:
                        return col
                return None
            
            df_viol["primary_violation"] = df_viol.apply(first_violation, axis=1)
            df_viol = df_viol[df_viol["primary_violation"].notna()]

            # Step 5: Count invoices per primary violation
            counts = df_viol["primary_violation"].value_counts()
            total = counts.sum()

            # Step 6: Calculate percentages
            violation_percentages = {
                col: round(100 * counts.get(col, 0) / total, 2) for col in violation_cols
            }

            return {
                "status": True,
                "message": "Violation percentages calculated",
                "data": violation_percentages
            }

        except Exception as e:
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
    

    @staticmethod
    async def vts_drill_down_violation(filters, cross_filters, drill_state, payload):
        try:
            # Step 1: Get base query and apply filters
            query = vts_query.vts_query.get(drill_state.split(",")[0])
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            vts_drill_query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
            print(vts_drill_query)

            vts_df = await VTSAnalyticsActions.execute_query(vts_drill_query)
            vts_df = vts_df.drop_duplicates(subset=['invoice_number'], keep='first')

            if vts_df.empty:
                return {"status": True, "message": "No data found", "data": []}

            # Step 2: Get TLs and fetch alerts
            tl_numbers_list = vts_df['tl_number'].tolist()
            tl_numbers_str = "', '".join(map(str, tl_numbers_list))

            alerts_query = f"""
                SELECT DISTINCT location_name, vehicle_number, transporter_code, zone
                FROM alerts
                WHERE vehicle_number IN ('{tl_numbers_str}')
                AND transporter_code != '' AND location_name != ''
            """
            df_alerts = await VTSAnalyticsActions.execute_query(alerts_query)
            if df_alerts.empty:
                return {"status": False, "message": "No matching vehicle details found in alerts", "data": []}

            merged_df = vts_df.merge(df_alerts, left_on="tl_number", right_on="vehicle_number", how="left")

            # Step 3: Remove missing or empty zones
            merged_df = merged_df[merged_df["zone"].notna() & (merged_df["zone"].str.strip() != "")]
            if merged_df.empty:
                return {"status": False, "message": "No valid zone data found after merging with alerts", "data": []}

            # Step 4: Merge transporter names
            email_query = """SELECT transporter_code, transporter_name FROM email_master"""
            df_email = await VTSAnalyticsActions.execute_query(email_query)
            final_df = merged_df.merge(df_email, on="transporter_code", how="left")
            final_df.drop(columns=["transporter_code"], inplace=True)

            # Step 5: Filter violation type
            violation_type = payload.get("violation_type")
            if not violation_type or violation_type not in final_df.columns:
                return {"status": False, "message": f"Invalid violation type: {violation_type}", "data": []}

            violation_filtered_df = final_df[final_df[violation_type].fillna(0) != 0].copy()

            # Step 6: Remove empty values for zone, location, transporter
            for key in ["zone", "location_name", "transporter_name"]:
                violation_filtered_df = violation_filtered_df[
                    violation_filtered_df[key].notna() & (violation_filtered_df[key].str.strip() != "")
                ]
                if payload.get(key):
                    violation_filtered_df = violation_filtered_df[violation_filtered_df[key] == payload[key]]

            if violation_filtered_df.empty:
                return {"status": True, "message": "No data found for the applied filters", "data": []}

            # Step 7: TL-level drill-down for invoice details
            selected_tl = payload.get("tl_number")
            if selected_tl:
                violation_filtered_df = violation_filtered_df[violation_filtered_df["tl_number"] == selected_tl]

                if violation_filtered_df.empty:
                    return {
                        "status": True,
                        "message": f"No invoices found for vehicle {selected_tl}",
                        "data": []
                    }

                # Return invoice details sorted by created_at
                invoice_df = violation_filtered_df.sort_values(by="created_at", ascending=True)
                invoice_df = invoice_df[["invoice_number", "created_at", violation_type]]

                # Rename columns for frontend
                invoice_df.rename(columns={
                    "invoice_number": "invoice_no",
                    "created_at": "created_at",
                    violation_type: f"actual_{violation_type}"  
                }, inplace=True)

                result = invoice_df.to_dict(orient="records")
                return {
                    "status": True,
                    "message": f"{violation_type} details for vehicle {selected_tl}",
                    "data": result
                }

            # Step 8: Determine grouping column for summaries
            if payload.get("transporter_name"):
                group_col = "tl_number"
            elif payload.get("location_name"):
                group_col = "transporter_name"
            elif payload.get("zone"):
                group_col = "location_name"
            else:
                group_col = "zone"

            # Step 9: Summarize counts
            summary_df = (
                violation_filtered_df.groupby(group_col)
                .agg({"invoice_number": pd.Series.nunique})
                .reset_index()
            )

            summary_df[violation_type] = violation_filtered_df.groupby(group_col).size().values
            if group_col != "tl_number":
                 summary_df["vehicle_count"] = violation_filtered_df.groupby(group_col)["tl_number"].nunique().values
                


            rename_mapping = {
                "invoice_number": "invoice_count",
            }
            summary_df.rename(columns=rename_mapping, inplace=True)

            # Also rename the dynamic violation column for clarity
            summary_df.rename(columns={violation_type: violation_type}, inplace=True)

            result = summary_df.to_dict(orient="records")
            return {
                "status": True,
                "message": f"{violation_type} drill-down data",
                "data": result
            }

        except Exception as e:
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
    
    @staticmethod
    async def vts_ongoing_trips(filters, cross_filters, drill_state, payload):
        try:
            # Step 1: Get base query and apply filters
            query = vts_query.vts_query.get(drill_state.split(",")[0])
            ongoing_trips_type = payload.get("ongoing_trips_type")
            
            if ongoing_trips_type:
                ongoing_trips_query = query.format(ongoing_trips_type=ongoing_trips_type)
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, ongoing_trips_query)
                query = VTSAnalyticsActions.apply_conditions_to_query(ongoing_trips_query, conditions)     
                print(query)
            else:
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
                query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)

            df = await VTSAnalyticsActions.execute_query(query)
            df.drop(columns=["zone"], inplace=True, errors="ignore")

            
            df = df.drop_duplicates(
                        subset=["event_start_datetime", "event_end_datetime", "tt_number", "invoice_no"],
                        keep="first"  
                    )
            
            if df.empty:
                return {"status": True, "message": "No data found", "data": []}
            
            # Step 2: Get TT numbers and fetch alerts
            sap_id_list = df['sap_id'].tolist()
            tt_numbers_str = "', '".join(map(str, sap_id_list))
            
            location_query = f"""
                 select sap_id,name as location_name, zone from location_master where sap_id IN ('{tt_numbers_str}')       
            """
            
            loc_df = await VTSAnalyticsActions.execute_query(location_query)
            if loc_df.empty:
                return {"status": False, "message": "No matching vehicle details found in alerts", "data": []}
            
            # Step 3: Merge dataframes
            merged_df = df.merge(loc_df, on="sap_id",  how="left")
            merged_df = merged_df.dropna(subset=["zone", "location_name"])
       
            # Step 4: Remove empty values for zone, location, transporter
            for key in ["zone", "location_name", "transporter_name"]:
                merged_df = merged_df[merged_df[key].notna() & (merged_df[key].str.strip() != "")]
                if payload.get(key):
                    merged_df = merged_df[merged_df[key] == payload[key]]

            if merged_df.empty:
                return {"status": True, "message": "No data found for the applied filters", "data": []}

            # Step 5: TT-level drill-down for trip details
            selected_tt = payload.get("tt_number")
            if selected_tt:
                merged_df = merged_df[merged_df["tt_number"] == selected_tt]

                if merged_df.empty:
                    return {
                        "status": True,
                        "message": f"No trips found for vehicle {selected_tt}",
                        "data": []
                    }
                
                merged_df["created_at"] = (
                                pd.to_datetime(merged_df["event_start_datetime"].fillna(merged_df["event_end_datetime"]))
                                .dt.date.astype(str)
                            )

                trip_df = merged_df.sort_values(by="created_at", ascending=True)
                trip_df = trip_df[["invoice_no", "created_at"]]

                result = trip_df.to_dict(orient="records")
                return {
                    "status": True,
                    "message": f"Trip details for vehicle {selected_tt}",
                    "data": result
                }

            # Step 6: Determine grouping column for summaries
            if payload.get("transporter_name"):
                group_col = "tt_number"
            elif payload.get("location_name"):
                group_col = "transporter_name"
            elif payload.get("zone"):
                group_col = "location_name"
            else:
                group_col = "zone"

            # Step 7: Summarize counts
            summary_df = (
                merged_df.groupby(group_col)
                .agg({"invoice_no": pd.Series.nunique})
                .reset_index()
            )

            if group_col != "tt_number":
                summary_df["vehicle_count"] = merged_df.groupby(group_col)["tt_number"].nunique().values

            
            rename_mapping = {
                "invoice_no": "invoice_count",
            }
            summary_df.rename(columns=rename_mapping, inplace=True)

            result = summary_df.to_dict(orient="records")
            return {
                "status": True,
                "message": f"Ongoing trips drill-down data",
                "data": result
            }

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
            
            if not base_query:
                return {"status": False, "message": "Query not found", "data": [], "percentages": []}

            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, base_query)
            conditions = VTSAnalyticsActions.add_alert_type_conditions(conditions, alert_type)
            
            alerts_query = VTSAnalyticsActions.apply_conditions_to_query(base_query, conditions)

            print(alerts_query)

            # Execute queries
            alerts_df = await VTSAnalyticsActions.execute_query(alerts_query)
            
            if alerts_df.empty:
                return {"status": True, "message": "success", "data": [], "percentages": []}

            # Get group by column
            group_by_column = VTSAnalyticsActions.get_group_by_column(drill_state)
            if not group_by_column or group_by_column not in alerts_df.columns:
                return {"status": False, "message": f"Column '{group_by_column}' not found", "data": [], "percentages": []}
            
            if 'violation_type' not in alerts_df.columns:
                return {"status": False, "message": "violation_type column not found", "data": [], "percentages": []}
            
            alerts_df = alerts_df[
                  alerts_df[group_by_column].notnull() & 
                 (alerts_df[group_by_column] != "")
                ]
            
            if alerts_df.empty:
                 return {"status": True, "message": "success", "data": [], "percentages": []}
            
            grouped = alerts_df.groupby([group_by_column, 'violation_type']).size().reset_index(name='count')
            
            if grouped.empty:
                 return {"status": True, "message": "success", "data": [], "percentages": []}
        
            # Prepare response data
            data_response = []
            for group_value in grouped[group_by_column].unique():
                group_data = grouped[grouped[group_by_column] == group_value]
                violations_list = [
                    {"violation_type": row['violation_type'], "count": int(row['count'])}
                    for _, row in group_data.iterrows()
                ]
                
                if violations_list:
                    data_response.append({group_value: violations_list})

            # Calculate percentages
            violation_totals = grouped.groupby('violation_type')['count'].sum().to_dict()
            grand_total = sum(violation_totals.values())
            percentages = []
            if grand_total > 0:
                percentages = [
                    {"violation_type": vtype, "percentage": round((count / grand_total) * 100, 2)}
                    for vtype, count in violation_totals.items()
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

            if not base_query:
                return {"status": False, "message": "Query not found", "data": []}

            # Build conditions with alert type (pass base_query for key transformation)
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, base_query)
            conditions = VTSAnalyticsActions.add_alert_type_conditions(conditions, alert_type)

            # Get period expression and format query
            period_expr = VTSAnalyticsActions.get_period_expression(drill_state)
            alerts_query = base_query.format(period_expr=period_expr)
            alerts_query = VTSAnalyticsActions.apply_conditions_to_query(alerts_query, conditions)

            print(alerts_query)

            # Execute queries
            alerts_df = await VTSAnalyticsActions.execute_query(alerts_query)
            
            if alerts_df.empty:
                return {"status": True, "message": "success", "data": []}

            if 'violation_type' not in alerts_df.columns or 'period' not in alerts_df.columns:
                 return {"status": False, "message": "Required columns not found", "data": []}
            
            alerts_df = alerts_df[
                (alerts_df["period"].notna()) &                      
                (alerts_df["period"].astype(str).str.strip() != "")
            ]

            if alerts_df.empty:
                return {"status": True, "message": "success", "data": []}
            
            grouped = alerts_df.groupby(['period', 'violation_type']).size().reset_index(name='count')
            
            if grouped.empty:
                return {"status": True, "message": "success", "data": []}
            
            result = []
            for period in grouped['period'].unique():
                period_data = grouped[grouped['period'] == period]
                formatted_date = VTSAnalyticsActions.format_date(period, drill_state)
                
                values = [
                    {"violation_type": row['violation_type'], "count": int(row['count'])}
                    for _, row in period_data.iterrows()
                ]
                
                if values:
                    result.append({"date": formatted_date, "records": values})
            
            # Sort by period (assuming period is sortable)
            result.sort(key=lambda x: x['date'])
            
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
        import pandas as pd
        import pytz
        from datetime import datetime, timedelta

        # --- HELPER FUNCTION: Build SQL Conditions (Only for columns in sales_trips_till_date) ---
        def build_sql_conditions_string(filter_list, table_alias='T'):
            conditions = []
            # Keys allowed for SQL pushdown in sales_trips_till_date
            allowed_keys = ['zone_nm', 'plant_nm', 'vehicle_id'] 
            
            for f in filter_list:
                key = getattr(f, "key", None)
                val = getattr(f, "value", None)
                cond = getattr(f, "cond", None)
                
                if key and val and key.lower() in allowed_keys:
                    df_col = key.lower()
                    if cond == "equals":
                        conditions.append(f"{table_alias}.{df_col} = '{val}'")
                    elif cond == "in":
                        if isinstance(val, list):
                            val_str = ', '.join(f"'{v}'" for v in val)
                            conditions.append(f"{table_alias}.{df_col} IN ({val_str})")
                        else:
                            conditions.append(f"{table_alias}.{df_col} = '{val}'")
            
            return " AND " + " AND ".join(conditions) if conditions else ""


        # ----- 1. Filter Separation and Date Condition Preparation -----
        
        # Separate filters: 'bu' for alerts, others for trips
        alerts_filters = [f for f in filters if getattr(f, "key", None) in ("bu",)]
        trips_filters = [f for f in filters if getattr(f, "key", None) not in ("bu",)]
        
        # Extract Transporter Filter for later Pandas application (must be done post-merge)
        transporter_filter = next((f for f in trips_filters if getattr(f, 'key') == 'transporter_name'), None)
        
        # SQL conditions for trips (zone_nm, plant_nm, vehicle_id)
        sql_trips_conditions = build_sql_conditions_string(trips_filters, table_alias='T')
        
        # Date condition from cross_filters
        date_condition_str = ""
        today = datetime.now().date()
        date_selection = next((getattr(f, "value", None) for f in cross_filters if getattr(f, "key", None) == "date"), None)

        if date_selection:
            if "," in date_selection:
                start_date, end_date = date_selection.split(",")
                date_condition_str = f"AND T.created_on::date BETWEEN '{start_date}' AND '{end_date}'"
            else:
                date_selection = date_selection.lower()
                if date_selection == "today":
                    date_condition_str = f"AND T.created_on::date = '{today}'"
                elif date_selection == "yesterday":
                    date_condition_str = f"AND T.created_on::date = '{today - timedelta(days=1)}'"

        # ----- 2. Fetch Alerts (Original Logic Restored) -----
        
        alerts_query = """
            SELECT location_name, bu, vehicle_number, transporter_code
            FROM alerts
            WHERE alert_section = 'VTS'
        """
        conditions = VTSAnalyticsActions.build_filter_conditions(alerts_filters, cross_filters, alerts_query)
        final_query = VTSAnalyticsActions.apply_conditions_to_query(alerts_query, conditions) 
        alerts_df = await VTSAnalyticsActions.execute_query(final_query)
        alerts_df.columns = [c.lower() for c in alerts_df.columns]

        if alerts_df.empty and alerts_filters:
            return {"status": "success", "total_invoice_count": 0, "total_vehicle_count": 0,
                    "filtered_invoice_count": 0, "filtered_vehicle_count": 0, "zones": []}
        
        # ----- 3. Fetch Trips (OPTIMIZED: SQL Filter Pushdown) -----
        
        trips_query = f"""
            SELECT 
                zone_nm, plant_nm, load_date, vehicle_id, qty_shortage, invoice_no, created_on 
            FROM 
                sales_trips_till_date T
            WHERE 
                qty_shortage > 0 
                {sql_trips_conditions} 
                {date_condition_str}
        """
        trips_df = await VTSAnalyticsActions.execute_query(trips_query)
        if trips_df.empty:
            return {"status": "success", "total_invoice_count": 0, "total_vehicle_count": 0,
                    "filtered_invoice_count": 0, "filtered_vehicle_count": 0, "zones": []}
            
        trips_df.columns = [c.lower() for c in trips_df.columns]
        
       

        # ----- 4. Merging (Original Logic Restored) -----

        # 4a. Merge Alerts
        if 'location_name' in alerts_df.columns and 'bu' in alerts_df.columns:
            plant_bu_mapping = alerts_df[['location_name', 'bu']].drop_duplicates()
            trips_df = trips_df.merge(plant_bu_mapping, how='left', left_on='plant_nm', right_on='location_name') \
                            .drop(columns=['location_name'], errors='ignore')

        if {'location_name', 'vehicle_number', 'transporter_code'}.issubset(alerts_df.columns):
            alerts_vehicle_mapping = alerts_df[['location_name', 'vehicle_number', 'transporter_code']].drop_duplicates()
            trips_df = trips_df.merge(alerts_vehicle_mapping, how='left',
                                    left_on=['plant_nm', 'vehicle_id'],
                                    right_on=['location_name', 'vehicle_number']) \
                            .drop(columns=['vehicle_number', 'location_name'], errors='ignore')

        # 4b. Merge email master
        email_query = "SELECT transporter_code, transporter_name FROM email_master"
        email_df = await VTSAnalyticsActions.execute_query(email_query)
        if not email_df.empty:
            email_df.columns = [c.lower() for c in email_df.columns]
            trips_df = trips_df.merge(email_df, how='left', on='transporter_code')
            
        # ----- 5. Filter valid trips (Original Logic Restored) -----
        
        trips_df['qty_shortage'] = pd.to_numeric(trips_df['qty_shortage'], errors='coerce')
        filtered_trips_df = trips_df[
            trips_df['transporter_name'].notnull() &
            trips_df['transporter_code'].notnull() &
            (trips_df['qty_shortage'] > 0)
        ].copy()

        # ----- 6. Apply Transporter Filter (Pandas, Original Logic Restored) -----
        
        # Apply the transporter_name filter here, post-merge.
        if transporter_filter:
            key = getattr(transporter_filter, "key", None)
            val = getattr(transporter_filter, "value", None)
            cond = getattr(transporter_filter, "cond", None)
            
            if key and val and key.lower() == 'transporter_name':
                df_col = key.lower()
                if cond == "equals":
                    filtered_trips_df = filtered_trips_df[filtered_trips_df[df_col] == val]
                elif cond == "in":
                    if not isinstance(val, list):
                        val = [val]
                    filtered_trips_df = filtered_trips_df[filtered_trips_df[df_col].isin(val)]

        # ----- 7. Counts after filtering (Original Logic Restored) -----
        
        filtered_invoice_count = filtered_trips_df['invoice_no'].nunique()
        filtered_vehicle_count = filtered_trips_df['vehicle_id'].nunique()
        
        if filtered_trips_df.empty:
            return {"status": "success", "total_invoice_count": 0, "total_vehicle_count": 0,
                    "filtered_invoice_count": 0, "filtered_vehicle_count": 0, "zones": []}
                    
        # Drop exact duplicates
        filtered_trips_df = filtered_trips_df.drop_duplicates()

        # ----- 8. Convert load_date to IST (CRITICAL FIX: Original Logic Restored) -----
        
        # This logic correctly checks if the column is already timezone-aware before localizing.
        ist = pytz.timezone("Asia/Kolkata")
        if 'load_date' in filtered_trips_df.columns:
            filtered_trips_df['load_date'] = pd.to_datetime(filtered_trips_df['load_date'])
            
            if filtered_trips_df['load_date'].dt.tz is None:
                # Localize to UTC if naive (no timezone), then convert
                filtered_trips_df['load_date'] = filtered_trips_df['load_date'].dt.tz_localize('UTC').dt.tz_convert(ist)
            else:
                # If already tz-aware, convert directly (avoids the "Already tz-aware" error)
                filtered_trips_df['load_date'] = filtered_trips_df['load_date'].dt.tz_convert(ist)
                
            # Format the result
            filtered_trips_df['load_date'] = filtered_trips_df['load_date'].dt.strftime("%Y-%m-%d %H:%M:%S%z")

        # ----- 9. Dynamic hierarchical grouping (Original Logic Restored) -----
        
        # Re-using your original recursive function structure for consistency
        def compute_group_summary(df, group_cols):
            if not group_cols:
                return None

            result = []
            current_col = group_cols[0]
            next_cols = group_cols[1:]

            for keys, group in df.groupby(current_col, dropna=False):
                item = {current_col: keys}
                item["shortage"] = group["qty_shortage"].sum()
                item["invoice_count"] = group["invoice_no"].nunique()
                item["vehicle_count"] = group["vehicle_id"].nunique()

                # recursive drilldown
                child = compute_group_summary(group, next_cols)
                if child:
                    if next_cols[0] == "plant_nm":
                        item["plants"] = child
                    elif next_cols[0] == "transporter_name":
                        item["transporters"] = child
                    elif next_cols[0] == "vehicle_id":
                        item["vehicles"] = child
                    elif next_cols[0] == "invoice_no":
                        item["invoices"] = child
                else:
                    # Last level reached → current_col is invoice_no
                    if current_col == "invoice_no" and "load_date" in group.columns:
                        # If multiple rows per invoice, take the first or min load_date
                        item["load_date"] = group["load_date"].iloc[0]

                result.append(item)

            return result

        # Determine grouping columns based on applied filters
        filter_keys = [getattr(f, "key", None) for f in filters] if filters else []
        if "vehicle_id" in filter_keys:
            group_cols = ["vehicle_id", "invoice_no"]
        elif "transporter_name" in filter_keys:
            group_cols = ["transporter_name", "vehicle_id"]
        elif "plant_nm" in filter_keys:
            group_cols = ["plant_nm", "transporter_name"]
        elif "zone_nm" in filter_keys:
            group_cols = ["zone_nm", "plant_nm"]
        else:
            group_cols = ["zone_nm"]

        zones_list = compute_group_summary(filtered_trips_df, group_cols)

        return {
            "status": "success",
            "filtered_invoice_count": filtered_invoice_count,
            "filtered_vehicle_count": filtered_vehicle_count,
            "zones": zones_list
        }