Cris_Alert_Mapping = {
    "RO": {
        "Product Low Level": {
            "name": "Product Low Level",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 3,
                    "assign_role": "Sales Officer RO",
                    "escalation_role": "Regional Manager RO",
                    "escalation_time": "PT6H"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 5,
                    "assign_role": "Regional Manager RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "PT6H"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 5,
                    "assign_role": "Zonal Head RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "PT12H"
                }
            }
        },
        "High Water Level": {
            "name": "High Water Level",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 3,
                    "assign_role": "Sales Officer RO",
                    "escalation_role": "Regional Manager RO",
                    "escalation_time": "P2D"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 6,
                    "assign_role": "Regional Manager RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "P2D"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 6,
                    "assign_role": "Zonal Head RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "P2D"
                }
            }
        },
        "TT Receipt": {
            "name": "TT Receipt",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 2,
                    "assign_role": "Sales Officer RO",
                    "escalation_role": "Regional Manager RO",
                    "escalation_time": "P1D"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 6,
                    "assign_role": "Regional Manager RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "P2D"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 6,
                    "assign_role": "Zonal Head RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "P2D"
                }
            }
        },
        "Decantation": {
            "name": "Decantation",
            "severity": "Critical",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 3,
                    "assign_role": "Sales Officer RO",
                    "escalation_role": "Regional Manager RO",
                    "escalation_time": "P1D"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 7,
                    "assign_role": "Regional Manager RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "P1D"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 7,
                    "assign_role": "Zonal Head RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "P2D"
                }
            }
        },
        "NANF": {
            "name": "NANF",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 2,
                    "assign_role": "Sales Officer RO",
                    "escalation_role": "Regional Manager RO",
                    "escalation_time": "P2D"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 5,
                    "assign_role": "Regional Manager RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "P2D"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 5,
                    "assign_role": "Zonal Head RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "P2D"
                }
            }
        },
        "No Pump Test": {
            "name": "No Pump Test",
            "severity": "High",
            "period": "weekly",
            "escalations": {
                "level - 1": {
                    "condition": "<",
                    "value": 3,
                    "assign_role": "Sales Officer RO",
                    "escalation_role": "Regional Manager RO",
                    "escalation_time": "P2D"
                },
                "level - 2": {
                    "condition": "<>",
                    "value": 7,
                    "assign_role": "Regional Manager RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "P2D"
                },
                "level - 3": {
                    "condition": ">",
                    "value": 7,
                    "assign_role": "Zonal Head RO",
                    "escalation_role": "Zonal Head RO",
                    "escalation_time": "P6D"
                }
            }
        }
    }
}
