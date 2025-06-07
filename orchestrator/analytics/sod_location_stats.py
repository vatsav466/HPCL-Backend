import urdhva_base
import traceback
import hpcl_ceg_model
import pandas as pd
import polars as pl
import utilities.helpers as helpers
from utilities.analog_data_mapping import Maintenance, Fault


async def generate_sod_engineering_location_stats(sap_id):
    status, location_data = await helpers.get_location_details('TAS', sap_id)
    if not status:
        return {"status": False, "data": "Invalid Location / Location not found"}

    device_types = (
        'MOV', 'HCD', 'Dyke', 'Hooter', 'Primary Level', 'Jockey Pump', 'VFT',
        'PT', 'ROSOV', 'ESD', 'Pump', 'Radar', 'Fire Engine', 'Barrier Gate',
        'Gantry BCU', 'MFM'
    )

    try:
        query = f"sap_id = '{location_data['sap_id']}' and device_type in {device_types}"
        params = urdhva_base.queryparams.QueryParams()
        params.fields = []
        params.q = query
        res = await hpcl_ceg_model.ArchitectureData.get_all(params, resp_type="plain")
        resp = res.get('data', '')

        if not resp:
            return {"status": False, "message": "No data found"}

        # Mapping interlocks
        maintenance_map = {}
        fault_map = {}

        for entry in Maintenance:
            equipment_names = entry.get("equipment_name", [])
            if isinstance(equipment_names, str):
                equipment_names = equipment_names.split(",")

            for equip in equipment_names:
                maintenance_map.setdefault(equip.strip(), set()).add(entry["interlock_name"])

        for entry in Fault:
            equipment_names = entry.get("equipment_name", [])
            if isinstance(equipment_names, str):
                equipment_names = equipment_names.split(",")

            for equip in equipment_names:
                fault_map.setdefault(equip.strip(), set()).add(entry["interlock_name"])


        df = pd.DataFrame(resp)
        df["count"] = pd.to_numeric(df["count"], errors="coerce").fillna(0).astype(int)
        grouped_df = df.groupby("device_type", as_index=False)["count"].sum()

        DEVICE_TYPE_MAPPING = {
            "MOV": "MOV",
            "HCD": "HCD",
            "Dyke": "Dyke",
            "Hooter": "Hooter",
            "Primary Level": "Primary Radar",
            "Jockey Pump": "Jockey Pump",
            "VFT": "VFT",
            "PT": "PT Hydrant",
            "ROSOV": "Rosov",
            "ESD": "ESD",
            "Pump": "Pumps",
            "Radar": "Secondary Radar",
            "Fire Engine": "Fire Engine",
            "Barrier Gate": "Barrier Gate",
            "Gantry BCU": "Gantry BCU",
            "MFM": "MFM"
        }

        hardcoded_status = [
            {"id": "lrca", "name": "LRCA", "status": "standby"},
            {"id": "lrcb", "name": "LRCB", "status": "online"},
            {"id": "safety_plc_a", "name": "PLC A", "status": "online"},
            {"id": "safety_plc_b", "name": "PLC B", "status": "standby"},
            {"id": "process_plc_a", "name": "PLC A", "status": "online"},
            {"id": "process_plc_b", "name": "PLC B", "status": "standby"}
        ]

        result_dict = {item["id"]: item for item in hardcoded_status}

        for _, row in grouped_df.iterrows():
            device_name = row["device_type"]
            total = row["count"]

            mapped_name = DEVICE_TYPE_MAPPING.get(device_name, device_name)
            device_id = mapped_name.lower().replace(" ", "_")
            maintenance_interlocks = maintenance_map.get(device_name, set())
            fault_interlocks = fault_map.get(device_name, set())

            total_maintenance_count = await get_alert_count_for_interlock_set(maintenance_interlocks, device_name)
            total_fault_count = await get_alert_count_for_interlock_set(fault_interlocks, device_name)

            result_dict[device_id] = {
                "id": device_id,
                "name": mapped_name,
                "status": None,
                "total": total,
                "faulty": total_fault_count,
                "maintanance": total_maintenance_count
            }

        result = list(result_dict.values())
        return {"status": True, "message": "Success", "data": result}

    except Exception as e:
        print(traceback.format_exc())
        return {"status": False, "message": f"Error: {str(e)}", "data": []}


async def get_alert_count_for_interlock_set(interlocks, equipment):
    if not interlocks or not equipment:
        return 0

    interlock_filter = ",".join(f"'{i}'" for i in interlocks)
    query = f"equipment_name='{equipment}' and interlock_name in ({interlock_filter})"
    params = urdhva_base.queryparams.QueryParams()
    params.q = query
    params.fields = ['interlock_name']

    result = await hpcl_ceg_model.Alerts.get_all(params, resp_type="plain")
    if not result.get("data"):
        return 0

    return len({entry['interlock_name'] for entry in result['data'] if 'interlock_name' in entry})


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
            zone_list.append({"id": zone, "name": zone})
            sap_id_list.append({"id": sap_id, "name": name})
        
        # If specific_sap_id is provided, only collect zones for that sap_id
        elif specific_sap_id and sap_id == specific_sap_id:
            zone_list.append({"id": zone, "name": zone})
            sap_id_list.append({"id": sap_id, "name": name})
        
        # If no specific filters, collect all data
        elif not specific_zone and not specific_sap_id:
            zone_list.append({"id": zone, "name": zone})
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