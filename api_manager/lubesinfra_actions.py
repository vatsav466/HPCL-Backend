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

router = fastapi.APIRouter(prefix='/lubesinfra')


# Action upload_lubes_file
@router.post('/upload_lubes_file', tags=['LUBESInfra'])
async def lubesinfra_upload_lubes_file(file: fastapi.UploadFile):
    try:
        df = pd.read_excel(file.file, sheet_name='Lube blending facility').fillna("")
        save_path = "/opt/ceg/algo/orchestrator/masterdata/infra_inputs"
        os.makedirs(save_path, exist_ok=True)
        dt_str = datetime.datetime.now().strftime("%Y%m%d_%H-%M-%S") + f"_{datetime.datetime.now().microsecond}"
        filename = f"Lubes_{dt_str}.xlsx"
        file_location = os.path.join(save_path, filename)
        df.to_excel(file_location, sheet_name='Lubes', index=False)
        df.columns = df.columns.str.strip().str.lower()
        df['sbu'] = 'LUBES'
        df['filename'] = filename

        df = df.rename(
            columns={'sap code': 'sap_id', 'company': 'company', 'location': 'location_name', 'zone': 'zone',
                     'state': 'state', 'district': 'district', 'base oil tankages(kl)': 'base_oil_tankages', 'landline': 'landline',
                     'address': 'address', 'status': 'status', 'latitude': 'latitude', 'longitude': 'longitude'
                     }
        )
        df['updated_by'] = ''
        df['sap_id'] = df['sap_id'].apply(
            lambda x: str(int(float(x))) if pd.notnull(x) and str(x).strip() != "" else ""
        )
        df['base_oil_tankages'] = pd.to_numeric(df['base_oil_tankages'], errors='coerce').fillna(0.0)
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce').fillna(0.0)
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce').fillna(0.0)
        df['state'] = df['state'].astype(str).str.replace(r"&", "and", regex=True)
        df['region'] = df['state']
        df['city'] = df['district']
        df['name'] = df['location_name'].fillna('').astype(str)
        df['zone'] = ''
        df['landline'] = df['landline'].fillna('').astype(str)

        df = df[[
            'sap_id', 'sbu', 'zone', 'state', 'district', 'city', 'address', 'region',
            'company', 'location_name', 'name', 'base_oil_tankages', 'landline',
            'address', 'status', 'latitude', 'longitude', 'filename', 'updated_by'
        ]]

        final_records = df.fillna("").to_dict(orient="records")
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        current_data = await LUBESInfra.get_all(urdhva_base.QueryParams(limit=0), resp_type="plain")
        existing_records = current_data.get("data", [])
        print('existing_records count: ', len(existing_records))

        if existing_records:
            print("----Moving current LUBESInfra to Historic before inserting new data----")

            numeric_fields = ["base_oil_tankages", "latitude", "longitude"]
            for rec in existing_records:
                rec["snapshot_date"] = today_str
                for field in numeric_fields:
                    try:
                        rec[field] = float(rec[field]) if rec[field] not in ("", None) else 0.0
                    except:
                        rec[field] = 0.0
            await HistoricLUBESInfra.bulk_update(existing_records, upsert=False)

        await urdhva_base.BasePostgresModel.execute_query("DELETE FROM lubes_infra")
        await LUBESInfra.bulk_update(final_records, upsert=False)
        return 'Uploaded successfully'

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


# Action get_all_lubes_infra
@router.post('/get_all_lubes_infra', tags=['LUBESInfra'])
async def lubesinfra_get_all_lubes_infra(data: Lubesinfra_Get_All_Lubes_InfraParams):
    try:
        params = urdhva_base.queryparams.QueryParams()
        params.fields = []
        params.limit = 0
        resp = await LUBESInfra.get_all(params, resp_type="plain")
        return resp
    except Exception as e:
        print(f"Error in get_all_lubes_infra': {e}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})


# Action update_lubes_data
@router.post('/update_lubes_data', tags=['LUBESInfra'])
async def lubesinfra_update_lubes_data(data: Lubesinfra_Update_Lubes_DataParams):
    try:
        lubes_data = data.lubes_data
        q = f"id='{lubes_data.unique_id}'"
        existing = await LUBESInfra.get_all(urdhva_base.QueryParams(q=q, limit=1), resp_type="plain")
        if existing["data"]:
            lubes_data = lubes_data.dict()
            lubes_data["id"] = existing["data"][0].get("id")
        else:
            return {"status": False, "message": f"No record found for ID {lubes_data.unique_id}"}

        await LUBESInfra(**lubes_data).modify()
        return {"status": True, "message": "LUBES Data Updated Successfully"}

    except Exception as e:
        print("Error in update_lubes_data:", str(e))
        traceback.print_exc()
        return {"status": False, "message": "An error occurred while updating LUBES data", "error": str(e)}


# Action add_lubes_data
@router.post('/add_lubes_data', tags=['LUBESInfra'])
async def lubesinfra_add_lubes_data(data: Lubesinfra_Add_Lubes_DataParams):
    try:
        lubes_data = data.lubes_data.dict()
        lubes_data["id"] = None
        await LUBESInfra(**lubes_data).create()
        await HistoricLUBESInfra(**lubes_data).create()
        return {"status": True, "message": "LUBES Data Created Successfully"}
    except Exception as e:
        print("Error in add_lubes_data:", str(e))
        traceback.print_exc()
        return {"status": False, "message": "An error occurred while creating LUBES data", "error": str(e)}
