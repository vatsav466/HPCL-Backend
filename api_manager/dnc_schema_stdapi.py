import urdhva_base.postgresmodel
import urdhva_base.queryparams
import urdhva_base.types
from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi
router = fastapi.APIRouter()


@router.get('/locationmaster/{id}', response_model=LocationMaster, tags=['LocationMaster'])
async def get(id: str):
    return await LocationMaster.get(id, skip_secrets=True)


@router.get('/locationmaster', response_model=LocationMasterGetResp, tags=['LocationMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LocationMaster.get_all(params, skip_secrets=True)


@router.get('/rolemaster/{id}', response_model=RoleMaster, tags=['RoleMaster'])
async def get(id: str):
    return await RoleMaster.get(id, skip_secrets=True)


@router.get('/rolemaster', response_model=RoleMasterGetResp, tags=['RoleMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await RoleMaster.get_all(params, skip_secrets=True)


@router.get('/assetmaster/{id}', response_model=AssetMaster, tags=['AssetMaster'])
async def get(id: str):
    return await AssetMaster.get(id, skip_secrets=True)


@router.get('/assetmaster', response_model=AssetMasterGetResp, tags=['AssetMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await AssetMaster.get_all(params, skip_secrets=True)


@router.post('/assetdata', response_model=assetData, tags=['assetData'])
async def create(inputObj: assetDataCreate):
    return await inputObj.create()


@router.put('/assetdata', response_model=assetData, tags=['assetData'])
async def update(inputObj: assetData):
    return await inputObj.modify()


@router.get('/assetdata/{id}', response_model=assetData, tags=['assetData'])
async def get(id: str):
    return await assetData.get(id, skip_secrets=True)


@router.get('/assetdata', response_model=assetDataGetResp, tags=['assetData'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await assetData.get_all(params, skip_secrets=True)


@router.delete('/assetdata/{id}', tags=['assetData'])
async def delete(id: str):
    return await assetData.delete(id)


@router.get('/alerts/{id}', response_model=Alerts, tags=['Alerts'])
async def get(id: str):
    return await Alerts.get(id, skip_secrets=True)


@router.get('/alerts', response_model=AlertsGetResp, tags=['Alerts'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await Alerts.get_all(params, skip_secrets=True)













