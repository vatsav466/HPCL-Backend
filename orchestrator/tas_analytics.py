import polars as pl
import urdhva_base
from datetime import datetime
from hpcl_ceg_model import Alerts, HostMFMFactor 
from hpcl_ceg_model import HostBayReAssignment, HostLocalLoadedTts, HostCancelledTts
import json 
import decimal
from orchestrator.dbconnector.widget_actions.vts_analytics import  download_streaming_data
from datetime import datetime, timedelta
import re
from utilities.analog_data_mapping import Maintenance, Fault, Normal
from orchestrator.tas_queries import (
    ESD_QUERIES, ESD_FIELDS, ESD_CATEGORIES,
    VFT_QUERIES, VFT_FIELDS, VFT_CATEGORIES,
    RADAR_QUERIES, RADAR_FIELDS, RADAR_CATEGORIES,
    BCU_QUERIES, BCU_FIELDS, BCU_INTERLOCKS, BCU_ALARM_DETAILS_LIMIT,
    FIRE_EFFECT_QUERIES, FIRE_EFFECT_FIELDS, FIRE_EFFECT_INTERLOCKS,
    FAIL_PATTERNS,ESD_DEVICE_ANALYSIS_CONFIG,HOST_LOCAL_LOADED_TTS_QUERIES,
    HOST_LOCAL_LOADED_TTS_FIELDS,TRUCK_TYPE_PATTERNS,PATTERN_ANALYSIS_CONFIG,BAY_REASSIGNMENT_CONFIG,
    build_complete_query, format_sap_ids_for_query, format_interlocks_for_query)


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

    if data.alert_severity:
        if isinstance(data.alert_severity, list):
            clean_severity = [s for s in data.alert_severity if s]

            if clean_severity:
                severity_vals = ", ".join(f"'{s}'" for s in clean_severity)
                alert_query += f" AND severity IN ({severity_vals})"
        else:
            if data.alert_severity.strip():
                alert_query += f" AND severity = '{data.alert_severity}'"

    print("FINAL alert_query >>>", alert_query)

    alert_params = urdhva_base.queryparams.QueryParams(
        q=alert_query,
        limit=0
    )

    # Fields needed for both cases
    alert_params.fields = [
        "unique_id",
        "alert_status",
        "severity",
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
                "severity",  
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

    # -----------------------------
    # Build alert query
    # -----------------------------
    alert_query = "alert_section = 'TAS'"

    alert_query += (
        f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
    )

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
        "zone", "location_name",
        "severity", "interlock_name", "equipment_name", "created_at" ]

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

    # Extract interlock names
    maintenance_terms = [
        i["interlock_name"].lower() for i in Maintenance if i.get("interlock_name")]

    fault_terms = [
        i["interlock_name"].lower() for i in Fault if i.get("interlock_name")]

    normal_terms = [
        i["interlock_name"].lower() for i in Normal if i.get("interlock_name")]


    # Categorize each alert
    df = df.with_columns(pl
        .when(
            pl.any_horizontal([ pl.col("interlock_name").str.to_lowercase().str.contains(t)
                for t in maintenance_terms])) .then(pl.lit("maintenance"))

        .when(
            pl.any_horizontal([
                pl.col("interlock_name").str.to_lowercase().str.contains(t)
                for t in fault_terms])) .then(pl.lit("fault"))
        
        .when(
            pl.any_horizontal([
                pl.col("interlock_name").str.to_lowercase().str.contains(t)
                for t in normal_terms])) .then(pl.lit("normal")) 

        .otherwise(pl.lit("other")) .alias("interlock_category"))
    
    # Aggregate summary counts
    summary_df = (
        df.group_by(["zone", "location_name"]) .agg([
            (pl.col("interlock_category") == "maintenance"). cast(pl.Int64).sum().alias("under_maintenance_count"),
            (pl.col("interlock_category") == "fault").cast(pl.Int64).sum().alias("fault_count")

        ]))

    return summary_df.to_dicts()

async def location_alert_critical(data):

    zone = data.zone or None
    location_name = data.location_name or None
    alert_status = data.alert_status or None
    severity_filter = data.alert_severity or []

    is_download = str(getattr(data, "download", "")).lower() == "true"

    
    # 2. BASE QUERY
    alert_query = "alert_section = 'TAS'"
    alert_query += (
        f" AND created_at::date BETWEEN "
        f"'{data.start_date}' AND '{data.end_date}'"
    )

    if zone:
        alert_query += f" AND zone = '{zone}'"
        

    if alert_status:
        alert_query += f" AND alert_status = '{alert_status}'"

    if location_name:
        alert_query += f" AND location_name = '{location_name}'"

    print("FINAL alert_query >>>", alert_query)
    #FETCH DATA
    params = urdhva_base.queryparams.QueryParams(q=alert_query, limit=0)
    params.fields = [
        "unique_id",
        "zone",
        "alert_status",
        "severity",
        "interlock_name",
        "location_name",
        "created_at"
    ]

    resp = await Alerts.get_all(params, resp_type="plain")
    rows = resp.get("data", [])

    if not rows:
        return []
    df = pl.DataFrame(rows)

    # 4. SEVERITY FILTER
    if isinstance(severity_filter, list):
        severity_filter = [
            s.strip().lower()
            for s in severity_filter
            if s and isinstance(s, str)
        ]

    if severity_filter:
        df = df.filter(
            pl.col("severity")
            .str.to_lowercase()
            .is_in(severity_filter)
        )


    # 5. DOWNLOAD MODE → RAW ALERTS (ALL OR ONE LOCATION)
    if is_download:
        now = datetime.utcnow()

        download_df = (
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
                "severity",
                "alert_status",
                "interlock_name",
                "location_name",
                "created_at",
                "ageing_days"
            ])
            .sort("ageing_days", descending=True)
        )

        print("DOWNLOAD RAW ROW COUNT >>>", download_df.height)

        return {
            "download": True,
            "download_type": "raw_alerts",
            "data": download_df.to_dicts()
        }

    # 6. DRILL-DOWN (LOCATION SELECTED, NON-DOWNLOAD)
    if location_name:
        now = datetime.utcnow()

        result = (
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
                "severity",
                "alert_status",
                "interlock_name",
                "location_name",
                "created_at",
                "ageing_days"
            ])
            .sort("ageing_days", descending=True)
        )

        print("DETAIL VIEW ROW COUNT >>>", result.height)
        return result.to_dicts()

    # 7. CLEAN INVALID LOCATIONS
    df = df.filter(
        (pl.col("location_name").is_not_null()) &
        (pl.col("location_name").str.strip_chars() != "")
    )

    # 8. INTERLOCK + SEVERITY COUNTS
    base_df = (
        df.group_by([
            "zone",
            "location_name",
            "interlock_name",
            "severity"
        ])
        .agg(pl.len().alias("count"))
    )

    # 9. TOTAL ALERTS PER LOCATION
    totals_df = (
        base_df.group_by(["zone", "location_name"])
        .agg(pl.sum("count").alias("total_alerts"))
    )

    # 10. NORMAL SUMMARY RESPONSE (DASHBOARD)
    result_df = (
        totals_df
        .join(base_df, on=["zone", "location_name"])
        .group_by(["zone", "location_name"])
        .agg([
            pl.first("total_alerts").alias("total_alerts"),
            pl.struct(
                ["interlock_name", "severity", "count"]
            ).alias("interlocks")
        ])
        .sort("total_alerts", descending=True)
    )

    print("TOTAL LOCATIONS RETURNED >>>", result_df.height)

    return result_df.to_dicts()


async def critical_alerts_by_equipment(data):
    alert_query = """
        alert_section = 'TAS'
        AND severity = 'Critical'
    """

    # Add alert_status filter based on payload
    if data.alert_status and data.alert_status.strip():
        alert_query += f" AND alert_status = '{data.alert_status}'"

    # Add date filter only if both dates are provided, not empty, and not "string"
    if (
        data.start_date and data.end_date
        and data.start_date.strip() and data.end_date.strip()
        and data.start_date.lower() != "string"
        and data.end_date.lower() != "string"
    ):
        alert_query += (
            f" AND created_at::date BETWEEN "
            f"'{data.start_date}' AND '{data.end_date}'"
        )

    # Add location_name filter if provided (and not empty/not "true")
    if data.location_name and data.location_name.strip() and data.location_name.lower() != "true":
        alert_query += f" AND location_name = '{data.location_name}'"

    if data.zone and data.zone.strip():
        alert_query += f" AND zone = '{data.zone}'"

    # Add equipment_type filter if provided
    if data.equipment_type:
        alert_query += f" AND equipment_type = '{data.equipment_type}'"

    alert_params = urdhva_base.queryparams.QueryParams(q=alert_query)
    alert_params.limit = 0

    alert_params.fields = ["equipment_type","alert_status", "zone"]

    if (
        (data.location_name and data.location_name.lower() == "true")
        or data.equipment_type
    ):
        alert_params.fields.append("location_name")

    alerts_resp = await Alerts.get_all(alert_params, resp_type="plain")
    alert_data = alerts_resp.get("data", [])

    if not alert_data:
        return []

    alerts_df = pl.DataFrame(alert_data)
    
    if alerts_df.is_empty():
        return []
    
    # Filter out rows where equipment_type is null or empty
    alerts_df = alerts_df.filter(
        (pl.col("equipment_type").is_not_null()) & 
        (pl.col("equipment_type").str.strip_chars() != "")
    )

    if alerts_df.is_empty():
        return []
    if not data.alert_status or not data.alert_status.strip():
        critical_alerts_df = (
            alerts_df
            .group_by("location_name")
            .agg([pl.when(pl.col("alert_status") == "Open")
                  .then(1).otherwise(0).sum().alias("open_critical_count"),
                pl.when(pl.col("alert_status") == "Close").then(1).otherwise(0).sum().alias("close_critical_count"),])
            .sort("open_critical_count", descending=True))

        return critical_alerts_df.to_dicts()
    if data.equipment_type and (
        not data.location_name or data.location_name.lower() != "true"
    ):
        critical_alerts_df = (
            alerts_df
            .group_by("location_name")
            .agg(pl.len().alias("critical_count"))
            .sort("critical_count", descending=True)
        )
        return critical_alerts_df.to_dicts()
    if data.location_name and data.location_name.lower() == "true":
        critical_alerts_df = (
            alerts_df
            .group_by("location_name")
            .agg(pl.len().alias("critical_count"))
            .sort("critical_count", descending=True)
        )
    else:
        critical_alerts_df = (
            alerts_df
            .group_by("equipment_type")
            .agg(pl.len().alias("critical_count"))
            .sort("critical_count", descending=True)
        )

    return critical_alerts_df.to_dicts()

async def tas_alerts_exception_report(data):

    q = "alert_section = 'TAS'"
    if data.start_date and data.end_date and data.start_date.lower() != "string":
        q += (
            f" AND created_at >= '{data.start_date} 00:00:00'"
            f" AND created_at <  '{data.end_date} 23:59:59'"
        )

    params = urdhva_base.queryparams.QueryParams(q=q, fields=json.dumps(["location_name", "sap_id", "interlock_name","created_at", "vehicle_number", "device_name"]))
    params.limit = 0

    alerts = (await Alerts.get_all(params, resp_type="plain")).get("data", [])
    if not alerts:
        return []
    df = (pl.DataFrame(alerts)
        .with_columns([
            pl.col("vehicle_number").str.strip_chars(),
            pl.col("interlock_name")
                .str.to_lowercase()
                .str.replace_all(" ", "")
                .alias("interlock_norm"),
            pl.col("created_at").dt.date().alias("created_date")
        ])
    )
    mfm = await HostMFMFactor.get_all(
        urdhva_base.queryparams.QueryParams(limit=0),
        resp_type="plain"
    )

    valid_sap_ids = {
        r["sap_id"] for r in mfm.get("data", [])
        if r.get("last_k_factor") is not None
    }

    df = df.filter(~((pl.col("interlock_norm") == "mfmkfactorchange")& (~pl.col("sap_id").is_in(valid_sap_ids))))
    INTERLOCK_MAP = {
        "bayreassignment": "Bay reassignment",
        "unauthorizedflow_bcu": "Unauthorized flow_BCU",
        "bcuvsmfmtotalizermismatchalarm": "BCU vs MFM totalizer mismatch alarm",
        "cancelttreported": "Cancel TT Reported",
        "unauthorizedflowalarmblend_bcu": "Unauthorized Flow Alarm Blend_BCU",
        "mfmkfactorchange": "MFM K Factor Change",
        "sickttreported": "Sick TT Reported",
        "bculocalloading": "BCU Local Loading",
        "kfactorchange_bcu": "K Factor Change_BCU",
        "kfactorchangeblend_bcu": "K Factor Change Blend_BCU",
    }

    DEVICE_INTERLOCKS = {
        "MFM K Factor Change",
        "Sick TT Reported",
        "K Factor Change_BCU",
        "K Factor Change Blend_BCU",
        "Unauthorized Flow Alarm Blend_BCU",
        "Unauthorized flow_BCU",
        "BCU vs MFM totalizer mismatch alarm"
    }

    df = (df.filter(pl.col("interlock_norm").is_in(list(INTERLOCK_MAP.keys()))).with_columns(pl.col("interlock_norm").replace(INTERLOCK_MAP).alias("interlock")))
    date_q = (
        f"created_at >= '{data.start_date} 00:00:00'"
        f" AND created_at < '{data.end_date} 23:59:59'"
    )

    # ---- Bay reassignment
    bay_df = (
        pl.DataFrame(
            (await HostBayReAssignment.get_all(
                urdhva_base.queryparams.QueryParams(q=date_q, limit=0),
                resp_type="plain"
            )).get("data", [])
        )
        .with_columns(pl.col("created_at").dt.date().alias("created_date"))
        .group_by(["truck_number", "created_date"])
        .agg([
            pl.col("load_number").drop_nulls().first(),
            pl.col("assigned_bay").drop_nulls().first(),
            pl.col("reassigned_bay").drop_nulls().first(),
        ])
    )

    # ---- Local loading
    local_df = (
        pl.DataFrame(
            (await HostLocalLoadedTts.get_all(
                urdhva_base.queryparams.QueryParams(q=date_q, limit=0),
                resp_type="plain"
            )).get("data", [])
        )
        .with_columns(pl.col("created_at").dt.date().alias("created_date"))
        .group_by(["truck_number", "created_date"])
        .agg([
            pl.col("bcu_number").drop_nulls().first(),
            pl.col("loaded_qty").drop_nulls().first(),
            pl.col("recipe_name").drop_nulls().first(),
        ])
    )

    # ---- Cancel TT
    cancel_df = (
        pl.DataFrame(
            (await HostCancelledTts.get_all(
                urdhva_base.queryparams.QueryParams(q=date_q, limit=0),
                resp_type="plain"
            )).get("data", [])
        )
        .with_columns(pl.col("created_at").dt.date().alias("created_date"))
        .group_by(["truck_number", "created_date"])
        .agg([
            pl.col("load_number").drop_nulls().first(),
            pl.col("required_qty").drop_nulls().first(),
            pl.col("product_name").drop_nulls().first(),
        ])
    )
    result = []

    for loc in df.select("location_name").unique().to_series():
        loc_df = df.filter(pl.col("location_name") == loc)
        row = {"Location": loc}

        for interlock in INTERLOCK_MAP.values():
            i_df = loc_df.filter(pl.col("interlock") == interlock)
            row[interlock] = i_df.height
            details = []

            if i_df.is_empty():
                row[f"{interlock}_detail"] = []
                continue

            details = []

            # Interlock-specific details
            if interlock == "Bay reassignment":
                details.extend(
                    i_df.select(["vehicle_number", "created_date"])
                        .unique()
                        .join(
                            bay_df,
                            left_on=["vehicle_number", "created_date"],
                            right_on=["truck_number", "created_date"],
                            how="left"
                        )
                        .filter(
                            (pl.col("load_number").is_not_null()) |
                            (pl.col("assigned_bay").is_not_null()) |
                            (pl.col("reassigned_bay").is_not_null())
                        )
                        .select([
                            "vehicle_number", "created_date",
                            "load_number", "assigned_bay", "reassigned_bay"
                        ])
                        .to_dicts()
                )

            elif interlock == "BCU Local Loading":
                joined_data = (
                    i_df.select(["vehicle_number", "created_date"])
                        .unique()
                        .join(
                            local_df,
                            left_on=["vehicle_number", "created_date"],
                            right_on=["truck_number", "created_date"],
                            how="left"
                        )
                        .select([
                            "vehicle_number", "created_date",
                            "bcu_number", "loaded_qty", "recipe_name"
                        ])
                )
                
                # Add records with at least one non-null value
                non_null_records = joined_data.filter(
                    (pl.col("bcu_number").is_not_null()) |
                    (pl.col("loaded_qty").is_not_null()) |
                    (pl.col("recipe_name").is_not_null())
                ).to_dicts()
                
                if non_null_records:
                    details.extend(non_null_records)
                else:
                    # If all joined records are null, add vehicle count summary with null fields
                    vehicle_counts = (
                        i_df.group_by(["vehicle_number", "created_date"])
                            .agg(pl.count().alias("count"))
                            .to_dicts()
                    )
                    for vc in vehicle_counts:
                        vc["bcu_number"] = None
                        vc["loaded_qty"] = None
                        vc["recipe_name"] = None
                    details.extend(vehicle_counts)

            elif interlock == "Cancel TT Reported":
                details.extend(
                    i_df.select(["vehicle_number", "created_date"])
                        .unique()
                        .join(
                            cancel_df,
                            left_on=["vehicle_number", "created_date"],
                            right_on=["truck_number", "created_date"],
                            how="left"
                        )
                        .filter(
                            (pl.col("load_number").is_not_null()) |
                            (pl.col("required_qty").is_not_null()) |
                            (pl.col("product_name").is_not_null())
                        )
                        .select([
                            "vehicle_number", "created_date",
                            "load_number", "required_qty", "product_name"
                        ])
                        .to_dicts()
                )

            else:
                group_cols = ["vehicle_number", "created_date"]
                if interlock in DEVICE_INTERLOCKS:
                    group_cols.append("device_name")

                details.extend(
                    i_df.group_by(group_cols)
                        .agg(pl.count().alias("count"))
                        .to_dicts()
                )

            row[f"{interlock}_detail"] = details

        result.append(row)

    if str(data.download).lower() == "true":
        return await download_streaming_data(
            pl.DataFrame(result), "exception_report"
        )

    return result

async def equipment_location_wise_count(data):
    """
    Get location-wise counts with Success/Fail breakdown for specific interlocks
    Supports ESD, VFT, RADAR, BCU, and Fire Effect equipment types
    """
    
    # Determine which equipment types to process
    equipment_types = []
    
    if data.equipment_name:
        equipment_name_str = data.equipment_name.strip()
        
        # Check if it's an array-like string format like "[VFT,ESD,RADAR,BCU,Fire Effect]"
        if equipment_name_str.startswith('[') and equipment_name_str.endswith(']'):
            # Remove brackets and split by comma
            equipment_name_str = equipment_name_str.strip('[]')
            equipment_types = [eq.strip().upper() for eq in equipment_name_str.split(',') if eq.strip()]
        else:
            # Single equipment name
            equipment_types = [equipment_name_str.upper()]
    else:
        # If no equipment_name provided, process all five
        equipment_types = DEFAULT_EQUIPMENT_TYPES.copy()
    
    final_combined_result = []
    
    for equipment_type in equipment_types:
        if equipment_type == 'ESD':
            result = await process_esd_data(data)
            if result:
                final_combined_result.extend(result)
        elif equipment_type == 'VFT':
            result = await process_vft_data(data)
            if result:
                final_combined_result.extend(result)
        elif equipment_type == 'RADAR':
            result = await process_radar_data(data)
            if result:
                final_combined_result.extend(result)
        elif equipment_type == 'BCU':
            result = await process_bcu_data(data)
            if result:
                final_combined_result.extend(result)
        elif equipment_type == 'FIRE EFFECT':
            result = await process_fire_effect_data(data)
            if result:
                final_combined_result.extend(result)
    
    
    return final_combined_result


async def process_esd_data(data):
    """
    Optimized ESD equipment data processing with unique_id matching
    Logic: For each base alert, check if corresponding "_Fail" alert exists 
    within 1 minute WITH THE SAME unique_id
    """
    # Build ESD Pushbutton query
    esd_pushbutton_query = build_complete_query(
        ESD_QUERIES["pushbutton_activated"],
        data.start_date,
        data.end_date,
        data.location_name
    )
    esd_pushbutton_params = urdhva_base.queryparams.QueryParams(q=esd_pushbutton_query, limit=0)
    esd_pushbutton_params.fields = ESD_FIELDS["pushbutton_activated"]

    esd_pushbutton_resp = await Alerts.get_all(esd_pushbutton_params, resp_type="plain")
    esd_pushbutton_data = esd_pushbutton_resp.get("data", [])

    # Process ESD Pushbutton data with details
    esd_activated_details = {}
    esd_device_activations = {}  # Track activation times per device
    if len(esd_pushbutton_data) > 0:
        esd_pushbutton_df = pl.DataFrame(esd_pushbutton_data)
        
        esd_pushbutton_df = esd_pushbutton_df.with_columns(
            pl.col("created_at").dt.strftime("%Y-%m-%dT%H:%M:%S").alias("created_at")
        )
        
        for row in esd_pushbutton_df.to_dicts():
            key = (row["sap_id"], row["location_name"])
            device_name = row.get("device_name", "")
            created_at_str = row["created_at"]

            if key not in esd_activated_details:
                esd_activated_details[key] = []
                esd_device_activations[key] = {}

            esd_activated_details[key].append({
                "created_at": created_at_str,
                "device_name": device_name
            })

            # Parse activation time for device tracking
            try:
                if isinstance(row["created_at"], str):
                    activation_time = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                else:
                    activation_time = row["created_at"]

                if device_name not in esd_device_activations[key]:
                    esd_device_activations[key][device_name] = []

                esd_device_activations[key][device_name].append({
                    'time': activation_time,
                    'created_at_str': created_at_str
                })
            except Exception as e:
                print(f"Error parsing activation time: {e}")

    # Get unique locations from pushbutton data
    if not esd_pushbutton_data:
        return []
    
    unique_locations = {}
    for record in esd_pushbutton_data:
        key = (record['sap_id'], record['location_name'])
        if key not in unique_locations:
            unique_locations[key] = {
                'sap_id': record['sap_id'],
                'location_name': record['location_name']
            }
    
    sap_ids = list(set(loc['sap_id'] for loc in unique_locations.values()))
    
    # Build batch query for all interlocks using template
    sap_ids_str = format_sap_ids_for_query(sap_ids)
    
    all_interlocks_query = ESD_QUERIES["all_interlocks_template"].format(
        sap_ids=sap_ids_str
    )
    
    if (data.start_date and data.end_date and
            data.start_date.strip() and data.end_date.strip() and
            data.start_date.lower() != "string" and data.end_date.lower() != "string"):
        all_interlocks_query += f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
    
    if data.location_name and data.location_name.strip():
        all_interlocks_query += f" AND location_name = '{data.location_name}'"
    
    interlock_params = urdhva_base.queryparams.QueryParams(q=all_interlocks_query, limit=0)
    interlock_params.fields = ESD_FIELDS["interlocks"] + ["device_name"]  # Add device_name

    interlock_resp = await Alerts.get_all(interlock_params, resp_type="plain")
    all_interlock_alerts = interlock_resp.get("data", [])   
    if not all_interlock_alerts:
        result = []
        for key, details in esd_activated_details.items():
            result_item = {
                "sap_id": key[0],
                "location_name": key[1],
                "equipment_type": "ESD",
                "no_of_esd_activated": len(details),
                "esd_activated_details": details[:10]
            }
            
            # Initialize categories from configuration
            for category in ESD_CATEGORIES.keys():
                result_item[category] = [{"success": 0, "failed": 0}]
            result.append(result_item)
        return result

    # Get time window from config
    time_window_minutes = ESD_DEVICE_ANALYSIS_CONFIG.get("time_window_minutes", 3)

    # Organize alerts by unique_id and category (keeping original logic)
    alerts_by_unique_id = {}
    
    for alert in all_interlock_alerts:
        unique_id = alert['unique_id']
        sap_id = alert['sap_id']
        location_name = alert.get('location_name', '')
        interlock_name = alert.get('interlock_name', '')
        device_name = alert.get('device_name', '')

        # Determine category
        category = None
        for cat, pattern in ESD_CATEGORIES.items():
            if re.search(pattern, interlock_name):
                category = cat
                break
        
        if not category:
            continue
        
        key = (unique_id, sap_id, location_name, category)
        
        if key not in alerts_by_unique_id:
            alerts_by_unique_id[key] = []
        
        try:
            created_at = alert['created_at']
            if isinstance(created_at, str):
                alert_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            else:
                alert_time = created_at
                   
            # Check if this is a Fail alert
            is_fail = any(pattern in interlock_name for pattern in FAIL_PATTERNS)
            
            alerts_by_unique_id[key].append({
                'id': alert.get('id'),
                'time': alert_time,
                'is_fail': is_fail,
                'interlock_name': interlock_name,
                'device_name': device_name
            })
        except Exception as e:
            print(f"Error parsing ESD alert time: {e}")
    
    # Sort alerts by time for efficient searching
    for key in alerts_by_unique_id:
        alerts_by_unique_id[key].sort(key=lambda x: x['time'])
        
    # Initialize results structure
    location_results = {}
    
    for key, loc_info in unique_locations.items():
        sap_id = loc_info['sap_id']
        location_name = loc_info['location_name']
        
        alarm_details = esd_activated_details.get(key, [])
        
        location_results[key] = {
            "sap_id": sap_id,
            "location_name": location_name,
            "equipment_type": "ESD",
            "no_of_esd_activated": len(alarm_details),
            "esd_activated_details": alarm_details,
            "device_activations": esd_device_activations.get(key, {})
        }
        
        # Initialize categories from configuration
        for category in ESD_CATEGORIES.keys():
            location_results[key][category] = {"success": 0, "failed": 0}

    # Process alerts with original logic (1-minute window + unique_id matching)
    processed_base_ids = set()

    # Also track per-device category counts
    device_category_counts = {}  # {(loc_key, device_name, created_at_str): {category: {success, failed}}}

    for key, alerts in alerts_by_unique_id.items():
        unique_id, sap_id, location_name, category = key
        
        matching_key = None
        for result_key, loc_info in unique_locations.items():
            if loc_info['sap_id'] == sap_id and loc_info['location_name'] == location_name:
                matching_key = result_key
                break
        
        if not matching_key:
            continue
        
        # Separate alerts into base and fail alerts
        base_alerts = [a for a in alerts if not a['is_fail']]
        fail_alerts = [a for a in alerts if a['is_fail']]
        
        # For each base alert, check if there's a corresponding fail alert within 1 minute
        for base_alert in base_alerts:
            if base_alert['id'] in processed_base_ids:
                continue
            
            base_time = base_alert['time']
            base_device = base_alert.get('device_name', '')
            time_start = base_time
            time_end = base_time + timedelta(minutes=1)
            
            found_fail = False
            
            # Check fail alerts WITH THE SAME unique_id
            for fail_alert in fail_alerts:
                fail_time = fail_alert['time']
                
                if fail_time < time_start:
                    continue
                
                if time_start <= fail_time <= time_end:
                    found_fail = True
                    processed_base_ids.add(base_alert['id'])
                    processed_base_ids.add(fail_alert['id'])
                    break
                elif fail_time > time_end:
                    break

            # Update location-level counts
            if found_fail:
                location_results[matching_key][category]["failed"] += 1
            else:
                location_results[matching_key][category]["success"] += 1

            # Track device-level counts within time window
            device_activations = location_results[matching_key]["device_activations"].get(base_device, [])
            for activation in device_activations:
                activation_time = activation['time']
                created_at_str = activation['created_at_str']

                # Check if this alert falls within the configured time window of this device activation
                if activation_time <= base_time <= activation_time + timedelta(minutes=time_window_minutes):
                    device_key = (matching_key, base_device, created_at_str)

                    if device_key not in device_category_counts:
                        device_category_counts[device_key] = {}
                        for cat in ESD_CATEGORIES.keys():
                            device_category_counts[device_key][cat] = {"success": 0, "failed": 0}

                    if found_fail:
                        device_category_counts[device_key][category]["failed"] += 1
                    else:
                        device_category_counts[device_key][category]["success"] += 1

            if base_alert['id'] not in processed_base_ids:
                processed_base_ids.add(base_alert['id'])

        # Process any unmatched fail alerts as failures
        for fail_alert in fail_alerts:
            if fail_alert['id'] not in processed_base_ids:
                location_results[matching_key][category]["failed"] += 1

                # Also add to device-level counts if within time window
                fail_time = fail_alert['time']
                fail_device = fail_alert.get('device_name', '')

                device_activations = location_results[matching_key]["device_activations"].get(fail_device, [])
                for activation in device_activations:
                    activation_time = activation['time']
                    created_at_str = activation['created_at_str']

                    if activation_time <= fail_time <= activation_time + timedelta(minutes=time_window_minutes):
                        device_key = (matching_key, fail_device, created_at_str)

                        if device_key not in device_category_counts:
                            device_category_counts[device_key] = {}
                            for cat in ESD_CATEGORIES.keys():
                                device_category_counts[device_key][cat] = {"success": 0, "failed": 0}

                        device_category_counts[device_key][category]["failed"] += 1

                processed_base_ids.add(fail_alert['id'])

    # Build final result with enriched device details
    final_result = []

    for key, value in location_results.items():
        # Enrich device details with category counts
        enriched_details = []
        for detail in value["esd_activated_details"][:10]:  # Limit to 10
            device_name = detail["device_name"]
            created_at_str = detail["created_at"]

            device_key = (key, device_name, created_at_str)

            enriched_detail = {
                "created_at": created_at_str,
                "device_name": device_name
            }

            # Calculate total count and add category counts
            total_count = 0
            if device_key in device_category_counts:
                for category in ESD_CATEGORIES.keys():
                    counts = device_category_counts[device_key][category]
                    enriched_detail[category] = [counts]
                    total_count += counts["success"] + counts["failed"]
            else:
                # No alerts found for this device activation
                for category in ESD_CATEGORIES.keys():
                    enriched_detail[category] = [{"success": 0, "failed": 0}]

            # Add count after device_name, before categories
            enriched_detail_ordered = {
                "created_at": created_at_str,
                "device_name": device_name,
                "count": total_count
            }
            # Add all category counts
            for category in ESD_CATEGORIES.keys():
                enriched_detail_ordered[category] = enriched_detail[category]

            enriched_detail = enriched_detail_ordered

            enriched_details.append(enriched_detail)

        result_item = {
            "sap_id": value["sap_id"],
            "location_name": value["location_name"],
            "equipment_type": value["equipment_type"],
            "no_of_esd_activated": value["no_of_esd_activated"],
            "esd_activated_details": enriched_details
        }

        # Add location-level category counts
        for category in ESD_CATEGORIES.keys():
            result_item[category] = [value[category]]
        
        final_result.append(result_item)
    
    final_result = sorted(final_result, key=lambda x: (x["sap_id"], x["location_name"]))
    return final_result

async def process_vft_data(data):
    """
    Process VFT equipment data with unique_id matching
    Logic: Match base and fail alerts within 1 minute WITH THE SAME unique_id
    """
    # Build VFT HHH alarm query
    vft_hhh_query = build_complete_query(
        VFT_QUERIES["hhh_alarm"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    vft_hhh_params = urdhva_base.queryparams.QueryParams(q=vft_hhh_query, limit=0)
    vft_hhh_params.fields = VFT_FIELDS["hhh_alarm"]

    vft_hhh_resp = await Alerts.get_all(vft_hhh_params, resp_type="plain")
    vft_hhh_data = vft_hhh_resp.get("data", [])
    # Build other interlocks query
    alert_query = build_complete_query(
        VFT_QUERIES["other_interlocks"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    alert_params = urdhva_base.queryparams.QueryParams(q=alert_query, limit=0)
    alert_params.fields = VFT_FIELDS["other_interlocks"]

    alerts_resp = await Alerts.get_all(alert_params, resp_type="plain")
    alert_data = alerts_resp.get("data", [])    
    # Process VFT HHH data with details
    vft_activated_details = {}
    if len(vft_hhh_data) > 0:
        vft_hhh_df = pl.DataFrame(vft_hhh_data)
        
        vft_hhh_df = vft_hhh_df.with_columns(
            pl.col("created_at").dt.strftime("%Y-%m-%dT%H:%M:%S").alias("created_at")
        )
        
        for row in vft_hhh_df.to_dicts():
            key = (row["sap_id"], row["location_name"])
            if key not in vft_activated_details:
                vft_activated_details[key] = []
            vft_activated_details[key].append({
                "created_at": row["created_at"],
                "device_name": row.get("device_name", "")
            })
    
    if not vft_hhh_data and not alert_data:
        print("WARNING: No VFT data found!")
        return []
    
    if not alert_data and vft_hhh_data:
        result = {}
        for key, details in vft_activated_details.items():
            result[key] = {
                "sap_id": key[0],
                "location_name": key[1],
                "equipment_type": "VFT",
                "no_of_vft_activated": len(details),
                "vft_activated_details": details
            }
            
            # Initialize categories from configuration
            for category in VFT_CATEGORIES.keys():
                result[key][category] = [{"success": 0, "failed": 0}]
        
        final_result = list(result.values())
        final_result = sorted(final_result, key=lambda x: (x["sap_id"], x["location_name"]))
              
        return final_result

    # Organize alerts by unique_id and category
    alerts_by_unique_id = {}
    
    for alert in alert_data:
        unique_id = alert['unique_id']
        sap_id = alert['sap_id']
        location_name = alert.get('location_name', '')
        interlock_name = alert.get('interlock_name', '')
        
        # Determine category
        category = None
        for cat, pattern in VFT_CATEGORIES.items():
            if re.search(pattern, interlock_name):
                category = cat
                break
        
        if not category:
            continue
        
        key = (unique_id, sap_id, location_name, category)
        
        if key not in alerts_by_unique_id:
            alerts_by_unique_id[key] = []
        
        try:
            created_at = alert['created_at']
            if isinstance(created_at, str):
                alert_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            else:
                alert_time = created_at
            
            # Check if this is a Fail alert
            is_fail = "Fail" in interlock_name
            
            alerts_by_unique_id[key].append({
                'id': alert.get('id'),
                'time': alert_time,
                'is_fail': is_fail,
                'interlock_name': interlock_name
            })
        except Exception as e:
            print(f"Error parsing VFT alert time: {e}")
    
    # Sort alerts by time
    for key in alerts_by_unique_id:
        alerts_by_unique_id[key].sort(key=lambda x: x['time'])    
    # Get unique locations
    unique_locations = {}
    for alert in alert_data:
        key = (alert['sap_id'], alert['location_name'])
        if key not in unique_locations:
            unique_locations[key] = {
                'sap_id': alert['sap_id'],
                'location_name': alert['location_name']
            }
    
    # Initialize results structure
    location_results = {}
    
    for key, loc_info in unique_locations.items():
        sap_id = loc_info['sap_id']
        location_name = loc_info['location_name']
        
        alarm_details = vft_activated_details.get(key, [])
        
        location_results[key] = {
            "sap_id": sap_id,
            "location_name": location_name,
            "equipment_type": "VFT",
            "no_of_vft_activated": len(alarm_details),
            "vft_activated_details": alarm_details
        }
        
        # Initialize categories from configuration
        for category in VFT_CATEGORIES.keys():
            location_results[key][category] = {"success": 0, "failed": 0}
    
    # Process alerts with 1-minute window + unique_id matching
    processed_count = 0
    success_count = 0
    failed_count = 0
    processed_base_ids = set()
    
    for key, alerts in alerts_by_unique_id.items():
        unique_id, sap_id, location_name, category = key
        
        matching_key = (sap_id, location_name)
        
        if matching_key not in location_results:
            continue
        
        # Separate alerts into base and fail alerts
        base_alerts = [a for a in alerts if not a['is_fail']]
        fail_alerts = [a for a in alerts if a['is_fail']]
        
        # For each base alert, check if there's a corresponding fail alert within 1 minute
        for base_alert in base_alerts:
            if base_alert['id'] in processed_base_ids:
                continue
            
            base_time = base_alert['time']
            time_start = base_time
            time_end = base_time + timedelta(minutes=1)
            
            found_fail = False
            
            # Check fail alerts WITH THE SAME unique_id
            for fail_alert in fail_alerts:
                fail_time = fail_alert['time']
                
                if fail_time < time_start:
                    continue
                
                if time_start <= fail_time <= time_end:
                    found_fail = True
                    processed_base_ids.add(base_alert['id'])
                    processed_base_ids.add(fail_alert['id'])
                    break
                elif fail_time > time_end:
                    break
            
            if found_fail:
                location_results[matching_key][category]["failed"] += 1
                failed_count += 1
            else:
                location_results[matching_key][category]["success"] += 1
                success_count += 1
            
            if base_alert['id'] not in processed_base_ids:
                processed_base_ids.add(base_alert['id'])
            
            processed_count += 1
            
            if processed_count % 100 == 0:
                print(f"  Processed {processed_count} alerts... (Success: {success_count}, Failed: {failed_count})")
        
        # Process any unmatched fail alerts as failures
        for fail_alert in fail_alerts:
            if fail_alert['id'] not in processed_base_ids:
                location_results[matching_key][category]["failed"] += 1
                failed_count += 1
                processed_base_ids.add(fail_alert['id'])
                processed_count += 1

    
    # Convert to list format
    final_result = []
    for key, value in location_results.items():
        result_item = {
            "sap_id": value["sap_id"],
            "location_name": value["location_name"],
            "equipment_type": value["equipment_type"],
            "no_of_vft_activated": value["no_of_vft_activated"],
            "vft_activated_details": value["vft_activated_details"]
        }
        
        for category in VFT_CATEGORIES.keys():
            result_item[category] = [value[category]]
        
        final_result.append(result_item)
    
    final_result = sorted(final_result, key=lambda x: (x["sap_id"], x["location_name"]))
    
    
    return final_result

async def process_radar_data(data):
    """
    Process RADAR equipment data with unique_id matching
    Logic: Match base and fail alerts within 1 minute WITH THE SAME unique_id
    """
    # Build RADAR activated query
    radar_activated_query = build_complete_query(
        RADAR_QUERIES["radar_activated"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    radar_activated_params = urdhva_base.queryparams.QueryParams(q=radar_activated_query, limit=0)
    radar_activated_params.fields = RADAR_FIELDS["radar_activated"]

    radar_activated_resp = await Alerts.get_all(radar_activated_params, resp_type="plain")
    radar_activated_data = radar_activated_resp.get("data", [])
    # Build other interlocks query
    alert_query = build_complete_query(
        RADAR_QUERIES["other_interlocks"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    alert_params = urdhva_base.queryparams.QueryParams(q=alert_query, limit=0)
    alert_params.fields = RADAR_FIELDS["other_interlocks"]

    alerts_resp = await Alerts.get_all(alert_params, resp_type="plain")
    alert_data = alerts_resp.get("data", [])
    
    print(f"RADAR other interlocks data count: {len(alert_data)}")
    
    # Process RADAR Activated data with details
    radar_activated_details = {}
    if len(radar_activated_data) > 0:
        radar_activated_df = pl.DataFrame(radar_activated_data)
        
        radar_activated_df = radar_activated_df.with_columns(
            pl.col("created_at").dt.strftime("%Y-%m-%dT%H:%M:%S").alias("created_at")
        )
        
        for row in radar_activated_df.to_dicts():
            key = (row["sap_id"], row["location_name"])
            if key not in radar_activated_details:
                radar_activated_details[key] = []
            radar_activated_details[key].append({
                "created_at": row["created_at"],
                "device_name": row.get("device_name", "")
            })
    
    if not radar_activated_data and not alert_data:
        print("WARNING: No RADAR data found!")
        return []
    
    if not alert_data and radar_activated_data:
        print("No other RADAR interlock data found, returning RADAR Activated counts only")
        result = {}
        for key, details in radar_activated_details.items():
            result[key] = {
                "sap_id": key[0],
                "location_name": key[1],
                "equipment_type": "RADAR",
                "no_of_radar_activated": len(details),
                "radar_activated_details": details
            }
            
            # Initialize categories from configuration
            for category in RADAR_CATEGORIES.keys():
                result[key][category] = [{"success": 0, "failed": 0}]
        
        final_result = list(result.values())
        final_result = sorted(final_result, key=lambda x: (x["sap_id"], x["location_name"]))               
        return final_result

    # Organize alerts by unique_id and category
    alerts_by_unique_id = {}
    
    for alert in alert_data:
        unique_id = alert['unique_id']
        sap_id = alert['sap_id']
        location_name = alert.get('location_name', '')
        interlock_name = alert.get('interlock_name', '')
        
        # Determine category
        category = None
        for cat, pattern in RADAR_CATEGORIES.items():
            if re.search(pattern, interlock_name):
                category = cat
                break
        
        if not category:
            continue
        
        key = (unique_id, sap_id, location_name, category)
        
        if key not in alerts_by_unique_id:
            alerts_by_unique_id[key] = []
        
        try:
            created_at = alert['created_at']
            if isinstance(created_at, str):
                alert_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            else:
                alert_time = created_at
            
            # Check if this is a Fail alert
            is_fail = "Fail" in interlock_name
            
            alerts_by_unique_id[key].append({
                'id': alert.get('id'),
                'time': alert_time,
                'is_fail': is_fail,
                'interlock_name': interlock_name
            })
        except Exception as e:
            print(f"Error parsing RADAR alert time: {e}")
    
    # Sort alerts by time
    for key in alerts_by_unique_id:
        alerts_by_unique_id[key].sort(key=lambda x: x['time'])    
    # Get unique locations
    unique_locations = {}
    for alert in alert_data:
        key = (alert['sap_id'], alert['location_name'])
        if key not in unique_locations:
            unique_locations[key] = {
                'sap_id': alert['sap_id'],
                'location_name': alert['location_name']
            }
    
    # Initialize results structure
    location_results = {}
    
    for key, loc_info in unique_locations.items():
        sap_id = loc_info['sap_id']
        location_name = loc_info['location_name']
        
        alarm_details = radar_activated_details.get(key, [])
        
        location_results[key] = {
            "sap_id": sap_id,
            "location_name": location_name,
            "equipment_type": "RADAR",
            "no_of_radar_activated": len(alarm_details),
            "radar_activated_details": alarm_details
        }
        
        # Initialize categories from configuration
        for category in RADAR_CATEGORIES.keys():
            location_results[key][category] = {"success": 0, "failed": 0}
    
    # Process alerts with 1-minute window + unique_id matching
    processed_count = 0
    success_count = 0
    failed_count = 0
    processed_base_ids = set()
    
    for key, alerts in alerts_by_unique_id.items():
        unique_id, sap_id, location_name, category = key
        
        matching_key = (sap_id, location_name)
        
        if matching_key not in location_results:
            continue
        
        # Separate alerts into base and fail alerts
        base_alerts = [a for a in alerts if not a['is_fail']]
        fail_alerts = [a for a in alerts if a['is_fail']]
        
        # For each base alert, check if there's a corresponding fail alert within 1 minute
        for base_alert in base_alerts:
            if base_alert['id'] in processed_base_ids:
                continue
            
            base_time = base_alert['time']
            time_start = base_time
            time_end = base_time + timedelta(minutes=1)
            
            found_fail = False
            
            # Check fail alerts WITH THE SAME unique_id
            for fail_alert in fail_alerts:
                fail_time = fail_alert['time']
                
                if fail_time < time_start:
                    continue
                
                if time_start <= fail_time <= time_end:
                    found_fail = True
                    processed_base_ids.add(base_alert['id'])
                    processed_base_ids.add(fail_alert['id'])
                    break
                elif fail_time > time_end:
                    break
            
            if found_fail:
                location_results[matching_key][category]["failed"] += 1
                failed_count += 1
            else:
                location_results[matching_key][category]["success"] += 1
                success_count += 1
            
            if base_alert['id'] not in processed_base_ids:
                processed_base_ids.add(base_alert['id'])
            
            processed_count += 1
            
            if processed_count % 100 == 0:
                print(f"  Processed {processed_count} alerts... (Success: {success_count}, Failed: {failed_count})")
        
        # Process any unmatched fail alerts as failures
        for fail_alert in fail_alerts:
            if fail_alert['id'] not in processed_base_ids:
                location_results[matching_key][category]["failed"] += 1
                failed_count += 1
                processed_base_ids.add(fail_alert['id'])
                processed_count += 1
    
    # Convert to list format
    final_result = []
    for key, value in location_results.items():
        result_item = {
            "sap_id": value["sap_id"],
            "location_name": value["location_name"],
            "equipment_type": value["equipment_type"],
            "no_of_radar_activated": value["no_of_radar_activated"],
            "radar_activated_details": value["radar_activated_details"]
        }
        
        for category in RADAR_CATEGORIES.keys():
            result_item[category] = [value[category]]
        
        final_result.append(result_item)
    
    final_result = sorted(final_result, key=lambda x: (x["sap_id"], x["location_name"]))    
    return final_result

async def process_bcu_data(data):
    """
    Optimized BCU equipment data processing with unique_id matching
    Logic: For each interlock alert, check if BCU Permissive Off_Fail exists 
    within 1 minute WITH THE SAME unique_id
    """
    # Build BCU alarm query
    bcu_alarm_query = build_complete_query(
        BCU_QUERIES["bcu_alarm"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    bcu_alarm_params = urdhva_base.queryparams.QueryParams(q=bcu_alarm_query, limit=0)
    bcu_alarm_params.fields = BCU_FIELDS["bcu_alarm"]
    
    bcu_alarm_resp = await Alerts.get_all(bcu_alarm_params, resp_type="plain")
    bcu_alarm_data = bcu_alarm_resp.get("data", [])
    
    if not bcu_alarm_data:
        return []

    # Process BCU alarm data with details - LIMIT TO configured value
    bcu_alarm_details = {}
    bcu_alarm_counts = {}
    
    bcu_alarm_df = pl.DataFrame(bcu_alarm_data)
    
    bcu_alarm_df = bcu_alarm_df.with_columns(
        pl.col("created_at").dt.strftime("%Y-%m-%dT%H:%M:%S").alias("created_at")
    )
    
    for row in bcu_alarm_df.to_dicts():
        key = (row["sap_id"], row["location_name"])
        
        if key not in bcu_alarm_counts:
            bcu_alarm_counts[key] = 0
        bcu_alarm_counts[key] += 1
        
        if key not in bcu_alarm_details:
            bcu_alarm_details[key] = []
        
        if len(bcu_alarm_details[key]) < BCU_ALARM_DETAILS_LIMIT:
            bcu_alarm_details[key].append({
                "created_at": row["created_at"],
                "device_name": row.get("device_name", "")
            })

    # Get unique locations
    unique_locations = {}
    for record in bcu_alarm_data:
        key = (record['sap_id'], record['location_name'])
        if key not in unique_locations:
            unique_locations[key] = {
                'sap_id': record['sap_id'],
                'location_name': record['location_name']
            }
    
    sap_ids = list(set(loc['sap_id'] for loc in unique_locations.values()))
        
    # Build batch query for all interlocks using template
    interlocks_str = format_interlocks_for_query(BCU_INTERLOCKS)
    sap_ids_str = format_sap_ids_for_query(sap_ids)
    
    all_interlocks_query = BCU_QUERIES["all_interlocks_template"].format(
        sap_ids=sap_ids_str,
        interlocks=interlocks_str
    )
    
    if (data.start_date and data.end_date and
            data.start_date.strip() and data.end_date.strip() and
            data.start_date.lower() != "string" and data.end_date.lower() != "string"):
        all_interlocks_query += f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
    
    interlock_params = urdhva_base.queryparams.QueryParams(q=all_interlocks_query, limit=0)
    interlock_params.fields = BCU_FIELDS["interlocks"]
    
    interlock_resp = await Alerts.get_all(interlock_params, resp_type="plain")
    all_interlock_alerts = interlock_resp.get("data", [])
    
    
    # Build batch query for BCU Permissive Off using template
    permissive_query = BCU_QUERIES["permissive_off_template"].format(
        sap_ids=sap_ids_str
    )
    
    if (data.start_date and data.end_date and
            data.start_date.strip() and data.end_date.strip() and
            data.start_date.lower() != "string" and data.end_date.lower() != "string"):
        permissive_query += f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
    
    permissive_params = urdhva_base.queryparams.QueryParams(q=permissive_query, limit=0)
    permissive_params.fields = BCU_FIELDS["permissive_off"]
    
    permissive_resp = await Alerts.get_all(permissive_params, resp_type="plain")
    all_permissive_alerts = permissive_resp.get("data", [])
        
    # Create efficient lookup structure organized by unique_id
    permissive_by_unique_id = {}
    for alert in all_permissive_alerts:
        unique_id = alert['unique_id']
        
        if unique_id not in permissive_by_unique_id:
            permissive_by_unique_id[unique_id] = []
        
        try:
            created_at = alert['created_at']
            if isinstance(created_at, str):
                alert_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            else:
                alert_time = created_at
            
            interlock_name = alert.get('interlock_name', '')
            is_fail = any(pattern in interlock_name for pattern in FAIL_PATTERNS)
            
            permissive_by_unique_id[unique_id].append({
                'id': alert.get('id'),
                'time': alert_time,
                'is_fail': is_fail,
                'interlock_name': interlock_name
            })
        except Exception as e:
            print(f"Error parsing permissive alert time: {e}")
    
    # Sort permissive alerts by time
    for unique_id in permissive_by_unique_id:
        permissive_by_unique_id[unique_id].sort(key=lambda x: x['time'])
        
    # Initialize results structure
    location_results = {}
    
    for key, loc_info in unique_locations.items():
        sap_id = loc_info['sap_id']
        location_name = loc_info['location_name']
        
        alarm_details = bcu_alarm_details.get(key, [])
        alarm_count = bcu_alarm_counts.get(key, 0)
        
        location_results[key] = {
            "sap_id": sap_id,
            "location_name": location_name,
            "equipment_type": "BCU",
            "no_of_bcu_alarm": alarm_count,
            "bcu_alarm_details": alarm_details
        }
        
        # Initialize all interlocks from configuration
        for interlock in BCU_INTERLOCKS:
            location_results[key][interlock] = {"success": 0, "failed": 0}
    
    # Process each interlock alert with 1-minute window logic + unique_id matching
    processed_count = 0
    success_count = 0
    failed_count = 0
    
    for alert in all_interlock_alerts:
        sap_id = alert['sap_id']
        unique_id = alert['unique_id']
        interlock_name = alert['interlock_name']
        created_at = alert['created_at']
        
        matching_key = None
        for key, loc_info in unique_locations.items():
            if loc_info['sap_id'] == sap_id:
                matching_key = key
                break
        
        if not matching_key:
            continue
        
        try:
            if isinstance(created_at, str):
                alert_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            else:
                alert_time = created_at
            
            time_start = alert_time
            time_end = alert_time + timedelta(minutes=1)
            
            is_failed = False
            
            # Check permissive alerts WITH THE SAME unique_id
            if unique_id in permissive_by_unique_id:
                for perm_alert in permissive_by_unique_id[unique_id]:
                    perm_time = perm_alert['time']
                    
                    if perm_time < time_start:
                        continue
                    
                    if time_start <= perm_time <= time_end:
                        if perm_alert['is_fail']:
                            is_failed = True
                            break
                    elif perm_time > time_end:
                        break
            
            if is_failed:
                location_results[matching_key][interlock_name]["failed"] += 1
                failed_count += 1
            else:
                location_results[matching_key][interlock_name]["success"] += 1
                success_count += 1
            
            processed_count += 1
            if processed_count % 1000 == 0:
                print(f"  Processed {processed_count}/{len(all_interlock_alerts)} alerts... (Success: {success_count}, Failed: {failed_count})")
                
        except Exception as e:
            print(f"  Error processing alert: {e}")
            if matching_key:
                location_results[matching_key][interlock_name]["success"] += 1
                success_count += 1
    
    
    # Convert to list format
    final_result = []
    for key, value in location_results.items():
        result_item = {
            "sap_id": value["sap_id"],
            "location_name": value["location_name"],
            "equipment_type": value["equipment_type"],
            "no_of_bcu_alarm": value["no_of_bcu_alarm"],
            "bcu_alarm_details": value["bcu_alarm_details"]
        }
        
        for interlock in BCU_INTERLOCKS:
            result_item[interlock] = [value[interlock]]
        
        final_result.append(result_item)
    
    final_result = sorted(final_result, key=lambda x: (x["sap_id"], x["location_name"]))    
    return final_result

async def process_fire_effect_data(data):
    """
    Optimized Fire Effect equipment data processing with unique_id matching
    Logic: For each interlock alert, check if corresponding "_Fail" alert exists 
    within 1 minute WITH THE SAME unique_id
    """
    # Build Fire Effect alarm query
    fire_effect_alarm_query = build_complete_query(
        FIRE_EFFECT_QUERIES["fire_effect_alarm"],
        data.start_date,
        data.end_date,
        data.location_name
    )


    fire_effect_alarm_params = urdhva_base.queryparams.QueryParams(q=fire_effect_alarm_query, limit=0)
    fire_effect_alarm_params.fields = FIRE_EFFECT_FIELDS["fire_effect_alarm"]
    
    fire_effect_alarm_resp = await Alerts.get_all(fire_effect_alarm_params, resp_type="plain")
    fire_effect_alarm_data = fire_effect_alarm_resp.get("data", [])
    

    if not fire_effect_alarm_data:
        return []

    # Process Fire Effect alarm data with details
    fire_effect_alarm_details = {}
    fire_effect_alarm_df = pl.DataFrame(fire_effect_alarm_data)
    
    fire_effect_alarm_df = fire_effect_alarm_df.with_columns(
        pl.col("created_at").dt.strftime("%Y-%m-%dT%H:%M:%S").alias("created_at")
    )
    
    for row in fire_effect_alarm_df.to_dicts():
        key = (row["sap_id"], row["location_name"])
        if key not in fire_effect_alarm_details:
            fire_effect_alarm_details[key] = []
        fire_effect_alarm_details[key].append({
            "created_at": row["created_at"],
            "device_name": row.get("device_name", "")
        })

    # Get unique locations
    unique_locations = {}
    for record in fire_effect_alarm_data:
        key = (record['sap_id'], record['location_name'])
        if key not in unique_locations:
            unique_locations[key] = {
                'sap_id': record['sap_id'],
                'location_name': record['location_name']
            }
    
    sap_ids = list(set(loc['sap_id'] for loc in unique_locations.values()))
        
    # Build batch query for all interlocks using template
    sap_ids_str = format_sap_ids_for_query(sap_ids)
    
    all_interlocks_query = FIRE_EFFECT_QUERIES["all_interlocks_template"].format(
        sap_ids=sap_ids_str
    )
    
    if (data.start_date and data.end_date and
            data.start_date.strip() and data.end_date.strip() and
            data.start_date.lower() != "string" and data.end_date.lower() != "string"):
        all_interlocks_query += f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
    
    interlock_params = urdhva_base.queryparams.QueryParams(q=all_interlocks_query, limit=0)
    interlock_params.fields = FIRE_EFFECT_FIELDS["interlocks"]
    
    interlock_resp = await Alerts.get_all(interlock_params, resp_type="plain")
    all_interlock_alerts = interlock_resp.get("data", [])
        
    if not all_interlock_alerts:
        result = []
        for key, details in fire_effect_alarm_details.items():
            result_item = {
                "sap_id": key[0],
                "location_name": key[1],
                "equipment_type": "Fire Effect",
                "no_of_fire_effect_alarm": len(details),
                "fire_effect_alarm_details": details
            }
            
            # Initialize categories from configuration
            for interlock in FIRE_EFFECT_INTERLOCKS:
                result_item[interlock] = [{"success": 0, "failed": 0}]
            
            result.append(result_item)
        return result
    
    # Organize alerts by unique_id and category
    alerts_by_unique_id = {}
    
    for alert in all_interlock_alerts:
        unique_id = alert['unique_id']
        sap_id = alert['sap_id']
        location_name = alert.get('location_name', '')
        interlock_name = alert.get('interlock_name', '')
        
        # Determine category
        category = None
        for interlock in FIRE_EFFECT_INTERLOCKS:
            if interlock.lower().replace(' ', '') in interlock_name.lower().replace(' ', ''):
                category = interlock
                break
        
        if not category:
            continue
        
        key = (unique_id, sap_id, location_name, category)
        
        if key not in alerts_by_unique_id:
            alerts_by_unique_id[key] = []
        
        try:
            created_at = alert['created_at']
            if isinstance(created_at, str):
                alert_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            else:
                alert_time = created_at
            
            # Check if this is a Fail alert
            is_fail = any(pattern in interlock_name for pattern in FAIL_PATTERNS)
            
            alerts_by_unique_id[key].append({
                'id': alert.get('id'),
                'time': alert_time,
                'is_fail': is_fail,
                'interlock_name': interlock_name
            })
        except Exception as e:
            print(f"Error parsing Fire Effect alert time: {e}")
    
    # Sort alerts by time for efficient searching
    for key in alerts_by_unique_id:
        alerts_by_unique_id[key].sort(key=lambda x: x['time'])
    
    
    # Initialize results structure
    location_results = {}
    
    for key, loc_info in unique_locations.items():
        sap_id = loc_info['sap_id']
        location_name = loc_info['location_name']
        
        alarm_details = fire_effect_alarm_details.get(key, [])
        
        location_results[key] = {
            "sap_id": sap_id,
            "location_name": location_name,
            "equipment_type": "Fire Effect",
            "no_of_fire_effect_alarm": len(alarm_details),
            "fire_effect_alarm_details": alarm_details
        }
        
        # Initialize categories from configuration
        for interlock in FIRE_EFFECT_INTERLOCKS:
            location_results[key][interlock] = {"success": 0, "failed": 0}
    
    # Process alerts with 1-minute window logic + unique_id matching
    processed_count = 0
    success_count = 0
    failed_count = 0
    processed_base_ids = set()
    
    for key, alerts in alerts_by_unique_id.items():
        unique_id, sap_id, location_name, category = key
        
        matching_key = None
        for result_key, loc_info in unique_locations.items():
            if loc_info['sap_id'] == sap_id and loc_info['location_name'] == location_name:
                matching_key = result_key
                break
        
        if not matching_key:
            continue
        
        # Separate alerts into base and fail alerts
        base_alerts = [a for a in alerts if not a['is_fail']]
        fail_alerts = [a for a in alerts if a['is_fail']]
        
        # For each base alert, check if there's a corresponding fail alert within 1 minute
        # WITH THE SAME unique_id (already grouped by unique_id)
        for base_alert in base_alerts:
            if base_alert['id'] in processed_base_ids:
                continue
            
            base_time = base_alert['time']
            time_start = base_time
            time_end = base_time + timedelta(minutes=1)
            
            found_fail = False
            
            # Check fail alerts WITH THE SAME unique_id
            for fail_alert in fail_alerts:
                fail_time = fail_alert['time']
                
                if fail_time < time_start:
                    continue
                
                if time_start <= fail_time <= time_end:
                    found_fail = True
                    processed_base_ids.add(base_alert['id'])
                    processed_base_ids.add(fail_alert['id'])
                    break
                elif fail_time > time_end:
                    break
            
            if found_fail:
                location_results[matching_key][category]["failed"] += 1
                failed_count += 1
            else:
                location_results[matching_key][category]["success"] += 1
                success_count += 1
            
            if base_alert['id'] not in processed_base_ids:
                processed_base_ids.add(base_alert['id'])
            
            processed_count += 1
            
            if processed_count % 100 == 0:
                print(f"  Processed {processed_count} alerts... (Success: {success_count}, Failed: {failed_count})")
        
        # Process any unmatched fail alerts as failures
        for fail_alert in fail_alerts:
            if fail_alert['id'] not in processed_base_ids:
                location_results[matching_key][category]["failed"] += 1
                failed_count += 1
                processed_base_ids.add(fail_alert['id'])
                processed_count += 1
    
    
    # Convert to list format
    final_result = []
    for key, value in location_results.items():
        result_item = {
            "sap_id": value["sap_id"],
            "location_name": value["location_name"],
            "equipment_type": value["equipment_type"],
            "no_of_fire_effect_alarm": value["no_of_fire_effect_alarm"],
            "fire_effect_alarm_details": value["fire_effect_alarm_details"]
        }
        
        for interlock in FIRE_EFFECT_INTERLOCKS:
            result_item[interlock] = [value[interlock]]
        
        final_result.append(result_item)
    
    final_result = sorted(final_result, key=lambda x: (x["sap_id"], x["location_name"]))
    
    
    return final_result

async def location_wise_total_loaded_qty(data):
    """
    Get location-wise total loaded quantity from host_local_loaded_tts
    Filters out records where sap_id or location_name is null/empty
    Categorizes loaded_qty by truck type: DG, PROVER, and TANK_TRUCK
    Analyzes loading patterns:
    - local_loading_repeated: 4+ trucks within one hour for same sap_id
    - particular_time_of_day: trucks sent at same hour across multiple days
    - particular_product: only one product type loaded
    - assigned_at_particular_bay: bay assignment details from host_bay_re_assignment

    Returns:
        List of dicts with sap_id, location_name, categorized totals, pattern flags, and bay info
    """

    # Build query using the helper function
    query = build_complete_query(
        HOST_LOCAL_LOADED_TTS_QUERIES["location_wise_total"],
        data.start_date,
        data.end_date,
        getattr(data, 'location_name', None)
    )

    # Add optional sap_id filter if provided
    sap_id = getattr(data, 'sap_id', None)
    if sap_id and sap_id.strip():
        query += f" AND sap_id = '{sap_id}'"

    try:
        from hpcl_ceg_model import HostLocalLoadedTts, HostBayReAssignment

        params = urdhva_base.queryparams.QueryParams(q=query, limit=0)

        # Use fields from config
        fields_to_fetch = HOST_LOCAL_LOADED_TTS_FIELDS.copy() if isinstance(HOST_LOCAL_LOADED_TTS_FIELDS,
                                                                            list) else list(
            HOST_LOCAL_LOADED_TTS_FIELDS)
        params.fields = fields_to_fetch

        resp = await HostLocalLoadedTts.get_all(params, resp_type="plain")
        result_data = resp.get("data", [])

        if not result_data:
            return []

        # Convert to polars DataFrame
        df = pl.DataFrame(result_data)

        # Filter out rows where sap_id or location_name is null/empty
        df = df.filter(
            (pl.col("sap_id").is_not_null()) &
            (pl.col("sap_id").str.strip_chars() != "") &
            (pl.col("location_name").is_not_null()) &
            (pl.col("location_name").str.strip_chars() != "")
        )

        if df.is_empty():
            return []

        # Parse created_at to datetime if it's not already
        if "created_at" in df.columns:
            df = df.with_columns([
                pl.col("created_at").cast(pl.Datetime).alias("created_at_dt")
            ])
        else:
            df = df.with_columns([
                pl.lit(None).cast(pl.Datetime).alias("created_at_dt")
            ])

        # Clean truck_number - REMOVE ALL WHITESPACES AND CONVERT TO UPPERCASE
        if "truck_number" in df.columns:
            df = df.with_columns([
                pl.when(pl.col("truck_number").is_not_null())
                .then(
                    pl.col("truck_number")
                    .cast(pl.Utf8)
                    .str.replace_all(r"\s+", "")  # Remove ALL whitespaces (spaces, tabs, newlines)
                    .str.to_uppercase()
                )
                .otherwise(pl.lit(""))
                .alias("truck_number_clean")
            ])
        else:
            df = df.with_columns([
                pl.lit("").alias("truck_number_clean")
            ])

        # Categorize truck types using config patterns
        prover_pattern = TRUCK_TYPE_PATTERNS["prover"]
        dg_pattern = TRUCK_TYPE_PATTERNS["dg"]

        df = df.with_columns([
            # PROVER: starts with 'P' and contains only letters
            pl.when(
                (pl.col("truck_number_clean") != "") &
                pl.col("truck_number_clean").str.starts_with(prover_pattern["starts_with"]) &
                ~pl.col("truck_number_clean").str.contains(r"\d")
            )
            .then(pl.col("loaded_qty"))
            .otherwise(0)
            .alias("prover_qty"),

            # DG: contains "DG"
            pl.when(
                (pl.col("truck_number_clean") != "") &
                pl.col("truck_number_clean").str.contains(dg_pattern["contains"])
            )
            .then(pl.col("loaded_qty"))
            .otherwise(0)
            .alias("dg_qty"),

            # TANK_TRUCK: not empty and not PROVER and not DG
            pl.when(
                (pl.col("truck_number_clean") != "") &
                ~(
                        pl.col("truck_number_clean").str.starts_with(prover_pattern["starts_with"]) &
                        ~pl.col("truck_number_clean").str.contains(r"\d")
                ) &
                ~pl.col("truck_number_clean").str.contains(dg_pattern["contains"])
            )
            .then(pl.col("loaded_qty"))
            .otherwise(0)
            .alias("tank_truck_qty")
        ])

        # Add date and hour columns for pattern analysis
        df = df.with_columns([
            pl.col("created_at_dt").dt.date().alias("load_date"),
            pl.col("created_at_dt").dt.hour().alias("load_hour"),
            pl.col("created_at_dt").dt.strftime("%Y-%m-%d %H:00:00").alias("hour_window")
        ])

        # ============================================================================
        # BAY RE-ASSIGNMENT DATA LOOKUP
        # ============================================================================

        # Fetch bay re-assignment data for matching truck numbers
        # Get unique truck numbers from the filtered data (already cleaned - no spaces)
        unique_trucks = df.filter(pl.col("truck_number_clean") != "").select(
            "truck_number_clean").unique().to_series().to_list()

        # Fetch bay assignment data
        bay_data = {}  # Format: {(truck_number, created_at_date): [bay_info]}
        if unique_trucks:
            try:
                # Build query for bay re-assignment table
                # Escape single quotes in truck numbers for SQL safety
                truck_list_str = "', '".join([t.replace("'", "''") for t in unique_trucks])
                bay_query = f"truck_number IN ('{truck_list_str}')"

                # Add date range filter with validation
                start_date = getattr(data, 'start_date', None)
                end_date = getattr(data, 'end_date', None)

                # Only add date filter if valid dates are provided
                if (start_date and end_date and
                        start_date != 'string' and end_date != 'string' and
                        str(start_date).strip() and str(end_date).strip()):
                    bay_query += f" AND created_at >= '{start_date}' AND created_at <= '{end_date}'"

                bay_params = urdhva_base.queryparams.QueryParams(q=bay_query, limit=0)
                # Use fields from config
                bay_params.fields = BAY_REASSIGNMENT_CONFIG["fields"]

                bay_resp = await HostBayReAssignment.get_all(bay_params, resp_type="plain")
                bay_result_data = bay_resp.get("data", [])

                # Create a dictionary for quick lookup: (truck_number, created_at_date) -> bay info
                # IMPORTANT: Clean truck numbers from bay table the same way
                for bay_record in bay_result_data:
                    truck_num_raw = bay_record.get("truck_number", "")
                    created_at_raw = bay_record.get("created_at")

                    if truck_num_raw and created_at_raw:
                        # Apply same cleaning: remove all whitespaces and uppercase
                        truck_num_clean = str(truck_num_raw).strip()
                        # Remove all types of whitespace
                        import re
                        truck_num_clean = re.sub(r'\s+', '', truck_num_clean).upper()

                        # Parse created_at to date only (ignore time for matching)
                        try:
                            if isinstance(created_at_raw, str):
                                created_at_dt = pl.Series([created_at_raw]).str.to_datetime().to_list()[0]
                            else:
                                created_at_dt = created_at_raw

                            created_at_date = created_at_dt.date() if hasattr(created_at_dt, 'date') else created_at_dt

                            if truck_num_clean:
                                # Use tuple of (truck_number, date) as key
                                key = (truck_num_clean, str(created_at_date))
                                if key not in bay_data:
                                    bay_data[key] = []
                                bay_data[key].append({
                                    "assigned_bay": bay_record.get("assigned_bay"),
                                    "reassigned_bay": bay_record.get("reassigned_bay"),
                                    "reassign_loaded_qty": bay_record.get("reassign_loaded_qty")
                                })
                        except Exception as date_err:
                            continue

            except Exception as bay_err:
                import traceback
                traceback.print_exc()

        # ============================================================================
        # END BAY RE-ASSIGNMENT DATA LOOKUP
        # ============================================================================

        # Group by sap_id and location_name for aggregations
        result_df = (
            df.group_by(["sap_id", "location_name"])
            .agg([
                pl.sum("dg_qty").alias("dg"),
                pl.sum("tank_truck_qty").alias("tank_truck"),
                pl.sum("prover_qty").alias("prover"),
                pl.sum("loaded_qty").alias("total_loaded_qty")
            ])
            .sort(["sap_id", "location_name"])
        )

        # Get pattern analysis thresholds from config
        min_trucks_per_hour = PATTERN_ANALYSIS_CONFIG["local_loading_repeated"]["min_trucks_per_hour"]
        min_days_for_pattern = PATTERN_ANALYSIS_CONFIG["particular_time_of_day"]["min_days_for_pattern"]
        min_occurrence_ratio = PATTERN_ANALYSIS_CONFIG["particular_time_of_day"]["min_occurrence_ratio"]
        unique_product_count = PATTERN_ANALYSIS_CONFIG["particular_product"]["unique_count"]

        # Analyze patterns for each sap_id
        pattern_analysis = []

        for row in result_df.iter_rows(named=True):
            sap_id_val = row.get("sap_id")
            location_name_val = row.get("location_name")

            # Filter data for this specific sap_id and location
            location_df = df.filter(
                (pl.col("sap_id") == sap_id_val) &
                (pl.col("location_name") == location_name_val)
            )

            # 1. Check for repeated loading (configurable threshold)
            local_loading_repeated = False
            if "hour_window" in location_df.columns:
                trucks_per_hour = (
                    location_df.group_by("hour_window")
                    .agg(pl.count().alias("truck_count"))
                )
                if not trucks_per_hour.is_empty():
                    max_trucks_in_hour = trucks_per_hour.select(pl.max("truck_count")).item()
                    local_loading_repeated = max_trucks_in_hour >= min_trucks_per_hour

            # 2. Check for particular time of day (configurable thresholds)
            particular_time_of_day = False
            if "load_hour" in location_df.columns and "load_date" in location_df.columns:
                # Get unique dates
                unique_dates = location_df.select(pl.col("load_date").unique()).to_series().to_list()

                if len(unique_dates) >= min_days_for_pattern:
                    # Count trucks per hour
                    hour_frequency = (
                        location_df.group_by("load_hour")
                        .agg(pl.count().alias("hour_count"))
                        .sort("hour_count", descending=True)
                    )

                    if not hour_frequency.is_empty():
                        # Get most frequent hour and its count
                        most_frequent_hour_count = hour_frequency.select(pl.first("hour_count")).item()

                        # If the most frequent hour appears on multiple days, it's a pattern
                        if most_frequent_hour_count >= max(min_days_for_pattern,
                                                           len(unique_dates) * min_occurrence_ratio):
                            particular_time_of_day = True

            # 3. Check for particular product (configurable unique count)
            particular_product = False
            if "recipe_name" in location_df.columns:
                # Get unique non-null recipe names
                unique_recipes = (
                    location_df.filter(pl.col("recipe_name").is_not_null())
                    .select(pl.col("recipe_name").unique())
                    .to_series()
                    .to_list()
                )

                # Filter out empty strings
                unique_recipes = [r for r in unique_recipes if r and str(r).strip() != ""]

                # Check against configured unique count
                particular_product = len(unique_recipes) == unique_product_count

            # 4. Check for bay assignments
            # Get all trucks for this location from host_local_loaded_tts (already cleaned - no spaces)
            location_trucks_df = location_df.select(["truck_number_clean", "load_date"]).unique()

            assigned_at_particular_bay = False  # Default to False if no match found

            # Search for truck + date match in host_bay_re_assignment
            for truck_row in location_trucks_df.iter_rows(named=True):
                truck = truck_row.get("truck_number_clean")
                load_date = truck_row.get("load_date")

                if not truck:
                    continue

                # Create key to lookup in bay_data (truck_number, date)
                key = (truck, str(load_date))

                if key in bay_data:
                    # Found matching truck_number AND created_at (date)
                    bay_info = bay_data[key][0]  # Take first record if multiple

                    assigned_at_particular_bay = {
                        "truck_number": truck,
                        "assigned_bay": bay_info.get("assigned_bay"),
                        "reassigned_bay": bay_info.get("reassigned_bay"),
                        "reassign_loaded_qty": bay_info.get("reassign_loaded_qty")
                    }

                    break  # Stop after finding first match

            pattern_analysis.append({
                "sap_id": sap_id_val,
                "location_name": location_name_val,
                "total_loaded_qty": row.get("total_loaded_qty", 0),
                "breakdown": {
                    "dg": row.get("dg", 0),
                    "tank_truck": row.get("tank_truck", 0),
                    "prover": row.get("prover", 0)
                },
                "local_loading_repeated": local_loading_repeated,
                "particular_time_of_day": particular_time_of_day,
                "particular_product": particular_product,
                "assigned_at_particular_bay": assigned_at_particular_bay
            })

        return pattern_analysis

    except Exception as e:
        print(f"Error fetching location-wise total loaded qty: {e}")
        import traceback
        traceback.print_exc()
        return []

async def top_five_alerts(data):
    
    # 1. BASE QUERY
    alert_query = "alert_section = 'TAS'"

    alert_query += (
        f" AND created_at::date BETWEEN "
        f"'{data.start_date}' AND '{data.end_date}'"
    )

    if data.alert_status:
        alert_query += f" AND alert_status = '{data.alert_status}'"

    if data.location_name:
        alert_query += f" AND location_name = '{data.location_name}'"

    if data.interlock_name:
        alert_query += f" AND interlock_name = '{data.interlock_name}'"

    if data.alert_severity:
        if isinstance(data.alert_severity, list):
            clean_severity = [s for s in data.alert_severity if s]
            if clean_severity:
                vals = ", ".join(f"'{s}'" for s in clean_severity)
                alert_query += f" AND severity IN ({vals})"
        else:
            alert_query += f" AND severity = '{data.alert_severity}'"

    print("FINAL alert_query >>>",alert_query)
    

    # 2. FETCH DATA
    params = urdhva_base.queryparams.QueryParams(q=alert_query, limit=0)
    params.fields = [
        "unique_id",
        "zone",
        "alert_status",
        "severity",
        "interlock_name",
        "location_name",
        "created_at"
    ]

    resp = await Alerts.get_all(params, resp_type="plain")
    rows = resp.get("data", [])

    if not rows:
        return []

    df = pl.DataFrame(rows)

AnalyticsModelMapping = {
    "Top Repeated Alerts": top_repeat_alerts,
    "Tas Severity Summary": tas_severity_summary,
    "Location Alert Critical": location_alert_critical,
    "Critical Alerts By Equipment":critical_alerts_by_equipment,
    "Tas Alerts Exception Report" :tas_alerts_exception_report,
    "Equipment Location Wise Count": equipment_location_wise_count,
    "Location Wise Total Loaded Qty": location_wise_total_loaded_qty,
    "Top five Alerts": top_five_alerts

}


async def tas_analytics_action(data):
    analytical_model = data.analytical_model

    if not analytical_model or analytical_model not in AnalyticsModelMapping:
        return {
            "status": False,
            "message": "Invalid Inputs"
        }
    return await AnalyticsModelMapping[analytical_model](data)
