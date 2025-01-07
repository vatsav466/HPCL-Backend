import hpcl_ceg_model
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/roles')


# Action create_role
@router.post('/create_role', tags=['Roles'])
async def roles_create_role(data: Roles_Create_RoleParams):
    role_data = {"name": data.name, "status": True, "allowed_pages": [{'menu_name': rec.menu_name,
                                                                       "allowed_sub_menus": rec.allowed_sub_menus}
                                                                      for rec in data.allowed_pages]}
    await hpcl_ceg_model.RolesCreate(**role_data).create()
    return True, f"Role {data.name} created successfully"


# Action update_role_status
@router.post('/update_role_status', tags=['Roles'])
async def roles_update_role_status(data: Roles_Update_Role_StatusParams):
    ...


# Action get_all_pages
@router.post('/get_all_pages', tags=['Roles'])
async def roles_get_all_pages(data: Roles_Get_All_PagesParams):
    role_mapping = [
        {"menu_name": "Home", "allowed_sub_menus": []}, {"menu_name": "CEMS", "allowed_sub_menus": []},
        {"menu_name": "Retail Outlet",
         "allowed_sub_menus": ["RO Home", "Supply Chain", "Dashboard", "Video Analytics", "Asset Master"]},
        {"menu_name": "Supply Chain", "allowed_sub_menus": ["Supply Chain Home", "Dashboard"]},
        {"menu_name": "SOD Terminal",
         "allowed_sub_menus": ["Terminal Home", "Supply Chain", "Dashboard", "Video Analytics"]},
        {"menu_name": "VTS", "allowed_sub_menus": ["VTS Home", "Video Analytics"]},
        {"menu_name": "VA", "allowed_sub_menus": ["VA Home", "Dashboard"]},
        {"menu_name": "LPG", "allowed_sub_menus": ["Plant", "Sales CDCMS", "LPG Analytics"]},
        {"menu_name": "CEMS", "allowed_sub_menus": ["Home", "Screens"]},
        {"menu_name": "Consumer Pump", "allowed_sub_menus": ["CP Home"]},
        {"menu_name": "RCD", "allowed_sub_menus": ["RCD Home"]}, {"menu_name": "Masters",
                                                                  "allowed_sub_menus": ["Location Masters",
                                                                                        "Role Masters",
                                                                                        "Asset Masters",
                                                                                        "State Code Masters"]},
        {"menu_name": "Settings",
         "allowed_sub_menus": ["Analytical-Studio", "Notification", "Alerts", "DNC Settings", "Users", "Roles",
                               "Jobs", "Configurations", "User", "Changelog", "Documentation"]}]
    return role_mapping
