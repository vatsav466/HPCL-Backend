import urdhva_base
import polars as pl
from datetime import datetime
import json
import os
import math
import hpcl_ceg_model
import traceback
import dashboard_studio_model
import charts_actions
import httpx
from collections import defaultdict
import orchestrator.workflow.workflow_process as workflow_process
import utilities.minio_connector as minio_connector
import decimal

import orchestrator.dbconnector.widget_actions.vts_analytics as vts_analytics
from datetime import datetime, timedelta, timezone
import re
import utilities.analog_data_mapping as analog_mapping
import orchestrator.tas_analytics.tas_queries as tas_queries
import orchestrator.alerting.listener.tas_listener as tas_listener
import utilities.helpers as helpers
import orchestrator.tas_analytics.tas_host_data as tas_host_data


def unix_ms_to_ist(ts_ms: int) -> datetime:
    IST = timezone(timedelta(hours=5, minutes=30))
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).astimezone(IST)


async def check_run_time_fire_engine(data):

    # Fire engine status (ON / OFF)
    engine_status = data["status"]
    device_name = data["device_name"]
    sap_id = data["sap_id"]
    bu = data["bu"]

    status, location_details = await helpers.get_location_details(bu, sap_id)
    if not status:
        print(f"Location data missing for SAP ID {sap_id}")
        return

    location_name = location_details["name"]
    zone = location_details["zone"]

    if engine_status in ["ON"]:
        fire_engine_on_datetime = unix_ms_to_ist(
            data["fire_engine_on_datetime"]
        )

        await hpcl_ceg_model.TasFireEngineTestCreate(
            device_name=device_name,
            sap_id=sap_id,
            location_name=location_name,
            zone=zone,
            fire_engine_on_datetime=fire_engine_on_datetime,
        ).create()

        return

    if engine_status in ["OFF"]:
        fire_engine_off_datetime = unix_ms_to_ist(
            data["fire_engine_off_datetime"]
        )

        params = urdhva_base.queryparams.QueryParams(
            q=(
                f"sap_id='{sap_id}' "
                f"AND device_name='{device_name}' "
                f"AND fire_engine_off_datetime IS NULL"
            ),
            limit=1,
            sort=json.dumps({"created_at": "desc"})
        )

        records = await hpcl_ceg_model.TasFireEngineTest.get_all(
            params, resp_type="plain"
        )

        rows = records.get("data", [])
        if not rows:
            return

        latest = rows[0]
        run_time = fire_engine_off_datetime - latest["fire_engine_on_datetime"]

        await hpcl_ceg_model.TasFireEngineTest(
            id=latest["id"],
            fire_engine_off_datetime=fire_engine_off_datetime,
            total_run_time=str(run_time),
        ).modify()


async def create_tas_faulty(data, certificate_file=None):
    """
    Create a TAS Faulty record and start the related workflow.

    Checks for duplicate records, initiates the Camunda workflow,
    optionally uploads a certificate to MinIO, and saves the
    TAS Faulty details in the database.

    Args:
        data: TAS Faulty request data.
        certificate_file: Optional certificate file.

    Returns:
        dict: Status, message, and created record details.
    """
    try:
        # Convert to dict at the start
        data = data.dict()

        sap_id = data['sap_id']
        device_type = data['device_type']
        equipment_name = data['equipment_name']
        zone = data['zone']
        location_name = data['name']
        user_remarks = data['user_remarks']
        faulty = data['faulty']

        print("sap_id:", sap_id)

        # Set default status
        data['status'] = "Open"

        # ---------------- DUPLICATE CHECK ----------------
        params = urdhva_base.queryparams.QueryParams(limit=1)
        params.q = (
            f"sap_id='{sap_id}' "
            f"AND device_type='{device_type}' "
            f"AND equipment_name='{equipment_name}'"
        )

        existing = await hpcl_ceg_model.TasFaulty.get_all(
            params, resp_type="plain"
        )

        if existing.get("data"):
            return {
                "status": False,
                "message": (
                    "Duplicate TasFaulty record exists for "
                    f"SAP ID = {sap_id}, Equipment = {equipment_name}"
                ),
                "data": {}
            }

        # ---------------- START WORKFLOW ----------------
        payload_workflow = {
            "variables": {
                "sap_id": {"value": sap_id, "type": "String"},
                "location_name": {"value": location_name, "type": "String"},
                "device_type": {"value": device_type, "type": "String"},
                "equipment_name": {"value": equipment_name, "type": "String"},
                "zone": {"value": zone, "type": "String"},
                "remarks": {"value": user_remarks, "type": "String"},
                "status": {"value": data['status'], "type": "String"},
            }
        }

        camunda_resp = await workflow_process.Camunda().start_tas_faulty_workflow(
            payload=payload_workflow,
            workflowId="TASFAULTYCHECK"
        )

        data['workflow_instance_id'] = camunda_resp.get("id", "")

        # ---------------- SAVE CERTIFICATE ----------------
        certificate_path = None

        if certificate_file:
            UPLOAD_DIR = os.path.join(
                urdhva_base.settings.uploads,
                "tas_faulty"
            )
            os.makedirs(UPLOAD_DIR, exist_ok=True)

            faulty_val = faulty
            if isinstance(faulty_val, datetime):
                faulty_val = faulty_val.strftime("%Y%m%d_%H%M%S")

            object_name = f"{faulty_val}_{sap_id}_{equipment_name}"

            file_path = os.path.join(
                UPLOAD_DIR,
                certificate_file.filename
            )

            with open(file_path, "wb") as f:
                f.write(await certificate_file.read())

            status_minio, minio_path = minio_connector.upload_to_minio(
                "TAS",
                "tas_faulty_certificates",
                object_name,
                file_path
            )

            if not status_minio:
                return {
                    "status": False,
                    "message": "MinIO upload failed",
                    "error": minio_path
                }

            certificate_path = minio_path
            data['certificate'] = certificate_path

            try:
                os.remove(file_path)
            except Exception:
                pass

        # ---------------- INSERT ----------------
        record = await hpcl_ceg_model.TasFaultyCreate(**data).create()

        return {
            "status": True,
            "message": "TasFaulty record saved successfully",
            "data": record
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Failed to save TasFaulty record: {e}",
            "data": {}
        }

async def update_tas_faulty(data):
    """
    Update a TAS Faulty record and trigger the Camunda workflow with vendor remarks and resolved status.
    """
    try:
        transaction_id = int(data.transaction_id)
        vendor_remarks = data.vendor_remarks
        resolved = bool(data.resolved)

        # ---------------- FETCH RECORD ----------------
        record = await hpcl_ceg_model.TasFaulty.get_all(urdhva_base.queryparams.QueryParams(q=f"id={transaction_id}", limit=1),
                                                        resp_type="plain")
        row = record.get("data")

        if not row:
            return {"status": False, "message": "No faulty record found", "data": {}}

        row = row[0]
        process_instance_id = row["workflow_instance_id"]
        if not process_instance_id:
            return {"status": False, "message": "Workflow instance not linked", "data": {}}

        # ---------------- TRIGGER CAMUNDA ----------------
        camunda_payload = {
            "messageName": "Resolved",
            "processInstanceId": process_instance_id,
            "processVariables": {
                "resolved": {"value": resolved, "type": "Boolean"},
                "remarks": {"value": vendor_remarks, "type": "String"}
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{urdhva_base.settings.tas_faulty_camunda_url}/engine-rest/message",
                json=camunda_payload,
                timeout=10
            )

        if response.status_code not in (200, 204):
            return {"status": False, "message": "Workflow trigger failed", "data": response.text}

        # ---------------- UPDATE RECORD ----------------
        update_data = dict(record)
        update_data.pop("id", None)
        update_data["vendor_remarks"] = vendor_remarks
        update_data["status"] = "Resolved" if resolved else "Rejected"

        await hpcl_ceg_model.TasFaulty(id=transaction_id, **update_data).modify()

        return {
            "status": True,
            "message": "Workflow triggered and record updated successfully",
            "data": {"transaction_id": transaction_id, "resolved": resolved}
        }

    except Exception as e:
        return {"status": False, "message": str(e), "data": {}}


async def get_info_tas_faulty(data):
    """
    Fetch device types or device names for a given SAP ID.

    - If only SAP ID is provided, returns all available device types.
    - If SAP ID and device type are provided, returns device names
      matching the given device type.
    """
    sap_id = data.sap_id
    device_type_filter = data.device_type

    device_json = tas_listener.load_device_data(sap_id)
    if not device_json:
        return {
            "status": False,
            "message": f"Device data not found for SAP ID {sap_id}"
        }

    devices = device_json.get("data", [])

    # ---------------- CASE 1: Only SAP ID ----------------
    if not device_type_filter:
        device_types = {
            device["device_type"]
            for device in devices
            if device.get("device_type")
        }

        return {
            "sap_id": sap_id,
            "device_types": sorted(device_types)
        }

    # ---------------- CASE 2: SAP ID + Device Type ----------------
    device_names = {
        device["device_name"]
        for device in devices
        if device.get("device_type") == device_type_filter
        and device.get("device_name")
    }

    return {
        "sap_id": sap_id,
        "device_type": device_type_filter,
        "device_names": sorted(device_names)
    }


def create_valid_vehicle_filter(column_name: str, min_length: int = 9) -> pl.Expr:
    """Validate vehicle/truck numbers: min length, contains A-Z and 0-9, alphanumeric only."""
    return pl.when(
        (pl.col(column_name).str.len_chars() >= min_length) &
        pl.col(column_name).str.contains(r"[A-Z]") &
        pl.col(column_name).str.contains(r"[0-9]") &
        pl.col(column_name).str.contains(r"^[A-Z0-9]+$")
    ).then(True).otherwise(False)


async def top_repeat_alerts(data):
    try:
        # 1. BUILD WHERE CLAUSE
        where_conditions = [
            "alert_section = 'TAS'",
            "interlock_name NOT IN ('BCU Permissive Off', 'BCU Permissive Off_Fail')"
        ]

        if data.start_date and data.end_date:
            where_conditions.append(f"created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'")

        if data.alert_status:
            where_conditions.append(f"alert_status = '{data.alert_status}'")

        if data.location_name:
            where_conditions.append(f"location_name = '{data.location_name}'")

        if data.alert_severity:
            if isinstance(data.alert_severity, list):
                clean_severity = [s for s in data.alert_severity if s]
                if clean_severity:
                    severity_vals = ", ".join(f"'{s}'" for s in clean_severity)
                    where_conditions.append(f"severity IN ({severity_vals})")
            elif data.alert_severity.strip():
                where_conditions.append(f"severity = '{data.alert_severity}'")

        # 2. HANDLE INTERLOCK-SPECIFIC OR GENERAL QUERY
        if data.interlock_name:
            where_conditions.append(f"interlock_name = '{data.interlock_name}'")
            where_clause = " AND ".join(where_conditions)

            # Query for detail list
            detail_query = f"""
                SELECT
                    unique_id, alert_status, severity, interlock_name, location_name, device_name,
                    TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at,
                    TO_CHAR(updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS updated_at,
                    FLOOR(
                        EXTRACT(
                            EPOCH FROM (
                                CASE
                                    WHEN alert_status = 'Close' 
                                    THEN updated_at - created_at
                                    ELSE NOW() - created_at
                                END
                            )
                        ) / 86400
                    ) AS ageing_days
                FROM Alerts
                WHERE {where_clause}
                ORDER BY ageing_days DESC;
            """
            detail_list = await hpcl_ceg_model.Alerts.get_aggr_data(detail_query, limit=0)
            detail_list = detail_list.get("data", [])

            # Query for ageing analysis
            ageing_query = f"""
                WITH ageing_data AS (
                SELECT
                    FLOOR(
                        EXTRACT(
                            EPOCH FROM (
                                CASE
                                    WHEN alert_status = 'Close' 
                                    THEN updated_at - created_at
                                    ELSE NOW() - created_at
                                END
                            )
                        ) / 86400
                    ) AS ageing_days,
                    location_name
                FROM Alerts
                    WHERE {where_clause}
                ),
                bucketed_data AS (
                    SELECT
                        location_name,
                        CASE
                            WHEN ageing_days = 0 THEN '0 Day'
                            WHEN ageing_days = 1 THEN '1 Day'
                            WHEN ageing_days = 2 THEN '2 Days'
                            WHEN ageing_days = 3 THEN '3 Days'
                            WHEN ageing_days = 4 THEN '4 Days'
                            WHEN ageing_days = 5 THEN '5 Days'
                            WHEN ageing_days BETWEEN 6 AND 10 THEN '6-10 Days'
                            WHEN ageing_days BETWEEN 11 AND 15 THEN '11-15 Days'
                            WHEN ageing_days BETWEEN 16 AND 30 THEN '16-30 Days'
                            WHEN ageing_days BETWEEN 31 AND 60 THEN '31-60 Days'
                            WHEN ageing_days > 60 THEN '60+ Days'
                        END AS ageing_bucket
                    FROM ageing_data
                )
                SELECT ageing_bucket, location_name, COUNT(*) as alert_count
                FROM bucketed_data
                GROUP BY ageing_bucket, location_name
                ORDER BY MIN(CASE 
                    WHEN ageing_bucket = '1 Day' THEN 1
                    WHEN ageing_bucket = '2 Days' THEN 2
                    WHEN ageing_bucket = '3 Days' THEN 3
                    WHEN ageing_bucket = '4 Days' THEN 4
                    WHEN ageing_bucket = '5 Days' THEN 5
                    WHEN ageing_bucket = '6-10 Days' THEN 6
                    WHEN ageing_bucket = '11-15 Days' THEN 11
                    WHEN ageing_bucket = '16-30 Days' THEN 16
                    WHEN ageing_bucket = '31-60 Days' THEN 31
                    ELSE 61
                END);
            """
            ageing_summary_raw = await hpcl_ceg_model.Alerts.get_aggr_data(ageing_query, limit=0)
            ageing_summary_raw = ageing_summary_raw.get("data", [])

            # Process ageing summary
            bucket_result = []
            if ageing_summary_raw:
                ageing_df = pl.DataFrame(ageing_summary_raw)
                ordered_buckets = [
                    "0 Day","1 Day", "2 Days", "3 Days", "4 Days", "5 Days",
                    "6-10 Days", "11-15 Days", "16-30 Days", "31-60 Days", "60+ Days"
                ]
                for bucket in ordered_buckets:
                    bucket_df = ageing_df.filter(pl.col("ageing_bucket") == bucket)
                    if not bucket_df.is_empty():
                        total_count = bucket_df["alert_count"].sum()
                        bucket_result.append({
                            "ageing_range": bucket,
                            "total_alerts": total_count,
                            "locations": bucket_df.select(["location_name", "alert_count"]).to_dicts()
                        })

            return {
                "status": True,
                "message": "Top repeat alerts processed successfully",
                "data": {
                    "detail_list": detail_list,
                    "ageing_analysis": bucket_result
                }
            }

        else:
            where_clause = " AND ".join(where_conditions)
            query = f"""
                SELECT interlock_name, COUNT(*) AS count
                FROM Alerts
                WHERE {where_clause}
                GROUP BY interlock_name
                ORDER BY count DESC
                LIMIT 5;
            """
            result = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=0)
            result = result.get("data", [])
            return {"status": True, "message": "Top repeat alerts processed successfully", "data": result}

    except Exception as e:
        print(f"Error in top_repeat_alerts: {e}")
        return {"status": False, "message": f"Error processing top repeat alerts: {e}", "data": []}


async def tas_severity_summary(data):
    try:
        where_conditions = ["alert_section = 'TAS'"]

        if data.start_date and data.end_date:
            where_conditions.append(
                f"created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
            )

        if data.zone:
            where_conditions.append(f"zone = '{data.zone}'")

        if data.alert_status:
            where_conditions.append(f"alert_status = '{data.alert_status}'")

        if data.location_name:
            where_conditions.append(f"location_name = '{data.location_name}'")

 
        where_clause = " AND ".join(where_conditions)

        location_params = urdhva_base.queryparams.QueryParams(
            q="location_onboard='true'",
            limit=0
        )
        location_params.fields = ["zone", "name"]
        all_location_resp = await hpcl_ceg_model.LocationMaster.get_all(location_params, resp_type="plain")
        all_locations = all_location_resp.get("data", [])

        maintenance_terms = [
            i["interlock_name"].lower()
            for i in analog_mapping.Maintenance
            if i.get("interlock_name")
        ]

        fault_terms = [
            i["interlock_name"].lower()
            for i in analog_mapping.Fault
            if i.get("interlock_name")
        ]

        normal_terms = [
            i["interlock_name"].lower()
            for i in analog_mapping.Normal
            if i.get("interlock_name")
        ]

        def build_contains_condition(terms):
            conditions = []
            for term in terms:
                if not term:
                    continue
                term_escaped = term.replace("'", "''")
                conditions.append(
                    f"LOWER(interlock_name) LIKE '%{term_escaped}%'"
                )
            return "(" + " OR ".join(conditions) + ")" if conditions else "FALSE"

        maintenance_condition = build_contains_condition(maintenance_terms)
        fault_condition = build_contains_condition(fault_terms)

        # Build category condition for filtering
        category_condition = ""
        if  data.interlock_category:
            if data.interlock_category.lower() == 'maintenance_count':
                category_condition = f"AND ({maintenance_condition})"
            elif data.interlock_category.lower() == 'fault_count':
                category_condition = f"AND ({fault_condition})"
            elif data.interlock_category.lower() == 'both':
                category_condition = f"AND (({maintenance_condition}) OR ({fault_condition}))"
           

        if data.location_name:
            detail_query = f"""
                SELECT
                    interlock_name,
                    equipment_name,
                    TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at,
                    CASE
                        WHEN {maintenance_condition} THEN 'maintenance'
                        WHEN {fault_condition} THEN 'fault'
                        ELSE 'other'
                    END AS interlock_category
                FROM Alerts
                WHERE {where_clause} {category_condition}
                ORDER BY created_at DESC;
            """            
            
            detail_result = await hpcl_ceg_model.Alerts.get_aggr_data(detail_query, limit=0)
            detail_data = detail_result.get("data", [])

            if not detail_data  and not data.interlock_category:
                # Return all locations with zero counts when No data is there
                result = []
                for loc in all_locations:
                    result.append({
                        "zone": loc.get("zone", ""),
                        "location_name": loc.get("name", ""),
                        "under_maintenance_count": 0,
                        "fault_count": 0
                    })
                return {
                    "status": True,
                    "message": "TAS severity detail processed successfully",
                    "data": result,
                }
            
            return {
                "status": True,
                "message": "TAS severity detail processed successfully",
                "data": detail_data,
            }
           

        summary_query = f"""
            WITH categorized AS (
                SELECT
                    zone,
                    location_name,
                    CASE
                        WHEN {maintenance_condition} THEN 'maintenance'
                        WHEN {fault_condition} THEN 'fault'
                        ELSE 'other'
                    END AS interlock_category
                FROM Alerts
                WHERE {where_clause}
            )
            SELECT
                zone,
                location_name,
                SUM(CASE WHEN interlock_category = 'maintenance' THEN 1 ELSE 0 END)
                    AS under_maintenance_count,
                SUM(CASE WHEN interlock_category = 'fault' THEN 1 ELSE 0 END)
                    AS fault_count
            FROM categorized
            GROUP BY zone, location_name
            ORDER BY zone, location_name;
        """

        summary_result = await hpcl_ceg_model.Alerts.get_aggr_data(summary_query, limit=0)
        summary_data = summary_result.get("data", [])

        # Add locations with zero counts if they don't have any alerts
        alert_locations = {(r["zone"], r["location_name"]) for r in summary_data}
        
        for loc in all_locations:
            zone = loc.get("zone", "")
            location_name = loc.get("name", "")
            if (zone, location_name) not in alert_locations:
                summary_data.append({
                    "zone": zone,
                    "location_name": location_name,
                    "under_maintenance_count": 0,
                    "fault_count": 0
                })

        return {
            "status": True,
            "message": "TAS severity summary processed successfully",
            "data": summary_data,
        }
    except Exception as e:
        print(f"Error in tas_severity_summary: {e}")
        return {
            "status": False,
            "message": f"Error processing TAS severity summary: {e}",
            "data": [],
        }


async def location_alert_critical(data):
    try:
        # 1. EXTRACT PARAMETERS
        zone = data.zone or None
        location_name = data.location_name or None
        alert_status = data.alert_status or None
        severity_filter = data.alert_severity or []
        is_download = str(getattr(data, "download", "")).lower() == "true"

        # 2. BUILD WHERE CLAUSE
        where_conditions = [
            "alert_section = 'TAS'",
            f"created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
        ]

        if zone:
            where_conditions.append(f"zone = '{zone}'")
        if alert_status:
            where_conditions.append(f"alert_status = '{alert_status}'")
        if location_name and not is_download and not location_name.lower() == "true":
            where_conditions.append(f"location_name = '{location_name}'")

        if isinstance(severity_filter, list) and severity_filter:
            severity_values = ", ".join(f"'{s.strip().lower()}'" for s in severity_filter if s and isinstance(s, str))
            if severity_values:
                where_conditions.append(f"LOWER(severity) IN ({severity_values})")

        where_clause = " AND ".join(where_conditions)

        # 3. DETERMINE QUERY TYPE (DOWNLOAD, DETAIL, OR SUMMARY)

        # DOWNLOAD OR DETAIL VIEW
        if is_download or location_name:
            query = f"""
                SELECT
                    unique_id,
                    zone,
                    severity,
                    alert_status,
                    interlock_name,
                    location_name,
                    TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at,
                    FLOOR(EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400) AS ageing_days
                FROM Alerts
                WHERE {where_clause}
                ORDER BY ageing_days DESC;
            """
            result = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=0)
            result_data = result.get("data", [])

            if is_download:
                return {
                    "download": True,
                    "download_type": "raw_alerts",
                    "data": result_data
                }
            return {"status": True, "message": "Critical alert details processed successfully", "data": result_data}

        #  SUMMARY VIEW (Dashboard)
        else:

            summary_query = f"""
                WITH base_alerts AS (
                    SELECT
                        zone,
                        location_name,
                        interlock_name,
                        severity
                    FROM Alerts
                    WHERE {where_clause} AND location_name IS NOT NULL AND location_name != ''
                ),
                interlock_counts AS (
                    SELECT
                        zone,
                        location_name,
                        interlock_name,
                        severity,
                        COUNT(*) as count
                    FROM base_alerts
                    GROUP BY zone, location_name, interlock_name, severity
                ),
                total_counts AS (
                    SELECT
                        zone,
                        location_name,
                        SUM(count) as total_alerts
                    FROM interlock_counts
                    GROUP BY zone, location_name
                )
                SELECT
                    t.zone,
                    t.location_name,
                    t.total_alerts,
                    json_agg(json_build_object('interlock_name', i.interlock_name, 'severity', i.severity, 'count', i.count)) as interlocks
                FROM total_counts t
                JOIN interlock_counts i ON t.zone = i.zone AND t.location_name = i.location_name
                GROUP BY t.zone, t.location_name, t.total_alerts
                ORDER BY t.total_alerts DESC;
            """

            result = await hpcl_ceg_model.Alerts.get_aggr_data(summary_query, limit=0)
            summary_data = result.get("data", [])

            # Merge with all onboarded locations
            all_locations = await get_all_onboarded_locations()
            print("Total onboarded locations:", len(all_locations))

            # Apply zone filter if provided
            if zone:
                all_locations = [
                    loc for loc in all_locations
                    if (loc.get("zone") or "").strip() == zone
                ]

            # Normalize DB result for easy lookup
            summary_lookup = {
                (row.get("location_name") or "").strip().upper(): row
                for row in summary_data
            }

            final_response = []

            for loc in all_locations:
                loc_name = (loc.get("name") or "").strip()
                loc_zone = loc.get("zone")

                if not loc_name:
                    continue

                normalized_name = loc_name.upper()

                if normalized_name in summary_lookup:
                    # Use real DB row
                    row = summary_lookup[normalized_name]
                    # Ensure zone always comes from master
                    row["zone"] = loc_zone
                    final_response.append(row)

                else:
                    # Add zero row
                    final_response.append({
                        "zone": loc_zone,
                        "location_name": loc_name,
                        "total_alerts": 0,
                        "interlocks": []
                    })

            # Sort by total_alerts descending
            final_response.sort(
                key=lambda x: x.get("total_alerts", 0),
                reverse=True
            )

            return {
                "status": True,
                "message": "Critical alert summary processed successfully",
                "data": final_response
            }

    except Exception as e:
        print(f"Error in location_alert_critical: {e}")
        return {
            "status": False,
            "message": f"Error processing critical alerts: {e}",
            "data": []
        }


async def critical_alerts_by_equipment(data):
    try:
        # 1. BUILD WHERE CLAUSE
        where_conditions = [
            "alert_section = 'TAS'",
            "severity = 'Critical'",
            "equipment_type IS NOT NULL",
            "equipment_type != ''"
        ]

        if data.alert_status and data.alert_status.strip():
            where_conditions.append(f"alert_status = '{data.alert_status}'")

        if (
                data.start_date and data.end_date and
                data.start_date.strip() and data.end_date.strip() and
                data.start_date.lower() != "string" and data.end_date.lower() != "string"
        ):
            where_conditions.append(f"created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'")

        if data.location_name and data.location_name.strip() and data.location_name.lower() != "true":
            where_conditions.append(f"location_name = '{data.location_name}'")

        if data.zone and data.zone.strip():
            where_conditions.append(f"zone = '{data.zone}'")

        if data.equipment_type:
            where_conditions.append(f"equipment_type = '{data.equipment_type}'")

        where_clause = " AND ".join(where_conditions)

        # 2. DETERMINE GROUPING AND AGGREGATION
        if not data.alert_status or not data.alert_status.strip():
            query = f"""
                SELECT
                    location_name,
                    SUM(CASE WHEN alert_status = 'Open' THEN 1 ELSE 0 END) AS open_critical_count,
                    SUM(CASE WHEN alert_status = 'Close' THEN 1 ELSE 0 END) AS close_critical_count
                FROM Alerts
                WHERE {where_clause}
                GROUP BY location_name
                ORDER BY open_critical_count DESC;
            """
        else:
            group_by_field = "location_name" if (
                                                            data.location_name and data.location_name.lower() == "true") or data.equipment_type else "equipment_type"
            query = f"""
                SELECT
                    {group_by_field},
                    COUNT(*) AS critical_count
                FROM Alerts
                WHERE {where_clause}
                GROUP BY {group_by_field}
                ORDER BY critical_count DESC;
            """

        # 3. FETCH DATA
        result = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=0)
        result = result.get("data", [])
        return {"status": True, "message": "Critical alerts processed successfully", "data": result}

    except Exception as e:
        print(f"Error in critical_alerts_by_equipment: {e}")
        return {"status": False, "message": f"Error processing critical alerts: {e}", "data": []}
    
async def get_all_onboarded_locations():
    """
    Fetch all onboarded TAS locations from location_master.
    Returns a list of dicts with 'name' (location_name) and 'zone'.
    """
    location_params = urdhva_base.queryparams.QueryParams(
        q="location_onboard='true'",
        limit=0
    )
    location_params.fields = ["name", "zone"]
    resp = await hpcl_ceg_model.LocationMaster.get_all(location_params, resp_type="plain")
    return resp.get("data", [])


async def tas_alerts_exception_report(data):
    q = "alert_section = 'TAS'"
    if data.start_date and data.end_date and data.start_date.lower() != "string":
        q += (
            f" AND created_at >= '{data.start_date} 00:00:00'"
            f" AND created_at <  '{data.end_date} 23:59:59'"
        )

    params = urdhva_base.queryparams.QueryParams(q=q, fields=json.dumps(
        ["location_name", "sap_id", "interlock_name", "created_at", "vehicle_number", "device_name"]))
    params.limit = 0

    alerts = (await hpcl_ceg_model.Alerts.get_all(params, resp_type="plain")).get("data", [])
    if not alerts:
        return []
    df = (pl.DataFrame(alerts, infer_schema_length=None)
          .with_columns([
        pl.col("vehicle_number").str.strip_chars(),
        pl.col("interlock_name")
        .str.to_lowercase()
        .str.replace_all(" ", "")
        .alias("interlock_norm"),
        pl.col("created_at").dt.date().alias("created_date"),
        pl.col("created_at").dt.truncate("1h").alias("created_at_hour")
    ])
          .with_columns([
        create_valid_vehicle_filter("vehicle_number").alias("is_valid_vehicle")
    ])
          .filter(pl.col("is_valid_vehicle") == True)
          .drop("is_valid_vehicle")
          )
    df = df.unique(subset=["vehicle_number", "created_at_hour", "interlock_norm"])


    mfm_q = (
        f"last_k_factor_change_date IS NOT NULL"
        f" AND last_k_factor_change_date != ''"
        f" AND last_k_factor_change_date >= '{data.start_date}'"
        f" AND last_k_factor_change_date <= '{data.end_date}'"
    )
    mfm = await hpcl_ceg_model.HostMFMFactor.get_all(
        urdhva_base.queryparams.QueryParams(q=mfm_q, limit=0),
        resp_type="plain"
    )
    mfm_data = mfm.get("data", [])

    mfm_data = [
        {k: (round(float(v), 2) if isinstance(v, decimal.Decimal) else v) for k, v in r.items()}
        for r in mfm_data
    ]

    mfm_df = (
        pl.DataFrame(mfm_data, infer_schema_length=None)
        .select(["sap_id", "location_name", "last_k_factor_change_date", "current_k_factor", "last_k_factor"])
    ) if mfm_data else pl.DataFrame({"sap_id": [], "location_name": [], "last_k_factor_change_date": [], "current_k_factor": [], "last_k_factor": []})

    # ADD after mfm_df block:
    meter_q = (
        f"last_meter_factor_change_date IS NOT NULL"
        f" AND last_meter_factor_change_date != ''"
        f" AND last_meter_factor_change_date >= '{data.start_date} 00:00:00'"
        f" AND last_meter_factor_change_date <= '{data.end_date} 23:59:59'"
    )
    meter = await hpcl_ceg_model.HostMFMFactor.get_all(
        urdhva_base.queryparams.QueryParams(q=meter_q, limit=0),
        resp_type="plain"
    )
    meter_data = meter.get("data", [])

    meter_data = [
        {k: (round(float(v), 2) if isinstance(v, decimal.Decimal) else v) for k, v in r.items()}
        for r in meter_data
    ]

    meter_df = (
        pl.DataFrame(meter_data, infer_schema_length=None)
        .select(["sap_id", "location_name", "last_meter_factor_change_date", "current_meter_factor", "last_meter_factor"])
    ) if meter_data else pl.DataFrame({"sap_id": [], "location_name": [], "last_meter_factor_change_date": [], "current_meter_factor": [], "last_meter_factor": []})


    INTERLOCK_MAP = {
        "bayreassignment": "Bay reassignment",
        "unauthorizedflow_bcu": "Unauthorized flow_BCU",
        "bcuvsmfmtotalizermismatchalarm": "BCU vs MFM totalizer mismatch alarm",
        "cancelttreported": "Cancel TT Reported",
        "unauthorizedflowalarmblend_bcu": "Unauthorized Flow Alarm Blend_BCU",
        "mfmkfactorchange": "MFM K Factor Change",
        "mfmmeterfactorchange": "MFM Meter Factor Change",
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

    df = (df.filter(pl.col("interlock_norm").is_in(list(INTERLOCK_MAP.keys()))).with_columns(
        pl.col("interlock_norm").replace(INTERLOCK_MAP).alias("interlock")))
    date_q = (
        f"created_at >= '{data.start_date} 00:00:00'"
        f" AND created_at < '{data.end_date} 23:59:59'"
    )

    # ---- Bay reassignment
    bay_df = (
        pl.DataFrame(
            (await hpcl_ceg_model.HostBayReAssignment.get_all(
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
            (await hpcl_ceg_model.HostLocalLoadedTts.get_all(
                urdhva_base.queryparams.QueryParams(q=date_q, limit=0),
                resp_type="plain"
            )).get("data", [])
        )
        .with_columns([
            pl.col("truck_number").str.strip_chars().alias("truck_number_clean"),
            pl.col("created_at").dt.date().alias("created_date")
        ])
        .with_columns([
            create_valid_vehicle_filter("truck_number_clean").alias("is_valid_truck")
        ])
        .filter(pl.col("is_valid_truck") == True)
        .group_by(["truck_number_clean", "created_date"])
        .agg([
            pl.col("bcu_number").drop_nulls().first(),
            pl.col("loaded_qty").drop_nulls().sum().alias("loaded_qty"),  # SUM the loaded_qty
            pl.col("recipe_name").str.strip_chars().drop_nulls().first(),
        ])
        .rename({"truck_number_clean": "truck_number"})
    )

    # ---- Cancel TT
    cancel_df = (
        pl.DataFrame(
            (await hpcl_ceg_model.HostCancelledTts.get_all(
                urdhva_base.queryparams.QueryParams(q=date_q, limit=0),
                resp_type="plain"
            )).get("data", []),
            infer_schema_length=None
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

            if interlock == "MFM K Factor Change":
                loc_mfm = mfm_df.filter(pl.col("location_name") == loc)
                row[interlock] = loc_mfm.height
                row[f"{interlock}_detail"] = loc_mfm.select([
                    "sap_id", "last_k_factor_change_date", "current_k_factor", "last_k_factor"
                ]).to_dicts()
                continue

            if interlock == "MFM Meter Factor Change":
                loc_meter = meter_df.filter(pl.col("location_name") == loc)
                row[interlock] = loc_meter.height
                row[f"{interlock}_detail"] = loc_meter.select([
                    "sap_id", "last_meter_factor_change_date", "current_meter_factor", "last_meter_factor"
                ]).to_dicts()
                continue

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
                if interlock == "MFM K Factor Change":
                    loc_mfm = mfm_df.filter(pl.col("location_name") == loc)
                    row[interlock] = loc_mfm.height
                    details.extend(
                        loc_mfm.select([
                            "sap_id", "last_k_factor_change_date", "current_k_factor", "last_k_factor"
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

    # ── Ensure ALL onboarded locations appear in result ──────────────────
    all_locations = await get_all_onboarded_locations()

    result_location_names = {row["Location"] for row in result}

    for loc_record in all_locations:
        loc_name = loc_record.get("name", "")
        if not loc_name or loc_name in result_location_names:
            continue
        zero_row = {"Location": loc_name}
        for interlock in INTERLOCK_MAP.values():
            zero_row[interlock] = 0
            zero_row[f"{interlock}_detail"] = []
        result.append(zero_row)

    result.sort(key=lambda x: x["Location"])

    if str(data.download).lower() == "true":
        return await vts_analytics.download_streaming_data(
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
        equipment_types = tas_queries.DEFAULT_EQUIPMENT_TYPES.copy()

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
    esd_pushbutton_query = tas_queries.build_complete_query(
        tas_queries.ESD_QUERIES["pushbutton_activated"],
        data.start_date,
        data.end_date,
        data.location_name
    )
    esd_pushbutton_params = urdhva_base.queryparams.QueryParams(q=esd_pushbutton_query, limit=0)
    esd_pushbutton_params.fields = tas_queries.ESD_FIELDS["pushbutton_activated"]

    esd_pushbutton_resp = await hpcl_ceg_model.Alerts.get_all(esd_pushbutton_params, resp_type="plain")
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

    # Build batch query for all interlocks using templat
    sap_ids_str = tas_queries.format_sap_ids_for_query(sap_ids)

    all_interlocks_query = tas_queries.ESD_QUERIES["all_interlocks_template"].format(
        sap_ids=sap_ids_str
    )

    if (data.start_date and data.end_date and
            data.start_date.strip() and data.end_date.strip() and
            data.start_date.lower() != "string" and data.end_date.lower() != "string"):
        all_interlocks_query += f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"

    if data.location_name and data.location_name.strip():
        all_interlocks_query += f" AND location_name = '{data.location_name}'"

    interlock_params = urdhva_base.queryparams.QueryParams(q=all_interlocks_query, limit=0)
    interlock_params.fields = tas_queries.ESD_FIELDS["interlocks"] + ["device_name"]  # Add device_name

    interlock_resp = await hpcl_ceg_model.Alerts.get_all(interlock_params, resp_type="plain")
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
            for category in tas_queries.ESD_CATEGORIES.keys():
                result_item[category] = [{"success": 0, "failed": 0}]
            result.append(result_item)
        return result

    # Get time window from config
    time_window_minutes = tas_queries.ESD_DEVICE_ANALYSIS_CONFIG.get("time_window_minutes", 3)

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
        for cat, pattern in tas_queries.ESD_CATEGORIES.items():
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
            is_fail = any(pattern in interlock_name for pattern in tas_queries.FAIL_PATTERNS)

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
        for category in tas_queries.ESD_CATEGORIES.keys():
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
                        for cat in tas_queries.ESD_CATEGORIES.keys():
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
                            for cat in tas_queries.ESD_CATEGORIES.keys():
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
                for category in tas_queries.ESD_CATEGORIES.keys():
                    counts = device_category_counts[device_key][category]
                    enriched_detail[category] = [counts]
                    total_count += counts["success"] + counts["failed"]
            else:
                # No alerts found for this device activation
                for category in tas_queries.ESD_CATEGORIES.keys():
                    enriched_detail[category] = [{"success": 0, "failed": 0}]

            # Add count after device_name, before categories
            enriched_detail_ordered = {
                "created_at": created_at_str,
                "device_name": device_name,
                "count": total_count
            }
            # Add all category counts
            for category in tas_queries.ESD_CATEGORIES.keys():
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
        for category in tas_queries.ESD_CATEGORIES.keys():
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
    vft_hhh_query = tas_queries.build_complete_query(
        tas_queries.VFT_QUERIES["hhh_alarm"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    vft_hhh_params = urdhva_base.queryparams.QueryParams(q=vft_hhh_query, limit=0)
    vft_hhh_params.fields = tas_queries.VFT_FIELDS["hhh_alarm"]

    vft_hhh_resp = await hpcl_ceg_model.Alerts.get_all(vft_hhh_params, resp_type="plain")
    vft_hhh_data = vft_hhh_resp.get("data", [])
    # Build other interlocks query
    alert_query = tas_queries.build_complete_query(
        tas_queries.VFT_QUERIES["other_interlocks"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    alert_params = urdhva_base.queryparams.QueryParams(q=alert_query, limit=0)
    alert_params.fields = tas_queries.VFT_FIELDS["other_interlocks"]

    alerts_resp = await hpcl_ceg_model.Alerts.get_all(alert_params, resp_type="plain")
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
            for category in tas_queries.VFT_CATEGORIES.keys():
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
        for cat, pattern in tas_queries.VFT_CATEGORIES.items():
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
        for category in tas_queries.VFT_CATEGORIES.keys():
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

        for category in tas_queries.VFT_CATEGORIES.keys():
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
    radar_activated_query = tas_queries.build_complete_query(
        tas_queries.RADAR_QUERIES["radar_activated"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    radar_activated_params = urdhva_base.queryparams.QueryParams(q=radar_activated_query, limit=0)
    radar_activated_params.fields = tas_queries.RADAR_FIELDS["radar_activated"]

    radar_activated_resp = await hpcl_ceg_model.Alerts.get_all(radar_activated_params, resp_type="plain")
    radar_activated_data = radar_activated_resp.get("data", [])
    # Build other interlocks query
    alert_query = tas_queries.build_complete_query(
        tas_queries.RADAR_QUERIES["other_interlocks"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    alert_params = urdhva_base.queryparams.QueryParams(q=alert_query, limit=0)
    alert_params.fields = tas_queries.RADAR_FIELDS["other_interlocks"]

    alerts_resp = await hpcl_ceg_model.Alerts.get_all(alert_params, resp_type="plain")
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
            for category in tas_queries.RADAR_CATEGORIES.keys():
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
        for cat, pattern in tas_queries.RADAR_CATEGORIES.items():
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
        for category in tas_queries.RADAR_CATEGORIES.keys():
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

        for category in tas_queries.RADAR_CATEGORIES.keys():
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
    bcu_alarm_query = tas_queries.build_complete_query(
        tas_queries.BCU_QUERIES["bcu_alarm"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    bcu_alarm_params = urdhva_base.queryparams.QueryParams(q=bcu_alarm_query, limit=0)
    bcu_alarm_params.fields = tas_queries.BCU_FIELDS["bcu_alarm"]

    bcu_alarm_resp = await hpcl_ceg_model.Alerts.get_all(bcu_alarm_params, resp_type="plain")
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

        if len(bcu_alarm_details[key]) < tas_queries.BCU_ALARM_DETAILS_LIMIT:
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
    interlocks_str = tas_queries.format_interlocks_for_query(tas_queries.BCU_INTERLOCKS)
    sap_ids_str = tas_queries.format_sap_ids_for_query(sap_ids)

    all_interlocks_query = tas_queries.BCU_QUERIES["all_interlocks_template"].format(
        sap_ids=sap_ids_str,
        interlocks=interlocks_str
    )

    if (data.start_date and data.end_date and
            data.start_date.strip() and data.end_date.strip() and
            data.start_date.lower() != "string" and data.end_date.lower() != "string"):
        all_interlocks_query += f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"

    interlock_params = urdhva_base.queryparams.QueryParams(q=all_interlocks_query, limit=0)
    interlock_params.fields = tas_queries.BCU_FIELDS["interlocks"]

    interlock_resp = await hpcl_ceg_model.Alerts.get_all(interlock_params, resp_type="plain")
    all_interlock_alerts = interlock_resp.get("data", [])

    # Build batch query for BCU Permissive Off using template
    permissive_query = tas_queries.BCU_QUERIES["permissive_off_template"].format(
        sap_ids=sap_ids_str
    )

    if (data.start_date and data.end_date and
            data.start_date.strip() and data.end_date.strip() and
            data.start_date.lower() != "string" and data.end_date.lower() != "string"):
        permissive_query += f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"

    permissive_params = urdhva_base.queryparams.QueryParams(q=permissive_query, limit=0)
    permissive_params.fields = tas_queries.BCU_FIELDS["permissive_off"]

    permissive_resp = await hpcl_ceg_model.Alerts.get_all(permissive_params, resp_type="plain")
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
            is_fail = any(pattern in interlock_name for pattern in tas_queries.FAIL_PATTERNS)

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
        for interlock in tas_queries.BCU_INTERLOCKS:
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
                print(
                    f"  Processed {processed_count}/{len(all_interlock_alerts)} alerts... (Success: {success_count}, Failed: {failed_count})")

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

        for interlock in tas_queries.BCU_INTERLOCKS:
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
    fire_effect_alarm_query = tas_queries.build_complete_query(
        tas_queries.FIRE_EFFECT_QUERIES["fire_effect_alarm"],
        data.start_date,
        data.end_date,
        data.location_name
    )

    fire_effect_alarm_params = urdhva_base.queryparams.QueryParams(q=fire_effect_alarm_query, limit=0)
    fire_effect_alarm_params.fields = tas_queries.FIRE_EFFECT_FIELDS["fire_effect_alarm"]

    fire_effect_alarm_resp = await hpcl_ceg_model.Alerts.get_all(fire_effect_alarm_params, resp_type="plain")
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
    sap_ids_str = tas_queries.format_sap_ids_for_query(sap_ids)

    all_interlocks_query = tas_queries.FIRE_EFFECT_QUERIES["all_interlocks_template"].format(
        sap_ids=sap_ids_str
    )

    if (data.start_date and data.end_date and
            data.start_date.strip() and data.end_date.strip() and
            data.start_date.lower() != "string" and data.end_date.lower() != "string"):
        all_interlocks_query += f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"

    interlock_params = urdhva_base.queryparams.QueryParams(q=all_interlocks_query, limit=0)
    interlock_params.fields = tas_queries.FIRE_EFFECT_FIELDS["interlocks"]

    interlock_resp = await hpcl_ceg_model.Alerts.get_all(interlock_params, resp_type="plain")
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
            for interlock in tas_queries.FIRE_EFFECT_INTERLOCKS:
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
        for interlock in tas_queries.FIRE_EFFECT_INTERLOCKS:
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
            is_fail = any(pattern in interlock_name for pattern in tas_queries.FAIL_PATTERNS)

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
        for interlock in tas_queries.FIRE_EFFECT_INTERLOCKS:
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

        for interlock in tas_queries.FIRE_EFFECT_INTERLOCKS:
            result_item[interlock] = [value[interlock]]

        final_result.append(result_item)

    final_result = sorted(final_result, key=lambda x: (x["sap_id"], x["location_name"]))

    return final_result


async def location_wise_total_loaded_qty(data):
    """
    Get location-wise total loaded quantity from host_local_loaded_tts
    Filters out records where sap_id or location_name is null/empty
    Categorizes loaded_qty by truck type: DG, PROVER, and TANK_TRUCK
    Analyzes loading patterns and enriches with indent request information
    """

    # Build query using the helper function
    query = tas_queries.build_complete_query(
        tas_queries.HOST_LOCAL_LOADED_TTS_QUERIES["location_wise_total"],
        data.start_date,
        data.end_date,
        getattr(data, 'location_name', None)
    )

    # Add optional sap_id filter if provided
    sap_id = getattr(data, 'sap_id', None)
    if sap_id and sap_id.strip():
        query += f" AND sap_id = '{sap_id}'"

    try:
        params = urdhva_base.queryparams.QueryParams(q=query, limit=0)

        # Use fields from config
        fields_to_fetch = tas_queries.HOST_LOCAL_LOADED_TTS_FIELDS.copy() if isinstance(
            tas_queries.HOST_LOCAL_LOADED_TTS_FIELDS,
            list) else list(
            tas_queries.HOST_LOCAL_LOADED_TTS_FIELDS)
        params.fields = fields_to_fetch

        resp = await hpcl_ceg_model.HostLocalLoadedTts.get_all(params, resp_type="plain")
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

        # Extract date only from created_at
        df = df.with_columns([
            pl.col("created_at_dt").dt.date().alias("load_date")
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

        # Filter valid truck numbers (pattern: alphanumeric, at least 9 characters)
        # Valid pattern example: TS08UG9576
        df = df.with_columns([
            create_valid_vehicle_filter("truck_number_clean").alias("is_valid_truck")
        ])
        # Categorize truck types using config patterns
        prover_pattern = tas_queries.TRUCK_TYPE_PATTERNS["prover"]
        dg_pattern = tas_queries.TRUCK_TYPE_PATTERNS["dg"]

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
            pl.col("created_at_dt").dt.hour().alias("load_hour"),
            pl.col("created_at_dt").dt.strftime("%Y-%m-%d %H:00:00").alias("hour_window")
        ])
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
                bay_params.fields = tas_queries.BAY_REASSIGNMENT_CONFIG["fields"]

                bay_resp = await hpcl_ceg_model.HostBayReAssignment.get_all(bay_params, resp_type="plain")
                bay_result_data = bay_resp.get("data", [])

                # Create a dictionary for quick lookup
                for bay_record in bay_result_data:
                    truck_num_raw = bay_record.get("truck_number", "")
                    created_at_raw = bay_record.get("created_at")

                    if truck_num_raw and created_at_raw:
                        # Apply same cleaning
                        truck_num_clean = str(truck_num_raw).strip()
                        truck_num_clean = re.sub(r'\s+', '', truck_num_clean).upper()

                        # Parse created_at to date only
                        try:
                            if isinstance(created_at_raw, str):
                                created_at_dt = pl.Series([created_at_raw]).str.to_datetime().to_list()[0]
                            else:
                                created_at_dt = created_at_raw

                            created_at_date = created_at_dt.date() if hasattr(created_at_dt, 'date') else created_at_dt

                            if truck_num_clean:
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
                traceback.print_exc()

        indent_data = {}  # Format: {(truck_number, date): user_id}
        location_master_data = {}  # Format: {sap_id: name}

        # Get unique valid trucks with dates for indent lookup
        valid_trucks_df = df.filter(
            (pl.col("is_valid_truck") == True) &
            (pl.col("truck_number_clean") != "")
        ).select(["truck_number_clean", "load_date"]).unique()

        if not valid_trucks_df.is_empty():
            try:
                # Query INDENT_REQUEST table from IMS_SAP schema
                # Build query for each truck + date combination
                indent_conditions = []
                for row in valid_trucks_df.iter_rows(named=True):
                    truck = row["truck_number_clean"]
                    date = row["load_date"]
                    # Escape single quotes
                    truck_escaped = truck.replace("'", "''")
                    indent_conditions.append(
                        f"(\"TRUCK_REGNO\" = '{truck_escaped}' AND DATE(\"INDENT_DATE\") = '{date}')"
                    )

                if indent_conditions:
                    # Build the query for IMS_SAP.INDENT_REQUEST
                    indent_query_conditions = " OR ".join(indent_conditions)

                    # Use the same pattern as your example
                    indent_query = f"""
                        SELECT
                            "TRUCK_REGNO",
                            "INDENT_DATE",
                            "USER_ID"
                        FROM "IMS_SAP"."INDENT_REQUEST"
                        WHERE {indent_query_conditions}
                    """
                    # Set connection parameters
                    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
                    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = "execute_query"

                    # Get the function
                    function = await charts_actions.charts_connection_vault_routing(
                        dashboard_studio_model.Charts_Connection_Vault_RoutingParams
                    )

                    # Execute the query
                    indent_results = await function(query=indent_query)

                    # Convert to list of dicts if it's a DataFrame or other format
                    if hasattr(indent_results, 'to_dict'):
                        indent_results = indent_results.to_dict('records')
                    elif not isinstance(indent_results, list):
                        indent_results = list(indent_results)

                    # Process indent results
                    user_ids = set()
                    for indent_row in indent_results:
                        # Handle both dict and asyncpg.Record format
                        truck_regno = indent_row.get("truck_regno") or indent_row.get("TRUCK_REGNO", "")
                        truck_regno = str(truck_regno).strip().replace(" ", "").upper()

                        indent_date = indent_row.get("indent_date") or indent_row.get("INDENT_DATE")
                        user_id = indent_row.get("user_id") or indent_row.get("USER_ID", "")

                        # Extract date from INDENT_DATE
                        if isinstance(indent_date, str):
                            indent_date_obj = pl.Series([indent_date]).str.to_datetime().to_list()[0]
                        else:
                            indent_date_obj = indent_date

                        indent_date_only = indent_date_obj.date() if hasattr(indent_date_obj,
                                                                             'date') else indent_date_obj

                        # Remove leading "00" from USER_ID if present
                        if user_id and user_id.startswith("00"):
                            user_id = user_id[2:]

                        # Store in indent_data
                        key = (truck_regno, str(indent_date_only))
                        indent_data[key] = user_id
                        user_ids.add(user_id)

                    # Now fetch location_master data for these USER_IDs
                    if user_ids:
                        # Build query for location_master table
                        user_ids_list = list(user_ids)
                        user_ids_str = "', '".join([uid.replace("'", "''") for uid in user_ids_list])
                        location_query = f"sap_id IN ('{user_ids_str}')"

                        location_params = urdhva_base.queryparams.QueryParams(q=location_query, limit=0)
                        location_params.fields = ["sap_id", "name"]

                        location_resp = await hpcl_ceg_model.LocationMaster.get_all(location_params, resp_type="plain")
                        location_result_data = location_resp.get("data", [])

                        # Build lookup dictionary
                        for loc_record in location_result_data:
                            sap_id_val = loc_record.get("sap_id")
                            name_val = loc_record.get("name")
                            if sap_id_val:
                                location_master_data[sap_id_val] = name_val

            except Exception as indent_err:
                print(f"Error fetching indent data: {indent_err}")
                traceback.print_exc()
        # Group by sap_id and location_name for aggregations
        result_df = (
            df.group_by(["sap_id", "location_name"])
            .agg([
                pl.col("dg_qty").sum().alias("dg"),
                pl.col("tank_truck_qty").sum().alias("tank_truck"),
                pl.col("prover_qty").sum().alias("prover"),
                (
                        pl.col("dg_qty") +
                        pl.col("tank_truck_qty") +
                        pl.col("prover_qty")
                ).sum().alias("total_loaded_qty")
            ])
            .sort(["sap_id", "location_name"])
        )

        # Get pattern analysis thresholds from config
        min_trucks_per_hour = tas_queries.PATTERN_ANALYSIS_CONFIG["local_loading_repeated"]["min_trucks_per_hour"]
        min_days_for_pattern = tas_queries.PATTERN_ANALYSIS_CONFIG["particular_time_of_day"]["min_days_for_pattern"]
        min_occurrence_ratio = tas_queries.PATTERN_ANALYSIS_CONFIG["particular_time_of_day"]["min_occurrence_ratio"]
        unique_product_count = tas_queries.PATTERN_ANALYSIS_CONFIG["particular_product"]["unique_count"]

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

            local_loading_repeated = False
            local_loading_repeated_details = []

            if "hour_window" in location_df.columns:
                # Group by load_date first, then find trucks within 2-hour window
                unique_dates = location_df.select(pl.col("load_date").unique()).to_series().to_list()

                temp_details = []
                seen_combinations = set()

                for date in unique_dates:
                    # Filter trucks for this date
                    day_df = location_df.filter(pl.col("load_date") == date)

                    # Get all valid trucks for this day with timestamps
                    day_trucks = day_df.filter(
                        (pl.col("truck_number_clean") != "")
                    ).select([
                        "truck_number_clean",
                        "created_at_dt",
                        "loaded_qty",
                        "bay_number"
                    ]).sort("created_at_dt")

                    if day_trucks.is_empty():
                        continue

                    # Convert to list for sliding window check
                    truck_rows = day_trucks.to_dicts()

                    # Filter valid tank trucks only
                    valid_rows = []
                    for r in truck_rows:
                        truck = r.get("truck_number_clean", "")
                        if not truck:
                            continue
                        is_prover = truck.startswith('P') and not any(c.isdigit() for c in truck)
                        is_dg = 'DG' in truck
                        has_letters = any(c.isalpha() for c in truck)
                        has_digits = any(c.isdigit() for c in truck)
                        if is_prover or is_dg or not (has_letters and has_digits):
                            continue
                        valid_rows.append(r)

                    # Sliding 2-hour window check
                    for i, base_row in enumerate(valid_rows):
                        base_time = base_row.get("created_at_dt")
                        if not base_time:
                            continue

                        # Find all trucks within 2 hours of base_time
                        window_trucks = []
                        for r in valid_rows:
                            compare_time = r.get("created_at_dt")
                            if not compare_time:
                                continue
                            diff_hours = abs((compare_time - base_time).total_seconds()) / 3600
                            if diff_hours <= 2:
                                window_trucks.append(r)

                        # Only process if 2+ trucks in this 2-hour window
                        unique_in_window = set(r["truck_number_clean"] for r in window_trucks)
                        if len(unique_in_window) < 2:  # Change this threshold as needed
                            continue

                        # Add trucks from this window to details
                        for r in window_trucks:
                            truck = r["truck_number_clean"]
                            created_at = r["created_at_dt"]
                            date_with_time = created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(created_at,
                                                                                                 'strftime') else str(
                                created_at)

                            unique_key = (truck, date_with_time)
                            if unique_key in seen_combinations:
                                continue
                            seen_combinations.add(unique_key)

                            # Get bay_number
                            bay_number = r.get("bay_number", "")
                            if bay_number:
                                bay_number = str(bay_number).strip().replace(" ", "").upper()

                            # Count how many times this truck appears on this date
                            truck_count_on_date = sum(
                                1 for row in valid_rows
                                if row["truck_number_clean"] == truck
                            )

                            # Sum loaded_qty for same truck + same datetime
                            total_loaded_qty = sum(
                                row["loaded_qty"] for row in valid_rows
                                if row["truck_number_clean"] == truck and row["created_at_dt"] == created_at
                            )

                            temp_details.append({
                                "date_with_time": date_with_time,
                                "truck_number": truck,
                                "loaded_qty": total_loaded_qty,
                                "bay_number": bay_number if bay_number else None,
                                "count": truck_count_on_date
                            })

                if temp_details:
                    local_loading_repeated_details = sorted(
                        temp_details,
                        key=lambda x: x['date_with_time']
                    )
                    local_loading_repeated = True

            particular_time_of_day = False
            particular_time_of_day_details = []

            if "load_hour" in location_df.columns and "load_date" in location_df.columns:
                unique_dates = location_df.select(pl.col("load_date").unique()).to_series().to_list()

                if len(unique_dates) >= min_days_for_pattern:
                    hour_frequency = (
                        location_df.group_by("load_hour")
                        .agg(pl.count().alias("hour_count"))
                        .sort("hour_count", descending=True)
                    )

                    if not hour_frequency.is_empty():
                        most_frequent_hour_count = hour_frequency.select(pl.first("hour_count")).item()

                        if most_frequent_hour_count >= max(min_days_for_pattern,
                                                           len(unique_dates) * min_occurrence_ratio):
                            pattern_detected = True

                            # Get the most frequent hour
                            most_frequent_hour = hour_frequency.select(pl.first("load_hour")).item()

                            # Collect details for trucks at that hour - ONLY VALID TANK TRUCKS
                            time_pattern_trucks = location_df.filter(
                                pl.col("load_hour") == most_frequent_hour
                            ).select([
                                "truck_number_clean",
                                "created_at_dt",
                                "load_date"
                            ]).unique()

                            pattern_dates = []
                            temp_details = []

                            for truck_row in time_pattern_trucks.iter_rows(named=True):
                                truck = truck_row.get("truck_number_clean")
                                created_at = truck_row.get("created_at_dt")
                                load_date = truck_row.get("load_date")

                                if not truck or not created_at:
                                    continue

                                # Filter: Skip PROVER (starts with P, no digits) and DG trucks
                                is_prover = truck.startswith('P') and not any(c.isdigit() for c in truck)
                                is_dg = 'DG' in truck

                                # Validate proper vehicle registration format (must have both letters AND digits)
                                has_letters = any(c.isalpha() for c in truck)
                                has_digits = any(c.isdigit() for c in truck)
                                is_valid_vehicle_format = has_letters and has_digits

                                # Only include valid tank trucks (vehicle registration format)
                                if is_prover or is_dg or not is_valid_vehicle_format:
                                    continue

                                # Format datetime as string
                                date_with_time = created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(created_at,
                                                                                                     'strftime') else str(
                                    created_at)

                                particular_time_of_day_details.append({
                                    "truck_number": truck,
                                    "date_with_time": date_with_time
                                })
                                pattern_dates.append(load_date)

                            # Only set flag to true if we have valid truck details
                            if temp_details and has_consecutive_dates(pattern_dates, min_days_for_pattern):
                                particular_time_of_day_details = temp_details
                                particular_time_of_day = True

            particular_product = False
            particular_product_details = []

            if "recipe_name" in location_df.columns:
                unique_recipes = (
                    location_df.filter(pl.col("recipe_name").is_not_null())
                    .select(pl.col("recipe_name").unique())
                    .to_series()
                    .to_list()
                )

                unique_recipes = [r for r in unique_recipes if r and str(r).strip() != ""]

                pattern_detected = len(unique_recipes) == unique_product_count

                # If pattern detected, collect details - ONLY VALID TANK TRUCKS
                if pattern_detected and unique_recipes:
                    product_trucks = location_df.filter(
                        pl.col("recipe_name").is_not_null()
                    ).select([
                        "truck_number_clean",
                        "load_date",
                        "recipe_name"
                    ]).unique()

                    for truck_row in product_trucks.iter_rows(named=True):
                        truck = truck_row.get("truck_number_clean")
                        load_date = truck_row.get("load_date")
                        recipe = truck_row.get("recipe_name")

                        if not truck:
                            continue

                        # Filter: Skip PROVER (starts with P, no digits) and DG trucks
                        is_prover = truck.startswith('P') and not any(c.isdigit() for c in truck)
                        is_dg = 'DG' in truck

                        # Validate proper vehicle registration format (must have both letters AND digits)
                        has_letters = any(c.isalpha() for c in truck)
                        has_digits = any(c.isdigit() for c in truck)
                        is_valid_vehicle_format = has_letters and has_digits

                        # Only include valid tank trucks (vehicle registration format)
                        if is_prover or is_dg or not is_valid_vehicle_format:
                            continue

                        particular_product_details.append({
                            "truck_number": truck,
                            "date": str(load_date),
                            "recipe_name": recipe
                        })

                    # Only set flag to true if we have valid truck details
                    particular_product = len(particular_product_details) > 0

            # 4. assigned_at_particular_bay logic
            assigned_at_particular_bay = False
            assigned_at_particular_bay_details = []

            # Get valid trucks for this location with bay_number
            location_trucks_with_bay = location_df.filter(
                (pl.col("is_valid_truck") == True) &
                (pl.col("truck_number_clean") != "") &
                (pl.col("bay_number").is_not_null())
            ).select([
                "truck_number_clean",
                "bay_number",
                "bcu_number",
                "created_at_dt",  # Include created_at with time instead of just load_date
                "load_date"
            ])

            if not location_trucks_with_bay.is_empty():
                # Clean bay_number - remove whitespaces and convert to uppercase
                location_trucks_with_bay = location_trucks_with_bay.with_columns([
                    pl.when(pl.col("bay_number").is_not_null())
                    .then(
                        pl.col("bay_number")
                        .cast(pl.Utf8)
                        .str.replace_all(r"\s+", "")  # Remove all whitespaces
                        .str.to_uppercase()
                    )
                    .otherwise(pl.lit(""))
                    .alias("bay_number_clean")
                ])

                # Also clean bcu_number
                location_trucks_with_bay = location_trucks_with_bay.with_columns([
                    pl.when(pl.col("bcu_number").is_not_null())
                    .then(
                        pl.col("bcu_number")
                        .cast(pl.Utf8)
                        .str.replace_all(r"\s+", "")
                        .str.to_uppercase()
                    )
                    .otherwise(pl.lit(""))
                    .alias("bcu_number_clean")
                ])

                # Filter out empty bay_numbers
                location_trucks_with_bay = location_trucks_with_bay.filter(
                    pl.col("bay_number_clean") != ""
                )

                # Remove duplicates based on truck_number and created_at (with time)
                location_trucks_with_bay = location_trucks_with_bay.unique(
                    subset=["truck_number_clean", "created_at_dt"]
                )

                if not location_trucks_with_bay.is_empty():
                    # Group by bay_number to find bays with 2+ trucks
                    bay_groups = (
                        location_trucks_with_bay.group_by("bay_number_clean")
                        .agg([
                            pl.count().alias("truck_count"),
                            pl.col("truck_number_clean").alias("trucks"),
                            pl.col("bcu_number_clean").alias("bcus"),
                            pl.col("created_at_dt").alias("timestamps"),
                            pl.col("load_date").alias("dates")
                        ])
                        .filter(pl.col("truck_count") >= 2)  # Only bays with 2+ trucks
                    )

                    if not bay_groups.is_empty():
                        # Collect details for all trucks at these particular bays
                        temp_details = []

                        for bay_row in bay_groups.iter_rows(named=True):
                            bay_number = bay_row.get("bay_number_clean")
                            trucks_list = bay_row.get("trucks", [])
                            bcus_list = bay_row.get("bcus", [])
                            timestamps_list = bay_row.get("timestamps", [])
                            dates_list = bay_row.get("dates", [])

                            # Add each truck's details - with validation
                            valid_trucks_in_bay = []
                            seen_combinations = set()  # Track unique truck+timestamp combinations

                            for i, truck in enumerate(trucks_list):
                                if not truck:
                                    continue

                                timestamp = timestamps_list[i] if i < len(timestamps_list) else None
                                if not timestamp:
                                    continue

                                # Create unique key with truck and timestamp
                                date_with_time = timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(timestamp,
                                                                                                    'strftime') else str(
                                    timestamp)
                                unique_key = (truck, date_with_time)

                                # Skip if already processed
                                if unique_key in seen_combinations:
                                    continue

                                seen_combinations.add(unique_key)

                                # ===== ADDITIONAL VALIDATION =====
                                # Filter: Skip PROVER (starts with P, no digits) and DG trucks
                                is_prover = truck.startswith('P') and not any(c.isdigit() for c in truck)
                                is_dg = 'DG' in truck

                                # Validate proper vehicle registration format (must have both letters AND digits)
                                has_letters = any(c.isalpha() for c in truck)
                                has_digits = any(c.isdigit() for c in truck)
                                is_valid_vehicle_format = has_letters and has_digits

                                # Skip invalid patterns like "ENTERDATAIT" (all letters, no digits)
                                # Skip test/dummy data patterns
                                invalid_patterns = ['ENTERDATAIT', 'ENTERDATA', 'TEST', 'DUMMY', 'NODATA']
                                is_invalid_pattern = any(pattern in truck.upper() for pattern in invalid_patterns)

                                # Only include valid tank trucks (vehicle registration format)
                                if is_prover or is_dg or not is_valid_vehicle_format or is_invalid_pattern:
                                    continue

                                bcu = bcus_list[i] if i < len(bcus_list) else ""
                                date = dates_list[i] if i < len(dates_list) else None

                                valid_trucks_in_bay.append({
                                    "truck_number": truck,
                                    "bay_number": bay_number,
                                    "bcu_number": bcu,
                                    "date": date_with_time  # Include full timestamp
                                })

                            # Only add to temp_details if this bay has 2+ VALID trucks
                            if len(valid_trucks_in_bay) >= 2:
                                temp_details.extend(valid_trucks_in_bay)

                        # Only set flag if we have valid results
                        if temp_details:
                            # Sort by bay_number, truck_number, and date for consistency
                            assigned_at_particular_bay_details = sorted(
                                temp_details,
                                key=lambda x: (x['bay_number'], x['truck_number'], x['date'])
                            )
                            assigned_at_particular_bay = True

            # 5. NEW: Get indent request details with location names
            indent_details = []

            # Get unique valid trucks for this location
            valid_trucks_for_location = location_df.filter(
                (pl.col("is_valid_truck") == True) &
                (pl.col("truck_number_clean") != "")
            ).select(["truck_number_clean", "load_date"]).unique()

            for truck_row in valid_trucks_for_location.iter_rows(named=True):
                truck = truck_row.get("truck_number_clean")
                load_date = truck_row.get("load_date")

                if not truck:
                    continue

                key = (truck, str(load_date))

                if key in indent_data:
                    user_id = indent_data[key]
                    location_name_from_master = location_master_data.get(user_id, None)

                    indent_details.append({
                        "truck_number": truck,
                        "date": str(load_date),
                        "user_id": user_id,
                        "vendor_name": location_name_from_master
                    })

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
                "local_loading_repeated_details": local_loading_repeated_details if local_loading_repeated else None,
                "particular_time_of_day": particular_time_of_day,
                "particular_time_of_day_details": particular_time_of_day_details if particular_time_of_day else None,
                "particular_product": particular_product,
                "particular_product_details": particular_product_details if particular_product else None,
                "assigned_at_particular_bay": assigned_at_particular_bay,
                "assigned_at_particular_bay_details": assigned_at_particular_bay_details if assigned_at_particular_bay else None,
                "indent_request_details": indent_details if indent_details else None
            })

        return pattern_analysis

    except Exception as e:
        print(f"Error fetching location-wise total loaded qty: {e}")
        traceback.print_exc()
        return []


async def top_five_alerts(data):
    try:
        # 1. BASE QUERY
        where_clause = "alert_section = 'TAS'"

        where_clause += (
            f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
        )

        if data.alert_status:
            where_clause += f" AND alert_status = '{data.alert_status}'"

        if data.location_name:
            where_clause += f" AND location_name = '{data.location_name}'"

        if data.alert_severity:
            if isinstance(data.alert_severity, list):
                clean_severity = [s for s in data.alert_severity if s]
                if clean_severity:
                    vals = ", ".join(f"'{s}'" for s in clean_severity)
                    where_clause += f" AND severity IN ({vals})"
            else:
                where_clause += f" AND severity = '{data.alert_severity}'"

        # 2. DRILL-DOWN (INTERLOCK CLICK)
        if data.interlock_name:
            where_clause += f" AND interlock_name = '{data.interlock_name}'"
            query = f"""
                SELECT
                    unique_id,
                    zone,
                    location_name,
                    interlock_name,
                    severity,
                    alert_status,
                    TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at,
                    FLOOR(EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400) AS ageing_days
                FROM Alerts
                WHERE {where_clause}
                ORDER BY ageing_days DESC;
            """
        # 3. TOP 5 ALERTS (NORMAL)
        else:
            where_clause += " AND interlock_name NOT IN ('BCU Permissive Off', 'BCU Permissive Off_Fail')"
            query = f"""
                SELECT
                    interlock_name,
                    COUNT(*) AS count
                FROM Alerts
                WHERE {where_clause}
                GROUP BY interlock_name
                ORDER BY count DESC
                LIMIT 5;
            """

        # 4. FETCH DATA
        result = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=0)
        result = result.get("data", [])
        return {"status": True, "message": "Top five alerts processed successfully", "data": result}
    except Exception as e:
        print(f"Error in top_five_alerts: {e}")
        return {"status": False, "message": f"Error in top_five_alerts: {e}", "data": []}


async def bcu_totalizer_diff_alert(data):
    # 1. BUILD QUERY
    conditions = []

    if data.start_date and data.end_date:
        conditions.append(
            f"date BETWEEN '{data.start_date}' AND '{data.end_date}'"
        )

    if data.location_name:
        conditions.append(
            f"location_name = '{data.location_name}'"
        )

    if data.zone:
        conditions.append(
            f"zone = '{data.zone}'"
        )

    query = " AND ".join(conditions) if conditions else ""

    # 2. QUERY PARAMS
    params = urdhva_base.queryparams.QueryParams(
        q=query,
        limit=0
    )

    params.fields = [
        "sap_id",
        "bcu_number",
        "bay_number",
        "location_name",
        "zone",
        "date",
        "bcu_mfm_net_totalizer_diff",
        "bcu_net_totalizer",
        "mfm_net_totalizer",
        "invoiced_qty",
        "invoiced_total_tl_qty_diff"
    ]

    # 3. FETCH DATA
    resp = await hpcl_ceg_model.HostDayEndDetails.get_all(params, resp_type="plain")
    records = resp.get("data", [])

    if not records:
        return []

    # 4. POLARS DATAFRAME
    df = pl.from_dicts(
        records,
        schema={
            "sap_id": pl.Utf8,
            "bcu_number": pl.Utf8,
            "bay_number": pl.Utf8,
            "location_name": pl.Utf8,
            "zone": pl.Utf8,
            "date": pl.Date,
            "bcu_mfm_net_totalizer_diff": pl.Int64,
            "bcu_net_totalizer": pl.Int64,
            "mfm_net_totalizer": pl.Int64,
            "invoiced_qty": pl.Int64,
            "invoiced_total_tl_qty_diff": pl.Int64,
        },
        strict=False
    )

    # 5. CALCULATIONS (TWO FORMULAS)
    df = df.with_columns([
        # Formula 1
        pl.when(pl.col("bcu_net_totalizer") > 0)
        .then(
            (pl.col("bcu_mfm_net_totalizer_diff") /
             pl.col("bcu_net_totalizer")).round(3)
        )
        .otherwise(None)
        .alias("MFM_VS_BCU_Totalizer_Diff"),

        # Formula 2
        pl.when(pl.col("bcu_net_totalizer") > 0)
        .then(
            (pl.col("invoiced_total_tl_qty_diff") /
             pl.col("bcu_net_totalizer")).round(3)
        )
        .otherwise(None)
        .alias("Invoice_VS_BCU_Totalizer_Diff"),
    ])

    # 6. THRESHOLD FILTER (EITHER CONDITION)
    df = df.filter(
        (pl.col("MFM_VS_BCU_Totalizer_Diff") > 0.05) |
        (pl.col("Invoice_VS_BCU_Totalizer_Diff") > 0.05)
    )

    if df.is_empty():
        return []

    # 7. FINAL RESPONSE
    result = (
        df
        .with_columns(
            pl.max_horizontal(
                "MFM_VS_BCU_Totalizer_Diff",
                "Invoice_VS_BCU_Totalizer_Diff"
            ).alias("max_diff")
        )
        .sort("max_diff", descending=True)  # sort by difference value
        .select([
            "sap_id",
            "bcu_number",
            "bay_number",
            "location_name",
            "zone",
            "date",
            "bcu_mfm_net_totalizer_diff",
            "invoiced_total_tl_qty_diff",
            "bcu_net_totalizer",
            "mfm_net_totalizer",
            "invoiced_qty",
            "MFM_VS_BCU_Totalizer_Diff",
            "Invoice_VS_BCU_Totalizer_Diff",
        ])
        .to_dicts()
    )

    return {
        "status": "success",
        "message": "BCU totalizer diff alerts fetched successfully",
        "data": result
    }


async def unauthorized_flow_dashboard(data):
    # BASE QUERY (RAW ALERTS)
    alert_query = """
        alert_section = 'TAS'
        AND interlock_name = 'Unauthorized Flow Alarm_BCU'
    """

    # Date range (mandatory)
    alert_query += (
        f" AND created_at::date BETWEEN '{data.start_date}' AND '{data.end_date}'"
    )

    # Optional filters
    if data.location_name:
        alert_query += f" AND location_name = '{data.location_name}'"

    if data.alert_status:
        alert_query += f" AND alert_status = '{data.alert_status}'"

    if data.zone:
        alert_query += f" AND zone = '{data.zone}'"

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

    alert_params.fields = [
        "location_name",
        "device_name",
        "zone",
        "created_at"
    ]

    alerts_resp = await hpcl_ceg_model.Alerts.get_all(alert_params, resp_type="plain")
    alert_data = alerts_resp.get("data", [])

    if not alert_data:
        return {
            "repeated_unauthorized_flow_count": 0,
            "locations": []
        }

    df = pl.DataFrame(alert_data)

    # REPEATED UNAUTHORIZED FLOW COUNT
    # (>2 alarms of same device on same date)
    repeated_df = (
        df
        .with_columns(pl.col("created_at").dt.date().alias("date"))
        .group_by(["location_name", "zone", "device_name", "date"])
        .agg(pl.count().alias("cnt"))
        .filter(pl.col("cnt") >= 2)
    )

    repeated_unauthorized_flow_count = repeated_df.height

    # LOCATION LEVEL AGGREGATION (NO TOP LIMIT)
    locations_df = (
        repeated_df
        .group_by(["location_name", "zone"])
        .agg(pl.sum("cnt").alias("count"))
        .sort("count", descending=True)
    )

    locations = []

    for loc in locations_df.to_dicts():
        location = loc["location_name"]
        zone = loc["zone"]

        devices = (
            repeated_df
            .filter(
                (pl.col("location_name") == location) &
                (pl.col("zone") == zone)
            )
            .select(["device_name", "date", "cnt"])
            .sort(["device_name", "date"])
            .to_dicts()
        )

        formatted_devices = [
            {
                "device_name": d["device_name"],
                "cnt": d["cnt"],
                "dates": [str(d["date"])]
            }
            for d in devices
        ]

        locations.append({
            "location_name": location,
            "count": loc["count"],
            "zone": zone,
            "devices": formatted_devices
        })

    # FINAL RESPONSE (ALL DATA)
    return {
        "status": "success",
        "message": "unauthorized flow counts",
        "data": {
            "repeated_unauthorized_flow_count": repeated_unauthorized_flow_count,
            "locations": locations
        }
    }


async def host_bay_reassignment_alert(data):
    # 1. BUILD QUERY
    conditions = []

    if data.start_date and data.end_date:
        conditions.append(
            f"date BETWEEN '{data.start_date}' AND '{data.end_date}'"
        )

    if data.location_name:
        conditions.append(
            f"location_name = '{data.location_name}'"
        )

    if data.truck_number:
        conditions.append(
            f"truck_number = '{data.truck_number}'"
        )

    query = " AND ".join(conditions) if conditions else ""

    # 2. QUERY PARAMS
    params = urdhva_base.queryparams.QueryParams(
        q=query,
        limit=0
    )

    params.fields = [
        "sap_id",
        "truck_number",
        "fan_number",
        "reassigned_bay",
        "location_name",
        "zone",
        "date"
    ]

    # 3. FETCH DATA
    resp = await hpcl_ceg_model.HostBayReAssignment.get_all(
        params,
        resp_type="plain"
    )

    records = resp.get("data", [])

    if not records:
        return {
            "status": "success",
            "message": "No host bay reassignment data found",
            "data": {
                "location_based_reassignment": []
            }
        }

    # 4. POLARS DATAFRAME
    df = pl.from_dicts(
        records,
        schema={
            "sap_id": pl.Utf8,
            "truck_number": pl.Utf8,
            "fan_number": pl.Utf8,
            "reassigned_bay": pl.Utf8,
            "location_name": pl.Utf8,
            "zone": pl.Utf8,
            "date": pl.Date,
        },
        strict=False
    )

    # 5. CLEAN DATA
    df = df.filter(pl.col("reassigned_bay").is_not_null())

    if df.is_empty():
        return {
            "status": "success",
            "message": "No valid reassigned bay records found",
            "data": {
                "location_based_reassignment": []
            }
        }

    # 6. IDENTIFY GROUPS WITH DISTINCT FAN_NUMBER >= 2
    valid_groups = (
        df.group_by([
            "sap_id",
            "location_name",
            "date",
            "reassigned_bay",
            "truck_number"
        ])
        .agg(
            pl.col("fan_number")
            .n_unique()
            .alias("distinct_fan_count")
        )
        .filter(pl.col("distinct_fan_count") >= 2)
    )

    if valid_groups.is_empty():
        return {
            "status": "success",
            "message": "No repeated bay reassignment found (distinct fan count < 2)",
            "data": {
                "location_based_reassignment": []
            }
        }

    # 7. FETCH RAW RECORDS FOR THOSE GROUPS
    final_df = (
        df.join(
            valid_groups,
            on=[
                "sap_id",
                "location_name",
                "date",
                "reassigned_bay",
                "truck_number"
            ],
            how="inner"
        )
        .unique(subset=[
            "sap_id",
            "location_name",
            "date",
            "reassigned_bay",
            "truck_number",
            "fan_number"
        ])
        .sort(["date", "reassigned_bay"])
    )
    # 8. BUILD RESPONSE (RAW ROWS)
    response = final_df.to_dicts()

    # 9. FINAL RESPONSE
    return {
        "status": "success",
        "message": "Repeated bay reassignment with distinct fan_number >= 2 fetched successfully",
        "data": {
            "location_based_reassignment": response
        }
    }


async def cancelled_tts_dashboard(data):
    # BUILD WHERE CONDITIONS
    conditions = []

    if data.filters:
        for f in data.filters:

            if not f.value:
                continue

            # Handle date range
            if f.key == "start_date":
                start_date = f.value if isinstance(f.value, str) else None
                end_date = next(
                    (x.value for x in data.filters if x.key == "end_date"),
                    None
                )

                if start_date and end_date:
                    conditions.append(
                        f"DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'"
                    )
                continue

            if f.key == "end_date":
                continue

            if isinstance(f.value, str):

                # if comma separated → split
                if "," in f.value:
                    clean_values = [v.strip() for v in f.value.split(",") if v.strip()]
                else:
                    clean_values = [f.value]

            else:
                clean_values = []

            if not clean_values:
                continue

            if f.cond == "=":
                if len(clean_values) == 1:
                    conditions.append(f"{f.key} = '{clean_values[0]}'")
                else:
                    values = ", ".join(f"'{v}'" for v in clean_values)
                    conditions.append(f"{f.key} IN ({values})")

            elif f.cond == "!=":
                if len(clean_values) == 1:
                    conditions.append(f"{f.key} != '{clean_values[0]}'")
                else:
                    values = ", ".join(f"'{v}'" for v in clean_values)
                    conditions.append(f"{f.key} NOT IN ({values})")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # COMMON CTE (Distinct Load Based)
    common_cte = f"""
        WITH base_data AS (
            SELECT *
            FROM host_cancelled_tts
            {where_clause}
        ),

        -- Top 10 locations based on DISTINCT load count
        location_totals AS (
            SELECT
                location_name,
                COUNT(DISTINCT load_number) AS total_location_raw_count
            FROM base_data
            GROUP BY location_name
            ORDER BY total_location_raw_count DESC
            LIMIT 10
        )
    """

    # DAY WISE SUMMARY (Distinct Load Based)
    day_wise_query = common_cte + """
        SELECT
            b.location_name,
            DATE(b.created_at) AS created_date,
            b.load_number,
            b.truck_number,
            b.zone,
            b.sap_id,

            SUM(b.required_qty) AS total_required_qty,

            -- DISTINCT LOAD COUNT FIXED
            COUNT(DISTINCT b.load_number) AS raw_record_count,

            STRING_AGG(DISTINCT b.customer_name, ', ') AS customer_name,
            STRING_AGG(DISTINCT b.cancelled_by, ', ') AS cancelled_by,
            STRING_AGG(DISTINCT b.remarks, ', ') AS remarks,

            lt.total_location_raw_count

        FROM base_data b
        JOIN location_totals lt
            ON b.location_name = lt.location_name

        GROUP BY
            b.location_name,
            DATE(b.created_at),
            b.load_number,
            b.truck_number,
            b.zone,
            b.sap_id,
            lt.total_location_raw_count

        ORDER BY
            lt.total_location_raw_count DESC,
            DATE(b.created_at) DESC
    """

    # TRUCK WISE SUMMARY (Distinct Load Based)
    truck_wise_query = f"""
        WITH base_data AS (
            SELECT *
            FROM host_cancelled_tts
            {where_clause}
        )
        SELECT
            location_name,
            truck_number,
            COUNT(DISTINCT load_number) AS truck_load_count
        FROM base_data
        GROUP BY location_name, truck_number
        ORDER BY truck_load_count DESC
    """

    # EXECUTE QUERIES
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = "execute_query"

    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams
    )

    day_result = await function(query=day_wise_query)
    truck_result = await function(query=truck_wise_query)

    # CLEAN NaN
    def clean_nan(data_list):
        return [
            {
                k: (None if isinstance(v, float) and math.isnan(v) else v)
                for k, v in row.items()
            }
            for row in (data_list or [])
        ]

    day_result = clean_nan(day_result)
    truck_result = clean_nan(truck_result)

    # STRUCTURE RESPONSE (Minimal Python Processing)
    location_map = defaultdict(list)

    for row in day_result:
        location_map[row["location_name"]].append(row)

    structured_day_summary = []

    for location, rows in location_map.items():

        formatted_rows = []

        for r in rows:
            formatted_rows.append({
                "created_date": r["created_date"],
                "load_number": r["load_number"],
                "truck_number": r["truck_number"],
                "total_required_qty": r["total_required_qty"],
                "raw_record_count": r["raw_record_count"],
                "customer_name": r["customer_name"],
                "cancelled_by": r["cancelled_by"],
                "remarks": r["remarks"]
            })

        structured_day_summary.append({
            "location_name": location,
            "sap_id": rows[0]["sap_id"],
            "zone": rows[0]["zone"],
            "total_location_raw_count": rows[0]["total_location_raw_count"],
            "day_wise_summary": formatted_rows
        })

    # FINAL RESPONSE
    return {
        "status": "success",
        "message": "Cancelled TTS dashboard data fetched successfully",
        "data": {
            "day_wise_summary": structured_day_summary,
            "truck_wise_summary": truck_result
        }
    }

async def sick_tts_dashboard(data):

    # BUILD WHERE CONDITIONS
    conditions = []

    if data.filters:
        for f in data.filters:

            if not f.value:
                continue

            # Handle date range
            if f.key == "start_date":
                start_date = f.value if isinstance(f.value, str) else None
                end_date = next(
                    (x.value for x in data.filters if x.key == "end_date"),
                    None
                )

                if start_date and end_date:
                    conditions.append(
                        f"DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'"
                    )
                continue

            if f.key == "end_date":
                continue

            if isinstance(f.value, str):

                if "," in f.value:
                    clean_values = [v.strip() for v in f.value.split(",") if v.strip()]
                else:
                    clean_values = [f.value]

            else:
                clean_values = []

            if not clean_values:
                continue

            if f.cond == "=":
                if len(clean_values) == 1:
                    conditions.append(f"{f.key} = '{clean_values[0]}'")
                else:
                    values = ", ".join(f"'{v}'" for v in clean_values)
                    conditions.append(f"{f.key} IN ({values})")

            elif f.cond == "!=":
                if len(clean_values) == 1:
                    conditions.append(f"{f.key} != '{clean_values[0]}'")
                else:
                    values = ", ".join(f"'{v}'" for v in clean_values)
                    conditions.append(f"{f.key} NOT IN ({values})")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # TOTAL COUNT (ALL LOCATIONS)
    total_query = f"""
        SELECT
            COUNT(DISTINCT load_number) AS total_sick_tts
        FROM host_sick_tts
        {where_clause}
    """

    # COMMON CTE FOR TOP 10 LOCATIONS
    common_cte = f"""
        WITH base_data AS (
            SELECT *
            FROM host_sick_tts
            {where_clause}
        ),

        location_totals AS (
            SELECT
                location_name,
                COUNT(DISTINCT load_number) AS total_location_raw_count
            FROM base_data
            GROUP BY location_name
            ORDER BY total_location_raw_count DESC
            LIMIT 10
        )
    """

    # LOCATION WISE SUMMARY (TOP 10)
    location_query = common_cte + """
        SELECT
            b.sap_id,
            b.location_name,
            STRING_AGG(DISTINCT b.load_number::text, ', ') AS load_number,
            COUNT(DISTINCT b.load_number) AS location_sick_count,
            lt.total_location_raw_count
        FROM base_data b
        JOIN location_totals lt
            ON b.location_name = lt.location_name
        GROUP BY
            b.sap_id,
            b.location_name,
            lt.total_location_raw_count
        ORDER BY
            lt.total_location_raw_count DESC
    """

    # VEHICLE WISE SUMMARY (ONLY TOP LOCATIONS)
    vehicle_query = common_cte + """
        SELECT
            b.sap_id,
            b.location_name,
            b.truck_number,
            STRING_AGG(DISTINCT b.load_number::text, ', ') AS load_number,
            COUNT(DISTINCT b.load_number) AS vehicle_load_count
        FROM base_data b
        JOIN location_totals lt
            ON b.location_name = lt.location_name
        GROUP BY
            b.sap_id,
            b.location_name,
            b.truck_number
        ORDER BY
            vehicle_load_count DESC
    """

    # RECORDS (ONLY TOP LOCATIONS)
    records_query = common_cte + """
        SELECT DISTINCT ON (b.load_number)
            b.load_number,
            b.truck_number,
            b.created_at,
            b.remarks,
            b.sap_id,
            b.zone,
            b.location_name,
            b.customer_name
        FROM base_data b
        JOIN location_totals lt
            ON b.location_name = lt.location_name
        ORDER BY
            b.load_number,
            b.created_at DESC
    """

    # EXECUTE QUERIES
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = "execute_query"

    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams
    )

    total_result = await function(query=total_query)
    location_result = await function(query=location_query)
    vehicle_result = await function(query=vehicle_query)
    records_result = await function(query=records_query)

    # CLEAN NaN VALUES
    def clean_nan(data_list):
        return [
            {
                k: (None if isinstance(v, float) and math.isnan(v) else v)
                for k, v in row.items()
            }
            for row in (data_list or [])
        ]

    location_result = clean_nan(location_result)
    vehicle_result = clean_nan(vehicle_result)
    records_result = clean_nan(records_result)

    # SAFE TOTAL FETCH
    total_sick_tts = 0
    if total_result and len(total_result) > 0:
        total_sick_tts = total_result[0].get("total_sick_tts", 0)

    # FINAL RESPONSE
    return {
        "status": "success",
        "message": "Sick TTS dashboard data fetched successfully",
        "data": {
            "total_sick_tts": total_sick_tts,
            "location_wise_summary": location_result,
            "vehicle_wise_summary": vehicle_result,
            "records": records_result
        }
    }


async def repeated_sick_cross_verification(data):

    # ---------------- FILTER BUILD ----------------
    conditions = []

    if data.filters:
        for f in data.filters:

            if not f.value:
                continue

            if f.key == "start_date":
                start_date = f.value if isinstance(f.value, str) else None
                end_date = next(
                    (x.value for x in data.filters if x.key == "end_date"),
                    None
                )

                if start_date and end_date:
                    conditions.append(
                        f"DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'"
                    )
                continue

            if f.key == "end_date":
                continue

            if isinstance(f.value, str):
                if "," in f.value:
                    clean_values = [v.strip() for v in f.value.split(",") if v.strip()]
                else:
                    clean_values = [f.value]
            else:
                clean_values = []

            if not clean_values:
                continue

            if f.cond == "=":
                if len(clean_values) == 1:
                    conditions.append(f"{f.key} = '{clean_values[0]}'")
                else:
                    values = ", ".join(f"'{v}'" for v in clean_values)
                    conditions.append(f"{f.key} IN ({values})")

            elif f.cond == "!=":
                if len(clean_values) == 1:
                    conditions.append(f"{f.key} != '{clean_values[0]}'")
                else:
                    values = ", ".join(f"'{v}'" for v in clean_values)
                    conditions.append(f"{f.key} NOT IN ({values})")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # ---------------- COMMON DATASET ----------------
    common_cte = f"""
        WITH combined_data AS (

            SELECT DISTINCT
                load_number,
                truck_number,
                location_name,
                customer_name,
                sap_id,
                zone,
                created_at,
                'SICK_TT' AS record_type
            FROM host_sick_tts
            {where_clause}

            UNION ALL

            SELECT DISTINCT
                load_number,
                truck_number,
                location_name,
                customer_name,
                sap_id,
                zone,
                created_at,
                'CANCELLED_TT' AS record_type
            FROM host_cancelled_tts
            {where_clause}
        )
    """

    # ---------------- LOCATION WISE (PIVOT) ----------------
    location_query = common_cte + """
        SELECT
            location_name,

            COUNT(DISTINCT CASE
                WHEN record_type = 'SICK_TT'
                THEN load_number
            END) AS sick_tt_count,

            COUNT(DISTINCT CASE
                WHEN record_type = 'CANCELLED_TT'
                THEN load_number
            END) AS cancelled_tt_count

        FROM combined_data
        GROUP BY location_name
        ORDER BY cancelled_tt_count DESC, sick_tt_count DESC
    """

    # ---------------- VEHICLE WISE (PIVOT) ----------------
    vehicle_query = common_cte + """
        SELECT
            truck_number,
            customer_name,

            COUNT(DISTINCT CASE
                WHEN record_type = 'SICK_TT'
                THEN load_number
            END) AS sick_tt_count,

            COUNT(DISTINCT CASE
                WHEN record_type = 'CANCELLED_TT'
                THEN load_number
            END) AS cancelled_tt_count

        FROM combined_data
        GROUP BY truck_number, customer_name
        ORDER BY cancelled_tt_count DESC, sick_tt_count DESC
    """

    # ---------------- CUSTOMER WISE (PIVOT) ----------------
    customer_query = common_cte + """
        SELECT
            customer_name,

            COUNT(DISTINCT CASE
                WHEN record_type = 'SICK_TT'
                THEN load_number
            END) AS sick_tt_count,

            COUNT(DISTINCT CASE
                WHEN record_type = 'CANCELLED_TT'
                THEN load_number
            END) AS cancelled_tt_count

        FROM combined_data
        GROUP BY customer_name
        ORDER BY cancelled_tt_count DESC, sick_tt_count DESC
    """

    # ---------------- RECORD DETAILS ----------------
    records_query = common_cte + """
        SELECT DISTINCT ON (load_number, record_type)
            load_number,
            truck_number,
            location_name,
            customer_name,
            sap_id,
            zone,
            created_at,
            record_type
        FROM combined_data
        ORDER BY load_number, record_type, created_at DESC
    """

    # ---------------- EXECUTION ----------------
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = "execute_query"

    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams
    )

    location_result = await function(query=location_query)
    vehicle_result = await function(query=vehicle_query)
    customer_result = await function(query=customer_query)
    records_result = await function(query=records_query)

    # ---------------- FINAL RESPONSE ----------------
    return {
        "status": "success",
        "message": "Sick & Cancelled TT combined dashboard fetched successfully",
        "data": {
            "location_wise_summary": location_result,
            "vehicle_wise_summary": vehicle_result,
            "customer_wise_summary": customer_result,
            "records": records_result
        }
    }
    
async def over_loaded_tts_dashboard(data):

    # BUILD WHERE CONDITIONS
    conditions = []

    # ALWAYS APPLY LAST 7 DAYS CONDITION
    conditions.append("created_at >= CURRENT_DATE - INTERVAL '7 days'")

    if data.filters:
        for f in data.filters:

            if not f.value:
                continue

            if isinstance(f.value, str):

                if "," in f.value:
                    clean_values = [v.strip() for v in f.value.split(",") if v.strip()]
                else:
                    clean_values = [f.value]

            else:
                clean_values = []

            if not clean_values:
                continue

            if f.cond == "=":
                if len(clean_values) == 1:
                    conditions.append(f"{f.key} = '{clean_values[0]}'")
                else:
                    values = ", ".join(f"'{v}'" for v in clean_values)
                    conditions.append(f"{f.key} IN ({values})")

            elif f.cond == "!=":
                if len(clean_values) == 1:
                    conditions.append(f"{f.key} != '{clean_values[0]}'")
                else:
                    values = ", ".join(f"'{v}'" for v in clean_values)
                    conditions.append(f"{f.key} NOT IN ({values})")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # TOTAL COUNT
    total_query = f"""
        SELECT
            COUNT(DISTINCT load_number) AS total_over_loaded
        FROM host_over_loaded_tts
        {where_clause}
    """

    # COMMON CTE
    common_cte = f"""
        WITH base_data AS (
            SELECT *
            FROM host_over_loaded_tts
            {where_clause}
        ),

        location_totals AS (
            SELECT
                location_name,
                COUNT(DISTINCT load_number) AS location_overload_count
            FROM base_data
            GROUP BY location_name
            ORDER BY location_overload_count DESC
            LIMIT 10
        )
    """

    # LOCATION WISE SUMMARY
    location_query = common_cte + """
        SELECT
            b.location_name,
            COUNT(DISTINCT b.load_number) AS location_overload_count,
            SUM(b.loaded_qty - b.required_qty) AS cumulative_excess_qty
        FROM base_data b
        JOIN location_totals lt
            ON b.location_name = lt.location_name
        GROUP BY
            b.location_name
        ORDER BY
            location_overload_count DESC
    """
    repeat_truck_query = f"""
        SELECT
            truck_number,
            location_name,
            COUNT(*) AS overload_count
        FROM host_over_loaded_tts
        {where_clause}
        GROUP BY truck_number, location_name
        HAVING COUNT(*) > 5
        ORDER BY overload_count DESC
    """
    records_query = common_cte + """
        SELECT
            b.load_number,
            b.truck_number,
            b.compartment_number,
            b.product_name,
            b.required_qty,
            b.loaded_qty,
            (b.loaded_qty - b.required_qty) AS excess_qty,

            COUNT(*) OVER (
                PARTITION BY b.location_name, b.load_number, b.bcu_number
            ) AS repeat_count,

            b.sap_id,
            b.zone,
            b.location_name,
            b.created_at,
            b.bcu_number

        FROM base_data b
        JOIN location_totals lt
            ON b.location_name = lt.location_name

        ORDER BY b.created_at DESC
    """

    # EXECUTE QUERIES
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
    dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = "execute_query"

    function = await charts_actions.charts_connection_vault_routing(
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams
    )

    total_result = await function(query=total_query)
    location_result = await function(query=location_query)
    # bcu_result = await function(query=bcu_repeat_query)
    records_result = await function(query=records_query)
    repeat_truck_result = await function(query=repeat_truck_query)

    # CLEAN NaN VALUES
    def clean_nan(data_list):
        return [
            {
                k: (None if isinstance(v, float) and math.isnan(v) else v)
                for k, v in row.items()
            }
            for row in (data_list or [])
        ]

    location_result = clean_nan(location_result)
    # bcu_result = clean_nan(bcu_result)
    records_result = clean_nan(records_result)
    repeat_truck_result = clean_nan(repeat_truck_result)

    # SAFE TOTAL FETCH
    total_over_loaded = 0
    if total_result and len(total_result) > 0:
        total_over_loaded = total_result[0].get("total_over_loaded", 0)

    # FINAL RESPONSE
    return {
        "status": "success",
        "message": "Over Loaded TTS dashboard data fetched successfully",
        "data": {
                "total_over_loaded": total_over_loaded,
                "location_wise_summary": location_result,
                "repeated_overload_trucks": repeat_truck_result,
                "records": records_result
            }
    }
    
def is_bay_empty(bay_data):
    return (
            bay_data.get("HostBayReAssignment", 0) == 0 and
            bay_data.get("LocalLoading", 0) == 0 and
            bay_data.get("OverLoading", 0) == 0 and
            bay_data.get("Alerts_Count", 0) == 0 and
            bay_data.get("Gantry_Permissive_off_Count", 0) == 0 and
            bay_data.get("MFM_VS_BCU", 0) == 0 and
            bay_data.get("BCU_VS_INVOICE", 0) == 0 and
            bay_data.get("HostUnauthorisedFlow_count", 0) == 0
    )


def calc_unauthorised_net_totalizer(df):
    if len(df) == 0 or "net_totalizer" not in df.columns:
        return 0.0
    df_with_date = df.with_columns(
        pl.col("created_at").cast(pl.Date).alias("date")
    )
    latest_per_day = (
        df_with_date.sort("created_at", descending=True)
        .group_by("date")
        .first()
        .filter(pl.col("net_totalizer") > 0)
    )
    if len(latest_per_day) == 0:
        return 0.0
    return round(float(latest_per_day.select(pl.col("net_totalizer").sum()).item()), 2)


def get_unauthorised_flow_for_bay_date(unauthorised_flow_df, date, bay_number_str):
    unauthorised_flow_count = 0
    unauthorised_flow_net_totalizer = 0.0
    unauthorised_flow_details = []

    if len(unauthorised_flow_df) == 0:
        return unauthorised_flow_count, unauthorised_flow_net_totalizer, unauthorised_flow_details

    filtered = unauthorised_flow_df.filter(
        (pl.col("created_at").cast(pl.Date) == date) &
        (pl.col("bay_number") == bay_number_str)
    )

    if len(filtered) == 0:
        return unauthorised_flow_count, unauthorised_flow_net_totalizer, unauthorised_flow_details

    unauthorised_flow_count = len(filtered)

    for row in filtered.sort("created_at", descending=False).iter_rows(named=True):
        unauthorised_flow_details.append({
            "location_name": row.get("location_name"),
            "bay_number": row.get("bay_number"),
            "bcu_number": row.get("bcu_number"),
            "created_at": str(row.get("created_at")),
            "start_totalizer": row.get("start_totalizer"),
            "end_totalizer": row.get("end_totalizer"),
            "net_totalizer": row.get("net_totalizer"),
        })

    unauthorised_flow_net_totalizer = calc_unauthorised_net_totalizer(filtered)

    return unauthorised_flow_count, unauthorised_flow_net_totalizer, unauthorised_flow_details


async def host_tables_combined_data(data):
    try:
        combined_df, alerts_df, day_end_df, total_bcu_count, total_active_bays_count, unauthorised_flow_df = \
            await tas_host_data.fetch_host_tables_as_dfs(data)

        selected_bay = None
        if hasattr(data, "filters") and data.filters:
            for f in data.filters:
                if getattr(f, "key", None) == "bay":
                    selected_bay = str(getattr(f, "value", "")).zfill(2)

        combined_df_is_empty = combined_df is None or combined_df.is_empty()

        result = []

        total_unauthorised_flow_count = len(unauthorised_flow_df) if len(unauthorised_flow_df) > 0 else 0

        total_counts = {
            "TotalBCU": total_bcu_count,
            "TotalActiveBays": total_active_bays_count,
            "HostBayReAssignment": 0,
            "LocalLoading": 0,
            "OverLoading": 0,
            "TotalUniqueTruckNumbersCount": 0,
            "UnauthorisedFlow": total_unauthorised_flow_count
        }

        if not combined_df_is_empty:
            combined_df = combined_df.with_columns(
                pl.col("created_at").cast(pl.Utf8).str.slice(0, 10).str.to_date("%Y-%m-%d").alias("date")
            )
            unique_dates = combined_df.select("date").unique().sort("date")
            unique_truck_count = combined_df.select("truck_number").unique().height

            total_counts.update({
                "HostBayReAssignment": len(combined_df.filter(pl.col("table_name") == "HostBayReAssignment")),
                "LocalLoading": len(combined_df.filter(pl.col("table_name") == "HostLocalLoaded")),
                "OverLoading": len(combined_df.filter(pl.col("table_name") == "HostOverLoaded")),
                "TotalUniqueTruckNumbersCount": unique_truck_count,
            })

            for date_row in unique_dates.iter_rows(named=True):
                date = date_row.get("date")
                date_df = combined_df.filter(pl.col("date") == date)

                # ── Gantry calculation (date-level) ──────────────────────────
                gantry_count_for_date = 0
                gantry_details_for_date = []
                if len(alerts_df) > 0:
                    filtered_gantry_date = alerts_df.filter(
                        (pl.col("created_at").cast(pl.Date) == date) &
                        (pl.col("interlock_name").str.contains("Gantry Permissive Off")) &
                        (~pl.col("interlock_name").str.contains("Fail"))
                    )
                    if len(filtered_gantry_date) > 0:
                        deduplicated_gantry = filtered_gantry_date.unique(
                            subset=["created_at", "interlock_name"],
                            keep="last"
                        ).sort("created_at", descending=True)

                        gantry_count_for_date = len(deduplicated_gantry)

                        for alert_row in deduplicated_gantry.iter_rows(named=True):
                            created_at = alert_row.get("created_at")
                            closed_at = alert_row.get("closed_at")
                            downtime_formatted = None
                            if created_at and closed_at:
                                time_diff = closed_at - created_at
                                total_seconds = int(time_diff.total_seconds())
                                days_td = total_seconds // 86400
                                hours = (total_seconds % 86400) // 3600
                                minutes = (total_seconds % 3600) // 60
                                seconds = total_seconds % 60
                                parts = []
                                if days_td > 0:
                                    parts.append(f"{days_td} day{'s' if days_td != 1 else ''}")
                                if hours > 0:
                                    parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                                if minutes > 0:
                                    parts.append(f"{minutes} min{'s' if minutes != 1 else ''}")
                                if seconds > 0 or not parts:
                                    parts.append(f"{seconds} sec{'s' if seconds != 1 else ''}")
                                downtime_formatted = " ".join(parts)

                            gantry_details_for_date.append({
                                "created_at": str(alert_row.get("created_at")),
                                "closed_at": str(alert_row.get("closed_at")) if alert_row.get("closed_at") else None,
                                "Downtime": downtime_formatted,
                                "interlock_name": alert_row.get("interlock_name"),
                                "device_name": alert_row.get("device_name"),
                                "location_name": alert_row.get("location_name"),
                                "sap_id": alert_row.get("sap_id"),
                            })

                # ── unique bays from combined_df ──────────────────────────────
                if selected_bay:
                    unique_bays = date_df.filter(
                        pl.col("assigned_bay").cast(pl.Utf8).str.zfill(2) == selected_bay
                    ).select("assigned_bay").unique().sort("assigned_bay")
                else:
                    unique_bays = date_df.select("assigned_bay").unique().sort("assigned_bay")

                # ── Filter out bay numbers > 30 ───────────────────────────────────
                unique_bays = unique_bays.filter(
                    pl.col("assigned_bay").cast(pl.Utf8).str.zfill(2).cast(pl.Int32, strict=False) <= 30
                )

                bays_data = []

                for bay_row in unique_bays.iter_rows(named=True):
                    bay_number = bay_row.get("assigned_bay")
                    bay_number_str = str(bay_number).zfill(2)

                    bay_df = date_df.filter(
                        pl.col("assigned_bay").cast(pl.Utf8).str.zfill(2) == bay_number_str
                    )

                    table_data = {}
                    for table_name in ["HostBayReAssignment", "HostLocalLoaded", "HostOverLoaded"]:
                        table_df = bay_df.filter(pl.col("table_name") == table_name)
                        trucks = []
                        for truck_row in table_df.iter_rows(named=True):
                            if table_name == "HostBayReAssignment":
                                truck_data = {
                                    "truck_number": truck_row.get("truck_number"),
                                    "created_at": str(truck_row.get("created_at")),
                                    "load_number": truck_row.get("load_number"),
                                    "location_name": truck_row.get("location_name"),
                                    "product_name": truck_row.get("product_name"),
                                    "required_qty": truck_row.get("required_qty"),
                                    "assigned_bay": truck_row.get("assigned_bay"),
                                    "reassigned_bay": truck_row.get("reassigned_bay")
                                }
                            else:
                                truck_data = {
                                    "truck_number": truck_row.get("truck_number"),
                                    "created_at": str(truck_row.get("created_at")),
                                    "load_number": truck_row.get("load_number"),
                                    "location_name": truck_row.get("location_name"),
                                    "product_name": truck_row.get("product_name"),
                                    "required_qty": truck_row.get("required_qty"),
                                    "loaded_qty": truck_row.get("loaded_qty"),
                                    "overloaded_qty": truck_row.get("overloaded_qty"),
                                    "cumulative_loaded_qty": truck_row.get("cumulative_loaded_qty")
                                }
                            trucks.append(truck_data)
                        table_data[table_name] = {"count": len(trucks), "trucks": trucks}

                    # ── Alerts for this bay (Phase 1) ─────────────────────────
                    alerts_count_bay, alerts_count_details_bay = get_alerts_for_bay_date(
                        alerts_df, date, bay_number_str
                    )

                    unauth_count, unauth_net, unauth_details = get_unauthorised_flow_for_bay_date(
                        unauthorised_flow_df, date, bay_number_str
                    )

                    total_count = len(bay_df) + alerts_count_bay + gantry_count_for_date

                    bay_data = {
                        "bay_number": bay_number,
                        "total_count": total_count,
                        "HostBayReAssignment": table_data["HostBayReAssignment"]["count"],
                        "HostBayReAssignment_details": table_data["HostBayReAssignment"]["trucks"],
                        "LocalLoading": table_data["HostLocalLoaded"]["count"],
                        "LocalLoading_details": table_data["HostLocalLoaded"]["trucks"],
                        "OverLoading": table_data["HostOverLoaded"]["count"],
                        "OverLoading_details": table_data["HostOverLoaded"]["trucks"],
                        "Alerts_Count": alerts_count_bay,
                        # "Gantry_Permissive_off_Count": gantry_count_for_date,
                        "MFM_VS_BCU": 0,
                        "BCU_VS_INVOICE": 0,
                        "HostUnauthorisedFlow_count": unauth_count,
                        "Cross_checked_ManuallyAP_system": 0,
                    }

                    if alerts_count_bay > 0:
                        bay_data["Alerts_Count_details"] = alerts_count_details_bay
                    if gantry_count_for_date > 0:
                        bay_data["Gantry_Permissive_off_Count_details"] = gantry_details_for_date
                    if unauth_count > 0:
                        bay_data["HostUnauthorisedFlow_details"] = unauth_details

                    if not is_bay_empty(bay_data):
                        bays_data.append(bay_data)

                if bays_data:
                    result.append({"date": str(date), "bays": bays_data})

        # ── Phase 2: Process day_end_df ───────────────────────────────────────
        if len(day_end_df) > 0:
            day_end_df_with_date = day_end_df.with_columns(
                pl.col("created_at").cast(pl.Date).alias("date")
            )
            unique_day_end_dates = day_end_df_with_date.select("date").unique().sort("date")
            existing_dates = {r["date"] for r in result}

            for date_row in unique_day_end_dates.iter_rows(named=True):
                date = date_row.get("date")
                day_end_for_date = day_end_df_with_date.filter(pl.col("date") == date)

                # ── Gantry for this date ──────────────────────────────────────
                gantry_count_for_date = 0
                gantry_details_for_date = []
                if len(alerts_df) > 0:
                    filtered_gantry_date = alerts_df.filter(
                        (pl.col("created_at").cast(pl.Date) == date) &
                        (pl.col("interlock_name").str.contains("Gantry Permissive Off")) &
                        (~pl.col("interlock_name").str.contains("Fail"))
                    )
                    if len(filtered_gantry_date) > 0:
                        deduplicated_gantry = filtered_gantry_date.unique(
                            subset=["created_at", "interlock_name"],
                            keep="last"
                        ).sort("created_at", descending=True)
                        gantry_count_for_date = len(deduplicated_gantry)
                        for alert_row in deduplicated_gantry.iter_rows(named=True):
                            created_at = alert_row.get("created_at")
                            closed_at = alert_row.get("closed_at")
                            downtime_formatted = None
                            if created_at and closed_at:
                                time_diff = closed_at - created_at
                                total_seconds = int(time_diff.total_seconds())
                                days_td = total_seconds // 86400
                                hours = (total_seconds % 86400) // 3600
                                minutes = (total_seconds % 3600) // 60
                                seconds = total_seconds % 60
                                parts = []
                                if days_td > 0:
                                    parts.append(f"{days_td} day{'s' if days_td != 1 else ''}")
                                if hours > 0:
                                    parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                                if minutes > 0:
                                    parts.append(f"{minutes} min{'s' if minutes != 1 else ''}")
                                if seconds > 0 or not parts:
                                    parts.append(f"{seconds} sec{'s' if seconds != 1 else ''}")
                                downtime_formatted = " ".join(parts)
                            gantry_details_for_date.append({
                                "created_at": str(alert_row.get("created_at")),
                                "closed_at": str(alert_row.get("closed_at")) if alert_row.get("closed_at") else None,
                                "Downtime": downtime_formatted,
                                "interlock_name": alert_row.get("interlock_name"),
                                "device_name": alert_row.get("device_name"),
                                "location_name": alert_row.get("location_name"),
                                "sap_id": alert_row.get("sap_id"),
                            })

                if selected_bay:
                    unique_bays = day_end_for_date.filter(
                        pl.col("bay_number_extracted").cast(pl.Utf8).str.zfill(2) == selected_bay
                    ).select(pl.col("bay_number_extracted").alias("bay")).unique().sort("bay")
                else:
                    unique_bays = day_end_for_date.select(
                        pl.col("bay_number_extracted").alias("bay")
                    ).unique().sort("bay")

                bays_data = []

                for bay_row in unique_bays.iter_rows(named=True):
                    bay_number_str = str(bay_row.get("bay")).zfill(2)

                    # ── MFM_VS_BCU ────────────────────────────────────────────
                    mfm_vs_bcu_bay = 0
                    mfm_vs_bcu_details_bay = []
                    filtered_mfm = day_end_for_date.filter(
                        (pl.col("bay_number_extracted").cast(pl.Utf8).str.zfill(2) == bay_number_str) &
                        pl.col('bcu_mfm_net_totalizer_diff').is_not_null() &
                        (pl.col('bcu_mfm_net_totalizer_diff') != 0)
                    ).sort("created_at", descending=True)
                    for row in filtered_mfm.iter_rows(named=True):
                        mfm_vs_bcu_details_bay.append({
                            "created_at": str(row.get("created_at")),
                            "bcu_number": row.get("bcu_number"),
                            "bay_number": row.get("bay_number"),
                            "bcu_net_totalizer": row.get("bcu_net_totalizer"),
                            "mfm_net_totalizer": row.get("mfm_net_totalizer"),
                            "difference": row.get("bcu_mfm_net_totalizer_diff")
                        })
                    mfm_vs_bcu_bay = len(mfm_vs_bcu_details_bay)

                    # ── BCU_VS_INVOICE ────────────────────────────────────────
                    bcu_vs_invoice_bay = 0
                    bcu_vs_invoice_details_bay = []
                    filtered_invoice = day_end_for_date.filter(
                        (pl.col("bay_number_extracted").cast(pl.Utf8).str.zfill(2) == bay_number_str) &
                        pl.col('invoiced_bcu_net_qty_diff').is_not_null() &
                        (pl.col('invoiced_bcu_net_qty_diff') != 0)
                    ).sort("created_at", descending=True)
                    for row in filtered_invoice.iter_rows(named=True):
                        bcu_vs_invoice_details_bay.append({
                            "created_at": str(row.get("created_at")),
                            "bcu_number": row.get("bcu_number"),
                            "bay_number": row.get("bay_number"),
                            "bcu_net_totalizer": row.get("bcu_net_totalizer"),
                            "invoiced_qty": row.get("invoiced_qty"),
                            "difference": row.get("invoiced_bcu_net_qty_diff")
                        })
                    bcu_vs_invoice_bay = len(bcu_vs_invoice_details_bay)

                    # ── Alerts for this bay (Phase 2) ─────────────────────────
                    alerts_count_bay, alerts_count_details_bay = get_alerts_for_bay_date(
                        alerts_df, date, bay_number_str
                    )

                    # ── Unauthorised flow ─────────────────────────────────────
                    unauth_count, unauth_net, unauth_details = get_unauthorised_flow_for_bay_date(
                        unauthorised_flow_df, date, bay_number_str
                    )

                    bays_data.append({
                        "bay_number": bay_number_str,
                        "MFM_VS_BCU": mfm_vs_bcu_bay,
                        "MFM_VS_BCU_details": mfm_vs_bcu_details_bay if mfm_vs_bcu_bay > 0 else [],
                        "BCU_VS_INVOICE": bcu_vs_invoice_bay,
                        "BCU_VS_INVOICE_details": bcu_vs_invoice_details_bay if bcu_vs_invoice_bay > 0 else [],
                        "Alerts_Count": alerts_count_bay,
                        "Alerts_Count_details": alerts_count_details_bay if alerts_count_bay > 0 else [],
                        # "Gantry_Permissive_off_Count": gantry_count_for_date,
                        # "Gantry_Permissive_off_Count_details": gantry_details_for_date if gantry_count_for_date > 0 else [],
                        "HostUnauthorisedFlow_count": unauth_count,
                        "HostUnauthorisedFlow_details": unauth_details,
                    })

                # ── Merge Phase 2 bays into existing result ───────────────────
                if str(date) in existing_dates:
                    for existing in result:
                        if existing["date"] == str(date):
                            for new_bay in bays_data:
                                matched = next(
                                    (b for b in existing["bays"] if
                                     str(b["bay_number"]).zfill(2) == new_bay["bay_number"]),
                                    None
                                )
                                if matched:
                                    matched["MFM_VS_BCU"] = new_bay["MFM_VS_BCU"]
                                    matched["BCU_VS_INVOICE"] = new_bay["BCU_VS_INVOICE"]
                                    if new_bay["MFM_VS_BCU"] > 0:
                                        matched["MFM_VS_BCU_details"] = new_bay["MFM_VS_BCU_details"]
                                    if new_bay["BCU_VS_INVOICE"] > 0:
                                        matched["BCU_VS_INVOICE_details"] = new_bay["BCU_VS_INVOICE_details"]
                                    if matched.get("HostUnauthorisedFlow_count", 0) == 0 and new_bay[
                                        "HostUnauthorisedFlow_count"] > 0:
                                        matched["HostUnauthorisedFlow_count"] = new_bay["HostUnauthorisedFlow_count"]
                                        matched["HostUnauthorisedFlow_details"] = new_bay[
                                            "HostUnauthorisedFlow_details"]
                                    if matched.get("Alerts_Count", 0) == 0 and new_bay["Alerts_Count"] > 0:
                                        matched["Alerts_Count"] = new_bay["Alerts_Count"]
                                        matched["Alerts_Count_details"] = new_bay["Alerts_Count_details"]
                                    # if matched.get("Gantry_Permissive_off_Count", 0) == 0 and new_bay["Gantry_Permissive_off_Count"] > 0:
                                    # matched["Gantry_Permissive_off_Count"] = new_bay["Gantry_Permissive_off_Count"]
                                    # matched["Gantry_Permissive_off_Count_details"] = new_bay["Gantry_Permissive_off_Count_details"]
                                else:
                                    new_entry = {
                                        "bay_number": new_bay["bay_number"],
                                        "total_count": (
                                                new_bay["MFM_VS_BCU"] +
                                                new_bay["BCU_VS_INVOICE"] +
                                                new_bay["HostUnauthorisedFlow_count"] +
                                                new_bay["Alerts_Count"]
                                            # new_bay["Gantry_Permissive_off_Count"]
                                        ),
                                        "HostBayReAssignment": 0,
                                        "HostBayReAssignment_details": [],
                                        "LocalLoading": 0,
                                        "LocalLoading_details": [],
                                        "OverLoading": 0,
                                        "OverLoading_details": [],
                                        "Alerts_Count": new_bay["Alerts_Count"],
                                        # "Gantry_Permissive_off_Count": new_bay["Gantry_Permissive_off_Count"],
                                        "MFM_VS_BCU": new_bay["MFM_VS_BCU"],
                                        "MFM_VS_BCU_details": new_bay["MFM_VS_BCU_details"],
                                        "BCU_VS_INVOICE": new_bay["BCU_VS_INVOICE"],
                                        "BCU_VS_INVOICE_details": new_bay["BCU_VS_INVOICE_details"],
                                        "HostUnauthorisedFlow_count": new_bay["HostUnauthorisedFlow_count"],
                                        "Cross_checked_ManuallyAP_system": 0,
                                    }
                                    if new_bay["Alerts_Count"] > 0:
                                        new_entry["Alerts_Count_details"] = new_bay["Alerts_Count_details"]
                                    # if new_bay["Gantry_Permissive_off_Count"] > 0:
                                    # new_entry["Gantry_Permissive_off_Count_details"] = new_bay["Gantry_Permissive_off_Count_details"]
                                    if new_bay["HostUnauthorisedFlow_count"] > 0:
                                        new_entry["HostUnauthorisedFlow_details"] = new_bay[
                                            "HostUnauthorisedFlow_details"]
                                    if not is_bay_empty(new_entry):
                                        existing["bays"].append(new_entry)
                else:
                    new_bays = []
                    for new_bay in bays_data:
                        new_entry = {
                            "bay_number": new_bay["bay_number"],
                            "total_count": (
                                    new_bay["MFM_VS_BCU"] +
                                    new_bay["BCU_VS_INVOICE"] +
                                    new_bay["HostUnauthorisedFlow_count"] +
                                    new_bay["Alerts_Count"]
                                # new_bay["Gantry_Permissive_off_Count"]
                            ),
                            "HostBayReAssignment": 0,
                            "HostBayReAssignment_details": [],
                            "LocalLoading": 0,
                            "LocalLoading_details": [],
                            "OverLoading": 0,
                            "OverLoading_details": [],
                            "Alerts_Count": new_bay["Alerts_Count"],
                            # "Gantry_Permissive_off_Count": new_bay["Gantry_Permissive_off_Count"],
                            "MFM_VS_BCU": new_bay["MFM_VS_BCU"],
                            "MFM_VS_BCU_details": new_bay["MFM_VS_BCU_details"],
                            "BCU_VS_INVOICE": new_bay["BCU_VS_INVOICE"],
                            "BCU_VS_INVOICE_details": new_bay["BCU_VS_INVOICE_details"],
                            "HostUnauthorisedFlow_count": new_bay["HostUnauthorisedFlow_count"],
                            "Cross_checked_ManuallyAP_system": 0,
                        }
                        if new_bay["Alerts_Count"] > 0:
                            new_entry["Alerts_Count_details"] = new_bay["Alerts_Count_details"]
                        # if new_bay["Gantry_Permissive_off_Count"] > 0:
                        # new_entry["Gantry_Permissive_off_Count_details"] = new_bay["Gantry_Permissive_off_Count_details"]
                        if new_bay["HostUnauthorisedFlow_count"] > 0:
                            new_entry["HostUnauthorisedFlow_details"] = new_bay["HostUnauthorisedFlow_details"]
                        if not is_bay_empty(new_entry):
                            new_bays.append(new_entry)

                    if new_bays:
                        result.append({"date": str(date), "bays": new_bays})
                        existing_dates.add(str(date))

        # ── Phase 3: Handle unauthorised_flow_df - merge into existing dates OR add new ──
        if len(unauthorised_flow_df) > 0:
            unauthorised_flow_df_with_date = unauthorised_flow_df.with_columns(
                pl.col("created_at").cast(pl.Date).alias("date")
            )
            unique_unauth_dates = unauthorised_flow_df_with_date.select("date").unique().sort("date")

            for date_row in unique_unauth_dates.iter_rows(named=True):
                date = date_row.get("date")

                date_unauth_df = unauthorised_flow_df_with_date.filter(pl.col("date") == date)

                if selected_bay:
                    unique_bays = date_unauth_df.filter(
                        pl.col("bay_number").cast(pl.Utf8).str.zfill(2) == selected_bay
                    ).select("bay_number").unique().sort("bay_number")
                else:
                    unique_bays = date_unauth_df.select("bay_number").unique().sort("bay_number")

                # ── Refresh existing_dates_set on each date iteration ─────────
                existing_dates_set = {r["date"] for r in result}

                new_bays = []
                for bay_row in unique_bays.iter_rows(named=True):
                    bay_number_str = str(bay_row.get("bay_number")).zfill(2)

                    unauth_count, unauth_net, unauth_details = get_unauthorised_flow_for_bay_date(
                        unauthorised_flow_df, date, bay_number_str
                    )

                    alerts_count_bay, alerts_count_details_bay = get_alerts_for_bay_date(
                        alerts_df, date, bay_number_str
                    )

                    new_entry = {
                        "bay_number": bay_number_str,
                        "total_count": unauth_count + alerts_count_bay,
                        "HostBayReAssignment": 0,
                        "HostBayReAssignment_details": [],
                        "LocalLoading": 0,
                        "LocalLoading_details": [],
                        "OverLoading": 0,
                        "OverLoading_details": [],
                        "Alerts_Count": alerts_count_bay,
                        # "Gantry_Permissive_off_Count": 0,
                        "MFM_VS_BCU": 0,
                        "MFM_VS_BCU_details": [],
                        "BCU_VS_INVOICE": 0,
                        "BCU_VS_INVOICE_details": [],
                        "HostUnauthorisedFlow_count": unauth_count,
                        "Cross_checked_ManuallyAP_system": 0,
                    }
                    if alerts_count_bay > 0:
                        new_entry["Alerts_Count_details"] = alerts_count_details_bay
                    if unauth_count > 0:
                        new_entry["HostUnauthorisedFlow_details"] = unauth_details

                    if str(date) in existing_dates_set:
                        # ── Date exists → merge bay into existing date ────────
                        for existing in result:
                            if existing["date"] == str(date):
                                matched = next(
                                    (b for b in existing["bays"] if str(b["bay_number"]).zfill(2) == bay_number_str),
                                    None
                                )
                                if matched:
                                    # Bay exists → update UnauthorisedFlow only if not already set
                                    if matched.get("HostUnauthorisedFlow_count", 0) == 0 and unauth_count > 0:
                                        matched["HostUnauthorisedFlow_count"] = unauth_count
                                        matched["HostUnauthorisedFlow_details"] = unauth_details
                                    # Also update Alerts if not already set
                                    if matched.get("Alerts_Count", 0) == 0 and alerts_count_bay > 0:
                                        matched["Alerts_Count"] = alerts_count_bay
                                        matched["Alerts_Count_details"] = alerts_count_details_bay
                                else:
                                    # Bay not in date → add as new bay entry
                                    if not is_bay_empty(new_entry):
                                        existing["bays"].append(new_entry)
                    else:
                        # ── Date does not exist → collect for new date entry ──
                        if not is_bay_empty(new_entry):
                            new_bays.append(new_entry)

                if new_bays and str(date) not in existing_dates_set:
                    result.append({"date": str(date), "bays": new_bays})

        # ── Phase 4: Handle alerts_df - merge into existing dates OR add new ──
        if len(alerts_df) > 0:
            alerts_df_with_date = alerts_df.with_columns(
                pl.col("created_at").cast(pl.Date).alias("date")
            )
            unique_alert_dates = alerts_df_with_date.select("date").unique().sort("date")

            for date_row in unique_alert_dates.iter_rows(named=True):
                date = date_row.get("date")

                date_alerts = alerts_df_with_date.filter(
                    (pl.col("date") == date) &
                    (pl.col("equipment_name") == "BCU")
                ).with_columns(
                    pl.col("device_name").str.extract(r"BC-(\d{2,3})[A-Za-z]?", 1).alias("alert_bay_number")
                )

                if selected_bay:
                    unique_bays = date_alerts.filter(
                        pl.col("alert_bay_number") == selected_bay
                    ).select("alert_bay_number").unique().sort("alert_bay_number")
                else:
                    unique_bays = date_alerts.select(
                        "alert_bay_number"
                    ).unique().sort("alert_bay_number")

                # ── Refresh existing_dates_set on each date iteration ─────────
                existing_dates_set = {r["date"] for r in result}

                new_bays = []
                for bay_row in unique_bays.iter_rows(named=True):
                    bay_number_str = str(bay_row.get("alert_bay_number")).zfill(2)

                    alerts_count_bay, alerts_count_details_bay = get_alerts_for_bay_date(
                        alerts_df, date, bay_number_str
                    )

                    if alerts_count_bay == 0:
                        continue

                    new_entry = {
                        "bay_number": bay_number_str,
                        "total_count": alerts_count_bay,
                        "HostBayReAssignment": 0,
                        "HostBayReAssignment_details": [],
                        "LocalLoading": 0,
                        "LocalLoading_details": [],
                        "OverLoading": 0,
                        "OverLoading_details": [],
                        "Alerts_Count": alerts_count_bay,
                        "Alerts_Count_details": alerts_count_details_bay,
                        # "Gantry_Permissive_off_Count": 0,
                        "MFM_VS_BCU": 0,
                        "MFM_VS_BCU_details": [],
                        "BCU_VS_INVOICE": 0,
                        "BCU_VS_INVOICE_details": [],
                        "HostUnauthorisedFlow_count": 0,
                        "Cross_checked_ManuallyAP_system": 0,
                    }

                    if str(date) in existing_dates_set:
                        # ── Date exists → merge bay into existing date ────────
                        for existing in result:
                            if existing["date"] == str(date):
                                matched = next(
                                    (b for b in existing["bays"] if str(b["bay_number"]).zfill(2) == bay_number_str),
                                    None
                                )
                                if matched:
                                    if matched.get("Alerts_Count", 0) == 0 and alerts_count_bay > 0:
                                        matched["Alerts_Count"] = alerts_count_bay
                                        matched["Alerts_Count_details"] = alerts_count_details_bay
                                else:
                                    if not is_bay_empty(new_entry):
                                        existing["bays"].append(new_entry)
                    else:
                        if not is_bay_empty(new_entry):
                            new_bays.append(new_entry)

                if new_bays and str(date) not in existing_dates_set:
                    result.append({"date": str(date), "bays": new_bays})

        # ── Final sort ────────────────────────────────────────────────────────
        result.sort(key=lambda x: x["date"])

        return {
            "Counts": total_counts,
            "data": result
        }

    except Exception as e:
        print(f"Error in host_tables_combined_data: {e}")
        traceback.print_exc()
        return []


# ── Helper function ───────────────────────────────────────────────────────────
def get_alerts_for_bay_date(alerts_df, date, bay_number_str):
    """
    Returns (alerts_count, alerts_details) for a specific bay and date.
    Extracts bay number from device_name using regex BC-(\\d{2}) (same as get_bay_counts).
    Deduplicates by (created_at, alert_bay_number, interlock_name).
    """
    alerts_count = 0
    alerts_details = []

    if len(alerts_df) == 0:
        return alerts_count, alerts_details

    filtered = alerts_df.filter(
        (pl.col("created_at").cast(pl.Date) == date) &
        (pl.col("equipment_name") == "BCU")
    )

    if len(filtered) > 0:
        filtered = filtered.with_columns(
            pl.col("device_name").str.extract(r"BC-(\d{2,3})[A-Za-z]?", 1).alias("alert_bay_number")
        )
        filtered = filtered.filter(pl.col("alert_bay_number").is_not_null())
        filtered = filtered.filter(pl.col("alert_bay_number") == bay_number_str)

        if len(filtered) > 0:
            deduplicated = filtered.unique(
                subset=["created_at", "alert_bay_number", "interlock_name"],
                keep="last"
            ).sort("created_at", descending=True)

            alerts_count = len(deduplicated)
            for alert_row in deduplicated.iter_rows(named=True):
                alerts_details.append({
                    "created_at": str(alert_row.get("created_at")),
                    "interlock_name": alert_row.get("interlock_name"),
                    "device_name": alert_row.get("device_name"),
                    "location_name": alert_row.get("location_name"),
                    "sap_id": alert_row.get("sap_id")
                })

    return alerts_count, alerts_details


def get_date_range_days(data) -> int:
    start_date = None
    end_date = None
    if data.filters:
        for f in data.filters:
            if f.key == "start_date" and f.value:
                start_date = f.value if isinstance(f.value, str) else f.value[0]
            elif f.key == "end_date" and f.value:
                end_date = f.value if isinstance(f.value, str) else f.value[0]
    if start_date and end_date:
        try:
            delta = datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")
            return max(delta.days, 1)
        except Exception:
            return 30
    return 30


def get_bay_metric_severity(count: int, days: int) -> str:
    scale = days / 30
    if count > 20 * scale:
        return "critical"
    elif count >= 10 * scale:
        return "high"
    elif count >= 1 * scale:
        return "medium"
    else:
        return "low"


def get_alerts_severity(count: int, days: int) -> str:
    scale = days / 30
    if count > 120 * scale:
        return "critical"
    elif count >= 70 * scale:
        return "high"
    elif count >= 30 * scale:
        return "medium"
    else:
        return "low"


def calc_unauthorised_net_totalizer(df):
    if len(df) == 0 or "net_totalizer" not in df.columns:
        return 0
    # Group by date, get latest row per day, sum net_totalizer
    df_with_date = df.with_columns(
        pl.col("created_at").cast(pl.Date).alias("date")
    )
    latest_per_day = (
        df_with_date.sort("created_at", descending=True)
        .group_by("date")
        .first()
        .filter(pl.col("net_totalizer") > 0)
    )
    if len(latest_per_day) == 0:
        return 0
    return round(float(latest_per_day.select(pl.col("net_totalizer").sum()).item()), 2)


def get_difference_severity(difference, days: int) -> str:
    scale = days / 30
    diff = abs(difference)
    if diff > 500 * scale:
        return "critical"
    elif diff >= 300 * scale:
        return "high"
    elif diff >= 50 * scale:
        return "medium"
    else:
        return "low"


async def get_bay_counts(data):
    """
    Get location-wise counts with bay-wise breakdown for ALL locations.
    Returns:
    {
        "total_counts": {...},  # Overall totals across all locations
        "locations": [
            {
                "location_name": "mathra",
                "counts": {...},
                "bays": [...]
            }
        ]
    }
    """
    # Fetch all data using existing function
    days = get_date_range_days(data)
    combined_df, alerts_df, day_end_df, total_bcu_count, total_active_bays_count, unauthorised_flow_df = \
        await tas_host_data.fetch_host_tables_as_dfs(data)

    all_onboarded = await get_all_onboarded_locations()

    if combined_df is None or combined_df.is_empty():
        zero_counts = {
            "TotalBCU": 0, "TotalActiveBays": 0, "HostBayReAssignment": 0,
            "LocalLoading": 0, "LocalLoading_qty": 0, "OverLoading": 0,
            "OverLoading_qty": 0, "TotalUniqueTruckNumbersCount": 0,
            "UnauthorisedFlow": 0, "UnauthorisedFlow_net_totalizer": 0,
            "Alerts_Count": 0, "Gantry_Permissive_off_Count": 0,
            "MFM_VS_BCU": 0, "MFM_VS_BCU_difference": 0,
            "BCU_VS_INVOICE": 0, "BCU_VS_INVOICE_difference": 0,
        }
        return {
            "total_counts": zero_counts,
            "locations": [
                {"location_name": loc["name"], "counts": zero_counts.copy(), "bays": []}
                for loc in all_onboarded if loc.get("name")
            ]
        }

    # Calculate OVERALL MFM_VS_BCU count and difference
    overall_mfm_vs_bcu_count = 0
    overall_mfm_vs_bcu_difference = 0
    if len(day_end_df) > 0:
        filtered_overall = day_end_df.filter(
            pl.col('bcu_mfm_net_totalizer_diff').is_not_null() &
            (pl.col('bcu_mfm_net_totalizer_diff') != 0)
        )
        if len(filtered_overall) > 0:
            overall_mfm_vs_bcu_difference = filtered_overall.select(pl.col("bcu_mfm_net_totalizer_diff").sum()).item()
            overall_mfm_vs_bcu_count = len(filtered_overall)

            # Calculate OVERALL BCU_VS_INVOICE count and difference
    overall_bcu_vs_invoice_count = 0
    overall_bcu_vs_invoice_difference = 0
    if len(day_end_df) > 0:
        filtered_overall = day_end_df.filter(
            pl.col('invoiced_bcu_net_qty_diff').is_not_null() &
            (pl.col('invoiced_bcu_net_qty_diff') != 0)
        )
        if len(filtered_overall) > 0:
            overall_bcu_vs_invoice_difference = filtered_overall.select(
                pl.col("invoiced_bcu_net_qty_diff").sum()).item()
            overall_bcu_vs_invoice_count = len(filtered_overall)

            # Calculate OVERALL total counts (all locations combined)
    overall_alerts_count = 0
    if len(alerts_df) > 0:
        overall_alerts = alerts_df.filter(pl.col("equipment_name") == "BCU")
        if len(overall_alerts) > 0:
            overall_alerts = overall_alerts.unique(subset=["created_at", "device_name", "interlock_name"], keep="last")
            overall_alerts_count = len(overall_alerts)

    overall_gantry_count = 0
    if len(alerts_df) > 0:
        overall_gantry = alerts_df.filter((pl.col("interlock_name").str.contains("Gantry Permissive Off")) & (
            ~pl.col("interlock_name").str.contains("Fail")))
        if len(overall_gantry) > 0:
            overall_gantry = overall_gantry.unique(subset=["created_at", "interlock_name"], keep="last")
            overall_gantry_count = len(overall_gantry)

    overall_unique_truck_count = combined_df.select("truck_number").unique().height

    # Calculate OVERALL OverLoading quantity difference
    overall_overloading_qty = 0
    if len(combined_df) > 0:
        overloaded_records = combined_df.filter(pl.col("table_name") == "HostOverLoaded")
        if len(overloaded_records) > 0:
            # Filter out null values
            overloaded_filtered = overloaded_records.filter(
                pl.col('loaded_qty').is_not_null() & pl.col('required_qty').is_not_null())
            if len(overloaded_filtered) > 0:
                # Calculate row-by-row absolute difference, then sum (matches SQL)
                overloaded_with_diff = overloaded_filtered.with_columns(
                    (pl.col("loaded_qty") - pl.col("required_qty")).abs().alias("row_difference"))
                overall_overloading_qty = int(overloaded_with_diff.select(pl.col("row_difference").sum()).item())

    # Calculate OVERALL LocalLoading quantity
    overall_localloading_qty = 0
    if len(combined_df) > 0:
        localloaded_records = combined_df.filter(pl.col("table_name") == "HostLocalLoaded")
        if len(localloaded_records) > 0:
            localloaded_filtered = localloaded_records.filter(
                pl.col('loaded_qty').is_not_null() &
                (pl.col('loaded_qty') != 0)
            )
            if len(localloaded_filtered) > 0:
                overall_localloading_qty = int(localloaded_filtered.select(pl.col("loaded_qty").sum()).item())

    total_counts = {
        "TotalBCU": total_bcu_count,
        "TotalActiveBays": total_active_bays_count,
        "HostBayReAssignment": len(combined_df.filter(pl.col("table_name") == "HostBayReAssignment")),
        "LocalLoading": len(combined_df.filter(pl.col("table_name") == "HostLocalLoaded")),
        "LocalLoading_qty": overall_localloading_qty,
        "OverLoading": len(combined_df.filter(pl.col("table_name") == "HostOverLoaded")),
        "OverLoading_qty": overall_overloading_qty,
        "TotalUniqueTruckNumbersCount": overall_unique_truck_count,
        "UnauthorisedFlow": 0,
        "UnauthorisedFlow_net_totalizer": 0,
        "Alerts_Count": overall_alerts_count,
        "Gantry_Permissive_off_Count": overall_gantry_count,
        "MFM_VS_BCU": overall_mfm_vs_bcu_count,
        "MFM_VS_BCU_difference": overall_mfm_vs_bcu_difference,
        "BCU_VS_INVOICE": overall_bcu_vs_invoice_count,
        "BCU_VS_INVOICE_difference": overall_bcu_vs_invoice_difference,

    }

    # Get unique locations
    # Get locations that exist in combined_df
    locations_with_data = set(
        combined_df.select("location_name").unique().to_series().to_list()
    )

    locations_result = []

    for loc_record in all_onboarded:
        location_name = loc_record.get("name")
        if not location_name:
            continue

        if location_name not in locations_with_data:
            locations_result.append({
                "location_name": location_name,
                "counts": {
                    "TotalBCU": 0, "TotalActiveBays": 0, "HostBayReAssignment": 0,
                    "LocalLoading": 0, "LocalLoading_qty": 0, "OverLoading": 0,
                    "OverLoading_qty": 0, "TotalUniqueTruckNumbersCount": 0,
                    "UnauthorisedFlow": 0, "UnauthorisedFlow_net_totalizer": 0,
                    "Alerts_Count": 0, "Gantry_Permissive_off_Count": 0,
                    "MFM_VS_BCU": 0, "MFM_VS_BCU_difference": 0,
                    "BCU_VS_INVOICE": 0, "BCU_VS_INVOICE_difference": 0,
                },
                "bays": []
            })
            continue

        # Location has data in combined_df → existing processing runs normally
        location_combined_df = combined_df.filter(pl.col("location_name") == location_name)

        location_unauthorised_df = unauthorised_flow_df
        if len(unauthorised_flow_df) > 0 and "location_name" in unauthorised_flow_df.columns:
            location_unauthorised_df = unauthorised_flow_df.filter(pl.col("location_name") == location_name)

        location_day_end_df = day_end_df
        if len(day_end_df) > 0 and "location_name" in day_end_df.columns:
            location_day_end_df = day_end_df.filter(pl.col("location_name") == location_name)

        # Calculate location-level BCU counts
        location_bcu_count = 0
        location_active_bays_count = 0

        if len(location_day_end_df) > 0:
            location_grouped = (
                location_day_end_df.group_by(["bay_number", "bcu_number"]).agg([
                    pl.col("bcu_start_totalizer").sum().alias("sum_start"),
                    pl.col("bcu_end_totalizer").sum().alias("sum_end"),
                ])
                .with_columns((pl.col("sum_end") - pl.col("sum_start")).alias("total_difference"))
            )

            location_bcu_count = location_grouped.height
            location_active_bays_count = location_grouped.filter(pl.col("total_difference") > 100).height

        # Calculate location-level MFM_VS_BCU count and difference
        location_mfm_vs_bcu_count = 0
        location_mfm_vs_bcu_difference = 0
        if len(location_day_end_df) > 0:
            # Filter out null and zero values from both columns
            filtered_location = location_day_end_df.filter(
                pl.col('bcu_mfm_net_totalizer_diff').is_not_null() & (pl.col('bcu_mfm_net_totalizer_diff') != 0))
            if len(filtered_location) > 0:
                location_mfm_vs_bcu_difference = filtered_location.select(
                    pl.col("bcu_mfm_net_totalizer_diff").sum()).item()
                location_mfm_vs_bcu_count = len(filtered_location)

        # Calculate location-level BCU_VS_INVOICE count and difference
        location_bcu_vs_invoice_count = 0
        location_bcu_vs_invoice_difference = 0
        if len(location_day_end_df) > 0:
            # Filter out null/zero invoiced_qty and null/zero bcu_net_totalizer
            filtered_location = location_day_end_df.filter(
                pl.col('invoiced_bcu_net_qty_diff').is_not_null() & (pl.col('invoiced_bcu_net_qty_diff') != 0))
            if len(filtered_location) > 0:
                location_bcu_vs_invoice_difference = filtered_location.select(
                    pl.col("invoiced_bcu_net_qty_diff").sum()).item()
                location_bcu_vs_invoice_count = len(filtered_location)

        # Calculate Gantry_Permissive_off_Count for this location
        location_gantry_count = 0
        if len(alerts_df) > 0:
            location_gantry = alerts_df.filter((pl.col("location_name") == location_name) & (
                pl.col("interlock_name").str.contains("Gantry Permissive Off")) & (
                                                   ~pl.col("interlock_name").str.contains("Fail")))
            if len(location_gantry) > 0:
                # Deduplicate by created_at and interlock_name
                location_gantry = location_gantry.unique(subset=["created_at", "interlock_name"], keep="last")
                location_gantry_count = len(location_gantry)

        # Calculate location-level counts
        unique_truck_count = location_combined_df.select("truck_number").unique().height

        # Placeholder for location_alerts_count (will be calculated from bays)
        location_alerts_count = 0

        # Calculate location-level OverLoading quantity difference
        location_overloading_qty = 0
        if len(location_combined_df) > 0:
            location_overloaded_records = location_combined_df.filter(pl.col("table_name") == "HostOverLoaded")
            if len(location_overloaded_records) > 0:
                # Filter out null values
                location_overloaded_filtered = location_overloaded_records.filter(
                    pl.col('loaded_qty').is_not_null() & pl.col('required_qty').is_not_null())
                if len(location_overloaded_filtered) > 0:
                    # Calculate row-by-row absolute difference, then sum (matches SQL)
                    location_overloaded_with_diff = location_overloaded_filtered.with_columns(
                        (pl.col("loaded_qty") - pl.col("required_qty")).abs().alias("row_difference"))
                    location_overloading_qty = int(
                        location_overloaded_with_diff.select(pl.col("row_difference").sum()).item())

        # Calculate location-level LocalLoading quantity
        location_localloading_qty = 0
        if len(location_combined_df) > 0:
            location_localloaded_records = location_combined_df.filter(pl.col("table_name") == "HostLocalLoaded")
            if len(location_localloaded_records) > 0:
                location_localloaded_filtered = location_localloaded_records.filter(
                    pl.col('loaded_qty').is_not_null() & (pl.col('loaded_qty') != 0))
                if len(location_localloaded_filtered) > 0:
                    location_localloading_qty = int(
                        location_localloaded_filtered.select(pl.col("loaded_qty").sum()).item())

        location_counts = {
            "TotalBCU": location_bcu_count,
            "TotalActiveBays": location_active_bays_count,
            "HostBayReAssignment": len(location_combined_df.filter(pl.col("table_name") == "HostBayReAssignment")),
            "LocalLoading": len(location_combined_df.filter(pl.col("table_name") == "HostLocalLoaded")),
            "LocalLoading_qty": location_localloading_qty,
            "OverLoading": len(location_combined_df.filter(pl.col("table_name") == "HostOverLoaded")),
            "OverLoading_qty": location_overloading_qty,
            "TotalUniqueTruckNumbersCount": unique_truck_count,
            "UnauthorisedFlow": 0,
            "UnauthorisedFlow_net_totalizer": 0,
            "Alerts_Count": location_alerts_count,
            "Gantry_Permissive_off_Count": location_gantry_count,
            "MFM_VS_BCU": location_mfm_vs_bcu_count,
            "MFM_VS_BCU_difference": location_mfm_vs_bcu_difference,
            "BCU_VS_INVOICE": location_bcu_vs_invoice_count,
            "BCU_VS_INVOICE_difference": location_bcu_vs_invoice_difference,

        }

        # Get unique bay numbers for this location
        unique_bays = pl.DataFrame({"bay": []}, schema={"bay": pl.Utf8})
        if len(location_day_end_df) > 0 and "bay_number_extracted" in location_day_end_df.columns:
            unique_bays = location_day_end_df.select(pl.col("bay_number_extracted").alias("bay")).unique().sort("bay")
        elif len(location_combined_df) > 0 and "assigned_bay" in location_combined_df.columns:
            # ── Fallback: get bays from combined_df when day_end_df is empty ──
            unique_bays = (
                location_combined_df
                .select(pl.col("assigned_bay").cast(pl.Utf8).str.zfill(2).alias("bay"))
                .filter(pl.col("bay").is_not_null() & (pl.col("bay") != ""))
                .unique()
                .sort("bay")
            )
        unique_bays_from_alerts = pl.DataFrame({"bay": []}, schema={"bay": pl.Utf8})
        if len(alerts_df) > 0 and "bay_number" in alerts_df.columns:
            unique_bays_from_alerts = (
                alerts_df
                .filter(pl.col("location_name") == location_name)
                .select(pl.col("bay_number").alias("bay"))
                .filter(pl.col("bay").is_not_null() & (pl.col("bay") != ""))
                .unique()
                .sort("bay")
            )
        # Merge both sources
        unique_bays = pl.concat([unique_bays, unique_bays_from_alerts], how="diagonal_relaxed").unique().sort("bay")

        # Calculate counts for each bay
        bays_data = []

        for bay_row in unique_bays.iter_rows(named=True):
            bay_number = bay_row.get("bay")
            bay_number_str = str(bay_number).zfill(2)  # for day_end_df / combined_df filtering
            bay_number_raw = str(bay_number)  # for alert device_name matching

            # Filter data for this specific bay
            bay_combined_df = location_combined_df.filter(
                pl.col("assigned_bay").cast(pl.Utf8).str.zfill(2) == bay_number_str
            )

            # Filter unauthorised flow for this bay
            bay_unauthorised_df = location_unauthorised_df
            if len(location_unauthorised_df) > 0 and "bay_number" in location_unauthorised_df.columns:
                bay_unauthorised_df = location_unauthorised_df.filter(pl.col("bay_number") == str(bay_number).zfill(2))

            # Calculate bay-specific BCU counts
            bay_bcu_count = 0
            bay_active_bays_count = 0

            if len(location_day_end_df) > 0 and "bay_number_extracted" in location_day_end_df.columns:
                bay_day_end = location_day_end_df.filter(pl.col("bay_number_extracted") == bay_number_str)

                if len(bay_day_end) > 0:
                    bay_grouped = (bay_day_end.group_by(["bay_number", "bcu_number"]).agg(
                        [pl.col("bcu_start_totalizer").sum().alias("sum_start"),
                         pl.col("bcu_end_totalizer").sum().alias("sum_end"), ])
                                   .with_columns((pl.col("sum_end") - pl.col("sum_start")).alias("total_difference")))

                    bay_bcu_count = bay_grouped.height
                    bay_active_bays_count = bay_grouped.filter(pl.col("total_difference") > 100).height

            # Calculate bay-specific MFM_VS_BCU count and difference
            bay_mfm_vs_bcu_count = 0
            bay_mfm_vs_bcu_difference = 0
            if len(location_day_end_df) > 0 and "bay_number_extracted" in location_day_end_df.columns:
                bay_day_end = location_day_end_df.filter(pl.col("bay_number_extracted") == bay_number_str)

                if len(bay_day_end) > 0:
                    filtered_bay = bay_day_end.filter(pl.col('bcu_mfm_net_totalizer_diff').is_not_null() & (
                                pl.col('bcu_mfm_net_totalizer_diff') != 0))
                    if len(filtered_bay) > 0:
                        bay_mfm_vs_bcu_difference = filtered_bay.select(
                            pl.col("bcu_mfm_net_totalizer_diff").sum()).item()
                        bay_mfm_vs_bcu_count = len(filtered_bay)

            # Calculate bay-specific BCU_VS_INVOICE count and difference
            bay_bcu_vs_invoice_count = 0
            bay_bcu_vs_invoice_difference = 0
            if len(location_day_end_df) > 0 and "bay_number_extracted" in location_day_end_df.columns:
                bay_day_end = location_day_end_df.filter(pl.col("bay_number_extracted") == bay_number_str)

                if len(bay_day_end) > 0:
                    filtered_bay = bay_day_end.filter(
                        pl.col('invoiced_bcu_net_qty_diff').is_not_null() & (pl.col('invoiced_bcu_net_qty_diff') != 0))
                    if len(filtered_bay) > 0:
                        bay_bcu_vs_invoice_difference = filtered_bay.select(
                            pl.col("invoiced_bcu_net_qty_diff").sum()).item()
                        bay_bcu_vs_invoice_count = len(filtered_bay)

            # Calculate unique trucks for this bay
            bay_unique_truck_count = bay_combined_df.select("truck_number").unique().height if len(
                bay_combined_df) > 0 else 0

            # Calculate Alerts_Count for this bay (BCU alerts only)
            bay_alerts_count = 0
            if len(alerts_df) > 0:
                bay_alerts = alerts_df.filter(
                    (pl.col("location_name") == location_name) &
                    (pl.col("equipment_name") == "BCU")
                )

                if "device_name" in bay_alerts.columns:
                    bay_alerts = bay_alerts.with_columns(
                        pl.col("device_name")
                        .str.extract(r"BC-(\d{2,3})[A-Za-z]?", 1)
                        .alias("alert_bay_number")
                    )
                    bay_alerts = bay_alerts.filter(
                        pl.col("alert_bay_number") == bay_number_raw
                    )

                if len(bay_alerts) > 0:
                    bay_alerts = bay_alerts.unique(subset=["created_at", "alert_bay_number", "interlock_name"],
                                                   keep="last")
                    bay_alerts_count = len(bay_alerts)

            # Note: Gantry_Permissive_off_Count is same for all bays in a location (it's location-wide)
            bay_gantry_count = location_gantry_count

            # Calculate bay-specific OverLoading quantity difference
            bay_overloading_qty = 0
            if len(bay_combined_df) > 0:
                bay_overloaded_records = bay_combined_df.filter(pl.col("table_name") == "HostOverLoaded")
                if len(bay_overloaded_records) > 0:
                    bay_overloaded_filtered = bay_overloaded_records.filter(
                        pl.col('loaded_qty').is_not_null() & pl.col('required_qty').is_not_null())
                    if len(bay_overloaded_filtered) > 0:
                        bay_overloaded_with_diff = bay_overloaded_filtered.with_columns(
                            (pl.col("loaded_qty") - pl.col("required_qty")).abs().alias("row_difference"))
                        bay_overloading_qty = int(
                            bay_overloaded_with_diff.select(pl.col("row_difference").sum()).item())

            # Calculate bay-specific LocalLoading quantity
            bay_localloading_qty = 0
            if len(bay_combined_df) > 0:
                bay_localloaded_records = bay_combined_df.filter(pl.col("table_name") == "HostLocalLoaded")
                if len(bay_localloaded_records) > 0:
                    bay_localloaded_filtered = bay_localloaded_records.filter(
                        pl.col('loaded_qty').is_not_null() & (pl.col('loaded_qty') != 0))
                    if len(bay_localloaded_filtered) > 0:
                        bay_localloading_qty = int(bay_localloaded_filtered.select(pl.col("loaded_qty").sum()).item())

            bay_reassignment_count = len(bay_combined_df.filter(pl.col("table_name") == "HostBayReAssignment")) if len(
                bay_combined_df) > 0 else 0
            bay_local_count = len(bay_combined_df.filter(pl.col("table_name") == "HostLocalLoaded")) if len(
                bay_combined_df) > 0 else 0
            bay_over_count = len(bay_combined_df.filter(pl.col("table_name") == "HostOverLoaded")) if len(
                bay_combined_df) > 0 else 0

            bay_counts = {
                "bay_number": str(bay_number).zfill(2),
                "counts": {
                    "TotalBCU": bay_bcu_count,
                    "TotalActiveBays": bay_active_bays_count,
                    "HostBayReAssignment": bay_reassignment_count,
                    "HostBayReAssignment_severity": get_bay_metric_severity(bay_reassignment_count, days),
                    "LocalLoading": bay_local_count,
                    "LocalLoading_severity": get_bay_metric_severity(bay_local_count, days),
                    "LocalLoading_qty": bay_localloading_qty,
                    "OverLoading": bay_over_count,
                    "OverLoading_severity": get_bay_metric_severity(bay_over_count, days),
                    "OverLoading_qty": bay_overloading_qty,
                    "TotalUniqueTruckNumbersCount": bay_unique_truck_count,
                    "UnauthorisedFlow": len(bay_unauthorised_df) if len(bay_unauthorised_df) > 0 else 0,
                    "UnauthorisedFlow_net_totalizer": calc_unauthorised_net_totalizer(bay_unauthorised_df),
                    "Alerts_Count": bay_alerts_count,
                    "Alerts_Count_severity": get_alerts_severity(bay_alerts_count, days),
                    "Gantry_Permissive_off_Count": 0,
                    "MFM_VS_BCU": bay_mfm_vs_bcu_count,
                    "MFM_VS_BCU_difference": bay_mfm_vs_bcu_difference,
                    "MFM_VS_BCU_severity": get_difference_severity(bay_mfm_vs_bcu_difference, days),
                    "BCU_VS_INVOICE": bay_bcu_vs_invoice_count,
                    "BCU_VS_INVOICE_difference": bay_bcu_vs_invoice_difference,
                    "BCU_VS_INVOICE_severity": get_difference_severity(bay_bcu_vs_invoice_difference, days)
                }
            }

            bays_data.append(bay_counts)

        # Update location_alerts_count by summing bay alerts
        location_counts["UnauthorisedFlow"] = sum(
            bay["counts"]["UnauthorisedFlow"] for bay in bays_data
        )
        location_counts["UnauthorisedFlow_net_totalizer"] = round(
            sum(bay["counts"]["UnauthorisedFlow_net_totalizer"] for bay in bays_data), 2
        )
        location_alerts_count = sum(bay["counts"]["Alerts_Count"] for bay in bays_data)
        location_counts["Alerts_Count"] = location_alerts_count

        locations_result.append({
            "location_name": location_name,
            "counts": location_counts,
            "bays": bays_data
        })

    total_counts["UnauthorisedFlow"] = sum(
        loc["counts"]["UnauthorisedFlow"] for loc in locations_result
    )
    total_counts["UnauthorisedFlow_net_totalizer"] = round(
        sum(loc["counts"]["UnauthorisedFlow_net_totalizer"] for loc in locations_result), 2
    )

    return {
        "total_counts": total_counts,
        "locations": locations_result
    }

async def gantry_override_analysis(data):
    """
    For each 'Gantry Permissive_Override' alert in the date range,
    check if any 'Gantry Permissive Off' alert existed BEFORE it on the same day.
    Returns location-wise grouped results. All override alerts included even if no permissive off found.
    """
    try:
        # ── Build conditions same as tas_host_data ────────────────────────────
        conditions = []

        if data.filters:
            for f in data.filters:

                if not f.value:
                    continue

                if f.key == "bay":
                    continue

                if f.key == "start_date":
                    start_date = f.value if isinstance(f.value, str) else f.value[0]
                    end_date_obj = next(
                        (x.value for x in data.filters if x.key == "end_date" and x.value),
                        None
                    )
                    end_date = (
                        end_date_obj if isinstance(end_date_obj, str)
                        else end_date_obj[0] if end_date_obj else None
                    )
                    if start_date and end_date:
                        conditions.append(
                            f"created_at::date BETWEEN '{start_date}' AND '{end_date}'"
                        )
                    continue

                if f.key == "end_date":
                    continue

                if isinstance(f.value, str):
                    clean_values = [v.strip() for v in f.value.split(",")] if "," in f.value else [f.value]
                else:
                    clean_values = [v for v in f.value if v]

                if not clean_values:
                    continue

                if f.cond == "=":
                    if len(clean_values) == 1:
                        conditions.append(f"{f.key} = '{clean_values[0]}'")
                    else:
                        values = ", ".join(f"'{v}'" for v in clean_values)
                        conditions.append(f"{f.key} IN ({values})")

                elif f.cond == "!=":
                    if len(clean_values) == 1:
                        conditions.append(f"{f.key} != '{clean_values[0]}'")
                    else:
                        values = ", ".join(f"'{v}'" for v in clean_values)
                        conditions.append(f"{f.key} NOT IN ({values})")

        # ── Step 1: Fetch Gantry Permissive_Override alerts ───────────────────
        override_conditions = ["alert_section = 'TAS'", "interlock_name = 'Gantry Permissive_Override'"]
        if conditions:
            override_conditions.extend(conditions)

        override_query = " AND ".join(override_conditions)
        override_params = urdhva_base.queryparams.QueryParams(q=override_query, limit=0)
        override_params.fields = json.dumps([
            "location_name", "device_name", "equipment_name",
            "interlock_name", "created_at"
        ])

        override_resp = await hpcl_ceg_model.Alerts.get_all(override_params, resp_type="plain")
        override_data = override_resp.get("data", [])

        if not override_data:
            return []

        override_df = pl.DataFrame(override_data).with_columns(
            pl.col("created_at").dt.date().alias("alert_date")
        )

        # ── Step 2: Fetch Gantry Permissive Off alerts (same date filter) ─────
        permissive_off_conditions = ["alert_section = 'TAS'", "interlock_name = 'Gantry Permissive Off'"]
        if conditions:
            permissive_off_conditions.extend(conditions)

        permissive_off_query = " AND ".join(permissive_off_conditions)
        permissive_off_params = urdhva_base.queryparams.QueryParams(q=permissive_off_query, limit=0)
        permissive_off_params.fields = json.dumps([
            "location_name", "device_name", "equipment_name",
            "interlock_name", "created_at"
        ])

        permissive_off_resp = await hpcl_ceg_model.Alerts.get_all(permissive_off_params, resp_type="plain")
        permissive_off_data = permissive_off_resp.get("data", [])

        permissive_off_df = pl.DataFrame(permissive_off_data).with_columns(
            pl.col("created_at").dt.date().alias("alert_date")
        ) if permissive_off_data else None

        # ── Step 3: Match override → permissive off before it on same day ─────
        location_wise_result = {}

        for row in override_df.iter_rows(named=True):
            loc = row["location_name"]
            override_time = row["created_at"]
            alert_date = row["alert_date"]

            # Find matching permissive off alerts (empty list if none found)
            matching = []
            if permissive_off_df is not None:
                matching = permissive_off_df.filter(
                    (pl.col("location_name") == loc) &
                    (pl.col("alert_date") == alert_date) &
                    (pl.col("created_at") < override_time)
                ).select([
                    "created_at", "device_name", "interlock_name", "equipment_name"
                ]).with_columns(
                    pl.col("created_at").cast(pl.Utf8).alias("created_at")
                ).to_dicts()

            if loc not in location_wise_result:
                location_wise_result[loc] = []

            location_wise_result[loc].append({
                "override_alert": {
                    "created_at": str(override_time),
                    "device_name": row["device_name"],
                    "interlock_name": row["interlock_name"],
                    "equipment_name": row["equipment_name"],
                },
                "permissive_off_before_override": matching  # empty list if no match
            })

        # ── Step 4: Build final response ──────────────────────────────────────
        return [
            {
                "location_name": loc,
                "override_count": len(records),
                "records": records
            }
            for loc, records in sorted(location_wise_result.items())
        ]

    except Exception as e:
        print(f"Error in gantry_override_analysis: {e}")
        return []
    
AnalyticsModelMapping = {
    "Top Repeated Alerts": top_repeat_alerts,
    "Tas Severity Summary": tas_severity_summary,
    "Location Alert Critical": location_alert_critical,
    "Critical Alerts By Equipment":critical_alerts_by_equipment,
    "Tas Alerts Exception Report" :tas_alerts_exception_report,
    "Equipment Location Wise Count": equipment_location_wise_count,
    "Location Wise Total Loaded Qty": location_wise_total_loaded_qty,
    "Top five Alerts": top_five_alerts,
    "BCU DIff Alerts":bcu_totalizer_diff_alert,
    "Unauthorized Alerts":unauthorized_flow_dashboard,
    "Hostbay Reassignment Alerts":host_bay_reassignment_alert,
    "Cancelled Report tts":cancelled_tts_dashboard,
    "Sick Report tts":sick_tts_dashboard,
    "Repeated_Sick_Cross":repeated_sick_cross_verification,
    "Over Loaded tts":over_loaded_tts_dashboard,
    "Host Tables Combined Data":host_tables_combined_data,
    "get bay counts":get_bay_counts,
    "Gantry Override Analysis": gantry_override_analysis,

}


async def tas_analytics_action(data):
    SKIP_KEYS = {"bay"}
    if hasattr(data, "filters") and data.filters:
        cleaned_filters = []
        for f in data.filters:
            if f.key in SKIP_KEYS:
                continue
            if f.value:
                cleaned_filters.append(f)

        data.filters = cleaned_filters   # optional cleanup

    analytical_model = data.analytical_model

    if not analytical_model or analytical_model not in AnalyticsModelMapping:
        return {
            "status": False,
            "message": "Invalid Inputs"
        }
    return await AnalyticsModelMapping[analytical_model](data)
