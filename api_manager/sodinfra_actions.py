from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import urdhva_base
import fastapi
import pandas as pd
import traceback
from http.client import HTTPException
import orchestrator.dashboard.chart_factory.infra_functions as infra_functions

router = fastapi.APIRouter(prefix='/sodinfra')


# Action upload_sod_file
@router.post('/upload_sod_file', tags=['SodInfra'])
async def sodinfra_upload_sod_file(data: fastapi.UploadFile):
    try:
        df = pd.read_excel(data.file, sheet_name='SOD').fillna("")
        df.columns = df.columns.str.strip().str.lower()
        df['bu'] = 'TAS'

        df = df.rename(
            columns={
                'company': 'company', 'type': 'type', 'location name': 'location_name', 'region ppac': 'region_ppac', 'ms (kl)': 'ms',
                'sko(kl)': 'sko', 'hsd(kl)': 'hsd', 'total(kl)': 'total', 'mode of reciept': 'mode_of_receipt',
                'latitude': 'latitude', 'longitude': 'longitude'
            }
        )

        query = ''' * FROM location_master'''
        resp = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0, skip=0)
        loc_df = pd.DataFrame(resp['data'])

        loc_df['updated_by'] = ''
        df['updated_by'] = ''
        df['location code'] = df['location code'].apply(
            lambda x: str(int(float(x))) if pd.notnull(x) and str(x).strip() != "" else ""
        )
        df['ms'] = pd.to_numeric(df['ms'], errors='coerce').fillna(0).astype(int)
        df['sko'] = pd.to_numeric(df['sko'], errors='coerce').fillna(0).astype(int)
        df['hsd'] = pd.to_numeric(df['hsd'], errors='coerce').fillna(0).astype(int)
        df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0).astype(int)
        loc_df['sap_id'] = loc_df['sap_id'].astype(str)

        merged_df = df.merge(
            loc_df[['sap_id', 'bu', 'zone', 'state', 'district', 'city', 'address', 'region', 'name']],
            left_on='location code',
            right_on='sap_id',
            how='left', suffixes=('', '_Y')
        )

        merged_df['sap_id'] = merged_df['sap_id'].fillna(merged_df['location code'])

        for col in ['bu', 'zone', 'state', 'district', 'city', 'address', 'region', 'name']:
            merged_df[col] = merged_df[col].fillna("")

        merged_df = merged_df[[
            'sap_id', 'bu', 'zone', 'state', 'district', 'city', 'address', 'region',
            'company', 'type', 'location_name', 'name', 'region_ppac', 'ms', 'sko',
            'hsd', 'total', 'mode_of_receipt', 'latitude', 'longitude','updated_by'
        ]]
        final_records = merged_df.fillna("").to_dict(orient="records")

        query = ''' DELETE FROM sod_infra '''
        result = await urdhva_base.BasePostgresModel.execute_query(query)
        print(result)

        await SodInfra.bulk_update(final_records, upsert=False)
        await HistoricSodInfra.bulk_update(final_records, upsert=False)
        return "Uploaded successfully"

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")



# Action get_all_sod_lpg_infra
@router.post('/get_all_sod_lpg_infra', tags=['SodInfra'])
async def sodinfra_get_all_sod_lpg_infra(data: Sodinfra_Get_All_Sod_Lpg_InfraParams):
    # return await infra_functions.sod_infra(data)
    return await infra_functions.sod_infra(filters=data.filters, cross_filters=data.cross_filters, drill_state=data.drill_state, limit=data.limit, time_grain=data.time_grain)


# Action get_count_company_infra
@router.post('/get_count_company_infra', tags=['SodInfra'])
async def sodinfra_get_count_company_infra(data: Sodinfra_Get_Count_Company_InfraParams):
    return await infra_functions.get_count_company_info(filters=data.filters, cross_filters=data.cross_filters,
                                           drill_state=data.drill_state, limit=data.limit, time_grain=data.time_grain)


# Action get_sod_lpg_infra
@router.post('/get_sod_lpg_infra', tags=['SodInfra'])
async def sodinfra_get_sod_lpg_infra(data: Sodinfra_Get_Sod_Lpg_InfraParams):
    return await infra_functions.get_sod_lpg_info(filters=data.filters, cross_filters=data.cross_filters,
                                                        drill_state=data.drill_state, limit=data.limit,
                                                        time_grain=data.time_grain)
