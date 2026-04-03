"""
IMS — LPG supply-chain indent KPIs (field force orchestrator).

Placeholder implementations: wire to ``ims_lpg_query.lpg_indent_queries`` once IMS_SAP table/column
names are confirmed from the SOP / data dictionary (see ``ims_lpg_query.py`` comments).

``table_data`` is passed from ``get_indent_details`` into each KPI handler so callers can later
choose aggregate counts vs row-level queries; behavior is not branched here yet.
"""
from __future__ import annotations
import urdhva_base
import charts_actions
import field_force_model
from typing import Any, Callable, Dict, List, Optional
import utilities.connection_mapping as connection_mapping
import orchestrator.field_force.utils as field_force_utils


def _widget_filters_to_dicts(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]],
) -> List[Dict[str, Any]]:
    if not widget_filters:
        return []
    out: List[Dict[str, Any]] = []
    for w in widget_filters:
        out.append(w.model_dump() if hasattr(w, "model_dump") else w.dict())
    return out


def generate_session_filters(
    query_filters: Optional[List[str]] = None, model: str = "IMS"
) -> List[str]:
    """Territory filters for LPG IMS widgets (delegates to shared IMS vendor mapping)."""
    return field_force_utils.generate_session_filters(
        vendor="IMS", model=model, query_filters=query_filters
    )


def _filters(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]],
) -> tuple[List[Dict[str, Any]], List[str]]:
    effective = field_force_utils.get_input_filters(
        _widget_filters_to_dicts(widget_filters),
        vendor="IMS",
        merge_session=True,
        model="IMS",
    )
    session = field_force_utils.generate_session_filters(vendor="IMS", model="IMS")
    return effective, session


async def execute_ims_query(query):
    connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    charts_ins = charts_actions.Charts_Connection_Vault_RoutingParams(
        connection_id=connection_id,
        action='execute_query'
    )
    function = await charts_actions.charts_connection_vault_routing(charts_ins)
    resp = await function(query=query)
    return resp


# --- Individual KPIs (Supply Chain — LPG funnel) ---
async def get_total_indents_raised(
        widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]] = None,
        level_filter: Optional[field_force_model.LevelFilterCreate] = None,
        drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
        *,
        table_data: bool = False,
):
    """Total indents raised (all states) in period — SOP: Total Indents Raised."""
    effective_filters, session_conditions = _filters(widget_filters)
    _ = (effective_filters, session_conditions, level_filter, drill_filter, table_data)
    conditions = [f"a.{condition}" for condition in session_conditions]
    conditions = " AND " + " AND ".join(conditions) if conditions else " "
    if table_data:
        query = f"""SELECT 
                a."INDENT_NO" AS "INDENT_NO", 
                b."PROD" AS "PROD", 
                a."LOCN_CODE" AS "LOCN_CODE", 
                a."DEALER_CODE" AS "DEALER_CODE", 
                a."INDENT_DATE" AS "INDENT_DATE", 
                a."PROD_REQD_DT" AS "PROD_REQD_DT" 
            FROM "LPGIMS_SAP"."INDENT_REQUEST" a
            JOIN "LPGIMS_SAP"."INDENT_PRODUCTS" b 
                ON a."LOCN_CODE" = b."LOCN_CODE" 
                AND a."INDENT_NO" = b."INDENT_NO"
            WHERE 
            TO_CHAR(a."PROD_REQD_DT",'yyyymmdd') >= TO_CHAR(SYSDATE,'yyyymmdd')
            {conditions}
            ORDER BY 
                a."INDENT_NO" DESC"""
    else:
        query = f"""SELECT count(*) FROM "LPGIMS_SAP"."INDENT_REQUEST" a WHERE 
                TO_CHAR(a."PROD_REQD_DT",'yyyymmdd') >= TO_CHAR(SYSDATE,'yyyymmdd')
                {conditions}"""
    resp = await execute_ims_query(query)
    return {
        "status": True,
        "data": resp,
        "message": "Total Indents Raised"
    }


async def get_cancelled_indents(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]] = None,
    level_filter: Optional[field_force_model.LevelFilterCreate] = None,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
    *,
    table_data: bool = False,
):
    """Indents cancelled in the selected window (SOP: Cancelled Indents)."""
    effective_filters, session_conditions = _filters(widget_filters)
    _ = (effective_filters, session_conditions, level_filter, drill_filter, table_data)
    conditions = [f"a.{condition}" for condition in session_conditions]
    conditions = " AND " + " AND ".join(conditions) if conditions else " "
    if table_data:
        query = f"""SELECT 
                    a."INDENT_NO" AS "INDENT_NO", 
                    b."PROD" AS "PROD", 
                    a."LOCN_CODE" AS "LOCN_CODE", 
                    a."DEALER_CODE" AS "DEALER_CODE", 
                    a."CANCEL_TIME" AS "CANCEL_TIME", 
                    a."INDENT_DATE" AS "INDENT_DATE", 
                    a."PROD_REQD_DT" AS "PROD_REQD_DT" 
                FROM "LPGIMS_SAP"."INDENT_REQUEST" a
                JOIN "LPGIMS_SAP"."INDENT_PRODUCTS" b 
                    ON a."LOCN_CODE" = b."LOCN_CODE" 
                    AND a."INDENT_NO" = b."INDENT_NO"
                WHERE 
                TO_CHAR(a."PROD_REQD_DT",'yyyymmdd') >= TO_CHAR(SYSDATE,'yyyymmdd')
                AND a."CANCEL_INDENT" IS NOT NULL 
                {conditions}
                ORDER BY 
                    a."INDENT_NO" DESC"""
    else:
        query = f"""SELECT count(*) FROM "LPGIMS_SAP"."INDENT_REQUEST" a WHERE 
                    TO_CHAR(a."PROD_REQD_DT",'yyyymmdd') >= TO_CHAR(SYSDATE,'yyyymmdd')
                    AND a."CANCEL_INDENT" IS NOT NULL 
                    {conditions}"""
    resp = await execute_ims_query(query)
    return {
        "status": True,
        "data": resp,
        "message": "Total Indents Raised"
    }


async def get_valid_indents(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]] = None,
    level_filter: Optional[field_force_model.LevelFilterCreate] = None,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
    *,
    table_data: bool = False,
):
    """Valid Indents  in the selected window (SOP: Valid Indents)."""
    effective_filters, session_conditions = _filters(widget_filters)
    _ = (effective_filters, session_conditions, level_filter, drill_filter, table_data)
    conditions = [f"a.{condition}" for condition in session_conditions]
    conditions = " AND " + " AND ".join(conditions) if conditions else " "
    if table_data:
        query = f"""SELECT 
                    a."LOCN_CODE" AS "LOCN_CODE", 
                    a."INDENT_NO" AS "INDENT_NO", 
                    b."PROD" AS "PROD", 
                    a."DEALER_CODE" AS "DEALER_CODE", 
                    a."INDENT_DATE" AS "INDENT_DATE", 
                    a."PROD_REQD_DT" AS "PROD_REQD_DT" 
                FROM "LPGIMS_SAP"."INDENT_REQUEST" a
                JOIN "LPGIMS_SAP"."INDENT_PRODUCTS" b 
                    ON a."LOCN_CODE" = b."LOCN_CODE" 
                    AND a."INDENT_NO" = b."INDENT_NO"
                WHERE 
                TO_CHAR(a."PROD_REQD_DT",'yyyymmdd') >= TO_CHAR(SYSDATE,'yyyymmdd')
                AND a."CANCEL_INDENT" IS NULL 
                AND a."VALID_INDENT_FLAG" IN ('Y', 'H') 
                {conditions}
                ORDER BY 
                    a."INDENT_NO" DESC"""
    else:
        query = f"""SELECT count(*) FROM "LPGIMS_SAP"."INDENT_REQUEST" a WHERE 
                    TO_CHAR(a."PROD_REQD_DT",'yyyymmdd') >= TO_CHAR(SYSDATE,'yyyymmdd')
                    AND a."CANCEL_INDENT" IS NULL 
                    AND a."VALID_INDENT_FLAG" IN ('Y', 'H') 
                    {conditions}"""
    resp = await execute_ims_query(query)
    return {
        "status": True,
        "data": resp,
        "message": "Total Indents Raised"
    }


async def get_pending_indents(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]] = None,
    level_filter: Optional[field_force_model.LevelFilterCreate] = None,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
    *,
    table_data: bool = False,
):
    """
    Indents awaiting approval / allocation (not yet released), per SOP “Pending Indents”.

    Output shape (target):
        {"summary": [{"pending_count": int, ...}], "drill_down": [...] | None, "total": int?}
    """
    effective_filters, session_conditions = _filters(widget_filters)
    _ = (effective_filters, session_conditions, level_filter, drill_filter, table_data)
    conditions = [f"a.{condition}" for condition in session_conditions]
    conditions = " AND " + " AND ".join(conditions) if conditions else " "
    if table_data:
        query = f"""SELECT 
                        a."LOCN_CODE" AS "LOCN_CODE", 
                        a."INDENT_NO" AS "INDENT_NO", 
                        b."PROD" AS "PROD", 
                        a."DEALER_CODE" AS "DEALER_CODE", 
                        a."INDENT_DATE" AS "INDENT_DATE", 
                        a."PROD_REQD_DT" AS "PROD_REQD_DT" 
                    FROM "LPGIMS_SAP"."INDENT_REQUEST" a
                    JOIN "LPGIMS_SAP"."INDENT_PRODUCTS" b 
                        ON a."LOCN_CODE" = b."LOCN_CODE" 
                        AND a."INDENT_NO" = b."INDENT_NO"
                    WHERE 
                    TO_CHAR(a."PROD_REQD_DT",'yyyymmdd') >= TO_CHAR(SYSDATE,'yyyymmdd')
                    AND a."TRUCK_REGNO" IS NULL 
                    AND a."VALID_INDENT_FLAG" IN ('Y', 'H') 
                    AND a."VALID_INDENT_FLAG" <> 'N' 
                    AND (a."CANCEL_INDENT" IS NULL OR a."CANCEL_INDENT" <> 'Y')
                    {conditions}
                    ORDER BY 
                        a."INDENT_NO" DESC"""
    else:
        query = f"""SELECT count(*) FROM "LPGIMS_SAP"."INDENT_REQUEST" a WHERE 
                        TO_CHAR(a."PROD_REQD_DT",'yyyymmdd') >= TO_CHAR(SYSDATE,'yyyymmdd')
                        AND "CANCEL_INDENT" IS NULL 
                        AND "VALID_INDENT_FLAG" IN ('Y', 'H') 
                        {conditions}"""
    resp = await execute_ims_query(query)
    return {
        "status": True,
        "data": resp,
        "message": "Total Indents Raised"
    }


async def get_indents_on_hold(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]] = None,
    level_filter: Optional[field_force_model.LevelFilterCreate] = None,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
    *,
    table_data: bool = False,
):
    """Indents explicitly on hold (credit / compliance / manual hold) — SOP: Indents on Hold."""
    effective_filters, session_conditions = _filters(widget_filters)
    _ = (effective_filters, session_conditions, level_filter, drill_filter, table_data)
    return {
        "status": False,
        "message": "Not implemented — wire ims_lpg_query indents_on_hold_query execution",
        "table_data": table_data,
        "data": [],
    }


async def get_trucks_allocated(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]] = None,
    level_filter: Optional[field_force_model.LevelFilterCreate] = None,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
    *,
    table_data: bool = False,
):
    """Count of indents with truck allocation (or trucks allocated) — SOP: Trucks Allocated."""
    effective_filters, session_conditions = _filters(widget_filters)
    _ = (effective_filters, session_conditions, level_filter, drill_filter, table_data)
    return {
        "status": False,
        "message": "Not implemented — wire ims_lpg_query trucks_allocated_query execution",
        "table_data": table_data,
        "data": [],
    }


async def get_sent_to_sap(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]] = None,
    level_filter: Optional[field_force_model.LevelFilterCreate] = None,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
    *,
    table_data: bool = False,
):
    """Indents pushed to SAP interface — SOP: Sent To SAP."""
    effective_filters, session_conditions = _filters(widget_filters)
    _ = (effective_filters, session_conditions, level_filter, drill_filter, table_data)
    return {
        "status": False,
        "message": "Not implemented — wire ims_lpg_query sent_to_sap_query execution",
        "table_data": table_data,
        "data": [],
    }


async def get_sales_order_placed(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]] = None,
    level_filter: Optional[field_force_model.LevelFilterCreate] = None,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
    *,
    table_data: bool = False,
):
    """Indents with SAP sales order created — SOP: Sales Order Placed."""
    effective_filters, session_conditions = _filters(widget_filters)
    _ = (effective_filters, session_conditions, level_filter, drill_filter, table_data)
    return {
        "status": False,
        "message": "Not implemented — wire ims_lpg_query sales_order_placed_query execution",
        "table_data": table_data,
        "data": [],
    }


async def get_invoice_created(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]] = None,
    level_filter: Optional[field_force_model.LevelFilterCreate] = None,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
    *,
    table_data: bool = False,
):
    """Indents with billing / invoice document — SOP: Invoice Created."""
    effective_filters, session_conditions = _filters(widget_filters)
    _ = (effective_filters, session_conditions, level_filter, drill_filter, table_data)
    return {
        "status": False,
        "message": "Not implemented — wire ims_lpg_query invoice_created_query execution",
        "table_data": table_data,
        "data": [],
    }


async def get_delivered(
    widget_filters: Optional[List[field_force_model.WidgetFiltersCreate]] = None,
    level_filter: Optional[field_force_model.LevelFilterCreate] = None,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
    *,
    table_data: bool = False,
):
    """Indents completed / delivered — SOP: Delivered."""
    effective_filters, session_conditions = _filters(widget_filters)
    _ = (effective_filters, session_conditions, level_filter, drill_filter, table_data)
    return {
        "status": False,
        "message": "Not implemented — wire ims_lpg_query delivered_query execution",
        "table_data": table_data,
        "data": [],
    }


_LPG_INDENT_ACTION_ALIASES: Dict[str, str] = {
    "pending_indents": "get_pending_indents",
    "cancelled_indents": "get_cancelled_indents",
    "valid_indents": "get_valid_indents",
    "total_indents_raised": "get_total_indents_raised",
    "indents_on_hold": "get_indents_on_hold",
    "trucks_allocated": "get_trucks_allocated",
    "sent_to_sap": "get_sent_to_sap",
    "sales_order_placed": "get_sales_order_placed",
    "invoice_created": "get_invoice_created",
    "indents_delivered": "get_delivered"
}


def _resolve_lpg_indent_action(action: str) -> Optional[str]:
    raw = (action or "").strip()
    if not raw:
        return None
    key = raw.lower().replace("-", "_")
    if key in _LPG_INDENT_ACTION_ALIASES:
        return _LPG_INDENT_ACTION_ALIASES[key]
    if key.startswith("get_"):
        return key
    candidate = f"get_{key}"
    return candidate


def _lpg_indent_action_handlers() -> Dict[str, Callable[..., Any]]:
    return {
        "get_total_indents_raised": get_total_indents_raised,
        "get_pending_indents": get_pending_indents,
        "get_cancelled_indents": get_cancelled_indents,
        "get_valid_indents": get_valid_indents,
        "get_indents_on_hold": get_indents_on_hold,
        "get_trucks_allocated": get_trucks_allocated,
        "get_sent_to_sap": get_sent_to_sap,
        "get_sales_order_placed": get_sales_order_placed,
        "get_invoice_created": get_invoice_created,
        "get_delivered": get_delivered,
        "get_lpg_supply_chain_funnel_summary": get_lpg_supply_chain_funnel_summary,
    }


async def get_indent_details(
    data: field_force_model.Indentmanagement_Get_Indent_DetailsParams,
) -> Dict[str, Any]:
    """
    Route ``data.action`` to the matching LPG KPI handler. Merges ``filters`` and ``cross_filters``.

    ``action`` may be a handler name (e.g. ``get_pending_indents``) or an alias (e.g. ``pending_indents``).

    ``data.table_data`` is forwarded to the handler as ``table_data`` (counts vs rows — implement later).
    """
    merged: List[field_force_model.WidgetFiltersCreate] = []
    merged.extend(data.filters or [])
    if data.cross_filters:
        merged.extend(data.cross_filters)

    resolved = _resolve_lpg_indent_action(data.action)
    if not resolved:
        return {
            "status": False,
            "message": "Missing or empty action for LPG get_indent_details",
            "data": [],
        }

    handlers = _lpg_indent_action_handlers()
    handler = handlers.get(resolved)
    if handler is None:
        return {
            "status": False,
            "message": f"Unknown LPG indent action: {data.action!r} (resolved: {resolved!r})",
            "data": [],
        }

    return await handler(merged, table_data=bool(data.table_data))
