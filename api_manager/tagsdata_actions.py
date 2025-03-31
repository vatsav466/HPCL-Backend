from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import json
import fastapi
import traceback
import pandas as pd
import os
from collections import defaultdict
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
from utilities.device_data_mapping import device_mapping
from utilities.analog_data_mapping import Maintenance, Fault

router = fastapi.APIRouter(prefix='/tagsdata')

BASE_JSON_PATH = "/opt/ceg/algo/things_board/device_data"

@router.post('/things_board_device_data', tags=['TagsData'])
async def tagsdata_things_board_device_data(data: Tagsdata_Things_Board_Device_DataParams):
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

        final_records = []

        # Enhanced device_type_mapping: (keyword, mapped_device_type, system_lookup_key)
        device_type_mapping = {
            "Tank": [
                ("Primary Gauge Level", "Primary Level", "Primary Gauge Level"),
                ("LEVEL SWITCH PROOF OK", "VFT", "LEVEL SWITCH PROOF OK"),
                ("RADAR HHH", "Radar", "RADAR HHH"),
                ("ROSOV OPEN", "ROSOV", "ROSOV OPEN STATUS IL1"),
                ("MOV", "MOV", "MOV STATUS IL1"),
                ("RIMSEAL FIRE", "RIMSEAL", "RIMSEAL FIRE ALARM")
            ],
            "OI": [
                ("Fire", "Fire Engine", "Fire Engine"),
                ("Jockey Pump Run", "Jockey Pump", "Jockey Pump Run"),
                ("Pt", "PT", "Farthest Point Pt"),
                ("PT", "PT", "Nearest Point PT")
            ]
        }
        # Initialize all counters
        fire_engine_count = 0
        pt_count = 0
        jockey_pump_count = 0
        # Build system mapping from device_mapping (case-insensitive)
        system_mapping = defaultdict(lambda: defaultdict(str))
        for device in device_mapping:
            device_type = device["device_type"].lower()
            for sensor_name, system in device["sensor_name"].items():
                normalized_sensor = sensor_name.strip().lower()
                system_mapping[device_type][normalized_sensor] = system

        # Create mapping from equipment_name to device_type from Maintenance and Fault
        equipment_to_device_type = {}
        
        # Process Maintenance data
        for item in Maintenance:
            equipments = item["equipment_name"].split(',')
            for equipment in equipments:
                equipment = equipment.strip()
                if equipment not in equipment_to_device_type:
                    equipment_to_device_type[equipment] = []
                if item["interlock_name"] not in equipment_to_device_type[equipment]:
                    equipment_to_device_type[equipment].append(item["interlock_name"])
        
        # Process Fault data
        for item in Fault:
            equipments = item["equipment_name"].split(',')
            for equipment in equipments:
                equipment = equipment.strip()
                if equipment not in equipment_to_device_type:
                    equipment_to_device_type[equipment] = []
                if item["interlock_name"] not in equipment_to_device_type[equipment]:
                    equipment_to_device_type[equipment].append(item["interlock_name"])

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

            location_counts = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'mf_count': 0}))

            for device in devices:
                raw_device_type = str(device.get('device_type', 'Unknown')).strip().lower()
                sensors = device.get('sensors', [])

                for sensor in sensors:
                    sensor_tag = str(sensor.get('sensor_tag', '')).strip()
                    if not sensor_tag:
                        continue

                    sensor_name = str(sensor.get('sensor_name', '')).strip()
                    if not sensor_name:
                        continue

                    mapped_device_type = None
                    system = "Unknown"
                    normalized_sensor = sensor_name.lower()

                    # Handle Tank devices
                    if raw_device_type == "tank":
                        for keyword, mapped, lookup_key in device_type_mapping["Tank"]:
                            if keyword.lower() in normalized_sensor:
                                mapped_device_type = mapped
                                # Use predefined lookup key for system
                                system_key = lookup_key.strip().lower()
                                system = system_mapping["tank"].get(system_key, "Unknown")
                                break
                   
                    # Handle OI devices
                    elif raw_device_type == "oi":
                        normalized_sensor = normalized_sensor.lower()
                        for keyword, mapped, lookup_key in device_type_mapping["OI"]:
                            lookup_key = lookup_key.strip().lower()

                            if keyword == "Fire" and normalized_sensor.startswith(keyword.lower()):
                                if normalized_sensor.startswith(keyword.lower()):
                                    mapped_device_type = mapped
                                    system_key = lookup_key
                                    system = system_mapping["oi"].get(system_key, "Unknown")
                                    break
                                 # Check for PT (endswith ' pt' or ' pt')
                            elif keyword in ["Pt", "PT"] and normalized_sensor.endswith(keyword.lower()):
                                 if normalized_sensor.endswith(keyword.lower()):
                                     mapped_device_type = mapped
                                     system_key = lookup_key
                                     system = system_mapping["oi"].get(system_key, "Unknown")
                                     break
                                    # Check for Jockey Pump Run (exact match or contains)
                            elif keyword == "Jockey Pump Run" and "jockey pump run" in normalized_sensor:
                                 if "jockey pump run" in normalized_sensor:
                                     mapped_device_type = mapped
                                     system_key = lookup_key
                                     system = system_mapping["oi"].get(system_key, "Unknown")
                                     break                   

                    # Handle other devices
                    else:
                        system = system_mapping[raw_device_type].get(normalized_sensor, "Unknown")
                        if system != "Unknown":
                            mapped_device_type = device["device_type"].title()

                    if mapped_device_type:
                        location_counts[mapped_device_type][system]['count'] += 1

            # Calculate mf_count for each device type
            for dev_type in location_counts:
                if dev_type in equipment_to_device_type:
                    interlock_names = equipment_to_device_type[dev_type]
                    total_mf_count = 0
                    
                    for interlock_name in interlock_names:
                        params = urdhva_base.queryparams.QueryParams(
                            limit=10000,
                            q=f"interlock_name='{interlock_name}' AND alert_status='Open' AND sap_id='{sap_id}'"
                        )
                        count = await Alerts.count(params)
                        total_mf_count += count
                    
                    # Distribute the mf_count across all systems for this device type
                    system_count = len(location_counts[dev_type])
                    if system_count > 0:
                        avg_mf_count = total_mf_count / system_count
                        for system in location_counts[dev_type]:
                            location_counts[dev_type][system]['mf_count'] = round(avg_mf_count)

            # Convert counts to final records
            for dev_type, system_counts in location_counts.items():
                if dev_type in ["Tank Maintenance","Fire Pump"]:
                    continue
                for sys, counts in system_counts.items():
                    final_records.append({
                        "sap_id": sap_id,
                        "name": location_name,
                        "zone": zone,
                        "device_type": dev_type,
                        "count": str(counts['count']),
                        "system": sys,
                        "mf_count": str(counts['mf_count'])
                    })

        # Update database
        try:
            await TagsData.bulk_update(final_records, upsert=False)
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
            
            # Convert 'count' to integer (handle any invalid data gracefully)
            df['count'] = pd.to_numeric(df['count'], errors='coerce').fillna(0).astype(int)
            # Select only required columns
            df = df[['sap_id', 'name', 'device_type', 'zone', 'count','system','mf_count']]
 
            # Convert DataFrame to list of dictionaries
            return {"status": True, "message": "Success", "data": df.to_dict(orient='records')}

        return {"status": False, "message": "No data found"}

    except Exception as e:
        return {"status": False, "message": f"Error: {str(e)}"}