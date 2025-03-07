from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import json
import traceback
import polars as pl
import os
from collections import defaultdict
import utilities.connection_mapping as connection_mapping
from api_manager.charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
from utilities.device_data_mapping import device_mapping

router = fastapi.APIRouter(prefix='/tagsdata')
# Create a dictionary for quick lookup
device_mapping_dict = {device["device_type"]: device["sensor_name"] for device in device_mapping}

@router.post('/things_board_device_data', tags=['TagsData'])
async def tagsdata_things_board_device_data(data: Tagsdata_Things_Board_Device_DataParams):
    try:
        # Setup connection parameters
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        
        # Query location_master to get bu, sap_id, zone, and name
        lpg_query = "SELECT bu, zone, sap_id, name FROM location_master WHERE bu = 'TAS'"
        df = await function(query=lpg_query)
        df = pl.DataFrame(df)
        
        base_path = "/opt/ceg/algo/things_board/device_data"  # Update with actual path
        
        async def process_device_data(sap_id, zone, name):
            file_path = os.path.join(base_path, f"{sap_id}.json")
            if not os.path.exists(file_path):
                return pl.DataFrame()
            
            try:
                with open(file_path, 'r') as file:
                    json_data = json.load(file)
                    devices = json_data.get('data', [])
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                return pl.DataFrame()
            
            rows = []
            for device in devices:
                device_type = device.get('device_type', '')
                equipment_name = device.get('device_name', '')
                sensors = device.get('sensors', [])
                
                system_counts = defaultdict(int)
                for sensor in sensors:
                    sensor_name = sensor.get('sensor_name', '').strip()
                    system = device_mapping_dict.get(device_type, {}).get(sensor_name)
                    if system:
                        system_counts[system] += 1
                
                for system, count in system_counts.items():
                    rows.append({
                        'sap_id': sap_id,
                        'zone': zone,
                        'name': name,
                        'equipment_name': equipment_name,
                        'device_type': device_type,
                        'system': system,
                        'count': str(count)  # Convert count to string
                    })
            
            return pl.DataFrame(rows) if rows else pl.DataFrame()
        
        result_frames = []
        for row in df.iter_rows(named=True):
            sap_id = row['sap_id']
            zone = row['zone']
            name = row['name']
            device_df = await process_device_data(sap_id, zone, name)
            if not device_df.is_empty():
                result_frames.append(device_df)
        
        if result_frames:
            final_df = pl.concat(result_frames)
        else:
            final_df = pl.DataFrame(schema={
                'sap_id': pl.Utf8,
                'zone': pl.Utf8,
                'name': pl.Utf8,
                'equipment_name': pl.Utf8,
                'device_type': pl.Utf8,
                'system': pl.Utf8,
                'count': pl.Utf8  # Ensure count is a string
            })
        
        # Convert all records before inserting
        final_records = final_df.to_dicts()
        
        # Ensure count is stored as string
        final_records = [{**record, 'count': str(record['count'])} for record in final_records]

        # Ensure data is not empty before inserting
        if not final_records:
            return {"status": False, "message": "No data to insert"}

        print("Final Records:", final_records)  # Debugging step

        # Insert/update records
        await TagsData.bulk_update(final_records, upsert=False)

        return {"status": True, "message": "Data inserted successfully", "data": final_records}

    except Exception as e:
        print(traceback.format_exc())
        return {"status": False, "message": f"Error: {e}"}

# Action get_tags_data
@router.post('/get_tags_data', tags=['TagsData'])
async def tagsdata_get_tags_data(data: Tagsdata_Get_Tags_DataParams):
    resp = await TagsData.get_all(resp_type='plain')
    res = resp.get("data", [])
    if res:
        res = pl.DataFrame(res)
        # Split equipment_name and extract name
        res = res.with_columns(
            pl.col("equipment_name").str.split('@').alias("split_name")
        ).with_columns(
            pl.col("split_name").list.get(0).alias("equipment_name")
        ).drop("split_name")  # Drop intermediate column
        # Convert count to integer
        res = res.with_columns(pl.col("count").cast(pl.Int64, strict=False))
        # Aggregate count based on device_type and system, keeping sap_id and location_name
        res = res.group_by(["device_type", "system"]).agg([
            pl.col("count").sum().alias("total_count"),
            pl.col("sap_id").first(),  # Keep first sap_id (change to list() if needed)
            pl.col("location_name").first()  # Keep first location_name
        ])
        return {"status": True, "message": "Success", "data": res.to_dicts()}