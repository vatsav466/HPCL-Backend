from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import urdhva_base
import json
import os
import polars as pl
import pandas as pd
import uuid
import typing
import importlib
import traceback
import math
import locale
import utilities.helpers
import re
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from fastapi.responses import FileResponse, JSONResponse
from orchestrator.dbconnector.widget_actions import widget_actions


async def sod_infra(filters, cross_filters, drill_state, limit, time_grain):
    try:
        sbu_configs = [
            {
                "name": "SOD",
                "table": "sod_infra",
                "rename_map": {"ms": "MS (KL)", "sko": "SKO (KL)", "hsd": "HSD (KL)", "total": "TOTAL (KL)"}
            },
            {
                "name": "LPG",
                "table": "lpg_infra",
                "rename_map": {
                    "installed_bottling_capacity": "INSTALLED BOTTLING CAPACITY (TMTPA)",
                    "operating_bottling_capacity": "OPERATING BOTTLING CAPACITY (TMTPA)",
                    "ccoe_tankage": "CCOE TANKAGE (TMT)"
                }
            },
            {
                "name": "AVIATION",
                "table": "aviation_infra",
                "rename_map": {}
            },
            {
                "name": "LUBES",
                "table": "lubes_infra",
                "rename_map": {"base_oil_tankages": "BASE OIL TANKAGES (KL)"}
            }
        ]

        company_color_map = {
            'hpcl': '#00006B',
            'iocl': '#FC4C02',
            'bpcl': '#FFE000',
            'hmel': '#00A651'
        }

        exclude_keys = {"filename", "updated_by", "id", "created_at", "updated_at", "entity_id"}
        lpg_only_columns = {"time_of_commissioning"}
        all_data = []
        for sbu in sbu_configs:
            query = f'''SELECT * FROM {sbu["table"]}'''
            applied_filters = []
            if filters:
                for f in filters:
                    key_name = getattr(f, "key", None)
                    if not key_name:
                        continue

                    # Skip LPG-only filter if not in LPG table
                    if key_name.lower() in lpg_only_columns and sbu["name"] != "LPG":
                        continue

                    applied_filters.append(f)

                if applied_filters:
                    query = await widget_actions.WidgetActions.apply_filter_drilldown(
                        query, applied_filters, drill_state
                    )

            result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0, skip=0)
            records = result.get("data", [])

            rename_map_lower = {k.lower(): v for k, v in sbu.get("rename_map", {}).items()}

            for i in range(len(records)):
                company = records[i].get('company', '').lower()
                records[i]['color_code'] = company_color_map.get(company, '#CCCCCC')
                records[i] = {k: v for k, v in records[i].items() if k not in exclude_keys}
                if rename_map_lower:
                    records[i] = {
                        rename_map_lower.get(k.lower(), k): v for k, v in records[i].items()
                    }

            all_data.extend(records)

        return {"status": True, "message": "success", "data": all_data}

    except Exception as e:
        logging.exception("Error while fetching SBU infra data")
        return {"error": str(e)}



async def get_count_company_info(filters, cross_filters, drill_state, limit, time_grain):
    try:
        sbu_tables = ["sod_infra", "lpg_infra", "aviation_infra", "lubes_infra"]

        select_columns = "sbu, company, zone, state, district, location_name"
        union_queries = [f"SELECT {select_columns} FROM {table}" for table in sbu_tables]
        combined_subquery = "\nUNION ALL\n".join(union_queries)

        combined_query = f'''
             company, COUNT(*) as count 
            FROM (
                {combined_subquery}
            ) AS combined
            GROUP BY company
        '''

        if filters:
            combined_query = await widget_actions.WidgetActions.apply_filter_drilldown(combined_query, filters, drill_state)

        result = await urdhva_base.BasePostgresModel.get_aggr_data(combined_query, limit=0, skip=0)
        data = result.get('data', [])

        return {"status": True, "message": "success", "data": data}

    except Exception as e:
        import logging
        logging.exception("Error while fetching combined SBU company count")
        return {"status": False, "error": str(e)}



async def get_sod_lpg_info(filters, cross_filters, drill_state, limit, time_grain):
    try:
        # Configuration for each SBU with rename map included
        sbu_configs = [
            {
                "name": "SOD",
                "table": "sod_infra",
                "columns": "sap_id, sbu, location_name, company, ms, sko, hsd, total, mode_of_receipt",
                "rename_map": {"ms": "MS (KL)", "sko": "SKO (KL)", "hsd": "HSD (KL)", "total": "TOTAL (KL)"}
            },
            {
                "name": "LPG",
                "table": "lpg_infra",
                "columns": "sap_id, sbu, location_name, company, installed_bottling_capacity, operating_bottling_capacity, ccoe_tankage, mode, supply",
                "rename_map": {
                    "installed_bottling_capacity": "INSTALLED BOTTLING CAPACITY (TMTPA)",
                    "operating_bottling_capacity": "OPERATING BOTTLING CAPACITY (TMTPA)",
                    "ccoe_tankage": "CCOE TANKAGE (TMT)"
                }
            },
            {
                "name": "AVIATION",
                "table": "aviation_infra",
                "columns": "sap_id, sbu, location_name, company, operation_status, tankage, mode, pincode, status",
                "rename_map": {}
            },
            {
                "name": "LUBES",
                "table": "lubes_infra",
                "columns": "sap_id, sbu, location_name, company, base_oil_tankages, landline, status",
                "rename_map": {"base_oil_tankages": "BASE OIL TANKAGES (KL)"}
            }
        ]

        all_data = []

        for config in sbu_configs:
            query = f'''
                SELECT {config["columns"]}
                FROM {config["table"]}
            '''
            if filters:
                query = await widget_actions.WidgetActions.apply_filter_drilldown(query, filters, drill_state)

            result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0, skip=0)
            records = result.get('data', [])

            if config["rename_map"]:
                rename_map_lower = {k.lower(): v for k, v in config["rename_map"].items()}
                for i in range(len(records)):
                    renamed = {rename_map_lower.get(k.lower(), k): v for k, v in records[i].items()}
                    records[i] = {k: v for k, v in renamed.items()}
            else:
                for i in range(len(records)):
                    records[i] = {k: v for k, v in records[i].items()}
            all_data.extend(records)

        return {"status": True, "message": "success", "data": all_data}

    except Exception as e:
        import logging
        logging.exception("Error while fetching SOD/LPG/Aviation/Lubes data")
        return {"error": str(e)}




async def get_distinct_sod_lpg_info(sbu: str = "", zone=None, state=None, district=None, company=None, location_name=None):
    try:
        sbu_tables = ["sod_infra", "lpg_infra", "aviation_infra", "lubes_infra"]
        select_columns = "sbu, zone, state, district, company, location_name"

        union_queries = [f"SELECT {select_columns} FROM {table}" for table in sbu_tables]
        union_block = "\nUNION\n".join(union_queries)

        query = f'''
            DISTINCT {select_columns}
            FROM (
                {union_block}
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

        def add_if_valid(val, target_set):
            if val and val.strip():
                target_set.add(val.strip())

        sbu_set, zone_set, state_set, district_set, company_set, location_name_set = set(), set(), set(), set(), set(), set()

        for row in rows:
            add_if_valid(row.get("sbu"), sbu_set)
            add_if_valid(row.get("zone"), zone_set)
            add_if_valid(row.get("state"), state_set)
            add_if_valid(row.get("district"), district_set)
            add_if_valid(row.get("company"), company_set)
            add_if_valid(row.get("location_name"), location_name_set)

        if not rows:
            sbu_set = {"SOD", "LPG", "AVIATION", "LUBES"}

        return {
            "status": True,
            "message": "success",
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
        import logging
        logging.exception("Error while fetching distinct infra info")
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


async def get_sales_info(filters, cross_filters, drill_state, limit, time_grain):
    try:
        query = f'''
            WITH base_data AS (
                SELECT "SBU_Name" AS sbu,
                       plant_cd AS sap_id,
                       "SalesArea_Name" AS sales_area,
                       fiscal_year,
                       "NETWEIGHT_TMT" AS "NETWEIGHT (TMT)"
                FROM "MOM_DAY_LEVEL_DATA"
            )
            SELECT sbu,
                   sap_id,
                   sales_area,
                   fiscal_year,
                   ROUND(SUM("NETWEIGHT (TMT)")::numeric, 4) AS "NETWEIGHT (TMT)"
            FROM base_data
            GROUP BY sbu, sap_id, sales_area, fiscal_year
        '''

        if filters:
            query = await widget_actions.WidgetActions.apply_filter_drilldown(query, filters, drill_state)

        print(query)

        result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0, skip=0)
        rows = result.get("data", [])
        rows = [{k.upper(): v for k, v in row.items()} for row in rows]

        return {"status": True, "message": "success", "data": rows}

    except Exception as e:
        print(f"Error in get_sales_info: {str(e)}")
        return {"status": False, "message": f"Error: {str(e)}", "data": []}

async def get_sales_officer_info(sbu, sap_id):
    try:
        query = f'''   
                u.username, u.first_name, u.last_name, u.novex_role, u.contact_number, sbu.sap_id
            FROM {sbu}_infra sbu
            LEFT JOIN users u 
                ON sbu.sap_id = ANY(u.sap_id)
            WHERE sbu.sbu = '{sbu}' AND sbu.sap_id = '{sap_id}' 
              AND (u.username IS NOT NULL OR u.first_name IS NOT NULL OR u.last_name IS NOT NULL OR u.novex_role IS NOT NULL )
            ORDER BY username
        '''

        result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0, skip=0)
        records = result.get("data", [])
        # Drop contract employees records
        records = [r for r in records if r.get("username") != r.get("first_name")]
        return {"status": True, "message": "Sales Officer Info fetched successfully", "data": records}

    except Exception as e:
        return {"status": False, "message": f"Error while fetching Sales Officer Info: {str(e)}", "data": []}

async def get_download_info(sbu, background_tasks):
    try:
        query = f''' * from {sbu}_infra '''
        result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0, skip=0)
        rows = result.get("data", [])
        if not rows:
            return {"status": "error", "message": "No data found."}

        df = pd.DataFrame(rows)
        output_dir = "/opt/ceg/algo/orchestrator/masterdata/infra_inputs"
        os.makedirs(output_dir, exist_ok=True)
        template_file_path = os.path.join(output_dir, f"Updated_{sbu}_infra_data.xlsx")
        df.to_excel(template_file_path, index=False, sheet_name=sbu)
        background_tasks.add_task(lambda: os.remove(template_file_path))

        return FileResponse(
            path=template_file_path,
            media_type="application/octet-stream",
            filename=f"Updated_{sbu}_infra_data.xlsx"
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}