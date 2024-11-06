from role_master_enum import *
from role_master_model import *
import fastapi

router = fastapi.APIRouter(prefix='/cegrolemaster')


# Action get_ceg_role_master
@router.post('/get_ceg_role_master', tags=['CEGRoleMaster'])
async def cegrolemaster_get_ceg_role_master(data: Cegrolemaster_Get_Ceg_Role_MasterParams):
    ...


# Action download_ceg_role_master
@router.post('/download_ceg_role_master', tags=['CEGRoleMaster'])
async def cegrolemaster_download_ceg_role_master(data: Cegrolemaster_Download_Ceg_Role_MasterParams):
    role_master_path = os.path.join(
        urdhva_base.settings.mft_path, 'ceg_role_master.csv'
    )


# Action upload_dnc_role_master
@router.post('/upload_dnc_role_master', tags=['CEGRoleMaster'])
async def cegrolemaster_upload_dnc_role_master(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    ...
