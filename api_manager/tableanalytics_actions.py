from hpcl_ceg_model import *
import fastapi
import ast
import orchestrator.analytics.aggregate_query_gateway as query_aggregate_gateway
router = fastapi.APIRouter(prefix='/tableanalytics')


# Action generate_data_aggregations
@router.post('/generate_data_aggregations', tags=['TableAnalytics'])
async def tableanalytics_generate_data_aggregations(data: Tableanalytics_Generate_Data_AggregationsParams):
    data = data.model_dump()
    if data.get('group_by'):
        for index, rec in enumerate(data['group_by']):
            print(rec)
            try:
                dec = ast.literal_eval(rec)
                if len(dec) > 1:
                    data['group_by'][index] = dec
            except Exception as e:
                print(e)
    return await query_aggregate_gateway.query_aggregate_gateway(**data)
