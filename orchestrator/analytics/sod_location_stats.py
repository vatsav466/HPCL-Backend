import urdhva_base
import hpcl_ceg_model
import pandas as pd
import utilities.helpers as helpers
from utilities.analog_data_mapping import Maintenance, Fault


async def generate_sod_engineering_location_stats(sap_id):
    """
    Function to get TAS location data for Engineering dashboard, This will give status of master/slave and
    Counts of Device/Equipment types with Faulty and Maintenance Count
    :param sap_id:
    :return:
    """
    status, location_data = await helpers.get_location_details('TAS', sap_id)
    if not status:
        return {"status": False, "data": "Invalid Location / Location not found"}

    try:
        query = f"sap_id='{location_data['sap_id']}'"
        params = urdhva_base.queryparams.QueryParams()
        params.fields = []
        params.q = query
        res = await hpcl_ceg_model.ArchitectureData.get_all(params, resp_type="plain")
        resp = res.get('data', '')

        if not resp:
            return {"status": False, "message": "No data found"}

        maintenance_map = {}
        fault_map = {}

        for entry in Maintenance:
            for equip in entry["equipment_name"].split(","):
                maintenance_map.setdefault(equip.strip(), set()).add(entry["interlock_name"])

        for entry in Fault:
            for equip in entry["equipment_name"].split(","):
                fault_map.setdefault(equip.strip(), set()).add(entry["interlock_name"])

        df = pd.DataFrame(resp)
        required_columns = ['device_type', 'count']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise KeyError(f"Missing columns: {missing_columns}")

        df["count"] = pd.to_numeric(df["count"], errors="coerce").fillna(0).astype(int)

        hardcoded_status = [
            {"id": "lrca", "name": "LRCA", "status": "standby"},
            {"id": "lrcb", "name": "LRCB", "status": "online"},
            {"id": "safety_plc_a", "name": "PLC A", "status": "online"},
            {"id": "safety_plc_b", "name": "PLC B", "status": "standby"},
            {"id": "process_plc_a", "name": "PLC A", "status": "online"},
            {"id": "process_plc_b", "name": "PLC B", "status": "standby"}
        ]

        DEVICE_TYPE_MAPPING = {
            "MOV": "MOV",
            "RIMSEAL": "RIMSEAL",
            "Dyke Valve": "Dyke Valve",
            "HCD": "HCD",
            "Dyke": "Dyke",
            "Hooter": "Hooter",
            "Primary Level": "Primary Radar",
            "LRC Switchover": "LRC Switchover",
            "PLC": "PLC",
            "Jockey Pump": "Jockey Pump",
            "Fire Effect": "Fire Effect",
            "UPS": "UPS",
            "Gantry override": "Gantry override",
            "VFT": "VFT",
            "PT": "PT Hydrant",
            "ROSOV": "Rosov",
            "ESD": "ESD",
            "Pump": "Pumps",
            "OI Tags": "OI Tags",
            "Radar": "Secondary Radar",
            "Fire Engine": "Fire Engine",
            "ESD Effect": "ESD Effect",
            "Barrier Gate": "Barrier Gate",
            "Power ESD": "Power ESD",
            "Gantry BCU": "Gantry BCU",
            "MFM": "MFM"
        } 

        result = []
        result.extend(hardcoded_status)

        for _, row in df.iterrows():
            device_name = row["device_type"]
            total = row["count"]

            mapped_name = DEVICE_TYPE_MAPPING.get(device_name, device_name)
            device_id = mapped_name.lower().replace(" ", "_")

            unique_maintenance_interlocks = maintenance_map.get(device_name, set())
            total_maintenance_count = len(unique_maintenance_interlocks)

            unique_fault_interlocks = fault_map.get(device_name, set())
            total_fault_count = len(unique_fault_interlocks)

            device_data = {
                "id": device_id,
                "name": mapped_name,
                "total": total,
                "faulty": total_fault_count,
                "maintanance": total_maintenance_count
            }

            result.append(device_data)

        return {"status": True, "message": "Success", "data": result}

    except Exception as e:
        return {"status": False, "message": f"Error: {str(e)}"}

async def get_alert_count_for_interlock(interlock):
    """
    This function checks the alert table for the count of a specific interlock.
    """
    if not interlock:
        return 0

    query = f"interlock_name='{interlock}'"
    params = urdhva_base.queryparams.QueryParams()
    params.q = query
    count = await hpcl_ceg_model.Alerts.count(params)
    return count

    # Hardcoded data for UI development purpose
    # json_data = [{"id": "lrca", "name": "LRCA", "status": "standby"},
    #              {"id": "lrcb", "name": "LRCB", "status": "online"},
    #              {"id": "safety_plc_a", "name": "PLC A", "status": "online"},
    #              {"id": "safety_plc_b", "name": "PLC B", "status": "standby"},
    #              {"id": "process_plc_a", "name": "PLC A", "status": "online"},
    #              {"id": "process_plc_b", "name": "PLC B", "status": "standby"},
    #              {"id": "gantry_bcu", "name": "Gantry BCU ", "total": 34, "faulty": 1, "maintanance": 1},
    #              {"id": "mfm", "name": "MFM", "total": 10, "faulty": 1, "maintanance": 0},
    #              {"id": "primary_radar", "name": "Primary Radar", "total": 11, "faulty": 0, "maintanance": 0},
    #              {"id": "mov", "name": "MOV", "total": 30, "faulty": 0, "maintanance": 0},
    #              {"id": "pumps", "name": "Pumps", "total": 14, "faulty": 0, "maintanance": 1},
    #              {"id": "barrier_gate", "name": "Barrier Gate", "total": 6, "faulty": 0, "maintanance": 0},
    #              {"id": "rosov", "name": "Rosov", "total": 30, "faulty": 1, "maintanance": 1},
    #              {"id": "vft", "name": "VFT", "total": 5, "faulty": 0, "maintanance": 0},
    #              {"id": "secondary_radar", "name": "Secondary Radar", "total": 5, "faulty": 0, "maintanance": 0},
    #              {"id": "pt_hydrant", "name": "PT Hydrant", "total": 1, "faulty": 0, "maintanance": 0},
    #              {"id": "hooter", "name": "Hooter", "total": 20, "faulty": 0, "maintanance": 4},
    #              {"id": "esd", "name": "ESD", "total": 10, "faulty": 0, "maintanance": 0},
    #              {"id": "fire_engine", "name": "Fire Engine", "total": 4, "faulty": 0, "maintanance": 0},
    #              {"id": "hcd", "name": "HCD", "total": 11, "faulty": 0, "maintanance": 0},
    #              {"id": "dyke", "name": "Dyke", "total": 4, "faulty": 0, "maintanance": 0},
    #              {"id": "jockey_pump", "name": "Jockey Pump", "total": 4, "faulty": 1, "maintanance": 1},
    #              {"id": "air_compressor", "name": "Air Compressor", "total": 6, "faulty": 0, "maintanance": 1}]
    # return {"status": True, "data":  json_data}

async def get_filtered_location_data(bu, location_onboard, specific_zone=None, specific_sap_id=None):
    """
    This function is used to get the filtered location data based on the location onboard flag, specific zone and specific sap_id.
    
    Parameters:
    bu (str): The business unit identifier.
    location_onboard (bool): The location onboard flag.
    specific_zone (str): The specific zone to filter by.
    specific_sap_id (str): The specific sap_id to filter by.
    
    Returns:
    dict: A dictionary containing the filtered zone and sap_id lists.
    """
    query = f"bu = '{bu}' and location_onboard = '{location_onboard}'"
    params = urdhva_base.queryparams.QueryParams(q=query)
    resp = await hpcl_ceg_model.LocationMaster.get_all(params, resp_type='plain')
    
    if not resp.get("data"):
        return {"status": False, "message": "No Data found", "data": []}
    
    data = resp.get("data", '')
    # Now create zone and sap_id lists
    zone_list = []
    sap_id_list = []

    for item in data:
        zone = item.get("zone")
        sap_id = item.get("sap_id")
        name = item.get("name", "")
        
        # If specific_zone is provided, only collect sap_ids for that zone
        if specific_zone and zone == specific_zone:
            if sap_id:
                sap_id_list.append({"id": sap_id, "name": name})
        
        # If specific_sap_id is provided, only collect zones for that sap_id
        elif specific_sap_id and sap_id == specific_sap_id:
            if zone:
                zone_list.append({"id": zone, "name": zone})
        
        # If no specific filters, collect all data
        elif not specific_zone and not specific_sap_id:
            if zone:
                zone_list.append({"id": zone, "name": zone})
            if sap_id:
                sap_id_list.append({"id": sap_id, "name": name})

    # Remove duplicates
    zone_list = [dict(t) for t in {tuple(d.items()) for d in zone_list}]
    sap_id_list = [dict(t) for t in {tuple(d.items()) for d in sap_id_list}]

    return {
        "status": True,
        "message": "Success",
        "data": {
            "zone": zone_list,
            "sap_id": sap_id_list
        }
    }