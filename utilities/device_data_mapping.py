device_mapping = [
                  {
                      "device_type": "Tank", 
                      "sensor_name":
                                {
                                  "Primary Gauge Level": "Process",
                                  "Primary Gauge HIGH": "Process",
                                  "TANK LEAKAGE STATUS": "Process",
                                  "Primary Gauge HIGH HIGH": "Process",
                                  "LEVEL SWITCH": "Safety",
                                  "LEVEL SWITCH PROOF OK": "Safety",
                                  "LEVEL SWITCH PROOF FAILED": "Safety",
                                  "RADAR HHH": "Safety",
                                  "RADAR PROOF OK": "Safety",
                                  "RADAR PROOF FAILED": "Safety",
                                  "ROSOV OPEN STATUS IL1": "Safety",
                                  "ROSOV FAIL TO CLOSE STATUS IL1": "Safety",
                                  "ROSOV OPEN STATUS IL2": "Safety",
                                  "ROSOV FAIL TO CLOSE STATUS IL2": "Safety",
                                  "ROSOV OPEN STATUS OL": "Safety",
                                  "ROSOV FAIL TO CLOSE STATUS OL": "Safety",
                                  "ROSOV OPEN STATUS RCL": "Safety",
                                  "ROSOV FAIL TO CLOSE STATUS RCL": "Safety",
                                  "MOV STATUS IL1": "Safety",
                                  "MOV STATUS IL2": "Safety",
                                  "MOV STATUS OL": "Safety",
                                  "MOV STATUS RCL": "Safety",
                                  "RIMSEAL FIRE ALARM": "Safety",
                                  "RIMSEAL FAULT ALARM": "Safety"
                                }
                    },
                    {
                       "device_type": "Tank Maintenance",
                       "sensor_name":
                                {
                                  "TANK MAINTENANCE": "Safety",
                                  "LEVEL SWITCH MAINTENANCE": "Safety",
                                  "RADAR MAINTENANCE": "Safety",
                                  "ROSOV MAINTENANCE IL1": "Safety",
                                  "ROSOV MAINTENANCE IL2": "Safety",
                                  "ROSOV MAINTENANCE OL": "Safety",
                                  "ROSOV MAINTENANCE RCL": "Safety",
                                  "MOV MAINTENANCE IL1": "Safety",
                                  "MOV MAINTENANCE IL2": "Safety",
                                  "MOV MAINTENANCE RCL": "Safety",
                                  "MOV MAINTENANCE OL": "Safety",
                                  "RIM SEAL MAINTENANCE STATUS": "Safety"
                                }
                    },
                    {
                        "device_type":"Pump",
                        "sensor_name":{
                            "PUMP ON STATUS": "Process",
                            "PUMP OFF STATUS": "Process",
                            "PUMP LR STATUS": "Process"
                        }
                    },
                     {
                       "device_type": "Fire Pump", 
                       "sensor_name":
                                {
                                  "PUMP ON STATUS": "Safety",
                                  "PUMP OFF STATUS": "Safety",
                                  "PUMP LR STATUS": "Safety",
                                  "FIRE PUMP MAINTENANCE": "Safety",
                                  "FIRE PUMP FAIL TO START 1": "Safety",
                                  "FIRE PUMP FAIL TO START 2": "Safety",
                                  "FIRE PUMP FAIL TO START 3": "Safety",
                                  "FIRE PUMP FAIL TO START 4":"Safety",
                                  "FIRE PUMP FAIL TO START 5":"Safety",
                                  "FIRE PUMP FAIL TO START STANDBY": "Safety",
                                  "FIRE PUMP FAIL TO START STANDBY1": "Safety",
                                  "FIRE PUMP FAIL TO START STANDBY2": "Safety",
                                  "FIRE PUMP TRIPPED FAULT": "Safety",
                                  "FIRE PUMP LLOP ALARM": "Safety",
                                  "FIRE PUMP HWT ALARM": "Safety",
                                 
                                }
                    },
                    {
                        "device_type": "UPS",
                        "sensor_name":
                                 {
                                   "UPS FAIL": "Process",
                                   "LOW BATTERY": "Process",
                                   "UPS ON": "Process",
                                   "UPS MAIN AC FAIL": "Process"

                                 }

                    },
                    {
                        "device_type": "PLC",
                        "sensor_name":
                                {
                                  "PLC A is Master": "Process",
                                  "PLC B is Master": "Process",
                                  "PLC A FAIL SAFE": "Process",
                                  "PLC B FAIL SAFE": "Process",
                                  "PLC A COOMUNCIATION": "Process",
                                  "PLC A COOMUNCIATION": "Process"
                                }
                    },
                    {
                        "device_type": "HCD",
                        "sensor_name":
                                 {
                                   "HCD 40 % ALARM": "Safety",
                                   "HCD 20 % ALARM": "Safety",
                                   "HCD FAULT": "Safety",
                                   "MISALIGNMENT FAULT": "Safety",
                                   "HCD MAINTENANCE": "Safety"
                                 }
                    },
                    {
                        "device_type": "Dyke",
                        "sensor_name":
                                {
                                    "DYKE VALVE STATUS": "Safety"
                                }
                    },
                    {
                        "device_type":"Barrier Gate",
                        "sensor_name":{
                            "BARRIER GATE OPEN STATUS": "Process",
                            "BARRIER GATE CLOSE STATUS":"Process",
                            "BARRIER GATE LR STATUS":"Process"
                        }
                    },
                    {
                       "device_type":"Hooter",
                       "sensor_name": {
                            "HOOTER STATUS":"Safety"
                        }
                    },
                    {
                        "device_type": "ESD",
                        "sensor_name": 
                                 {
                                     "ESD STATUS": "Safety",
                                     "ESD MAINTENANCE STATUS": "Safety"
                                 }
                    },
                  
                    {
                        "device_type": "Loading Point",
                        "sensor_name": 
                                 {
                                  "LP Earthing STATUS": "Process",
                                  "NO FLOW STATUS OF MAIN": "Gantry",
                                  "LOW FLOW STATUS OF MAIN": "Gantry",
                                  "HIGH FLOW STATUS OF MAIN": "Gantry",
                                  "UNAUTHORISE FLOW STATUS OF MAIN": "Gantry",
                                  "METER OVERRUN STATUS OF MAIN": "Gantry",
                                  "BLEND OVERDOSE STATUS OF MAIN": "Gantry",
                                  "BLEND UNDERDOSE STATUS OF MAIN": "Gantry",
                                  "ADD OVERDOSE STATUS OF MAIN": "Gantry",
                                  "ADD UNDERDOSE STATUS OF MAIN": "Gantry",
                                  "BCU LOADING STATUS": "Gantry",
                                  "K-FACTOR CHANGE STATUS": "Gantry",
                                  "BCU VS MFM TOTALIZER MISMATCH": "Gantry",
                                  "DAY START TOTALIZER MISMATCH": "Gantry"
                                 }
                    },
                    {
                        "device_type": "Gantry override",
                        "sensor_name": 
                                 {
                                      "OVERRIDE STATUS": "Gantry"
                                 }
                    },
                    {
                        "device_type": "ESD Effect",
                        "sensor_name": 
                                 {
                                  "Cause": "Safety",
                                   "All ROSOVs Closed": "Safety",
                                   "Barrier Gate Opened": "Process",
                                   "TLF Gantry Permissive Power Off": "Process",
                                   "All TLF Product Pumps Stopped": "Process",
                                   "All Tanks in Dormant Mode": "Process",
                                   "All DBBVs Closed": "Process",
                                   "ESD Command to Process PLC": "Safety",
                                   "Siren Activated": "Process",
                                   "ESD Hooter Activated in Control Room": "Safety",
                                   "Power ESD Activation After 120 Sec": "Safety",
                                   "TTL Dispatch in Dormant Mode": "Process"
                                 }
                    },
                    {
                        "device_type": "Fire Effect",
                        "sensor_name":{
                            "Cause":"Safety",
                            "TLF Gantry Permissive Power Off":"Process",
                            "All TLF Product Pumps Stopped":"Process",
                            "TLF Header Line MOV Close":"Process"
                        }
                    },
                    {
                        "device_type": "Air Compressor",
                        "sensor_name":
                                 {
                                      "Air Compressor": "Safety"
                                 }
                    },
                    {
                        "device_type": "LRC Switchover",
                        "sensor_name": 
                                 {
                                      "LRC SWITCHOVER 30 DAYS STATUS": "Process"
                                 }
                    },
                    {
                        "device_type": "OI",
                        "sensor_name":
                                 {
                                      "Fire Engine":"Safety",
                                      "Jockey Pump Run":"Safety",
                                      "Farthest Point Pt":"Safety",
                                      "Nearest Point PT":"Safety"
                                 }
                    },
                     
                  ]