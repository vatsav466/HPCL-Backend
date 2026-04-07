"""
CRIS (Tank Inventory + Nozzle Sales) - Field Force orchestrator.
Functional schema for TankInventory and NozzleSales APIs. No implementation.
"""
import hpcl_ceg_model
import field_force_model
import polars as pl
import datetime
from typing import List, Optional
import orchestrator.field_force.utils as field_force_utils
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams


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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
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
    effective_filters = await field_force_utils.get_input_filters(data or [], vendor="CRIS", merge_session=True)
    session_conditions = field_force_utils.generate_session_filters(vendor="CRIS")
    pass  # TODO: use effective_filters and session_conditions in implementation


# Default product groups and conversion factors for nozzle_sales TMT calculation
NOZZLE_SALES_MS_PRODUCTS_DEFAULT = ("MS", "E20", "POWER 99", "POWER 95", "POWER 100")
NOZZLE_SALES_HSD_PRODUCTS_DEFAULT = ("HSD", "TURBO")
NOZZLE_SALES_MS_DIVISOR = 1411.0
NOZZLE_SALES_HSD_DIVISOR = 1210.0
NOZZLE_SALES_VOLUME_FACTOR = 0.89

# Relative period shorthand: "1D" = last 1 day (yesterday), "7D" = last 7 days, etc.
NOZZLE_SALES_RELATIVE_DAYS_PATTERN = {"1d": 1, "2d": 2, "7d": 7, "15d": 15, "30d": 30}


def _nozzle_sales_parse_date_spec(date_spec, reference_date=None):
    """
    Parse flexible date_spec into (start_date_str, end_date_str) for SQL, both 'YYYY-MM-DD'.

    date_spec can be:
    - None or 1 or "1D": single day = yesterday (relative to reference_date).
    - int (2, 7, 15, ...) or str "2D", "7D", "15D", "30D": last N days ending yesterday (inclusive).
    - str "YYYY-MM-DD" or datetime.date: single exact date.
    - (start, end) or [start, end]: date range; start/end as str or date.

    reference_date: date to use as "today" for relative specs; default datetime.date.today().
    """
    today = reference_date if reference_date is not None else datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    def to_str(d):
        if d is None:
            return None
        if isinstance(d, datetime.date) and not isinstance(d, datetime.datetime):
            return d.strftime("%Y-%m-%d")
        if isinstance(d, datetime.datetime):
            return d.date().strftime("%Y-%m-%d")
        s = str(d).strip()
        if not s:
            return None
        return s

    if date_spec is None:
        start_date = end_date = yesterday
    elif isinstance(date_spec, int):
        if date_spec <= 1:
            start_date = end_date = yesterday
        else:
            end_date = yesterday
            start_date = today - datetime.timedelta(days=date_spec)
    elif isinstance(date_spec, str):
        date_spec = date_spec.strip().lower()
        if date_spec in NOZZLE_SALES_RELATIVE_DAYS_PATTERN:
            n = NOZZLE_SALES_RELATIVE_DAYS_PATTERN[date_spec]
            if n <= 1:
                start_date = end_date = yesterday
            else:
                end_date = yesterday
                start_date = today - datetime.timedelta(days=n)
        else:
            try:
                d = datetime.datetime.strptime(date_spec, "%Y-%m-%d").date()
                start_date = end_date = d
            except ValueError:
                start_date = end_date = yesterday
    elif isinstance(date_spec, (list, tuple)) and len(date_spec) >= 2:
        start_date = date_spec[0]
        end_date = date_spec[1]
        if isinstance(start_date, str):
            try:
                start_date = datetime.datetime.strptime(start_date.strip()[:10], "%Y-%m-%d").date()
            except ValueError:
                start_date = yesterday
        if isinstance(end_date, str):
            try:
                end_date = datetime.datetime.strptime(end_date.strip()[:10], "%Y-%m-%d").date()
            except ValueError:
                end_date = yesterday
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        start_date = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else to_str(start_date)
        end_date = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else to_str(end_date)
        return start_date, end_date
    elif isinstance(date_spec, (datetime.date, datetime.datetime)):
        d = date_spec.date() if isinstance(date_spec, datetime.datetime) else date_spec
        s = d.strftime("%Y-%m-%d")
        return s, s
    else:
        start_date = end_date = yesterday

    start_date = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else to_str(start_date)
    end_date = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else to_str(end_date)
    return start_date, end_date


def _nozzle_sales_build_tmt_expr(products: tuple, divisor: float, alias: str) -> str:
    """Build SQL expression for TMT: (SUM(sales_volume) FILTER / divisor) / 1000 / factor."""
    if not products:
        return None

    case_parts = []

    for p in products:
        if p in NOZZLE_SALES_MS_PRODUCTS_DEFAULT:
            case_parts.append(
                f"WHEN ns.product_grp = '{p}' THEN ns.sales_volume / {NOZZLE_SALES_MS_DIVISOR}"
            )
        elif p in NOZZLE_SALES_HSD_PRODUCTS_DEFAULT:
            case_parts.append(
                f"WHEN ns.product_grp = '{p}' THEN ns.sales_volume / {NOZZLE_SALES_HSD_DIVISOR}"
            )

    case_sql = " ".join(case_parts)

    return (
        f"ROUND(( (SUM(CASE "
        f"{case_sql} "
        f"ELSE 0 END) "
        f") / 1000.0 ) / {NOZZLE_SALES_VOLUME_FACTOR}, 2) AS {alias}"
    )
    

def _nozzle_sales_build_filter_conditions(filters):
    """
    Build SQL WHERE conditions from filters list.

    Each filter: {'key': 'sap_id', 'cond': '=', 'value': None, 'values': ['a', 'b']}.
    - value: single value (used with cond '=' or '!=').
    - values: multiple values (used with cond 'in' or 'not in').
    - cond: '=', '!=', 'in', 'not in'.

    Returns list of SQL condition strings (e.g. ["ns.sap_id IN ('a','b')"]).
    Column names are mapped to nozzle_sales (ns) or location_master (lm) columns; values are quoted as literals.
    """
    if not filters:
        return []
    conditions = []
    # Map filter key to (table_alias, column_name) for SQL
    key_to_col = {
        "region": ("ns", "region"),
        "sap_id": ("ns", "sap_id"),
        "zone": ("lm", "zone"),
        "state": ("lm", "state"),
        "sales_area": ("lm", "sales_area"),
        "product": ("ns", "product_grp"),
        "location_name": ("ns", "location_name")
    }
    for f in filters:
        if not isinstance(f, dict):
            continue
        key = (f.get("key") or "").strip().lower()
        cond = (f.get("cond") or "=").strip().lower()
        value = f.get("value")
        values = f.get("values")
        if key not in key_to_col:
            continue
        tbl, col = key_to_col[key]
        qual = f"{tbl}.{col}"
        if values is not None and (isinstance(values, (list, tuple)) and len(values) > 0):
            vals = [str(v).strip() for v in values if v is not None]
            if not vals:
                continue
            lit = ", ".join(f"'{v}'" for v in vals)
            if cond == "not in":
                conditions.append(f"{qual} NOT IN ({lit})")
            else:
                conditions.append(f"{qual} IN ({lit})")
        elif value is not None:
            lit = f"'{str(value).strip()}'"
            if cond == "!=":
                conditions.append(f"{qual} != {lit}")
            else:
                conditions.append(f"{qual} = {lit}")
    return conditions


async def nozzle_sales(
    segregation: str = "sales_area",
    ms_products: tuple = None,
    hsd_products: tuple = None,
    date_spec=None,
    filters=None,
    level_filter=None,
    include_expected_sites: bool = True,
    reference_date=None,
):
    """
    Nozzle sales by segregation level (global, zone, sales_area, state, sap_id) with configurable MS/HSD products.

    Args:
        segregation: One of "global", "zone", "sales_area", "state", "sap_id". Default "sales_area".
        ms_products: Product groups for MS volume TMT. Default ("MS","POWER 99","POWER 95","POWER 100").
        hsd_products: Product groups for HSD volume TMT. Default ("HSD","TURBO").
        date_spec: Flexible date or range. Default None = yesterday (same as "1D").
            - None or 1 or "1D": single day = yesterday.
            - int (2, 7, 15, ...) or "2D", "7D", "15D", "30D": last N days ending yesterday (inclusive).
            - str "YYYY-MM-DD": single exact date.
            - (start, end) or [start, end]: date range; start/end as "YYYY-MM-DD" or date.
            - datetime.date: single exact date.
        filters: Optional list of filter dicts. Each: {'key': 'sap_id', 'cond': '=', 'value': None, 'values': ['a','b']}.
            - value: single value (use with cond '=' or '!=').
            - values: multiple values (use with cond 'in' or 'not in').
            - cond: '=', '!=', 'in', 'not in'.
            - key: 'sap_id', 'zone', 'state', 'sales_area'. When sap_id is selected, name is included in output for sap_id segregation.
        include_expected_sites: If True, attach expected site count per segment from location_master (RO). Default True.
        reference_date: Date used as "today" for relative specs (e.g. "1D", 7); default today.

    Returns:
        {"daily_zone_product_nozzle_sales": [{"transaction_date", "<segment_col>", "connected_sites", "MS_volume(TMT)", "HSD_volume(TMT)"[, "name"], ...]}.
        For segregation sap_id, each row includes "sap_id" and "name" (location name).
    """

    if isinstance(segregation, str):
        segregation = [segregation]

    segregation = [s.strip().lower() for s in segregation]

    valid_segs = ("zone", "sales_area", "state", "sap_id", "product", "location_name", "monthly")
    segregation = [s for s in segregation if s in valid_segs]
    if not segregation:
        segregation = ["global"]

    sales_volume = None
    all_products = []
    if ms_products:
        all_products.extend(ms_products)
    if hsd_products:
        all_products.extend(hsd_products)

    sales_volume = _nozzle_sales_build_tmt_expr(
        tuple(all_products) if all_products else list(NOZZLE_SALES_MS_PRODUCTS_DEFAULT) + list(NOZZLE_SALES_HSD_PRODUCTS_DEFAULT),    
        None,                
        "sales_volume"
    )

    filters = filters if filters is not None else []
    if all_products:
        filters.append({
            "key": "product",
            "cond": "in",
            "values": all_products
        })
    filter_conditions = _nozzle_sales_build_filter_conditions(filters)

    need_lm_for_filters = any("lm." in c for c in filter_conditions)
    extra_where = " AND ".join(filter_conditions) if filter_conditions else ""

    if isinstance(date_spec, list) and len(date_spec) == 1 and "," in date_spec[0]:
        start_str, end_str = date_spec[0].split(",", 1)
        date_spec = [start_str.strip(), end_str.strip()]

    start_d, end_d = _nozzle_sales_parse_date_spec(date_spec, reference_date=reference_date)
    if start_d == end_d:
        date_filter = f"ns.transaction_date::DATE = '{start_d}'"
    else:
        date_filter = f"ns.transaction_date::DATE BETWEEN '{start_d}' AND '{end_d}'"
    where_parts = [date_filter]
    if extra_where:
        where_parts.append(extra_where)
    where_clause = " AND ".join(where_parts)

    group_cols = []
    dim_col = None
    if "global" in segregation:
        join_lm = need_lm_for_filters
        from_join = "FROM public.nozzle_sales ns"
        if join_lm:
            from_join += " JOIN public.location_master lm ON ns.sap_id = lm.sap_id"
        nozzle_sales_query = f"""
            SELECT
                ns.transaction_date::DATE AS transaction_date,
                COUNT(DISTINCT ns.site_id) AS connected_sites,
                {sales_volume}
            {from_join}
            WHERE {where_clause}
            GROUP BY ns.transaction_date::DATE
            ORDER BY ns.transaction_date::DATE
        """
        group_cols = []
        dim_col = None
        print("nozzle sales query global ---->\n", nozzle_sales_query)

    elif "monthly" in segregation:

        from_join = "FROM public.nozzle_sales ns JOIN public.location_master lm ON ns.sap_id = lm.sap_id"

        has_filters = any(f.get("key") for f in (filters or []))
        level = (level_filter or {}).get("level", "").lower()


        select_columns = [
                "DATE_TRUNC('month', ns.transaction_date)::DATE AS month",
                "COALESCE(ns.zone, lm.zone) AS zone"
            ]

        group_by_parts = [
                "DATE_TRUNC('month', ns.transaction_date)::DATE",
                "COALESCE(ns.zone, lm.zone)"
            ]
        #default query 
        if not has_filters and not level:
            select_sql = ",\n        ".join(select_columns)
            group_by_sql = ", ".join(group_by_parts)
            nozzle_sales_query = f"""
                SELECT
                    {select_sql},
                    COUNT(DISTINCT ns.site_id) AS connected_sites,
                    {sales_volume}
                {from_join}
                GROUP BY {group_by_sql}
                ORDER BY {group_by_sql}
            """
            print("Default monthly zone query ---->\n", nozzle_sales_query)

        else:

            filter_conditions = [
                cond for cond in filter_conditions
                if "ns.transaction_date" not in cond.lower()
            ]
            filter_conditions_monthly = []

            for f, cond in zip(filters or [], filter_conditions):
                key = f.get("key", "").lower()

                if level == "zone" and key == "zone":
                    filter_conditions_monthly.append(cond)

                elif level == "region" and key in ("zone", "region"):
                    filter_conditions_monthly.append(cond)

                elif level == "sales_area" and key in ("zone", "region", "sales_area"):
                    filter_conditions_monthly.append(cond)

            where_clause_monthly = ""
            if filter_conditions_monthly:
                where_clause_monthly = "WHERE " + " AND ".join(filter_conditions_monthly)

            if level == "zone":
                select_columns.append("ns.region AS region")
                group_by_parts.append("ns.region")

            elif level == "region":
                select_columns.append("ns.region AS region")
                select_columns.append("ns.sales_area AS sales_area")

                group_by_parts.append("ns.region")
                group_by_parts.append("ns.sales_area")

            elif level == "sales_area":
                select_columns.append("ns.region AS region")
                select_columns.append("ns.sales_area AS sales_area")
                select_columns.append("ns.location_name AS location_name")

                group_by_parts.append("ns.region")
                group_by_parts.append("ns.sales_area")
                group_by_parts.append("ns.location_name")

            select_sql = ",\n        ".join(select_columns)
            group_by_sql = ", ".join(group_by_parts)

            nozzle_sales_query = f"""
                SELECT
                    {select_sql},
                    COUNT(DISTINCT ns.site_id) AS connected_sites,
                    {sales_volume}
                {from_join}
                {where_clause_monthly}
                GROUP BY {group_by_sql}
                ORDER BY {group_by_sql}
            """

            print("Filtered monthly query ---->\n", nozzle_sales_query)

    else:
        select_columns = ["ns.transaction_date::DATE AS transaction_date"]
        group_by_parts = ["ns.transaction_date::DATE"]
        group_cols = []
        dim_col = None 

        for seg in segregation:
            if seg == "sap_id":
                select_columns.append("ns.sap_id AS sap_id")
                select_columns.append("COALESCE(lm.name, ns.location_name) AS name")
                group_by_parts.append("ns.sap_id")
                group_by_parts.append("COALESCE(lm.name, ns.location_name)")
                group_cols.extend(["sap_id", "name"])
            elif seg == "sales_area":
                select_columns.append("COALESCE(ns.sales_area, lm.sales_area) AS sales_area")
                group_by_parts.append("COALESCE(ns.sales_area, lm.sales_area)")
            elif seg == "state":
                select_columns.append("lm.state AS state")
                group_by_parts.append("lm.state")
            elif seg == "zone":
                select_columns.append("COALESCE(ns.zone, lm.zone) AS zone")
                group_by_parts.append("COALESCE(ns.zone, lm.zone)")
            elif seg == "product":
                select_columns.append("ns.product_grp AS product")
                group_by_parts.append("ns.product_grp")
            elif seg == "location_name":
                select_columns.append("ns.location_name AS location_name")
                group_by_parts.append("ns.location_name")

        # Aggregates
        select_columns.append("COUNT(DISTINCT ns.site_id) AS connected_sites")
        if sales_volume:
            select_columns.append(sales_volume)
        # Join everything
        select_sql = ",\n        ".join(select_columns)
        group_by_sql = ", ".join(group_by_parts)
        from_join = "FROM public.nozzle_sales ns JOIN public.location_master lm ON ns.sap_id = lm.sap_id"

        nozzle_sales_query = f"""
        SELECT
            {select_sql}
        {from_join}
        WHERE {where_clause}
        GROUP BY {group_by_sql}
        ORDER BY {group_by_sql}
        """
        print("nozzle sales query ---->\n",nozzle_sales_query)


    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = "execute_query"
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    rows = await function(query=nozzle_sales_query)
    nozzle_sales_df = pl.DataFrame(rows)

    if nozzle_sales_df.is_empty():
            return {
                "status": True,
                "message": "success",
                "data": []
            }

    for col in group_cols:
        if col in nozzle_sales_df.columns:
            nozzle_sales_df = nozzle_sales_df.filter(pl.col(col).is_not_null())


    if (ms_products or hsd_products) and ("product", "zone") in segregation:
        nozzle_sales_df = nozzle_sales_df.with_columns(
            pl.when(pl.col("product").is_in(ms_products))
                .then(pl.lit("MS"))
                .when(pl.col("product").is_in(hsd_products))
                .then(pl.lit("HSD"))
                .otherwise(pl.col("product"))
                .alias("product")
        )

        nozzle_sales_df = nozzle_sales_df.group_by(["transaction_date", "zone", "product"]).agg(
            pl.col("connected_sites").sum().alias("connected_sites"),
            pl.col("sales_volume").sum().alias("sales_volume")
        ).sort("transaction_date")


    return {
        "daily_zone_product_nozzle_sales": nozzle_sales_df.to_dicts()
    }



async def nozzle_sales_tmt(filters= None, cross_filters=None, level_filter=None, segregation=None, ms_products=None, hsd_products=None, action: str= ""):
    """
    this function used for nozzle sales tmt where user gives the filters like zone , product and date range
    and based on that the data will be fetched from the database and return the response to the user 
    """
    raw_filters = filters or []
    cross_filters = cross_filters or []
    date_range = []
    segregation =segregation or []
    ms_products = ms_products or []
    hsd_products = hsd_products or []

    for fc in cross_filters:
        key = fc.get("key", "").lower() 
        if key == "date" and (fc.get("value") or fc.get("values")):
            if fc.get("values"):
                date_range.extend(fc["values"])  
            elif fc.get("value"):
                if "," in fc["value"]:
                    date_range.extend([d.strip() for d in fc["value"].split(",")])
                else:
                    date_range.append(fc["value"])

    # combined_filters = cross_filters + raw_filters
    combined_filters = (cross_filters or []) + (raw_filters or [])
    if action == "nozzle_daily_sales_tmt":
        today = datetime.datetime.now().date()
        yesterday = today - datetime.timedelta(days=1)
        # the nozzle sales table stores the data with a delay of 1 day.so today's date is mapped to yesterday's date.
        if date_range:
            normalized = []
            print("date range before normalization:", date_range)
            for d in date_range:
                try:
                    parsed = datetime.datetime.strptime(d.strip()[:10], "%Y-%m-%d").date()
                    if parsed == today:
                        parsed = yesterday
                    normalized.append(parsed.strftime("%Y-%m-%d"))
                except Exception:
                    normalized.append(d)
            date_range = normalized

        result = await nozzle_sales(
            segregation=segregation,
            filters=combined_filters,
            # filters=cross_filters,
            date_spec=date_range,
            ms_products=ms_products,
            hsd_products=hsd_products,
            level_filter=level_filter
        )
        return result

    elif action == "nozzle_monthly_sales_tmt":
        if cross_filters:
            cross_filters = cross_filters
        else:
            cross_filters= None

        seg = ["monthly"]
        if segregation:
            seg.extend(segregation)

        df = await nozzle_sales(
            segregation= seg,
            filters= combined_filters,
            ms_products= ms_products,
            hsd_products= hsd_products,
            level_filter= level_filter
        )
        
        df = pl.DataFrame(df["daily_zone_product_nozzle_sales"])

        overall = None
        zone = None
        region = None
        sales_area = None
        location = None
        level = level_filter.get("level") if level_filter else None

        if not raw_filters:
            zone = df.select(["month", "zone", "sales_volume"])
            overall = df.group_by("month").agg([
                pl.sum("sales_volume").alias("sales_volume"),
                pl.sum("connected_sites").alias("connected_sites")
            ]).sort("month")

        if "zone" == level:
            region = df.select(["month", "region", "sales_volume"])

        if "region" == level:
            sales_area = df.select(["month", "sales_area", "sales_volume"])

        if "sales_area" == level:
            location = df.select(["month", "location_name", "sales_volume"])

        return {
            "overall": overall.to_dicts() if overall is not None else [],
            "monthly": overall.to_dicts() if overall is not None else [],
            "zone": zone.to_dicts() if zone is not None else [],
            "region": region.to_dicts() if region is not None else [],
            "sales_area": sales_area.to_dicts() if sales_area is not None else [],
            "location": location.to_dicts() if location is not None else []
        }
    
    return {}
    
