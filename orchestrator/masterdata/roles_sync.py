import urdhva_base
import asyncio
import hpcl_ceg_model


async def sync_user_roles():
    role_mapping = {"Zonal SOD": {"allowed_pages": [{"menu_name": "SOD Terminal",
                                                     "allowed_sub_menus": ["Supply Chain", "Terminal Home",
                                                                           "Video Analytics"]}], "name": "SOD",
                                  "status": True},
                    "Zonal Head LEVEL SOD": {"allowed_pages": [{"menu_name": "SOD Terminal",
                                                                "allowed_sub_menus": ["Supply Chain",
                                                                                      "Terminal Home", "Dashboard",
                                                                                      "Video Analytics"]}],
                                             "name": "SOD", "status": True},
                    "SOD Planning Officer": {"allowed_pages": [{"menu_name": "SOD Terminal",
                                                                "allowed_sub_menus": ["Supply Chain", "Terminal Home",
                                                                                      "Video Analytics"]}],
                                             "name": "SOD", "status": True},
                    "HQO SOD": {"allowed_pages": [{"menu_name": "SOD Terminal",
                                                   "allowed_sub_menus": ["Supply Chain", "Terminal Home",
                                                                         "Video Analytics"]},
                                                  {"menu_name": "Supply Chain",
                                                   "allowed_sub_menus": ["Supply Chain Home"]}], "name": "SOD",
                                "status": True},
                    "Plant Incharge SOD": {"allowed_pages": [{"menu_name": "SOD Terminal",
                                                              "allowed_sub_menus": ["Supply Chain", "Terminal Home",
                                                                                    "Video Analytics"]}],
                                           "name": "SOD", "status": True},
                    "COLA HQO Officer SOD": {
                        "allowed_pages": [{"menu_name": "SOD Terminal", "allowed_sub_menus": ["Supply Chain"]}],
                        "name": "SOD", "status": True},
                    "HQO Head SOD": {"allowed_pages": [{"menu_name": "SOD Terminal",
                                                        "allowed_sub_menus": ["Supply Chain", "Terminal Home" 
                                                                                              "Video Analytics"]},
                                                       {"menu_name": "Supply Chain",
                                                        "allowed_sub_menus": ["Supply Chain Home"]}], "name": "SOD",
                                     "status": True},
                    "Plant Incharge LPG": {"allowed_pages": [{"menu_name": "LPG",
                                                              "allowed_sub_menus": ["LPG Operations", "LPG Home",
                                                                                    "Video Analytics"]}],
                                           "name": "SOD", "status": True},
                    "HQO LPG": {"allowed_pages": [{"menu_name": "LPG",
                                                   "allowed_sub_menus": ["LPG Operations", "LPG Home",
                                                                         "Video Analytics"]}], "name": "SOD",
                                "status": True},
                    "Zonal LPG SOD": {"allowed_pages": [{"menu_name": "LPG",
                                                         "allowed_sub_menus": ["LPG Operations", "LPG Home",
                                                                               "Video Analytics"]}], "name": "LPG",
                                      "status": True},
                    "Admin": {"allowed_pages": [], "status": True}
                    }
    await hpcl_ceg_model.Roles.bulk_update([{"name": key, "status": True, "allowed_pages": value["allowed_pages"]}
                                            for key, value in role_mapping.items()])


if __name__ == "__main__":
    asyncio.run(sync_user_roles())
