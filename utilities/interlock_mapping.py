import urdhva_base.utilities


# Interlock name and sop mapping for TAS Alerts
tas_interlock_mapping = [
                         {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation FirstTime","model": "VTS", "workflow_name": "Tas_Vts_Deviation_FirstTime_90days"},
                         {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_SecondTime_2years"},

                         {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_FirstTime_90days"},
                         {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_SecondTime_2years"},

                         {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect", "model": "VTS", "workflow_name": "Tas_Vts_PermanantBlock"},                         
                         {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering", "model": "VTS", "workflow_name": "Tas_Vts_PermanantBlock"},

                         {"sop_id": "SOP001", "interlock_name": "VTS Offline FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_FirstTime_90days"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Offline SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_SecondTime_2years"},

                         {"sop_id": "SOP001", "interlock_name": "Night Driving FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_FirstTime_7days"},
                         {"sop_id": "SOP001", "interlock_name": "Night Driving SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_FirstTime_90days"},
                         {"sop_id": "SOP001", "interlock_name": "Night Driving ThirdTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_SecondTime_2years"},

                         {"sop_id": "SOP001", "interlock_name": "Speed Violation FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_FirstTime_7days"},
                         {"sop_id": "SOP001", "interlock_name": "Speed Violation SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_FirstTime_90days"},
                         {"sop_id": "SOP001", "interlock_name": "Speed Violation ThirdTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_SecondTime_2years"},

                         {"sop_id": "SOP001", "interlock_name": "NoHalt Zone FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_FirstTime_90days"},
                         {"sop_id": "SOP001", "interlock_name": "NoHalt Zone SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Deviation_SecondTime_2years"},

                         {"sop_id": "SOP001E", "interlock_name": "Route Deviation Exception FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_FirstTime_7days"},
                         {"sop_id": "SOP001E", "interlock_name": "Route Deviation Exception SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_ThirdTime_2years"},

                         {"sop_id": "SOP001E", "interlock_name": "Unauthorized Stoppage Exception FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_FirstTime_7days"},
                         {"sop_id": "SOP001E", "interlock_name": "Unauthorized Stoppage Exception SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_ThirdTime_2years"},

                         {"sop_id": "SOP001E", "interlock_name": "VTS PowerDisconnect Exception", "model": "VTS", "workflow_name": "Tas_Vts_Exception_ThirdTime_2years"},
                         {"sop_id": "SOP001E", "interlock_name": "VTS device Tampering Exception", "model": "VTS", "workflow_name": "Tas_Vts_Exception_ThirdTime_2years"},

                         {"sop_id": "SOP001E", "interlock_name": "VTS offline Exception FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_FirstTime_7days"},
                         {"sop_id": "SOP001E", "interlock_name": "VTS Offline Exception SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_ThirdTime_2years"},
                         
                         {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_FirstTime_7days"},
                         {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_SecondTime_90days"},
                         {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception ThirdTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_ThirdTime_2years"},


                         {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_FirstTime_7days"},
                         {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_SecondTime_90days"},
                         {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception ThirdTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_ThirdTime_2years"},

                         {"sop_id": "SOP001E", "interlock_name": "NoHalt zone Exception FirstTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_FirstTime_7days"},
                         {"sop_id": "SOP001E", "interlock_name": "NoHalt Zone Exception SecondTime", "model": "VTS", "workflow_name": "Tas_Vts_Exception_ThirdTime_2years"},

                         {"sop_id": "SOP001", "interlock_name": "EM Locks : VTS Offline - Lorry", "model": "VTS"},

                         {"sop_id": "SOP001", "interlock_name": "Tank overfill prevention(ROSV)", "workflow_name": ""},
                         {"sop_id": "SOP001", "interlock_name": "Tank Overfill Protection", "workflow_name": "Tank Overfill Protection"},
                         {"sop_id": "SOP002", "interlock_name": "Plant ESD(closure of tank ROSOVs)", "workflow_name": ""},
                         {"sop_id": "SOP002", "interlock_name": "EM Locks : VTS Offline - Customer", "model": "VTS", "workflow_name": ""},
                         {"sop_id": "SOP003", "interlock_name": "Plant ESD(Power shutdown)", "workflow_name": ""},
                         {"sop_id": "SOP004", "interlock_name": "Rim seal fire protection system", "workflow_name": ""},
                         {"sop_id": "SOP005", "interlock_name": "HCDS(Audio visual alarm in control room)", "workflow_name": ""},
                         {"sop_id": "SOP007", "interlock_name": "Tank overfill prevention(MOV)", "workflow_name": ""},
                         {"sop_id": "SOP007", "interlock_name": "Tank overfill prevention close inlet MOV", "workflow_name": "Tank overfill prevention close inlet MOV"},
                         {"sop_id": "SOP009", "interlock_name": "Plant ESD(Closure of tank MOVS)", "workflow_name": ""},
                         {"sop_id": "SOP011", "interlock_name": "Dyke drain valve position indication", "workflow_name": ""},
                         {"sop_id": "SOP012", "interlock_name": "Pulse Security Alarm", "workflow_name": ""},
                         {"sop_id": "SOP013", "interlock_name": "K factors", "workflow_name": ""},
                         {"sop_id": "SOP014", "interlock_name": "No flow alarm", "workflow_name": ""},
                         {"sop_id": "SOP015", "interlock_name": "Low flow alarm", "workflow_name": ""},
                         {"sop_id": "SOP016", "interlock_name": "High flow alarm", "workflow_name": ""},
                         {"sop_id": "SOP017", "interlock_name": "Un-Authorized Flow alarm", "workflow_name": ""},
                         {"sop_id": "SOP018", "interlock_name": "Meter Overrun Alarm", "workflow_name": ""},
                         {"sop_id": "SOP019", "interlock_name": "Blend Overdose Alarm", "workflow_name": ""},
                         {"sop_id": "SOP020", "interlock_name": "Blend Under-dose Alarm", "workflow_name": ""},
                         {"sop_id": "SOP021", "interlock_name": "Additive Overdose Alarm", "workflow_name": ""},
                         {"sop_id": "SOP022", "interlock_name": "Additive Under-dose Alarm", "workflow_name": ""},
                         {"sop_id": "SOP023", "interlock_name": "Operability Index", "workflow_name": ""},
                         {"sop_id": "SOP024", "interlock_name": "Intrusion Detection", "model": "VA", "workflow_name": "TAS_VA_Workflow"},
                         {"sop_id": "SOP024", "interlock_name": "Intrusion", "model": "VA", "workflow_name": "TAS_VA_Workflow"},
                         {"sop_id": "SOP024", "interlock_name": "Smoke Detection", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP024", "interlock_name": "Fire Detection", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP024", "interlock_name": "Fire/Smoke  ", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP024", "interlock_name": "Absence Of Wheelchock", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP025", "interlock_name": "Non-wearing of Safety Belt at Height", "model": "VA", "workflow_name": "TAS_VA_Workflow"},
                         {"sop_id": "SOP026", "interlock_name": "Non-Wearing of Safety Helmet", "model": "VA", "workflow_name": "TAS_VA_Workflow"},
                         {"sop_id": "SOP027", "interlock_name": "Person not wearing Safety Helmet", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP028", "interlock_name": "Person not wearing Safety Harness/Belt", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP029", "interlock_name": "Absence Of Fire Extinguisher Tt Operations", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP030", "interlock_name": "Fire Hose is not available", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP031", "interlock_name": "Person not wearing Protective Clothing", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP032", "interlock_name": "Camera is offline", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP033", "interlock_name": "Work Beyond time", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP291", "interlock_name": "Indent Dry Out", "workflow_name": ""}]

# Interlock name and sop mapping for RO Alerts
ro_interlock_mapping = [{"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_FirstTime_90days"},
                        {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_SecondTime_2years"},

                        {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_FirstTime_90days"},
                        {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_SecondTime_2years"},

                        {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect", "model": "VTS", "workflow_name": "Ro_Vts_PermanantBlock"},                         
                        {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering", "model": "VTS", "workflow_name": "Ro_Vts_PermanantBlock"},

                        {"sop_id": "SOP001", "interlock_name": "VTS Offline FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_FirstTime_90days"},
                        {"sop_id": "SOP001", "interlock_name": "VTS Offline SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_SecondTime_2years"},

                        {"sop_id": "SOP001", "interlock_name": "Night Driving FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_FirstTime_7days"},
                        {"sop_id": "SOP001", "interlock_name": "Night Driving SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_FirstTime_90days"},
                        {"sop_id": "SOP001", "interlock_name": "Night Driving ThirdTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_SecondTime_2years"},

                        {"sop_id": "SOP001", "interlock_name": "Speed Violation FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_FirstTime_7days"},
                        {"sop_id": "SOP001", "interlock_name": "Speed Violation SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_FirstTime_90days"},
                        {"sop_id": "SOP001", "interlock_name": "Speed Violation ThirdTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_SecondTime_2years"},

                        {"sop_id": "SOP001", "interlock_name": "NoHalt Zone FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_FirstTime_90days"},
                        {"sop_id": "SOP001", "interlock_name": "NoHalt Zone SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Deviation_SecondTime_2years"},

                        {"sop_id": "SOP001E", "interlock_name": "Route Deviation Exception FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_FirstTime_7days"},
                        {"sop_id": "SOP001E", "interlock_name": "Route Deviation Exception SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_ThirdTime_2years"},

                        {"sop_id": "SOP001E", "interlock_name": "Unauthorized Stoppage Exception FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_FirstTime_7days"},
                        {"sop_id": "SOP001E", "interlock_name": "Unauthorized Stoppage Exception SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_ThirdTime_2years"},

                        {"sop_id": "SOP001E", "interlock_name": "VTS PowerDisconnect Exception", "model": "VTS", "workflow_name": "Ro_Vts_Exception_ThirdTime_2years"},
                        {"sop_id": "SOP001E", "interlock_name": "VTS device Tampering Exception", "model": "VTS", "workflow_name": "Ro_Vts_Exception_ThirdTime_2years"},

                        {"sop_id": "SOP001E", "interlock_name": "VTS offline Exception FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_FirstTime_7days"},
                        {"sop_id": "SOP001E", "interlock_name": "VTS Offline Exception SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_ThirdTime_2years"},
                         
                        {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_FirstTime_7days"},
                        {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_SecondTime_90days"},
                        {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception ThirdTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_ThirdTime_2years"},


                        {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_FirstTime_7days"},
                        {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_SecondTime_90days"},
                        {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception ThirdTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_ThirdTime_2years"},

                        {"sop_id": "SOP001E", "interlock_name": "NoHalt zone Exception FirstTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_FirstTime_7days"},
                        {"sop_id": "SOP001E", "interlock_name": "NoHalt Zone Exception SecondTime", "model": "VTS", "workflow_name": "Ro_Vts_Exception_ThirdTime_2years"},

                        {"sop_id": "SOP001", "interlock_name": "Auto RSP Interlock"},
                        {"sop_id": "SOP002", "interlock_name": "Auto RSP Mismatch Interlock"},
                        {"sop_id": "SOP003", "interlock_name": "Testing Interlock"},
                        {"sop_id": "SOP005", "interlock_name": "k-Factor Interlock"},
                        {"sop_id": "SOP006", "interlock_name": "Tank Low Level  Interlock"},
                        {"sop_id": "SOP007", "interlock_name": "Water Level High Interlock"},
                        {"sop_id": "SOP008", "interlock_name": "Decantation Violation","model": "VA", "workflow_name": "Safety_Violation"},
                        {"sop_id": "SOP008", "interlock_name": "Absence Of Earthing","model": "VA", "workflow_name": "Safety_Violation"},
                        {"sop_id": "SOP008", "interlock_name": "Absence Of Wheelchock","model": "VA", "workflow_name": "Safety_Violation"},
                        {"sop_id": "SOP009", "interlock_name": "Alight From Two Wheeler", "model": "VA", "workflow_name": "Vehicle_Count"},
                        {"sop_id": "SOP009", "interlock_name": "Unauthorised Filling Of Container", "model": "VA", "workflow_name": "Vehicle_Count"},
                        {"sop_id": "SOP009", "interlock_name": "Vehicle Mixing", "model": "VA", "workflow_name": "Vehicle_Count"},
                        {"sop_id": "SOP009", "interlock_name": "Vehicle Cluttering", "model": "VA", "workflow_name": "Vehicle_Count"},
                        {"sop_id": "SOP009", "interlock_name": "Wrong Entry of Vehicle", "model": "VA", "workflow_name": "Vehicle_Count"},
                        {"sop_id": "SOP010", "interlock_name": "ATG Communication Failure Interlock"},
                        {"sop_id": "SOP011", "interlock_name": "TT Decantation Interlock"},
                        {"sop_id": "SOP012", "interlock_name": "FCC Offline"},
                        {"sop_id": "SOP013", "interlock_name": "High level ( ATG) interlock"},
                        {"sop_id": "SOP014", "interlock_name": "Person not wearing Safety Helmet", "model": "VA", "workflow_name": "UC_RO_SOP14_20"},
                        {"sop_id": "SOP015", "interlock_name": "Person not wearing Safety Harness/Belt", "model": "VA", "workflow_name": "UC_RO_SOP14_20"},
                        {"sop_id": "SOP016", "interlock_name": "Absence Of Fire Extinguisher Decantation", "model": "VA", "workflow_name": "UC_RO_SOP14_20"},
                        {"sop_id": "SOP017", "interlock_name": "Fire Hose is not available during UC", "model": "VA", "workflow_name": "UC_RO_SOP14_20"},
                        {"sop_id": "SOP017", "interlock_name": "Smoke Detection", "model": "VA", "workflow_name": "UC_RO_SOP14_20"},
                        {"sop_id": "SOP017", "interlock_name": "Fire Detection", "model": "VA", "workflow_name": "UC_RO_SOP14_20"},
                        {"sop_id": "SOP017", "interlock_name": "Fire/Smoke Detection", "model": "VA", "workflow_name": "UC_RO_SOP14_20"},
                        {"sop_id": "SOP018", "interlock_name": "Person not wearing Protective Clothing", "model": "VA", "workflow_name": "UC_RO_SOP14_20"},
                        {"sop_id": "SOP018", "interlock_name": "Nozzle"},
                        {"sop_id": "SOP019", "interlock_name": "Camera is offline", "model": "VA", "workflow_name": "UC_RO_SOP14_20"},
                        {"sop_id": "SOP999", "interlock_name": "Nozzle Interlock"},
                        {"sop_id": "SOP999", "interlock_name": "Bay Interlock"},
                        {"sop_id": "SOP291", "interlock_name": "Indent Dry Out", "workflow_name": "Indent Dry Out"},
                        {"sop_id": "SOP292", "interlock_name": "Dry Out Each Indent Wise MainFlow", "workflow_name": "Dry Out Each Indent Wise MainFlow"},
                        {"sop_id": "SOP293", "interlock_name": "Dry Out Triggering Flow"}]

# Interlock name and sop mapping for LPG Alerts
lpg_interlock_mapping = [
    {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_FirstTime_90days"},
    {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_SecondTime_2years"},

    {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_FirstTime_90days"},
    {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_SecondTime_2years"},

    {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect", "model": "VTS", "workflow_name": "Lpg_Vts_PermanantBlock"},                         
    {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering", "model": "VTS", "workflow_name": "Lpg_Vts_PermanantBlock"},

    {"sop_id": "SOP001", "interlock_name": "VTS Offline FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_FirstTime_90days"},
    {"sop_id": "SOP001", "interlock_name": "VTS Offline SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_SecondTime_2years"},

    {"sop_id": "SOP001", "interlock_name": "Night Driving FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_FirstTime_7days"},
    {"sop_id": "SOP001", "interlock_name": "Night Driving SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_FirstTime_90days"},
    {"sop_id": "SOP001", "interlock_name": "Night Driving ThirdTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_SecondTime_2years"},

    {"sop_id": "SOP001", "interlock_name": "Speed Violation FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_FirstTime_7days"},
    {"sop_id": "SOP001", "interlock_name": "Speed Violation SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_FirstTime_90days"},
    {"sop_id": "SOP001", "interlock_name": "Speed Violation ThirdTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_SecondTime_2years"},

    {"sop_id": "SOP001", "interlock_name": "NoHalt Zone FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_FirstTime_90days"},
    {"sop_id": "SOP001", "interlock_name": "NoHalt Zone SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Deviation_SecondTime_2years"},

    {"sop_id": "SOP001E", "interlock_name": "Route Deviation Exception FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_FirstTime_7days"},
    {"sop_id": "SOP001E", "interlock_name": "Route Deviation Exception SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_ThirdTime_2years"},

    {"sop_id": "SOP001E", "interlock_name": "Unauthorized Stoppage Exception FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_FirstTime_7days"},
    {"sop_id": "SOP001E", "interlock_name": "Unauthorized Stoppage Exception SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_ThirdTime_2years"},

    {"sop_id": "SOP001E", "interlock_name": "VTS PowerDisconnect Exception", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_ThirdTime_2years"},
    {"sop_id": "SOP001E", "interlock_name": "VTS device Tampering Exception", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_ThirdTime_2years"},

    {"sop_id": "SOP001E", "interlock_name": "VTS offline Exception FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_FirstTime_7days"},
    {"sop_id": "SOP001E", "interlock_name": "VTS Offline Exception SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_ThirdTime_2years"},
    
    {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_FirstTime_7days"},
    {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_SecondTime_90days"},
    {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception ThirdTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_ThirdTime_2years"},


    {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_FirstTime_7days"},
    {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_SecondTime_90days"},
    {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception ThirdTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_ThirdTime_2years"},

    {"sop_id": "SOP001E", "interlock_name": "NoHalt zone Exception FirstTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_FirstTime_7days"},
    {"sop_id": "SOP001E", "interlock_name": "NoHalt Zone Exception SecondTime", "model": "VTS", "workflow_name": "Lpg_Vts_Exception_ThirdTime_2years"},

    {"sop_id": "SOP001", "interlock_name": "Healthy Status of High level alarm interlock loops for vessels"},
    {"sop_id": "SOP002", "interlock_name": "Health status of Plant ESD level Interlock loops"},
    {"sop_id": "SOP003", "interlock_name": "Health status of Plant MCP level Interlock loops"},
    {"sop_id": "SOP004", "interlock_name": "Health status of Fire Water Level in Tanks"},
    {"sop_id": "SOP005", "interlock_name": "Fire Fighting Water line is under Pressure"},
    {"sop_id": "SOP006", "interlock_name": "Filling Operation  Interlock"},
    {"sop_id": "SOP007", "interlock_name": "OLD Bypass"},
    {"sop_id": "SOP007A", "interlock_name": "Loss of Communication"},
    {"sop_id": "SOP008", "interlock_name": "Checking of OLD"},
    {"sop_id": "SOP009", "interlock_name": "Quality of Cylinders in OLD Machine"},
    {"sop_id": "SOP010", "interlock_name": "VLD Bypass"},
    {"sop_id": "SOP011", "interlock_name": "Checking of VLD"},
    {"sop_id": "SOP012", "interlock_name": "Quality of Cylinders in VLD Machine"},
    {"sop_id": "SOP013", "interlock_name": "Quality of Cylinders in Water bath"},
    {"sop_id": "SOP013A", "interlock_name": "TestBath communication loss"},
    {"sop_id": "SOP014", "interlock_name": "Intrusion Detection", "model": "VA", "workflow_name": "VA_Intrusion_Detection_With_EA"},
    {"sop_id": "SOP014", "interlock_name": "Intrusion Person At Perimeter", "model": "VA", "workflow_name": "VA_Intrusion_Detection_With_EA"},
    {"sop_id": "SOP014", "interlock_name": "Missing Wheel Chock", "model": "VA", "workflow_name": "VA_Intrusion_Detection_With_EA"},
    {"sop_id": "SOP015", "interlock_name": "Non-wearing of Helmet", "model": "VA", "workflow_name": "VA_NoHelmet_Detection_With_EA"},
    {"sop_id": "SOP016", "interlock_name": "Non-wearing of Safety Belt at Height", "model": "VA", "workflow_name": "VA_NoSafetyBelt_Detection_With_EA"},
    {"sop_id": "SOP017", "interlock_name": "LPG Leakage", "model": "VA", "workflow_name": "VA_Leakage_Detection_With_EA"},
    {"sop_id": "SOP017", "interlock_name": "Lpg Leakage Detection", "model": "VA", "workflow_name": "VA_Leakage_Detection_With_EA"},
    {"sop_id": "SOP017", "interlock_name": "Lpg Leakage Filling Gun", "model": "VA", "workflow_name": "VA_Leakage_Detection_With_EA"},
    {"sop_id": "SOP017", "interlock_name": "Smoke Detection", "model": "VA", "workflow_name": "VA_Leakage_Detection_With_EA"},
    {"sop_id": "SOP017", "interlock_name": "Fire/Smoke Detection", "model": "VA", "workflow_name": "VA_Leakage_Detection_With_EA"},
    {"sop_id": "SOP017", "interlock_name": "Fire Detection", "model": "VA", "workflow_name": "VA_Leakage_Detection_With_EA"},
    {"sop_id": "SOP021", "interlock_name": "Person not wearing Safety Helmet", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP022", "interlock_name": "Person not wearing Safety Harness/Belt", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP023", "interlock_name": "Fire Extinguisher", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP024", "interlock_name": "Fire Hose is not available", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP025", "interlock_name": "Person not wearing Protective Clothing", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP026", "interlock_name": "Camera is offline", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP027", "interlock_name": "Work Beyond time", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP029", "interlock_name": "Healthiness of Pump Operations"},
    {"sop_id": "SOP033", "interlock_name": "Healthiness of Fire Engine"},
    {"sop_id": "SOP034", "interlock_name": "Healthiness of Deluge Valve"}]

rdi_interlock_mapping = [{"sop_id": "SOP001", "interlock_name": "Product Quality Density"},
                         {"sop_id": "SOP002", "interlock_name": "Product Quality Water"},
                         {"sop_id": "SOP003", "interlock_name": "Unauthorized Decantation RDI"}]


def get_interlock_name(bu, interlock_name=None, sop_id=None):
    if not bu or (not interlock_name and not sop_id):
        return {}
    mapping = eval(f'{urdhva_base.utilities.snake_case(bu)}_interlock_mapping')
    print("mapping --> ", mapping)
    filtered_data = []
    if sop_id:
        print("sop_id-->", sop_id)
        filtered_data = list(filter(lambda x: x['sop_id'].lower() == sop_id.lower(), mapping))
        print(f"Entries with sop_id '{sop_id}':")
        for item in filtered_data:
            print(item) 
        if len(filtered_data) > 1 and interlock_name:
            filtered_data = list(filter(lambda x: x['interlock_name'].lower() == interlock_name.lower(), filtered_data))
            print("filtered_data(1)------>", filtered_data)
    elif interlock_name:
        filtered_data = list(filter(lambda x: x['interlock_name'].lower() == interlock_name.lower(), mapping))
        print("filtered_data(2)", filtered_data)
    print("filtered_data--->", filtered_data[0])
    return filtered_data[0] if filtered_data else {}


def fmt_il_name(interlock_name=None):
    # Fetch interlock details from configuration
    """
    Format interlock name and return interlock details for a given BU.

    If sop_id is provided, fetches the interlock details based on the sop_id.
    If interlock_name is provided, fetches the interlock details based on the interlock_name.
    If neither sop_id nor interlock_name is provided, returns an empty dictionary.

    :param interlock_name: The name of the interlock
    :param sop_id: The SOP ID of the interlock
    :return: A dictionary containing the interlock details. The dictionary will contain the keys 'sop_id', 'interlock_name', 'location_name', 'device_name', 'device_type', 'device_id', 'state', 'city', 'zone' and 'interlock_status'. If the interlock is not found, an empty dictionary is returned.
    """
    if interlock_name:
        interlock_name = ''.join(char for char in interlock_name if char not in ' :()-/_')

    return interlock_name
