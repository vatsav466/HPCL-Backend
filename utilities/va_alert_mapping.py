VA_Alert_Mapping = {
    "RO": {
        "FIRE/SMOKE": {
            "name": "Fire/Smoke Detection",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "",
                    "escalation_role": "",
                    "escalation_time": ""
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 25
                },
                "level - 3": {
                    "condition": ">",
                    "value": 25
                }
            }
        },
        "SMOKE": {
            "name": "Smoke Detection",
            "severity": "Critical"
        },
        "Fire": {
            "name": "Fire Detection",
            "severity": "Critical"
        },
        "ABSENCE_OF_EARTHING": {
            "name": "Absence Of Earthing",
            "severity": "Critical"
        },
        "ABSENCE_OF_WHEELCHOCK": {
            "name": "Absence Of Wheelchock",
            "severity": "High"
        },
        "ABSENCE_OF_FIRE_EXTINGUISHER_DECANTATION": {
            "name": "Absence Of Fire Extinguisher Decantation",
            "severity": "High"
        },
        "UNAUTHORISED_FILLING_OF_CONTAINER": {
            "name": "Unauthorised Filling Of Container",
            "severity": "Medium"
        },
        "ALIGHT_FROM_TWO_WHEELER": {
            "name": "Alight From Two Wheeler",
            "severity": "Medium"
        },
        "ABSENCE OF EARTHING": {
            "name": "Absence Of Earthing",
            "severity": "Critical"
        },
        "ABSENCE OF WHEELCHOCK": {
            "name": "Absence Of Wheelchock",
            "severity": "High"
        }
    },
    "TAS": {
        "ABSENCE_OF_FIRE_EXTINGUISHER_DECANTATION": {
            "name": "Non compliance of Fire Extinguisher (TT Unloading)",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 25,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 25,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "FIRE": {
            "name": "Fire",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 0,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 0,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 0,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "SPILLAGE_IN_DUS": {
            "name": "Spillage",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 25,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 25,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "LINE_OF_FIRE": {
            "name": "Perimeter Intrusion",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 25,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 25,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "LOCKIN_POSITION_DOME_COVERS": {
            "name": "TT Dome Covers",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 25,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 25,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "VALVE_OPEN": {
            "name": "valve Box in open status",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 25,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 25,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "ABSENCE_OF_SAFETY_HARNESS": {
            "name": "Safety Harness non compliance (TT Unloading)",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 25,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 25,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "ABSENCE_OF_WHEELCHOCK": {
            "name": "Wheel choke non compliance (TT Unloading)",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 25,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 25,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "SUSPICIOUS_ACTIVITY": {
            "name": "Intrusion in nonworking hours (Storage Area/Wagon Gantry)",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 25,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 50,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 50,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "OBSTRUCTION": {
            "name": "Obstruction on approach road (Emergency gate)",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 25,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 50,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 50,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "PPE_HELMET": {
            "name": "PPE non compliance",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 25,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 50,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 50,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "UNAUTHORISED_FILLING_OF_CONTAINER": {
            "name": "Product filling in unauthorized container (TT Gantry)",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 25,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 50,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 50,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "ABSENCE_OF_TT_CREW": {
            "name": "TT Crew non availability (TT unloading)",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 25,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 50,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 50,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "PERSON_BELOW_TT": {
            "name": "TT Crew entering below TT",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 25,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 50,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 50,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "COOKING": {
            "name": "Unauthorized activity in parking area",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 25,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 50,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 50,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "CRASH_GUARD_STATUS": {
            "name": "Non availability of Crash Guard in TT",
            "severity": "Medium",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 35,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 60,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 60,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "KEY_REMOVAL": {
            "name": "Emergency gate Key Removal",
            "severity": "Medium",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 35,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 60,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 60,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "PARKING_DISCIPLINE": {
            "name": "Parking Discipline deviation",
            "severity": "Medium",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 35,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 60,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 60,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "UNAUTH_GATE_OPENING": {
            "name": "Unauthorized Activity (Emergency Gate opening )",
            "severity": "Medium",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 35,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 60,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 60,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "OVERCROWDING": {
            "name": "Clustering of people",
            "severity": "Low",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 50,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 100,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 100,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "TT_BRANDING": {
            "name": "TT Branding non compliance",
            "severity": "Low",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 50,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 100,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 100,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        },
        "UNAUTH_STACKING": {
            "name": "Unauthorized activity (Stacking of unwanted material in shed)",
            "severity": "Low",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 50,
                    "assign_role": "Safety Officer SOD",
                    "escalation_role": "Location In-Charge SOD",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 100,
                    "assign_role": "Zonal Operation SOD",
                    "escalation_role": "Zonal HSE SOD",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 100,
                    "assign_role": "HQO Operation SOD",
                    "escalation_role": "HQO HSE SOD",
                    "escalation_time": "P6H"
                }
            }
        }
    },
    "LPG": {
        "TTCrew-NearTT": {
            "name": "TT Crew non avaibaility near TT",
            "severity": "Medium",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 35,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 60,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "Smoke-Detection": {
            "name": "Smoke",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 0,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 0,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 0,
                    "assign_role": "HQO Operations LPG",
                    "escalation_role": "HQO HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "Fire-Detection": {
            "name": "Fire",
            "severity": "Critical",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 0,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 0,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 0,
                    "assign_role": "HQO Operations LPG",
                    "escalation_role": "HQO HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "Fire-Extinguisher": {
            "name": "Fire Extinguisher Non Compliance (TT)",
            "severity": "High",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 15,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 15,
                    "assign_role": "HQO Operations LPG",
                    "escalation_role": "HQO HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "Wheel-Chock": {
            "name": "Wheel choke non compliance (TT)",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 15,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 15,
                    "assign_role": "HQO Operations LPG",
                    "escalation_role": "HQO HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "Intrusion-PersonAtPerimeter": {
            "name": "Perimeter Intrusion",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 10,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 25,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 25,
                    "assign_role": "HQO Operations LPG",
                    "escalation_role": "HQO HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "LPGLeak-FillingGun": {
            "name": "LPG Leakages thru Filling Gun",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 0,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 5,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 15,
                    "assign_role": "HQO Operations LPG",
                    "escalation_role": "HQO HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "LPGLeak-Detection": {
            "name": "LPG Leakages",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 0,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 5,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 15,
                    "assign_role": "HQO Operations LPG",
                    "escalation_role": "HQO HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "PPE-Compliance": {
            "name": "PPE non compliance",
            "severity": "Medium",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 25,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 50,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 50,
                    "assign_role": "HQO Operations LPG",
                    "escalation_role": "HQO HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "Truck-Position": {
            "name": "Position of Truck on weigh bridge",
            "severity": "Medium",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 35,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 60,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "Free-Road": {
            "name": "Obstruction on Road (Emergency gate)",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 25,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 50,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 50,
                    "assign_role": "HQO Operations LPG",
                    "escalation_role": "HQO HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        },
        "Cylinder-Rolling": {
            "name": "Obstruction on Road (Emergency gate)",
            "severity": "Low",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 50,
                    "assign_role": "Safety Officer LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "P6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 100,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal HSE LPG",
                    "escalation_time": "P6H"
                }
            }
        }
    }
}
