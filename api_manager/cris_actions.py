from field_force_enum import *
from field_force_model import *
import fastapi

import orchestrator.field_force.cris as field_force_cris

router = fastapi.APIRouter(prefix='/cris')


def _params(data):
    return data.model_dump() if hasattr(data, 'model_dump') else data.dict()


# Action stock_availability
@router.post('/stock_availability', tags=['CRIS'])
async def cris_stock_availability(data: Cris_Stock_AvailabilityParams):
    return await field_force_cris.stock_availability(**_params(data))


# Action tank_utilization
@router.post('/tank_utilization', tags=['CRIS'])
async def cris_tank_utilization(data: Cris_Tank_UtilizationParams):
    return await field_force_cris.tank_utilization(**_params(data))


# Action nozzle_sales_analysis
@router.post('/nozzle_sales_analysis', tags=['CRIS'])
async def cris_nozzle_sales_analysis(data: Cris_Nozzle_Sales_AnalysisParams):
    return await field_force_cris.nozzle_sales_analysis(**_params(data))


# Action nozzle_sales_comparison
@router.post('/nozzle_sales_comparison', tags=['CRIS'])
async def cris_nozzle_sales_comparison(data: Cris_Nozzle_Sales_ComparisonParams):
    return await field_force_cris.nozzle_sales_comparison(**_params(data))


# Action nozzle_sales_prev_day_comparison
@router.post('/nozzle_sales_prev_day_comparison', tags=['CRIS'])
async def cris_nozzle_sales_prev_day_comparison(data: Cris_Nozzle_Sales_Prev_Day_ComparisonParams):
    return await field_force_cris.get_nozzle_sales_day_comparison(**_params(data))


# Action product_availability_days
@router.post('/product_availability_days', tags=['CRIS'])
async def cris_product_availability_days(data: Cris_Product_Availability_DaysParams):
    return await field_force_cris.get_product_availability(data)
