import urdhva_base
import asyncio
import hpcl_ceg_model


async def sync_user_roles():
    role_mapping = {
                    "Location In-Charge SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Safety Officer SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "M&I Officer SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal Safety Officer SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal M&I Officer SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal Head LEVEL SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Dashboard",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "SOD Planning Officer": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "HQO SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "Supply Chain",
                                "allowed_sub_menus": [
                                    "Supply Chain Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "COLA HQO Officer SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "HQO Head SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home""Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "Supply Chain",
                                "allowed_sub_menus": [
                                    "Supply Chain Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Safety Officer LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Location In-Charge LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Maintenanace Officer LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Maintenance Officer LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Regional Manager LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal HSE LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Zonal Distributions Head LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Zonal Operations Head LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "HQO LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",                    
                                    "Video Analytics",
                                    "LPG Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "HQO HSE LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",
                                    "Video Analytics",
                                    "LPG Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "HQO Operations LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Home",
                                    "LPG Plant",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Sales Performance": {
                        "allowed_pages": [
                            {
                                "menu_name": "Sales Performance",
                                "allowed_sub_menus": [
                                    "Sales Performance",
                                    "Industry Performance",
                                    "Performance Insights"
                                ]
                            }
                        ],
                        "name": "Sales",
                        "status": True
                    },
                    "Admin": {
                        "allowed_pages": [],
                        "status": True
                    }
                }
    await hpcl_ceg_model.Roles.bulk_update([{"name": key, "status": True, "allowed_pages": value["allowed_pages"]}
                                            for key, value in role_mapping.items()], upsert=True,
                                           upsert_skip_keys=['name'])


if __name__ == "__main__":
    asyncio.run(sync_user_roles())
