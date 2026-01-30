from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import os
import shutil
from fastapi import UploadFile, File, Depends
from fastapi import HTTPException
from fastapi.responses import FileResponse
import utilities.minio_connector as minio_connector
import httpx
import urdhva_base
from datetime import datetime
from orchestrator.workflow.workflow_process import Camunda
# import tassealdateform_actions
from  orchestrator.alerting.listener.tas_listener import load_device_data

router = fastapi.APIRouter(prefix='/tasfaulty')




# Action tas_faulty_create
@router.post("/tas_faulty_create", tags=["TasFaulty"])
async def tasfaulty_tas_faulty_create(
    data: Tasfaulty_Tas_Faulty_CreateParams = Depends(Tasfaulty_Tas_Faulty_CreateParams),
    certificate_file: UploadFile | str |  None = File(None)
):
    try:
        payload = data.dict()
        payload["status"]="Open"

        sap_id = payload.get("sap_id")
        device_type = payload.get("device_type")
        equipment_name = payload.get("equipment_name")

        # ---------------- DUPLICATE CHECK ----------------
        params = urdhva_base.queryparams.QueryParams()
        params.fields = []
        params.q = (
            f"sap_id='{sap_id}' "
            f"AND device_type='{device_type}' "
            f"AND equipment_name='{equipment_name}'"
        )

        existing = await TasFaulty.get_all(params, resp_type="plain")

        if existing.get("data"):
            return {
                "status": False,
                "message": (
                    "Duplicate TasFaulty record exists for "
                    f"SAP ID = {sap_id}, Equipment = {equipment_name} "),"data": {}
            }

        # ---------------- START WORKFLOW ----------------
        payload_workflow = {
            "variables": {
                "sap_id": {"value": sap_id, "type": "String"},
                "location_name": {"value": payload.get("name",""), "type": "String"},
                "device_type": {"value": device_type, "type": "String"},
                "equipment_name": {"value": equipment_name, "type": "String"},
                "zone": {"value": payload.get("zone",""), "type": "String"},
                "remarks": {"value": payload.get("user_remarks",""), "type": "String"},
                "status": {"value": payload.get("status",""), "type": "String"},
            }
        }

        camunda_resp = await Camunda().start_tas_faulty_workflow(payload=payload_workflow, workflowId="TASFAULTYCHECK")
        workflow_instance_id = camunda_resp.get("id","")
        payload["workflow_instance_id"] = workflow_instance_id


        # ---------------- SAVE CERTIFICATE ----------------
        if certificate_file:
            UPLOAD_DIR = os.path.join(
                urdhva_base.settings.uploads,
                "tas_faulty"
            )
            os.makedirs(UPLOAD_DIR, exist_ok=True)

            file_name = certificate_file.filename
            file_path = os.path.join(UPLOAD_DIR, file_name)
            faulty_val = payload.get("faulty")
            if isinstance(faulty_val, datetime):
                faulty_val = faulty_val.strftime("%Y%m%d_%H%M%S")

            object_name = f"{faulty_val}_{sap_id}_{equipment_name}"
            # Save locally
            with open(file_path, "wb") as f:
                f.write(await certificate_file.read())

            # Upload to MinIO
            status, minio_path = minio_connector.upload_to_minio(
                "TAS",
                "tas_faulty_certificates",
                object_name,
                file_path
            )

            if not status:
                return {
                    "status": False,
                    "message": "MinIO upload failed",
                    "error": minio_path
                }

            payload["certificate"] = minio_path

            #  cleanup local file
            try:
                os.remove(file_path)
            except Exception:
                pass

        # ---------------- INSERT ----------------
        record = TasFaultyCreate(**payload)
        result = await record.create()

        return {
            "status": True,
            "message": "TasFaulty record saved successfully",
            "data": result
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Failed to save TasFaulty record: {e}",
            "data": {}
        }


# Action update_faulty
@router.post('/update_faulty', tags=['TasFaulty'])
async def tasfaulty_update_faulty(data: Tasfaulty_Update_FaultyParams):
    try:
        id = int(data.transaction_id)
        vendor_remarks = data.vendor_remarks
        resolved = data.resolved  # Boolean

        # ---------------- FETCH RECORD ----------------
        params = urdhva_base.queryparams.QueryParams()
        params.q = f"id={id}"
        params.limit = 1
        params.fields = []

        existing = await TasFaulty.get_all(params, resp_type="plain")
        rows = existing.get("data")

        if not rows:
            return {
                "status": False,
                "message": "No faulty record found",
                "data": {}
            }

        row = rows[0]
        process_instance_id = row.get("workflow_instance_id")

        if not process_instance_id:
            return {
                "status": False,
                "message": "Workflow instance not linked",
                "data": {}
            }

        # ---------------- TRIGGER CAMUNDA FIRST ----------------
        camunda_payload = {
            "messageName": "Resolved",
            "processInstanceId": process_instance_id,
            "processVariables": {
                "resolved": {
                    "value": resolved,
                    "type": "Boolean"
                },
                "remarks": {
                    "value": vendor_remarks,
                    "type": "String"
                }
            }
        }

        async with httpx.AsyncClient() as client:
            camunda_resp = await client.post(
                f"{urdhva_base.settings.tas_faulty_camunda_url}/engine-rest/message",
                json=camunda_payload,
                timeout=10
            )

        if camunda_resp.status_code not in (200, 204):
            return {
                "status": False,
                "message": "workflow trigger failed",
                "data": camunda_resp.text
            }

        #update record
        update_data = dict(row)
        update_data.pop("id", None)
        update_data["vendor_remarks"] = vendor_remarks

        if resolved is False:
            update_data["status"] = "Rejected"

        if resolved is True:
            update_data["status"] = "Resolved"

        await TasFaulty(id=id, **update_data).modify()

        return {
            "status": True,
            "message": "workflow triggered successfully and record updated",
            "data": {
                "transaction_id": id,
                "resolved": resolved
            }
        }

    except Exception as e:
        return {
            "status": False,
            "message": str(e),
            "data": {}
        }



# Action get_info
@router.post("/get_info", tags=["TasFaulty"])
async def tasfaulty_get_info(data: Tasfaulty_Get_InfoParams):

    sap_id = data.sap_id
    device_type_filter = data.device_type

    device_json = load_device_data(sap_id)

    if not device_json:
        return {
            "status": False,
            "message": f"Device data not found for SAP ID {sap_id}"

        }

    devices = device_json.get("data", [])

    # -------------------------
    # CASE 1: Only sap_id
    # -------------------------
    if not device_type_filter:
        device_names = set()
        print('deddd',device_names)
        device_types = set()

        for device in devices:
            if device.get("device_type"):
                device_types.add(device["device_type"])
                # print('swa',device_types)

        return {
            "sap_id": sap_id,
            # "device_names": sorted(device_names),
            "device_types": sorted(device_types)
        }

    # -------------------------
    # CASE 2: sap_id + device_type
    # -------------------------
    filtered_device_names = set()

    for device in devices:
        # Condition 1
        if device.get("device_type") == device_type_filter:
            # Condition 2
            if device.get("device_name"):
                filtered_device_names.add(device["device_name"])


    return {
        "sap_id": sap_id,
        "device_type": device_type_filter,
        "device_names": sorted(filtered_device_names)
    }