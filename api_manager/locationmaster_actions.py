import urdhva_base
from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi
import polars as pl

router = fastapi.APIRouter(prefix='/locationmaster')


# Action upload_masterFile
@router.post('/upload_masterFile', tags=['LocationMaster'])
async def locationmaster_upload_masterfile(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    """
    Uploads a master file and returns the file path and the first few rows of the data as a sample.

    Args:
        uploadfile (fastapi.UploadFile): The file to be uploaded

    Returns:
        A dictionary containing the file path and the first few rows of the data as a sample.
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
        raise HTTPException(status_code=500, detail="File upload failed.") from e
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to process CSV file.") from e