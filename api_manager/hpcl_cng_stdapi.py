import urdhva_base.postgresmodel
import urdhva_base.queryparams
import urdhva_base.types
from hpcl_cng_enum import *
from hpcl_cng_model import *
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


@router.get('/roassetmaster/{id}', response_model=ROAssetMaster, tags=['ROAssetMaster'])
async def get(id: str):
    return await ROAssetMaster.get(id, skip_secrets=True)


@router.get('/roassetmaster', response_model=ROAssetMasterGetResp, tags=['ROAssetMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await ROAssetMaster.get_all(params, skip_secrets=True)


@router.get('/tasassetmaster/{id}', response_model=TASAssetMaster, tags=['TASAssetMaster'])
async def get(id: str):
    return await TASAssetMaster.get(id, skip_secrets=True)


@router.get('/tasassetmaster', response_model=TASAssetMasterGetResp, tags=['TASAssetMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await TASAssetMaster.get_all(params, skip_secrets=True)


@router.get('/lpgassetmaster/{id}', response_model=LPGAssetMaster, tags=['LPGAssetMaster'])
async def get(id: str):
    return await LPGAssetMaster.get(id, skip_secrets=True)


@router.get('/lpgassetmaster', response_model=LPGAssetMasterGetResp, tags=['LPGAssetMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LPGAssetMaster.get_all(params, skip_secrets=True)


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


@router.get('/locationdevice/{id}', response_model=LocationDevice, tags=['LocationDevice'])
async def get(id: str):
    return await LocationDevice.get(id, skip_secrets=True)


@router.get('/locationdevice', response_model=LocationDeviceGetResp, tags=['LocationDevice'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LocationDevice.get_all(params, skip_secrets=True)

