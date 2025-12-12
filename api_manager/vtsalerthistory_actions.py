from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi

router = fastapi.APIRouter(prefix='/vtsalerthistory')


logger = urdhva_base.logger.Logger.getInstance("api_manager")


INTERLOCK_SUBSTRING_MAPPING = {
    "RouteDeviation": "route_deviation_count",
    "PowerDisconnect": "main_supply_removel_count",
    "Continuous Driving": "countinuous_driving_count",
    "Unauthorized Stoppage": "stoppage_violations_count",
    "device Tampering": "device_tampering_count",
    "VTS offline" : "device_offline_count",
    "VTS Offline": "device_offline_count",
    "Night Driving": "night_driving_count",
    "Speed Violation": "speed_violation_count",
    "NoHalt zone": "no_halt_zone_count",
}


# Action vts_alerts_analytics
@router.post('/vts_alerts_analytics', tags=['VtsAlertHistory'])
async def vtsalerthistory_vts_alerts_analytics(data: Vtsalerthistory_Vts_Alerts_AnalyticsParams):
    """
    Fetch VTS alert data violations based on alert_id 
    """
    try:
        params = urdhva_base.queryparams.QueryParams()
        params.q = f"alert_id='{data.alert_id}'"
        resp = await VtsAlertHistory.get_all(params=params, resp_type="plain")
        resp = resp['data']

        if data.interlock_name:
            column_name = None
            interlock = data.interlock_name.lower()
            for key, value in INTERLOCK_SUBSTRING_MAPPING.items():
                if key.lower() in interlock:
                    column_name = value
                    break
            
            if not column_name:
                 return {"status": "failure", "message": "Invalid interlock_name"}
            
            result = []
            for r in resp:
                result.append({
                        "vendor_id": r.get("vendor_id"),
                        "truck_number": r.get("tl_number"),
                        "invoice_number": r.get("invoice_number"),
                        "vts_start_datetime": r.get("vts_start_datetime"),
                        "vts_end_datetime": r.get("vts_end_datetime"),
                        column_name: r.get(column_name)
                })
                        
            return {"status": "success", "message":"violations counts", "data": result}

    except Exception as e:
        logger.error(f"Error in vtsalerthistory_vts_alerts_analytics: {e}")
        return {"status": "failure", "message": str(e)}

