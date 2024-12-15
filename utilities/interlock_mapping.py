import urdhva_base.utilities


# Interlock name and sop mapping for TAS Alerts
tas_interlock_mapping = [{"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation SecondTime", "model": "VTS",
                          "block_duration": 730, "block_msg": "2 years"},
                         {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage FirstTime", "model": "VTS",
                          "block_duration": 90, "block_msg": "90 days"},
                         {"sop_id": "SOP001", "interlock_name": "Unauthorized Stoppage SecondTime", "model": "VTS",
                          "block_duration": 730, "block_msg": "2 years"},
                         {"sop_id": "SOP001", "interlock_name": "VTS RouteDeviation FirstTime", "model": "VTS",
                          "block_duration": 90, "block_msg": "90 days"},
                         {"sop_id": "SOP001", "interlock_name": "VTS PowerDisconnect", "model": "VTS"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Offline FirstTime", "model": "VTS",
                          "block_duration": 90, "block_msg": "90 days"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Offline SecondTime", "model": "VTS",
                          "block_duration": 730, "block_msg": "2 years"},
                         {"sop_id": "SOP001", "interlock_name": "Tank overfill prevention(ROSV)"},
                         {"sop_id": "SOP001", "interlock_name": "Night Driving FirstTime", "model": "VTS",
                          "block_duration": 7, "block_msg": "7 days"},
                         {"sop_id": "SOP001", "interlock_name": "VTS Device Tampering", "model": "VTS",
                          "block_duration": 1460, "block_msg": "Permanent"},
                         {"sop_id": "SOP001", "interlock_name": "Night Driving SecondTime", "model": "VTS",
                          "block_duration": 90, "block_msg": "90 days"},
                         {"sop_id": "SOP001", "interlock_name": "Night Driving ThirdTime", "model": "VTS",
                          "block_duration": 730, "block_msg": "2 years"},
                         {"sop_id": "SOP001", "interlock_name": "Speed Violation FirstTime", "model": "VTS",
                          "block_duration": 7, "block_msg": "7 days"},
                         {"sop_id": "SOP001", "interlock_name": "NoHalt Zone FirstTime", "model": "VTS",
                          "block_duration": 90, "block_msg": "90 days"},
                         {"sop_id": "SOP001", "interlock_name": "NoHalt Zone SecondTime", "model": "VTS",
                          "block_duration": 730, "block_msg": "2 years"},
                         {"sop_id": "SOP001", "interlock_name": "Speed Violation SecondTime", "model": "VTS",
                          "block_duration": 90, "block_msg": "90 days"},
                         {"sop_id": "SOP001", "interlock_name": "Speed Violation ThirdTime", "model": "VTS",
                          "block_duration": 730, "block_msg": "2 years"},
                         {"sop_id": "SOP001", "interlock_name": "EM Locks : VTS Offline - Lorry", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "Route Deviation Exception SecondTime",
                          "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "VTS Offline Exception SecondTime", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "Unauthorized Stoppage Exception SecondTime",
                          "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "Route Deviation Exception FirstTime", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "Unauthorized Stoppage Exception FirstTime",
                          "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "VTS PowerDisconnect Exception", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "VTS offline Exception FirstTime", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception FirstTime", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "VTS device Tampering Exception", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception SecondTime", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception FirstTime", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "NoHalt zone Exception FirstTime", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "Night Driving Exception ThirdTime", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "NoHalt Zone Exception SecondTime", "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception SecondTime",
                          "model": "VTS"},
                         {"sop_id": "SOP001E", "interlock_name": "Speed Violation Exception ThirdTime", "model": "VTS"},
                         {"sop_id": "SOP002", "interlock_name": "Plant ESD(closure of tank ROSOVs)"},
                         {"sop_id": "SOP002", "interlock_name": "EM Locks : VTS Offline - Customer", "model": "VTS"},
                         {"sop_id": "SOP003", "interlock_name": "Plant ESD(Power shutdown)"},
                         {"sop_id": "SOP004", "interlock_name": "Rim seal fire protection system"},
                         {"sop_id": "SOP005", "interlock_name": "HCDS(Audio visual alarm in control room)"},
                         {"sop_id": "SOP007", "interlock_name": "Tank overfill prevention(MOV)"},
                         {"sop_id": "SOP009", "interlock_name": "Plant ESD(Closure of tank MOVS)"},
                         {"sop_id": "SOP011", "interlock_name": "Dyke drain valve position indication"},
                         {"sop_id": "SOP012", "interlock_name": "Pulse Security Alarm"},
                         {"sop_id": "SOP013", "interlock_name": "K factors"},
                         {"sop_id": "SOP014", "interlock_name": "No flow alarm"},
                         {"sop_id": "SOP015", "interlock_name": "Low flow alarm"},
                         {"sop_id": "SOP016", "interlock_name": "High flow alarm"},
                         {"sop_id": "SOP017", "interlock_name": "Un-Authorized Flow alarm"},
                         {"sop_id": "SOP018", "interlock_name": "Meter Overrun Alarm"},
                         {"sop_id": "SOP019", "interlock_name": "Blend Overdose Alarm"},
                         {"sop_id": "SOP020", "interlock_name": "Blend Under-dose Alarm"},
                         {"sop_id": "SOP021", "interlock_name": "Additive Overdose Alarm"},
                         {"sop_id": "SOP022", "interlock_name": "Additive Under-dose Alarm"},
                         {"sop_id": "SOP023", "interlock_name": "Operability Index"},
                         {"sop_id": "SOP024", "interlock_name": "Intrusion Detection", "model": "VA"},
                         {"sop_id": "SOP024", "interlock_name": "Valve Open TAS", "model": "VA"},
                         {"sop_id": "SOP025", "interlock_name": "Non-wearing of Safety Belt at Height", "model": "VA"},
                         {"sop_id": "SOP026", "interlock_name": "Non-Wearing of Safety Helmet", "model": "VA"},
                         {"sop_id": "SOP027", "interlock_name": "Person not wearing Safety Helmet", "model": "VA"},
                         {"sop_id": "SOP028", "interlock_name": "Person not wearing Safety Harness/Belt",
                          "model": "VA"},
                         {"sop_id": "SOP029", "interlock_name": "Fire Extinguisher is not available", "model": "VA"},
                         {"sop_id": "SOP030", "interlock_name": "Fire Hose is not available", "model": "VA"},
                         {"sop_id": "SOP031", "interlock_name": "Person not wearing Protective Clothing",
                          "model": "VA"},
                         {"sop_id": "SOP032", "interlock_name": "Camera is offline", "model": "VA"},
                         {"sop_id": "SOP033", "interlock_name": "Work Beyond time", "model": "VA"},
                         {"sop_id": "SOP034", "interlock_name": "Tas Loss of communication VA", "model": "VA"},
                         {"sop_id": "SOP291", "interlock_name": "Indent Dry Out"}]

# Interlock name and sop mapping for RO Alerts
ro_interlock_mapping = [{"sop_id": "SOP001", "interlock_name": "Auto RSP Interlock"},
                        {"sop_id": "SOP001", "interlock_name": "Auto RSP Interlock"},
                        {"sop_id": "SOP002", "interlock_name": "Auto RSP Mismatch Interlock"},
                        {"sop_id": "SOP003", "interlock_name": "Testing Interlock"},
                        {"sop_id": "SOP005", "interlock_name": "k-Factor Interlock"},
                        {"sop_id": "SOP006", "interlock_name": "Tank Low Level  Interlock"},
                        {"sop_id": "SOP007", "interlock_name": "Water Level High Interlock"},
                        {"sop_id": "SOP008", "interlock_name": "Absence Of Sand Bucket Decantation RO",
                         "model": "VA"},
                        {"sop_id": "SOP008", "interlock_name": "Absence Of Sand Bucket RO","model": "VA"},
                        {"sop_id": "SOP009", "interlock_name": "Overstaying Of Heavy Vehicle RO", "model": "VA"},
                        {"sop_id": "SOP009", "interlock_name": "Overstaying Of Four Wheelers RO", "model": "VA"},
                        {"sop_id": "SOP009", "interlock_name": "Overstaying Of Two Wheelers RO", "model": "VA"},
                        {"sop_id": "SOP010", "interlock_name": "ATG Communication Failure Interlock"},
                        {"sop_id": "SOP011", "interlock_name": "TT Decantation Interlock"},
                        {"sop_id": "SOP012", "interlock_name": "FCC Offline"},
                        {"sop_id": "SOP013", "interlock_name": "High level ( ATG) interlock"},
                        {"sop_id": "SOP016", "interlock_name": "Absence Of Fire Extinguisher RO", "model": "VA"},
                        {"sop_id": "SOP018", "interlock_name": "Nozzle"},
                        {"sop_id": "SOP999", "interlock_name": "Nozzle Interlock"},
                        {"sop_id": "SOP999", "interlock_name": "Bay Interlock"},
                        {"sop_id": "SOP291", "interlock_name": "Indent Dry Out"}]

# Interlock name and sop mapping for LPG Alerts
lpg_interlock_mapping = [
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
    {"sop_id": "SOP014", "interlock_name": "Intrusion Detection", "model": "VA"},
    {"sop_id": "SOP015", "interlock_name": "Non-wearing of Helmet", "model": "VA"},
    {"sop_id": "SOP016", "interlock_name": "Non-wearing of Safety Belt at Height", "model": "VA"},
    {"sop_id": "SOP017", "interlock_name": "LPG Leakage/Fire in Plant", "model": "VA"},
    {"sop_id": "SOP018", "interlock_name": "Loss of communication(VA)", "model": "VA"},
    {"sop_id": "SOP021", "interlock_name": "Ppe Compliance LPG", "model": "VA"},
    {"sop_id": "SOP022", "interlock_name": "Person not wearing Safety Harness/Belt", "model": "VA"},
    {"sop_id": "SOP023", "interlock_name": "Fire Extinguisher LPG", "model": "VA"},
    {"sop_id": "SOP024", "interlock_name": "Fire Hose is not available", "model": "VA"},
    {"sop_id": "SOP025", "interlock_name": "Person not wearing Protective Clothing", "model": "VA"},
    {"sop_id": "SOP026", "interlock_name": "Camera is offline", "model": "VA"},
    {"sop_id": "SOP027", "interlock_name": "Work Beyond time", "model": "VA"},
    {"sop_id": "SOP029", "interlock_name": "Healthiness of Pump Operations"},
    {"sop_id": "SOP033", "interlock_name": "Healthiness of Fire Engine"},
    {"sop_id": "SOP034", "interlock_name": "Healthiness of Deluge Valve"}]

rdi_interlock_mapping = [{"sop_id": "SOP001", "interlock_name": "Product Quality Density"},
                         {"sop_id": "SOP002", "interlock_name": "Product Quality Water"},
                         {"sop_id": "SOP003", "interlock_name": "Unauthorized Decantation RDI"}]


# def get_interlock_name(bu, interlock_name=None, sop_id=None):
#     # Fetch interlock details from configuration
#     if not bu or (not interlock_name and not sop_id):
#         return {}
#     mapping = eval(f'{urdhva_base.utilities.snake_case(bu)}_interlock_mapping')
#     filtered_data = []
#     if sop_id:
#         filtered_data = list(filter(lambda x: x['sop_id'].lower() == sop_id.lower(), mapping))
#     elif interlock_name:
#         filtered_data = list(filter(lambda x: x['interlock_name'].lower() == interlock_name.lower(), mapping))
#     elif sop_id and interlock_name:
#         filtered_data = list(filter(lambda x: x['sop_id'].lower() == sop_id.lower() and x['interlock_name'].lower() == interlock_name.lower(), mapping))
#     print("filtered_data--->", filtered_data[0])
#     return filtered_data[0] if filtered_data else {}

def get_interlock_name(bu, interlock_name=None, sop_id=None):
    # Fetch interlock details from configuration
    if not bu or (not interlock_name and not sop_id):
        return {}
    mapping = eval(f'{urdhva_base.utilities.snake_case(bu)}_interlock_mapping')
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
    #print("filtered_data--->", filtered_data[0])
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
        interlock_name = ''.join(char for char in interlock_name if char not in ' :()-/')

    return interlock_name
