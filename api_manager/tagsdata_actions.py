from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import json
import traceback
import polars as pl
import pandas as pd
import utilities.connection_mapping as connection_mapping
from api_manager.charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams


router = fastapi.APIRouter(prefix='/tagsdata')


# Action things_board_device_data
@router.post('/things_board_device_data', tags=['TagsData'])
async def tagsdata_things_board_device_data(data: Tagsdata_Things_Board_Device_DataParams):
    try:
        Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
        Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
        
        lpg_query = "SELECT bu, sap_id, name FROM location_master WHERE bu = 'TAS' "
        try:
            df = await function(query=lpg_query)
            df = pl.DataFrame(df)
            print("df", df.columns)
            print("df", df)
            base_path = "/opt/ceg/algo/things_board/device_data/"  # Update with actual path
            
            async def process_json(sap_id):
                file_path = os.path.join(base_path, f"{sap_id}.json")
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r') as file:
                            data = json.load(file)
                            # Extract the 'data' key if it exists
                            if isinstance(data, dict) and "data" in data:
                                data = data["data"]
                            # Ensure data is a list
                            if isinstance(data, list) and data:
                                df_json = pl.DataFrame(data)
                                if "device_type" in df_json.columns:
                                    grouped_df = df_json.group_by("device_type").len().rename({"len": "count"})
                                    return grouped_df.with_columns(pl.col("count").cast(pl.Int64))  # Ensure type consistency                    
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
                # Return an empty DataFrame if no data is found
                return pl.DataFrame({"device_type": [], "count": []}, schema={"device_type": pl.Utf8, "count": pl.Int64})
            
            result_frames = []
            for sap_id in df["sap_id"].to_list():
                counts_df = await process_json(sap_id)
                counts_df = counts_df.with_columns(pl.lit(sap_id).alias("sap_id"))
                result_frames.append(counts_df)
            
            final_df = pl.concat(result_frames, how="vertical") if result_frames else pl.DataFrame({"sap_id": [], "device_type": [], "count": []}, schema={"sap_id": pl.Utf8, "device_type": pl.Utf8, "count": pl.Int64})
            final_df = final_df.join(df.select(["sap_id", "name"]), on="sap_id", how="left")
            final_df = final_df.select(["sap_id", "name", "device_type", "count"]).to_dicts()
            await TagsData.bulk_update(final_df, upsert=False)
            return final_df
        except Exception as e:
            print(traceback.format_exc())
            return {"status": False, "message": f"Error: {e}"}
    except Exception as e:
        print(traceback.format_exc())
        return {"status": False, "message": f"Error: {e}"}
