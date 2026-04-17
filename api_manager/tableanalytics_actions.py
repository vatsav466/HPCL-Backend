from hpcl_ceg_model import *
import fastapi
import ast
import orchestrator.analytics.aggregate_query_gateway as query_aggregate_gateway
import orchestrator.analytics.session_filters as session_filters

router = fastapi.APIRouter(prefix='/tableanalytics')

# Session territory filters are always merged (not exposed on the API model). Adjust here if needed.
_TABLEANALYTICS_SESSION_VENDOR = "NOVEX"
_TABLEANALYTICS_SESSION_MODEL = None  # None → same column map as vendor
_TABLEANALYTICS_SESSION_COLUMN_PREFIX = "loc"  # joined table alias for NOVEX columns (region, zone, etc.)


def _apply_tableanalytics_session_filters(data: dict) -> None:
    """Always merge role-based territory filters into ``filters`` (``TERRITORY_COLUMN_BY_VENDOR``)."""
    session_f = session_filters.session_territory_filters_for_gateway(
        vendor=_TABLEANALYTICS_SESSION_VENDOR,
        model=_TABLEANALYTICS_SESSION_MODEL,
        column_name_prefix=_TABLEANALYTICS_SESSION_COLUMN_PREFIX,
    )
    user_f = data.get("filters") or {}
    data["filters"] = session_filters.merge_user_filters_with_session(user_f, session_f)


# Action generate_data_aggregations
@router.post('/generate_data_aggregations', tags=['TableAnalytics'])
async def tableanalytics_generate_data_aggregations(data: Tableanalytics_Generate_Data_AggregationsParams):
    data = data.model_dump()
    if data.get('group_by'):
        for index, rec in enumerate(data['group_by']):
            try:
                dec = ast.literal_eval(rec)
                if len(dec) > 1:
                    data['group_by'][index] = dec
            except Exception as e:
                print(e)
    _apply_tableanalytics_session_filters(data)
    return await query_aggregate_gateway.query_aggregate_gateway(**data)
