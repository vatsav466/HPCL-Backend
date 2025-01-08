from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import urdhva_base.settings
import urdhva_base.queryparams as queryparams
import authenticator.authentication_manager_ad as auth_manager
router = fastapi.APIRouter(prefix='/users')


# Action fetch_users
@router.post('/fetch_users', tags=['Users'])
async def users_fetch_users(data: Users_Fetch_UsersParams):
    params = queryparams.QueryParams(search_text=data.search_string, limit=data.limit, skip=data.skip)
    # return await Users.


# Action create_user
@router.post('/create_user', tags=['Users'])
async def users_create_user(data: Users_Create_UserParams):
    return await auth_manager.AuthenticationManager.create_user(data.username, data.password, data.role,
                                                                data.first_name, data.last_name, data.employee_id, True)


# Action login
@router.post('/login', tags=['Users'])
async def users_login(request: fastapi.Request, data: Users_LoginParams):
    status, resp = await auth_manager.AuthenticationManager.login(data.username, data.password)
    if not status:
        response = fastapi.responses.JSONResponse({"status": False, "msg": resp}, 401)
    else:
        response = fastapi.responses.JSONResponse({"status": True, "msg": "Logged in Successfully"},
                                                  200)
        response.set_cookie(urdhva_base.settings.cookie_name, resp, httponly=urdhva_base.settings.session_httponly,
                            secure=urdhva_base.settings.session_secure, samesite=urdhva_base.settings.session_same_site)
    return response


# Action update_user_status
@router.post('/update_user_status', tags=['Users'])
async def users_update_user_status(data: Users_Update_User_StatusParams):
    ...


# Action logout
@router.post('/logout', tags=['Users'])
async def users_logout(request: fastapi.Request, data: Users_LogoutParams):
    # Clearing the session
    return await auth_manager.AuthenticationManager.logout(request)
