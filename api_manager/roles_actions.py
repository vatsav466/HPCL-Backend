from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/roles')


# Action create_role
@router.post('/create_role', tags=['Roles'])
async def roles_create_role(data: Roles_Create_RoleParams):
    ...


# Action update_role_status
@router.post('/update_role_status', tags=['Roles'])
async def roles_update_role_status(data: Roles_Update_Role_StatusParams):
    ...


# Action get_all_pages
@router.post('/get_all_pages', tags=['Roles'])
async def roles_get_all_pages(data: Roles_Get_All_PagesParams):
    ...
