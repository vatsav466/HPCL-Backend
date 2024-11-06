import urdhva_base
from hpcl_cng_enum import *
from hpcl_cng_model import *
import os
import shutil
import fastapi
import polars as pl

router = fastapi.APIRouter(prefix='/lpgassetmaster')

logger = urdhva_base.logger.Logger.getInstance("api_manager")

# Action upload_tas_asset_master
@router.post('/upload_tas_asset_master', tags=['LPGAssetMaster'])
async def lpgassetmaster_upload_tas_asset_master(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    """
    Upload TAS Asset Master file.

    This API endpoint accepts a CSV file and saves it to the MFT path.
    It then reads the CSV file and returns the data as a JSON response.

    Args:
        data (Lpgassetmaster_Upload_Tas_Asset_MasterParams): The CSV file to be uploaded.

    Returns:
        Dict[str, Any]: A JSON response containing the filename and data.

    Raises:
        HTTPException: If there is an error uploading the file.
        HTTPException: If there is an error processing the CSV file.
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
