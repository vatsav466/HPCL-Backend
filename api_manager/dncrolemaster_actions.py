from role_master_enum import *
from role_master_model import *
import fastapi

router = fastapi.APIRouter(prefix='/dncrolemaster')


# Action get_dnc_role_master
@router.post('/get_dnc_role_master', tags=['DNCRoleMaster'])
async def dncrolemaster_get_dnc_role_master(data: Dncrolemaster_Get_Dnc_Role_MasterParams):
    ...


# Action download_dnc_role_master
@router.post('/download_dnc_role_master', tags=['DNCRoleMaster'])
async def dncrolemaster_download_dnc_role_master(data: Dncrolemaster_Download_Dnc_Role_MasterParams):
    ...


# Action upload_dnc_role_master
@router.post('/upload_dnc_role_master', tags=['DNCRoleMaster'])
async def dncrolemaster_upload_dnc_role_master(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    ...
