import urdhva_base
import json
import datetime
import traceback
import hpcl_ceg_model
import orchestrator.alerting.alert_factory as alert_create
import orchestrator.alerting.listener.tas_maintenance_alert_check as alert_close
logger = urdhva_base.logger.Logger.getInstance("esd_activation_processing_log")

class TasEsdActivation:
    async def get_required_variables(self):
        return ["BU", "sap_id", "sop_id", "device_id", 
                "device_type", "device_name", "cause_effect", 
                "effect_sop_id", "cause_sop_id", "alert_id", "interlock_name", 
                "rosov_interlock_name", "dbbv_interlock_name", "esd_fail_status",
                "rosov_pl_mode", "esd_close_status"]

    async def tas_esd_activation_check(self, params):
        rosov_interlock_name = params.get("rosov_interlock_name", "")
        dbbv_interlock_name = params.get("dbbv_interlock_name", "")
        esd_fail_status = params.get("esd_fail_status", "")
        rosov_pl_mode = params.get("rosov_pl_mode", "")
        esd_close_status = params.get("esd_close_status", "")
        bu = params.get("BU", "")
        sap_id = params.get("sap_id", "")
        sop_id = params.get("sop_id", "")
        device_id = params.get("device_id", "")
        device_name = params.get("device_name", "")
        
        # Time window for checking related alerts (in seconds)
        time_window = 10
        
        # Initialize counters
        maintenance_alert_count = rosov_pl_close_count = esd_close_status_count = 0
        
        # Query to check for interlock alerts
        interlock_query = f"bu = 'TAS' and sap_id = '{sap_id}' and alert_section = 'TAS'"
        if rosov_interlock_name:
            interlock_query += f" and interlock_name = '{rosov_interlock_name}'"
        if dbbv_interlock_name:
            if interlock_query:
                interlock_query += " OR "
            interlock_query += f"interlock_name = '{dbbv_interlock_name}'"
        
        # Add the time constraint
        if interlock_query:
            interlock_query += f" AND created_at >= NOW() - INTERVAL '{time_window} seconds'"
        else:
            interlock_query = f"created_at >= NOW() - INTERVAL '{time_window} seconds'"
        
        # Use the query parameters system from your framework
        params = urdhva_base.queryparams.QueryParams()
        params.fields = ["tas_device_name", "location_name"]
        params.q = interlock_query
        interlock_results = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
        interlock_results = interlock_results.get("data", [])
        
        # If no interlock alerts found, return early
        if not interlock_results:
            return {"status": "No matching interlock alerts found"}
        
        # Find ESD close interlock alerts happening within the time window
        esd_device_names = []
        for result in interlock_results:
            esd_close_query = f"bu = 'TAS' and sap_id = '{sap_id}' and alert_section = 'TAS' and interlock_name = {esd_fail_status} AND created_at >= NOW() - INTERVAL '{time_window} seconds'"
            esd_params = urdhva_base.queryparams.QueryParams()
            esd_params.fields = ["tas_device_name", location_name]
            esd_params.q = esd_close_query
            esd_close_alerts = await hpcl_ceg_model.Alerts.get_all(esd_params, resp_type='plain')
            esd_close_data = esd_close_alerts.get("data", [])
            
            if esd_close_data:
                for alert in esd_close_data:
                    esd_device_names.append(alert.get('tas_device_name', ''))
        
        # Check maintenance alerts for the ESD devices
        for device_name in esd_device_names:
            if not device_name:
                continue
                
            # Format the device name for querying maintenance alerts
            # The maintenance device name has "_M" suffix, so we need to account for that
            equipment_maintenance_query = (
                f"bu = 'TAS' and "
                f"sap_id = '{sap_id}' and "
                f"alert_section = 'TAS' and "
                f"regexp_replace(tas_device_name, '_M$', '') = '{device_name}' and "
                f"interlock_name LIKE '%Maintenance%' and "
                f"alert_status != 'Close'"
            )
            
            maint_params = urdhva_base.queryparams.QueryParams()
            maint_params.q = equipment_maintenance_query
            
            # Get the count using the framework's method
            maintenance_alerts = await hpcl_ceg_model.Alerts.get_all(maint_params, resp_type='plain')
            maintenance_data = maintenance_alerts.get("data", [])
            maintenance_alert_count += len(maintenance_data)
        
        # Count devices with rosov_pl_mode = "close"
        rosov_pl_close_query = f"bu = 'TAS' and sap_id = '{sap_id}' and alert_section = 'TAS' and interlock_name = '{rosov_pl_mode}' and alert_status = 'Close' AND created_at >= NOW() - INTERVAL '{time_window} seconds'"
        rosov_params = urdhva_base.queryparams.QueryParams()
        rosov_params.q = rosov_pl_close_query
        rosov_pl_results = await hpcl_ceg_model.Alerts.get_all(rosov_params, resp_type='plain')
        rosov_pl_data = rosov_pl_results.get("data", [])
        rosov_pl_close_count = len(rosov_pl_data)
        
        # Count devices with esd_close_status
        esd_close_query = f"esd_close_status IS NOT NULL AND esd_close_status != '' AND created_at >= NOW() - INTERVAL '{time_window} seconds'"
        esd_status_params = urdhva_base.queryparams.QueryParams()
        esd_status_params.q = esd_close_query
        esd_status_results = await hpcl_ceg_model.Alerts.get_all(esd_status_params, resp_type='plain')
        esd_status_data = esd_status_results.get("data", [])
        esd_close_status_count = len(esd_status_data)
        
        # Calculate total count
        total_count = maintenance_alert_count + rosov_pl_close_count + esd_close_status_count
        
        # Get total tank count from architecture data
        arch_query = f"sap_id = '{sap_id}'"
        arch_params = urdhva_base.queryparams.QueryParams()
        arch_params.q = arch_query
        arch_params.fields = ["total_tank_count", "name"]
        arch_data = await hpcl_ceg_model.ArchitectureData.get_all(arch_params, resp_type='plain')
        
        # Calculate distinct tank count
        total_tank_count = 0
        if arch_data and "data" in arch_data:
            # Get unique tank counts
            unique_tank_counts = set(item.get("total_tank_count", 0) for item in arch_data["data"])
            total_tank_count = len(unique_tank_counts)
        
        # Compare counts and create alert if they match
        if total_count == total_tank_count:
            alert_message = "All ROSOVs closed (Except PL Receipt)"
            
            # Create alert using the framework's method
            alert_data = {
                "BU": bu,
                "sap_id": sap_id,
                "location_name": "",
                "sop_id": "SOP02A",
                "interlock_name": alert_message,
                "alert_status": "Open",
                "alert_state": "InProgress",
                "severity": "CRITICAL",
                "alert_section": "TAS"
            }
            
            # Create the alert and get its ID
            created_alert = await alert_create.AlertFactory().create_alert(alert_data=alert_data)
            
            # Extract the unique_id and id from the created alert
            if created_alert and isinstance(created_alert, dict):
                alert_unique_id = created_alert.get("unique_id")
                alert_id = created_alert.get("id")
                
                # Add the IDs to alert_data for closing
                alert_data["unique_id"] = alert_unique_id
                alert_data["id"] = alert_id
                
                # Close the alert workflow
                await alert_close.close_tas_workflow(alert_data=alert_data)
                
                return {"status": "success", "message": alert_message, "count": total_count, 
                        "alert_id": alert_id, "unique_id": alert_unique_id}
            else:
                return {"status": "alert creation failed", "message": "Could not get alert ID"}
        else:
            return {"status": "counts don't match", "total_count": total_count, "tank_count": total_tank_count}
