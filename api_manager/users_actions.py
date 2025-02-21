from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import traceback
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
async def users_update_user_status(request: fastapi.Request, data: Users_Update_User_StatusParams):
    if not data.username:
        return False, "Invalid input"
    try:
        user_name = data.username  # Assuming user_id is the primary key
        query = f"username='{user_name}'"
        params = urdhva_base.queryparams.QueryParams()
        params.fields = []
        params.q = query
        resp = await Users.get_all(params, resp_type="plain")

        if not isinstance(resp, dict):
            resp = resp._dict_

        if resp["data"]:
            resp = resp["data"][0]
            specific_columns = ["sap_id", "region", "sales_area", "zone"]
            for key in specific_columns:
                if not hasattr(data, key) or "*" in getattr(data, key):
                    setattr(data, key, [])

            resp['first_name'] = data.first_name
            resp['last_name'] = data.last_name
            resp['region'] = data.region
            resp['state'] = data.state
            resp['zone'] = data.zone
            resp['sap_id'] = data.sap_id
            resp['bu'] = data.bu
            resp['sales_area'] = data.sales_area
            resp['novex_role'] = data.novex_role
            await Users(**resp).modify()
            return True, "User updated successfully"

    except Exception as e:
        print(traceback.format_exc())
        return False, "Error updating user details, Contact support"


# Action logout
@router.post('/logout', tags=['Users'])
async def users_logout(request: fastapi.Request, data: Users_LogoutParams):
    # Clearing the session
    return await auth_manager.AuthenticationManager.logout(request)
