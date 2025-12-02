import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import traceback
import authenticator.authentication_manager_ad as authentication_manager_ad

router = fastapi.APIRouter(prefix='/usermaster')


# Action create_user
@router.post('/create_user', tags=['UserMaster'])
async def usermaster_create_user(data: Usermaster_Create_UserParams):
    try:
        if urdhva_base.context.context.exists():
            rpt = urdhva_base.context.context.get('rpt', {})
        else:
            rpt = {}
        
        if rpt and rpt.get('username','') in ['admin','superadmin']:
            return False, "Not allowed to perform this operation"

        if not isinstance(data.data,dict):
            data = data.data.__dict__
        
        query = f"""username = '{data.get('username','')}'
                """
        user_data = await Users.get_all(urdhva_base.QueryParams(q=query), resp_type="plain")
        if user_data["data"]:
            return False, "User Already Exists"
        

        if not data.get('is_ad_user') and not data.get('password'):
            return False, "Not a Valid ADUser"
        
        
        user_response = await UsersCreate(**{
            "username": data.get('username'),
            "email": data.get("email",""),
            "first_name": data.get('first_name',''),
            "last_name": data.get('last_name'),
            "password": data.get('password'),
            "employee_id": data.get('username'),
            "bu": data.get('bu',[]),
            "sap_id": data.get('sap_id',[]),
            "system_role": data.get('system_role',[]),
            "novex_role": data.get('novex_role',[]),
            "region": data.get('region',[]),
            "state": data.get('state',[]),
            "zone": data.get('zone',[]),
            "sales_area": data.get('sales_area',[]),
            "manual_user": True,
            "status": data.get('status'),
            "is_ad_user": data.get('is_ad_user')
        }).create()
        if user_response:
            if rpt:
                await SystemAuditLogCreate(
                    **{
                        "employee_id": rpt["username"],
                        "role": rpt["novex_role"],
                        "email": rpt.get("email",""),
                        "section": "User Action",
                        "remarks": f"User {data.get('user_name')} created successfully"
                    }
                    ).create()
                return {
                    "success": True, 
                    "message": "User created successfully",
                }
    except Exception as e:
        print("traceback :", traceback.format_exc())
        if rpt:
            await SystemAuditLogCreate(
                **{
                    "employee_id": rpt["username"],
                    "role": rpt["novex_role"],
                    "email": rpt.get("email",""),
                    "section": "User Action",
                    "remarks": f"Failed to create user {data.get('user_name')}"
                }
            ).create()
        
        return {
            "success": False, 
            "message": "An error occurred while creating user details."
        }
    
    

    


# Action update_user
@router.post('/update_user', tags=['UserMaster'])
async def usermaster_update_user(data: Usermaster_Update_UserParams):
    try:
        if urdhva_base.context.context.exists():
            rpt = urdhva_base.context.context.get('rpt', {})
        else:
            rpt = {}
        
        if rpt and rpt.get('username','') in ['admin','superadmin']:
            return False, "Not allowed to perform this operation"
        
        if not isinstance(data.data,dict):
            data = data.data.__dict__
        
        query = f"""username = '{data.get('username','')}'
                """

        user_data = await Users.get_all(urdhva_base.QueryParams(q=query), resp_type="plain")
        if not user_data["data"]:
            return False, "User does not exists to modify"
        
        data_dict = data
        data_dict.update({"id": user_data['data'][0]['id']})
        params = urdhva_base.QueryParams(q="")
        role = await Roles.get_all(params, resp_type="plain")
        roles = []
        if role["data"]:
            roles = [u['name'] for u in role["data"]]
        
        changes = []
        for key, new_value in data_dict.items():
            old_value = user_data['data'][0][key]

            # Condition only for novex_role
            if key == "novex_role":
                if new_value is not None and old_value != new_value:
                    invalid_roles = [role for role in new_value if role not in roles]
                    if invalid_roles:
                        return {
                            "success": False,
                            "message": "Update failed: Invalid Roles",
                            "details": {
                                "invalid_roles_attempted": invalid_roles,
                                "valid_roles_available": roles
                            }
                        }

                    changes.append(f"{key} changed from '{old_value}' to '{new_value}'")

                # For all other keys — just detect change, no validation
                elif new_value is not None and old_value != new_value:
                    changes.append(f"{key} changed from '{old_value}' to '{new_value}'")
        
        if changes:
            remarks = "Changes: " + "; ".join(changes)
        else:
            remarks = "No changes detected"
        
        response = await Users(**data_dict).modify()

        if response:
            if rpt:
                await SystemAuditLogCreate(
                    **{
                        "employee_id": rpt["username"],
                        "role": rpt["novex_role"],
                        "email": rpt.get("email",""),
                        "section": "User Action",
                        "remarks": remarks
                    }
                ).create()
            return {
                "success": True, 
                "message": "User details updated successfully",
                "changes": changes if changes else ["No changes detected"]
            }
    except Exception as e:
        print("traceback :", traceback.format_exc())
        if rpt:
            await SystemAuditLogCreate(
                **{
                    "employee_id": rpt["username"],
                    "role": rpt["novex_role"],
                    "email": rpt.get("email",""),
                    "section": "User Action",
                    "remarks": "Failed to update user details "
                }
            ).create()
        return {
            "success": False, 
            "message": "An error occurred while updating user details. "
        }
