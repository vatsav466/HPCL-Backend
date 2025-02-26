import urdhva_base.utilities


# Interlock name and sop mapping for TAS Alerts
tas_interlock_mapping = [
                         {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation FirstTime","model": "VTS", "workflow_name": "TAS SOP001 90 DAYS 1st Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation SecondTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 2nd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation ThirdTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 3rd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation FourthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 4th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation FifthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 5th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation SixthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 6th Instance"},


                         {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage FirstTime", "model": "VTS", "workflow_name": "TAS SOP001 90 DAYS 1st Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage SecondTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 2nd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage ThirdTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 3rd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage FourthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 4th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage FifthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 5th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage SixthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 6th Instance"},

                         {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect FirstTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 1st Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect SecondTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 2nd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect ThirdTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 3rd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect FourthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 4th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect FifthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 5th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect SixthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 6th Instance"},
                         
                         {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering FirstTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 1st Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering SecondTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 2nd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering ThirdTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 3rd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering FourthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 4th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering FifthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 5th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering SixthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 6th Instance"},

                         {"sop_id": "SOP001", "interlock_name": "VTS Offline FirstTime", "model": "VTS", "workflow_name": "TAS SOP001 90 DAYS 1st Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Offline SecondTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 2nd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Offline ThirdTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 3rd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Offline FourthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 4th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Offline FifthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 5th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Offline SixthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 6th Instance"},

                         {"sop_id": "SOP001", "interlock_name": "Night Driving FirstTime", "model": "VTS", "workflow_name": "TAS SOP001 7 DAYS 1st Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Night Driving SecondTime", "model": "VTS", "workflow_name": "TAS SOP001 90 DAYS 2nd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Night Driving ThirdTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 3rd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Night Driving FourthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 4th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Night Driving FifthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 5th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Night Driving SixthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 6th Instance"},

                         {"sop_id": "SOP001", "interlock_name": "Speed Violation FirstTime", "model": "VTS", "workflow_name": "TAS SOP001 7 DAYS 1st Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Speed Violation SecondTime", "model": "VTS", "workflow_name": "TAS SOP001 90 DAYS 2nd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Speed Violation ThirdTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 3rd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Speed Violation FourthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 4th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Speed Violation FifthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 5th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "Speed Violation SixthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 6th Instance"},

                         {"sop_id": "SOP001", "interlock_name": "NoHalt Zone FirstTime", "model": "VTS", "workflow_name": "TAS SOP001 90 DAYS 1st Instance"},
                         {"sop_id": "SOP001", "interlock_name": "NoHalt Zone SecondTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 2nd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "NoHalt Zone ThirdTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 3rd Instance"},
                         {"sop_id": "SOP001", "interlock_name": "NoHalt Zone FourthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 4th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "NoHalt Zone FifthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 5th Instance"},
                         {"sop_id": "SOP001", "interlock_name": "NoHalt Zone SixthTime", "model": "VTS", "workflow_name": "TAS SOP001 730 DAYS 6th Instance"},

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

                         {"sop_id": "SOP001", "interlock_name": "Tank Overfill Protection", "workflow_name": "TAS TANK OVERFILL PREVENTION SOP001"},
                         {"sop_id": "SOP01A", "interlock_name": "Tank overfill prevention close inlet1 MOV", "workflow_name": "TAS TANK OVERFILL PREVENTION SOP001"},
                         {"sop_id": "SOP01A", "interlock_name": "Tank overfill prevention close inlet1 ROSOV", "workflow_name": "TAS TANK OVERFILL PREVENTION SOP001"},
                         {"sop_id": "SOP01A", "interlock_name": "Tank overfill prevention close inlet2 MOV", "workflow_name": "TAS TANK OVERFILL PREVENTION SOP001"},
                         {"sop_id": "SOP01A", "interlock_name": "Tank overfill prevention close inlet2 ROSOV", "workflow_name": "TAS TANK OVERFILL PREVENTION SOP001"},
                         {"sop_id": "SOP002", "interlock_name": "Plant ESD Closure of Effect", "workflow_name": "TAS ESD CLOSURE OF EFFECT SOP002"},
                         {"sop_id": "SOP002", "interlock_name": "EM Locks : VTS Offline - Customer", "model": "VTS", "workflow_name": ""},
                         {"sop_id": "SOP02A", "interlock_name": "All ROSOVs closed", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP02A", "interlock_name": "Tanks in TTL Dispatch in Dormant Mode", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP02A", "interlock_name": "As Power ESD Activation in Main PMCC Panel after 120 Sec", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP02A", "interlock_name": "Hooter cum strobe for ESD activated in control room", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP02A", "interlock_name": "Siren Activated", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP02A", "interlock_name": "ESD Command To Process PLC", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP02A", "interlock_name": "All DBBVs Closed", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP02A", "interlock_name": "All Tanks in Dormant Mode", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP02A", "interlock_name": "All TLF Product Pumps Stopped", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP02A", "interlock_name": "TLF Gantry Permissive Power Off", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP02A", "interlock_name": "Barrier Gate opened", "workflow_name": "ESD FIRE EFFECTS"},
                         {"sop_id": "SOP003", "interlock_name": "Tank Overfill Proof test Updated", "workflow_name": "HHH PROOF TEST"},
                         {"sop_id": "SOP003", "interlock_name": "Tank Overfill Proof test Failed", "workflow_name": "HHH PROOF TEST"},
                         {"sop_id": "SOP004", "interlock_name": "Tank Rim Seal fault Detection System", "workflow_name": "RIM SEAL"},
                         {"sop_id": "SOP005", "interlock_name": "HCDS Audio Alarm in Control Room, Audio Alarm in Field", "workflow_name": "TAS HCD ALARM SOP005"},
                         {"sop_id": "SOP006", "interlock_name": "Earthing Failure Alarm", "workflow_name": "EARTHING FAILURE"},
                         {"sop_id": "SOP007", "interlock_name": "ESD is Under Maintenance", "workflow_name": "TAS ESD MAINTENANCE"},
                         {"sop_id": "SOP008", "interlock_name": "RimSeal is Under Maintenance", "workflow_name": "TAS ESD MAINTENANCE"},
                         {"sop_id": "SOP009", "interlock_name": "Tank is Under Maintenance", "workflow_name": "TAS ROSOV UNDER MAINTENANCE"},
                         {"sop_id": "SOP010", "interlock_name": "ROSOV is Under Maintenance", "workflow_name": "TAS ROSOV UNDER MAINTENANCE"},
                         {"sop_id": "SOP011", "interlock_name": "VFT is Under Maintenance", "workflow_name": "TAS ROSOV UNDER MAINTENANCE"},
                         {"sop_id": "SOP012", "interlock_name": "Radar is Under Maintenance", "workflow_name": "TAS ROSOV UNDER MAINTENANCE"},
                         {"sop_id": "SOP013", "interlock_name": "Fire protection asset undergoing maintenance", "workflow_name": "Fire Pump Alarm"},
                         {"sop_id": "SOP014", "interlock_name": "HCD is Under Maintenance", "workflow_name": "TAS ESD MAINTENANCE"},
                         {"sop_id": "SOP015", "interlock_name": "Dyke Valve Audio Alarm in Control Room, Audio Alarm in Field", "workflow_name": "TAS HCD AND DYKE ACTIVATION"},
                         {"sop_id": "SOP016", "interlock_name": "HCD Fault Alarm", "workflow_name": "TAS HCD FAULT ALARM"},
                         {"sop_id": "SOP017", "interlock_name": "Air Compressor Fault", "workflow_name": "TAS HCD FAULT ALARM"},
                         {"sop_id": "SOP018", "interlock_name": "IL1 ROSOV failed to close", "workflow_name": "TAS HCD FAULT ALARM"},
                         {"sop_id": "SOP018", "interlock_name": "IL2 ROSOV failed to close", "workflow_name": "TAS HCD FAULT ALARM"},
                         {"sop_id": "SOP018", "interlock_name": "OL ROSOV failed to close", "workflow_name": "TAS HCD FAULT ALARM"},
                         {"sop_id": "SOP018", "interlock_name": "REC ROSOV failed to close", "workflow_name": "TAS HCD FAULT ALARM"},
                         {"sop_id": "SOP019", "interlock_name": "Fire engine fail to start", "workflow_name": "Fire Pump Alarm"},
                         {"sop_id": "SOP020", "interlock_name": "Jockey pump fail to start", "workflow_name": "Fire Pump Alarm"},
                         {"sop_id": "SOP021", "interlock_name": "PLC fault alarm", "workflow_name": "CONTROL ROOM"},
                         {"sop_id": "SOP021", "interlock_name": "UPS fail alarm", "workflow_name": "CONTROL ROOM"},
                         {"sop_id": "SOP022", "interlock_name": "LRC Master Switchover required in 30 days", "workflow_name": "CONTROL ROOM"},
                         {"sop_id": "SOP023", "interlock_name": "Firefighting system parameter", "workflow_name": "FIRE CRITICAL DATA"},
                         {"sop_id": "SOP023", "interlock_name": "All TLF Product Pumps Stopped", "workflow_name": "FIRE CRITICAL DATA"},
                         {"sop_id": "SOP023", "interlock_name": "TLF Gantry Permissive Power Off", "workflow_name": "FIRE CRITICAL DATA"},
                         {"sop_id": "SOP024", "interlock_name": "BCU Totalizer Mismatch with last day Totalizer", "workflow_name": "TOTALISER MISMATCH"},
                         {"sop_id": "SOP026", "interlock_name": "BCU Totalizer Mismatch with MFM Totalizer", "workflow_name": "K Factor Change"},
                         {"sop_id": "SOP027", "interlock_name": "K - Factor Changed", "workflow_name": "K Factor Change"},
                         {"sop_id": "SOP028", "interlock_name": "Pulse Security", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP028", "interlock_name": "K-Factors", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP028", "interlock_name": "No Flow", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP028", "interlock_name": "Low Flow", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP028", "interlock_name": "High Flow Alarm", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP028", "interlock_name": "Unauthorized Flow Alarm", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP028", "interlock_name": "Meter overrun Alarm", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP028", "interlock_name": "Blend overdose Alarm", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP028", "interlock_name": "Blend Underdose Alarm", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP028", "interlock_name": "Additive Overdose Alarm", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP028", "interlock_name": "Additive Underdose Alarm", "workflow_name": "BCU ALARM PARAMETERS"},
                         {"sop_id": "SOP029", "interlock_name": "Tank leakage alarm", "workflow_name": "TANK LEAKAGE"},
                         {"sop_id": "SOP032", "interlock_name": "Primary RG High Level alarm", "workflow_name": "TANK PRIMARY RADAR GAUGE HAND HH"},
                         {"sop_id": "SOP291", "interlock_name": "Indent Dry Out", "workflow_name": ""},
                         
                         {"sop_id": "SOP033", "interlock_name": "Non compliance of Fire Extinguisher (TT Unloading)", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP034", "interlock_name": "Fire", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP035", "interlock_name": "Spillage", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP036", "interlock_name": "Perimeter Intrusion", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP037", "interlock_name": "TT Dome Covers", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP038", "interlock_name": "valve Box in open status", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP039", "interlock_name": "Safety Harness non compliance (TT Unloading)", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP040", "interlock_name": "Wheel choke non compliance (TT Unloading)", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP041", "interlock_name": "Intrusion in nonworking hours (Storage Area/Wagon Gantry)", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP042", "interlock_name": "Obstruction on approach road (Emergency gate)", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP043", "interlock_name": "PPE non compliance", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP044", "interlock_name": "Product filling in unauthorized container (TT Gantry)", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP045", "interlock_name": "TT Crew non availability (TT unloading)", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP046", "interlock_name": "TT Crew entering below TT", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP047", "interlock_name": "Unauthorized activity in parking area", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP048", "interlock_name": "Non availability of Crash Guard in TT", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP049", "interlock_name": "Emergency gate Key Removal", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP050", "interlock_name": "Parking Discipline deviation", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP051", "interlock_name": "Unauthorized Activity (Emergency Gate opening )", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP052", "interlock_name": "Clustering of people", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP053", "interlock_name": "TT Branding non compliance", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"},
                         {"sop_id": "SOP054", "interlock_name": "Unauthorized activity (Stacking of unwanted material in shed)", "model": "VA", "workflow_name": "UC_TAS_SOP27_33"}
                         
                         {"sop_id": "SOP055", "interlock_name": "Fan Number Not Generated", "model": "EMLock", "workflow_name": ""},
                         {"sop_id": "SOP056", "interlock_name": "Swipe In Count Exceeded", "model": "EMLock", "workflow_name": ""},
                         {"sop_id": "SOP057", "interlock_name": "TT outside Terminal Radius / VTS Exception", "model": "EMLock", "workflow_name": ""},
                         {"sop_id": "SOP058", "interlock_name": "Swipe Out Count Limit Exceed", "model": "EMLock", "workflow_name": ""},
                         {"sop_id": "SOP059", "interlock_name": "Invoice Not Generated", "model": "EMLock", "workflow_name": ""},
                         {"sop_id": "SOP060", "interlock_name": "TT outside RO radius/VTS Exception", "model": "EMLock", "workflow_name": ""},
                         {"sop_id": "SOP061", "interlock_name": "OTP Count Exceed", "model": "EMLock", "workflow_name": ""}]

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
                        {"sop_id": "SOP293", "interlock_name": "Dry Out Triggering Flow"}
                        
                        {"sop_id": "SOP020", "interlock_name": "Fan Number Not Generated", "model": "EMLock", "workflow_name": ""},
                        {"sop_id": "SOP021", "interlock_name": "Swipe In Count Exceeded", "model": "EMLock", "workflow_name": ""},
                        {"sop_id": "SOP022", "interlock_name": "TT outside Terminal Radius / VTS Exception", "model": "EMLock", "workflow_name": ""},
                        {"sop_id": "SOP023", "interlock_name": "Swipe Out Count Limit Exceed", "model": "EMLock", "workflow_name": ""},
                        {"sop_id": "SOP024", "interlock_name": "Invoice Not Generated", "model": "EMLock", "workflow_name": ""},
                        {"sop_id": "SOP025", "interlock_name": "TT outside RO radius/VTS Exception", "model": "EMLock", "workflow_name": ""},
                        {"sop_id": "SOP026", "interlock_name": "OTP Count Exceed", "model": "EMLock", "workflow_name": ""}]

# Interlock name and sop mapping for LPG Alerts
lpg_interlock_mapping = [
    {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation FirstTime","model": "VTS", "workflow_name": "LPG SOP001 90 DAYS 1st Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation SecondTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 2nd Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation ThirdTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 3rd Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation FourthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 4th Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation FifthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 5th Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation SixthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 6th Instance"},


    {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage FirstTime", "model": "VTS", "workflow_name": "LPG SOP001 90 DAYS 1st Instance"},
    {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage SecondTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 2nd Instance"},
    {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage ThirdTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 3rd Instance"},
    {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage FourthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 4th Instance"},
    {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage FifthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 5th Instance"},
    {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage SixthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 6th Instance"},

    {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect FirstTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 1st Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect SecondTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 2nd Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect ThirdTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 3rd Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect FourthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 4th Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect FifthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 5th Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect SixthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 6th Instance"},
    
    {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering FirstTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 1st Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering SecondTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 2nd Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering ThirdTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 3rd Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering FourthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 4th Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering FifthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 5th Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering SixthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 6th Instance"},

    {"sop_id": "SOP001", "interlock_name": "VTS Offline FirstTime", "model": "VTS", "workflow_name": "LPG SOP001 90 DAYS 1st Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS Offline SecondTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 2nd Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS Offline ThirdTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 3rd Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS Offline FourthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 4th Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS Offline FifthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 5th Instance"},
    {"sop_id": "SOP001", "interlock_name": "VTS Offline SixthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 6th Instance"},

    {"sop_id": "SOP001", "interlock_name": "Night Driving FirstTime", "model": "VTS", "workflow_name": "LPG SOP001 7 DAYS 1st Instance"},
    {"sop_id": "SOP001", "interlock_name": "Night Driving SecondTime", "model": "VTS", "workflow_name": "LPG SOP001 90 DAYS 2nd Instance"},
    {"sop_id": "SOP001", "interlock_name": "Night Driving ThirdTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 3rd Instance"},
    {"sop_id": "SOP001", "interlock_name": "Night Driving FourthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 4th Instance"},
    {"sop_id": "SOP001", "interlock_name": "Night Driving FifthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 5th Instance"},
    {"sop_id": "SOP001", "interlock_name": "Night Driving SixthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 6th Instance"},

    {"sop_id": "SOP001", "interlock_name": "Speed Violation FirstTime", "model": "VTS", "workflow_name": "LPG SOP001 7 DAYS 1st Instance"},
    {"sop_id": "SOP001", "interlock_name": "Speed Violation SecondTime", "model": "VTS", "workflow_name": "LPG SOP001 90 DAYS 2nd Instance"},
    {"sop_id": "SOP001", "interlock_name": "Speed Violation ThirdTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 3rd Instance"},
    {"sop_id": "SOP001", "interlock_name": "Speed Violation FourthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 4th Instance"},
    {"sop_id": "SOP001", "interlock_name": "Speed Violation FifthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 5th Instance"},
    {"sop_id": "SOP001", "interlock_name": "Speed Violation SixthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 6th Instance"},

    {"sop_id": "SOP001", "interlock_name": "NoHalt Zone FirstTime", "model": "VTS", "workflow_name": "LPG SOP001 90 DAYS 1st Instance"},
    {"sop_id": "SOP001", "interlock_name": "NoHalt Zone SecondTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 2nd Instance"},
    {"sop_id": "SOP001", "interlock_name": "NoHalt Zone ThirdTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 3rd Instance"},
    {"sop_id": "SOP001", "interlock_name": "NoHalt Zone FourthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 4th Instance"},
    {"sop_id": "SOP001", "interlock_name": "NoHalt Zone FifthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 5th Instance"},
    {"sop_id": "SOP001", "interlock_name": "NoHalt Zone SixthTime", "model": "VTS", "workflow_name": "LPG SOP001 730 DAYS 6th Instance"},

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
    {"sop_id": "SOP023", "interlock_name": "Fire Extinguisher", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP024", "interlock_name": "Fire Hose is not available", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP025", "interlock_name": "Person not wearing Protective Clothing", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP026", "interlock_name": "Camera is offline", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP027", "interlock_name": "Work Beyond time", "model": "VA", "workflow_name": "UC_LPG_SOP21_27"},
    {"sop_id": "SOP029", "interlock_name": "Healthiness of Pump Operations"},
    {"sop_id": "SOP033", "interlock_name": "Healthiness of Fire Engine"},
    {"sop_id": "SOP034", "interlock_name": "Healthiness of Deluge Valve"},
    {"sop_id": "SOP077", "interlock_name": "cs_rejections", "workflow_name": "UC_LPG_SOP07_77"},
    {"sop_id": "SOP078", "interlock_name": "gd_rejections", "workflow_name": "UC_LPG_SOP08_78"},
    {"sop_id": "SOP079", "interlock_name": "pt_rejections", "workflow_name": "UC_LPG_SOP09_79"}]

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
        # for item in filtered_data:
        #     print(item)
        if len(filtered_data) > 1 and interlock_name:
            filtered_data = list(filter(lambda x: x['interlock_name'].lower() == interlock_name.lower(), filtered_data))
            print("filtered_data(1)------>", filtered_data)
    elif interlock_name:
        filtered_data = list(filter(lambda x: x['interlock_name'].lower() == interlock_name.lower(), mapping))
        print("filtered_data(2)", filtered_data)
    print("filtered_data--->", filtered_data)
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
