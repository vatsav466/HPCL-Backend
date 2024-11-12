import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import os
import json
import shutil
import fastapi
import traceback
import polars as pl
import urdhva_base.redispool
from fastapi.responses import FileResponse
import orchestrator.alerting.alert_helper as alert_helper
import orchestrator.masterdata.location_master_upload as location_master_upload

router = fastapi.APIRouter(prefix='/locationmaster')

logger = urdhva_base.logger.Logger.getInstance("api_manager")


# Action upload_location_master
@router.post('/upload_location_master', tags=['LocationMaster'])
async def locationmaster_upload_location_master(upload_file: fastapi.UploadFile = fastapi.File(None)):
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
    try:
        df = pl.read_csv(upload_file.file).with_columns(pl.all().cast(pl.Utf8, strict=False))
    except Exception as e:
        print(f"Exception while reading CSV file, {e}")
        return False, "Failed to process CSV file, Please reverify uploaded content and reverify"
    return await location_master_upload.upload_location_master_data(df)


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
            download_path = urdhva_base.settings.download_path
            downloadpath = os.path.join(download_path, "downloads")
            if not os.path.exists(downloadpath):
                os.makedirs(downloadpath)
            
            if not os.path.exists(f'{urdhva_base.settings.ui_path}/downloads'):
                os.system(f'ln -s {downloadpath} {urdhva_base.settings.ui_path}')
            df.write_csv(downloadpath + "location_master.csv")  # Save directly to file
            return {"status": True, "message": "Success","data": os.path.join('/downloads', "location_master.csv")}        
        return {"status": False, "message": "No data found", "data": []}
    return {"status": False, "message": "No response", "data": []}


# Action fetch_global_stats
@router.post('/fetch_global_stats', tags=['LocationMaster'])
async def locationmaster_fetch_global_stats(data: Locationmaster_Fetch_Global_StatsParams):
    ...


# Action download_template
@router.post('/download_template', tags=['LocationMaster'])
async def locationmaster_download_template(data: Locationmaster_Download_TemplateParams):
    """
    Download Location Master Template.

    This API endpoint creates a template CSV file for the Location Master data
    with the same columns as the existing location master CSV, but without any data.
    The template file is then served for download.

    Args:
        data (Locationmaster_Download_TemplateParams): The parameters for the 
        download template request.

    Returns:
        FileResponse: A response that serves the template CSV file for download.

    Raises:
        HTTPException: If there is an error creating or serving the CSV template.
    """
    download_path = urdhva_base.settings.download_path
    downloadpath = os.path.join(download_path, "downloads")
    template_file_path = os.path.join(download_path, "location_master_template.csv")

    df = pl.read_csv(f"{downloadpath}/location_master.csv")
    # Create a new empty DataFrame with the same columns
    template_df = pl.DataFrame({col: [] for col in df.columns})
    
    # Save the empty DataFrame as a template CSV
    template_df.write_csv(template_file_path)

    # Serve the template file for download
    return FileResponse(
        path=template_file_path,
        media_type="application/octet-stream",
        filename="location_master_template.csv"
    )