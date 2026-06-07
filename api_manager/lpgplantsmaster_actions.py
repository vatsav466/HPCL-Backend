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


# Action plant_details
@router.post('/plant_details', tags=['LpgPlantsMaster'])
async def lpgplantsmaster_plant_details(data: Lpgplantsmaster_Plant_DetailsParams):
    try:
        plants = await hpcl_ceg_model.LpgPlantsMaster.get_all(urdhva_base.QueryParams(), resp_type="plain")
        result = []
        for plant in plants["data"]:
            sap_id = plant["sap_id"]
            # Carousel count
            carousels = await hpcl_ceg_model.LpgCarousals.get_all(urdhva_base.QueryParams(q=f"sap_id={sap_id}"), resp_type="plain")
            # Connection Status
            connection_status = False
            try:
                status_resp = await lpgplantoperations_check_connection_status(Lpgplantoperations_Check_Connection_StatusParams(sap_id=str(sap_id)))
                connections = status_resp.get("data", {}).get("connection_status", [])
                if connections:
                    connection_status = any(x.get("status", False) for x in connections)

            except Exception:
                pass

            result.append({
                "sap_id": sap_id,
                "plant_name": plant.get("plant_name"),
                "ip_address": plant.get("ip_address"),
                "port": plant.get("port_no"),
                "username": plant.get("username"),
                "db_type": plant.get("db_type"),
                "db_name": plant.get("db_name"),
                "carousals": len(carousels["data"]),
                "status": connection_status
            })

        return {
            "status": True,
            "message": "success",
            "data": result
        }

    except Exception as e:
        return {
            "status": False,
            "message": str(e),
            "data": []
        }
