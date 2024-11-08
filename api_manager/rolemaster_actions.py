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
import orchestrator.masterdata.role_master_upload as role_master_upload

router = fastapi.APIRouter(prefix='/rolemaster')

logger = urdhva_base.logger.Logger.getInstance("api_manager")


# Action upload_role_master
@router.post('/upload_role_master', tags=['RoleMaster'])
async def rolemaster_upload_role_master(upload_file: fastapi.UploadFile = fastapi.File(None)):
    """
    Upload Role Master file.

    This API endpoint accepts a CSV file and saves it to the MFT path.
    It then reads the CSV file and returns the data as a JSON response.

    Args:
        upload_file (fastapi.UploadFile): The CSV file to be uploaded.

    Returns:
        Dict[str, Any]: A JSON response containing the filename and data.

    Raises:
        HTTPException: If there is an error uploading the file.
        HTTPException: If there is an error processing the CSV file.
    """
    try:
        df = pl.read_csv(uploadfile.file).with_columns(pl.all().cast(pl.Utf8, strict=False))
    except Exception as e:
        print(f"Exception while reading CSV file, {e}")
        return False, "Failed to process CSV file, Please reverify uploaded content and reverify"
    return role_master_upload.upload_role_master_data(df)


# Action download_role_master
@router.post('/download_role_master', tags=['RoleMaster'])
async def rolemaster_download_role_master(data: Rolemaster_Download_Role_MasterParams):
    """
    Download Role Master data.

    This API endpoint fetches the data from the RoleMaster model and saves it as a CSV file to the download path specified in the settings.
    The API then returns a JSON response containing a success message and the file path of the saved CSV file.

    Args:
        data (Rolemaster_Download_Role_MasterParams): The input data containing the BU, SAP ID, and other optional parameters.

    Returns:
        Dict[str, Any]: A JSON response containing the status, message, and data (if any).

    Raises:
        HTTPException: If there is an error fetching the data or saving the CSV file.
    """
    data = await RoleMaster.get_all()
    
    # Convert to a dictionary if it's a custom object
    resp_dict = data.__dict__
    
    if resp_dict.get('body'):
        # Decode the byte string to a normal string
        body_str = resp_dict['body'].decode('utf-8')
        
        # Parse the JSON string into a Python dictionary
        role_data = json.loads(body_str)
        
        # Check if there are multiple records in the "data" key
        records = role_data.get("data", [])
        
        if records:
            # Convert the records to a Polars DataFrame
            df = pl.DataFrame(records)
            
            download_path = urdhva_base.settings.download_path
            downloadpath = os.path.join(download_path, "downloads")
            if not os.path.exists(downloadpath):
                os.makedirs(downloadpath)
            
            if not os.path.exists(f'{urdhva_base.settings.ui_path}/downloads'):
                os.system(f'ln -s {downloadpath} {urdhva_base.settings.ui_path}')
            df.write_csv(downloadpath + "role_master.csv")  # Save directly to file
            return {"status": True, "message": "Success","data": os.path.join('/downloads', "role_master.csv")}        
        return {"status": False, "message": "No data found", "data": []}
    return {"status": False, "message": "No response", "data": []}


