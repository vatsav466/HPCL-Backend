from hpcl_cng_enum import *
from hpcl_cng_model import *
import fastapi

router = fastapi.APIRouter(prefix='/dncrolemaster')


# Action get_dnc_role_master
@router.post('/get_dnc_role_master', tags=['DNCRoleMaster'])
async def dncrolemaster_get_dnc_role_master(data: Dncrolemaster_Get_Dnc_Role_MasterParams):
    ...


# Action download_dnc_role_master
@router.post('/download_dnc_role_master', tags=['DNCRoleMaster'])
async def dncrolemaster_download_dnc_role_master(data: Dncrolemaster_Download_Dnc_Role_MasterParams):
    ...


# Action upload_dnc_role_master
@router.post('/upload_dnc_role_master', tags=['DNCRoleMaster'])
async def dncrolemaster_upload_dnc_role_master(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    """
    Upload DNC Role Master data.

    This API endpoint accepts a CSV file, saves it to the specified MFT path, and 
    processes it by storing each row in Redis. The key in Redis is created using 
    the format `bu_sapid`, and the value is the entire row in JSON format.

    Args:
        uploadfile (fastapi.UploadFile): The CSV file to be uploaded.

    Returns:
        Dict[str, Any]: A JSON response containing the filename and the first few rows of data.

    Raises:
        HTTPException: If there is an error uploading the file (500).
        HTTPException: If there is an error processing the CSV file (400).
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
            await redis_client.hset("dnc_master", redis_key, json.dumps(row)) 
            
        # Display data or perform further processing as needed
        return {"filename": file_path, "data": data.to_dicts()}  # Returns the first few rows as a sample
    except Exception as e:
        raise fastapi.HTTPException(status_code=500, detail="File upload failed.") from e
    except Exception as e:
        raise fastapi.HTTPException(status_code=400, detail="Failed to process CSV file.") from e

