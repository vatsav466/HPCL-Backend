from dnc_schema_enum import *
from dnc_schema_model import *
import fastapi
import json
import datetime
import requests
import urdhva_base

router = fastapi.APIRouter(prefix='/locationdevice')

logger = urdhva_base.logger.Logger.getInstance("api_manager")


# Action upload_device_masterFile
@router.post('/upload_device_masterFile', tags=['LocationDevice'])
async def locationdevice_upload_device_masterfile(data: Locationdevice_Upload_Device_MasterfileParams):
    ...


# Action read_location_device_data
@router.post('/read_location_device_data', tags=['LocationDevice'])
async def locationdevice_read_location_device_data(data: Locationdevice_Read_Location_Device_DataParams):
    loc_id = data.location_id
    resp = await dnc_schema_model.LocationDevice.get(loc_id)
    return {
        "status": True, "message": "Justification Submitted", "data": resp
    }
