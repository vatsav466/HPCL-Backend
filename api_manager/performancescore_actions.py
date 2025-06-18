from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/performancescore')


# Action get_pi_score
@router.post('/get_pi_score', tags=['PerformanceScore'])
async def performancescore_get_pi_score(data: Performancescore_Get_Pi_ScoreParams):
    ...
