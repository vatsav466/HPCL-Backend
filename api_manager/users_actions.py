from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/users')


# Action fetch_users
@router.post('/fetch_users', tags=['Users'])
async def users_fetch_users(data: Users_Fetch_UsersParams):
    ...


# Action create_user
@router.post('/create_user', tags=['Users'])
async def users_create_user(data: Users_Create_UserParams):
    ...


# Action update_user_status
@router.post('/update_user_status', tags=['Users'])
async def users_update_user_status(data: Users_Update_User_StatusParams):
    ...


# Action login
@router.post('/login', tags=['Users'])
async def users_login(data: Users_LoginParams):
    ...
