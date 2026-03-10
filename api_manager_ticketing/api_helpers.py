import urdhva_base
from hpcl_ceg_ticketing_enum import *
from hpcl_ceg_ticketing_model import *
from fastapi import APIRouter, HTTPException
import uuid
import traceback
import datetime
import json
from pathlib import Path
import utilities.minio_connector as minio_connector
from typing import List

async def attach_file_common(
    model_class,
    ticket_id: str,
    comment_id: str,
    upload_files: List[fastapi.UploadFile],
    attachment_field: str
):

    if not upload_files:
        return {"status": False, "message": "No files uploaded"}

    allowed_extensions = [
        ".png", ".jpg", ".jpeg", ".gif",
        ".csv", ".xlsx", ".xls",
        ".pdf", ".doc", ".docx"
    ]

    target_dir = urdhva_base.settings.ticketing_attachments
    os.makedirs(target_dir, exist_ok=True)

    # Fetch record first
    params = urdhva_base.queryparams.QueryParams(
        q=f"id='{comment_id}' and ticket_id='{ticket_id}'",
        limit=1
    )

    resp = await model_class.get_all(params, resp_type="plain")

    if not resp or not resp.get("data"):
        return {"status": False, "message": "Record not found"}

    record = resp["data"][0]

    # Get existing attachments (LIST SAFE)
    existing_attachments = record.get(attachment_field) or []

    if isinstance(existing_attachments, str):
        try:
            existing_attachments = json.loads(existing_attachments)
        except:
            existing_attachments = []

    uploaded_paths = []

    for upload_file in upload_files:

        file_extension = Path(upload_file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            continue  # skip unsupported file

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex
        # unique_filename = f"{timestamp}_{upload_file.filename}_{timestamp}"
        original_name = Path(upload_file.filename).stem  # Solar_installation
        extension = Path(upload_file.filename).suffix  # .xlsx
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{original_name}_{timestamp}{extension}"
        saved_file_path = os.path.join(target_dir, unique_filename)

        try:
            # Save locally
            with open(saved_file_path, "wb") as f:
                f.write(await upload_file.read())

            # Upload to MinIO
            status, minio_path = minio_connector.upload_to_minio(
                "ticket_comments",
                record.get("ticket_id"),
                unique_id,
                saved_file_path
            )

            if status:
                existing_attachments.append(minio_path)
                uploaded_paths.append(minio_path)

        finally:
            if os.path.exists(saved_file_path):
                os.remove(saved_file_path)

    # Update DB once
    await model_class(
        **{
            "id": record.get("id"),
            attachment_field: existing_attachments
        }
    ).modify()

    return {
        "status": True,
        "message": "Files attached successfully",
        attachment_field: existing_attachments
    }