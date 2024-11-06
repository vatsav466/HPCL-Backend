from ceg_role_master_enum import *
from ceg_role_master_model import *
import fastapi
import json
import polars as pl

router = fastapi.APIRouter(prefix='/cegrolemaster')


# Action get_ceg_role_master
@router.post('/get_ceg_role_master', tags=['CEGRoleMaster'])
async def cegrolemaster_get_ceg_role_master(data: Cegrolemaster_Get_Ceg_Role_MasterParams):
    """
    Get CEG Role Master data.

    This API endpoint retrieves the CEG Role Master data 
    based on the given filters.

    Parameters:
    - data (Cegrolemaster_Get_Ceg_Role_MasterParams): The parameters for the API call.
        role_id (str): The role ID.
        source_system (str): The source system.

    Returns:
        CEGRoleMasterGetResp: The response containing the CEG Role Master data.
    """
    ...


# Action download_ceg_role_master
@router.post('/download_ceg_role_master', tags=['CEGRoleMaster'])
async def cegrolemaster_download_ceg_role_master(data: Cegrolemaster_Download_Ceg_Role_MasterParams):
    """
    Download CEG Role Master data.

    This API endpoint generates a CSV file containing the CEG Role Master data 
    based on the specified conditions and saves it to the MFT path.

    Args:
        data (Cegrolemaster_Download_Ceg_Role_MasterParams): Parameters 
        specifying the conditions for downloading the CEG Role Master data.

    Returns:
        None: The function does not return any value but writes a CSV file 
        to the specified path.

    Raises:
        HTTPException: If there is an error in generating or saving the CSV file.
    """
    role_master_path = os.path.join(
        urdhva_base.settings.mft_path, 'ceg_role_master.csv'
    )


# Action upload_dnc_role_master
@router.post('/upload_dnc_role_master', tags=['CEGRoleMaster'])
async def cegrolemaster_upload_dnc_role_master(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    """
    Upload DNC Role Master data.

    This API endpoint accepts a CSV file and saves it to the MFT path. It then reads the CSV file 
    and saves the data to the database.

    Args:
        uploadfile (fastapi.UploadFile): The CSV file to be uploaded.

    Returns:
        None: The function does not return any value but writes a CSV file 
        to the specified path.

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
        data = pl.read_csv(file_path)
        # Iterate through the rows of the CSV and extract `bu` and `sapid`
        for row in data.iter_rows(named=True):
            bu = row["bu"]  # Assuming 'bu' column exists in the CSV
            sapid = row["sapid"]  # Assuming 'sapid' column exists in the CSV
            
            # Create a Redis key using the format bu_sapid
            redis_key = f"{bu.upper()}_{sapid}"
            
            # Set the key in Redis with the value being the data row
            await redis_client.hset("ceg_master", redis_key, json.dumps(row)) 
            
        # Display data or perform further processing as needed
        return {"filename": file_path, "data": data.to_dicts()}  # Returns the first few rows as a sample
    except Exception as e:
        raise fastapi.HTTPException(status_code=500, detail="File upload failed.") from e
    except Exception as e:
        raise fastapi.HTTPException(status_code=400, detail="Failed to process CSV file.") from e
