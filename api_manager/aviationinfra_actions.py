from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import urdhva_base
import fastapi
import pandas as pd
import datetime
import traceback
from http.client import HTTPException
import orchestrator.dashboard.chart_factory.infra_functions as infra_functions
from fastapi.responses import FileResponse, JSONResponse
import polars as pl

router = fastapi.APIRouter(prefix='/aviationinfra')


# Action upload_aviation_file
@router.post('/upload_aviation_file', tags=['AVIATIONInfra'])
async def aviationinfra_upload_aviation_file(file: fastapi.UploadFile):
    try:
        df = pd.read_excel(file.file, sheet_name='Aviation').fillna("")
        save_path = "/opt/ceg/algo/orchestrator/masterdata/infra_inputs"
        os.makedirs(save_path, exist_ok=True)
        dt_str = datetime.datetime.now().strftime("%Y%m%d_%H-%M-%S") + f"_{datetime.datetime.now().microsecond}"
        filename = f"Aviation_{dt_str}.xlsx"
        file_location = os.path.join(save_path, filename)
        print('file_location: ', file_location)
        df.to_excel(file_location, sheet_name='LPG', index=False)
        df.columns = df.columns.str.strip().str.lower()
        df['sbu'] = 'AVIATION'
        df['filename'] = filename

        df = df.rename(
            columns={'sap code': 'sap_id', 'company': 'company', 'source 1': 'location_name', 'source 2': 'name',
                     'zone': 'zone', 'state': 'state',
                     'district': 'district', 'aviation sbu': 'city',
                     'tankage': 'tankage', 'operation status': 'operation_status',
                     'mode': 'mode', 'address': 'address', 'pin code': 'pincode', 'status': 'status',
                     'latitude': 'latitude', 'longitude': 'longitude'
                     })
        print(df.columns)
        df['updated_by'] = ''
        df['sap_id'] = df['sap_id'].apply(
            lambda x: str(int(float(x))) if pd.notnull(x) and str(x).strip() != "" else ""
        )

        df['tankage'] = pd.to_numeric(df['tankage'], errors='coerce').fillna(
            0.0).astype(float)

        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce').fillna(
            0).astype(float)
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce').fillna(0).astype(float)
        df['state'] = df['state'].astype(str).str.replace(r"&", "and", regex=True)
        df['region'] = df['state']
        df['name'] = df['name'].fillna('').astype(str)
        df['pincode'] = df['pincode'].fillna('').astype(str)

        df = df[[
            'sap_id', 'sbu', 'zone', 'state', 'district', 'city', 'address', 'region',
            'company', 'location_name', 'name', 'tankage', 'operation_status',
            'mode', 'address', 'pincode', 'status', 'latitude', 'longitude', 'filename', 'updated_by'
        ]]

        final_records = df.fillna("").to_dict(orient="records")

        query = ''' DELETE FROM aviation_infra '''
        result = await urdhva_base.BasePostgresModel.execute_query(query)
        print(result)

        await AVIATIONInfra.bulk_update(final_records, upsert=False)
        await HistoricAVIATIONInfra.bulk_update(final_records, upsert=False)
        return 'Uploaded successfully'

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


# Action get_all_aviation_infra
@router.post('/get_all_aviation_infra', tags=['AVIATIONInfra'])
async def aviationinfra_get_all_aviation_infra(data: Aviationinfra_Get_All_Aviation_InfraParams):
    try:
        params = urdhva_base.queryparams.QueryParams()
        params.fields = []
        params.limit = 0
        resp = await AVIATIONInfra.get_all(params, resp_type="plain")
        return resp
    except Exception as e:
        print(f"Error in get_all_aviation_infra': {e}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})
