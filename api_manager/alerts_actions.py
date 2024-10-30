from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi

router = fastapi.APIRouter(prefix='/alerts')


# Action justification
@router.post('/justification', tags=['Alerts'])
async def alerts_justification(data: Alerts_JustificationParams):
    ...


# Action reject
@router.post('/reject', tags=['Alerts'])
async def alerts_reject(data: Alerts_RejectParams):
    ...


# Action approve
@router.post('/approve', tags=['Alerts'])
async def alerts_approve(data: Alerts_ApproveParams):
    ...


# Action override
@router.post('/override', tags=['Alerts'])
async def alerts_override(data: Alerts_OverrideParams):
    ...
