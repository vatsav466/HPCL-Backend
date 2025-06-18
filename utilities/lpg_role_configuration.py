lpg_role_mapping={
    "LPG": {
        "Check Scale Rejection": {
            "name": "Check Scale Rejection",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 0,
                    "assign_role": "Maintenance Officer LPG",
                    "escalation_role": "Maintenance Officer LPG",
                    "escalation_time": "PT24H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 1,
                    "assign_role": "Location In-Charge LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "PT24H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 2,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal Operations Head LPG",
                    "escalation_time": "PT24H"
                },
                "level - 4": {
                    "condition": ">",
                    "value": 3,
                    "assign_role": "HQO LPG",
                    "escalation_role": "HQO LPG",
                    "escalation_time": "PT24H"
                }
            }
        },
        "Valve Leak Rejection": {
            "name": "Valve Leak Rejection",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 0,
                    "assign_role": "Maintenance Officer LPG",
                    "escalation_role": "Maintenance Officer LPG",
                    "escalation_time": "PT24H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 1,
                    "assign_role": "Location In-Charge LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "PT24H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 2,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal Operations Head LPG",
                    "escalation_time": "PT24H"
                },
                "level - 4": {
                    "condition": ">",
                    "value": 3,
                    "assign_role": "HQO LPG",
                    "escalation_role": "HQO LPG",
                    "escalation_time": "PT24H"
                }
            }
        },
        "O-Ring Leak Rejection": {
            "name": "O-Ring Leak Rejection",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 0,
                    "assign_role": "Maintenance Officer LPG",
                    "escalation_role": "Maintenance Officer LPG",
                    "escalation_time": "PT24H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 1,
                    "assign_role": "Location In-Charge LPG",
                    "escalation_role": "Location In-Charge LPG",
                    "escalation_time": "PT24H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 2,
                    "assign_role": "Zonal Operations Head LPG",
                    "escalation_role": "Zonal Operations Head LPG",
                    "escalation_time": "PT24H"
                },
                "level - 4": {
                    "condition": ">",
                    "value": 3,
                    "assign_role": "HQO LPG",
                    "escalation_role": "HQO LPG",
                    "escalation_time": "PT24H"
                }
            }
        }
    }
}