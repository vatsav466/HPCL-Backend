device_mapping = [
                  {
                      "device_type": "Tank", 
                      "sensor_name":
                                {
                                  "Primary Gauge Level": "Process",
                                  "Primary Gauge HIGH": "Process",
                                  "TANK LEAKAGE STATUS": "Process",
                                  "Primary Gauge HIGH HIGH": "Process",
                                  "VFT": "Safety",
                                  "LEVEL SWITCH PROOF OK": "Safety",
                                  "LEVEL SWITCH PROOF FAILED": "Safety",
                                  "RADAR PROOF TEST OK": "Safety",
                                  "RADAR PROOF TEST NOT OK": "Safety",
                                  "Seconary Radar": "Safety",
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
                                  "RimSeal": "Safety"
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
                       "device_type": "Fire Pump", 
                       "sensor_name":
                                {
                                  "PUMP ON STATUS": "Safety",
                                  "PUMP OFF STATUS": "Safety",
                                  "PUMP LR STATUS": "Safety",
                                  "FIRE PUMP MAINTENANCE (PT, Jocky, FE)": "Safety",
                                  "FIRE PUMP FAIL TO START 1": "Safety",
                                  "FIRE PUMP FAIL TO START 2": "Safety",
                                  "FIRE PUMP FAIL TO START 3": "Safety",
                                  "FIRE PUMP FAIL TO START STANDBY": "Safety",
                                  "FIRE PUMP TRIPPED FAULT": "Safety",
                                  "FIRE PUMP LLOP ALARM": "Safety",
                                  "FIRE PUMP HWT ALARM": "Safety" 
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
                                  "PLC A COMMUNICATION": "Process",
                                  "PLC B COMMUNICATION": "Process"
                                }
                    },
                    {
                        "device_type": "HCD",
                        "sensor_name":
                                 {
                                   "HCD 40% ALARM": "Safety",
                                   "HCD 20% ALARM": "Safety",
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
                        "device_type": "ESD",
                        "sensor_name": 
                                 {
                                     "ESD STATUS": "Safety",
                                     "ESD MAINTENANCE STATUS": "Safety"
                                 }
                    },
                    {
                        "device_type": "Gantry Override",
                        "sensor_name": 
                                 {
                                      "OVERRIDE STATUS": "Gantry"
                                 }
                    },
                    {
                        "device_type": "Loading Point",
                        "sensor_name": 
                                 {
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
                        "device_type": "ESD Effect",
                        "sensor_name": 
                                 {
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
                        "sensor_name": 
                                 {
                                   "TLF Gantry Permissive Power Off": "Process",
                                   "All TLF Product Pumps Stopped": "Process",
                                   "TLF Header Line MOV Close": "Process" 
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
                        "device_type": "Fire Engine",
                        "sensor_name":
                                 {
                                      "Fire Engine": "Safety"
                                 }
                    },
                    {
                        "device_type": "Jockey Pump",
                        "sensor_name":
                                 {
                                      "Jockey Pump": "Safety"
                                 }
                    },
                    {
                        "device_type": "PT Hydrant",
                        "sensor_name":
                                 {
                                      "PT Hydrant": "Safety"
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
                        "device_type": "BCU",
                        "sensor_name":
                                 {
                                      "BCU": "Safety"
                                 }
                    }
                  ]