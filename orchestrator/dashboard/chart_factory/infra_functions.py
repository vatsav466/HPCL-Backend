from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import urdhva_base
import json
import os
import polars as pl
import uuid
import typing
import importlib
import traceback
import math
import locale
import utilities.helpers
import re
from decimal import Decimal
from datetime import datetime, timedelta
from fastapi.responses import FileResponse, JSONResponse
from orchestrator.dbconnector.widget_actions import widget_actions


async def sod_infra(filters, cross_filters, drill_state, limit, time_grain):
    try:
        sod_query = ''' * from sod_infra '''
        lpg_query = ''' * from lpg_infra '''

        if filters:
            sod_query = await widget_actions.WidgetActions.apply_filter_drilldown(sod_query, filters, drill_state)
            lpg_query = await widget_actions.WidgetActions.apply_filter_drilldown(lpg_query, filters, drill_state)

        sod_result = await urdhva_base.BasePostgresModel.get_aggr_data(sod_query, limit=0, skip=0)
        sod = sod_result['data']
        lpg_result = await urdhva_base.BasePostgresModel.get_aggr_data(lpg_query, limit=0, skip=0)
        lpg = lpg_result['data']

        # company_color_map = {
        #     'hpcl': '#1E90FF',  # Dodger Blue
        #     'iocl': '#FF4500',  # Orange Red
        #     'bpcl': '#32CD32',  # Lime Green
        #     'hmel': '#8A2BE2'   # Blue Violet
        # }

        company_color_map = {
            'hpcl': '#00006B',
            'iocl': '#FC4C02',
            'bpcl': '#FFE000',
            'hmel': '#00A651'
        }

        exclude_keys = {"filename", "updated_by", "id", "created_at", "updated_at", "entity_id"}

        # Add color_code and filter keys for SOD
        for i in range(len(sod)):
            company = sod[i].get('company', '').lower()
            sod[i]['color_code'] = company_color_map.get(company, '#CCCCCC')
            sod[i] = {k: v for k, v in sod[i].items() if k not in exclude_keys}

        # Add color_code and filter keys for LPG
        for i in range(len(lpg)):
            company = lpg[i].get('company', '').lower()
            lpg[i]['color_code'] = company_color_map.get(company, '#CCCCCC')
            lpg[i] = {k: v for k, v in lpg[i].items() if k not in exclude_keys}

        return {"status": True, "message": "success", "data": sod + lpg}

    except Exception as e:
        print(f"Error while fetching SOD/LPG data: {e}")
        return {"error": str(e)}



async def get_count_company_info(filters, cross_filters, drill_state, limit, time_grain):
    try:
        combined_query = '''
             company, COUNT(*) as count 
            FROM (
                SELECT sbu,company,zone,state,district,location_name FROM sod_infra
                UNION ALL
                SELECT sbu,company,zone,state,district,location_name FROM lpg_infra
            ) AS combined
            GROUP BY company
        '''

        if filters:
            combined_query = await widget_actions.WidgetActions.apply_filter_drilldown(combined_query, filters, drill_state)

        result = await urdhva_base.BasePostgresModel.get_aggr_data(combined_query, limit=0, skip=0)
        data = result['data']

        return {"status": True, "message": "success", "data": data}
    except Exception as e:
        print(f"Error while fetching combined SOD/LPG data: {e}")
        return {"status": False, "error": str(e)}


async def get_sod_lpg_info(filters, cross_filters, drill_state, limit, time_grain):
    try:
        sod_query = ''' sap_id, sbu, location_name, company, ms, sko, hsd, total, mode_of_receipt from sod_infra '''
        lpg_query = ''' sap_id, sbu, location_name, company, installed_bottling_capacity, operating_bottling_capacity, ccoe_tankage, mode, supply from lpg_infra '''

        if filters:
            sod_query = await widget_actions.WidgetActions.apply_filter_drilldown(sod_query, filters, drill_state)
            lpg_query = await widget_actions.WidgetActions.apply_filter_drilldown(lpg_query, filters, drill_state)

        sod_result = await urdhva_base.BasePostgresModel.get_aggr_data(sod_query, limit=0, skip=0)
        sod = sod_result['data']
        lpg_result = await urdhva_base.BasePostgresModel.get_aggr_data(lpg_query, limit=0, skip=0)
        lpg = lpg_result['data']

        data = sod + lpg
        return {"status": True, "message": "success", "data": data}

    except Exception as e:
        print(f"Error while fetching SOD/LPG data: {e}")
        return {"error": str(e)}


async def get_distinct_sod_lpg_info(sbu: str = "", zone=None, state=None, district=None, company=None, location_name=None):
    try:

        query = '''
            SELECT DISTINCT sbu, zone, state, district, company, location_name
            FROM (
                SELECT sbu, zone, state, district, company, location_name FROM sod_infra
                UNION
                SELECT sbu, zone, state, district, company, location_name FROM lpg_infra
            ) AS combined_infra
        '''

        conditions = []

        if sbu:
            conditions.append(f"sbu = '{sbu}'")
        if zone:
            zone_str = "', '".join(zone)
            conditions.append(f"zone IN ('{zone_str}')")
        if state:
            state_str = "', '".join(state)
            conditions.append(f"state IN ('{state_str}')")
        if district:
            district_str = "', '".join(district)
            conditions.append(f"district IN ('{district_str}')")
        if company:
            company_str = "', '".join(company)
            conditions.append(f"company IN ('{company_str}')")
        if location_name:
            location_str = "', '".join(location_name)
            conditions.append(f"location_name IN ('{location_str}')")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0, skip=0)
        rows = result.get("data", [])

        sbu_set =set()
        zone_set = set()
        state_set = set()
        district_set = set()
        company_set = set()
        location_name_set = set()

        for row in rows:
            if row.get("sbu") and row["sbu"].strip():
                sbu_set.add(row["sbu"].strip())
            if row.get("zone") and row["zone"].strip():
                zone_set.add(row["zone"].strip())
            if row.get("state") and row["state"].strip():
                state_set.add(row["state"].strip())
            if row.get("district") and row["district"].strip():
                district_set.add(row["district"].strip())
            if row.get("company") and row["company"].strip():
                company_set.add(row["company"].strip())
            if row.get("location_name") and row["location_name"].strip():
                location_name_set.add(row["location_name"].strip())

        return {"status": True, "message": "success",
            "data": {
                "sbu": sorted(sbu_set),
                "company": sorted(company_set),
                "zone": sorted(zone_set),
                "state": sorted(state_set),
                "district": sorted(district_set),
                "location_name": sorted(location_name_set)
            }
        }
    except Exception as e:
        print(f"Error while fetching SOD/LPG data: {e}")
        return {"error": str(e)}

async def get_download_template_info(sbu):
    try:
        download_path = urdhva_base.settings.download_path
        downloadpath = os.path.join(download_path)
        template_file_path = os.path.join(download_path, f"{sbu}_Infra_template.xlsx")
        source_file = os.path.join(downloadpath, f"{sbu}_Infra.xlsx")

        if not os.path.exists(source_file):
            return JSONResponse(status_code=404,
                                content={"detail": f"Source CSV for '{sbu}' not found at {source_file}"})

        df = pl.read_excel(source_file)
        template_df = pl.DataFrame({col: [] for col in df.columns})
        # template_df.write_excel(template_file_path, sheet_name=f"{sbu}")
        temp = template_df.to_pandas()
        temp.to_excel(template_file_path, index=False, sheet_name=f"{sbu}")

        return FileResponse(path=template_file_path, media_type="application/octet-stream",
                            filename=f"{sbu}_template.xlsx")

    except Exception as e:
        print(f"Error generating template for {sbu}: {e}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})