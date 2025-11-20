import urdhva_base
import asyncio
import traceback
import pandas as pd
import numpy as np
import hpcl_ceg_model
import mysql.connector
import dashboard_studio_model
from datetime import datetime
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from orchestrator.dbconnector.widget_actions import widget_actions
import orchestrator.dbconnector.widget_actions.vts_query as vts_query
import orchestrator.dbconnector.credential_loader as credential_loader
import io
import os
import polars as pl
import json
from fastapi.responses import StreamingResponse
from fastapi import Request
from fastapi.responses import JSONResponse, FileResponse
from openpyxl import load_workbook, Workbook  
from openpyxl.utils import get_column_letter


async def generate_cross_filter(cross_filters):
    _filters, daterange = [], None
    try:
        if cross_filters:
            for f in cross_filters:
                if "DATE" in f.key:
                    start = f.value.split(",")[0]
                    end = f.value.split(",")[-1]
                    daterange = f"'{start} 00:00:00' AND '{end} 23:59:59'"
                else:
                    _filters.append({f.key: f.value})
        return _filters, daterange
    except Exception as e:
        print("--- Exception in cross filters ---")
        print("Exception :", str(e))
        return _filters, daterange


async def get_drill_down_filter(filters, query):
    try:
        conditions = []
        _key = None
        if filters:
            for rec in filters:
                if (rec.key).lower().replace('"', '') in ["rejection_type"]:
                    _key = (rec.value).lower().replace('"', '')
                    continue
                values = rec.value.split(",")
                if len(values) == 1:
                    conditions.append(f'{rec.key} = \'{values[0]}\'')
                else:
                    conditions.append(f"{rec.key} IN {tuple(values)}")
        if conditions:
            if "where" in query.lower():
                query += " AND " + " AND ".join(conditions)
            else:
                query += " WHERE " + " AND ".join(conditions)
        if _key:
            return query, _key
        return query
    except Exception as e:
        print("--- Exception in drill down filters ---")
        print("Exception :", str(e))
        return query

async def filter_data(df, _filters):
    try:        
        if _filters:
            print("-"*30)
            print("_filters :", _filters)
            print("data columns :", df.columns)
            print("length of data :", len(df))
            mask = pd.Series(True, index=df.index)
            for _filter in _filters:
                for key, value in _filter.items():
                    key = key.replace('"','')
                    mask = mask & (df[key].fillna('') == value)
            df = df[mask]
            print("length of filtered data :", len(df))
            print("-"*30)
        return df
    except Exception as e:
        print("Exception in filtering data :", str(e))
    return df

async def safe_json(df):
    return df.replace([np.inf, -np.inf, np.nan], None).to_dict(orient="records")

class VTSAnalyticsActions:
    
    @staticmethod
    def transform_key(key, query=None):
        """Transform keys based on query context"""
        # if query and any(x in query.lower() for x in ["vts_alert_history", "vts_ongoing_trips"]) and key.lower() == "bu":
        #     return "location_type"
        # if query and "vts_alert_history" in query.lower() and key.lower() == "sap_id":
        #     return "location_id" 
        if query and 'sales_trips_till_date' in query.lower() and key.lower() == 'bu':
            return None
         
        if query and 'sales_trips_till_date' in query.lower() and key.lower() == 'zone':
            return 'zone_nm'
        
        return key
    
    @staticmethod
    def build_filter_conditions(filters, cross_filters, query):
        """Build WHERE conditions from filters and cross_filters"""
        all_conditions = []
        
        if 'sales_trips_till_date' in query.lower():
            bu_filter = None
            if filters:
                for f in filters:
                    if hasattr(f, 'key') and f.key.lower() == 'bu':
                        bu_filter = f
                        break
            
            bu_value = bu_filter.value if bu_filter else None

            if bu_value:
                bu = bu_value.upper()
                if bu == 'TAS':
                    all_conditions.append("division = '11'")
                    all_conditions.append("sales_org = '7000'")
                    all_conditions.append("(qty_shortage > '0')")
                elif bu == 'LPG':
                    all_conditions.append("division in ('20', '21')")
                    all_conditions.append("sales_org = '2000'")
                    all_conditions.append("(qty_shortage > '0')")
                elif bu == 'I&C':
                    all_conditions.append("distribution_channel = '12'")
                    all_conditions.append("sales_org = '3000'")
                    all_conditions.append("route <> 'EXW001'")
            
            else:
                all_conditions.append("division = '11'")
                all_conditions.append("sales_org = '7000'")
        
        elif 'sales_trips_till_date' not in query.lower():
            bu_filter = None
            if filters:
                for f in filters:
                    if hasattr(f, 'key') and f.key.lower() == 'bu':
                        bu_filter = f
                        break
            
            if bu_filter and bu_filter.value.upper() == 'I&C':
                all_conditions.append("bu = 'TAS'")
               
        # Process regular filters
        if filters:
            for rec in filters:
                key = VTSAnalyticsActions.transform_key(rec.key, query)
                if key is None:
                    continue

                if (key.lower() == 'bu' and 'sales_trips_till_date' not in query.lower() and
                     rec.value.upper() == 'I&C'):
                   continue

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
        end_date = val.split(",")[-1]
        end = f"{end_date} 23:59:59"
       
        if "vts_alert_history" in query.lower():
            return f"vts_end_datetime BETWEEN '{start}' AND '{end}'"
        
        if "vts_tripauditmaster" in query.lower():
            return f"createdat BETWEEN '{start}' AND '{end}'"
        
        onging_trips = ["violation_type = 'wr'", "violation_type = 'tc'", "violation_type = 'hs'"]
        if any(ot in query.lower() for ot in onging_trips):
            return f"event_start_datetime BETWEEN '{start}' AND '{end}'"
        
        if "violation_type = 'rd'" in query.lower():
            return f"event_end_datetime BETWEEN '{start}' AND '{end}'"
        
        if "sales_trips_till_date" in query.lower():
            return f"invoice_date::DATE BETWEEN '{start}' AND '{end}'"
        
        if "completed_trips_risk_score" in query.lower():
            return f"scheduled_trip_start_datetime BETWEEN '{start}' AND '{end}'"
                
        queries = ["vts_device_removed", "vts_harsh_acceleration", "vts_harsh_braking", "vts_panic"]
        if any(q in query.lower() for q in queries):
            return f"event_date BETWEEN '{start}' AND '{end}'"
        
        
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
            conditions.append("vehicle_unblocked_date is null")
        elif alert_type.lower() == "auto_unblock":
            conditions.append("alert_status = 'Close' AND mark_as_false = false AND vehicle_unblocked_date is not null")
        elif alert_type.lower() == "manual_unblock":
            conditions.append("alert_status = 'Close' AND mark_as_false = true and vehicle_unblocked_date is not null")
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
            truck_number = payload.get("view", "")

            if truck_number:
                select_parts = []
                for v_type in all_violations:
                    select_parts.append(
                        f"SUM(CASE WHEN violation_type = '{v_type}' THEN 1 ELSE 0 END) AS {v_type}"
                    )
                select_clause = ",\n                    ".join(select_parts)

                view_query = f"""
                    SELECT 
                        sap_id,
                        location_name,
                        vehicle_number,
                        zone,
                        created_at,
                        {select_clause}
                    FROM alerts
                    WHERE vehicle_number = '{truck_number}'
                    AND alert_section = 'VTS'
                    GROUP BY sap_id, location_name, vehicle_number, zone, created_at
                """
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, view_query)
                conditions = VTSAnalyticsActions.add_alert_type_conditions(conditions, alert_type)
                view_query = VTSAnalyticsActions.apply_conditions_to_query(view_query, conditions)
                print(view_query)

                df_view = await VTSAnalyticsActions.execute_query(view_query)

                if df_view.empty:
                    return {"status": True, "message": "No data found for this truck", "data": []}

               
                truck_master_query = """SELECT distinct truck_no, transporter_name FROM vts_truck_master"""
                df_truck_master = await VTSAnalyticsActions.execute_query(truck_master_query)

                # Merge alerts.vehicle_number ↔ vts_truck_master.truck_number
                merged_df = df_view.merge(df_truck_master, left_on="vehicle_number", right_on="truck_no", how="left")
                merged_df.drop(columns=["truck_no"], inplace=True)

                return {"status": True, "message": "success", "data": await safe_json(merged_df)}

            
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
                                
                truck_master_query = """SELECT truck_no, transporter_name FROM vts_truck_master"""
                df_truck_master = await VTSAnalyticsActions.execute_query(truck_master_query)

                merged_df = df_data.merge(df_truck_master, left_on="vehicle_number", right_on="truck_no", how="left")
                merged_df.drop(columns=["truck_no"], inplace=True)

                return {"status": True, "message": "success", "data":await safe_json(merged_df)}

            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            conditions = VTSAnalyticsActions.add_alert_type_conditions(conditions, alert_type)
            vts_insite_query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
            print(vts_insite_query)
            df1 = await VTSAnalyticsActions.execute_query(vts_insite_query)

            truck_master_query = """SELECT truck_no, transporter_name FROM vts_truck_master"""
            df_truck_master = await VTSAnalyticsActions.execute_query(truck_master_query)

            merged_df = df1.merge(df_truck_master, left_on="vehicle_number", right_on="truck_no", how="left")
            merged_df.drop(columns=["truck_no"], inplace=True)

            if payload.get("download") == "true":
                for col in merged_df.select_dtypes(include=["datetime64[ns, UTC]", "datetimetz"]).columns:
                    merged_df[col] = merged_df[col].dt.tz_localize(None)

                merged_df = merged_df.dropna(axis=1, how="all")
                merged_df = merged_df.loc[:, (merged_df.astype(str).apply(lambda x: x.str.strip() != "").any())]

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"itdg_{timestamp}.xlsx"

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    merged_df.to_excel(writer, index=False, sheet_name='itdg_alerts')

                output.seek(0)
                headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
                return StreamingResponse(
                    output,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers
                )

            return {"status": True, "message": "success", "data": await safe_json(merged_df)}

        except Exception as e:
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}

      
    @staticmethod
    async def vts_insite_violation(filters, cross_filters, drill_state, payload):
        """
        Main function to handle VTS violation queries with BU-specific merge logic:
        - I&C: Default=Shortage LEFT Violations, Filtered=Shortage INNER Violations
        - TAS/LPG: Default=Violations OUTER Shortage, Filtered=Violations LEFT Shortage
        - Others: Violations LEFT Shortage (always)
        """
        try:
            # Identify Business Unit
            bu_ic = any(getattr(f, 'key') == 'bu' and getattr(f, 'value') == 'I&C' for f in filters)
            bu_lpg = any(getattr(f, 'key') == 'bu' and getattr(f, 'value') == 'LPG' for f in filters)
            bu_tas = any(getattr(f, 'key') == 'bu' and getattr(f, 'value') == 'TAS' for f in filters)
            
            query = vts_query.vts_query.get(drill_state.split(",")[0])
            all_violations = vts_query.vts_query.get("all_violations", [])
            violation_types = payload.get("violation_type", []) if payload else []
            truck_number = payload.get("view", "")

            def extract_invoice_number(invoice_str):
                """Extract base invoice number: 9017293614-ZF23-1992 -> 9017293614"""
                if pd.isna(invoice_str) or invoice_str is None:
                    return None
                invoice_str = str(invoice_str).strip()
                if '-' in invoice_str:
                    return invoice_str.split('-')[0]
                return invoice_str

            async def get_shortage_data():
                """Fetch ALL shortage data from sales_trips_till_date"""
                shortage_query = """
                    SELECT 
                        vehicle_id, 
                        invoice_no,
                        plant_nm,
                        zone_nm,
                        invoice_date,
                        CASE 
                            WHEN qty_shortage = 'NaN' THEN '0.0'
                            WHEN qty_shortage IS NULL THEN '0.0'
                            ELSE qty_shortage 
                        END as qty_shortage,
                        material_group_nm
                    FROM sales_trips_till_date
                    WHERE load_status = '6'
                """
                
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, shortage_query)
                shortage_query = VTSAnalyticsActions.apply_conditions_to_query(shortage_query, conditions)
                df_shortage = await VTSAnalyticsActions.execute_query(shortage_query)
                
                if df_shortage.empty:
                    return pd.DataFrame()
                
                # Convert qty_shortage to numeric
                df_shortage['qty_shortage'] = pd.to_numeric(df_shortage['qty_shortage'], errors='coerce').fillna(0.0)
                
                # Filter out zero shortages for non-I&C BUs when not in default mode
                if not bu_ic and violation_types:
                    df_shortage = df_shortage[df_shortage['qty_shortage'] != 0]
                    if df_shortage.empty:
                        return pd.DataFrame()
                
                # Create standardized column names for merging
                df_shortage['invoice_match_key'] = df_shortage['invoice_no'].astype(str).str.strip()
                df_shortage['tl_number'] = df_shortage['vehicle_id']
                df_shortage['invoice_number'] = df_shortage['invoice_no']
                
                return df_shortage

            async def get_truck_master():
                """Get truck master data for all trucks"""
                truck_query = """
                    SELECT DISTINCT 
                        truck_no, 
                        transporter_name,
                        location_name,
                        zone
                    FROM vts_truck_master
                """
                return await VTSAnalyticsActions.execute_query(truck_query)

            def determine_merge_strategy():
                """
                Determine merge strategy based on BU and violation_types:
                Returns: (merge_how, base_is_shortage)
                """
                has_violation_filter = bool(violation_types)
                
                if bu_ic:
                    if has_violation_filter:
                        return ('inner', True)  # Shortage INNER Violations
                    else:
                        return ('left', True)   # Shortage LEFT Violations
                elif bu_tas or bu_lpg:
                    if has_violation_filter:
                        return ('left', False)  # Violations LEFT Shortage
                    else:
                        return ('outer', False) # Violations OUTER Shortage
                else:
                    # Default BU behavior
                    return ('left', False)      # Violations LEFT Shortage

            def merge_shortage_with_violations(df_violations, df_shortage, df_truck_master, aggregate=True):
                """
                Merge shortage and violations based on BU-specific logic
                """
                merge_how, base_is_shortage = determine_merge_strategy()
                
                if df_shortage.empty and df_violations.empty:
                    return pd.DataFrame()
                
                if df_shortage.empty:
                    if base_is_shortage:
                        # If shortage is base and empty, return empty
                        return pd.DataFrame()
                    else:
                        # If violations are base, add empty shortage column
                        if aggregate:
                            df_violations['qty_shortage'] = 0
                        else:
                            df_violations['qty_shortage_detail'] = ''
                        
                        # Map with truck master
                        if not df_truck_master.empty and not df_violations.empty:
                            truck_lookup = df_truck_master.set_index('truck_no')
                            
                            if 'transporter_name' not in df_violations.columns or df_violations['transporter_name'].isna().any():
                                df_violations['transporter_name'] = df_violations.get('transporter_name', pd.Series(index=df_violations.index)).fillna(
                                    df_violations['tl_number'].map(truck_lookup['transporter_name'])
                                )
                        
                        return df_violations
                
                if df_violations.empty:
                    if not base_is_shortage:
                        # Violations are base but empty
                        return pd.DataFrame()
                
                # Prepare match keys
                if not df_violations.empty and 'invoice_number' in df_violations.columns:
                    df_violations['invoice_match_key'] = df_violations['invoice_number'].apply(extract_invoice_number)
                
                df_shortage['invoice_match_key'] = df_shortage['invoice_no'].astype(str).str.strip()
                
                if aggregate:
                    # Aggregate shortage by vehicle + invoice
                    df_shortage_agg = df_shortage.groupby(
                        ['tl_number', 'invoice_match_key'], 
                        as_index=False
                    ).agg({
                        'qty_shortage': 'sum',
                        'plant_nm': 'first',
                        'zone_nm': 'first',
                        'invoice_number': 'first',
                        'invoice_date': 'first'
                    })
                    
                    # Perform merge based on strategy
                    if base_is_shortage:
                        # Shortage is base (I&C)
                        if df_violations.empty or 'invoice_number' not in df_violations.columns:
                            df_merged = df_shortage_agg.copy()
                        else:
                            df_merged = df_shortage_agg.merge(
                                df_violations,
                                left_on=['tl_number', 'invoice_match_key'],
                                right_on=['tl_number', 'invoice_match_key'],
                                how=merge_how,
                                suffixes=('_shortage', '')
                            )
                            # Use shortage invoice_number when violations invoice_number is null
                            df_merged['invoice_number'] = df_merged['invoice_number'].fillna(df_merged.get('invoice_number_shortage', ''))
                            df_merged['invoice_date'] = df_merged.get('invoice_date_shortage', df_merged.get('invoice_date', ''))
                    else:
                        # Violations are base (TAS/LPG/Others)
                        if df_violations.empty:
                            df_merged = df_shortage_agg.copy()
                        else:
                            df_merged = df_violations.merge(
                                df_shortage_agg,
                                left_on=['tl_number', 'invoice_match_key'],
                                right_on=['tl_number', 'invoice_match_key'],
                                how=merge_how,
                                suffixes=('', '_shortage')
                            )
                    
                    # Fill missing data from shortage for unmatched records
                    if 'location_name' not in df_merged.columns:
                        # Column missing → create using plant_nm or blank
                        df_merged['location_name'] = df_merged['plant_nm'] if 'plant_nm' in df_merged.columns else ''
                    else:
                        # Column exists → fill NaN with plant_nm
                        if 'plant_nm' in df_merged.columns:
                            df_merged['location_name'] = df_merged['location_name'].fillna(df_merged['plant_nm'])
                        else:
                            df_merged['location_name'] = df_merged['location_name'].fillna('')

                    if 'zone' not in df_merged.columns:
                       df_merged['zone'] = df_merged['zone_nm'] if 'zone_nm' in df_merged.columns else ''
                    else:
                        if 'zone_nm' in df_merged.columns:
                            df_merged['zone'] = df_merged['zone'].fillna(df_merged['zone_nm'])
                        else:
                            df_merged['zone'] = df_merged['zone'].fillna('')
                    
                    if 'invoice_number' not in df_merged.columns or df_merged['invoice_number'].isna().any():
                        df_merged['invoice_number'] = df_merged.get('invoice_number', '').fillna(
                            df_merged.get('invoice_match_key', '')
                        )
                    
                    # Handle created_at/violation_date with fallback to invoice_date
                    if 'created_at' not in df_merged.columns:
                        if 'violation_date' in df_merged.columns:
                            df_merged['created_at'] = df_merged['violation_date'].fillna(
                                df_merged.get('invoice_date', '')
                            )
                        else:
                            df_merged['created_at'] = df_merged.get('invoice_date', '')
                    elif df_merged['created_at'].isna().any():
                        df_merged['created_at'] = df_merged['created_at'].fillna(
                            df_merged.get('violation_date', df_merged.get('invoice_date', ''))
                        )

                    df_merged['created_at'] = pd.to_datetime(df_merged['created_at'], format='%Y%m%d', errors='coerce').dt.strftime('%Y-%m-%d')
                    df_merged['qty_shortage'] = pd.to_numeric(df_merged['qty_shortage'], errors='coerce').fillna(0)
                    
                else:
                    # Detailed shortage with material groups
                    def create_shortage_detail(group):
                        """Create formatted shortage detail string"""
                        details = []
                        for _, row in group.iterrows():
                            shortage = float(row['qty_shortage']) if pd.notna(row['qty_shortage']) else 0
                            # For I&C default include zeros, for others only non-zero
                            if bu_ic and not violation_types:
                                mat_group = str(row['material_group_nm']).strip() if pd.notna(row['material_group_nm']) else '0'
                                details.append(f"{mat_group}:{shortage}")
                            elif shortage != 0:
                                mat_group = str(row['material_group_nm']).strip() if pd.notna(row['material_group_nm']) else '0'
                                details.append(f"{mat_group}:{shortage}")
                        return ', '.join(details) if details else ''
                    
                    df_shortage_grouped = df_shortage.groupby(
                        ['tl_number', 'invoice_match_key']
                    ).apply(create_shortage_detail).reset_index(name='qty_shortage_detail')
                    
                    # Get metadata
                    df_shortage_meta = df_shortage.groupby(
                        ['tl_number', 'invoice_match_key']
                    ).agg({
                        'plant_nm': 'first',
                        'zone_nm': 'first',
                        'invoice_number': 'first',
                        'invoice_date': 'first'
                    }).reset_index()
                    
                    df_shortage_grouped = df_shortage_grouped.merge(
                        df_shortage_meta,
                        on=['tl_number', 'invoice_match_key'],
                        how='left'
                    )
                    
                    # Perform merge based on strategy
                    if base_is_shortage:
                        # Shortage is base (I&C)
                        if df_violations.empty or 'invoice_number' not in df_violations.columns:
                            df_merged = df_shortage_grouped.copy()
                        else:
                            df_merged = df_shortage_grouped.merge(
                                df_violations,
                                left_on=['tl_number', 'invoice_match_key'],
                                right_on=['tl_number', 'invoice_match_key'],
                                how=merge_how,
                                suffixes=('_shortage', '')
                            )
                            df_merged['invoice_number'] = df_merged['invoice_number'].fillna(df_merged.get('invoice_number_shortage', ''))
                            df_merged['invoice_date'] = df_merged.get('invoice_date_shortage', df_merged.get('invoice_date', ''))
                    else:
                        # Violations are base (TAS/LPG/Others)
                        if df_violations.empty:
                            df_merged = df_shortage_grouped.copy()
                        else:
                            df_merged = df_violations.merge(
                                df_shortage_grouped,
                                left_on=['tl_number', 'invoice_match_key'],
                                right_on=['tl_number', 'invoice_match_key'],
                                how=merge_how,
                                suffixes=('', '_shortage')
                            )
                    
                    # Fill missing data
                    if 'location_name' not in df_merged.columns:
                        # Column missing → create using plant_nm or blank
                        df_merged['location_name'] = df_merged['plant_nm'] if 'plant_nm' in df_merged.columns else ''
                    else:
                        # Column exists → fill NaN with plant_nm
                        if 'plant_nm' in df_merged.columns:
                            df_merged['location_name'] = df_merged['location_name'].fillna(df_merged['plant_nm'])
                        else:
                            df_merged['location_name'] = df_merged['location_name'].fillna('')
                  
                    if 'zone' not in df_merged.columns:
                       df_merged['zone'] = df_merged['zone_nm'] if 'zone_nm' in df_merged.columns else ''
                    else:
                        if 'zone_nm' in df_merged.columns:
                            df_merged['zone'] = df_merged['zone'].fillna(df_merged['zone_nm'])
                        else:
                            df_merged['zone'] = df_merged['zone'].fillna('')

                    if 'invoice_number' not in df_merged.columns or df_merged['invoice_number'].isna().any():
                        df_merged['invoice_number'] = df_merged.get('invoice_number', '').fillna(
                            df_merged.get('invoice_match_key', '')
                        )
                    
                    # Handle created_at/violation_date with fallback to invoice_date
                    if 'created_at' not in df_merged.columns:
                        if 'violation_date' in df_merged.columns:
                            df_merged['created_at'] = df_merged['violation_date'].fillna(
                                df_merged.get('invoice_date', '')
                            )
                        else:
                            df_merged['created_at'] = df_merged.get('invoice_date', '')
                    elif df_merged['created_at'].isna().any():
                        df_merged['created_at'] = df_merged['created_at'].fillna(
                            df_merged.get('violation_date', df_merged.get('invoice_date', ''))
                        )
                    

                    df_merged['created_at'] = pd.to_datetime(df_merged['created_at'], format='%Y%m%d', errors='coerce').dt.strftime('%Y-%m-%d')
                    df_merged['qty_shortage_detail'] = df_merged['qty_shortage_detail'].fillna('')
                
                # Map with truck master for missing transporter_name, location_name, zone
                if not df_truck_master.empty and not df_merged.empty:
                    # Create truck lookup
                    truck_lookup = df_truck_master.set_index('truck_no')
                    
                    # Fill transporter_name
                    if 'transporter_name' not in df_merged.columns:
                        df_merged['transporter_name'] = df_merged['tl_number'].map(truck_lookup['transporter_name'])
                    elif df_merged['transporter_name'].isna().any():
                        df_merged['transporter_name'] = df_merged['transporter_name'].fillna(
                            df_merged['tl_number'].map(truck_lookup['transporter_name'])
                        )
                    
                    # Fill location_name from truck master if still missing
                    if df_merged['location_name'].isna().any():
                        df_merged['location_name'] = df_merged['location_name'].fillna(
                            df_merged['tl_number'].map(truck_lookup['location_name'])
                        )
                    
                    # Fill zone from truck master if still missing
                    if df_merged['zone'].isna().any():
                        df_merged['zone'] = df_merged['zone'].fillna(
                            df_merged['tl_number'].map(truck_lookup['zone'])
                        )
                
                # Clean up temporary columns
                df_merged.drop(columns=['invoice_match_key', 'plant_nm', 'zone_nm', 'invoice_number_shortage', 
                                    'invoice_date', 'invoice_date_shortage'], 
                            inplace=True, errors='ignore')
                
                # Add null violation to 0
                for v in all_violations:
                    if v in df_merged.columns:
                        df_merged[v] = df_merged[v].fillna(0)
                
                return df_merged

            has_qty_shortage_filter = 'qty_shortage' in violation_types if violation_types else False
            vts_violation_types = [v for v in violation_types if v != 'qty_shortage'] if violation_types else []

            # Get truck master data (used across all flows)
            df_truck_master = await get_truck_master()

            # ==================== TRUCK NUMBER VIEW ====================
            if truck_number:
                view_query = f"""
                    SELECT 
                        tl_number,
                        invoice_number,
                        location_name,
                        zone,
                        DATE(vts_end_datetime) as violation_date,
                        stoppage_violations_count,
                        route_deviation_count,
                        device_tamper_count,
                        main_supply_removal_count,
                        night_driving_count,
                        speed_violation_count,
                        continuous_driving_count
                    FROM vts_alert_history
                    WHERE tl_number = '{truck_number}'
                    AND invoice_number IS NOT NULL
                    ORDER BY violation_date DESC, invoice_number
                """
                
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, view_query)
                view_query = VTSAnalyticsActions.apply_conditions_to_query(view_query, conditions)
                df_view = await VTSAnalyticsActions.execute_query(view_query)
                
                if not df_view.empty:
                    df_view = df_view.drop_duplicates(subset=["invoice_number"], keep="first")
                
                # Get shortage data and filter for this truck
                df_shortage = await get_shortage_data()
                if not df_shortage.empty:
                    df_shortage = df_shortage[df_shortage['tl_number'] == truck_number]
                
                # Check if we have any data
                if df_view.empty and df_shortage.empty:
                    return {"status": True, "message": "No data found for this vehicle", "data": []}
                
                # Merge
                final_df = merge_shortage_with_violations(df_view, df_shortage, df_truck_master, aggregate=False)
                
                if final_df.empty:
                    return {"status": True, "message": "No data found for this vehicle", "data": []}
                
                if 'qty_shortage_detail' not in final_df.columns:
                    final_df['qty_shortage_detail'] = ''
                
                # Ensure created_at uses violation_date as fallback if needed
                if 'violation_date' in final_df.columns:
                    final_df['created_at'] = final_df.get('created_at', final_df['violation_date']).fillna(final_df['violation_date'])
                
                # Ensure transporter_name is filled
                if 'transporter_name' not in final_df.columns or final_df['transporter_name'].isna().any():
                    if not df_truck_master.empty:
                        truck_lookup = df_truck_master.set_index('truck_no')
                        final_df['transporter_name'] = final_df.get('transporter_name', pd.Series(index=final_df.index)).fillna(
                            final_df['tl_number'].map(truck_lookup['transporter_name'])
                        )
                if 'violation_date' in final_df.columns:
                    final_df['violation_date'] = final_df['violation_date'].fillna(
                         pd.to_datetime(final_df['created_at'], errors='coerce').dt.strftime('%Y-%m-%d')
                                    )
                return {"status": True, "message": "success", "data": await safe_json(final_df)}
            
            # ==================== QTY SHORTAGE ONLY FILTER ====================
            if has_qty_shortage_filter and not vts_violation_types:
                shortage_query = """
                    SELECT 
                        vehicle_id AS tl_number, 
                        invoice_no AS invoice_number,
                        plant_nm AS location_name,
                        invoice_date,
                        CASE 
                            WHEN qty_shortage = 'NaN' THEN '0.0'
                            WHEN qty_shortage IS NULL THEN '0.0'
                            ELSE qty_shortage 
                        END AS qty_shortage,
                        material_group_nm,
                        zone_nm AS zone,
                        load_date AS created_at
                    FROM sales_trips_till_date
                    WHERE 
                        load_status = '6'
                """

                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, shortage_query)
                shortage_query = VTSAnalyticsActions.apply_conditions_to_query(shortage_query, conditions)
                df_shortage_all = await VTSAnalyticsActions.execute_query(shortage_query)

                if df_shortage_all.empty:
                    return {"status": True, "message": "No shortage data found", "data": []}

                df_shortage_all["qty_shortage"] = pd.to_numeric(df_shortage_all["qty_shortage"], errors="coerce").fillna(0.0)
                df_shortage_all = df_shortage_all[df_shortage_all["qty_shortage"] > 0]

                if df_shortage_all.empty:
                    return {"status": True, "message": "No non-zero shortage data found", "data": []}

                shortage_agg = df_shortage_all.groupby("invoice_number", as_index=False).agg({
                    "qty_shortage": "sum",
                    "zone": "first",
                    "location_name": "first",
                    "tl_number": "first",
                    "material_group_nm": "first"
                })

                tl_numbers_list = shortage_agg["tl_number"].unique().tolist()
                tl_numbers_str = "', '".join(map(str, tl_numbers_list))

                violation_columns = [
                    f"CASE WHEN {v_type} != 0 THEN 1 ELSE 0 END AS {v_type}"
                    for v_type in all_violations
                ]
                select_clause = ",\n       ".join(violation_columns)

                history_query = f"""
                    SELECT DISTINCT
                        tl_number,
                        invoice_number,
                        {select_clause}
                    FROM vts_alert_history
                    WHERE tl_number IN ('{tl_numbers_str}')
                """

                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, history_query)
                history_query = VTSAnalyticsActions.apply_conditions_to_query(history_query, conditions)
                df_history = await VTSAnalyticsActions.execute_query(history_query)

                if df_history.empty:
                    df_history = pd.DataFrame(columns=["tl_number", "invoice_number"] + all_violations)

                # Strip invoice numbers to match format
                df_history["invoice_number"] = df_history["invoice_number"].astype(str).str.split("-").str[0]
                
                # Drop duplicate invoice_numbers from vts_alert_history, keep first
                df_history = df_history.drop_duplicates(subset=["invoice_number"], keep="first")

                truck_query = """
                    SELECT DISTINCT truck_no, transporter_name
                    FROM vts_truck_master
                """
                df_truck = await VTSAnalyticsActions.execute_query(truck_query)

                # Merge with history (only violations, no zone/location_name to avoid conflicts)
                merged_df = shortage_agg.merge(
                    df_history, 
                    on=["tl_number", "invoice_number"], 
                    how="left"
                )

                # Merge with truck master
                merged_df = merged_df.merge(df_truck, left_on="tl_number", right_on="truck_no", how="left")
                merged_df.drop(columns=["truck_no"], inplace=True, errors="ignore")

                # Process violation columns
                for col in all_violations:
                    if col in merged_df.columns:
                        merged_df[col] = (merged_df[col] > 0).astype(int)
                    else:
                        merged_df[col] = 0

                # Since we already aggregated shortage by invoice, just take first values
                agg_dict = {
                    "qty_shortage": "first",
                    "zone": "first",
                    "location_name": "first",
                    "tl_number": "first",
                    "transporter_name": "first",
                }
                for v_col in all_violations:
                    agg_dict[v_col] = "max"  

                agg_df = merged_df.groupby("invoice_number", as_index=False).agg(agg_dict)

                final_cols = ["invoice_number", "zone", "location_name", "tl_number", "qty_shortage", "transporter_name"] + all_violations
                agg_df = agg_df[final_cols]

                return {"status": True, "message": "success", "data": await safe_json(agg_df)}

            # ==================== SPECIFIC VIOLATION TYPES ====================
            if violation_types:
                select_parts = [
                    f"COUNT(DISTINCT CASE WHEN {v_type} != 0 THEN invoice_number END) AS {v_type}"
                    for v_type in all_violations
                ]
                select_clause = ",\n           ".join(select_parts)
                
                if vts_violation_types:
                    having_parts = [
                        f"COUNT(DISTINCT CASE WHEN {v_type} != 0 THEN invoice_number END) > 0"
                        for v_type in vts_violation_types
                    ]
                    having_clause = " AND ".join(having_parts)
                else:
                    having_clause = "1=1"
                
                violation_query = vts_query.vts_query.get("vts_insite_history_type")
                violation_query = violation_query.format(select_clause=select_clause, having_clause=having_clause)
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, violation_query)
                violation_query = VTSAnalyticsActions.apply_conditions_to_query(violation_query, conditions)
                
                df_history = await VTSAnalyticsActions.execute_query(violation_query)
                if not df_history.empty:
                    df_history = df_history.drop_duplicates(subset=["invoice_number"], keep="first")

                # Get shortage data
                df_shortage = await get_shortage_data()
                
                # Merge
                final_df = merge_shortage_with_violations(df_history, df_shortage, df_truck_master, aggregate=True)

                # Filter by qty_shortage if requested
                if has_qty_shortage_filter and not final_df.empty:
                    final_df = final_df[final_df.get('qty_shortage', 0) > 0]

                if final_df.empty:
                    return {"status": True, "message": "No violations found", "data": []}

                # Aggregate by invoice
                violation_cols = [col for col in all_violations if col in final_df.columns]
                agg_dict = {
                    "qty_shortage": "sum",
                    "zone": "first",
                    "location_name": "first",
                    "tl_number": "first",
                    "transporter_name": "first",
                }
                for col in violation_cols:
                    agg_dict[col] = "max"

                final_df = final_df.groupby("invoice_number", as_index=False).agg(agg_dict)

                for col in violation_cols:
                    final_df[col] = final_df[col].fillna(0).astype(int)

                return {"status": True, "message": "success", "data": await safe_json(final_df)}

            # ==================== DEFAULT CASE - ALL DATA ====================
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
            df_history = await VTSAnalyticsActions.execute_query(query)
            
            if not df_history.empty and 'invoice_number' in df_history.columns:
                df_history = df_history.drop_duplicates(subset=["invoice_number"], keep="first")

            # Get shortage data
            df_shortage = await get_shortage_data()
            
            # Merge
            final_df = merge_shortage_with_violations(df_history, df_shortage, df_truck_master, aggregate=True)

            if final_df.empty:
                return {"status": True, "message": "No data found", "data": []}

            # Ensure qty_shortage column exists
            if 'qty_shortage' not in final_df.columns:
                final_df['qty_shortage'] = 0
            else:
                final_df['qty_shortage'] = pd.to_numeric(final_df['qty_shortage'], errors='coerce').fillna(0)
            
            # Filter out rows with no violations at all
            violation_cols = [v for v in all_violations if v in final_df.columns]
            violation_cols.append('qty_shortage')
            
            final_df['total_violations'] = final_df[violation_cols].sum(axis=1)

            if bu_ic and not violation_types:
                # For I&C default, include all rows (including zero violations)
                pass
            else:   
                final_df = final_df[final_df['total_violations'] > 0]

            final_df.drop(columns=['total_violations'], inplace=True, errors='ignore')

            if final_df.empty:
                return {"status": True, "message": "No violation data found", "data": []}

            # ==================== HANDLE GROUP_BY ====================
            group_by_col = payload.get("group_by") if payload else None
            if group_by_col and group_by_col in final_df.columns:
                violation_cols = [v for v in all_violations if v in final_df.columns]
                violation_cols.append('qty_shortage')
            
                agg_df = final_df.groupby(group_by_col)[violation_cols].sum().reset_index()
                agg_df['total_count'] = agg_df[violation_cols].sum(axis=1)
                
                return {"status": True, "message": "success", "data": agg_df.to_dict(orient='records')}

            # ==================== HANDLE DRILL-DOWN ====================
            qlick_view = payload.get("qlick_view") if payload else None
            click_value = payload.get("click_value") if payload else None
            location_name = payload.get("location_name") if payload else None
            
            violation_cols = [v for v in all_violations if v in final_df.columns]
            violation_cols.append('qty_shortage')

            # ZONE VIEW
            if qlick_view == "zone" and not click_value:
                final_df["zone"] = final_df["zone"].fillna("Unknown")
                agg_df = final_df.groupby("zone")[violation_cols].sum().reset_index()
                agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                return {"status": True, "message": "Zone-wise violations", "data": agg_df.to_dict(orient="records")}

            # ZONE -> LOCATION DRILL
            if qlick_view == "zone" and click_value:
                zone_df = final_df[final_df["zone"] == click_value]
                if zone_df.empty:
                    return {"status": True, "message": f"No data found for zone {click_value}", "data": []}
                
                agg_df = zone_df.groupby("location_name")[violation_cols].sum().reset_index()
                agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                
                return {"status": True, "message": f"Violations for all plants in zone {click_value}", "data": agg_df.to_dict(orient="records")}

            # LOCATION -> TRANSPORTER DRILL
            elif qlick_view == "location_name" and click_value:
                location_df = final_df[final_df["location_name"] == click_value]
                if location_df.empty:
                    return {"status": True, "message": f"No data found for location {click_value}", "data": []}
                
                agg_df = location_df.groupby("transporter_name")[violation_cols].sum().reset_index()
                agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                
                return {"status": True, "message": f"Violations for all transporters in location {click_value}", "data": agg_df.to_dict(orient="records")}

            # TRANSPORTER -> VEHICLE DRILL
            elif qlick_view == "transporter_name" and click_value and location_name:
                transporter_df = final_df[
                    (final_df["transporter_name"] == click_value) & 
                    (final_df["location_name"] == location_name)
                ]
                if transporter_df.empty:
                    return {"status": True, "message": f"No data found for transporter {click_value}", "data": []}
                
                agg_df = transporter_df.groupby("tl_number")[violation_cols].sum().reset_index()
                agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                
                return {"status": True, "message": f"Vehicle-wise violations for transporter {click_value}", "data": agg_df.to_dict(orient="records")}

            # VEHICLE -> INVOICE DRILL
            elif qlick_view == "tl_number" and click_value:
                vehicle_df = final_df[final_df["tl_number"] == click_value]
                if vehicle_df.empty:
                    return {"status": True, "message": f"No data found for vehicle {click_value}", "data": []}
                
                if 'invoice_number' in vehicle_df.columns:
                    group_cols = ["invoice_number"]
                    if "created_at" in vehicle_df.columns:
                        group_cols.append("created_at")
                    
                    agg_df = vehicle_df.groupby(group_cols)[violation_cols].sum().reset_index()
                    agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                else:
                    agg_df = vehicle_df.copy()
                    agg_df["total_count"] = agg_df[violation_cols].sum(axis=1)
                
                return {"status": True, "message": f"Invoice-wise violations for vehicle {click_value}", "data": agg_df.to_dict(orient="records")}

            # ==================== DOWNLOAD ====================
            if payload.get("download") == "true":
                merged_df = pd.DataFrame(final_df)
                for col in merged_df.select_dtypes(include=["datetime64[ns, UTC]", "datetimetz"]).columns:
                    merged_df[col] = merged_df[col].dt.tz_localize(None)

                merged_df = merged_df.dropna(axis=1, how="all")
                merged_df = merged_df.loc[:, (merged_df.astype(str).apply(lambda x: x.str.strip() != "").any())]

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"violations_{timestamp}.xlsx"

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    merged_df.to_excel(writer, index=False, sheet_name='violations')

                output.seek(0)
                headers = {
                    "Content-Disposition": f'attachment; filename="{file_name}"'
                }
                return StreamingResponse(
                    output,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers
                )

            return {"status": True, "message": "success", "data": await safe_json(final_df)}

        except Exception as e:
            print("ERROR:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
        
    @staticmethod
    async def violation_percentages(filters, cross_filters, drill_state, payload):
        try:
            # Step 1: Get base query and apply filters
            query = vts_query.vts_query.get(drill_state.split(",")[0])
            emlock_open_query = vts_query.vts_query.get("emlock_open")

            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
            df = await VTSAnalyticsActions.execute_query(query)

            emlock_conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, emlock_open_query)
            emlock_query = VTSAnalyticsActions.apply_conditions_to_query(emlock_open_query, emlock_conditions)
            emlock_df = await VTSAnalyticsActions.execute_query(emlock_query)
            emlock_open = emlock_df["emlock_open"][0] if not emlock_df.empty else 0

            if df.empty:
                return {"status": True, "message": "No data found", "data": []}

            # Step 2: Define violation columns
            violation_cols = [
                "route_deviation_count",
                "stoppage_violations_count",
                "device_tamper_count",
                "speed_violation_count",
                "night_driving_count",
                "main_supply_removal_count"
            ]

            df_viol = df[["invoice_number"] + violation_cols].copy()
            df_viol.dropna(subset=["invoice_number"], inplace=True)

            # Step 3: Convert to binary (mark violations)
            for col in violation_cols:
                if col == "main_supply_removal_count":
                    df_viol[col] = df_viol[col].apply(lambda x: 1 if x and x >= 6 else 0)
                else:
                    df_viol[col] = df_viol[col].apply(lambda x: 1 if x and x != 0 else 0)

            # Step 4: Count each violation across all invoices
            violation_counts = {col: df_viol[col].sum() for col in violation_cols}

            # Step 5: Add emlock_open
            violation_counts["emlock_open"] = emlock_open

            # Step 6: Get shortage count
            shortage_result = await VTSAnalyticsActions.total_count_shortage(filters, cross_filters, drill_state, payload)
            shortage_count = shortage_result.get("trip_count", 0) if shortage_result.get("status") else 0
            violation_counts["shortage_count"] = shortage_count

            # --- PRINT COUNTS ---
            print("Violation counts (including emlock and shortage):")
            for key, count in violation_counts.items():
                print(f"{key}: {count}")

            # Step 7: Calculate total and percentages
            total_all = sum(violation_counts.values())
            percentages = {}
            for key, count in violation_counts.items():
                percentages[key] = round(100 * count / total_all, 2) if total_all > 0 else 0

            # Step 8: Adjust rounding so total = 100
            total_percent = round(sum(percentages.values()), 2)
            diff = round(100 - total_percent, 2)
            if diff != 0:
                largest_key = max(percentages, key=percentages.get)
                percentages[largest_key] = round(percentages[largest_key] + diff, 2)
            
            download_flag = payload.get("download")
            if (isinstance(download_flag, bool) and download_flag) or (
                isinstance(download_flag, str) and download_flag.strip().lower() == "true"
            ):
                print("Download requested — generating Excel with multiple violation sheets")

                output = io.BytesIO()
                
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    combined_violation_rows = []
                    for v_type in list(violation_counts.keys()):
                        print(f"Generating sheet for: {v_type}")

                        # ------------------------------------
                        #  Case 1: Handle Emlock Open separately
                        # ------------------------------------
                        if v_type == "emlock_open":
                            print("Fetching full emlock_open data from vts_tripauditmaster...")

                            
                            emlock_query = """
                                SELECT *
                                FROM vts_tripauditmaster
                                WHERE 
                                    (swipeoutl1 != 'true' OR swipeoutl2 != 'true')
                            """

                           
                            emlock_conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, emlock_query)
                            emlock_query = VTSAnalyticsActions.apply_conditions_to_query(emlock_query, emlock_conditions)

                            
                            emlock_df = await VTSAnalyticsActions.execute_query(emlock_query)

                            
                            print("emlock_df columns:", list(emlock_df.columns) if emlock_df is not None else "None")
                            print("emlock_df row count:", len(emlock_df) if emlock_df is not None else 0)
                            print("emlock_df sample:", emlock_df.head(5).to_dict(orient='records') if emlock_df is not None and not emlock_df.empty else "Empty")

                            if emlock_df is None or emlock_df.empty:
                                pd.DataFrame([{"message": "No data found for emlock_open"}]).to_excel(
                                    writer, index=False, sheet_name="emlock_open"
                                )
                                continue

                            
                            emlock_df.to_excel(writer, index=False, sheet_name="emlock_open")
                            print(f" Wrote sample ({len(emlock_df)} rows) to emlock_open sheet.")
                            continue

                        # ------------------------------------
                        #  Case 2: Handle Shortage Count separately
                        # ------------------------------------
                        if v_type == "shortage_count":
                            print("Fetching shortage data (independent SQL)…")

                            # ------------------------------
                            # 1. Build NEW shortage SQL (no BU filter)
                            # ------------------------------
                            

                            shortage_query= f"""
                                SELECT *
                                FROM sales_trips_till_date T
                                WHERE  load_status = '6'                
                            """
                            shortage_conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, shortage_query)
                            shortage_query = VTSAnalyticsActions.apply_conditions_to_query(shortage_query, shortage_conditions)

                            
                            shortage_df = await VTSAnalyticsActions.execute_query(shortage_query)
                            shortage_vehicle_count = shortage_df['vehicle_id'].nunique()
                            shortage_invoice_count = shortage_df['invoice_no'].nunique()

                            print("Shortage SQL:\n", shortage_query)

                            # ------------------------------
                            # 2. Execute the SQL to get FULL DATA
                            # ------------------------------
                            shortage_df = await VTSAnalyticsActions.execute_query(shortage_query)

                            print("shortage_df columns:", list(shortage_df.columns) if shortage_df is not None else "None")
                            print("shortage_df row count:", len(shortage_df) if shortage_df is not None else 0)
                            # print("shortage_df sample:", shortage_df.head(5).to_dict(orient='records') if shortage_df is not None and not shortage_df.empty else "Empty")

                            # ------------------------------
                            # 3. Write to Excel (not count)
                            # ------------------------------
                            if shortage_df is None or shortage_df.empty:
                                pd.DataFrame([{"message": "No data found for shortage_count"}]).to_excel(
                                    writer, index=False, sheet_name="shortage_count"
                                )
                            else:
                                shortage_df.to_excel(writer, index=False, sheet_name="shortage_count")

                            continue
                        # ------------------------------------
                        # Case 3: All other violation types (default logic)
                        # ------------------------------------
                        if v_type in violation_cols:
                            # DO NOTHING HERE
                            # DON'T QUERY ALL VIOLATIONS HERE
                            continue

                    # -----------------------------------------------------
                    # 🔵 AFTER LOOP (this runs ONLY ONCE)
                    # -----------------------------------------------------
                    violation_query = """
                        SELECT
                            tl_number,
                            invoice_number,
                            location_name,
                            zone,
                            DATE(vts_end_datetime) AS created_at,
                            stoppage_violations_count,
                            route_deviation_count,
                            device_tamper_count,
                            main_supply_removal_count,
                            night_driving_count,
                            speed_violation_count,
                            continuous_driving_count
                        FROM vts_alert_history
                        WHERE 
                            (
                                stoppage_violations_count > 0 OR
                                route_deviation_count > 0 OR
                                device_tamper_count > 0 OR
                                main_supply_removal_count > 0 OR
                                night_driving_count > 0 OR
                                speed_violation_count > 0 OR
                                continuous_driving_count > 0
                            )
                    """

                    violation_conditions = VTSAnalyticsActions.build_filter_conditions(
                        filters, cross_filters, violation_query
                    )
                    violation_query = VTSAnalyticsActions.apply_conditions_to_query(
                        violation_query, violation_conditions
                    )

                    print("FINAL ALL VIOLATIONS SQL:", violation_query)

                    viol_df = await VTSAnalyticsActions.execute_query(violation_query)
                    viol_df = viol_df.drop_duplicates(subset=['invoice_number'], keep='first')

                    if viol_df is None or viol_df.empty:
                        pd.DataFrame([{"message": "No violations found"}]).to_excel(
                            writer, index=False, sheet_name="all_violations"
                        )
                    else:
                        # viol_df.drop_duplicates(inplace=True)
                        viol_df.to_excel(writer, index=False, sheet_name="all_violations")

                # --- Finalize and stream Excel file ---
                output.seek(0)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"violation_percentages_{timestamp}.xlsx"
                headers = {"Content-Disposition": f'attachment; filename=\"{file_name}\"'}

                return StreamingResponse(
                    output,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers
                )

            # Step 9: Return final response
            return {
                "status": True,
                "message": "Violation percentages calculated",
                "data": percentages
            }

        except Exception as e:
            import traceback
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}



    @staticmethod
    async def total_count_shortage(filters, cross_filters, drill_state, payload):
        try:
            # Step 1: Build the base query to get shortage data
            shortage_query = """
            SELECT 
                sap_id, 
                vehicle_id, 
                invoice_no,
                SUM(qty_shortage::numeric) as qty_shortage 
            FROM sales_trips_till_date
            WHERE
                load_status = '6'
            GROUP BY vehicle_id, invoice_no, sap_id
            """
            
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, shortage_query)
            shortage_query = VTSAnalyticsActions.apply_conditions_to_query(shortage_query, conditions)
            print("Shortage Query:", shortage_query)

            # REMOVED: shortage_query = VTSAnalyticsActions.apply_conditions_to_query(shortage_query, conditions_str)
            
            # Step 2: Get location master data
            location_query = """
            SELECT 
                sap_id,
                bu
            FROM location_master
            """
            
            # Execute both queries
            shortage_df = await VTSAnalyticsActions.execute_query(shortage_query)
            location_df = await VTSAnalyticsActions.execute_query(location_query)
            
            # Check if dataframes are empty
            if shortage_df.empty:
                return {"status": True, "message": "No shortage data found", "data": []}
            
            if location_df.empty:
                return {"status": False, "message": "Location master data not available", "data": []}
            
            # Step 3: Merge the dataframes on sap_id
            merged_df = shortage_df.merge(location_df, on='sap_id', how='left')
            
            filtered_df = merged_df.copy()
            
            if filters:
                for rec in filters:
                    if rec.key.lower() == 'bu':
                        filtered_df = filtered_df[filtered_df['bu'] == rec.value]
            
            total_count = len(filtered_df)
                
            return {
                "status": True, 
                "message": "Success", 
                "trip_count": total_count
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
            # vts_df = vts_df.drop_duplicates(subset=['invoice_number'], keep='first')
            vts_df.rename(columns={"vts_end_datetime": "created_at"}, inplace=True)
            vts_df["created_at"] = pd.to_datetime(vts_df["created_at"]).dt.date
            vts_df = vts_df.sort_values(by='created_at', ascending=True)
            # vts_df = vts_df.drop_duplicates(subset=['invoice_number', 'zone'], keep='first')


            if vts_df.empty:
                return {"status": True, "message": "No data found", "data": []}
            
            transporter_query = """SELECT distinct truck_no, transporter_name FROM vts_truck_master"""
            transporter_df = await VTSAnalyticsActions.execute_query(transporter_query)
            merged_df = vts_df.merge(transporter_df, left_on="tl_number", right_on="truck_no", how="left")

            # Step 5: Filter violation type
            violation_type = payload.get("violation_type")
            if not violation_type or violation_type not in merged_df.columns:
                return {"status": False, "message": f"Invalid violation type: {violation_type}", "data": []}

            violation_filtered_df = merged_df[merged_df[violation_type].fillna(0) != 0].copy()
            violation_filtered_df = violation_filtered_df.sort_values(by='created_at', ascending=True)
            violation_filtered_df = violation_filtered_df.drop_duplicates(subset=['invoice_number'], keep='first')

            # Step 6: Remove empty values for zone, location, transporter
            for key in ["zone", "location_name", "transporter_name"]:
                if payload.get(key):
                    violation_filtered_df = violation_filtered_df[violation_filtered_df[key] == payload[key]]

            if violation_filtered_df.empty:
                return {"status": True, "message": "No data found for the applied filters", "data": []}

            # Step 7: TL-level drill-down for invoice details
            selected_tl = payload.get("tl_number")
            if selected_tl:
                violation_filtered_df = violation_filtered_df[violation_filtered_df["tl_number"] == selected_tl]

                if violation_filtered_df.empty:
                    return {"status": True,  "message": f"No invoices found for vehicle {selected_tl}", "data": []  }

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
                return { "status": True,  "message": f"{violation_type} details for vehicle {selected_tl}",  "data": result }

            # Step 8: Determine grouping column for summaries
            if payload.get("transporter_name"):
                group_col = "tl_number"
            elif payload.get("location_name"):
                group_col = "transporter_name"
            elif payload.get("zone"):
                group_col = "location_name"
            else:
                group_col = "zone"
            if "zone" in violation_filtered_df.columns:
                violation_filtered_df["zone"] = violation_filtered_df["zone"].fillna("UNKNOWN")

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
            return {"status": True,  "message": f"{violation_type} drill-down data", "data": result }

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
            else:
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
                query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)

            # Step 2: Execute base ongoing trips query
            df = await VTSAnalyticsActions.execute_query(query)
            df.drop(columns=["zone"], inplace=True, errors="ignore")

            # Remove duplicate records
            df = df.drop_duplicates(
                subset=["event_start_datetime", "event_end_datetime", "tt_number", "invoice_no"],
                keep="first"
            )

            if df.empty:
                return {"status": True, "message": "No data found", "data": []}

            # Step 3: Get location info
            sap_id_list = df['sap_id'].dropna().astype(str).tolist()
            if not sap_id_list:
                df["location_name"] = "Unknown"
                df["zone"] = "Unknown"
                merged_df = df.copy()
            else:
                sap_id_str = "', '".join(map(str, sap_id_list))
                location_query = f"""
                    SELECT sap_id, name AS location_name, zone 
                    FROM location_master 
                    WHERE sap_id IN ('{sap_id_str}')
                """
                loc_df = await VTSAnalyticsActions.execute_query(location_query)

                # Step 4: Merge location info (keep all trips)
                df["sap_id"] = df["sap_id"].astype(str).str.strip()
                loc_df["sap_id"] = loc_df["sap_id"].astype(str).str.strip()
                merged_df = df.merge(loc_df, on="sap_id", how="left")

                # Fill missing values — don't drop any record
                merged_df["location_name"] = merged_df["location_name"].fillna("Unknown")
                merged_df["zone"] = merged_df["zone"].fillna("Unknown")

            # Step 5: Fetch alert history only for ongoing trips' invoices
            invoice_list = merged_df["invoice_no"].dropna().astype(str).unique().tolist()
            if not invoice_list:
                return {"status": True, "message": "No invoices found in trips", "data": []}

            invoices_str = "', '".join(invoice_list)
            completed_trips_query = f"""
                SELECT DISTINCT invoice_no
                FROM vts_completed_trip
                WHERE invoice_no IN ('{invoices_str}')
            """
            alert_df = await VTSAnalyticsActions.execute_query(completed_trips_query)
            alert_invoice_list = alert_df["invoice_no"].astype(str).tolist() if not alert_df.empty else []

            # Step 6: Filter based on live / closed status
            status_filter = payload.get("status")
            if status_filter == "live":
                merged_df = merged_df[~merged_df["invoice_no"].astype(str).isin(alert_invoice_list)]
            elif status_filter == "closed":
                merged_df = merged_df[merged_df["invoice_no"].astype(str).isin(alert_invoice_list)]

            if merged_df.empty:
                return {"status": True, "message": f"No {status_filter} trips found", "data": []}

            # Step 7: TT-level drill-down
            selected_tt = payload.get("tt_number")
            if selected_tt:
                merged_df = merged_df[merged_df["tt_number"] == selected_tt]
                if merged_df.empty:
                    return {"status": True, "message": f"No trips found for vehicle {selected_tt}", "data": []}

                merged_df["created_at"] = (
                    pd.to_datetime(merged_df["event_start_datetime"].fillna(merged_df["event_end_datetime"]))
                    .dt.date.astype(str)
                )
                trip_df = merged_df.sort_values(by="created_at", ascending=True)
                trip_df = trip_df[["invoice_no", "created_at"]]
                result = trip_df.to_dict(orient="records")
                return {"status": True, "message": f"Trip details for vehicle {selected_tt}", "data": result}

            # Step 8: Grouping logic (zone / location / transporter)
            merged_df["zone"] = merged_df["zone"].fillna("Unknown")
            merged_df["location_name"] = merged_df["location_name"].fillna("Unknown")
            merged_df["transporter_name"] = merged_df["transporter_name"].fillna("Unknown")

            if payload.get("transporter_name"):
                group_col = "tt_number"
            elif payload.get("location_name"):
                group_col = "transporter_name"
            elif payload.get("zone"):
                group_col = "location_name"
            else:
                group_col = "zone"

            summary_df = (
                merged_df.groupby(group_col, dropna=False)
                .agg({"invoice_no": pd.Series.nunique})
                .reset_index()
            )

            if group_col != "tt_number":
                summary_df["vehicle_count"] = merged_df.groupby(group_col, dropna=False)["tt_number"].nunique().values

            summary_df.rename(columns={"invoice_no": "invoice_count"}, inplace=True)
            result = summary_df.to_dict(orient="records")

            # Step 9: Handle Excel download
            if payload.get("download") == "true":
                for col in merged_df.select_dtypes(include=["datetime64[ns, UTC]", "datetimetz"]).columns:
                    merged_df[col] = merged_df[col].dt.tz_localize(None)

                violation_mapping = {
                    "HS": "Hotspot",
                    "TC": "Trip not closed more than 2 hours",
                    "RD": "Route Deviation > 2km",
                    "WR": "Trip without route"
                }
                if "violation_type" in merged_df.columns:
                    merged_df["violation_type"] = merged_df["violation_type"].replace(violation_mapping)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"{ongoing_trips_type}{status_filter}{timestamp}.xlsx"
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    merged_df.to_excel(writer, index=False, sheet_name='ongoing_trips')
                output.seek(0)
                headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
                return StreamingResponse(
                    output,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers
                )

            return {"status": True, "message": f"{status_filter} data found", "data": result}

        except Exception as e:
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}


    @staticmethod
    async def safety_compliance(filters, cross_filters, drill_state, payload):                       
        try:
            if payload.get("download"):
                print("Download requested — generating Excel with multiple sheets (Polars only)")

                # Step 1: Parse table names
                table_names = [tbl.strip() for tbl in drill_state.split(",") if tbl.strip()]
                if not table_names:
                    return JSONResponse({"error": "Missing drill_state (table names)"}, status_code=400)

                # Create an in-memory Excel file
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    combined_violation_rows = []


                    # Step 2: Loop tables and add sheets dynamically
                    for table_name in table_names:

                        query = vts_query.vts_query.get("safety_compliance")
                        query = query.format(drill_state=table_name)

                        conditions = VTSAnalyticsActions.build_filter_conditions(
                            filters, cross_filters, query
                        )
                        final_query = VTSAnalyticsActions.apply_conditions_to_query(
                            query, conditions
                        )

                        print(f" Running query for table '{table_name}': {final_query}")

                        df = await VTSAnalyticsActions.execute_query(final_query)
                        df = df.drop_duplicates(keep="first")

                        if df is None or len(df) == 0:
                            print(f"No data found for {table_name}, skipping...")
                            continue

                        # if not isinstance(df, pl.DataFrame):
                        #     df = pl.DataFrame(df)

                        # # Convert Polars → Pandas for Excel writer
                        # pdf = df.to_pandas()

                        # Write to Excel sheet (sheet name from table_name)
                        sheet_name = table_name[:31]  # Excel max 31 chars
                        df.to_excel(writer, index=False, sheet_name=sheet_name)

                # Finalize BytesIO
                output.seek(0)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"safety_complaince_{timestamp}.xlsx"

                headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}

                return StreamingResponse(
                    output,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers
                )
            # Step 1: Get base query
            query = vts_query.vts_query.get('safety_compliance')
            drill_state_col = drill_state.split(",")[0]
            query = query.format(drill_state=drill_state_col)

            # Step 2: Apply filters
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
            print(query)

            # Step 3: Execute query
            df = await VTSAnalyticsActions.execute_query(query)
            df = df.drop_duplicates(keep='first')

            if df.empty:
                return {"status": True, "message": "No data found", "data": []}

            # Step 4: Apply payload filters for zone, location_name, transporter_name
            for key in ["zone", "location_name", "transporter_name"]:
                if payload.get(key):
                    df = df[df[key] == payload[key]]

            if df.empty:
                return {"status": True, "message": "No data found for the applied filters", "data": []}

            # Step 5: If tt_number in payload, return per-trip details with timestamp
            selected_tt = payload.get("tt_number")
            if selected_tt:
                trip_df = df[df["tt_number"] == selected_tt].copy()
                if trip_df.empty:
                    return {"status": True, "message": f"No trips found for vehicle {selected_tt}", "data": []}

                # Keep full event_date with timestamp
                trip_df = trip_df.sort_values(by="event_date")
                result = trip_df[["invoice_no", "event_date"]].rename(columns={"event_date": "created_at"}).to_dict(orient="records")

                return {"status": True, "message": f"Trip details for vehicle {selected_tt}", "data": result}

            # Step 6: Determine grouping column
            if payload.get("transporter_name"):
                group_col = "tt_number"
            elif payload.get("location_name"):
                group_col = "transporter_name"
            elif payload.get("zone"):
                group_col = "location_name"
            else:
                group_col = "zone"

            # Step 7: Group by and summarize
            df[group_col] = df[group_col].fillna("Unknown")
            summary_df = df.groupby(group_col).agg(
                invoice_count=("invoice_no", "nunique"),
                vehicle_count=("tt_number", "nunique"),
                **{f"{drill_state_col}_count": ("event_date", "count")}
            ).reset_index()

            result = summary_df.to_dict(orient='records')
            return {"status": True, "message": "success", "data": result}

        except Exception as e:
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
    
    @staticmethod
    async def safety_compliance_percentage(filters, cross_filters, drill_state, payload):
            try:
                # Queries returning counts
                query_keys = [
                    "vts_panic",
                    "vts_harsh_braking",
                    "vts_harsh_acceleration",
                    "vts_device_removed"
                ]

            
                counts = {}
                for key in query_keys:
                    query = vts_query.vts_query.get(key)
                    conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
                    query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
                
                    df = await VTSAnalyticsActions.execute_query(query)
                    counts[key] = int(df.iloc[0, 0]) if not df.empty else 0
                  

            
                total = sum(counts.values())
                if total == 0:
                    return {"status": True, "message": "No data found", "data": []}

                percentages = {k: round((v / total) * 100, 2) for k, v in counts.items()}

            
                diff = 100 - sum(percentages.values())
                if abs(diff) > 0.01:
                    max_key = max(percentages, key=percentages.get)
                    percentages[max_key] = round(percentages[max_key] + diff, 2)

                return {"status": True, "message": "Success", "data": percentages}

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
        import pytz
        from datetime import datetime, timedelta
        
        # ----- 1. Filter Separation and Date Condition Preparation ----- 
        trips_filters = filters  # All filters apply to trips
        
        # Extract Transporter Filter for later Pandas application (must be done post-merge)
        transporter_filter = next((f for f in trips_filters if getattr(f, 'key') == 'transporter_name'), None)
        trips_query = f"""
            SELECT *     
            FROM 
                sales_trips_till_date T
            WHERE load_status = '6'
        """
        sql_filters = [f for f in filters if getattr(f, "key", None) != "transporter_name"]    
        conditions = VTSAnalyticsActions.build_filter_conditions(sql_filters, cross_filters, trips_query)
        trips_query = VTSAnalyticsActions.apply_conditions_to_query(trips_query, conditions)
        print("trips_query", trips_query)
        trips_df = await VTSAnalyticsActions.execute_query(trips_query)
        if trips_df.empty:
            return {"status": "success", "total_invoice_count": 0, "total_vehicle_count": 0,
                    "filtered_invoice_count": 0, "filtered_vehicle_count": 0, "zones": []}
            
        trips_df.columns = [c.lower() for c in trips_df.columns]
        # 4b. Merge email master
        email_query = "SELECT transporter_code, transporter_name FROM email_master"
        email_df = await VTSAnalyticsActions.execute_query(email_query)

        if not email_df.empty:
            email_df.columns = [c.lower() for c in email_df.columns]

            # Clean and normalize keys
            email_df['transporter_code'] = (
                email_df['transporter_code']
                .astype(str)
                .str.strip()
                .str.replace(r'^00', '', regex=True)
            )
            trips_df['carrier_no'] = (
                trips_df['carrier_no']
                .astype(str)
                .str.strip()
                .str.replace(r'^00', '', regex=True)
            )

            # Ensure transporter_code is unique
            email_df = email_df.drop_duplicates(subset=['transporter_code'])

            # SAFE mapping: no extra rows, just add transporter_name column
            email_map = email_df.set_index('transporter_code')['transporter_name']
            trips_df['transporter_name'] = trips_df['carrier_no'].map(email_map)

            # --- Debug export for missing transporter_name ---
            # trips_df.to_csv('/Users/algofusion/Downloads/missing_transporters.csv', index=False)

        # ----- 5. Filter valid trips (Original Logic) -----
        
        # trips_df['qty_shortage'] = pd.to_numeric(trips_df['qty_shortage'], errors='coerce')
        trips_df['qty_shortage'] = (
            trips_df['qty_shortage']
            .astype(str)
            .str.replace(r"[^0-9.]", "", regex=True)  # keep only digits & decimal
            .str.strip()
        )

        trips_df['qty_shortage'] = pd.to_numeric(trips_df['qty_shortage'], errors='coerce').fillna(0)

        filtered_trips_df = trips_df[
            # trips_df['transporter_name'].notnull() &
            # trips_df['transporter_code'].notnull() &
            (trips_df['qty_shortage'] > 0)
        ].copy()

        # ----- 6. Apply Transporter Filter (Pandas, Original Logic) -----
        
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

        # ----- 7. Counts after filtering (Original Logic) -----
        filtered_vehicle_count = filtered_trips_df['vehicle_id'].nunique()
        filtered_invoice_count = filtered_trips_df['invoice_no'].nunique()

        # filtered_vehicle_count = len(filtered_trips_df['vehicle_id'])
        
        if filtered_trips_df.empty:
            return {"status": "success", "total_invoice_count": 0, "total_vehicle_count": 0,
                    "filtered_invoice_count": 0, "filtered_vehicle_count": 0, "zones": []}
                    
        # filtered_trips_df = filtered_trips_df.drop_duplicates()

        # ----- 8. Convert load_date to IST (CRITICAL FIX: Original Logic) -----
        
        ist = pytz.timezone("Asia/Kolkata")
        if 'load_date' in filtered_trips_df.columns:
            filtered_trips_df['load_date'] = pd.to_datetime(filtered_trips_df['load_date'])
            
            if filtered_trips_df['load_date'].dt.tz is None:
                filtered_trips_df['load_date'] = filtered_trips_df['load_date'].dt.tz_localize('UTC').dt.tz_convert(ist)
            else:
                filtered_trips_df['load_date'] = filtered_trips_df['load_date'].dt.tz_convert(ist)
                
            filtered_trips_df['load_date'] = filtered_trips_df['load_date'].dt.strftime("%Y-%m-%d %H:%M:%S%z")

        # ----- 9. Dynamic hierarchical grouping (Original Logic) -----
        
        def compute_group_summary(df, group_cols):
            if not group_cols:
                return None

            result = []
            current_col = group_cols[0]
            next_cols = group_cols[1:]

            for keys, group in df.groupby(current_col, dropna=False):
                item = {current_col: keys}
                # item["shortage"] = group["qty_shortage"].sum()
                item["shortage"] = group["qty_shortage"].astype(float).sum()

                item["invoice_count"] = group["invoice_no"].nunique()
                # item["vehicle_count"] = group["vehicle_id"].nunique()
                # item["invoice_count"] = len(group["invoice_no"])
                # print('item["invoice_count"]', item["invoice_count"])
                item["vehicle_count"] = group["vehicle_id"].nunique()  
                

                # --- Material Group Bifurcation Logic ---
                if "material_group_nm" in group.columns and "qty_shortage" in group.columns:
                    bif_df = (
                        group
                        .groupby("material_group_nm", dropna=False)["qty_shortage"]
                        .sum()
                        .reset_index()
                    )

                    item["item_bifurcation"] = [
                        {
                            "material_group_nm": row["material_group_nm"],
                            "shortage": round(float(row["qty_shortage"]), 2),
                        }
                        for _, row in bif_df.iterrows()
                    ]


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
                    if current_col == "invoice_no" and "load_date" in group.columns:
                        item["load_date"] = group["load_date"].iloc[0]
                    

                result.append(item)

            return result

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
        if "material_group_nm" not in filtered_trips_df.columns and "item_no" in filtered_trips_df.columns:
            filtered_trips_df.rename(columns={"item_no": "material_group_nm"}, inplace=True)
        
        
        if payload.get('table') == "true":
            filtered_trips_df = filtered_trips_df.rename(columns={'material_group_nm':'product_bifurcation', 'qty_shortage':'shortage'})
            filtered_trips_df['product_bifurcation'] = (
                    filtered_trips_df['product_bifurcation'].astype(str) + 
                    ':' + filtered_trips_df['shortage'].astype(str)
                )
            table_df =( filtered_trips_df
                .groupby(['vehicle_id', 'invoice_no'], as_index=False)
                .agg({
                    'shortage': 'sum',  # sum shortages for same vehicle+invoice
                    'product_bifurcation': lambda x: ', '.join(x),
                    'plant_nm': 'first',
                    'zone_nm': 'first',
                    'transporter_name': 'first',
                    'load_date': 'first'
                })
            )

            shortage_filter = payload.get("shortage_filter") # <=
            if shortage_filter:
                sf = str(shortage_filter).replace(" ", "")

                if "<" in sf:
                    limit = float(sf.split("<")[1])
                    table_df = table_df[table_df["shortage"] < limit]
                elif ">=" in sf or "≥" in sf:
                    limit = float(sf.split(">=")[1]) if ">=" in sf else float(sf.replace("≥", ""))
                    table_df = table_df[table_df["shortage"] >= limit]

            total_records = len(table_df)
            # print("total_records:", total_records)
            total_shortage = table_df["shortage"].sum()

            # 3) Pagination
            page = int(payload.get("page", 1))
            page_size = int(payload.get("page_size", 100))  # default 100

            if page_size <= 0:
                page_size = total_records

            start = (page - 1) * page_size
            end = page * page_size

            paged_df = table_df.iloc[start:end]

            return {
                "status": "success",
                "message": "Table Data fetched successfully",
                "data": await safe_json(paged_df),
                "page": page,
                "page_size": page_size,
                "total_records": total_records,"total_shortage":total_shortage
            }
            
            #  return {"status": "success","message": "Table Data fetched successfully", "data": await safe_json(table_df)}
    
        filtered_trips_df = filtered_trips_df.replace([float('inf'), float('-inf')], None)
        filtered_trips_df = filtered_trips_df.where(pd.notnull(filtered_trips_df), None)
        print("TOTAL SHORTAGE BEFORE GROUPING =", filtered_trips_df["qty_shortage"].astype(float).sum())


        zones_list = compute_group_summary(filtered_trips_df, group_cols)

        
        def clean_for_json(obj):
            import math
            if isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_for_json(v) for v in obj]
            elif obj is None:
                return ""        # convert None -> empty string
            elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return ""        # convert NaN or inf -> empty string
            return obj

        # Clean nested structure (zones_list)
        zones_list = clean_for_json(zones_list)
        # -------------------------------------------------------

        from fastapi.encoders import jsonable_encoder
        from fastapi.responses import JSONResponse


        response_data = {
            "status": "success",
            "filtered_invoice_count": filtered_invoice_count,
            "filtered_vehicle_count": filtered_vehicle_count,
            "zones": zones_list
        }

        return JSONResponse(content=jsonable_encoder(response_data))
    
    @staticmethod
    async def get_unblock_ageing(filters, cross_filters, drill_state, payload):
        try:
            # Cross filters
            _filters, daterange = await generate_cross_filter(cross_filters)
            current_date = datetime.now().strftime("%Y-%m-%d")
            closed_query = vts_query.vts_query.get("closed_alerts")
            
            # Updated shortage query - remove hardcoded conditions
            shortage_query = vts_query.vts_query.get("unblocked_tt_shortage")

            # Drill Down filters for closed_query
            closed_query = await get_drill_down_filter(filters, closed_query)

            access_filters = [
                dashboard_studio_model.WidgetFiltersCreate(**rec)
                for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)
            ]
            closed_query = await widget_actions.WidgetActions.apply_filter_drilldown(closed_query, access_filters, drill_state)

            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, shortage_query)
            shortage_query = VTSAnalyticsActions.apply_conditions_to_query(shortage_query, conditions)
            shortage_query += " GROUP BY vehicle_id"

            # Apply date condition to closed_query only (since shortage_query date is handled by build_filter_conditions)
            clause = "WHERE" if "where" not in closed_query.lower() else "AND"
            if daterange:
                closed_query += f" {clause} created_at BETWEEN {daterange}"
            else:
                closed_query += f" {clause} CAST(created_at AS DATE) = '{current_date}'"

            print("Final Shortage Query:", shortage_query)

            resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=closed_query, limit=0)
            shortage_resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=shortage_query, limit=0)
            
            df = pd.DataFrame(resp.get("data", []))
            df = await filter_data(df, _filters)
            shortage = pd.DataFrame(shortage_resp.get("data", []))

            df["vehicle_blocked_end_date"] = pd.to_datetime(df["vehicle_blocked_end_date"]).dt.tz_localize(None)
            df["vehicle_blocked_start_date"] = pd.to_datetime(df["vehicle_blocked_start_date"]).dt.tz_localize(None)

            df["ageing"] = (df["vehicle_blocked_end_date"] - df["vehicle_blocked_start_date"]).dt.days + 1
                        
            violation_counts = (
                df.pivot_table(
                    index=["sap_id", "zone", "tt_number"],
                    columns="violation_type",
                    values="location_name",
                    aggfunc="count",
                    fill_value=0
                )
            )
            avg_ageing = (
                df.groupby(["sap_id", "location_name", "transporter_code", "zone", "tt_number"])["ageing"]
                .mean()
                .reset_index()
            )
            df = (
                avg_ageing.merge(violation_counts, on=["sap_id", "tt_number"], how="left")
            )
            df.columns.name = None
            df["ageing"] = df["ageing"].round(2)
            df = pd.merge(df, shortage, on="tt_number", how="left")
            df = df.fillna(0)

            for col in [
                "continuous_driving_count", "device_tamper_count", "main_supply_removal_count",
                "night_driving_count", "route_deviation_count", "speed_violation_count",
                "stoppage_violations_count"
                ]:
                if col not in df.columns:
                    df[col] = 0
            df.rename(
                columns={"continuous_driving_count": "CD", "device_tamper_count": "DT",
                        "main_supply_removal_count": "PD", "night_driving_count": "ND",
                        "route_deviation_count": "RD", "speed_violation_count": "SV",
                        "stoppage_violations_count": "US"}, inplace=True)            

            if drill_state:
                group_by_keys = [drill_state]
                if filters:
                    filter_keys = [rec.key.strip('"') for rec in filters]
                    if "zone" in filter_keys and "location_name" not in filter_keys:
                        group_by_keys = ["zone", "location_name"]
                    elif "zone" in filter_keys and "location_name" in filter_keys and "transporter_code" not in filter_keys:
                        group_by_keys = ["zone", "location_name", "transporter_code"]
                    elif "zone" in filter_keys and "location_name" in filter_keys and "transporter_code" in filter_keys and "tt_number" not in filter_keys:
                        group_by_keys = ["zone", "location_name", "transporter_code", "tt_number"]

                df = df.groupby(group_by_keys, as_index=False).agg({
                                "CD": "sum", "DT": "sum", "PD": "sum",
                                "ND": "sum", "RD": "sum", "SV": "sum",
                                "US": "sum", "ageing": "mean", "shortage": "sum"})

            return {"status": True, "message": "success", "data": df.to_dict(orient='records')}
        except Exception as e:
            print("-- Exception in get unblock ageing widget --")
            print("traceback :", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
    
    async def get_emlock_open_data(filters, cross_filters, drill_state, payload):
        try:
            # Cross filters
            _filters, daterange = await generate_cross_filter(cross_filters)
            current_date = datetime.now().strftime("%Y-%m-%d")
            query = vts_query.vts_query.get("get_emlock_open_data")
            
            # Drill Down filters
            query = await get_drill_down_filter(filters, query)

            access_filters = [
                dashboard_studio_model.WidgetFiltersCreate(**rec)
                for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)
                ]
            query = await widget_actions.WidgetActions.apply_filter_drilldown(query, access_filters, drill_state)

            clause = "WHERE" if "where" not in query.lower() else "AND"
            if daterange:
                query += f" {clause} createdat BETWEEN {daterange}"
            else:
                query += f" {clause} CAST(createdat AS DATE) = '{current_date}'"
            
            print("Final Query for emlock open data:", query)

            resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=query, limit=0)
            df = pd.DataFrame(resp.get("data", []))

            if df.empty:
                return {"status": True, "message": "No data found", "data": []}
            
            df = await filter_data(df, _filters)

            if payload.get("search") == "true":
                return {'status': True, 'message': 'success', 'data': df.to_dict(orient='records')}
                        
            swipe_out_l1 = df[df['swipeoutl1'].fillna('').str.lower() == 'false']
            swipe_out_l2 = df[df['swipeoutl2'].fillna('').str.lower() == 'false']
            
            swipe_out_l1_count = len(swipe_out_l1)
            swipe_out_l2_count = len(swipe_out_l2)
            
            group_by_keys = ["zone"]
            if filters:
                filter_keys = [rec.key.strip('"') for rec in filters]
                if "zone" in filter_keys and "region" not in filter_keys:
                    group_by_keys = ["zone", "region"]
                elif "zone" in filter_keys and "region" in filter_keys and "location_name" not in filter_keys:
                    group_by_keys = ["zone", "region", "location_name"]
                elif "zone" in filter_keys and "region" in filter_keys and "location_name" in filter_keys and "trucknumber" not in filter_keys:
                    group_by_keys = ["zone", "region", "location_name", "trucknumber"]

            swipe_out_l1 = swipe_out_l1.groupby(group_by_keys, as_index=False).agg({
                "swipeoutl1": "count"
            })
            swipe_out_l2 = swipe_out_l2.groupby(group_by_keys, as_index=False).agg({
                "swipeoutl2": "count",
            })
            df = pd.concat([swipe_out_l1, swipe_out_l2])
            df = df.fillna(0)

            df = df.groupby(group_by_keys, as_index=False).agg({
                "swipeoutl1": "sum",
                "swipeoutl2": "sum"
            })

            return {
                "status": True, 
                "message": "success", 
                "swipe_out_l1_count": swipe_out_l1_count,
                "swipe_out_l2_count": swipe_out_l2_count,
                "data": df.to_dict(orient='records')
                }
        except Exception as e:
            print("-- Exception in zone wise productivity widget --")
            print("traceback :", traceback.format_exc())

    @staticmethod
    async def power_disconnection(filters, cross_filters, drill_state, payload):
        try:
            # Step 1: Get base query and apply filters
            query = vts_query.vts_query.get(drill_state.split(",")[0])
            if not query:
                return {"status": False, "message": "Query not found", "data": []}
            
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            final_query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)

            
            vts_df = await VTSAnalyticsActions.execute_query(final_query)
            vts_df = vts_df.drop_duplicates(subset=['invoice_number'], keep='first')
            
            if vts_df.empty:
                return {"status": True, "message": "No power disconnection alerts found", "data": []}

            print(vts_df)
            
            # Step 2: Get TLs and fetch alerts
            tl_numbers_list = vts_df['tl_number'].tolist()
            tl_numbers_str = "', '".join(map(str, tl_numbers_list))
            
            alerts_query = f"""
                SELECT DISTINCT location_name, vehicle_number, transporter_code
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
            
            merged_df["transporter_code"] = merged_df["transporter_code"].astype(str).apply(lambda x: x[2:] if x.startswith("00") else x)
            
            # Step 4: Merge transporter names
            email_query = """SELECT transporter_code, transporter_name FROM email_master"""
            df_email = await VTSAnalyticsActions.execute_query(email_query)
            final_df = merged_df.merge(df_email, on="transporter_code", how="left")
            final_df.drop(columns=["transporter_code"], inplace=True)
            
            # Step 5: Filter for power disconnection violations (>= 6)
            violation_type = "main_supply_removal_count"
            violation_filtered_df = final_df[final_df[violation_type].fillna(0) >= 6].copy()
            
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
                    return {"status": True, "message": f"No invoices found for vehicle {selected_tl}", "data": []}
                
                # Return invoice details sorted by created_at
                invoice_df = violation_filtered_df.sort_values(by="created_at", ascending=True)
                invoice_df = invoice_df[["invoice_number", "created_at", violation_type]]
                
                # Rename columns for frontend
                invoice_df.rename(columns={
                    "invoice_number": "invoice_no",
                    "created_at": "created_at"
                }, inplace=True)
                
                result = invoice_df.to_dict(orient="records")
                return {"status": True, "message": f"{violation_type} details for vehicle {selected_tl}", "data": result}
            
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
            # violation_count_more_than_6: Count of invoices where main_supply_removal_count >= 6
            # total_violations: Sum of actual main_supply_removal_count values
            summary_df = (
                violation_filtered_df.groupby(group_col)
                .agg({
                    "invoice_number": pd.Series.nunique,  # invoice_count
                    violation_type: ['count', 'sum']  # count of records >= 6, and sum of actual values
                })
                .reset_index()
            )
            
            # Flatten multi-level columns
            summary_df.columns = [group_col, 'invoice_count', 'violation_count_more_than_6', 'total_violations']
            
            if group_col != "tl_number":
                summary_df["vehicle_count"] = violation_filtered_df.groupby(group_col)["tl_number"].nunique().values
            
            result = summary_df.to_dict(orient="records")
            return {"status": True, "message": f"{violation_type} drill-down data", "data": result}
        
        except Exception as e:
            print("Exception in power_disconnection:", str(e))
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}
    

    @staticmethod
    async def risk_score(filters, cross_filters, drill_state, payload, limit=0, offset=0, batch_size=10000):
        """
        Fetch data from the specified risk score table.
        limit=0 means fetch all records
        """
        try:
            table_name = payload.get("table_name")
            columns = payload.get("columns")

            if not table_name:
                return {"status": False, "message": "table_name not provided in payload", "data": []}

            print(f"Fetching data from table: {table_name}")

            if columns and isinstance(columns, list) and columns:
                select_columns = ", ".join([f'"{col}"' for col in columns])
                base_query = f'SELECT {select_columns} FROM public."{table_name}"'
            else:
                base_query = f'SELECT * FROM public."{table_name}"'

            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, base_query)
            filtered_query = VTSAnalyticsActions.apply_conditions_to_query(base_query, conditions)

            # First, get the total count
            count_query = f"SELECT COUNT(*) as total FROM ({filtered_query}) as subquery"
            count_resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=count_query, limit=1)
            total_records = count_resp.get("data", [{}])[0].get("total", 0) if count_resp.get("data") else 0
            

            all_data = []
            current_offset = 0
            total_fetched = 0
            fetch_all = (limit == 0)
            target_limit = total_records if fetch_all else limit
            
            while total_fetched < target_limit:
                # Calculate batch size for this iteration
                remaining = target_limit - total_fetched
                this_limit = min(batch_size, remaining)

                # Construct query with LIMIT and OFFSET
                batch_query = f"{filtered_query} LIMIT {this_limit} OFFSET {current_offset}"
                
                # Execute batch query
                batch_resp = await urdhva_base.BasePostgresModel.get_aggr_data(
                    query=batch_query, 
                    limit=0  # Set to 0 to avoid double limiting
                )
                batch_data = batch_resp.get("data", [])
                
                if not batch_data:
                    print(f"No more data at offset {current_offset}")
                    break

                batch_rows = len(batch_data)
                all_data.extend(batch_data)
                total_fetched += batch_rows
                current_offset += batch_rows

                # If we got fewer records than requested, we've reached the end
                if batch_rows < this_limit:
                    break

            if not all_data:
                return {"status": True, "message": "No data found", "data": [], "count": 0}

            return {
                "status": True,
                "message": f"Successfully fetched {len(all_data)} records from {table_name}",
                "data": all_data,  # Include data if needed
                "count": len(all_data),
                "total_in_table": total_records
            }
        except Exception as e:
            print("Exception in risk_score:", str(e))
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}