from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import urdhva_base.queryparams as queryparams

router = fastapi.APIRouter(prefix='/users')


# Action fetch_users
@router.post('/fetch_users', tags=['Users'])
async def users_fetch_users(data: Users_Fetch_UsersParams):
    params = queryparams.QueryParams(search_text=data.search_string, limit=data.limit, skip=data.skip)
    # return await Users.


# Action create_user
@router.post('/create_user', tags=['Users'])
async def users_create_user(data: Users_Create_UserParams):
    ...


# Action update_role_status
@router.post('/update_role_status', tags=['Users'])
async def users_update_role_status(data: Users_Update_Role_StatusParams):
    ...


# Action login
@router.post('/login', tags=['Users'])
async def users_login(data: Users_LoginParams):
    ...
