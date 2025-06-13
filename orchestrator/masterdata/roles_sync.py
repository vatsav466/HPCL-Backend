import urdhva_base
import asyncio
import hpcl_ceg_model


async def sync_user_roles():
    role_mapping = {
                    "Zonal Operations SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
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
                    "Zonal Operations LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Analytics",
                                    "LPG Inventory",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "HQO Operation SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Terminal Automation",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Location In-Charge SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Maintenance Officer SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Plant In-Charge SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Planning Officer SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal Chief Manager SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal Executive Officer SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal Manager SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal Operations Head SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal HSE SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "Zonal Transport Officer SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                                    "Terminal Automation",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "HQO HSE SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Terminal Automation",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "HQO Supply Officer SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Terminal Automation",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                    "Distribution Manager SOD": {
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
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "HQO General Manager SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Terminal Automation",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "HQO Manager SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Terminal Automation",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                                    "Terminal Home",
                                    "Terminal Automation",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
                                ]
                            }
                        ],
                        "name": "SOD",
                        "status": True
                    },
                    "HQO Operations SOD": {
                        "allowed_pages": [
                            {
                                "menu_name": "SOD Terminal",
                                "allowed_sub_menus": [
                                    "Supply Chain",
                                    "Terminal Home",
                                    "Terminal Automation",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "VTS",
                                "allowed_sub_menus": [
                                    "VTS Home"
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
                                    "LPG Plant",
                                    "LPG Inventory",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Sales Officer LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Analytics",
                                    "LPG Inventory",
                                ]
                            },
                            {
                                "menu_name": "Sales Performance",
                                "allowed_sub_menus": [
                                    "Performance"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Location In-Charge LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Inventory",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Maintenance Officer LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Inventory",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Planning Officer LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Inventory",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Regional Manager LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Analytics",
                                    "LPG Inventory",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "Performance",
                                "allowed_sub_menus": [
                                    "Sales Performance"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "ERP Assistant Manager LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Inventory"                                    
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Zonal HSE LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Inventory",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Zonal Officer LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Analytics",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Zonal Operations Chief Manager LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Inventory",
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
                                    "LPG Plant",
                                    "LPG Inventory",
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
                                    "LPG Plant",
                                    "LPG Inventory",
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
                                    "LPG Plant",
                                    "LPG Inventory",
                                    "Video Analytics",
                                    "LPG Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "HQO Head LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Inventory",
                                    "Video Analytics",
                                    "LPG Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "Zonal Head LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Inventory",
                                    "Video Analytics",
                                    "LPG Analytics"
                                ]
                            },
                            {
                                "menu_name": "Performance",
                                "allowed_sub_menus": [
                                    "Sales Performance"                                    
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "HQO Sale General Manager": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "Video Analytics",
                                    "LPG Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "HQO HSE LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Inventory",
                                    "Video Analytics",
                                    "LPG Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
                        "status": True
                    },
                    "HQO Operations LPG": {
                        "allowed_pages": [
                            {
                                "menu_name": "LPG",
                                "allowed_sub_menus": [
                                    "LPG Operations",
                                    "LPG Plant",
                                    "LPG Inventory",
                                    "Video Analytics",
                                    "LPG Analytics"
                                ]
                            }
                        ],
                        "name": "LPG",
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
                        "allowed_pages": [
                            
                        ],
                        "status": True
                    },
                    "Super Admin": {
                        "allowed_pages": [
                            
                        ],
                        "status": True
                    },
                    "Sales Officer RO": {
                        "allowed_pages": [
                            {
                                "menu_name": "Retail Outlet",
                                "allowed_sub_menus": [
                                    "RO Home",
                                    "Supply Chain",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "Performance",
                                "allowed_sub_menus": [
                                    "Sales Performance"
                                ]
                            }
                            
                        ],
                        "name": "RO",
                        "status": True
                    },
                    "Regional Manager RO": {
                        "allowed_pages": [
                            {
                                "menu_name": "Retail Outlet",
                                "allowed_sub_menus": [
                                    "RO Home",
                                    "Supply Chain",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "Performance",
                                "allowed_sub_menus": [
                                    "Sales Performance"
                                ]
                            }
                        ],
                        "name": "RO",
                        "status": True
                    },
                    "HQO Officer RO": {
                        "allowed_pages": [
                            {
                                "menu_name": "Retail Outlet",
                                "allowed_sub_menus": [
                                    "RO Home",
                                    "Supply Chain",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "Performance",
                                "allowed_sub_menus": [
                                    "Sales Performance"
                                ]
                            }
                        ],
                        "name": "RO",
                        "status": True
                    },
                    "HQO RO": {
                        "allowed_pages": [
                            {
                                "menu_name": "Retail Outlet",
                                "allowed_sub_menus": [
                                    "RO Home",
                                    "Supply Chain",
                                    "Video Analytics"
                                ]
                            },
                            {
                                "menu_name": "Performance",
                                "allowed_sub_menus": [
                                    "Sales Performance"
                                ]
                            }
                        ],
                        "name": "RO",
                        "status": True
                    },
                    "Zonal Head RO": {
                        "allowed_pages": [
                            {
                                "menu_name": "Retail Outlet",
                                "allowed_sub_menus": [
                                    "RO Home",
                                    "Supply Chain",
                                    "Video Analytics"
                                ]
                            }
                        ],
                        "name": "RO",
                        "status": True
                    },
                    "RO Dealer": {
                        "allowed_pages": [
                            {
                                "menu_name": "Retail Outlet",
                                "allowed_sub_menus": [
                                    "RO Home",
                                    "Supply Chain"
                                ]
                            }                         
                        ],
                        "name": "RO",
                        "status": True
                    }
                }
    await hpcl_ceg_model.Roles.bulk_update([{"name": key, "status": True, "allowed_pages": value["allowed_pages"]}
                                            for key, value in role_mapping.items()], upsert=True,
                                           upsert_skip_keys=['name'])


if __name__ == "__main__":
    asyncio.run(sync_user_roles())
