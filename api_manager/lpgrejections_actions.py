from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/lpgrejections')


# Action get_cs_rejections
@router.post('/get_cs_rejections', tags=['LpgRejections'])
async def lpgrejections_get_cs_rejections(data: Lpgrejections_Get_Cs_RejectionsParams):
    ...


# Action get_gd_rejections
@router.post('/get_gd_rejections', tags=['LpgRejections'])
async def lpgrejections_get_gd_rejections(data: Lpgrejections_Get_Gd_RejectionsParams):
    ...


# Action get_pt_rejections
@router.post('/get_pt_rejections', tags=['LpgRejections'])
async def lpgrejections_get_pt_rejections(data: Lpgrejections_Get_Pt_RejectionsParams):
    ...
