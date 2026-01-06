import urdhva_base.postgresmodel
import urdhva_base.queryparams
import urdhva_base.types
from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi
router = fastapi.APIRouter()


@router.post('/tasagentcommstatus', response_model=TasAgentCommStatus, tags=['TasAgentCommStatus'])
async def create(inputObj: TasAgentCommStatusCreate):
    return await inputObj.create()


@router.put('/tasagentcommstatus', response_model=TasAgentCommStatus, tags=['TasAgentCommStatus'])
async def update(inputObj: TasAgentCommStatus):
    return await inputObj.modify()


@router.get('/tasagentcommstatus/{id}', response_model=TasAgentCommStatus, tags=['TasAgentCommStatus'])
async def get(id: str):
    return await TasAgentCommStatus.get(id, skip_secrets=True)


@router.get('/tasagentcommstatus', response_model=TasAgentCommStatusGetResp, tags=['TasAgentCommStatus'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await TasAgentCommStatus.get_all(params, skip_secrets=True)


@router.delete('/tasagentcommstatus/{id}', tags=['TasAgentCommStatus'])
async def delete(id: str):
    return await TasAgentCommStatus.delete(id)


@router.post('/tasagentservicestatus', response_model=TasAgentServiceStatus, tags=['TasAgentServiceStatus'])
async def create(inputObj: TasAgentServiceStatusCreate):
    return await inputObj.create()


@router.put('/tasagentservicestatus', response_model=TasAgentServiceStatus, tags=['TasAgentServiceStatus'])
async def update(inputObj: TasAgentServiceStatus):
    return await inputObj.modify()


@router.get('/tasagentservicestatus/{id}', response_model=TasAgentServiceStatus, tags=['TasAgentServiceStatus'])
async def get(id: str):
    return await TasAgentServiceStatus.get(id, skip_secrets=True)


@router.get('/tasagentservicestatus', response_model=TasAgentServiceStatusGetResp, tags=['TasAgentServiceStatus'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await TasAgentServiceStatus.get_all(params, skip_secrets=True)


@router.delete('/tasagentservicestatus/{id}', tags=['TasAgentServiceStatus'])
async def delete(id: str):
    return await TasAgentServiceStatus.delete(id)











