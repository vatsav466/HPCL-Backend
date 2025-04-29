import urdhva_base
import re
import time
import json
import httpx
import datetime
import traceback
import hpcl_ceg_model
import utilities.helpers as helpers
from orchestrator.alerting.alert_manager import create_alert, close_alert

logger = urdhva_base.logger.Logger.getInstance("maintenance_alert_processing_log")

async def maintenance_alert_check(alert_data):
    """
    Check if an alert should be created based on maintenance status and existing alerts.
    
    Returns:
        bool: True if alert should be skipped (don't create), False if alert should be created
    """
    try:
        logger.info(f"Checking maintenance status for alert_data: {json.dumps(alert_data, default=str)}")
        related_equipment_names = ["VFT", "RADAR", "ROSOV", "MOV", "RIMSEAL"]
        current_equipment_name = alert_data.get('equipment_name', '')
        original_device_name = alert_data.get('device_name', '')

        # Extract tas_device_name
        if re.match(r'^[A-Z]+-\d+_', original_device_name):
            tas_device_name = original_device_name.split('_', 1)[1]
        else:
            tas_device_name = original_device_name

        interlock_name = alert_data.get('interlock_name', '')
        if tas_device_name.endswith('_M'):
            tas_device_name_for_query = tas_device_name[:-2]  # remove last 2 characters
        else:
            tas_device_name_for_query = tas_device_name
            
        # Only perform this check if the current alert's interlock name does NOT end with "Maintenance"
        if not interlock_name.endswith("Maintenance"):
            logger.info(f"Checking for maintenance alerts for equipment: {current_equipment_name}")
            
            # Query for any alerts with the same equipment_name where interlock_name ends with "Maintenance"
            equipment_maintenance_query = (
                f"""bu = 'TAS' and """
                f"""sap_id = '{alert_data.get('sap_id', '')}' and """
                f"""alert_section = 'TAS' and """
                f"""regexp_replace(tas_device_name, '_M$', '') = '{tas_device_name_for_query}' and """
                f"""interlock_name LIKE '%Maintenance%' and """
                f"""alert_status != 'Close'"""
            )
            logger.info(f"Equipment maintenance check query: {equipment_maintenance_query}")
            equipment_maintenance_params = urdhva_base.queryparams.QueryParams(q=equipment_maintenance_query)
            equipment_maintenance_resp = await hpcl_ceg_model.Alerts.get_all(equipment_maintenance_params, resp_type='plain')
            
            if equipment_maintenance_resp["data"]:
                logger.info(f"Equipment {current_equipment_name} has a maintenance alert - skipping new alert")
                return True  # Skip alert creation - maintenance alert exists for the same equipment
        
        # If we got here, no reason to skip the alert
        logger.info(f"No blocking conditions found - alert will be created")
        return False  # Create the alert
        
    except Exception as e:
        logger.error(f"Error in maintenance alert check: {e}")
        logger.error(traceback.format_exc())
        # In case of error, let the alert through by default
        return False

async def close_tas_workflow(alert_data, message_type='Message'):
    try:
        alert_data['alert_type'] = 'TAS'
        alert_data['alert_id'] = alert_data.get('external_id', '')
        logger.info(f"Closing camunda workflow for alert_id: {alert_data.get('id')} {json.dumps(alert_data, default=str)}")
        data = {
            "messageName": message_type,
            "businessKey": alert_data['unique_id'],
            "processVariables": {
                "alert_id": {"value": alert_data['id'], "type": "String"},
                "closed": {"value": True, "type": "Boolean"}
            }
        }

        url = await helpers.get_camunda_url(bu=alert_data['bu'], sap_id=alert_data['sap_id'],
                                            alert_section="TAS")
        url += "/engine-rest/message"
        
        time.sleep(3)
        r = httpx.post(url, headers={'Content-Type': 'application/json'}, json=data, verify=False)
        if int(r.status_code / 100) != 2:
            logger.info(f"Error while sending message to camunda: {r.status_code} - {r.text}")
        else:
            logger.info("Message sent to camunda")
        
        await close_alert(alert_data=alert_data)
        
    except Exception as e:
        logger.error(f"Exception in closing camunda flow {e} for alert_id {alert_data.get('id', 'unknown')}, "
                    f"business_key {alert_data.get('unique_id', 'unknown')}")
        logger.error(traceback.format_exc())


async def create_under_maintenance_alert(alert_data):
    """
    Handle alerts related to equipment maintenance status.
    For "Tank_Under Maintenance" alerts, close any recent alerts for that device.
    For other alerts, check if a tank is under maintenance before creating.
    """
    try:
        logger.info(f"Processing maintenance alert for {alert_data.get('tas_device_name')}")
        
        if alert_data['interlock_name'] == 'Tank_Under Maintenance':
            logger.info(f"Processing Tank under maintenance alert for {alert_data.get('tas_device_name')}")
            
            # Wait briefly to ensure database consistency
            time.sleep(3)
            
            # Check for recent alerts on this device to close them
            maintenance_query = (
                f"""bu = 'TAS' and """
                f"""sap_id = '{alert_data.get('sap_id', '')}' and """
                f"""alert_section = 'TAS' and """
                f"""device_id = '{alert_data.get('device_id', '')}' and """
                f"""created_at >= NOW() - INTERVAL '5 minutes' and """
                f"""alert_status != 'Close'"""
            )
            maintenance_params = urdhva_base.queryparams.QueryParams(q=maintenance_query)
            logger.info(f"Tank maintenance query: {maintenance_query}")

            maintenance_resp = await hpcl_ceg_model.Alerts.get_all(maintenance_params, resp_type='plain')
            logger.debug(f"Maintenance query results: {json.dumps(maintenance_resp, default=str)}")

            if maintenance_resp["data"]:
                logger.info(f"Found {len(maintenance_resp['data'])} alerts to close for tank under maintenance")
                for data in maintenance_resp["data"]:
                    logger.info(f"Closing alert: {data.get('id')}")
                    await close_tas_workflow(data)
            
            # Create the maintenance alert
            await create_alert(alert_data=alert_data)
            return
        
        # Handle other (non-Tank_Under Maintenance) alerts
        else:
            logger.info(f"Processing non-tank maintenance alert for {alert_data.get('tas_device_name')}")
            
            # Check if there's an active Tank_Under Maintenance alert for this device
            maintenance_query = (
                f"""bu = 'TAS' and """
                f"""sap_id = '{alert_data.get('sap_id', '')}' and """
                f"""alert_section = 'TAS' and """
                f"""device_id = '{alert_data.get('device_id', '')}' and """
                f"""interlock_name = 'Tank_Under Maintenance' and """
                f"""alert_status != 'Close'"""
            )
            maintenance_params = urdhva_base.queryparams.QueryParams(q=maintenance_query)
            maintenance_resp = await hpcl_ceg_model.Alerts.get_all(maintenance_params, resp_type='plain')
            
            if maintenance_resp['data']:
                logger.info(f"Found Tank Under Maintenance alert - skipping alert creation for {alert_data.get('tas_device_name')}")
            else:
                logger.info(f"No Tank Under Maintenance found - creating alert for {alert_data.get('tas_device_name')}")
                await create_alert(alert_data=alert_data)
            return
            
    except Exception as e:
        logger.error(f"Error in create_under_maintenance_alert: {e}")
        logger.error(traceback.format_exc())
        # In case of error, create the alert by default to avoid missing critical alerts
        await create_alert(alert_data=alert_data)