import urdhva_base
import os
import json
import asyncio
import traceback
import hpcl_ceg_model
import uuid
from datetime import datetime, timedelta
import tas_duplicate_alert_check as duplicates_check
from orchestrator.alerting.alert_manager import create_alert 


async def tas_bcu_analog():
    try:
        # Interlock names to monitor
        interlock_names = ["BCU K- Factor Change", "BCU Local Loading", "MFM factor Change"]
        
        # Calculate the start of the current week (Monday)
        today = datetime.now()
        start_of_week = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week_str = start_of_week.strftime("%Y-%m-%d")
        end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
        end_of_week_str = end_of_week.strftime("%Y-%m-%d %H:%M:%S")
        
        # Loop through each interlock name
        for interlock_name in interlock_names:
            # Query to get the count of alerts for each device_name for the interlock in the current week
            query1 = f"""
                SELECT device_name, COUNT(*) as alert_count
                FROM alerts
                WHERE interlock_name = '{interlock_name}'
                AND created_at BETWEEN '{start_of_week_str}' AND '{end_of_week_str}'
                GROUP BY device_name
            """
            params = urdhva_base.queryparams.QueryParams(q=query1)
            resp1 = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
            
            # Process the response
            for record in resp1.get("data", []):
                device_name = record.get("device_name")
                alert_count = record.get("alert_count", 0)
                
                # Trigger alert only when exactly 3 occurrences are found in the week
                if alert_count == 3:
                   # Create alert data
                    query2 = f"""
                        SELECT severity,  sap_id , device_type
                        FROM alerts
                        WHERE interlock_name = '{interlock_name}'
                        AND device_name = '{device_name}'
                        ORDER BY created_at DESC
                        LIMIT 1
                    """
                    params = urdhva_base.queryparams.QueryParams(q=query2)
                    resp2 = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
                    if resp2.get("data", []):
                       severity = resp2["data"][0].get("severity", "")
                       sap_id = resp2["data"][0].get("sap_id", "")
                    alert_data = {
                        "interlock_name": "K Factor BCU Primissive Off_Fail",
                        "device_name": device_name,
                        "sop_id": "SOP28A",
                        "sap_id": sap_id,
                        "severity": severity,
                        "alert_id": str(uuid.uuid1())     
                    }
                    
                    # Check for duplicates
                    is_duplicate = await duplicates_check.duplicate_check(alert_data)
                    if is_duplicate:
                        print(f"Duplicate alert found for {interlock_name} on device {device_name}. Skipping alert creation.")
                        continue
                    
                    # Check alert history
                    alert_history = await duplicates_check.alert_history_check(alert_data, month_check=True)
                    if alert_history:
                        print(f"Alert history exists for {interlock_name} on device {device_name}. Skipping alert creation.")
                        continue
                    # Create the alert
                    success, msg = await create_alert(alert_data)
                    if success:
                        print(f"Weekly summary alert created successfully for {interlock_name} on device {device_name}.")
                    else:
                        print(f"Failed to create weekly summary alert for {interlock_name} on device {device_name}: {msg}")
    except Exception as e:
        print(f"Error in tas_bcu_analog: {traceback.format_exc()}")