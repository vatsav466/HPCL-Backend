from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import pandas as pd
import traceback
from http.client import HTTPException

router = fastapi.APIRouter(prefix='/lpginfra')


# Action upload_lpg_file
@router.post('/upload_lpg_file', tags=['LPGInfra'])
async def lpginfra_upload_lpg_file(data: fastapi.UploadFile):
    try:
        df = pd.read_excel(data.file, sheet_name='LPG plants').fillna("")
        save_path = "/opt/ceg/algo/orchestrator/masterdata/infra_inputs"
        os.makedirs(save_path, exist_ok=True)
        dt_str = datetime.datetime.now().strftime("%Y%m%d_%H-%M-%S") + f"_{datetime.datetime.now().microsecond}"
        filename = f"LPG_{dt_str}.xlsx"
        file_location = os.path.join(save_path, filename)
        print('file_location: ',file_location)
        df.to_excel(file_location, sheet_name='LPG', index=False)
        df.columns = df.columns.str.strip().str.lower()
        df['bu'] = 'LPG'
        df['filename'] = filename

        df = df.rename(
            columns={'company': 'company', 'location': 'location_name', 'zone': 'zone', 'state': 'state',
                     'district': 'district',
                     'installed bottling capacity    (tmtpa)': 'installed_bottling_capacity',
                     'operating bottling capacity    (tmtpa)': 'operating_bottling_capacity',
                     'ccoe tankage  (tmt)': 'ccoe_tankage', 'time of commissioning': 'time_of_commissioning',
                     'mode': 'mode', 'supply': 'supply', 'LOCATION': 'location_name',
                     'latitude': 'latitude', 'longitude': 'longitude'
                     })

        query = ''' * FROM location_master'''

        resp = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0, skip=0)
        loc_df = pd.DataFrame(resp['data'])
        loc_df['updated_by'] = ''
        df['updated_by'] = ''
        df['sap code'] = df['sap code'].apply(
            lambda x: str(int(float(x))) if pd.notnull(x) and str(x).strip() != "" else ""
        )
        df['time_of_commissioning'] = df['time_of_commissioning'].astype(str)
        df['installed_bottling_capacity'] = pd.to_numeric(df['installed_bottling_capacity'], errors='coerce').fillna(
            0.0).astype(float)
        df['operating_bottling_capacity'] = pd.to_numeric(df['operating_bottling_capacity'], errors='coerce').fillna(
            0.0).astype(float)
        df['ccoe_tankage'] = pd.to_numeric(df['ccoe_tankage'], errors='coerce').fillna(0.0).astype(float)

        loc_df['sap_id'] = loc_df['sap_id'].astype(str)
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce').fillna(
            0).astype(float)
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce').fillna(0).astype(float)

        merged_df = df.merge(
            loc_df[['sap_id', 'bu', 'zone', 'state', 'district', 'city', 'address', 'region', 'name']],
            left_on='sap code',
            right_on='sap_id',
            how='left', suffixes=('', '_Y')
        )

        merged_df['sap_id'] = merged_df['sap_id'].fillna(merged_df['sap code'])

        for col in ['bu', 'zone', 'state', 'district', 'city', 'address', 'region', 'name']:
            merged_df[col] = merged_df[col].fillna("")

        merged_df = merged_df[[
            'sap_id', 'bu', 'zone', 'state', 'district', 'city', 'address', 'region',
            'company', 'location_name', 'name', 'installed_bottling_capacity', 'operating_bottling_capacity',
            'ccoe_tankage',
            'time_of_commissioning', 'mode', 'supply', 'latitude', 'longitude', 'filename', 'updated_by'
        ]]
        for col in merged_df.select_dtypes(include='object').columns:
            merged_df[col] = merged_df[col].astype(str).str.strip()

        final_records = merged_df.fillna("").to_dict(orient="records")

        query = ''' DELETE FROM lpg_infra '''
        result = await urdhva_base.BasePostgresModel.execute_query(query)
        print(result)

        await LPGInfra.bulk_update(final_records, upsert=False)
        await HistoricLPGInfra.bulk_update(final_records, upsert=False)
        return 'Uploaded successfully'

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
