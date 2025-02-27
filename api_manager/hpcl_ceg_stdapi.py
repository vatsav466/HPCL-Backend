import urdhva_base.postgresmodel
import urdhva_base.queryparams
import urdhva_base.types
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
router = fastapi.APIRouter()


@router.get('/roles/{id}', response_model=Roles, tags=['Roles'])
async def get(id: str):
    return await Roles.get(id, skip_secrets=True)


@router.get('/roles', response_model=RolesGetResp, tags=['Roles'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await Roles.get_all(params, skip_secrets=True)


@router.get('/users/{id}', response_model=Users, tags=['Users'])
async def get(id: str):
    return await Users.get(id, skip_secrets=True)


@router.get('/users', response_model=UsersGetResp, tags=['Users'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await Users.get_all(params, skip_secrets=True)


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


@router.get('/dryouthistory/{id}', response_model=DryOutHistory, tags=['DryOutHistory'])
async def get(id: str):
    return await DryOutHistory.get(id, skip_secrets=True)


@router.get('/dryouthistory', response_model=DryOutHistoryGetResp, tags=['DryOutHistory'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await DryOutHistory.get_all(params, skip_secrets=True)


@router.post('/carryfwdindent', response_model=CarryFwdIndent, tags=['CarryFwdIndent'])
async def create(inputObj: CarryFwdIndentCreate):
    return await inputObj.create()


@router.put('/carryfwdindent', response_model=CarryFwdIndent, tags=['CarryFwdIndent'])
async def update(inputObj: CarryFwdIndent):
    return await inputObj.modify()


@router.get('/carryfwdindent/{id}', response_model=CarryFwdIndent, tags=['CarryFwdIndent'])
async def get(id: str):
    return await CarryFwdIndent.get(id, skip_secrets=True)


@router.get('/carryfwdindent', response_model=CarryFwdIndentGetResp, tags=['CarryFwdIndent'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await CarryFwdIndent.get_all(params, skip_secrets=True)


@router.delete('/carryfwdindent/{id}', tags=['CarryFwdIndent'])
async def delete(id: str):
    return await CarryFwdIndent.delete(id)


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


@router.post('/lpgoperationssummary', response_model=LpgOperationsSummary, tags=['LpgOperationsSummary'])
async def create(inputObj: LpgOperationsSummaryCreate):
    return await inputObj.create()


@router.put('/lpgoperationssummary', response_model=LpgOperationsSummary, tags=['LpgOperationsSummary'])
async def update(inputObj: LpgOperationsSummary):
    return await inputObj.modify()


@router.get('/lpgoperationssummary/{id}', response_model=LpgOperationsSummary, tags=['LpgOperationsSummary'])
async def get(id: str):
    return await LpgOperationsSummary.get(id, skip_secrets=True)


@router.get('/lpgoperationssummary', response_model=LpgOperationsSummaryGetResp, tags=['LpgOperationsSummary'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LpgOperationsSummary.get_all(params, skip_secrets=True)


@router.delete('/lpgoperationssummary/{id}', tags=['LpgOperationsSummary'])
async def delete(id: str):
    return await LpgOperationsSummary.delete(id)


@router.post('/lpgcsrejections', response_model=LpgCsRejections, tags=['LpgCsRejections'])
async def create(inputObj: LpgCsRejectionsCreate):
    return await inputObj.create()


@router.put('/lpgcsrejections', response_model=LpgCsRejections, tags=['LpgCsRejections'])
async def update(inputObj: LpgCsRejections):
    return await inputObj.modify()


@router.get('/lpgcsrejections/{id}', response_model=LpgCsRejections, tags=['LpgCsRejections'])
async def get(id: str):
    return await LpgCsRejections.get(id, skip_secrets=True)


@router.get('/lpgcsrejections', response_model=LpgCsRejectionsGetResp, tags=['LpgCsRejections'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LpgCsRejections.get_all(params, skip_secrets=True)


@router.delete('/lpgcsrejections/{id}', tags=['LpgCsRejections'])
async def delete(id: str):
    return await LpgCsRejections.delete(id)


@router.post('/lpggdrejections', response_model=LpgGdRejections, tags=['LpgGdRejections'])
async def create(inputObj: LpgGdRejectionsCreate):
    return await inputObj.create()


@router.put('/lpggdrejections', response_model=LpgGdRejections, tags=['LpgGdRejections'])
async def update(inputObj: LpgGdRejections):
    return await inputObj.modify()


@router.get('/lpggdrejections/{id}', response_model=LpgGdRejections, tags=['LpgGdRejections'])
async def get(id: str):
    return await LpgGdRejections.get(id, skip_secrets=True)


@router.get('/lpggdrejections', response_model=LpgGdRejectionsGetResp, tags=['LpgGdRejections'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LpgGdRejections.get_all(params, skip_secrets=True)


@router.delete('/lpggdrejections/{id}', tags=['LpgGdRejections'])
async def delete(id: str):
    return await LpgGdRejections.delete(id)


@router.post('/lpgptrejections', response_model=LpgPtRejections, tags=['LpgPtRejections'])
async def create(inputObj: LpgPtRejectionsCreate):
    return await inputObj.create()


@router.put('/lpgptrejections', response_model=LpgPtRejections, tags=['LpgPtRejections'])
async def update(inputObj: LpgPtRejections):
    return await inputObj.modify()


@router.get('/lpgptrejections/{id}', response_model=LpgPtRejections, tags=['LpgPtRejections'])
async def get(id: str):
    return await LpgPtRejections.get(id, skip_secrets=True)


@router.get('/lpgptrejections', response_model=LpgPtRejectionsGetResp, tags=['LpgPtRejections'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LpgPtRejections.get_all(params, skip_secrets=True)


@router.delete('/lpgptrejections/{id}', tags=['LpgPtRejections'])
async def delete(id: str):
    return await LpgPtRejections.delete(id)


@router.post('/lpgrejections', response_model=LpgRejections, tags=['LpgRejections'])
async def create(inputObj: LpgRejectionsCreate):
    return await inputObj.create()


@router.put('/lpgrejections', response_model=LpgRejections, tags=['LpgRejections'])
async def update(inputObj: LpgRejections):
    return await inputObj.modify()


@router.get('/lpgrejections/{id}', response_model=LpgRejections, tags=['LpgRejections'])
async def get(id: str):
    return await LpgRejections.get(id, skip_secrets=True)


@router.get('/lpgrejections', response_model=LpgRejectionsGetResp, tags=['LpgRejections'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LpgRejections.get_all(params, skip_secrets=True)


@router.delete('/lpgrejections/{id}', tags=['LpgRejections'])
async def delete(id: str):
    return await LpgRejections.delete(id)


@router.post('/lpgsalessummarydata', response_model=LpgSalesSummaryData, tags=['LpgSalesSummaryData'])
async def create(inputObj: LpgSalesSummaryDataCreate):
    return await inputObj.create()


@router.put('/lpgsalessummarydata', response_model=LpgSalesSummaryData, tags=['LpgSalesSummaryData'])
async def update(inputObj: LpgSalesSummaryData):
    return await inputObj.modify()


@router.get('/lpgsalessummarydata/{id}', response_model=LpgSalesSummaryData, tags=['LpgSalesSummaryData'])
async def get(id: str):
    return await LpgSalesSummaryData.get(id, skip_secrets=True)


@router.get('/lpgsalessummarydata', response_model=LpgSalesSummaryDataGetResp, tags=['LpgSalesSummaryData'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LpgSalesSummaryData.get_all(params, skip_secrets=True)


@router.delete('/lpgsalessummarydata/{id}', tags=['LpgSalesSummaryData'])
async def delete(id: str):
    return await LpgSalesSummaryData.delete(id)


@router.post('/lpgconsumerssummary', response_model=LpgConsumersSummary, tags=['LpgConsumersSummary'])
async def create(inputObj: LpgConsumersSummaryCreate):
    return await inputObj.create()


@router.put('/lpgconsumerssummary', response_model=LpgConsumersSummary, tags=['LpgConsumersSummary'])
async def update(inputObj: LpgConsumersSummary):
    return await inputObj.modify()


@router.get('/lpgconsumerssummary/{id}', response_model=LpgConsumersSummary, tags=['LpgConsumersSummary'])
async def get(id: str):
    return await LpgConsumersSummary.get(id, skip_secrets=True)


@router.get('/lpgconsumerssummary', response_model=LpgConsumersSummaryGetResp, tags=['LpgConsumersSummary'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LpgConsumersSummary.get_all(params, skip_secrets=True)


@router.delete('/lpgconsumerssummary/{id}', tags=['LpgConsumersSummary'])
async def delete(id: str):
    return await LpgConsumersSummary.delete(id)


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


@router.get('/devicemaster/{id}', response_model=DeviceMaster, tags=['DeviceMaster'])
async def get(id: str):
    return await DeviceMaster.get(id, skip_secrets=True)


@router.get('/devicemaster', response_model=DeviceMasterGetResp, tags=['DeviceMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await DeviceMaster.get_all(params, skip_secrets=True)


@router.get('/vtsalerthistory/{id}', response_model=VtsAlertHistory, tags=['VtsAlertHistory'])
async def get(id: str):
    return await VtsAlertHistory.get(id, skip_secrets=True)


@router.get('/vtsalerthistory', response_model=VtsAlertHistoryGetResp, tags=['VtsAlertHistory'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await VtsAlertHistory.get_all(params, skip_secrets=True)


@router.get('/emlockalerthistory/{id}', response_model=EmLockAlertHistory, tags=['EmLockAlertHistory'])
async def get(id: str):
    return await EmLockAlertHistory.get(id, skip_secrets=True)


@router.get('/emlockalerthistory', response_model=EmLockAlertHistoryGetResp, tags=['EmLockAlertHistory'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await EmLockAlertHistory.get_all(params, skip_secrets=True)


@router.get('/vaalerthistory/{id}', response_model=VaAlertHistory, tags=['VaAlertHistory'])
async def get(id: str):
    return await VaAlertHistory.get(id, skip_secrets=True)


@router.get('/vaalerthistory', response_model=VaAlertHistoryGetResp, tags=['VaAlertHistory'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await VaAlertHistory.get_all(params, skip_secrets=True)


@router.post('/m60levelmetadata', response_model=M60LevelMetaData, tags=['M60LevelMetaData'])
async def create(inputObj: M60LevelMetaDataCreate):
    return await inputObj.create()


@router.put('/m60levelmetadata', response_model=M60LevelMetaData, tags=['M60LevelMetaData'])
async def update(inputObj: M60LevelMetaData):
    return await inputObj.modify()


@router.get('/m60levelmetadata/{id}', response_model=M60LevelMetaData, tags=['M60LevelMetaData'])
async def get(id: str):
    return await M60LevelMetaData.get(id, skip_secrets=True)


@router.get('/m60levelmetadata', response_model=M60LevelMetaDataGetResp, tags=['M60LevelMetaData'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await M60LevelMetaData.get_all(params, skip_secrets=True)


@router.delete('/m60levelmetadata/{id}', tags=['M60LevelMetaData'])
async def delete(id: str):
    return await M60LevelMetaData.delete(id)


@router.post('/momlevelfinalmetadata', response_model=MomLevelFinalMetaData, tags=['MomLevelFinalMetaData'])
async def create(inputObj: MomLevelFinalMetaDataCreate):
    return await inputObj.create()


@router.put('/momlevelfinalmetadata', response_model=MomLevelFinalMetaData, tags=['MomLevelFinalMetaData'])
async def update(inputObj: MomLevelFinalMetaData):
    return await inputObj.modify()


@router.get('/momlevelfinalmetadata/{id}', response_model=MomLevelFinalMetaData, tags=['MomLevelFinalMetaData'])
async def get(id: str):
    return await MomLevelFinalMetaData.get(id, skip_secrets=True)


@router.get('/momlevelfinalmetadata', response_model=MomLevelFinalMetaDataGetResp, tags=['MomLevelFinalMetaData'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await MomLevelFinalMetaData.get_all(params, skip_secrets=True)


@router.delete('/momlevelfinalmetadata/{id}', tags=['MomLevelFinalMetaData'])
async def delete(id: str):
    return await MomLevelFinalMetaData.delete(id)


@router.post('/industryperformance', response_model=IndustryPerformance, tags=['IndustryPerformance'])
async def create(inputObj: IndustryPerformanceCreate):
    return await inputObj.create()


@router.put('/industryperformance', response_model=IndustryPerformance, tags=['IndustryPerformance'])
async def update(inputObj: IndustryPerformance):
    return await inputObj.modify()


@router.get('/industryperformance/{id}', response_model=IndustryPerformance, tags=['IndustryPerformance'])
async def get(id: str):
    return await IndustryPerformance.get(id, skip_secrets=True)


@router.get('/industryperformance', response_model=IndustryPerformanceGetResp, tags=['IndustryPerformance'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await IndustryPerformance.get_all(params, skip_secrets=True)


@router.delete('/industryperformance/{id}', tags=['IndustryPerformance'])
async def delete(id: str):
    return await IndustryPerformance.delete(id)


@router.post('/consumerpumptankdelivery', response_model=ConsumerPumpTankDelivery, tags=['ConsumerPumpTankDelivery'])
async def create(inputObj: ConsumerPumpTankDeliveryCreate):
    return await inputObj.create()


@router.put('/consumerpumptankdelivery', response_model=ConsumerPumpTankDelivery, tags=['ConsumerPumpTankDelivery'])
async def update(inputObj: ConsumerPumpTankDelivery):
    return await inputObj.modify()


@router.get('/consumerpumptankdelivery/{id}', response_model=ConsumerPumpTankDelivery, tags=['ConsumerPumpTankDelivery'])
async def get(id: str):
    return await ConsumerPumpTankDelivery.get(id, skip_secrets=True)


@router.get('/consumerpumptankdelivery', response_model=ConsumerPumpTankDeliveryGetResp, tags=['ConsumerPumpTankDelivery'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await ConsumerPumpTankDelivery.get_all(params, skip_secrets=True)


@router.delete('/consumerpumptankdelivery/{id}', tags=['ConsumerPumpTankDelivery'])
async def delete(id: str):
    return await ConsumerPumpTankDelivery.delete(id)


@router.post('/consumperpumptransaction', response_model=ConsumperPumpTransaction, tags=['ConsumperPumpTransaction'])
async def create(inputObj: ConsumperPumpTransactionCreate):
    return await inputObj.create()


@router.put('/consumperpumptransaction', response_model=ConsumperPumpTransaction, tags=['ConsumperPumpTransaction'])
async def update(inputObj: ConsumperPumpTransaction):
    return await inputObj.modify()


@router.get('/consumperpumptransaction/{id}', response_model=ConsumperPumpTransaction, tags=['ConsumperPumpTransaction'])
async def get(id: str):
    return await ConsumperPumpTransaction.get(id, skip_secrets=True)


@router.get('/consumperpumptransaction', response_model=ConsumperPumpTransactionGetResp, tags=['ConsumperPumpTransaction'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await ConsumperPumpTransaction.get_all(params, skip_secrets=True)


@router.delete('/consumperpumptransaction/{id}', tags=['ConsumperPumpTransaction'])
async def delete(id: str):
    return await ConsumperPumpTransaction.delete(id)


@router.get('/bulevelgeocoordinates/{id}', response_model=BuLevelGeoCoordinates, tags=['BuLevelGeoCoordinates'])
async def get(id: str):
    return await BuLevelGeoCoordinates.get(id, skip_secrets=True)


@router.get('/bulevelgeocoordinates', response_model=BuLevelGeoCoordinatesGetResp, tags=['BuLevelGeoCoordinates'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await BuLevelGeoCoordinates.get_all(params, skip_secrets=True)


@router.post('/lpgsubsidyexceptiondata', response_model=LpgSubsidyExceptionData, tags=['LpgSubsidyExceptionData'])
async def create(inputObj: LpgSubsidyExceptionDataCreate):
    return await inputObj.create()


@router.put('/lpgsubsidyexceptiondata', response_model=LpgSubsidyExceptionData, tags=['LpgSubsidyExceptionData'])
async def update(inputObj: LpgSubsidyExceptionData):
    return await inputObj.modify()


@router.get('/lpgsubsidyexceptiondata/{id}', response_model=LpgSubsidyExceptionData, tags=['LpgSubsidyExceptionData'])
async def get(id: str):
    return await LpgSubsidyExceptionData.get(id, skip_secrets=True)


@router.get('/lpgsubsidyexceptiondata', response_model=LpgSubsidyExceptionDataGetResp, tags=['LpgSubsidyExceptionData'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LpgSubsidyExceptionData.get_all(params, skip_secrets=True)


@router.delete('/lpgsubsidyexceptiondata/{id}', tags=['LpgSubsidyExceptionData'])
async def delete(id: str):
    return await LpgSubsidyExceptionData.delete(id)


@router.post('/lpgsubsidyfailuredata', response_model=LpgSubsidyFailureData, tags=['LpgSubsidyFailureData'])
async def create(inputObj: LpgSubsidyFailureDataCreate):
    return await inputObj.create()


@router.put('/lpgsubsidyfailuredata', response_model=LpgSubsidyFailureData, tags=['LpgSubsidyFailureData'])
async def update(inputObj: LpgSubsidyFailureData):
    return await inputObj.modify()


@router.get('/lpgsubsidyfailuredata/{id}', response_model=LpgSubsidyFailureData, tags=['LpgSubsidyFailureData'])
async def get(id: str):
    return await LpgSubsidyFailureData.get(id, skip_secrets=True)


@router.get('/lpgsubsidyfailuredata', response_model=LpgSubsidyFailureDataGetResp, tags=['LpgSubsidyFailureData'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LpgSubsidyFailureData.get_all(params, skip_secrets=True)


@router.delete('/lpgsubsidyfailuredata/{id}', tags=['LpgSubsidyFailureData'])
async def delete(id: str):
    return await LpgSubsidyFailureData.delete(id)


@router.post('/lpgoperationsrejections', response_model=LpgOperationsRejections, tags=['LpgOperationsRejections'])
async def create(inputObj: LpgOperationsRejectionsCreate):
    return await inputObj.create()


@router.put('/lpgoperationsrejections', response_model=LpgOperationsRejections, tags=['LpgOperationsRejections'])
async def update(inputObj: LpgOperationsRejections):
    return await inputObj.modify()


@router.get('/lpgoperationsrejections/{id}', response_model=LpgOperationsRejections, tags=['LpgOperationsRejections'])
async def get(id: str):
    return await LpgOperationsRejections.get(id, skip_secrets=True)


@router.get('/lpgoperationsrejections', response_model=LpgOperationsRejectionsGetResp, tags=['LpgOperationsRejections'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LpgOperationsRejections.get_all(params, skip_secrets=True)


@router.delete('/lpgoperationsrejections/{id}', tags=['LpgOperationsRejections'])
async def delete(id: str):
    return await LpgOperationsRejections.delete(id)


@router.post('/consumerpumptransactions', response_model=ConsumerPumpTransactions, tags=['ConsumerPumpTransactions'])
async def create(inputObj: ConsumerPumpTransactionsCreate):
    return await inputObj.create()


@router.put('/consumerpumptransactions', response_model=ConsumerPumpTransactions, tags=['ConsumerPumpTransactions'])
async def update(inputObj: ConsumerPumpTransactions):
    return await inputObj.modify()


@router.get('/consumerpumptransactions/{id}', response_model=ConsumerPumpTransactions, tags=['ConsumerPumpTransactions'])
async def get(id: str):
    return await ConsumerPumpTransactions.get(id, skip_secrets=True)


@router.get('/consumerpumptransactions', response_model=ConsumerPumpTransactionsGetResp, tags=['ConsumerPumpTransactions'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await ConsumerPumpTransactions.get_all(params, skip_secrets=True)


@router.delete('/consumerpumptransactions/{id}', tags=['ConsumerPumpTransactions'])
async def delete(id: str):
    return await ConsumerPumpTransactions.delete(id)


@router.post('/consumerpumptankinventory', response_model=ConsumerPumpTankInventory, tags=['ConsumerPumpTankInventory'])
async def create(inputObj: ConsumerPumpTankInventoryCreate):
    return await inputObj.create()


@router.put('/consumerpumptankinventory', response_model=ConsumerPumpTankInventory, tags=['ConsumerPumpTankInventory'])
async def update(inputObj: ConsumerPumpTankInventory):
    return await inputObj.modify()


@router.get('/consumerpumptankinventory/{id}', response_model=ConsumerPumpTankInventory, tags=['ConsumerPumpTankInventory'])
async def get(id: str):
    return await ConsumerPumpTankInventory.get(id, skip_secrets=True)


@router.get('/consumerpumptankinventory', response_model=ConsumerPumpTankInventoryGetResp, tags=['ConsumerPumpTankInventory'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await ConsumerPumpTankInventory.get_all(params, skip_secrets=True)


@router.delete('/consumerpumptankinventory/{id}', tags=['ConsumerPumpTankInventory'])
async def delete(id: str):
    return await ConsumerPumpTankInventory.delete(id)


@router.post('/consumerpumpstocksreceipts', response_model=ConsumerPumpStocksReceipts, tags=['ConsumerPumpStocksReceipts'])
async def create(inputObj: ConsumerPumpStocksReceiptsCreate):
    return await inputObj.create()


@router.put('/consumerpumpstocksreceipts', response_model=ConsumerPumpStocksReceipts, tags=['ConsumerPumpStocksReceipts'])
async def update(inputObj: ConsumerPumpStocksReceipts):
    return await inputObj.modify()


@router.get('/consumerpumpstocksreceipts/{id}', response_model=ConsumerPumpStocksReceipts, tags=['ConsumerPumpStocksReceipts'])
async def get(id: str):
    return await ConsumerPumpStocksReceipts.get(id, skip_secrets=True)


@router.get('/consumerpumpstocksreceipts', response_model=ConsumerPumpStocksReceiptsGetResp, tags=['ConsumerPumpStocksReceipts'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await ConsumerPumpStocksReceipts.get_all(params, skip_secrets=True)


@router.delete('/consumerpumpstocksreceipts/{id}', tags=['ConsumerPumpStocksReceipts'])
async def delete(id: str):
    return await ConsumerPumpStocksReceipts.delete(id)


@router.post('/hostsicktts', response_model=HostSickTts, tags=['HostSickTts'])
async def create(inputObj: HostSickTtsCreate):
    return await inputObj.create()


@router.put('/hostsicktts', response_model=HostSickTts, tags=['HostSickTts'])
async def update(inputObj: HostSickTts):
    return await inputObj.modify()


@router.get('/hostsicktts/{id}', response_model=HostSickTts, tags=['HostSickTts'])
async def get(id: str):
    return await HostSickTts.get(id, skip_secrets=True)


@router.get('/hostsicktts', response_model=HostSickTtsGetResp, tags=['HostSickTts'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await HostSickTts.get_all(params, skip_secrets=True)


@router.delete('/hostsicktts/{id}', tags=['HostSickTts'])
async def delete(id: str):
    return await HostSickTts.delete(id)


@router.post('/hostcancelledtts', response_model=HostCancelledTts, tags=['HostCancelledTts'])
async def create(inputObj: HostCancelledTtsCreate):
    return await inputObj.create()


@router.put('/hostcancelledtts', response_model=HostCancelledTts, tags=['HostCancelledTts'])
async def update(inputObj: HostCancelledTts):
    return await inputObj.modify()


@router.get('/hostcancelledtts/{id}', response_model=HostCancelledTts, tags=['HostCancelledTts'])
async def get(id: str):
    return await HostCancelledTts.get(id, skip_secrets=True)


@router.get('/hostcancelledtts', response_model=HostCancelledTtsGetResp, tags=['HostCancelledTts'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await HostCancelledTts.get_all(params, skip_secrets=True)


@router.delete('/hostcancelledtts/{id}', tags=['HostCancelledTts'])
async def delete(id: str):
    return await HostCancelledTts.delete(id)


@router.post('/hostkfactorchanges', response_model=HostKFactorChanges, tags=['HostKFactorChanges'])
async def create(inputObj: HostKFactorChangesCreate):
    return await inputObj.create()


@router.put('/hostkfactorchanges', response_model=HostKFactorChanges, tags=['HostKFactorChanges'])
async def update(inputObj: HostKFactorChanges):
    return await inputObj.modify()


@router.get('/hostkfactorchanges/{id}', response_model=HostKFactorChanges, tags=['HostKFactorChanges'])
async def get(id: str):
    return await HostKFactorChanges.get(id, skip_secrets=True)


@router.get('/hostkfactorchanges', response_model=HostKFactorChangesGetResp, tags=['HostKFactorChanges'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await HostKFactorChanges.get_all(params, skip_secrets=True)


@router.delete('/hostkfactorchanges/{id}', tags=['HostKFactorChanges'])
async def delete(id: str):
    return await HostKFactorChanges.delete(id)


@router.post('/hostlocalloadedtts', response_model=HostLocalLoadedTts, tags=['HostLocalLoadedTts'])
async def create(inputObj: HostLocalLoadedTtsCreate):
    return await inputObj.create()


@router.put('/hostlocalloadedtts', response_model=HostLocalLoadedTts, tags=['HostLocalLoadedTts'])
async def update(inputObj: HostLocalLoadedTts):
    return await inputObj.modify()


@router.get('/hostlocalloadedtts/{id}', response_model=HostLocalLoadedTts, tags=['HostLocalLoadedTts'])
async def get(id: str):
    return await HostLocalLoadedTts.get(id, skip_secrets=True)


@router.get('/hostlocalloadedtts', response_model=HostLocalLoadedTtsGetResp, tags=['HostLocalLoadedTts'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await HostLocalLoadedTts.get_all(params, skip_secrets=True)


@router.delete('/hostlocalloadedtts/{id}', tags=['HostLocalLoadedTts'])
async def delete(id: str):
    return await HostLocalLoadedTts.delete(id)


@router.post('/hostbayreassignment', response_model=HostBayReAssignment, tags=['HostBayReAssignment'])
async def create(inputObj: HostBayReAssignmentCreate):
    return await inputObj.create()


@router.put('/hostbayreassignment', response_model=HostBayReAssignment, tags=['HostBayReAssignment'])
async def update(inputObj: HostBayReAssignment):
    return await inputObj.modify()


@router.get('/hostbayreassignment/{id}', response_model=HostBayReAssignment, tags=['HostBayReAssignment'])
async def get(id: str):
    return await HostBayReAssignment.get(id, skip_secrets=True)


@router.get('/hostbayreassignment', response_model=HostBayReAssignmentGetResp, tags=['HostBayReAssignment'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await HostBayReAssignment.get_all(params, skip_secrets=True)


@router.delete('/hostbayreassignment/{id}', tags=['HostBayReAssignment'])
async def delete(id: str):
    return await HostBayReAssignment.delete(id)


@router.post('/hostmanualbayassigned', response_model=HostManualBayAssigned, tags=['HostManualBayAssigned'])
async def create(inputObj: HostManualBayAssignedCreate):
    return await inputObj.create()


@router.put('/hostmanualbayassigned', response_model=HostManualBayAssigned, tags=['HostManualBayAssigned'])
async def update(inputObj: HostManualBayAssigned):
    return await inputObj.modify()


@router.get('/hostmanualbayassigned/{id}', response_model=HostManualBayAssigned, tags=['HostManualBayAssigned'])
async def get(id: str):
    return await HostManualBayAssigned.get(id, skip_secrets=True)


@router.get('/hostmanualbayassigned', response_model=HostManualBayAssignedGetResp, tags=['HostManualBayAssigned'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await HostManualBayAssigned.get_all(params, skip_secrets=True)


@router.delete('/hostmanualbayassigned/{id}', tags=['HostManualBayAssigned'])
async def delete(id: str):
    return await HostManualBayAssigned.delete(id)


@router.post('/hostmanualfanprinted', response_model=HostManualFanPrinted, tags=['HostManualFanPrinted'])
async def create(inputObj: HostManualFanPrintedCreate):
    return await inputObj.create()


@router.put('/hostmanualfanprinted', response_model=HostManualFanPrinted, tags=['HostManualFanPrinted'])
async def update(inputObj: HostManualFanPrinted):
    return await inputObj.modify()


@router.get('/hostmanualfanprinted/{id}', response_model=HostManualFanPrinted, tags=['HostManualFanPrinted'])
async def get(id: str):
    return await HostManualFanPrinted.get(id, skip_secrets=True)


@router.get('/hostmanualfanprinted', response_model=HostManualFanPrintedGetResp, tags=['HostManualFanPrinted'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await HostManualFanPrinted.get_all(params, skip_secrets=True)


@router.delete('/hostmanualfanprinted/{id}', tags=['HostManualFanPrinted'])
async def delete(id: str):
    return await HostManualFanPrinted.delete(id)


@router.post('/hostunauthorisedflow', response_model=HostUnauthorisedFlow, tags=['HostUnauthorisedFlow'])
async def create(inputObj: HostUnauthorisedFlowCreate):
    return await inputObj.create()


@router.put('/hostunauthorisedflow', response_model=HostUnauthorisedFlow, tags=['HostUnauthorisedFlow'])
async def update(inputObj: HostUnauthorisedFlow):
    return await inputObj.modify()


@router.get('/hostunauthorisedflow/{id}', response_model=HostUnauthorisedFlow, tags=['HostUnauthorisedFlow'])
async def get(id: str):
    return await HostUnauthorisedFlow.get(id, skip_secrets=True)


@router.get('/hostunauthorisedflow', response_model=HostUnauthorisedFlowGetResp, tags=['HostUnauthorisedFlow'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await HostUnauthorisedFlow.get_all(params, skip_secrets=True)


@router.delete('/hostunauthorisedflow/{id}', tags=['HostUnauthorisedFlow'])
async def delete(id: str):
    return await HostUnauthorisedFlow.delete(id)


@router.post('/hostoverloadedtts', response_model=HostOverLoadedTts, tags=['HostOverLoadedTts'])
async def create(inputObj: HostOverLoadedTtsCreate):
    return await inputObj.create()


@router.put('/hostoverloadedtts', response_model=HostOverLoadedTts, tags=['HostOverLoadedTts'])
async def update(inputObj: HostOverLoadedTts):
    return await inputObj.modify()


@router.get('/hostoverloadedtts/{id}', response_model=HostOverLoadedTts, tags=['HostOverLoadedTts'])
async def get(id: str):
    return await HostOverLoadedTts.get(id, skip_secrets=True)


@router.get('/hostoverloadedtts', response_model=HostOverLoadedTtsGetResp, tags=['HostOverLoadedTts'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await HostOverLoadedTts.get_all(params, skip_secrets=True)


@router.delete('/hostoverloadedtts/{id}', tags=['HostOverLoadedTts'])
async def delete(id: str):
    return await HostOverLoadedTts.delete(id)


@router.post('/tagsdata', response_model=TagsData, tags=['TagsData'])
async def create(inputObj: TagsDataCreate):
    return await inputObj.create()


@router.put('/tagsdata', response_model=TagsData, tags=['TagsData'])
async def update(inputObj: TagsData):
    return await inputObj.modify()


@router.get('/tagsdata/{id}', response_model=TagsData, tags=['TagsData'])
async def get(id: str):
    return await TagsData.get(id, skip_secrets=True)


@router.get('/tagsdata', response_model=TagsDataGetResp, tags=['TagsData'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await TagsData.get_all(params, skip_secrets=True)


@router.delete('/tagsdata/{id}', tags=['TagsData'])
async def delete(id: str):
    return await TagsData.delete(id)