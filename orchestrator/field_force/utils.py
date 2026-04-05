"""
Shared utilities for Field Force orchestrator (IMS, CRIS, Novex, etc.).
"""
from typing import Any, Dict, List, Optional
import orchestrator.field_force.vendor_territory_mapping as vendor_territory_mapping

# -------- Territory → column name per vendor/model (for WHERE conditions and WidgetFilters) --------
TERRITORY_COLUMN_BY_VENDOR: Dict[str, Dict[str, str]] = {
    "IMS": {
        "location": "LOCN_CODE",
        # "sales_area": "sales_area",
        # "region": "region",
        # "zone": "zone",
        "plant": "LOCN_CODE",
        "dealer": "SUBSTR(DEALER_CODE,3,10)",
    },
    "IMS_LPG": {
        "location": "LOCN_CODE",
        "plant": "LOCN_CODE",
        "sales_area": "SAREA_CODE",
        "zone": "ZONE",
    },
    "CRIS": {
        "location": "rosapcode",
        "sales_area": "SALES_AREA",
        "region": "Region",
    },
    "NOVEX": {
        "location": "sap_id",
        "sales_area": "sales_area",
        "region": "region",
        "zone": "zone",
    },
}


def format_in_condition(column: str, value: Any) -> str:
    """
    Build a single SQL-friendly condition: column = 'val' or column in ('a','b').

    Values are stringified and wrapped in quotes for IN clauses. Used by
    generate_session_filters in ims and cris. Caller should use parameterized
    queries in production when values may be user-controlled.

    :param column: SQL column (or field) name.
    :param value: Single value (str, int, etc.) or list of values for IN clause.
    :return: Condition string, e.g. "sales_area='MUMBAI DS SA'" or "sap_id in ('1','2')".
             Empty string if value is None or empty list.
    """
    if value is None or (isinstance(value, list) and len(value) == 0):
        return ""
    if isinstance(value, list):
        quoted = tuple(f'{str(v)}' for v in value)
        return f"{column} in {quoted}"
    return f"{column}='{str(value)}'"


def generate_session_filters(
    vendor: str,
    model: Optional[str] = None,
    query_filters: Optional[List[str]] = None,
) -> List[str]:
    """
    Build WHERE-style conditions from the current user's session (role-based territory).

    Uses vendor_territory_mapping.get_role_based_filters(vendor) and maps each territory
    type to the correct column name for the given model, then formats as SQL conditions.

    :param vendor: Target system for territory mapping, e.g. "IMS", "CRIS".
    :param model: Optional; defaults to vendor. Used to look up column map (e.g. "CRIS" vs "NOVEX").
    :param query_filters: Optional; not merged here; caller can combine with returned list.
    :return: List of condition strings (e.g. "sales_area='MUMBAI DS SA'"). Empty if no session.
    """
    conditions = []
    filters = vendor_territory_mapping.get_role_based_filters(vendor)
    model_key = (model or vendor).upper()
    column_map = TERRITORY_COLUMN_BY_VENDOR.get(model_key)
    if not column_map:
        return conditions
    for territory, value in filters.items():
        col = column_map.get(territory)
        if not col:
            continue
        cond = format_in_condition(col, value)
        if cond:
            conditions.append(cond)
    return conditions


def _value_is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def _coalesce_widget_value_and_values(item: Dict[str, Any]) -> None:
    """
    If ``value`` is empty but ``values`` is a non-empty list, normalize to a single ``value``
    or ``cond`` ``in`` + ``values``, in place.
    """
    v = item.get("value")
    vs = item.get("values")
    if not _value_is_empty(v):
        return
    if not isinstance(vs, list) or len(vs) == 0:
        return
    strs = [str(x) for x in vs if x is not None and str(x).strip() != ""]
    if not strs:
        return
    if len(strs) == 1:
        item["value"] = strs[0]
        item["cond"] = "="
        item.pop("values", None)
    else:
        item["values"] = strs
        item["cond"] = "in"
        item.pop("value", None)


def widget_filters_to_condition_strings(
    widget_filters: List[Dict[str, Any]],
) -> List[str]:
    """
    Convert normalized widget filters to the same SQL-style fragments as
    :func:`generate_session_filters` (via :func:`format_in_condition`).

    Examples: ``SAREA_CODE='384'``, ``ZONE in ('a', 'b')``.

    Reuses :func:`_coalesce_widget_value_and_values`, so ``cond: '='`` with
    multiple ``values`` becomes an ``IN`` list before formatting.
    """
    out: List[str] = []
    for raw in widget_filters or []:
        item = dict(raw)
        _coalesce_widget_value_and_values(item)
        col = str(item.get("key") or "").strip()
        if not col:
            continue
        v = item.get("value")
        vs = item.get("values")
        if isinstance(vs, list) and len(vs) > 1:
            s = format_in_condition(col, [str(x) for x in vs])
        elif isinstance(vs, list) and len(vs) == 1:
            s = format_in_condition(col, str(vs[0]))
        elif not _value_is_empty(v):
            s = format_in_condition(col, v)
        else:
            continue
        if s:
            out.append(s)
    return out


def _apply_vendor_territory_to_widget_item(
    item: Dict[str, Any], territory_type: str, vendor: str
) -> None:
    """Map filter values through vendor_territory (e.g. sales_area codes) like session filters."""
    c = str(item.get("cond") or "").lower()
    if c == "in" and isinstance(item.get("values"), list):
        mapped = vendor_territory_mapping.get_vendor_territory(
            territory_type, item["values"], vendor
        )
        if isinstance(mapped, list):
            item["values"] = [str(x) for x in mapped]
        elif mapped is not None:
            item["values"] = [str(mapped)]
    elif not _value_is_empty(item.get("value")):
        mapped = vendor_territory_mapping.get_vendor_territory(
            territory_type, item.get("value"), vendor
        )
        if isinstance(mapped, list):
            if len(mapped) == 1:
                item["value"] = str(mapped[0])
            elif len(mapped) > 1:
                item["values"] = [str(x) for x in mapped]
                item["cond"] = "in"
                item.pop("value", None)
        elif mapped is not None:
            item["value"] = str(mapped)


def normalize_widget_filters_for_model(
    widget_filters: List[Dict[str, Any]],
    vendor: str,
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Map semantic territory keys on widget filters to SQL column names (same as session path)
    and normalize ``value`` / ``values`` (e.g. empty ``value`` with ``values: ['384']``).

    Only rewrites ``key`` when it matches a territory key in ``TERRITORY_COLUMN_BY_VENDOR``
    for the given model (case-insensitive). Already-resolved column names are left unchanged.
    """
    model_key = (model or vendor).upper()
    column_map = TERRITORY_COLUMN_BY_VENDOR.get(model_key, {})
    out: List[Dict[str, Any]] = []
    for raw in widget_filters or []:
        item = dict(raw)
        _coalesce_widget_value_and_values(item)
        key = str(item.get("key") or "").strip()
        if not key:
            out.append(item)
            continue
        lk = key.lower()
        sql_col = column_map.get(lk)
        if sql_col:
            item["key"] = sql_col
            _coalesce_widget_value_and_values(item)
            _apply_vendor_territory_to_widget_item(item, lk, vendor)
        out.append(item)
    return out


def session_dict_to_widget_filters(
    session_dict: Dict[str, Any],
    column_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Convert session filter dict (territory -> value/list) to WidgetFilters format.

    Each entry becomes {"key": column_name, "cond": "=" | "in", "value": str} or
    {"key": column_name, "cond": "in", "values": list}. Used so session and request
    filters can be handled uniformly.

    :param session_dict: Dict from get_role_based_filters, e.g. {"sales_area": "X"} or {"region": ["A","B"]}.
    :param column_map: Territory type -> column name, e.g. TERRITORY_COLUMN_BY_VENDOR["IMS"].
    :return: List of filter items in WidgetFilters shape (key, cond, value or values).
    """
    out: List[Dict[str, Any]] = []
    for territory, value in session_dict.items():
        col = column_map.get(territory)
        if not col:
            continue
        if isinstance(value, list):
            if len(value) == 0:
                continue
            if len(value) == 1:
                out.append({"key": col, "cond": "=", "value": str(value[0])})
            else:
                out.append({"key": col, "cond": "in", "values": [str(v) for v in value]})
        else:
            out.append({"key": col, "cond": "=", "value": str(value)})
    return out


def get_input_filters(
    widget_filters: List[Dict[str, Any]],
    vendor: str = "IMS",
    merge_session: bool = True,
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Configure effective input filters in WidgetFilters format, optionally merging session-based filters.

    Session filters (from get_role_based_filters) are converted to the same WidgetFilters structure
    (key, cond, value or values). Session filters are applied first (role restriction), then the
    request's widget_filters (user selection). Use from ims.py (vendor="IMS") or cris.py (vendor="CRIS").

    :param widget_filters: Filters from the API request (list of {key, cond, value?/values?}).
    :param vendor: Target system for territory mapping; "IMS", "CRIS", etc.
    :param merge_session: If True, prepend session-derived filters; if False, return copy of widget_filters.
    :param model: Optional; for CRIS/NOVEX use model to pick column map; defaults to vendor.
    :return: List of filter items in WidgetFilters format.
    """
    normalized = normalize_widget_filters_for_model(
        list(widget_filters) if widget_filters else [],
        vendor=vendor,
        model=model,
    )
    if not merge_session:
        return normalized

    session_dict = vendor_territory_mapping.get_role_based_filters(vendor)
    if not session_dict:
        return normalized

    model_key = (model or vendor).upper()
    column_map = TERRITORY_COLUMN_BY_VENDOR.get(model_key, {})
    session_as_widgets = session_dict_to_widget_filters(session_dict, column_map)
    return session_as_widgets + normalized
