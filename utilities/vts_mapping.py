vts_interlock_mapping = {
    "speed_violation_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "Speed Violation FirstTime",
                "block_duration": 7,
                "block_msg": "7 days",
                "clear_count": True
            },
            "1": {
                "interlock_name": "Speed Violation SecondTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "2": {
                "interlock_name": "Speed Violation ThirdTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "Speed Violation",
        "alert_threshold": 5
    },
    "night_driving_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "Night Driving FirstTime",
                "block_duration": 7,
                "block_msg": "7 days",
                "clear_count": True
            },
            "1": {
                "interlock_name": "Night Driving SecondTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "2": {
                "interlock_name": "Night Driving ThirdTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "Night Driving",
        "alert_threshold": 5
    },
    "route_deviation_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "VTS RouteDeviation FirstTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "1": {
                "interlock_name": "VTS RouteDeviation SecondTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "Route Deviation",
        "alert_threshold": 5
    },
    "stoppage_violations_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "Unauthorized Stoppage FirstTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "1": {
                "interlock_name": "Unauthorized Stoppage SecondTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "Stoppage  Violations",
        "alert_threshold": 5,
    },
    "no_halt_zone_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "NoHalt Zone FirstTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "1": {
                "interlock_name": "NoHalt Zone SecondTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "NoHalt Zone",
        "alert_threshold": 0
    },
    "device_offline_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "VTS Offline FirstTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "1": {
                "interlock_name": "VTS Offline SecondTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "Device Offline",
        "alert_threshold": 0
    },
    "device_tamper_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "VTS Device Tampering",
                "block_duration": 731,
                "block_msg": "Permanent",
                "clear_count": True
            }
        },
        "description": "Device Tampered",
        "alert_threshold": 0
    },
    "main_supply_removal_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "VTS PowerDisconnect",
                "block_duration": 731,
                "block_msg": "Permanent",
                "clear_count": True
            }
        },
        "description": "Main Supply Removal",
        "alert_threshold": 0
    }
}

vts_exception_interlock_mapping = {
    "speed_violation_count": {
        "alerting_rules": {
            "1": {
                "interlock_name": "Speed Violation Exception FirstTime",
                "block_duration": 7,
                "block_msg": "7 days",
                "clear_count": True
            },
            "2": {
                "interlock_name": "Speed Violation Exception SecondTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "3": {
                "interlock_name": "Speed Violation Exception ThirdTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "Speed Violation",
        "alert_threshold": 5
    },
    "night_driving_count": {
        "alerting_rules": {
            "1": {
                "interlock_name": "Night Driving Exception FirstTime",
                "block_duration": 7,
                "block_msg": "7 days",
                "clear_count": True
            },
            "2": {
                "interlock_name": "Night Driving Exception SecondTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "3": {
                "interlock_name": "Night Driving Exception ThirdTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "Night Driving",
        "alert_threshold": 5
    },
    "route_deviation_count": {
        "alerting_rules": {
            "1": {
                "interlock_name": "Route Deviation Exception FirstTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "2": {
                "interlock_name": "Route Deviation Exception SecondTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "Route Deviation",
        "alert_threshold": 5
    },
    "stoppage_violations_count": {
        "alerting_rules": {
            "1": {
                "interlock_name": "Unauthorized Stoppage Exception FirstTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "2": {
                "interlock_name": "Unauthorized Stoppage Exception SecondTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "Stoppage  Violations",
        "alert_threshold": 5,
    },
    "no_halt_zone_count": {
        "alerting_rules": {
            "1": {
                "interlock_name": "NoHalt zone Exception FirstTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "2": {
                "interlock_name": "NoHalt Zone Exception SecondTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "NoHalt Zone",
        "alert_threshold": 0
    },
    "device_offline_count": {
        "alerting_rules": {
            "1": {
                "interlock_name": "VTS offline Exception FirstTime",
                "block_duration": 90,
                "block_msg": "90 days",
                "clear_count": True
            },
            "2": {
                "interlock_name": "VTS Offline Exception SecondTime",
                "block_duration": 730,
                "block_msg": "2 years",
                "clear_count": True
            }
        },
        "description": "Device Offline",
        "alert_threshold": 0
    },
    "device_tamper_count": {
        "alerting_rules": {
            "1": {
                "interlock_name": "VTS device Tampering Exception",
                "block_duration": 731,
                "block_msg": "Permanent",
                "clear_count": True
            }
        },
        "description": "Device Tampered",
        "alert_threshold": 0
    },
    "main_supply_removal_count": {
        "alerting_rules": {
            "1": {
                "interlock_name": "VTS PowerDisconnect Exception",
                "block_duration": 731,
                "block_msg": "Permanent",
                "clear_count": True
            }
        },
        "description": "Main Supply Removal",
        "alert_threshold": 0
    }
}
