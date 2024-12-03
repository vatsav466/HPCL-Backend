vts_interlock_mapping = {
    "speed_violation_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "Speed Violation FirstTime",
                "block_duration": 7,
                "block_msg": "7 days"
            },
            "1": {
                "interlock_name": "Speed Violation SecondTime",
                "block_duration": 90,
                "block_msg": "90 days"
            },
            "2": {
                "interlock_name": "Speed Violation ThirdTime",
                "block_duration": 730,
                "block_msg": "2 years"
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
                "block_msg": "7 days"
            },
            "1": {
                "interlock_name": "Night Driving SecondTime",
                "block_duration": 90,
                "block_msg": "90 days"
            },
            "2": {
                "interlock_name": "Night Driving ThirdTime",
                "block_duration": 730,
                "block_msg": "2 years"
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
                "block_msg": "90 days"
            },
            "1": {
                "interlock_name": "VTS RouteDeviation SecondTime",
                "block_duration": 730,
                "block_msg": "2 years"
            }
        },
        "description": "Route Deviation",
        "alert_threshold": 1
    },
    "stoppage_violations_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "Unauthorized Stoppage FirstTime",
                "block_duration": 90,
                "block_msg": "90 days"
            },
            "1": {
                "interlock_name": "Unauthorized Stoppage SecondTime",
                "block_duration": 730,
                "block_msg": "2 years"
            }
        },
        "description": "Stoppage  Violations",
        "alert_threshold": 5,
    },
    "no_halt_zone_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "No Halt Zone FirstTime",
                "block_duration": 90,
                "block_msg": "90 days"
            },
            "1": {
                "interlock_name": "No Halt Zone SecondTime",
                "block_duration": 730,
                "block_msg": "2 years"
            }
        },
        "description": "NoHalt Zone",
        "alert_threshold": 1
    },
    "device_offline_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "VTS Offline FirstTime",
                "block_duration": 90,
                "block_msg": "90 days"
            },
            "1": {
                "interlock_name": "VTS Offline SecondTime",
                "block_duration": 730,
                "block_msg": "2 years"
            }
        },
        "description": "Device Offline",
        "alert_threshold": 1
    },
    "device_tamper_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "VTS Device Tampering",
                "block_duration": 731,
                "block_msg": "Permanent"
            }
        },
        "description": "Device Tampered",
        "alert_threshold": 5
    },
    "main_supply_removal_count": {
        "alerting_rules": {
            "0": {
                "interlock_name": "VTS Main Supply Removal",
                "block_duration": 731,
                "block_msg": "Permanent"
            }
        },
        "description": "Main Supply Removal",
        "alert_threshold": 5
    }
}
