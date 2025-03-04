from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
from orchestrator.analytics.performance_index import tas_performance_index
from orchestrator.analytics.performance_index import lpg_performance_index

router = fastapi.APIRouter(prefix='/performanceindex')


# Action get_pi_score
@router.post('/get_pi_score', tags=['PerformanceIndex'])
async def performanceindex_get_pi_score(data: Performanceindex_Get_Pi_ScoreParams):
    if data.bu == "TAS":
        tas_pi = tas_performance_index.TASPerformanceIndex()
        await tas_pi.initialize()  # Load rules_df asynchronously
        tas_resp = await tas_pi.generate_performance_index_tas(data.sap_id)
        return {"tas_performance": tas_resp}

    elif data.bu == "LPG":
        lpg_pi = lpg_performance_index.LPGPerformanceIndex()
        await lpg_pi.initialize()  # Load rules_df asynchronously
        lpg_resp = await lpg_pi.generate_performance_index_lpg(data.sap_id)
        return {"lpg_performance": lpg_resp}



# Action get_pi_score_by_category
@router.post('/get_pi_score_by_category', tags=['PerformanceIndex'])
async def performanceindex_get_pi_score_by_category(data: Performanceindex_Get_Pi_Score_By_CategoryParams):
    ...
