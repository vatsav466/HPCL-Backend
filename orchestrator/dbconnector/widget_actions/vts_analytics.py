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
from fastapi.responses import StreamingResponse


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
        end = val.split(",")[1]
       
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
            return f"created_on BETWEEN '{start}' AND '{end}'"
                
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
        Main function to handle VTS violation queries with proper invoice-level shortage matching
        """
        try:
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

            async def get_shortage_data(tl_numbers_list=None, invoice_numbers_list=None):
                """
                Fetch shortage data from sales_trips_till_date
                Returns DataFrame with vehicle_id, invoice_no, qty_shortage, material_group_nm
                """
                where_conditions = []
                
                if tl_numbers_list:
                    tl_numbers_str = "', '".join(map(str, tl_numbers_list))
                    where_conditions.append(f"vehicle_id IN ('{tl_numbers_str}')")
                
                if invoice_numbers_list:
                    base_invoice_numbers = [extract_invoice_number(inv) for inv in invoice_numbers_list if extract_invoice_number(inv)]
                    base_invoice_numbers = list(set(base_invoice_numbers))
                    
                    if base_invoice_numbers:
                        invoice_numbers_str = "', '".join(map(str, base_invoice_numbers))
                        where_conditions.append(f"invoice_no IN ('{invoice_numbers_str}')")
                
                where_clause = " AND ".join(where_conditions)
                
                shortage_query = f"""
                    SELECT 
                        vehicle_id, 
                        invoice_no,
                        CASE 
                            WHEN qty_shortage = 'NaN' THEN '0.0'
                            WHEN qty_shortage IS NULL THEN '0.0'
                            ELSE qty_shortage 
                        END as qty_shortage,
                        material_group_nm
                    FROM sales_trips_till_date
                    WHERE 
                        sbu_cd = '7000'
                        AND division = '11'
                        AND load_status = '6'
                        AND (qty_shortage::numeric < 100)
                        AND (qty_shortage::numeric > 0 OR qty_shortage IS NULL)
                        AND {where_clause}
                """
                df_shortage = await VTSAnalyticsActions.execute_query(shortage_query)
                
                if df_shortage.empty:
                    return pd.DataFrame()
                
                # Convert qty_shortage to numeric, replacing errors with 0
                df_shortage['qty_shortage'] = pd.to_numeric(df_shortage['qty_shortage'], errors='coerce').fillna(0.0)
                
                # Filter out rows where qty_shortage is 0
                df_shortage = df_shortage[df_shortage['qty_shortage'] != 0]
                
                if df_shortage.empty:
                    return pd.DataFrame()
                
                df_shortage['invoice_match_key'] = df_shortage['invoice_no'].astype(str).str.strip()
                
                return df_shortage

            def merge_shortage_data(df, df_shortage, aggregate=True):
                """
                Merge shortage data with main dataframe
                If aggregate=True: sum qty_shortage by vehicle + invoice
                If aggregate=False: keep material_group_nm detail with comma-separated values
                """
                if 'invoice_number' not in df.columns:
                    if not aggregate:
                        df['qty_shortage_detail'] = ''
                    return df
                
                if df_shortage.empty:
                    if not aggregate:
                        df['qty_shortage_detail'] = ''
                    return df
                    
                df['invoice_match_key'] = df['invoice_number'].apply(extract_invoice_number)
                     
                if aggregate:
                    df_shortage_agg = df_shortage.groupby(
                        ['vehicle_id', 'invoice_match_key'], 
                        as_index=False
                    )['qty_shortage'].sum()
                    
                    df_merged = df.merge(
                        df_shortage_agg[['vehicle_id', 'invoice_match_key', 'qty_shortage']],
                        left_on=['tl_number', 'invoice_match_key'],
                        right_on=['vehicle_id', 'invoice_match_key'],
                        how='left'
                    )
                    
                    df_merged.drop(columns=['vehicle_id', 'invoice_match_key'], inplace=True, errors='ignore')
                    df_merged['qty_shortage'] = pd.to_numeric(df_merged['qty_shortage'], errors='coerce').fillna(0)
                    
                else:
                    df_shortage_detailed = df_shortage.groupby(
                        ['vehicle_id', 'invoice_match_key', 'material_group_nm'],
                        as_index=False
                    )['qty_shortage'].sum()
                    
                    def create_shortage_detail(group):
                        """Create formatted shortage detail string with only non-zero values"""
                        details = []
                        for _, row in group.iterrows():
                            shortage = float(row['qty_shortage'])
                            if shortage != 0:  # Only include non-zero shortages
                                mat_group = str(row['material_group_nm']).strip()
                                details.append(f"{mat_group}:{shortage}")
                        return ', '.join(details) if details else ''
                    
                    df_shortage_grouped = df_shortage_detailed.groupby(
                        ['vehicle_id', 'invoice_match_key']
                    ).apply(create_shortage_detail).reset_index(name='qty_shortage_detail')
                    
                    df_merged = df.merge(
                        df_shortage_grouped[['vehicle_id', 'invoice_match_key', 'qty_shortage_detail']],
                        left_on=['tl_number', 'invoice_match_key'],
                        right_on=['vehicle_id', 'invoice_match_key'],
                        how='left'
                    )
                    
                    df_merged.drop(columns=['vehicle_id', 'invoice_match_key'], inplace=True, errors='ignore')
                    df_merged['qty_shortage_detail'] = df_merged['qty_shortage_detail'].fillna('')
                
                return df_merged

            has_qty_shortage_filter = 'qty_shortage' in violation_types if violation_types else False
            vts_violation_types = [v for v in violation_types if v != 'qty_shortage'] if violation_types else []
            all_violations_with_shortage = all_violations + ['qty_shortage']

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
                
                df_view = df_view.drop_duplicates(subset=["invoice_number"], keep="first")
                
                if df_view.empty:
                    return {"status": True, "message": "No violation history found for this vehicle", "data": []}

                invoice_list = df_view['invoice_number'].unique().tolist()
                     
                df_shortage = await get_shortage_data(
                    tl_numbers_list=[truck_number],
                    invoice_numbers_list=invoice_list
                )
                
                               
                truck_query = f"""
                    SELECT DISTINCT truck_no, transporter_name
                    FROM vts_truck_master
                    WHERE truck_no = '{truck_number}'
                """
                df_truck = await VTSAnalyticsActions.execute_query(truck_query)
                
                if not df_truck.empty:
                    final_df = df_view.merge(df_truck, left_on="tl_number", right_on="truck_no", how="left")
                    final_df.drop(columns=['truck_no'], inplace=True, errors='ignore')
                else:
                    final_df = df_view.copy()
                    final_df['transporter_name'] = None
                
                final_df = merge_shortage_data(final_df, df_shortage, aggregate=False)
                
                
                if 'qty_shortage_detail' not in final_df.columns:
                    final_df['qty_shortage_detail'] = ''
                
                final_df['qty_shortage_detail'] = final_df['qty_shortage_detail'].fillna('')
                
                if final_df.empty:
                    return {"status": True, "message": "No non-zero violations found", "data": []}

                return {"status": True, "message": "success", "data": await safe_json(final_df)}

            
            if has_qty_shortage_filter and not vts_violation_types:
                shortage_query = """
                    SELECT 
                        vehicle_id AS tl_number, 
                        invoice_no AS invoice_number,
                        plant_nm AS location_name,
                        CASE 
                            WHEN qty_shortage = 'NaN' THEN '0.0'
                            WHEN qty_shortage IS NULL THEN '0.0'
                            ELSE qty_shortage 
                        END AS qty_shortage,
                        material_group_nm,
                        zone,
                        load_date AS created_at
                    FROM sales_trips_till_date
                    WHERE 
                        sbu_cd = '7000'
                        AND division = '11'
                        AND load_status = '6'
                        AND (qty_shortage::numeric < 100)
                        AND (qty_shortage::numeric > 0 OR qty_shortage IS NULL)
                """

                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, shortage_query)
                shortage_query = VTSAnalyticsActions.apply_conditions_to_query(shortage_query, conditions)
                df_shortage_all = await VTSAnalyticsActions.execute_query(shortage_query)

                if df_shortage_all.empty:
                    return {"status": True, "message": "No shortage data found", "data": []}

                df_shortage_all["qty_shortage"] = pd.to_numeric(df_shortage_all["qty_shortage"], errors="coerce").fillna(0.0)
                df_shortage_all = df_shortage_all[df_shortage_all["qty_shortage"] != 0]

                if df_shortage_all.empty:
                    return {"status": True, "message": "No non-zero shortage data found", "data": []}

                # Build violation filters
                tl_numbers_list = df_shortage_all["tl_number"].unique().tolist()
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
                        location_name,
                        zone,
                        {select_clause}
                    FROM vts_alert_history
                    WHERE tl_number IN ('{tl_numbers_str}')
                    AND invoice_number IS NOT NULL
                """

                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, history_query)
                history_query = VTSAnalyticsActions.apply_conditions_to_query(history_query, conditions)
                df_history = await VTSAnalyticsActions.execute_query(history_query)

                df_history = df_history.drop_duplicates(subset=["invoice_number"], keep="first")

                # Truck master
                truck_query = """
                    SELECT DISTINCT truck_no, transporter_name
                    FROM vts_truck_master
                """
                df_truck = await VTSAnalyticsActions.execute_query(truck_query)

                # Merge shortage + history
                merged_history = df_shortage_all.merge(
                    df_history,
                    on=["tl_number", "invoice_number"],
                    how="left"
                )

                # Merge truck info
                final_df = merged_history.merge(
                    df_truck,
                    left_on="tl_number",
                    right_on="truck_no",
                    how="left"
                )
                final_df.drop(columns=["truck_no"], inplace=True, errors="ignore")

                # Only positive shortages
                final_df = final_df[final_df["qty_shortage"] > 0]

                # Handle possible duplicates
                for base_col in ["zone", "location_name"]:
                    if f"{base_col}_x" in final_df.columns:
                        final_df[base_col] = final_df[f"{base_col}_x"]
                    elif f"{base_col}_y" in final_df.columns:
                        final_df[base_col] = final_df[f"{base_col}_y"]

                # Aggregate by invoice
                agg_df = (
                    final_df.groupby("invoice_number", as_index=False)
                    .agg({
                        "qty_shortage": "sum",
                        "zone": "first",
                        "location_name": "first",
                        "tl_number": "first",
                        "transporter_name": "first"
                    })
                )

                agg_df = agg_df[["invoice_number", "zone", "location_name", "tl_number", "qty_shortage","transporter_name"]]

                return {"status": True, "message": "success", "data": await safe_json(agg_df)}
        
            if violation_types:
                select_parts = [
                    f"COUNT(CASE WHEN {v_type} != 0 THEN invoice_number END) AS {v_type}"
                    for v_type in all_violations
                ]
                select_clause = ",\n           ".join(select_parts)
                
                if vts_violation_types:
                    having_parts = [
                        f"COUNT(CASE WHEN {v_type} != 0 THEN 1 END) > 0"
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
                
                df_history = df_history.drop_duplicates(subset=["invoice_number"], keep="first")

                if df_history.empty:
                    return {"status": True, "message": "No violations found", "data": []}

                tl_numbers_list = df_history['tl_number'].unique().tolist()
                
                df_shortage = await get_shortage_data(tl_numbers_list=tl_numbers_list)
                
                tl_numbers_str = "', '".join(map(str, tl_numbers_list))
                truck_query = f"""
                    SELECT DISTINCT truck_no, transporter_name
                    FROM vts_truck_master
                """
                df_truck = await VTSAnalyticsActions.execute_query(truck_query)

                final_df = df_history.merge(df_truck, left_on="tl_number", right_on="truck_no", how="left")
                final_df.drop(columns=['truck_no'], inplace=True, errors='ignore')
                
                final_df = merge_shortage_data(final_df, df_shortage, aggregate=True)

                if has_qty_shortage_filter:
                    final_df = final_df[final_df['qty_shortage'] > 0]

                if final_df.empty:
                    return {"status": True, "message": "No non-zero violations found", "data": []}

                return {"status": True, "message": "success", "data": await safe_json(final_df)}

            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
            query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)
            df_history = await VTSAnalyticsActions.execute_query(query)
            
            if df_history.empty:
                return {"status": True, "message": "No history data found", "data": []}

            if 'invoice_number' in df_history.columns:
                df_history = df_history.drop_duplicates(subset=["invoice_number"], keep="first")

            tl_numbers_list = df_history['tl_number'].unique().tolist()
            
            df_shortage = await get_shortage_data(tl_numbers_list=tl_numbers_list)
            
            tl_numbers_str = "', '".join(map(str, tl_numbers_list))
            truck_query = f"""
                SELECT DISTINCT truck_no, transporter_name
                FROM vts_truck_master
            """
            df_truck = await VTSAnalyticsActions.execute_query(truck_query)

            final_df = df_history.merge(df_truck, left_on="tl_number", right_on="truck_no", how="left")
            final_df.drop(columns=['truck_no'], inplace=True, errors='ignore')
            
            final_df = merge_shortage_data(final_df, df_shortage, aggregate=True)
            
            # ==================== HANDLE GROUP_BY ====================
            group_by_col = payload.get("group_by") if payload else None
            if group_by_col and group_by_col in final_df.columns:
                violation_cols = [v for v in all_violations if v in final_df.columns]
                violation_cols.append('qty_shortage')
            
                agg_df = final_df.groupby(group_by_col)[violation_cols].sum().reset_index()
                agg_df['total_count'] = agg_df[violation_cols].sum(axis=1)
                
                return {"status": True, "message": "success", "data": agg_df.to_dict(orient='records')}

            qlick_view = payload.get("qlick_view") if payload else None
            click_value = payload.get("click_value") if payload else None
            location_name = payload.get("location_name") if payload else None
            
            violation_cols = [v for v in all_violations if v in final_df.columns]
            violation_cols.append('qty_shortage')

            # ZONE VIEW (no click - show all zones)
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

            if final_df.empty:
                return {"status": True, "message": "No non-zero violations found", "data": []}

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
                plant_cd as sap_id, 
                vehicle_id, 
                invoice_no,
                SUM(qty_shortage::numeric) as qty_shortage 
            FROM sales_trips_till_date
            WHERE sbu_cd = '7000'
                AND division = '11'
                AND load_status = '6'
                AND (qty_shortage::numeric < 100)
                AND (qty_shortage::numeric > 0 OR qty_shortage IS NULL)
            GROUP BY vehicle_id, invoice_no, plant_cd 
            """
            
            conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, shortage_query)
            shortage_query = VTSAnalyticsActions.apply_conditions_to_query(shortage_query, conditions)

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
                print(query)
            else:
                conditions = VTSAnalyticsActions.build_filter_conditions(filters, cross_filters, query)
                query = VTSAnalyticsActions.apply_conditions_to_query(query, conditions)

            df = await VTSAnalyticsActions.execute_query(query)
            df.drop(columns=["zone"], inplace=True, errors="ignore")

            # Remove duplicate records
            df = df.drop_duplicates(
                subset=["event_start_datetime", "event_end_datetime", "tt_number", "invoice_no"],
                keep="first"
            )

            if df.empty:
                return {"status": True, "message": "No data found", "data": []}

            # Step 2: Get location info
            sap_id_list = df['sap_id'].tolist()
            tt_numbers_str = "', '".join(map(str, sap_id_list))

            location_query = f"""
                SELECT sap_id, name AS location_name, zone
                FROM location_master
                WHERE sap_id IN ('{tt_numbers_str}')
            """

            loc_df = await VTSAnalyticsActions.execute_query(location_query)
            if loc_df.empty:
                return {"status": False, "message": "No matching vehicle details found in alerts", "data": []}

            # Step 3: Merge data
            merged_df = df.merge(loc_df, on="sap_id", how="left")
            merged_df = merged_df.dropna(subset=["zone", "location_name"])

            if payload.get("search") == "true":
                merged_df = merged_df.dropna(axis=1, how="all")  
                merged_df = merged_df.loc[:, merged_df.astype(str).ne("").any()] 
                merged_df = merged_df.drop(["created_at","updated_at"], axis=1, errors='ignore')               
                return {"status": True, "message": "Data found", "data": merged_df.to_dict(orient="records")}

            # Step 4: Remove empty rows based on filters
            for key in ["zone", "location_name", "transporter_name"]:
                merged_df = merged_df[merged_df[key].notna() & (merged_df[key].astype(str).str.strip() != "")]
                if payload.get(key):
                    merged_df = merged_df[merged_df[key] == payload[key]]

            if merged_df.empty:
                return {"status": True, "message": "No data found for the applied filters", "data": []}

            # Step 5: TT-level drill-down
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

            # Step 6: Determine grouping column
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

            summary_df.rename(columns={"invoice_no": "invoice_count"}, inplace=True)
            result = summary_df.to_dict(orient="records")

            # Step 8: Handle Excel download
            if payload.get("download") == "true":
                # Remove timezone info
                for col in merged_df.select_dtypes(include=["datetime64[ns, UTC]", "datetimetz"]).columns:
                    merged_df[col] = merged_df[col].dt.tz_localize(None)

                # Drop completely empty columns
                merged_df = merged_df.drop(columns=['created_at', 'updated_at'])
                merged_df = merged_df.dropna(axis=1, how="all")
                merged_df = merged_df.loc[:, (merged_df.astype(str).apply(lambda x: x.str.strip() != "").any())]

                violation_mapping = {
                    "HS": "Hotspot",
                    "TC": "Trip not closed more than 2 hours",
                    "RD": "Route Deviation > 2km",
                    "WR": "Trip without route"
                }

                if "violation_type" in merged_df.columns:
                    merged_df["violation_type"] = merged_df["violation_type"].replace(violation_mapping)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"{ongoing_trips_type}_{timestamp}.xlsx"

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    merged_df.to_excel(writer, index=False, sheet_name='ongoing_trips')

                output.seek(0)
                headers = {
                    "Content-Disposition": f'attachment; filename="{file_name}"'
                }
                return StreamingResponse(
                    output,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers
                )

            return {"status": True, "message": f"{ongoing_trips_type} drill-down data", "data": result}

        except Exception as e:
            print("traceback:", traceback.format_exc())
            return {"status": False, "message": str(e), "data": []}


    @staticmethod
    async def safety_compliance(filters, cross_filters, drill_state, payload):                       
        try:
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
        import pandas as pd
        import pytz
        from datetime import datetime, timedelta

        # --- HELPER FUNCTION: Build SQL Conditions (Extended for bu, sap_id, zone) ---
        def build_sql_conditions_string(filter_list, table_alias='T'):
            conditions = []
            # Extended keys allowed for SQL pushdown in sales_trips_till_date
            # Assuming these columns exist in the table. Adjust column names if different.
            allowed_keys = ['zone_nm', 'plant_nm', 'vehicle_id', 'bu', 'sap_id', 'zone'] 
            
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
       
        trips_filters = filters  # All filters apply to trips
        
        # Extract Transporter Filter for later Pandas application (must be done post-merge)
        transporter_filter = next((f for f in trips_filters if getattr(f, 'key') == 'transporter_name'), None)
        
        # SQL conditions for trips (zone_nm, plant_nm, vehicle_id, bu, sap_id, zone)
        sql_trips_conditions = build_sql_conditions_string(trips_filters, table_alias='T')
        
        # Date condition from cross_filters
        date_condition_str = ""
        today = datetime.now().date()
        date_selection = next(
                    (getattr(f, "value", None) for f in cross_filters if getattr(f, "key", "").lower() == "date"), 
                    None
                )

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

       
        
        trips_query = f"""
            SELECT *     
            FROM 
                sales_trips_till_date T
            WHERE 
                sbu_cd = '7000'
                AND division = '11'
                AND load_status = '6'
                AND (qty_shortage::numeric < 100)
                AND (qty_shortage::numeric > 0 OR qty_shortage IS NULL)
                {sql_trips_conditions}
                {date_condition_str};

        """

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

            # --- Normalize both columns for merge ---
            trips_df['carrier_no'] = trips_df['carrier_no'].astype(str).str.strip()
            email_df['transporter_code'] = email_df['transporter_code'].astype(str).str.strip()

            # Remove leading 00 from both for matching
            trips_df['carrier_no'] = trips_df['carrier_no'].str.replace(r'^00', '', regex=True)
            email_df['transporter_code'] = email_df['transporter_code'].str.replace(r'^00', '', regex=True)

            # --- Merge on carrier_no <-> transporter_code ---
            trips_df = trips_df.merge(
                email_df,
                how='left',
                left_on='carrier_no',
                right_on='transporter_code'
            )

            # --- Debug export for missing transporter_name ---
            # trips_df.to_csv('/Users/algofusion/Downloads/missing_transporters.csv', index=False)

        # ----- 5. Filter valid trips (Original Logic) -----
        
        trips_df['qty_shortage'] = pd.to_numeric(trips_df['qty_shortage'], errors='coerce')
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
        
        # filtered_invoice_count = filtered_trips_df['invoice_no'].nunique()
        filtered_vehicle_count = filtered_trips_df['vehicle_id'].nunique()
        filtered_invoice_count = len(filtered_trips_df['invoice_no'])
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
                item["shortage"] = group["qty_shortage"].sum()
                # item["invoice_count"] = group["invoice_no"].nunique()
                # item["vehicle_count"] = group["vehicle_id"].nunique()
                item["invoice_count"] = len(group["invoice_no"])
                # print('item["invoice_count"]', item["invoice_count"])
                item["vehicle_count"] = group["vehicle_id"].nunique()         # unique vehicles

                # print('item["vehicle_count"]', item["vehicle_count"])

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

        zones_list = compute_group_summary(filtered_trips_df, group_cols)

        return {
            "status": "success",
            "filtered_invoice_count": filtered_invoice_count,
            "filtered_vehicle_count": filtered_vehicle_count,
            "zones": zones_list
        }
    

    
    async def get_unblock_ageing(filters, cross_filters, drill_state, payload):
        try:
            # Cross filters
            _filters, daterange = await generate_cross_filter(cross_filters)
            current_date = datetime.now().strftime("%Y-%m-%d")
            closed_query = vts_query.vts_query.get("closed_alerts")
            
            shortage = vts_query.vts_query.get("unblocked_tt_shortage")

            # Drill Down filters
            closed_query = await get_drill_down_filter(filters, closed_query)

            access_filters = [
                dashboard_studio_model.WidgetFiltersCreate(**rec)
                for rec in await hpcl_ceg_model.LpgOperationsSummary.get_clause_conditions(formated=True)
                ]
            closed_query = await widget_actions.WidgetActions.apply_filter_drilldown(closed_query, access_filters, drill_state)

            clause = "WHERE" if "where" not in closed_query.lower() else "AND"
            if daterange:
                closed_query += f" {clause} created_at BETWEEN {daterange}"
                shortage += f" {clause} load_date BETWEEN {daterange}"
            else:
                closed_query += f" {clause} CAST(created_at AS DATE) = '{current_date}'"
                shortage += f" {clause} CAST(load_date AS DATE) = '{current_date}'"

            shortage += " GROUP BY vehicle_id"

            resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=closed_query, limit=0)
            shortage = await urdhva_base.BasePostgresModel.get_aggr_data(query=shortage, limit=0)
            
            df = pd.DataFrame(resp.get("data", []))
            df = await filter_data(df, _filters)
            shortage = pd.DataFrame(shortage.get("data", []))

            shortage.rename(columns={"vehicle_number": "tt_number"}, inplace=True)

            df["vehicle_unblocked_date"] = pd.to_datetime(df["vehicle_unblocked_date"]).dt.tz_localize(None)
            df["vehicle_blocked_start_date"] = pd.to_datetime(df["vehicle_blocked_start_date"]).dt.tz_localize(None)

            df["ageing"] = (df["vehicle_unblocked_date"] - df["vehicle_blocked_start_date"]).dt.days + 1
                        
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
            df = pd.merge(df, shortage, on=["tt_number"], how="left")
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