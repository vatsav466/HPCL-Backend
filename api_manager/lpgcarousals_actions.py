import urdhva_base
import hpcl_ceg_model
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/lpgcarousals')


# Action create_carousal
@router.post('/create_carousal', tags=['LpgCarousals'])
async def lpgcarousals_create_carousal(data: Lpgcarousals_Create_CarousalParams):
    try:
        query = f"sap_id={data.sap_id} and carousal_id={data.carousal_id}"
        existing = await hpcl_ceg_model.LpgCarousals.get_all(urdhva_base.QueryParams(q=query), resp_type="plain")
        if existing.get("data"):
            return {
                "status": False,
                "message": f"Carousal {data.carousal_id} already exists for SAP ID {data.sap_id}",
                "data": None
            }

        resp = await hpcl_ceg_model.LpgCarousalsCreate(**data.__dict__).create()
        return {
            "status": True,
            "message": "Carousal created successfully",
            "data": resp
        }

    except Exception as e:
        return {
            "status": False,
            "message": str(e),
            "data": None
        }


# Action update_carousal
@router.post('/update_carousal', tags=['LpgCarousals'])
async def lpgcarousals_update_carousal(data: Lpgcarousals_Update_CarousalParams):
    try:
        existing = await hpcl_ceg_model.LpgCarousals.get_all(urdhva_base.QueryParams(q=f"sap_id={data.sap_id} and carousal_id={data.carousal_id}"), resp_type="plain")
        if not existing.get("data"):
            return {
                "status": False,
                "message": "Carousal not found",
                "data": None
            }

        record = existing["data"][0]
        for key, value in data.__dict__.items():
            if value is not None:
                record[key] = value

        resp = await hpcl_ceg_model.LpgCarousals(**record).modify()

        return {
            "status": True,
            "message": "Carousal updated successfully",
            "data": resp
        }

    except Exception as e:
        return {
            "status": False,
            "message": str(e),
            "data": None
        }

# Action delete_carousal
@router.post('/delete_carousal', tags=['LpgCarousals'])
async def lpgcarousals_delete_carousal(data: Lpgcarousals_Delete_CarousalParams):
    try:
        resp = await hpcl_ceg_model.LpgCarousals.get_all(urdhva_base.QueryParams(q=f"sap_id={data.sap_id} and carousal_id={data.carousal_id}"), resp_type="plain")
        if not resp["data"]:
            return {
                "status": False,
                "message": "Carousal not found",
                "data": None
            }

        await hpcl_ceg_model.LpgCarousals.delete(resp["data"][0]["id"])
        return {
            "status": True,
            "message": "Carousal deleted successfully",
            "data": None
        }

    except Exception as e:
        return {
            "status": False,
            "message": str(e),
            "data": None
        }
