import polars as pl
import urdhva_base
from datetime import datetime
from hpcl_ceg_model import Alerts, HostMFMFactor 
import decimal
from orchestrator.dbconnector.widget_actions.vts_analytics import  download_streaming_data




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
        "zone",
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
            df.group_by(["zone", "location_name"])
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
                "zone",
                "alert_status",
                "interlock_name",
                "location_name",
                "created_at",
                "ageing_days"
            ])
            .sort("ageing_days", descending=True)
            .to_dicts()
        )

    if not data.location_name and data.alert_severity == "Critical":

        base_df = (
            df.group_by(["zone", "location_name", "interlock_name"])
            .agg(pl.len().alias("count"))
        )

        totals_df = (
            base_df.group_by(["zone", "location_name"])
                .agg(pl.sum("count").alias("total_critical"))
                .sort("total_critical", descending=True)
                .head(10)  
        )

        result_df = (
            totals_df.join(base_df, on=["zone", "location_name"])
                    .group_by(["zone", "location_name"])
                    .agg([
                        pl.first("total_critical"),
                        pl.struct(["interlock_name", "count"]).alias("interlocks")
                    ])
                    .sort("total_critical", descending=True)
        )

        return result_df.to_dicts()

async def critical_alerts_by_equipment(data):
    alert_query = """
        alert_section = 'TAS'
        AND severity = 'Critical'
    """    
    
    # Add date filter only if both dates are provided, not empty, and not "string"
    if (data.start_date and data.end_date and 
        data.start_date.strip() and data.end_date.strip() and
        data.start_date.lower() != "string" and data.end_date.lower() != "string"):
        alert_query += f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
    
    if data.equipment_type:
        alert_query += f" AND equipment_type = '{data.equipment_type}'"

    print("FINAL alert_query >>>", alert_query)

    alert_params = urdhva_base.queryparams.QueryParams(
        q=alert_query
    )
    alert_params.limit = 0
    alert_params.fields = [
        "equipment_type"
    ]
    
    # Check if location_name is NOT "false" (string comparison)
    if data.location_name and data.location_name.lower() != "false":
        alert_params.fields.append("location_name")

    alerts_resp = await Alerts.get_all(alert_params, resp_type="plain")
    alert_data = alerts_resp.get("data", [])
    
    print(f"Total records fetched: {len(alert_data)}")  

    if not alert_data:
        return []

    alerts_df = pl.DataFrame(alert_data)
    
    if alerts_df.is_empty():
        return []
    
    # Check if location_name is provided and NOT "false"
    if data.location_name and data.location_name.lower() != "false":
        critical_alerts_df = (
            alerts_df
            .group_by(["location_name", "equipment_type"])
            .agg(pl.len().alias("critical_count"))
            .sort(["location_name", "critical_count"], descending=[False, True])
        )
    else:
        # location_name is "false" or not provided - group by equipment_type only
        critical_alerts_df = (
            alerts_df
            .group_by(["equipment_type"])
            .agg(pl.len().alias("critical_count"))
            .sort(["critical_count"], descending=[True])
        )
    
    print(f"Grouped results:\n{critical_alerts_df}")  

    return critical_alerts_df.to_dicts()

async def tas_alerts_exception_report(data):
    alert_query = "alert_section = 'TAS'"

    alert_params = urdhva_base.queryparams.QueryParams(q=alert_query)
    alert_params.limit = 0

    alerts_resp = await Alerts.get_all(alert_params, resp_type="plain")
    alert_data = alerts_resp.get("data", [])

    if not alert_data:
        return []

    df = pl.DataFrame(alert_data)

    print("Original Polars DataFrame:")
    print(df)

    # Fetch host_mfm_factor data
    mfm_params = urdhva_base.queryparams.QueryParams()
    mfm_params.limit = 0
    mfm_resp = await HostMFMFactor.get_all(mfm_params, resp_type="plain")
    mfm_data = mfm_resp.get("data", [])
    
    # Convert any Decimal types to float before creating DataFrame
    if mfm_data:
        for row in mfm_data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
    
    # Handle empty data case
    if not mfm_data:
        mfm_df = pl.DataFrame()
        valid_sap_ids = set()
    else:
        mfm_df = pl.DataFrame(mfm_data)
        
        # Get sap_ids where last_k_factor IS NOT NULL
        valid_sap_ids = set()
        if not mfm_df.is_empty() and "sap_id" in mfm_df.columns and "last_k_factor" in mfm_df.columns:
            valid_sap_ids = set(
                mfm_df.filter(pl.col("last_k_factor").is_not_null())
                .select("sap_id")
                .to_series()
                .to_list()
            )

    print(f"\nValid SAP IDs with last_k_factor: {valid_sap_ids}")

    # Filter out MFM K Factor Change alerts where sap_id doesn't have last_k_factor
    df = df.with_columns(
        pl.when(
            (pl.col("interlock_name").str.to_lowercase().str.replace_all(" ", "") == "mfmkfactorchange") &
            (~pl.col("sap_id").is_in(valid_sap_ids))
        )
        .then(pl.lit(True))
        .otherwise(pl.lit(False))
        .alias("exclude_from_count")
    )

    # Filter out excluded rows
    df = df.filter(~pl.col("exclude_from_count"))

    # Normalize interlock_name: convert to lowercase and remove spaces for matching
    df = df.with_columns(
        pl.col("interlock_name").str.to_lowercase().str.replace_all(" ", "").alias("interlock_name_normalized")
    )

    # Define the interlock names you want as columns (original format)
    interlock_columns = [
        "Bay reassignment",
        "Unauthorized flow_BCU",
        "BCU vs MFM totalizer mismatch alarm",
        "Cancel TT Reported",
        "Unauthorized Flow Alarm Blend_BCU",
        "MFM K Factor Change",
        "Sick TT Reported",
        "BCU Local Loading",
        "K Factor Change_BCU",
        "K Factor Change Blend_BCU"
    ]

    # Create normalized versions for matching
    interlock_normalized = {
        col.lower().replace(" ", ""): col for col in interlock_columns
    }

    print("\nNormalized mapping:")
    print(interlock_normalized)

    # Map the normalized names back to original names
    df = df.with_columns(
        pl.col("interlock_name_normalized").replace(interlock_normalized, default=pl.col("interlock_name")).alias(
            "interlock_name_mapped")
    )

    print("\nDataFrame with normalized and mapped columns:")
    print(df.select(["location_name", "interlock_name", "interlock_name_normalized", "interlock_name_mapped"]))

    # Create a pivot table counting occurrences of each interlock_name per location_name
    pivot_df = df.group_by(["location_name", "interlock_name_mapped"]).agg(
        pl.len().alias("count")
    ).pivot(
        values="count",
        index="location_name",
        columns="interlock_name_mapped",
        aggregate_function="sum"
    )

    # Ensure all required columns exist, fill missing ones with 0
    for col in interlock_columns:
        if col not in pivot_df.columns:
            pivot_df = pivot_df.with_columns(pl.lit(0).alias(col))

    # Reorder columns to match the desired order
    column_order = ["location_name"] + interlock_columns
    pivot_df = pivot_df.select([col for col in column_order if col in pivot_df.columns])

    # Fill null values with 0
    pivot_df = pivot_df.fill_null(0)

    # Rename location_name to Location for final output
    pivot_df = pivot_df.rename({"location_name": "Location"})
    pivot_df = pivot_df.filter(pl.col("Location").is_not_null() & (pl.col("Location") != ""))
    pivot_df = pivot_df.sort("Location")

    print("\nPivot Table (Location-wise Interlock Counts):")
    print(pivot_df)
    
    # Check if download is requested (handle both string "true" and boolean True)
    if data.download and str(data.download).lower() == "true":
        return await download_streaming_data(pivot_df, filename="exception_report")

    return pivot_df.to_dicts()

AnalyticsModelMapping = {
    "Top Repeated Alerts": top_repeat_alerts,
    "Tas Severity Summary": tas_severity_summary,
    "Location Alert Critical": location_alert_critical,
    "Critical Alerts By Equipment":critical_alerts_by_equipment,
    "Tas Alerts Exception Report":tas_alerts_exception_report
}


async def tas_analytics_action(data):
    analytical_model = data.analytical_model

    if not analytical_model or analytical_model not in AnalyticsModelMapping:
        return {
            "status": False,
            "message": "Invalid Inputs"
        }
    return await AnalyticsModelMapping[analytical_model](data)