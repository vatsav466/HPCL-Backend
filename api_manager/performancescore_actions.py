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
        fixed_columns = [
            "Sr No", "SAP ID", "Name", "Zone", "Region", "Score", "Rank",
            "Cyl. Rejections (Check Scale, Valve Leak & O Ring Leak)",
            "Productivity (Cyl/hr)",
            "Production (MT)",
            "LPG Production interruption (Hrs)",
            "Video Analytics",
            "VTS"
        ]

        temp_result = sorted(sap_scores.values(), key=lambda x: -x['overall'])
        df_rows = []
        rank = 1
        prev_score = None
        # print("temp_result: ",temp_result)
        for i, rec in enumerate(temp_result):
            current_score = rec['overall'] 
            if prev_score is not None and current_score < prev_score:
                rank = i + 1
            prev_score = current_score

            df_rows.append({
                "Sr No": i + 1,
                "SAP ID": rec['sap_id'],
                "Name": rec['name'],
                "Zone": rec['zone'],
                "Region": rec['region'],
                "Score": rec['overall'],
                "Rank": rank,
                "Cyl. Rejections (Check Scale, Valve Leak & O Ring Leak)": rec['category_scores'].get("PQ Rejection", {}).get('oi_score', 0),
                "Productivity (Cyl/hr)": rec['category_scores'].get("Productivity", {}).get('oi_score', 0),
                "Production (MT)": rec['category_scores'].get("Production", {}).get('oi_score', 0),
                "LPG Production interruption (Hrs)": rec['category_scores'].get("LPG Breakdown", {}).get('oi_score', 0),
                "Video Analytics": rec['category_scores'].get("VA", {}).get('oi_score', 0),
                "VTS": rec['category_scores'].get("VTS", {}).get('oi_score', 0),
            })

        # --- 3. Save Excel with 3-Row Header (Manual Writing - IMPLEMENTING FORMATTING) ---
        # output_dir = "/Users/algofusion/Downloads"
        output_dir = "/opt/downloads"
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
        
        # --- Column Mappings (Used to determine where to write scores and weightages) ---
        param_cols = {
            "Cyl. Rejections (Check Scale, Valve Leak & O Ring Leak)": {"col_idx": 7, "cat_key": "PQ Rejection"},
            "Productivity (Cyl/hr)": {"col_idx": 8, "cat_key": "Productivity"},
            "Production (MT)": {"col_idx": 9, "cat_key": "Production"},
            "LPG Production interruption (Hrs)": {"col_idx": 10, "cat_key": "LPG Breakdown"},
            "Video Analytics": {"col_idx": 11, "cat_key": "VA"},
            "VTS": {"col_idx": 12, "cat_key": "VTS"},
        }
        last_col_index = len(fixed_columns) - 1 
        
        # --- Row 1 (index 0): Merged Header ---
        worksheet.merge_range(0, 7, 0, last_col_index, 'Parameter wise Scores', merge_orange_format)
        
        # Merge the first 7 columns across all three header rows (Rows 1-3)
        for col_num in range(7):
            worksheet.merge_range(0, col_num, 2, col_num, fixed_columns[col_num], merge_orange_format)
            
        # --- Row 2 (index 1): Main Headers (Full Names) with Filters ---
        # The main headers for parameter scores start at column 7 and are written in Row 2 (index 1)
        for header, info in param_cols.items():
            col_num = info["col_idx"]
            worksheet.write(1, col_num, header, orange_format)
            
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
