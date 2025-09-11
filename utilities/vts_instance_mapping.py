''' 
Here
0 = Instance 1
1 = Instance 2
2 = Instance 3

Ex: 
For instance one 
>> Speed violation 
instance_1 count = 3 which is used to add logic like > 3
instance_2 count = 2 which is used to add logic like > 2
Here for instance_2 
check the count like >3 which is on 4th count and adding >2 which is 3 then total will be 7
'''

instance_mapping = {
    "TAS":{
        "0":{
            "device_tamper_count":{
                "violation_count": 1
            },
            "main_supply_removal_count":{
                "violation_count": 1
            },
            "route_deviation_count":{
                "violation_count": 5
            },
            "stoppage_violations_count":{
                "violation_count": 5
            },
            "speed_violation_count":{
                "violation_count": 3
            },
            "night_driving_count":{
                "violation_count": 3
            },
            "continuous_driving_count":{
                "violation_count": 3
            }
        },
        "1":{
            "device_tamper_count":{
                "violation_count": 0
            },
            "main_supply_removal_count":{
                "violation_count": 0
            },
            "route_deviation_count":{
                "violation_count": 4
            },
            "stoppage_violations_count":{
                "violation_count": 4
            },
            "speed_violation_count":{
                "violation_count": 2
            },
            "night_driving_count":{
                "violation_count": 2
            },
            "continuous_driving_count":{
                "violation_count": 2
            }
        },
        "2":{
            "device_tamper_count":{
                "violation_count": 0
            },
            "main_supply_removal_count":{
                "violation_count": 0
            },
            "route_deviation_count":{
                "violation_count": 4
            },
            "stoppage_violations_count":{
                "violation_count": 4
            },
            "speed_violation_count":{
                "violation_count": 2
            },
            "night_driving_count":{
                "violation_count": 2
            },
            "continuous_driving_count":{
                "violation_count": 2
            }
        }
    },
    "LPG":{
        "0":{
            "device_tamper_count":{
                "violation_count": 0
            },
            "main_supply_removal_count":{
                "violation_count": 0
            },
            "route_deviation_count":{
                "violation_count": 5
            },
            "stoppage_violations_count":{
                "violation_count": 5
            },
            "speed_violation_count":{
                "violation_count": 3
            },
            "night_driving_count":{
                "violation_count": 3
            },
            "continuous_driving_count":{
                "violation_count": 3
            }
        },
        "1":{
            "device_tamper_count":{
                "violation_count": 0
            },
            "main_supply_removal_count":{
                "violation_count": 0
            },
            "route_deviation_count":{
                "violation_count": 5
            },
            "stoppage_violations_count":{
                "violation_count": 5
            },
            "speed_violation_count":{
                "violation_count": 3
            },
            "night_driving_count":{
                "violation_count": 3
            },
            "continuous_driving_count":{
                "violation_count": 3
            }
        },
        "2":{
            "device_tamper_count":{
                "violation_count": 0
            },
            "main_supply_removal_count":{
                "violation_count": 0
            },
            "route_deviation_count":{
                "violation_count": 5
            },
            "stoppage_violations_count":{
                "violation_count": 5
            },
            "speed_violation_count":{
                "violation_count": 3
            },
            "night_driving_count":{
                "violation_count": 3
            },
            "continuous_driving_count":{
                "violation_count": 3
            }
        }
    }
}