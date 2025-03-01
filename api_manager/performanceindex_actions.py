from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
from orchestrator.analytics.performance_index import tas_performance_index

router = fastapi.APIRouter(prefix='/performanceindex')


# Action get_pi_score
@router.post('/get_pi_score', tags=['PerformanceIndex'])
async def performanceindex_get_pi_score(data: Performanceindex_Get_Pi_ScoreParams):
    tas_pi = tas_performance_index.TASPerformanceIndex()  # Create instance
    await tas_pi.initialize()       # Load rules_df asynchronously
    resp = await tas_pi.generate_performance_index_tas(data.sap_id)
    return resp


# Action get_pi_score_by_category
@router.post('/get_pi_score_by_category', tags=['PerformanceIndex'])
async def performanceindex_get_pi_score_by_category(data: Performanceindex_Get_Pi_Score_By_CategoryParams):
    ...
