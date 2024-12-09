import urdhva_base.postgresmodel
import urdhva_base.queryparams
import urdhva_base.types
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
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


@router.get('/interlock/{id}', response_model=Interlock, tags=['Interlock'])
async def get(id: str):
    return await Interlock.get(id, skip_secrets=True)


@router.get('/interlock', response_model=InterlockGetResp, tags=['Interlock'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await Interlock.get_all(params, skip_secrets=True)


@router.get('/emlock/{id}', response_model=EMLock, tags=['EMLock'])
async def get(id: str):
    return await EMLock.get(id, skip_secrets=True)


@router.get('/emlock', response_model=EMLockGetResp, tags=['EMLock'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await EMLock.get_all(params, skip_secrets=True)


@router.get('/vts/{id}', response_model=VTS, tags=['VTS'])
async def get(id: str):
    return await VTS.get(id, skip_secrets=True)


@router.get('/vts', response_model=VTSGetResp, tags=['VTS'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await VTS.get_all(params, skip_secrets=True)


@router.get('/alerts/{id}', response_model=Alerts, tags=['Alerts'])
async def get(id: str):
    return await Alerts.get(id, skip_secrets=True)


@router.get('/alerts', response_model=AlertsGetResp, tags=['Alerts'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await Alerts.get_all(params, skip_secrets=True)


@router.post('/cemslocationmaster', response_model=CEMSLocationMaster, tags=['CEMSLocationMaster'])
async def create(inputObj: CEMSLocationMasterCreate):
    return await inputObj.create()


@router.put('/cemslocationmaster', response_model=CEMSLocationMaster, tags=['CEMSLocationMaster'])
async def update(inputObj: CEMSLocationMaster):
    return await inputObj.modify()


@router.get('/cemslocationmaster/{id}', response_model=CEMSLocationMaster, tags=['CEMSLocationMaster'])
async def get(id: str):
    return await CEMSLocationMaster.get(id, skip_secrets=True)


@router.get('/cemslocationmaster', response_model=CEMSLocationMasterGetResp, tags=['CEMSLocationMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await CEMSLocationMaster.get_all(params, skip_secrets=True)


@router.delete('/cemslocationmaster/{id}', tags=['CEMSLocationMaster'])
async def delete(id: str):
    return await CEMSLocationMaster.delete(id)


@router.post('/cemsquantitymaster', response_model=CEMSQuantityMaster, tags=['CEMSQuantityMaster'])
async def create(inputObj: CEMSQuantityMasterCreate):
    return await inputObj.create()


@router.put('/cemsquantitymaster', response_model=CEMSQuantityMaster, tags=['CEMSQuantityMaster'])
async def update(inputObj: CEMSQuantityMaster):
    return await inputObj.modify()


@router.get('/cemsquantitymaster/{id}', response_model=CEMSQuantityMaster, tags=['CEMSQuantityMaster'])
async def get(id: str):
    return await CEMSQuantityMaster.get(id, skip_secrets=True)


@router.get('/cemsquantitymaster', response_model=CEMSQuantityMasterGetResp, tags=['CEMSQuantityMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await CEMSQuantityMaster.get_all(params, skip_secrets=True)


@router.delete('/cemsquantitymaster/{id}', tags=['CEMSQuantityMaster'])
async def delete(id: str):
    return await CEMSQuantityMaster.delete(id)


@router.post('/credsmodel', response_model=CredsModel, tags=['CredsModel'])
async def create(inputObj: CredsModelCreate):
    return await inputObj.create()


@router.put('/credsmodel', response_model=CredsModel, tags=['CredsModel'])
async def update(inputObj: CredsModel):
    return await inputObj.modify()


@router.get('/credsmodel/{id}', response_model=CredsModel, tags=['CredsModel'])
async def get(id: str):
    return await CredsModel.get(id, skip_secrets=True)


@router.get('/credsmodel', response_model=CredsModelGetResp, tags=['CredsModel'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await CredsModel.get_all(params, skip_secrets=True)


@router.delete('/credsmodel/{id}', tags=['CredsModel'])
async def delete(id: str):
    return await CredsModel.delete(id)


@router.post('/indentdryout', response_model=IndentDryOut, tags=['IndentDryOut'])
async def create(inputObj: IndentDryOutCreate):
    return await inputObj.create()


@router.put('/indentdryout', response_model=IndentDryOut, tags=['IndentDryOut'])
async def update(inputObj: IndentDryOut):
    return await inputObj.modify()


@router.get('/indentdryout/{id}', response_model=IndentDryOut, tags=['IndentDryOut'])
async def get(id: str):
    return await IndentDryOut.get(id, skip_secrets=True)


@router.get('/indentdryout', response_model=IndentDryOutGetResp, tags=['IndentDryOut'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await IndentDryOut.get_all(params, skip_secrets=True)


@router.delete('/indentdryout/{id}', tags=['IndentDryOut'])
async def delete(id: str):
    return await IndentDryOut.delete(id)


@router.post('/screens', response_model=Screens, tags=['Screens'])
async def create(inputObj: ScreensCreate):
    return await inputObj.create()


@router.put('/screens', response_model=Screens, tags=['Screens'])
async def update(inputObj: Screens):
    return await inputObj.modify()


@router.get('/screens/{id}', response_model=Screens, tags=['Screens'])
async def get(id: str):
    return await Screens.get(id, skip_secrets=True)


@router.get('/screens', response_model=ScreensGetResp, tags=['Screens'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await Screens.get_all(params, skip_secrets=True)


@router.delete('/screens/{id}', tags=['Screens'])
async def delete(id: str):
    return await Screens.delete(id)