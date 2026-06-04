import urdhva_base
import hpcl_ceg_model
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/lpgplantsmaster')


# Action create_location
@router.post('/create_location', tags=['LpgPlantsMaster'])
async def lpgplantsmaster_create_location(data: Lpgplantsmaster_Create_LocationParams):
    try:
        print("Data received:", data.__dict__)
        query = f"sap_id = {data.sap_id}"

        existing = await hpcl_ceg_model.LpgPlantsMaster.get_all(urdhva_base.QueryParams(q=query), resp_type="plain")
        if existing.get("data"):
            return {
                "status": False,
                "message": f"Location with SAP ID {data.sap_id} already exists",
                "data": None
            }
        location = await hpcl_ceg_model.LocationMaster.get_all(urdhva_base.QueryParams(q=f"sap_id='{data.sap_id}' and bu='LPG'"), resp_type="plain")
        if not location.get("data"):
            return {
                "status": False,
                "message": f"SAP ID {data.sap_id} not found in Location Master",
                "data": None
            }

        loc = location["data"][0]
        data_dict = data.__dict__
        data_dict["plant_name"] = loc["name"]   
        data_dict["region"] = loc["region"]
        data_dict["zone"] = loc["zone"]

        resp = await hpcl_ceg_model.LpgPlantsMasterCreate(**data_dict).create()
        print("Response from model:", resp)
        return {"status": True, "message": "Location created successfully", "data": resp}
    except Exception as e:
        return {
            "status": False,
            "message": str(e),
            "data": None
        }


# Action update_location
@router.post('/update_location', tags=['LpgPlantsMaster'])
async def lpgplantsmaster_update_location(data: Lpgplantsmaster_Update_LocationParams):
    try:
        query = f"sap_id = {data.sap_id}"
        existing = await hpcl_ceg_model.LpgPlantsMaster.get_all(urdhva_base.QueryParams(q=query), resp_type="plain")
        if not existing.get("data"):
            return {
                "status": False,
                "message": f"Location with SAP ID {data.sap_id} does not exist",
                "data": None
            }

        record = existing["data"][0]
        for key, value in data.__dict__.items():
            if value is not None:
                record[key] = value

        resp = await hpcl_ceg_model.LpgPlantsMaster(**record).modify()
        return {
            "status": True,
            "message": "Location updated successfully",
            "data": resp
        }

    except Exception as e:
        return {
            "status": False,
            "message": str(e),
            "data": None
        }

# Action delete_location
@router.post('/delete_location', tags=['LpgPlantsMaster'])
async def lpgplantsmaster_delete_location(data: Lpgplantsmaster_Delete_LocationParams):
    try:
        resp = await hpcl_ceg_model.LpgPlantsMaster.get_all(urdhva_base.QueryParams(q=f"sap_id={data.sap_id}"), resp_type="plain")
        if not resp["data"]:
            return {"status": False, "message": "Location not found", "data": None}

        await hpcl_ceg_model.LpgPlantsMaster.delete(resp["data"][0]["id"])

        return {"status": True, "message": "Location deleted successfully", "data": None}

    except Exception as e:
        return {"status": False, "message": str(e), "data": None}
