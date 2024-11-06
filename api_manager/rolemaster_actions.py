import urdhva_base
from hpcl_cng_enum import *
from hpcl_cng_model import *
import os
import json
import shutil
import fastapi
import constants
import traceback
import polars as pl

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
    redis_client = await urdhva_base.redispool.get_redis_connection()
    upload_dir = urdhva_base.settings.mft_path
    os.makedirs(upload_dir, exist_ok=True)
    
    # Define the file path
    file_path = os.path.join(upload_dir, uploadfile.filename)
    
    # Save the uploaded file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(uploadfile.file, buffer)
        data = pl.read_csv(file_path).with_columns(pl.all().cast(pl.Utf8,strict=False))
        # Iterate through the rows of the CSV and extract `bu` and `sapid`
        data = data.rename(constants.Role)
        for row in data.to_dicts():
            bu = row["bu"]  # Assuming 'bu' column exists in the CSV
            sapid = row["sapid"]  # Assuming 'sapid' column exists in the CSV
            
            # Create a Redis key using the format bu_sapid
            redis_key = f"{bu.upper()}_{sapid}"
            
            # Set the key in Redis with the value being the data row
            await redis_client.hset("role_master", redis_key, json.dumps(row)) 
        
        data = data.to_dicts()
        for data_dump in data:
            data_obj = RoleMasterCreate(**data_dump)
            print(await data_obj.create())

        # Display data or perform further processing as needed
        return {"filename": file_path, "data": data} 

    except Exception as e:
        print(traceback.format_exc())
        raise fastapi.HTTPException(status_code=500, detail="File upload failed.") from e
    except Exception as e:
        print(traceback.format_exc())
        raise fastapi.HTTPException(status_code=400, detail="Failed to process CSV file.") from e

