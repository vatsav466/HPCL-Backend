from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
from pathlib import Path
import orchestrator.natural_gas.natural_gas_data_sync as natural_gas_data_sync

router = fastapi.APIRouter(prefix='/naturalgasconnections')


# Action upload_connection_data
@router.post('/upload_connection_data', tags=['NaturalGasConnections'])
async def naturalgasconnections_upload_connection_data(
    upload_file: fastapi.UploadFile = fastapi.File(None),
    include_cumulative_columns: bool = False,
    include_grand_total_ngc_column: bool = False,
):
    # Validate the uploaded file type
    file_extension = Path(upload_file.filename).suffix.lower()
    allowed_extensions = [".xlsx"]
    if file_extension not in allowed_extensions:
        return fastapi.responses.JSONResponse(
            status_code=400, content={"message": "Unsupported file type"}
        )
    return await natural_gas_data_sync.convert_dpr_file_data(
        upload_file,
        include_cumulative_columns=include_cumulative_columns,
        include_grand_total_ngc_column=include_grand_total_ngc_column,
    )


# Action confirm_data_sync
@router.post('/confirm_data_sync', tags=['NaturalGasConnections'])
async def naturalgasconnections_confirm_data_sync(data: Naturalgasconnections_Confirm_Data_SyncParams):
    return await natural_gas_data_sync.sync_dpr_data(data.ack_id)
