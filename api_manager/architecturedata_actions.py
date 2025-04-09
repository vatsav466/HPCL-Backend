from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import json
import traceback
import pandas as pd
import os
from collections import defaultdict
import utilities.connection_mapping as connection_mapping
from api_manager.charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
from utilities.analog_data_mapping import Maintenance, Fault
# import urdhva_base.queryparams

router = fastapi.APIRouter(prefix='/architecturedata')

BASE_JSON_PATH = "/opt/ceg/algo/things_board/device_data/"

@router.post('/architecture_details', tags=['ArchitectureData'])
async def architecturedata_architecture_details(data: Architecturedata_Architecture_DetailsParams):
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
        
      
        mfm_query = "SELECT sap_id, COUNT(mfm_number) as mfm_count FROM host_mfm_factor GROUP BY sap_id"
        mfm_df = await execute_query(query=mfm_query)
        mfm_df = pd.DataFrame(mfm_df)
        mfm_map = dict(zip(mfm_df['sap_id'],mfm_df['mfm_count']))

        final_records = []

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
                ("Jockey", "Jockey Pump"),
                ("Pt", "PT"),
                ("PT", "PT")
            ]
        }

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

            location_counts = defaultdict(int)

            for device in devices:
                device_type = str(device.get('device_type', 'Unknown'))
                sensors = device.get('sensors', [])

                if device_type in ['Tank', 'OI']:
                    # Tank/OI: Count based on sensors with valid tags
                    for sensor in sensors:
                        sensor_tag = str(sensor.get('sensor_tag', '')).strip()
                        if not sensor_tag:
                            continue  # Skip sensors without tags
                        sensor_name = str(sensor.get('sensor_name', '')).lower()
                        
                        # Special handling for OI "Pt/PT" at end of string
                        if device_type == 'OI':
                            for keyword, mapped_type in device_type_mapping[device_type]:
                                if keyword in ['Pt', 'PT']:
                                    if sensor_name.endswith(keyword.lower()):
                                        location_counts[mapped_type] += 1
                                        break
                                elif keyword.lower() in sensor_name:
                                    location_counts[mapped_type] += 1
                                    break
                        else:  # Tank devices
                            for keyword, mapped_type in device_type_mapping[device_type]:
                                if keyword.lower() in sensor_name:
                                    location_counts[mapped_type] += 1
                                    break
                else:
                    # Non-Tank/OI: Count device itself (1 per device)
                    location_counts[device_type] += 1

            # Convert counts to final records
            for dev_type, count in location_counts.items():
                if dev_type in ["Tank Maintenance","Fire Pump"]:
                    continue
                elif dev_type == "Loading Point":
                     dev_type = "Gantry BCU" 
                final_records.append({
                    "sap_id": sap_id,
                    "name": location_name,
                    "zone": zone,
                    "device_type": dev_type,
                    "count": str(count)
                })
            # Add MFM count if available
            if sap_id in mfm_map:
                final_records.append({
                    "sap_id": sap_id,
                    "name": location_name,
                    "zone": zone,
                    "device_type": "MFM",
                    "count": str(mfm_map[sap_id])
                })
        # Update database
        try:
            await ArchitectureData.bulk_update(final_records, upsert=False)
            print(f"Updated {len(final_records)} records.")
            return {"status": True, "message": "Data updated successfully."}
        except Exception as e:
            print(f"Database Error: {e}")
            return {"status": False, "message": f"Database Error: {str(e)}"}

    except Exception as e:
        print(traceback.format_exc())
        return {"status": False, "message": f"Error: {str(e)}"}

@router.post('/architecture_data', tags=['ArchitectureData'])
async def architecturedata_architecture_data(data: Architecturedata_Architecture_DataParams):
    try:
        limit = 10000
        skip = 0
        res = []

        # Fetch all data in chunks
        while True:
            resp = await ArchitectureData.get_all(
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
            df = df[['sap_id', 'name', 'count', 'device_type', 'zone']]
 
            # Convert DataFrame to list of dictionaries
            return {"status": True, "message": "Success", "data": df.to_dict(orient='records')}

        return {"status": False, "message": "No data found"}

    except Exception as e:
        return {"status": False, "message": f"Error: {str(e)}"}


  
