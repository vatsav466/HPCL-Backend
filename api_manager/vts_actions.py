import urdhva_base
from hpcl_ceg_model import Alerts, Vts_Alert_ManagerParams
import fastapi
import polars as pl
from datetime import datetime
from dateutil.relativedelta import relativedelta

router = fastapi.APIRouter(prefix='/vts')


# Action alert_manager
@router.post('/alert_manager', tags=['VTS'])
async def vts_alert_manager(data: Vts_Alert_ManagerParams):
    query = f"alert_section='VTS' AND alert_status='Open'"
    conditions = []
    for rec in data.filters:
        if "DATE" in rec.key:
            start = rec.value.split(",")[0]
            end = (datetime.strptime(rec.value.split(",")[-1], "%Y-%m-%d") + relativedelta(days=1)).strftime("%Y-%m-%d")
            conditions.append(f"created_at BETWEEN '{start}' AND '{end}' ")
            query = query.split("WHERE")[0].split("where")[0]
            continue
        rec.value = rec.value.split(",")
        # Now handle other cases
        if isinstance(rec.value, str):
            condition = f"{rec.key} = '{rec.value}'"
        else:
            if len(rec.value) == 1:
                condition = f"{rec.key} = '{rec.value[0]}'"
            else:
                condition = f"{rec.key} in {tuple(rec.value)}"
        conditions.append(condition)
    if conditions:
        query += ' AND '
        query  += ' AND '.join(conditions)
    alert_data = await Alerts.get_all(
        urdhva_base.queryparams.QueryParams(
            q=query, limit=0
            ), resp_type='plain')
    
    required_columns =  [
            "bu", "tt_number", "sap_id", "location_name", "severity","zone",
            "instance_level", "instance_status", "violation_type",
            "maker", "checker", "actual_trip_end_date", "novex_alert_created_date",
            "vehicle_blocked_start_date", "vehicle_blocked_end_date","alert_id"
        ]
    if alert_data["data"]:
        alert_data = alert_data["data"]
        df = pl.DataFrame(alert_data)
        df = df.rename(
            {
                "unique_id": "alert_id", "interlock_name": "instance_level", 
                "vehicle_number": "tt_number", "device_id": "instance_status", 
                "assigned_user_roles": "maker", "last_escalated_to": "checker", 
                "external_timestamp": "actual_trip_end_date", "created_at": "novex_alert_created_date"
            }
        )
        df = df.select(required_columns)
        alert_data = df.to_dicts()
    return {"status": True, "message": "success", "data": alert_data}