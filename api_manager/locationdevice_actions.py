import urdhva_base
from hpcl_cng_enum import *
from hpcl_cng_model import *
import fastapi
import os
import shutil
import polars as pl
from api_manager import hpcl_cng_model

router = fastapi.APIRouter(prefix='/locationdevice')

logger = urdhva_base.logger.Logger.getInstance("api_manager")

# Action upload_device_masterFile
@router.post('/upload_device_masterFile', tags=['LocationDevice'])
async def locationdevice_upload_device_masterfile(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    """
    Upload Device Master File.

    This API endpoint accepts a device master file and processes it for the Location Device.
    
    Args:
        data (Locationdevice_Upload_Device_MasterfileParams): The device master file data to be uploaded.
    
    Returns:
        Response: A response indicating the success or failure of the upload operation.
    
    Raises:
        HTTPException: If there is an error during the upload or processing of the file.
    """
    upload_dir = urdhva_base.settings.mft_path
    os.makedirs(upload_dir, exist_ok=True)
    
    # Define the file path
    file_path = os.path.join(upload_dir, uploadfile.filename)
    
    # Save the uploaded file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(uploadfile.file, buffer)
        data = pl.read_csv(file_path)
        # Display data or perform further processing as needed
        return {"filename": file_path, "data": data.to_dicts()}  # Returns the first few rows as a sample
    except Exception as e:
        raise fastapi.HTTPException(status_code=500, detail="File upload failed.") from e
    except Exception as e:
        raise fastapi.HTTPException(status_code=400, detail="Failed to process CSV file.") from e



# Action read_location_device_data
@router.post('/read_location_device_data', tags=['LocationDevice'])
async def locationdevice_read_location_device_data(data: Locationdevice_Read_Location_Device_DataParams):
    """
    Action read_location_device_data

    This API is used to read location device data.

    Args:
        data (Locationdevice_Read_Location_Device_DataParams): A JSON object with the following properties:
            - location_id (str): The ID of the location device

    Returns:
        A JSON object with the following properties:
            - status (bool): True if the justification was submitted successfully, False otherwise
            - message (str): A message indicating the status of the justification submission
            - data (dict): The location device data
    """
    try:
        loc_id = data.location_id
        resp = await hpcl_cng_model.LocationDevice.get(loc_id)
        return {
            "status": True, "message": "Justification Submitted", "data": resp
        }
    
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": str(e), "data": []}

