from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import pandas as pd 
from orchestrator.dbconnector.widget_actions import widget_actions
import traceback
from orchestrator.analytics.performance_index import tas_performance_index
from orchestrator.analytics.performance_index import lpg_performance_index
import pandas as pd
from datetime import datetime
from fastapi.responses import FileResponse, JSONResponse
# Import required libraries
import pandas as pd
import os
import fastapi
from starlette.responses import FileResponse
import xlsxwriter # Required for manual formatting
# Assuming PerformanceScore, PerformanceScoreHistory, and widget_actions are imported elsewhere.
# NOTE: Ensure these imports are available in your environment for the code to run
# from your_models import PerformanceScore, PerformanceScoreHistory 
# from your_actions import widget_actions 


router = fastapi.APIRouter(prefix='/performancescore')


# Action get_pi_score
@router.post('/get_pi_score', tags=['PerformanceScore'])
async def performancescore_get_pi_score(data: Performancescore_Get_Pi_ScoreParams):
    ...


# Action download_performance_score
@router.post('/download_performance_score', tags=['PerformanceScore'])
async def performancescore_download_performance_score(data: Performancescore_Download_Performance_ScoreParams,background_tasks: fastapi.BackgroundTasks):
    try:
        def safe_float(x):
            try:
                return float(x)
            except Exception:
                return 0.0

        # Build filter clause
        clause = ""
        if data.filters:
            resp = await widget_actions.WidgetActions().generate_filter_clause(data.filters)
            clause = f" AND {resp}" if resp else ""

        # Only support TAS and LPG
        if data.bu not in ["TAS", "LPG"]:
            return {"status": "error", "message": f"BU '{data.bu}' not supported for download."}

        location_str = f" AND sap_id='{data.sap_id}'" if getattr(data, "sap_id", None) else ""
        table = "performance_score" if data.filters and any(f.value == "t" for f in data.filters) else "performance_score_history"

        # Fetch data
        query = f"SELECT * FROM {table} WHERE bu='{data.bu}' {location_str} {clause}"
        model = PerformanceScore if table == "performance_score" else PerformanceScoreHistory
        score_data = await model.get_aggr_data(query, limit=0)
        print('query: ',query)
        rows = score_data.get("data", [])

        if not rows:
            return {"status": "error", "message": "No data found."}

        # ----- Aggregate SAP scores (YOUR ORIGINAL LOGIC) -----
        sap_scores = {}
        for rec in rows:
            sid = rec.get('sap_id')
            if not sid:
                continue

            if sid not in sap_scores:
                sap_scores[sid] = {
                    'sap_id': sid,
                    'name': rec.get('name'),
                    'zone': rec.get('zone'),
                    'region': rec.get('region'),
                    'total_scores': [],
                    'category_scores': {}
                }

            sap_scores[sid]['total_scores'].append(safe_float(rec.get('score', 0)))

            for cat in rec.get('category', []):
                cat_name = cat.get('name')
                if not cat_name:
                    continue
                sap_scores[sid]['category_scores'].setdefault(cat_name, []).append({
                    'score': safe_float(cat.get('score', 0)),
                    'weightage': safe_float(cat.get('weightage', 0))
                })

        # ----- Compute final scores and extract weightages for header -----
        category_weightages = {} # <-- Initialized for header row extraction
        for details in sap_scores.values():
            # Category scores
            final_cat_scores = {}
            for cat, scores in details['category_scores'].items():
                if scores:
                    final_cat_scores[cat] = {
                        'oi_score': round(sum(s['score'] for s in scores) / len(scores), 2),
                        'weightage': round(sum(s['weightage'] for s in scores) / len(scores), 2)
                    }
                    # Capture the weightage for the header row
                    if cat not in category_weightages:
                        category_weightages[cat] = final_cat_scores[cat]['weightage']
                        
            details['category_scores'] = final_cat_scores

            # Overall score
            total_scores = details['total_scores']
            details['overall'] = round(sum(total_scores) / len(total_scores), 2) if total_scores else 0

        # ----- 2. Prepare Excel rows (YOUR ORIGINAL LOGIC) -----
        bu_columns = []
        if data.bu == "TAS":
            bu_columns = ['Safety Interlocks', 'Gantry Interlocks', 'Process Interlocks',
                          'Water Quantity', 'Foam Quantity', 'Fire Engines In Auto Mode',
                          'Hydrant Line', 'Dryouts and Carry forward', 'EMLOCK']
        elif data.bu == "LPG":
            bu_columns = ["Cyl. Rejections (Check Scale, Valve Leak & O Ring Leak)",
                "Productivity (Cyl/hr)",
                "Production (MT)",
                "LPG Production interruption (Hrs)"]
        common_columns = ["Video Analytics", "VTS"]
        # base_columns = ["Sr No", "SAP ID", "Name", "Zone", "Region", "Score", "Rank"]
        base_columns = ["Sr No", "SAP ID", "Name", "Zone", "Region", "Score", "Rank", "Zonal Average","All India Average"]

        fixed_columns = base_columns + bu_columns + common_columns

        temp_result = sorted(sap_scores.values(), key=lambda x: -x['overall'])
        # Calculate All India Average (average of all plant overall scores)
        all_india_average = round(
            sum(rec['overall'] for rec in temp_result) / len(temp_result), 2
        )
        df_rows = []
        zone_map = {}    # zone → list of scores
        for rec in temp_result:
            zone = rec['zone']
            score = rec['overall']
            zone_map.setdefault(zone, []).append(score)

        zone_avg = {z: round(sum(vals) / len(vals), 2) for z, vals in zone_map.items()}
        rank = 1
        prev_score = None
        # print("temp_result: ",temp_result)

        # Fetching Score record key
        def get_score(rec, key):
            data = rec.get('category_scores', {}).get(key)
            if not data:
                return 0
            if isinstance(data, list):
                return data[0].get('oi_score', 0)
            return data.get('oi_score', 0)

        for i, rec in enumerate(temp_result):
            current_score = rec['overall'] 
            if prev_score is not None and current_score < prev_score:
                rank = rank + 1
            prev_score = current_score
            
            def get_bu_data(bu, rec):
                data = {
                    "Sr No": i + 1,
                    "SAP ID": rec['sap_id'],
                    "Name": rec['name'],
                    "Zone": rec['zone'],
                    "Region": rec['region'],
                    "Score": rec['overall'],
                    "Rank": rank,
                    "Zonal Average": zone_avg.get(rec['zone'], 0),
                    "All India Average": all_india_average,
                    "Video Analytics": get_score(rec, "VA"),
                    "VTS": get_score(rec, "VTS")
                }
                if bu == 'LPG':
                    data.update({"Cyl. Rejections (Check Scale, Valve Leak & O Ring Leak)": get_score(rec, "PQ Rejection"),
                    "Productivity (Cyl/hr)": get_score(rec, "Productivity"),
                    "Production (MT)": get_score(rec, "Production"),
                    "LPG Production interruption (Hrs)": get_score(rec, "LPG Breakdown")})
                elif bu == 'TAS':
                    for key, name in {'Safety_Interlocks': 'Safety Interlocks',
                                      'Gantry_Interlocks': 'Gantry Interlocks',
                                      'Process_Interlocks': 'Process Interlocks',
                                      'Water_Quantity': 'Water Quantity',
                                      'Foam_Quantity': 'Foam Quantity',
                                      'Fire_Engines_In_Auto_Mode': 'Fire Engines In Auto Mode',
                                      'Hydrant_Line': 'Hydrant Line', 'EMLOCK': 'EMLOCK',
                                      'Dryouts and Carry forward': 'Dryouts and Carry forward'}.items():
                        data.update({name: get_score(rec, key)})
                return data

            df_rows.append(get_bu_data(data.bu , rec))

        # --- 3. Save Excel with 3-Row Header (Manual Writing - IMPLEMENTING FORMATTING) ---
        # output_dir = "/Users/algofusion/Downloads"
        output_dir = "/opt/downloads"
        # output_dir = "/Users/algofusion/downloads"
        os.makedirs(output_dir, exist_ok=True)
        template_file_path = os.path.join(output_dir, f"Updated_{data.bu}_infra_data.xlsx")
        
        # Initialize ExcelWriter with xlsxwriter engine
        writer = pd.ExcelWriter(template_file_path, engine='xlsxwriter')
        sheet_name = data.bu
        
        workbook = writer.book
        worksheet = workbook.add_worksheet(sheet_name) 

        # --- Define Formats ---
        orange_format = workbook.add_format({
            'bold': True, 'text_wrap': True, 'align': 'center', 'valign': 'vcenter',
            'fg_color': '#f5cba2', 'border': 1
        })
        
        merge_orange_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 
            'fg_color': '#f5cba2', 'border': 1
        })

        # Format for the weightage row (Row 3)
        weightage_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 
            'fg_color': '#f5cba2', 'font_color': '#800080', 'border': 1 
        })
        
        data_format = workbook.add_format({'align': 'center', 'valign': 'vcenter'})

        param_cols = {}
        # --- Column Mappings (Used to determine where to write scores and weightages) ---
        if data.bu == 'TAS':
            start_num = 8
            for key, name in {'Safety_Interlocks': 'Safety Interlocks',
             'Gantry_Interlocks': 'Gantry Interlocks',
             'Process_Interlocks': 'Process Interlocks',
             'Water_Quantity': 'Water Quantity',
             'Foam_Quantity': 'Foam Quantity',
             'Fire_Engines_In_Auto_Mode': 'Fire Engines In Auto Mode',
             'Hydrant_Line': 'Hydrant Line', 'EMLOCK': 'EMLOCK',
             'Dryouts and Carry forward': 'Dryouts and Carry forward',
                              "VA": "Video Analytics", "VTS": "VTS" }.items():
                param_cols.update({name: {"col_idx": start_num, "cat_key": key}})
                start_num += 1
        elif data.bu == 'LPG':
            param_cols = {
                "Cyl. Rejections (Check Scale, Valve Leak & O Ring Leak)": {"col_idx": 9, "cat_key": "PQ Rejection"},
                "Productivity (Cyl/hr)": {"col_idx": 10, "cat_key": "Productivity"},
                "Production (MT)": {"col_idx": 11, "cat_key": "Production"},
                "LPG Production interruption (Hrs)": {"col_idx": 12, "cat_key": "LPG Breakdown"},
                "Video Analytics": {"col_idx": 13, "cat_key": "VA"},
                "VTS": {"col_idx": 14, "cat_key": "VTS"},
            }
        last_col_index = len(fixed_columns) - 1 
        
        # --- Row 1 (index 0): Merged Header ---
        worksheet.merge_range(0, 9, 0, last_col_index, 'Parameter wise Scores', merge_orange_format)
        
        # Merge the first 7 columns across all three header rows (Rows 1-3)
        for col_num in range(9):
            worksheet.merge_range(0, col_num, 2, col_num, fixed_columns[col_num], merge_orange_format)
        for col_num, col_name in enumerate(base_columns):
            worksheet.write(1, col_num, col_name, orange_format)

        for header, info in param_cols.items():
            col_num = info["col_idx"]
            worksheet.write(1, col_num, header, orange_format)
            
        # --- Row 2 (index 1): Main Headers (Full Names) with Filters ---
        # The main headers for parameter scores start at column 7 and are written in Row 2 (index 1)
        
            
        # --- Row 3 (index 2): Weightages ---
        # Write parameter weightage numbers on Row 3
        for header, info in param_cols.items():
            col_num = info["col_idx"]
            cat_key = info["cat_key"]
            weightage = category_weightages.get(cat_key, 0)
            
            # Format weightage as integer if it's a whole number
            formatted_weightage = int(weightage) if weightage == round(weightage) else weightage
            
            worksheet.write(2, col_num, formatted_weightage, weightage_format)
            
        # --- Row 4 (index 3): Data Body (All Records) ---
        row_num = 3 # Start writing data at row index 3 (Row 4 in Excel)
        ordered_keys = fixed_columns 
        
        # This loop iterates over ALL aggregated records (df_rows)
        for row_data in df_rows:
            for col_num, key in enumerate(ordered_keys):
                value = row_data.get(key, 0)
                worksheet.write(row_num, col_num, value, data_format)
            
            row_num += 1 # Increment row for the next record

        # --- APPLY AUTOFILTER ---
        # Apply filter to the main data header row (Row 2/index 1).
        worksheet.autofilter(1, 0, 1, last_col_index) 
        
        # --- Auto-adjust column widths ---
        for i, col in enumerate(fixed_columns):
            width = 15
            if i in [2, 7]: # Name and the long Rejections header need more width
                width = 25
            worksheet.set_column(i, i, width)

        
        # Close the Pandas Excel writer and output the Excel file.
        writer.close()

        # Schedule deletion after response
        background_tasks.add_task(lambda path=template_file_path: os.remove(path))

        return FileResponse(
            path=template_file_path,
            media_type="application/octet-stream",
            filename=f"Updated_{data.bu}_infra_data.xlsx"
        )

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {"status": "error", "message": str(e)}
