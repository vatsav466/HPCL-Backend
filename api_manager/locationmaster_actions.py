import urdhva_base
from hpcl_cng_enum import *
from hpcl_cng_model import *
import os
import json
import shutil
import fastapi
import traceback
import polars as pl
import urdhva_base.redispool
import utilities.bu_key_mapping as bu_key_mapping
import orchestrator.alerting.alert_helper as alert_helper

router = fastapi.APIRouter(prefix='/locationmaster')

logger = urdhva_base.logger.Logger.getInstance("api_manager")


# Action upload_location_master
@router.post('/upload_location_master', tags=['LocationMaster'])
async def locationmaster_upload_location_master(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    """
    Upload Location Master file.

    This API endpoint accepts a CSV file and saves it to the MFT path.
    It then reads the CSV file and returns the data as a JSON response.

    Args:
        data (Locationmaster_Upload_Location_MasterParams): The CSV file to be uploaded.

    Returns:
        Dict[str, Any]: A JSON response containing the filename and data.

    Raises:
        HTTPException: If there is an error uploading the file.
        HTTPException: If there is an error processing the CSV file.
    """
    redis_client = await urdhva_base.redispool.get_redis_connection()
    upload_dir = urdhva_base.settings.mft_path
    os.makedirs(upload_dir, exist_ok=True)
    
    # Define the file path
    file_path = os.path.join(upload_dir, uploadfile.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(uploadfile.file, buffer)
        data = pl.read_csv(file_path).with_columns(pl.all().cast(pl.Utf8,strict=False))
        # Iterate through the rows of the CSV and extract `bu` and `sapid`
        data = data.rename(bu_key_mapping.Location)
    except Exception as e:
        print(traceback.format_exc())
        raise fastapi.HTTPException(status_code=400, detail="Failed to process CSV file.") from e

    # Save the uploaded file
    try:
        data = data.to_dicts()
        for data_dump in data:
            data_obj = LocationMasterCreate(**data_dump)
            print(await data_obj.create())
            await alert_helper.set_location_details(data_dump["bu"], data_dump["sap_id"], data_dump)

        # Display data or perform further processing as needed
        return {"filename": file_path, "data": data}  # Returns the first few rows as a sample
    except Exception as e:
        print(traceback.format_exc())
        raise fastapi.HTTPException(status_code=500, detail="File upload failed.") from e
    except Exception as e:
        print(traceback.format_exc())
        raise fastapi.HTTPException(status_code=400, detail="Failed to process CSV file.") from e


# Action download_location_master
@router.post('/download_location_master', tags=['LocationMaster'])
async def locationmaster_download_location_master(data: Locationmaster_Download_Location_MasterParams):
    # Fetching data from the LocationMaster model
    """
    Download Location Master data.

    This API endpoint fetches the data from the LocationMaster model and saves it as a CSV file to the download path specified in the settings.
    The API then returns a JSON response containing a success message and the file path of the saved CSV file.

    Args:
        data (Locationmaster_Download_Location_MasterParams): The input data containing the BU, SAP ID, and other optional parameters.

    Returns:
        Dict[str, Any]: A JSON response containing the status, message, and data (if any).

    Raises:
        HTTPException: If there is an error fetching the data or saving the CSV file.
    """
    data = await LocationMaster.get_all()
    
    # Convert to a dictionary if it's a custom object
    resp_dict = data.__dict__
    
    if resp_dict.get('body'):
        # Decode the byte string to a normal string
        body_str = resp_dict['body'].decode('utf-8')
        
        # Parse the JSON string into a Python dictionary
        loc_data = json.loads(body_str)
        
        # Check if there are multiple records in the "data" key
        records = loc_data.get("data", [])
        
        if records:
            # Convert the records to a Polars DataFrame
            df = pl.DataFrame(records)
            
            # Save the Polars DataFrame as a CSV file
            output_path = urdhva_base.settings.download_path
            file_path = os.path.join(output_path, "location_master.csv")
            df.write_csv(file_path)  # Save directly to file
            
            # Return the CSV file path or a success message
            return {"status": True, "message": f"File saved successfully to path {file_path}", "data": df.to_dicts()}
        
        return {"status": False, "message": "No data found", "data": []}
    
    return {"status": False, "message": "No body in the response", "data": []}