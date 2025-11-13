import os
import urdhva_base
from minio import Minio
from minio.error import S3Error


def get_minio_client():
    return Minio(
        urdhva_base.settings.minio_endpoint.replace("https://", "").replace("http://", ""),
        access_key=urdhva_base.settings.minio_access_key,
        secret_key=urdhva_base.settings.minio_secret_key,
        region="us-east-1",
        secure=urdhva_base.settings.minio_secure,
    )


def upload_to_minio(bu, section, unique_id, filepath):
    if not os.path.exists(filepath):
        return False, "File not found"
    if not urdhva_base.settings.minio_endpoint:
        return False, "Missing minio endpoint"
    object_path = "/".join(["novex", bu, section, unique_id, os.path.basename(filepath)])
    try:
        minio_client = get_minio_client()
    except Exception as e:
        print(f"Exception while uploading {object_path}: {e}")
        return False, "Could not connect to minio"
    try:
        minio_client.fput_object(urdhva_base.settings.minio_bucket, object_path, filepath)
        object_stat = minio_client.stat_object(urdhva_base.settings.minio_bucket, object_path)
        return True, object_stat.object_name
    except Exception as e:
        print(f"Exception while uploading {object_path}: {e}")
        return False, "Error uploading file to minio"


def download_from_minio(object_path):
    if not urdhva_base.settings.minio_endpoint:
        return False, "Missing minio endpoint"
    try:
        minio_client = get_minio_client()
    except Exception as e:
        print(f"Exception while connecting to minio: {e}")
        return False, "Could not connect to minio"
    try:
        response = minio_client.get_object(urdhva_base.settings.minio_bucket, object_path)
        output_file = "/tmp/" + os.path.basename(object_path)
        with open(output_file, 'wb') as f:
            f.write(response.read())
        return True, output_file
    except Exception as e:
        print(f"Exception while downloading {object_path}: {e}")
        return False, "Error downloading file"
