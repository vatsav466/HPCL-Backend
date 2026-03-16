"""
CRIS (Tank Inventory + Nozzle Sales) - Field Force orchestrator.
Functional schema for TankInventory and NozzleSales APIs. No implementation.
"""
import field_force_model
from typing import List, Optional
import orchestrator.field_force.utils as field_force_utils


# -------- Session-based filter generation --------
def generate_session_filters(query_filters=None, model: str = "CRIS"):
    """
    Build a list of WHERE-style conditions from the current user's session (role-based territory).

    Delegates to utils.generate_session_filters with vendor "CRIS". Column names come from
    utils.TERRITORY_COLUMN_BY_VENDOR for the given model (CRIS or NOVEX).

    :param query_filters: Optional; not merged here; caller can combine with returned list.
    :param model: "CRIS" or "NOVEX". CRIS uses rosapcode/SALES_AREA; NOVEX uses sap_id/sales_area/region/zone.
    :return: List of condition strings (e.g. "SALES_AREA='MUMBAI DS SA'").
    """
    return field_force_utils.generate_session_filters(vendor="CRIS", model=model, query_filters=query_filters)


async def stock_availability(
    data: field_force_model.WidgetFiltersCreate,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
):
    """
    Stock availability by product. Optional drill-down to dealer and tank level.

    Input:
        data: WidgetFilters.
        drill_filter: optional {"drill_to": "dealer_tank"}.
    Output:
        {"summary": [{"product_code", "product_name", "total_stock", "available_stock", "unit", ...}],
         "drill_down": [{"dealer_id", "dealer_name", "tank_id", "product_code", "quantity", ...}] or None,
         "total": int?, "drill_to": str?}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def tank_utilization(
    data: field_force_model.WidgetFiltersCreate,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
):
    """
    Tank utilization by product (Capacity vs Quantity). Drill-down to dealer and tank level.

    Input:
        data: WidgetFilters.
        drill_filter: optional {"drill_to": "dealer_tank"}.
    Output:
        {"summary": [{"product_code", "total_capacity", "total_quantity", "utilization_pct", ...}],
         "drill_down": [{"dealer_id", "tank_id", "capacity", "quantity", "utilization_pct", ...}] or None,
         "total": int?, "drill_to": str?}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


# -------- Nozzle Sales (CRIS) --------


async def get_nozzle_sales_by_product(
    data: field_force_model.WidgetFiltersCreate,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
):
    """
    Nozzle sales by product. Drill-down to outlet and products.

    Input:
        data: WidgetFilters.
        drill_filter: optional {"drill_to": "outlets"}.
    Output:
        {"summary": [{"product_code", "product_name", "volume", "sales_count", "period", ...}],
         "drill_down": [{"outlet_id", "outlet_name", "dealer_id", "product_code", "volume", ...}] or None,
         "total": int?, "drill_to": str?}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def get_nozzle_sales_day_comparison(
    data: field_force_model.WidgetFiltersCreate,
):
    """
    Today's vs yesterday's sales by product.

    Input:
        data: WidgetFilters.
    Output:
        {"current": [{"product_code", "volume", "date": "today"}],
         "previous": [{"product_code", "volume", "date": "yesterday"}],
         "comparison": [{"product_code", "current_volume", "previous_volume", "pct_change", ...}],
         "period_current": "today", "period_previous": "yesterday"}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def get_product_performance(
    data: field_force_model.WidgetFiltersCreate,
):
    """
    MS vs Power / HSD vs Turbo sales performance.

    Input:
        data: WidgetFilters.
    Output:
        {"summary": [{"product_code", "product_name", "volume", "pct_share", "rank", "period", ...}],
         "drill_down": None, "total": int?}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def get_degrading_outlets(
    data: field_force_model.WidgetFiltersCreate,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
):
    """
    Number of outlets degrading and percentage of degrading by product. Drill-down to outlet.

    Input:
        data: WidgetFilters.
        drill_filter: optional {"drill_to": "outlets"}.
    Output:
        {"summary": [{"product_code", "degrading_outlet_count", "total_outlets", "degrading_pct", ...}],
         "drill_down": [{"outlet_id", "outlet_name", "product_code", "current_volume", "previous_volume", "pct_change", ...}] or None,
         "total": int?, "drill_to": str?}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def get_top_degrading_dealers(
    data: field_force_model.WidgetFiltersCreate,
    top_count: int = 10,
    by_product: bool = False,
):
    """
    Top dealers with degrading sales; overall and optionally by product.

    Input:
        data: WidgetFilters.
        top_count: max dealers to return (default 10).
        by_product: if True, breakdown by product per dealer.
    Output:
        {"summary": [{"dealer_id", "dealer_name", "degrading_pct", "volume_drop", "product_code"?, ...}],
         "drill_down": None,          "total": int?, "top_count": int}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def get_high_risk_outlets(
    data: field_force_model.WidgetFiltersCreate,
):
    """
    High-risk outlets (dealers where sales drop was high).

    Input:
        data: WidgetFilters.
    Output:
        {"summary": [{"outlet_id", "outlet_name", "dealer_id", "sales_drop_pct", "current_volume", "previous_volume", "risk_level", ...}],
         "drill_down": None, "total": int?}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def get_zero_sales_outlets(
    data: field_force_model.WidgetFiltersCreate,
    period: Optional[str] = None,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
):
    """
    Zero sales outlets for selected period: 1_week | 15_days | 1_month. Drill-down to outlet.

    Input:
        data: WidgetFilters.
        period: "1_week" | "15_days" | "1_month".
        drill_filter: optional {"drill_to": "outlets"}.
    Output:
        {"summary": [{"outlet_count": int, "period", "product_code"?, ...}],
         "drill_down": [{"outlet_id", "outlet_name", "dealer_id", "last_sale_date", "days_zero", ...}] or None,
         "total": int?, "period": str?, "drill_to": str?}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def get_outlets_by_degrowth_group(
    data: field_force_model.WidgetFiltersCreate,
):
    """
    Outlets grouped by degrowth percentage (e.g. 5–10%, 10–20%, ...).

    Input:
        data: WidgetFilters.
    Output:
        {"summary": [{"degrowth_bucket": str, "outlet_count": int, "min_pct", "max_pct", "total_volume_drop", ...}],
         "drill_down": None, "total": int?}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def get_power_sales_growth_locations(
    data: field_force_model.WidgetFiltersCreate,
    top_count: int = 10,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
):
    """
    Top locations where Power sales are growing rapidly. Drill-down to location.

    Input:
        data: WidgetFilters.
        top_count: max locations (default 10).
        drill_filter: optional {"drill_to": "locations"}.
    Output:
        {"summary": [{"location_id", "location_name", "power_volume", "growth_pct", "rank", ...}],
         "drill_down": [{"location_id", "location_name", "product_breakdown", ...}] or None,
         "total": int?, "drill_to": str?, "top_count": int}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def nozzle_sales_analysis(
    data: field_force_model.WidgetFiltersCreate,
):
    """
    Legacy: MTD, Today, by product.

    Input:
        data: WidgetFilters.
    Output:
        {"summary": [{"product_code", "today_volume", "mtd_volume", "period", ...}],
         "drill_down": None, "total": int?}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


async def nozzle_sales_comparison(
    data: field_force_model.WidgetFiltersCreate,
):
    """
    Legacy: present year vs last year comparison.

    Input:
        data: WidgetFilters.
    Output:
        {"current": [{"product_code", "volume", "year": current_year}],
         "previous": [{"product_code", "volume", "year": previous_year}],
         "comparison": [{"product_code", "current_volume", "previous_volume", "pct_change", ...}],
         "period_current": str, "period_previous": str}
    """
    effective_filters = field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation
