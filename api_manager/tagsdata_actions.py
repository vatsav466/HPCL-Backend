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
from utilities.analog_data_mapping import Maintenanace, Fault

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
        mapping_base_path = '/opt/ceg/algo/utilities/'
        mapping_df = pl.read_csv(os.path.join(mapping_base_path, 'DashboardAssetMapping.csv'))
        mapping_df = mapping_df.with_columns(mapping_df["Device Type"].fill_null(strategy="forward"))

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
                
                # getting the equipment names according to the device type
                equipment_names = mapping_df.filter(pl.col('Device Type') == device_type)["Equipments(sensor_type)"].to_list()
                system_counts = defaultdict(int)
                system_total_count = defaultdict(int)  # for total count
                system_m_f_count = defaultdict(int)  # for maintainance_fault count
                
                for sensor in sensors:
                    sensor_name = sensor.get('sensor_name', '').strip()
                    # looping every equipment to check whether it is present in sensor name
                    for equipment in equipment_names:
                        equipment = equipment.strip() if equipment else ""
                        if equipment and equipment.lower() in sensor_name.lower():
                            system = device_mapping_dict.get(device_type, {}).get(equipment)
                            if system:
                                system_total_count[system] += 1
                                
                                # Find matching maintenance records
                                for maintenance in Maintenance:
                                    maintenance_equipment = maintenance.get('equipment_name', '').strip() if maintenance.get('equipment_name') else ""
                                    # Use same comparison logic as with sensors
                                    if maintenance_equipment and maintenance_equipment.lower() == equipment.lower():
                                        interlock_name = maintenance.get('interlock_name')
                                        if interlock_name:
                                            print("maintenance interlock_name: ", interlock_name)
                                            params = urdhva_base.queryparams.QueryParams(
                                                limit=10000,
                                                q=f"interlock_name='{interlock_name}'"
                                            )
                                            total = await Alerts.count(params)
                                            print("total maintenance: ", total)
                                            system_m_f_count[system] += total
                                
                                # Find matching fault records
                                for fault in Fault:
                                    fault_equipment = fault.get('equipment_name', '').strip() if fault.get('equipment_name') else ""
                                    # Use same comparison logic as with sensors
                                    if fault_equipment and fault_equipment.lower() == equipment.lower():
                                        interlock_name = fault.get('interlock_name')
                                        if interlock_name:
                                            print("fault interlock_name: ", interlock_name)
                                            params = urdhva_base.queryparams.QueryParams(
                                                limit=10000,
                                                q=f"interlock_name='{interlock_name}'"
                                            )
                                            total = await Alerts.count(params)
                                            print("total fault: ", total)
                                            system_m_f_count[system] += total
                # taking keys to merge the above declared two dicts
                all_keys = set(system_total_count.keys()).union(system_m_f_count.keys())
                # declaring varibale to store the merged dict
                merged_dict = {}
                # merging the two dict, and adding the value in the list
                for key in all_keys:
                    merged_dict[key] = [
                        value for value in (system_total_count.get(key, 0), system_m_f_count.get(key, 0))
                    ]
                for system, count in merged_dict.items():
                    rows.append({
                        'sap_id': sap_id,
                        'zone': zone,
                        'name': name,
                        'equipment_name': equipment_name,
                        'device_type': device_type,
                        'system': system,
                        'count': str(count[0]),  # Convert count to string, first value for total count
                        'mf_count': str(count[1])  # second value for mf count
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
                'count': pl.Utf8,  # Ensure count is a string
                'mf_count': pl.Utf8
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
            pl.col("mf_count").sum().alias("mf_count"),
            pl.col("sap_id").first(),  # Keep first sap_id (change to list() if needed)
            pl.col("name").first()  # Keep first location_name
        ])
        return {"status": True, "message": "Success", "data": res.to_dicts()}