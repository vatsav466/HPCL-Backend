import polars as pl
import urdhva_base
from datetime import datetime
from hpcl_ceg_model import Alerts

async def top_repeat_alerts(data):

    alert_query = """
        alert_section = 'TAS'
        AND interlock_name NOT IN ('BCU Permissive Off','BCU Permissive Off_Fail')
    """


    alert_query += (
        f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
    )


    if data.alert_status:
        alert_query += f" AND alert_status = '{data.alert_status}'"

    if data.location_name:
        alert_query += f" AND location_name = '{data.location_name}'"

    if data.interlock_name:
        alert_query += f" AND interlock_name = '{data.interlock_name}'"

    print("FINAL alert_query >>>", alert_query)

    alert_params = urdhva_base.queryparams.QueryParams(
        q=alert_query,
        limit=0
    )

    # Fields needed for both cases
    alert_params.fields = [
        "unique_id",
        "alert_status",
        "interlock_name",
        "location_name",
        "created_at"
    ]

    alerts_resp = await Alerts.get_all(alert_params, resp_type="plain")
    alert_data = alerts_resp.get("data", [])

    if not alert_data:
        return []

    df = pl.DataFrame(alert_data)
 
    # CASE 2: INTERLOCK SELECTED → DETAIL LIST
    
    if data.interlock_name:

        now = datetime.utcnow()

        detail_df = (
            df
            .with_columns([
                # Remove microseconds
                pl.col("created_at")
                  .dt.strftime("%Y-%m-%dT%H:%M:%S")
                  .alias("created_at"),

                # Ageing in days
                (
                    (pl.lit(now) - pl.col("created_at"))
                    .dt.total_days()
                    .cast(pl.Int64)
                ).alias("ageing_days")
            ])
            .select([
                "unique_id",
                "alert_status",      
                "interlock_name",
                "location_name",
                "created_at",
                "ageing_days"
            ])
            .sort("ageing_days", descending=True)
        )

        return detail_df.to_dicts()

    # CASE 1: NO INTERLOCK → TOP 5 REPEATED

    top_alarms_df = (
        df
        .group_by("interlock_name")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
        .head(5)
    )

    return top_alarms_df.to_dicts()

async def tas_severity_summary(data):

    alert_query = """
        alert_section = 'TAS'
        AND severity = 'Critical'
    """

    alert_query += (
        f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
    )

    if data.alert_status:
        alert_query += f" AND alert_status = '{data.alert_status}'"


    if data.zone:
        alert_query += f" AND zone = '{data.zone}'"


    if data.location_name:
        alert_query += f" AND location_name = '{data.location_name}'"

    print("FINAL alert_query >>>", alert_query)

    alert_params = urdhva_base.queryparams.QueryParams(
        q=alert_query,
        limit=0
    )

    alert_params.fields = [
        "zone",
        "location_name",
        "severity",
        "interlock_name",
        "equipment_name",
        "created_at"
    ]

    alerts_resp = await Alerts.get_all(alert_params, resp_type="plain")
    alert_data = alerts_resp.get("data", [])

    if not alert_data:
        return []

    df = pl.DataFrame(alert_data)

    # CASE 2: location_name specified → DETAIL VIEW
    
    if data.location_name:
        detail_df = (
            df
            .with_columns(
                pl.col("created_at")
                .dt.strftime("%Y-%m-%dT%H:%M:%S")
                .alias("created_at")
            )
            .select([
                "interlock_name",
                "equipment_name",
                "created_at"
            ])
            .sort("created_at", descending=True)
        )

        return detail_df.to_dicts()

    # CASE 1: SUMMARY VIEW

    summary_df = (
        df.group_by(["zone", "location_name"])
        .agg([
            pl.len().alias("critical_count"),
            (
                pl.when(
                    pl.col("interlock_name")
                      .str.contains("(?i)under maintenance")
                )
                .then(1)
                .otherwise(0)
                .sum()
                .alias("equipment_under_maintenance_count")
            )
        ])
        .sort("critical_count", descending=True)
    )

    return summary_df.to_dicts()

async def location_alert_critical(data):

    alert_query = """
        alert_section = 'TAS'
        AND severity = 'Critical'
    """

    alert_query += (
        f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
    )

    if data.zone:
        alert_query += f" AND zone = '{data.zone}'"

    if data.alert_status:
        alert_query += f" AND alert_status = '{data.alert_status}'"

    if data.location_name:
        alert_query += f" AND location_name = '{data.location_name}'"

    print("FINAL alert_query >>>", alert_query)

    # FETCH DATA
    params = urdhva_base.queryparams.QueryParams(q=alert_query, limit=0)
    params.fields = [
        "unique_id",
        "alert_status",
        "interlock_name",
        "location_name",
        "created_at"
    ]

    resp = await Alerts.get_all(params, resp_type="plain")
    rows = resp.get("data", [])

    if not rows:
        return []

    df = pl.DataFrame(rows)
    # CASE 1
    # No location
    # → Top 5 locations (TOTAL critical count)
    if not data.location_name and not data.alert_severity:

        return (
            df.group_by("location_name")
              .agg(pl.len().alias("critical_count"))
              .sort("critical_count", descending=True)
              .head(5)
              .to_dicts()
        )

    # CASE 2
    # Location selected
    # → ALL critical alerts with ageing
    if data.location_name and not data.alert_severity:

        now = datetime.utcnow()

        return (
            df.with_columns([
                pl.col("created_at")
                  .dt.strftime("%Y-%m-%dT%H:%M:%S")
                  .alias("created_at"),
                (
                    (pl.lit(now) - pl.col("created_at"))
                    .dt.total_days()
                    .cast(pl.Int64)
                ).alias("ageing_days")
            ])
            .select([
                "unique_id",
                "alert_status",
                "interlock_name",
                "location_name",
                "created_at",
                "ageing_days"
            ])
            .sort("ageing_days", descending=True)
            .to_dicts()
        )
    # CASE 3
    # No location + severity key present
    # → Top 10 (location + interlock) counts
    if not data.location_name and data.alert_severity == "Critical":

        return (
            df.group_by(["location_name", "interlock_name"])
              .agg(pl.len().alias("count"))
              .sort("count", descending=True)
              .head(10)
              .to_dicts()
        )

AnalyticsModelMapping = {
    "Top Repeated Alerts": top_repeat_alerts,
    "Tas Severity Summary": tas_severity_summary,
    "Location Alert Critical": location_alert_critical
}


async def tas_analytics_action(data):
    analytical_model = data.analytical_model

    if not analytical_model or analytical_model not in AnalyticsModelMapping:
        return {
            "status": False,
            "message": "Invalid Inputs"
        }
    return await AnalyticsModelMapping[analytical_model](data)