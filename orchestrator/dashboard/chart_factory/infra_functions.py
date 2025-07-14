from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import urdhva_base
import json
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

        company_color_map = {
            'hpcl': '#00006B',
            'iocl': '#02164F',
            'bpcl': '#FFE000',
            'hmel': '#RRGGBB'
        }

        # color_code to SOD data
        for item in sod:
            company = item.get('company', '').lower()
            item['color_code'] = company_color_map.get(company, '#CCCCCC')

        # color_code to LPG data
        for item in lpg:
            company = item.get('company', '').lower()
            item['color_code'] = company_color_map.get(company, '#CCCCCC')

        # output = {"SOD": sod, "LPG": lpg}
        data = sod + lpg
        return {"status": True, "message": "success", "data": data}

    except Exception as e:
        print(f"Error while fetching SOD/LPG data: {e}")
        return {"error": str(e)}



async def get_count_company_info(filters, cross_filters, drill_state, limit, time_grain):
    try:
        sod_query = '''   company,bu, count(location_name) FROM sod_infra Group by company, bu '''
        lpg_query = '''   company,bu, count(location_name) FROM lpg_infra Group by company, bu '''

        if filters:
            sod_query = await widget_actions.WidgetActions.apply_filter_drilldown(sod_query, filters, drill_state)
            lpg_query = await widget_actions.WidgetActions.apply_filter_drilldown(lpg_query, filters, drill_state)

        sod_result = await urdhva_base.BasePostgresModel.get_aggr_data(sod_query, limit=0, skip=0)
        sod = sod_result['data']
        lpg_result = await urdhva_base.BasePostgresModel.get_aggr_data(lpg_query, limit=0, skip=0)
        lpg = lpg_result['data']

        company_color_map = {
            'hpcl': '#00006B',
            'iocl': '#02164F',
            'bpcl': '#FFE000',
            'hmel': '#RRGGBB'
        }
        # color_code to SOD data
        for item in sod:
            company = item.get('company', '').lower()
            item['color_code'] = company_color_map.get(company, '#CCCCCC')

        # color_code to LPG data
        for item in lpg:
            company = item.get('company', '').lower()
            item['color_code'] = company_color_map.get(company, '#CCCCCC')

        # combined_output = {"SOD": sod, "LPG": lpg}

        data = sod + lpg
        return {"status": True, "message": "success", "data": data}
    except Exception as e:
        print(f"Error while fetching SOD/LPG data: {e}")
        return {"error": str(e)}
