from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
from orchestrator.tas_analytics import tas_analytics_action 

router = fastapi.APIRouter(prefix='/tasanalytics')


# Action tas_analytics
@router.post('/tas_analytics', tags=['TasAnalytics'])
async def tasanalytics_tas_analytics(data: Tasanalytics_Tas_AnalyticsParams):

    return await tas_analytics_action(data)
