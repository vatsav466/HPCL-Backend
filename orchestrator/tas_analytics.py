import polars as pl
import urdhva_base
from datetime import datetime
from hpcl_ceg_model import Alerts, HostMFMFactor 
import decimal
from orchestrator.dbconnector.widget_actions.vts_analytics import  download_streaming_data
from datetime import datetime, timedelta
import re


from orchestrator.tas_queries import (
    ESD_QUERIES, ESD_FIELDS, ESD_CATEGORIES,
    VFT_QUERIES, VFT_FIELDS, VFT_CATEGORIES,
    RADAR_QUERIES, RADAR_FIELDS, RADAR_CATEGORIES,
    BCU_QUERIES, BCU_FIELDS, BCU_INTERLOCKS, BCU_ALARM_DETAILS_LIMIT,
    FIRE_EFFECT_QUERIES, FIRE_EFFECT_FIELDS, FIRE_EFFECT_INTERLOCKS,
    FAIL_PATTERNS,
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

    alert_params = urdhva_base.queryparams.QueryParams(
        q=alert_query
    )
    alert_params.limit = 0
    alert_params.fields = [
        "equipment_type"
    ]
    
    if data.location_name and data.location_name.lower() == "true":
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
    
    # Check again if dataframe is empty after filtering
    if alerts_df.is_empty():
        return []
    
    # Check if location_name is "true" - group by location only
    if data.location_name and data.location_name.lower() == "true":
        critical_alerts_df = (
            alerts_df
            .group_by(["location_name"])
            .agg(pl.len().alias("critical_count"))
            .sort(["critical_count"], descending=[True])
        )
    else:
        # location_name is not "true" - group by equipment_type only
        critical_alerts_df = (
            alerts_df
            .group_by(["equipment_type"])
            .agg(pl.len().alias("critical_count"))
            .sort(["critical_count"], descending=[True])
        )
    
    return critical_alerts_df.to_dicts()

async def tas_alerts_exception_report(data):
    alert_query = "alert_section = 'TAS'"
    
    # Add date filter if provided
    if (data.start_date and data.end_date and 
        data.start_date.strip() and data.end_date.strip() and
        data.start_date.lower() != "string" and data.end_date.lower() != "string"):
        alert_query += f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"

    alert_params = urdhva_base.queryparams.QueryParams(q=alert_query)
    alert_params.limit = 0

    alerts_resp = await Alerts.get_all(alert_params, resp_type="plain")
    alert_data = alerts_resp.get("data", [])

    if not alert_data:
        return []

    df = pl.DataFrame(alert_data)

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

    # Map the normalized names back to original names
    df = df.with_columns(
        pl.col("interlock_name_normalized").replace(interlock_normalized, default=pl.col("interlock_name")).alias(
            "interlock_name_mapped")
    )
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
    
    # Check if download is requested (handle both string "true" and boolean True)
    if data.download and str(data.download).lower() == "true":
        return await download_streaming_data(pivot_df, filename="exception_report")

    return pivot_df.to_dicts()

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
    if len(esd_pushbutton_data) > 0:
        esd_pushbutton_df = pl.DataFrame(esd_pushbutton_data)
        
        esd_pushbutton_df = esd_pushbutton_df.with_columns(
            pl.col("created_at").dt.strftime("%Y-%m-%dT%H:%M:%S").alias("created_at")
        )
        
        for row in esd_pushbutton_df.to_dicts():
            key = (row["sap_id"], row["location_name"])
            if key not in esd_activated_details:
                esd_activated_details[key] = []
            esd_activated_details[key].append({
                "created_at": row["created_at"],
                "device_name": row.get("device_name", "")
            })

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
    interlock_params.fields = ESD_FIELDS["interlocks"]
    
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
                "esd_activated_details": details
            }
            
            # Initialize categories from configuration
            for category in ESD_CATEGORIES.keys():
                result_item[category] = [{"success": 0, "failed": 0}]
            
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
                'interlock_name': interlock_name
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
            "esd_activated_details": alarm_details
        }
        
        # Initialize categories from configuration
        for category in ESD_CATEGORIES.keys():
            location_results[key][category] = {"success": 0, "failed": 0}
    
    # Process alerts with 1-minute window logic AND unique_id matching
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
                    # Found matching fail alert with same unique_id within 1 minute
                    found_fail = True
                    processed_base_ids.add(base_alert['id'])
                    processed_base_ids.add(fail_alert['id'])
                    print(f"  ✓ Matched: unique_id={unique_id}, category={category}, "
                          f"base_time={base_time.strftime('%H:%M:%S')}, "
                          f"fail_time={fail_time.strftime('%H:%M:%S')}")
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
            "no_of_esd_activated": value["no_of_esd_activated"],
            "esd_activated_details": value["esd_activated_details"]
        }
        
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

AnalyticsModelMapping = {
    "Top Repeated Alerts": top_repeat_alerts,
    "Tas Severity Summary": tas_severity_summary,
    "Location Alert Critical": location_alert_critical,
    "Critical Alerts By Equipment":critical_alerts_by_equipment,
    "Tas Alerts Exception Report" :tas_alerts_exception_report,
    "Equipment Location Wise Count": equipment_location_wise_count

}


async def tas_analytics_action(data):
    analytical_model = data.analytical_model

    if not analytical_model or analytical_model not in AnalyticsModelMapping:
        return {
            "status": False,
            "message": "Invalid Inputs"
        }
    return await AnalyticsModelMapping[analytical_model](data)
