import urdhva_base
from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi
import polars as pl

router = fastapi.APIRouter(prefix='/assetmaster')


# Action upload_masterFile
@router.post('/upload_masterFile', tags=['AssetMaster'])
async def assetmaster_upload_masterfile(uploadfile: fastapi.UploadFile = fastapi.File(None)):
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


# Action upload_masterFile
@router.post('/upload_masterFile', tags=['AssetMaster'])
async def assetmaster_upload_masterfile(data: Assetmaster_Upload_MasterfileParams):
    ...
