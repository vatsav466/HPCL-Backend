import urdhva_base.postgresmodel
import urdhva_base.queryparams
import urdhva_base.types
from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi
import polars as pl
router = fastapi.APIRouter()


@router.post("/locationmaster/upload_file", tags=['LocationMaster'])
async def upload_file(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    """
    Upload a CSV file to the server and read it into a DataFrame.

    Args:
    - uploadfile: The file to upload. The file should be a CSV file.

    Returns:
    - A dictionary containing the filename and the first few rows of the CSV file as a sample.
    - The filename is the path on the server where the file was saved.
    - The data is a list of dictionaries, where each dictionary represents a row in the CSV file.
    - The dictionary keys are the column names in the CSV file, and the dictionary values are the column values.

    Raises:
    - HTTPException: If the file upload fails.
    - HTTPException: If the file is not a valid CSV file.
    """
    os.makedirs("/Users/mac_1/Downloads", exist_ok=True)
    file_path = os.path.join("/Users/mac_1/Downloads/", uploadfile.filename)
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


@router.get('/locationmaster/{id}', response_model=LocationMaster, tags=['LocationMaster'])
async def get(id: str):
    return await LocationMaster.get(id, skip_secrets=True)


@router.get('/locationmaster', response_model=LocationMasterGetResp, tags=['LocationMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await LocationMaster.get_all(params, skip_secrets=True)


@router.post("/rolemaster/upload_file", tags=['RoleMaster'])
async def upload_file(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    """
    Upload a CSV file to the server and read it into a DataFrame.

    Args:
    - uploadfile: The file to upload. The file should be a CSV file.

    Returns:
    - A dictionary containing the filename and the first few rows of the CSV file as a sample.
    - The filename is the path on the server where the file was saved.
    - The data is a list of dictionaries, where each dictionary represents a row in the CSV file.
    - The dictionary keys are the column names in the CSV file, and the dictionary values are the column values.

    Raises:
    - HTTPException: If the file upload fails.
    - HTTPException: If the file is not a valid CSV file.
    """
    os.makedirs("/Users/mac_1/Downloads", exist_ok=True)
    file_path = os.path.join("/Users/mac_1/Downloads/", uploadfile.filename)
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


@router.get('/rolemaster/{id}', response_model=RoleMaster, tags=['RoleMaster'])
async def get(id: str):
    return await RoleMaster.get(id, skip_secrets=True)


@router.get('/rolemaster', response_model=RoleMasterGetResp, tags=['RoleMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await RoleMaster.get_all(params, skip_secrets=True)


@router.post("/assetmaster/upload_file", tags=['AssetMaster'])
async def upload_file(uploadfile: fastapi.UploadFile = fastapi.File(None)):
    """
    Upload a CSV file to the server and read it into a DataFrame.

    Args:
    - uploadfile: The file to upload. The file should be a CSV file.

    Returns:
    - A dictionary containing the filename and the first few rows of the CSV file as a sample.
    - The filename is the path on the server where the file was saved.
    - The data is a list of dictionaries, where each dictionary represents a row in the CSV file.
    - The dictionary keys are the column names in the CSV file, and the dictionary values are the column values.

    Raises:
    - HTTPException: If the file upload fails.
    - HTTPException: If the file is not a valid CSV file.
    """
    os.makedirs("/Users/mac_1/Downloads", exist_ok=True)
    file_path = os.path.join("/Users/mac_1/Downloads/", uploadfile.filename)
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


@router.get('/assetmaster/{id}', response_model=AssetMaster, tags=['AssetMaster'])
async def get(id: str):
    return await AssetMaster.get(id, skip_secrets=True)


@router.get('/assetmaster', response_model=AssetMasterGetResp, tags=['AssetMaster'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await AssetMaster.get_all(params, skip_secrets=True)

