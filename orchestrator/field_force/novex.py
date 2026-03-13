"""
Novex - Field Force orchestrator (Dry-Out under Novex).
Functional schema for DryOutManagement APIs. No implementation.
"""
import field_force_model
from typing import List, Optional

# dry_out_type in data (WidgetFiltersCreate): 0 = dry-out, 1 = Intra dry-out

async def get_dry_out_locations(
    data: field_force_model.WidgetFiltersCreate,
    by_product: bool = False,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
):
    """
    Total dry-out locations; optionally by product. Drill-down to locations.

    Input:
        data: field_force_model.WidgetFiltersCreate (include dry_out_type: 0 or 1 as filter if needed).
        by_product: if True, break summary by product.
        drill_filter: optional {"drill_to": "locations"}.
    Output:
        {"summary": [{"location_id"?, "product_code"?, "dry_out_count", "dry_out_type", ...}],
         "drill_down": [{"location_id", "location_name", "product_code", "dry_out_date", ...}] or None,
         "total": int?, "drill_to": str?, "by_product": bool}
    """
    pass


async def get_dry_out_indent_analysis(
    data: field_force_model.WidgetFiltersCreate,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
):
    """
    Dry-out indent analysis: with indent / without indent by product;
    Pending vs Executed. Drill-down to locations.

    Input:
        data: field_force_model.WidgetFiltersCreate.
        drill_filter: optional {"drill_to": "locations"}.
    Output:
        {"summary": [{"product_code", "with_indent_count", "without_indent_count",
                     "pending_count", "executed_count", "volume", ...}],
         "drill_down": [{"location_id", "location_name", "product_code", "has_indent", "status", ...}] or None,
         "total": int?, "drill_to": str?}
    """
    pass


async def get_dry_out_indents(
    data: field_force_model.WidgetFiltersCreate,
    drill_filter: Optional[field_force_model.DrillFilterCreate] = None,
):
    """
    Backward-compatible: same as get_dry_out_indent_analysis.
    Dry-out indents analysis with optional drill-down.

    Input:
        data: field_force_model.WidgetFiltersCreate.
        drill_filter: optional DrillFilter.
    Output:
        Same as get_dry_out_indent_analysis.
    """
    pass
