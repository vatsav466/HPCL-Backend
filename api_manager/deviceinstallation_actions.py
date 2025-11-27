from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import urdhva_base.queryparams as queryparams

router = fastapi.APIRouter(prefix='/deviceinstallation')


# Action update_device_installation
# @router.post('/update_device_installation', tags=['DeviceInstallation'])
# # async def deviceinstallation_update_device_installation(data: Deviceinstallation_Update_Device_InstallationParams):
# async def deviceinstallation_update_device_installation(
#     data: Deviceinstallation_Update_Device_InstallationParams = Depends(),
#     certificate_file: UploadFile | None = File(None),
# ):
#     try:
#         # 1) Convert UI payload to dict
#         payload = data.dict()
#         sap_tt_no = payload.get("sap_tt_no")

#         # 2) If user uploaded a certificate file → save it & store path in payload
#         if certificate_file is not None and sap_tt_no:
#             file_path = await save_certificate_file(certificate_file, sap_tt_no)
#             payload["certificate"] = file_path  # overwrite manual text like "ISO27001"

#         # 3) Check if this sap_tt_no already exists
#         params = queryparams.QueryParams()
#         params.fields = []  # all fields
#         params.q = f"sap_tt_no='{sap_tt_no}'"

#         existing = await DeviceInstallation.get_all(params, resp_type="plain")

#         # Normalize response to dict
#         if not isinstance(existing, dict):
#             if hasattr(existing, "_dict_"):
#                 existing = existing._dict_
#             elif hasattr(existing, "__dict__"):
#                 existing = existing.__dict__

#         # If any record found, return duplicate message
#         if existing.get("data"):
#             return {
#                 "status": False,
#                 "message": f"SAP TT No. {sap_tt_no} already exists. Record not inserted.",
#                 "data": {}
#             }

#         # 4) If not duplicate → insert new record
#         record = DeviceInstallationCreate(**payload)
#         result = await record.create()

#         if not isinstance(result, dict):
#             if hasattr(result, "_dict_"):
#                 result = result._dict_
#             elif hasattr(result, "__dict__"):
#                 result = result.__dict__

#         return {
#             "status": True,
#             "message": "Device installation saved successfully",
#             "data": result
#         }

#     except Exception as e:
#         return {
#             "status": False,
#             "message": f"Failed to save device installation: {e}",
#             "data": {}
#         }
# Action update_device_installation
@router.post('/update_device_installation', tags=['DeviceInstallation'])
async def deviceinstallation_update_device_installation(data: Deviceinstallation_Update_Device_InstallationParams):
    try:
        # 1) Convert UI payload to dict
        payload = data.dict()
        sap_tt_no = payload.get("sap_tt_no")

        # 2) Check if this sap_tt_no already exists
        params = queryparams.QueryParams()
        params.fields = []  # all fields
        params.q = f"sap_tt_no='{sap_tt_no}'"

        existing = await DeviceInstallation.get_all(params, resp_type="plain")

        # Normalize response to dict
        if not isinstance(existing, dict):
            if hasattr(existing, "_dict_"):
                existing = existing._dict_
            elif hasattr(existing, "__dict__"):
                existing = existing.__dict__

        # If any record found, return duplicate message
        if existing.get("data"):
            return {
                "status": False,"message": f"SAP TT No {sap_tt_no} already exists. Record not inserted","data": {}
            }

        # 3) If not duplicate → insert new record
        record = DeviceInstallationCreate(**payload)
        result = await record.create()

        if not isinstance(result, dict):
            if hasattr(result, "_dict_"):
                result = result._dict_
            elif hasattr(result, "__dict__"):
                result = result.__dict__

        return {
            "status": True,"message": "Device installation saved successfully","data": result
        }

    except Exception as e:
        return {"status": False,"message": f"Failed to save device installation: {e}","data": {}
        }