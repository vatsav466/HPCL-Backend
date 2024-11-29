vts_interlock_mapping = {
    "speed_violation_count": {
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
        "interlock_name": "Speed Violation ThirdTime",
        "block_duration": 730,
        "block_msg": "2 years"
    },
    "night_driving_count": {
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
        "interlock_name": "Night Driving ThirdTime",
        "block_duration": 730,
        "block_msg": "2 years"
    },
    "route_deviation_count": {
        "0": {
            "interlock_name": "VTS RouteDeviation FirstTime",
            "block_duration": 90,
            "block_msg": "90 days"
        },
        "interlock_name": "VTS RouteDeviation SecondTime",
        "block_duration": 730,
        "block_msg": "2 years"
    },
    "stoppage_violations_count": {
        "0": {
            "interlock_name": "Unauthorized Stoppage FirstTime",
            "block_duration": 90,
            "block_msg": "90 days"
        },
        "interlock_name": "Unauthorized Stoppage SecondTime",
        "block_duration": 730,
        "block_msg": "2 years"
    },
    "no_halt_zone_count": {
        "0": {
            "interlock_name": "No Halt Zone FirstTime",
            "block_duration": 90,
            "block_msg": "90 days"
        },
        "interlock_name": "No Halt Zone SecondTime",
        "block_duration": 730,
        "block_msg": "2 years"
    },
    "device_offline_count": {
        "0": {
            "interlock_name": "VTS Offline FirstTime",
            "block_duration": 90,
            "block_msg": "90 days"
        },
        "interlock_name": "VTS Offline SecondTime",
        "block_duration": 730,
        "block_msg": "2 years"
    },
    "device_tamper_count": {
        "interlock_name": "VTS Device Tampering",
        "block_duration": 731,
        "block_msg": "Permanent"
    },
    "main_supply_removal_count": {
        "interlock_name": "VTS Power Disconnect",
        "block_duration": 731,
        "block_msg": "Permanent"
        }
}


