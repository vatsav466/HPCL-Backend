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

        df = df.rename(
            columns={'Company': 'company', 'LOCATION': 'location_name',
                     'INSTALLED BOTTLING CAPACITY    (TMTPA)': 'installed_bottling_capacity',
                     'OPERATING BOTTLING CAPACITY    (TMTPA)': 'operating_bottling_capacity',
                     'CCOE TANKAGE  (TMT)': 'ccoe_tankage', 'Time of commissioning': 'time_of_commissioning',
                     'Mode': 'mode', 'Supply': 'supply', 'LOCATION': 'location_name',
                     'Latitude': 'latitude', 'Longitude': 'longitude'
                     })

        query = ''' * FROM location_master'''

        resp = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0, skip=0)
        loc_df = pd.DataFrame(resp['data'])
        loc_df['updated_by'] = ''
        df['updated_by'] = ''
        df['SAP code'] = df['SAP code'].apply(
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
            left_on='SAP code',
            right_on='sap_id',
            how='left', suffixes=('', '_Y')
        )

        merged_df = merged_df[[
            'sap_id', 'bu', 'zone', 'state', 'district', 'city', 'address', 'region',
            'company', 'location_name', 'name', 'installed_bottling_capacity', 'operating_bottling_capacity',
            'ccoe_tankage',
            'time_of_commissioning', 'mode', 'supply', 'latitude', 'longitude', 'updated_by'
        ]]
        final_records = merged_df.fillna("").to_dict(orient="records")
        await LPGInfra.bulk_update(final_records, upsert=False)
        return 'Uploaded successfully'

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
