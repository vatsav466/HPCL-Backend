import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import os
import json
import fastapi
import traceback
import pandas as pd
from collections import defaultdict
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from utilities.analog_data_mapping import Maintenance, Fault
from utilities.device_data_mapping import system_classification
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams

router = fastapi.APIRouter(prefix='/tagsdata')

BASE_JSON_PATH = "/opt/ceg/algo/things_board/device_data"

@router.post('/things_board_device_data', tags=['TagsData'])
async def tagsdata_things_board_device_data(data: Tagsdata_Things_Board_Device_DataParams):
    """
    Description:
        Fetches and processes device data from ThingsBoard for TAS BU locations and updates the database.
    Input:
        data: Tagsdata_Things_Board_Device_DataParams
    Returns:
        A status and message indicating the success or failure of the operation.
    Details:
        - Establishes a connection and executes queries to fetch location and MFM data.
        - Processes JSON files to extract device and sensor information.
        - Aggregates counts of devices and maintenance faults by device type and location.
        - Updates the database with the processed records.
    """

    try:    
        # Setup connection
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        execute_query = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)

        # Fetch TAS BU locations
        location_query = "SELECT bu, zone, sap_id, name FROM location_master WHERE bu = 'TAS'"
        location_df = await execute_query(query=location_query)
        location_df = pd.DataFrame(location_df)
        
        if location_df.empty:
            return {"status": False, "message": "No TAS locations found."}
        
        mfm_query = "SELECT sap_id, COUNT(DISTINCT mfm_number) AS mfm_count FROM host_mfm_factor where bcu_number is not NULL GROUP BY sap_id ORDER BY sap_id;"
        mfm_df = await execute_query(query=mfm_query)
        mfm_df = pd.DataFrame(mfm_df)
        mfm_map = dict(zip(mfm_df['sap_id'],mfm_df['mfm_count']))

        device_type_mapping = {
            "Tank": [
                ("Primary Gauge Level", "Primary Level"),
                ("LEVEL SWITCH PROOF OK", "VFT"),
                ("RADAR HHH", "Radar"),
                ("ROSOV OPEN", "ROSOV"),
                ("MOV", "MOV"),
                ("RIMSEAL FIRE", "RIMSEAL")
            ],
            "OI": [
                ("Fire", "Fire Engine"),
                ("Jockey Pump Run", "Jockey Pump"),
                ("Pt", "PT"),
                ("PT", "PT")
            ],
            "ESD": [
                ("ESD MAINTENANCE", "ESD")
            ]
        }

        # Use a dict to aggregate records by (sap_id, device_type)
        aggregated_records = {}

        # Process each location
        for _, row in location_df.iterrows():
            sap_id = str(row['sap_id'])
            location_name = str(row['name'])
            zone = str(row['zone'])

            json_path = os.path.join(BASE_JSON_PATH, f"{sap_id}.json")
            if not os.path.exists(json_path):
                print(f"Skipping {sap_id}: File not found.")
                continue

            try:
                with open(json_path, 'r') as file:
                    devices = json.load(file).get('data', [])
            except json.JSONDecodeError:
                print(f"Invalid JSON for {sap_id}.")
                continue

            location_counts = defaultdict(list)

            for device in devices:
                device_type = str(device.get('device_type', 'Unknown'))
                sensors = device.get('sensors', [])
                device_name = str(device.get('device_name', ''))
                if device_type in ['Tank', 'OI', 'ESD']:
                    for sensor in sensors:
                        sensor_tag = str(sensor.get('sensor_tag', '')).strip()
                        if not sensor_tag:
                            continue
                        sensor_name = str(sensor.get('sensor_name', '')).lower()
                        
                        if device_type == 'OI':
                            for keyword, mapped_type in device_type_mapping[device_type]:
                                if keyword == 'Fire':
                                    if sensor_name.startswith(keyword.lower()):
                                        location_counts[mapped_type].append(device_name)
                                        break
                                elif keyword in ['Pt', 'PT']:
                                    if sensor_name.endswith(keyword.lower()):
                                        location_counts[mapped_type].append(device_name)
                                        break
                                elif keyword.lower() in sensor_name:
                                    location_counts[mapped_type].append(device_name)
                                    break
                        else:
                            for keyword, mapped_type in device_type_mapping[device_type]:
                                if keyword.lower() in sensor_name:
                                    location_counts[mapped_type].append(device_name)
                                    break
                else:
                    location_counts[device_type].append(device_name)

            tank_devices = set()
            for dev_type, device_names in location_counts.items():
                if dev_type in ["Primary Level", "VFT", "Radar", "ROSOV", "MOV", "RIMSEAL"]:
                    for device_name in device_names:
                        tank_name = device_name.split('@')[0] if '@' in device_name else device_name
                        tank_devices.add(tank_name)
            
            total_tank_count = len(tank_devices)

            # Aggregate counts and mf_counts per (sap_id, device_type)
            for dev_type, device_names in location_counts.items():
                count = 0
                for device_name in device_names:
                    if dev_type == "Hooter" and device_name.split('@')[0].endswith("HOOTER_ACK"):
                        continue
                    if dev_type == "Pump" and any(kw in device_name.upper() for kw in ["BLUE DYE", "FO"]):
                        continue
                    count += 1

                if dev_type in ["Tank Maintenance", "Fire Pump"]:
                    continue
                if dev_type == "Loading Point":
                    dev_type = "Gantry BCU"

                if count <= 0:
                    continue

                # Compose key for aggregation
                key = (sap_id, dev_type)

                # Prepare system classification
                upper_dev_type = dev_type.upper()
                system = system_classification.get(upper_dev_type, "Unknown")

                # Get maintenance fault count from alerts table
                mf_count = 0
                interlocks = []

                for maintenance_item in Maintenance:
                    equipment = maintenance_item["equipment_name"]
                    if isinstance(equipment, list):
                        if dev_type in equipment and maintenance_item["alert_category"] == system:
                            interlocks.append(maintenance_item["interlock_name"])
                    elif dev_type.upper() == equipment.upper() and maintenance_item["alert_category"] == system:
                        interlocks.append(maintenance_item["interlock_name"])

                for fault_item in Fault:
                    equipment = fault_item["equipment_name"]
                    if isinstance(equipment, list):
                        if dev_type in equipment and fault_item["alert_category"] == system:
                            interlocks.append(fault_item["interlock_name"])
                    elif dev_type.upper() == equipment.upper() and fault_item["alert_category"] == system:
                        interlocks.append(fault_item["interlock_name"])

                if interlocks:
                    in_clause = ", ".join(f"'{item}'" for item in interlocks)
                    query = (f"SELECT COUNT(DISTINCT device_name) as count FROM alerts "
                             f"WHERE interlock_name IN ({in_clause}) AND alert_status='Open' "
                             f"AND sap_id='{sap_id}'")
                    resp = await execute_query(query=query)
                    if resp and len(resp) > 0:
                        mf_count = resp[0]['count'] or 0

                if key in aggregated_records:
                    aggregated_records[key]["count"] += count
                    aggregated_records[key]["mf_count"] += mf_count
                else:
                    aggregated_records[key] = {
                        "sap_id": sap_id,
                        "name": location_name,
                        "zone": zone,
                        "device_type": dev_type,
                        "count": count,
                        "mf_count": mf_count,
                        "system": system,
                        "total_tank_count": total_tank_count if dev_type in ["Primary Level", "VFT", "Radar", "ROSOV", "MOV", "RIMSEAL"] else None
                    }

            # Add MFM count record similarly
            if sap_id in mfm_map:
                mfm_dev_type = "MFM"
                key = (sap_id, mfm_dev_type)
                mfm_count = mfm_map[sap_id]

                mfm_system = "Gantry"
                mfm_mf_count = 0
                interlocks = []

                for maintenance_item in Maintenance:
                    equipment = maintenance_item["equipment_name"]
                    if (isinstance(equipment, str) and equipment.upper() == "MFM" and 
                        maintenance_item["alert_category"] == mfm_system):
                        interlocks.append(maintenance_item["interlock_name"])
                    elif isinstance(equipment, list) and "MFM" in equipment and maintenance_item["alert_category"] == mfm_system:
                        interlocks.append(maintenance_item["interlock_name"])

                for fault_item in Fault:
                    equipment = fault_item["equipment_name"]
                    if (isinstance(equipment, str) and equipment.upper() == "MFM" and 
                        fault_item["alert_category"] == mfm_system):
                        interlocks.append(fault_item["interlock_name"])
                    elif isinstance(equipment, list) and "MFM" in equipment and fault_item["alert_category"] == mfm_system:
                        interlocks.append(fault_item["interlock_name"])

                if interlocks:
                    in_clause = ", ".join(f"'{item}'" for item in interlocks)
                    query = (f"SELECT COUNT(DISTINCT device_name) as count FROM alerts "
                             f"WHERE interlock_name IN ({in_clause}) AND alert_status='Open' "
                             f"AND sap_id='{sap_id}'")
                    resp = await execute_query(query=query)
                    if resp and len(resp) > 0:
                        mfm_mf_count = resp[0]['count'] or 0

                if key in aggregated_records:
                    aggregated_records[key]["count"] += mfm_count
                    aggregated_records[key]["mf_count"] += mfm_mf_count
                else:
                    aggregated_records[key] = {
                        "sap_id": sap_id,
                        "name": location_name,
                        "zone": zone,
                        "device_type": mfm_dev_type,
                        "count": mfm_count,
                        "mf_count": mfm_mf_count,
                        "system": mfm_system,
                        "total_tank_count": None
                    }

        # Prepare final_records list from aggregated data
        final_records = []
        for record in aggregated_records.values():
            # Convert counts to strings as per your original code
            rec = {
                "sap_id": record["sap_id"],
                "name": record["name"],
                "zone": record["zone"],
                "device_type": record["device_type"],
                "count": str(record["count"]),
                "mf_count": str(record["mf_count"]),
                "system": record["system"]
            }
            if record["total_tank_count"] is not None:
                rec["total_tank_count"] = record["total_tank_count"]
            final_records.append(rec)

        # Update database
        try:
            await TagsData.bulk_update(final_records, upsert=True)
            print(f"Updated {len(final_records)} records.")
            return {"status": True, "message": "Data updated successfully."}
        except Exception as e:
            print(f"Database Error: {e}")
            return {"status": False, "message": f"Database Error: {str(e)}"}

    except Exception as e:
        print(traceback.format_exc())
        return {"status": False, "message": f"Error: {str(e)}"}


@router.post('/get_tags_data', tags=['TagsData'])
async def tagsdata_get_tags_data(data: Tagsdata_Get_Tags_DataParams):
    try:
        # First call the device data function to ensure we have latest data
        device_data_result = await tagsdata_things_board_device_data(Tagsdata_Things_Board_Device_DataParams())
        
        if not device_data_result.get('status'):
            return {"status": False, "message": "Failed to refresh device data"}
        limit = 10000
        skip = 0
        res = []

        # Fetch all data in chunks
        while True:
            resp = await TagsData.get_all(
                urdhva_base.queryparams.QueryParams(
                    limit=limit, 
                    skip=skip, 
                    sort=json.dumps({'created_at': 'DESC'})
                ),
                resp_type='plain'
            )
            if not resp['data']:
                break
            res.extend(resp['data'])
            if len(resp['data']) < limit:
                break
            skip += limit  # Increase skip to fetch next batch

        # Convert to DataFrame if data exists
        if res:
            df = pd.DataFrame(res)  # Convert list of dictionaries to DataFrame

            # print(df.columns)  # Debugging step to check column names

            # Convert 'count' to integer, handling errors
            df['count'] = pd.to_numeric(df['count'], errors='coerce').fillna(0).astype(int)

            # Ensure required columns exist
            required_columns = ['sap_id', 'name', 'zone', 'system', 'count', 'mf_count']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise KeyError(f"Missing columns: {missing_columns}")

            # Convert 'mf_count' to numeric (handling missing values)
            df['mf_count'] = pd.to_numeric(df['mf_count'], errors='coerce').fillna(0).astype(int)

            # **Exclude specific sap_id values**
            df = df[~df['sap_id'].isin(['1588', '1992', '1999'])]

            # Apply filtering if 'zone' or 'plant' is provided
            if 'zone' in df.columns and data.zone:
                df = df[df['zone'] == data.zone]

            if 'sap_id' in df.columns and data.plant:
                df = df[df['sap_id'] == data.plant]

            # Group by relevant columns and sum 'count' only
            df = df.groupby(['system', 'sap_id', 'name', 'zone'], as_index=False).agg({
                'count': 'sum',  # Summing 'count' only
                'mf_count': 'sum'  # Summing 'mf_count'
            })

            # Convert DataFrame to list of dictionaries
            return {"status": True, "message": "Success", "data": df.to_dict(orient='records')}

        return {"status": False, "message": "No data found"}

    except Exception as e:
        print(traceback.format_exc())
        return {"status": False, "message": f"Error: {str(e)}"}