import os
import shutil
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import urdhva_base.queryparams as queryparams
from fastapi import UploadFile, File, Depends,Form
from hpcl_ceg_model import DeviceInstallation
                              



router = fastapi.APIRouter(prefix='/deviceinstallation')

# Action update_device_installation
@router.post('/update_device_installation', tags=['DeviceInstallation'])
async def deviceinstallation_upload_certificate(
    payload: str = Form(...),
    certificate_file: UploadFile = File(...)
):
    try:
        import json
        data = json.loads(payload)

        sap_tt_no = data.get("sap_tt_no")
        if not sap_tt_no:
            return {"status": False, "message": "sap_tt_no is required", "data": []}

        # 1) Save file
        file_path = await save_certificate_file(certificate_file, sap_tt_no)

        # 2) Fetch existing record
        params = queryparams.QueryParams()
        params.q = f"sap_tt_no='{sap_tt_no}'"
        params.limit = 1

        existing = await DeviceInstallation.get_all(params, resp_type="plain")

        # --- Normalize existing ---
        if isinstance(existing, dict):
            rows = existing.get("data", [])
        elif isinstance(existing, list):
            rows = existing
        else:
            rows = []

        if not rows:
            return {"status": False, "message": "No record found", "data": []}

        record_id = rows[0].get("id")

        # 3) ONLY update certificate field
        update_payload = {"certificate": file_path}

        await DeviceInstallation(id=record_id, **update_payload).modify()

        # 4) Fetch updated record
        updated = await DeviceInstallation.get_all(params, resp_type="plain")

        # --- Normalize updated (THIS WAS FAILING FOR YOU) ---
        if isinstance(updated, dict):
            updated_rows = updated.get("data", [])
        elif isinstance(updated, list):
            updated_rows = updated
        else:
            updated_rows = []

        return {
            "status": True,
            "message": "Certificate uploaded successfully",
            "file_path": file_path,
            "data": updated_rows
        }

    except Exception as e:
        print("Upload error:", e)
        return {"status": False, "message": str(e), "data": []}

async def save_certificate_file(file: UploadFile, sap_tt_no: str):
    # Save to /opt/downloads
    base_dir = "/opt/downloads"
    os.makedirs(base_dir, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[-1]
    file_name = f"{sap_tt_no}_certificate.{ext}"
    file_path = os.path.join(base_dir, file_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path

# Action upload_certificate
# ---------------------------------------------------------
# API: upload + update only certificate column
# ---------------------------------------------------------
@router.post('/upload_certificate', tags=['DeviceInstallation'])
async def upload_certificate(
        sap_tt_no: str = Form(...),
        certificate_file: UploadFile = File(...)
):
    try:
        # 1) Save file
        file_path = await save_certificate_file(certificate_file, sap_tt_no)

        # 2) Fetch existing record
        params = queryparams.QueryParams()
        params.q = f"sap_tt_no='{sap_tt_no}'"
        params.limit = 1

        existing = await DeviceInstallation.get_all(params, resp_type="plain")

        # Normalize
        rows = existing.get("data", []) if isinstance(existing, dict) else existing

        if not rows:
            return {
                "success": False,
                "message": f"No record found for sap_tt_no {sap_tt_no}"
            }

        record_id = rows[0].get("id")   # Correct field is "id"

        # 3) Update certificate field
        updated_data = {"certificate": file_path}
        await DeviceInstallation(id=record_id, **updated_data).modify()

        # 4) Return response
        return {
            "success": True,
            "message": "Certificate uploaded and updated successfully",
            "sap_tt_no": sap_tt_no,
            "certificate_path": file_path
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }
