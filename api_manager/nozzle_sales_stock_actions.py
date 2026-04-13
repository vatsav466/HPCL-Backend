from field_force_enum import *
from field_force_model import *
import fastapi

import orchestrator.field_force.cris as field_force_cris
router = fastapi.APIRouter(prefix='/nozzle_sales_stock')


# Action stock_availability
@router.post('/stock_availability', tags=['nozzle_sales_stock'])
async def nozzle_sales_stock_stock_availability(data: Nozzle_Sales_Stock_Stock_AvailabilityParams):
    ...


# Action tank_utilization
@router.post('/tank_utilization', tags=['nozzle_sales_stock'])
async def nozzle_sales_stock_tank_utilization(data: Nozzle_Sales_Stock_Tank_UtilizationParams):
    ...


# Action nozzle_sales_analysis
@router.post('/nozzle_sales_analysis', tags=['nozzle_sales_stock'])
async def nozzle_sales_stock_nozzle_sales_analysis(data: Nozzle_Sales_Stock_Nozzle_Sales_AnalysisParams):
    ...


# Action nozzle_sales_comparison
@router.post('/nozzle_sales_comparison', tags=['nozzle_sales_stock'])
async def nozzle_sales_stock_nozzle_sales_comparison(data: Nozzle_Sales_Stock_Nozzle_Sales_ComparisonParams):
    ...


# Action nozzle_sales_prev_day_comparison
@router.post('/nozzle_sales_prev_day_comparison', tags=['nozzle_sales_stock'])
async def nozzle_sales_stock_nozzle_sales_prev_day_comparison(data: Nozzle_Sales_Stock_Nozzle_Sales_Prev_Day_ComparisonParams):
    ...


# Action product_availability_days
@router.post('/product_availability_days', tags=['nozzle_sales_stock'])
async def nozzle_sales_stock_product_availability_days(data: Nozzle_Sales_Stock_Product_Availability_DaysParams):
    return await field_force_cris.get_product_availability(data)
