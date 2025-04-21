import urdhva_base
import re
import datetime
import traceback
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("maintenance_alert_processing_log")

async def maintenance_alert_check(alert_data):
    """
    Check if an alert should be created based on maintenance status and existing alerts.
    
    Returns:
        bool: True if alert should be skipped (don't create), False if alert should be created
    """
    try:
        print("alert_data ---> ", alert_data)
        related_equipment_names = ["VFT", "RADAR", "ROSOV", "MOV", "RIMSEAL"]
        current_equipment_name = alert_data.get('equipment_name', '')
        original_device_name = alert_data.get('device_name', '')
        interlock_name = alert_data.get('interlock_name', '')
        device_id = alert_data.get('device_id', '')

        # Extract tas_device_name
        if re.match(r'^[A-Z]+-\d+_', original_device_name):
            tas_device_name = original_device_name.split('_', 1)[1]
        else:
            tas_device_name = original_device_name

        # First, check if there's an existing Tank_Under Maintenance alert for this device
        maintenance_query = (
            f"""bu = 'TAS' and """
            f"""alert_section = 'TAS' and """
            f"""device_id = '{device_id}' and """
            f"""tas_device_name = '{tas_device_name}' and """
            f"""device_type = '{alert_data.get('device_type', '')}' and """
            f"""interlock_name = 'Tank_Under Maintenance' and """
            f"""alert_status != 'Close'"""
        )
        print(f"Checking if tank is under maintenance with query: {maintenance_query}")
        logger.debug(f"Checking if tank is under maintenance with query: {maintenance_query}")
        maintenance_params = urdhva_base.queryparams.QueryParams(q=maintenance_query)
        maintenance_resp = await hpcl_ceg_model.Alerts.get_all(maintenance_params, resp_type='plain')
        
        tank_under_maintenance_exists = len(maintenance_resp.get("data", [])) > 0
        
        # RULE 1: If this is a Tank_Under Maintenance alert
        if interlock_name == 'Tank_Under Maintenance':
            # Only create if it doesn't already exist
            if not tank_under_maintenance_exists:
                print(f"Creating Tank_Under Maintenance alert")
                logger.info(f"Creating Tank_Under Maintenance alert")
                return False  # Create the alert
            else:
                print(f"Tank_Under Maintenance alert already exists - skipping duplicate")
                logger.info(f"Tank_Under Maintenance alert already exists - skipping duplicate")
                return True  # Skip duplicate maintenance alert
                
        # RULE 2: If this is a related equipment alert
        if current_equipment_name in related_equipment_names:
            # Check if Tank_Under Maintenance exists
            if tank_under_maintenance_exists:
                # If Tank_Under Maintenance exists, skip all related equipment alerts
                print(f"Tank under maintenance exists - skipping related equipment alert for {current_equipment_name}")
                logger.info(f"Tank under maintenance exists - skipping related equipment alert for {current_equipment_name}")
                return True  # Skip related equipment alert
            else:
                # If no Tank_Under Maintenance, create related equipment alerts
                print(f"No Tank_Under Maintenance - creating alert for related equipment {current_equipment_name}")
                logger.info(f"No Tank_Under Maintenance - creating alert for related equipment {current_equipment_name}")
                return False  # Create the related equipment alert
        
        # For non-related equipment, check for equipment-specific maintenance
        if not interlock_name.endswith("Maintenance"):
            if tas_device_name.endswith('_M'):
                tas_device_name_for_query = tas_device_name[:-2]  # remove last 2 characters
            else:
                tas_device_name_for_query = tas_device_name
                
            equipment_maintenance_query = (
                f"""bu = 'TAS' and """
                f"""alert_section = 'TAS' and """
                f"""regexp_replace(tas_device_name, '_M$', '') = '{tas_device_name_for_query}' and """
                f"""interlock_name LIKE '%Maintenance%' and """
                f"""alert_status != 'Close'"""
            )
            print(f"Equipment maintenance check query: {equipment_maintenance_query}")
            logger.debug(f"Equipment maintenance check query: {equipment_maintenance_query}")
            equipment_maintenance_params = urdhva_base.queryparams.QueryParams(q=equipment_maintenance_query)
            equipment_maintenance_resp = await hpcl_ceg_model.Alerts.get_all(equipment_maintenance_params, resp_type='plain')
            
            if equipment_maintenance_resp["data"]:
                print(f"Equipment {current_equipment_name} has a maintenance alert - skipping new alert")
                logger.info(f"Equipment {current_equipment_name} has a maintenance alert - skipping new alert")
                return True  # Skip alert creation - maintenance alert exists for the same equipment
        
        # If we got here, no reason to skip the alert
        print(f"No blocking conditions found - alert will be created")
        logger.info(f"No blocking conditions found - alert will be created")
        return False  # Create the alert
   
    except Exception as e:
        print(f"Error in maintenance alert check: {e}")
        print(traceback.format_exc())
        logger.error(f"Error in maintenance alert check: {e}")
        logger.error(traceback.format_exc())
        # In case of error, let the alert through by default
        return False



    #     # logger.info(f"Checking alert creation conditions for device: {alert_data.get('device_name', '')}")
        
    #     # # Extract business unit, defaulting to 'TAS' if not provided
    #     # bu = alert_data.get('bu', 'TAS')
        
    #     # # Check for direct duplicates first (same device and interlock name)
    #     # query = (
    #     #     f"""bu = '{bu}' and """
    #     #     f"""alert_section = 'TAS' and """
    #     #     f"""device_id = '{alert_data.get('device_id', '')}' and """
    #     #     f"""device_name = '{alert_data.get('device_name', '')}' and """
    #     #     f"""interlock_name = '{alert_data.get('interlock_name', '')}' and """
    #     #     f"""alert_status != 'Close'"""
    #     # )
    #     # params = urdhva_base.queryparams.QueryParams(q=query)
    #     # logger.debug(f"Direct duplicate check query: {query}")
    #     # resp = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
        
    #     # if resp["data"]:
    #     #     logger.info(f"Duplicate alert found for device: {alert_data.get('device_name')}")
    #     #     return True  # Skip alert creation - duplicate exists
        
    #     # # Check for same device_type alerts
    #     # device_type = alert_data.get('device_type')
    #     # if device_type:
    #     #     query_equipment = (
    #     #         f"""bu = '{bu}' and """
    #     #         f"""alert_section = 'TAS' and """
    #     #         f"""device_type = '{device_type}' and """
    #     #         f"""alert_status != 'Close'"""
    #     #     )
    #     #     logger.debug(f"Equipment check query: {query_equipment}")
    #     #     params_equipment = urdhva_base.queryparams.QueryParams(q=query_equipment)
    #     #     resp_equipment = await hpcl_ceg_model.Alerts.get_all(params_equipment, resp_type='plain')
            
    #     #     if resp_equipment["data"]:
    #     #         logger.info(f"Alert already exists for equipment type: {device_type}")
    #     #         return True  # Skip alert creation - alert for same equipment type exists
        
    #     # Special handling for equipment related to tanks under maintenance
    #     print("alert_data ---> ", alert_data)
    #     related_equipment_names = ["VFT", "RADAR", "ROSOV", "MOV", "RIMSEAL"]
    #     current_equipment_name = alert_data.get('equipment_name', '')
    #     original_device_name = alert_data.get('device_name', '')

    #     # Extract tas_device_name
    #     if re.match(r'^[A-Z]+-\d+_', original_device_name):
    #         tas_device_name = original_device_name.split('_', 1)[1]
    #     else:
    #         tas_device_name = original_device_name

    #     # Always check Tank_Under Maintenance first
    #     maintenance_query = (
    #         f"""bu = 'TAS' and """
    #         f"""alert_section = 'TAS' and """
    #         f"""device_id = '{alert_data.get('device_id', '')}' and """
    #         f"""tas_device_name = '{tas_device_name}' and """
    #         f"""device_type = '{alert_data.get('device_type', '')}' and """
    #         f"""interlock_name = 'Tank_Under Maintenance' and """
    #         f"""alert_status != 'Close'"""
    #     )
    #     print(f"Checking if tank is under maintenance with query: {maintenance_query}")
    #     logger.debug(f"Checking if tank is under maintenance with query: {maintenance_query}")
    #     maintenance_params = urdhva_base.queryparams.QueryParams(q=maintenance_query)
    #     maintenance_resp = await hpcl_ceg_model.Alerts.get_all(maintenance_params, resp_type='plain')

    #     if maintenance_resp["data"]:
    #         print(f"Tank under maintenance - skipping alert for {current_equipment_name}")
    #         logger.info(f"Tank under maintenance - skipping alert for {current_equipment_name}")
    #         return True  # Skip alert creation if tank is under maintenance

    #     # Now, if equipment is in related list and tank is not under maintenance, allow the alert
    #     if current_equipment_name in related_equipment_names:
    #         print(f"Skipping Alert creation - for {current_equipment_name} as Tank is under Maintenance")
    #         logger.info(f"Skipping Alert creation - for {current_equipment_name} as Tank is under Maintenance")
    #         return True  # Allow alert creation

    #     # New logic: Check for alerts with maintenance interlock for the same equipment_name
    #     interlock_name = alert_data.get('interlock_name', '')
    #     if tas_device_name.endswith('_M'):
    #         tas_device_name_for_query = tas_device_name[:-2]  # remove last 2 characters
    #     else:
    #         tas_device_name_for_query = tas_device_name
    #     # Only perform this check if the current alert's interlock name does NOT end with "Maintenance"
    #     if not interlock_name.endswith("Maintenance"):
    #         print(f"Checking for maintenance alerts for equipment: {current_equipment_name}")
    #         logger.debug(f"Checking for maintenance alerts for equipment: {current_equipment_name}")
            
    #         # Query for any alerts with the same equipment_name where interlock_name ends with "Maintenance"
    #         equipment_maintenance_query = (
    #             f"""bu = 'TAS' and """
    #             f"""alert_section = 'TAS' and """
    #             f"""regexp_replace(tas_device_name, '_M$', '') = '{tas_device_name_for_query}' and """
    #             f"""interlock_name LIKE '%Maintenance%' and """
    #             f"""alert_status != 'Close'"""
    #         )
    #         print(f"Equipment maintenance check query: {equipment_maintenance_query}")
    #         logger.debug(f"Equipment maintenance check query: {equipment_maintenance_query}")
    #         equipment_maintenance_params = urdhva_base.queryparams.QueryParams(q=equipment_maintenance_query)
    #         equipment_maintenance_resp = await hpcl_ceg_model.Alerts.get_all(equipment_maintenance_params, resp_type='plain')
            
    #         if equipment_maintenance_resp["data"]:
    #             print(f"Equipment {current_equipment_name} has a maintenance alert - skipping new alert")
    #             logger.info(f"Equipment {current_equipment_name} has a maintenance alert - skipping new alert")
    #             return True  # Skip alert creation - maintenance alert exists for the same equipment
        
    #     # If we got here, no reason to skip the alert
    #     logger.info(f"No blocking conditions found - alert will be created")
    #     return False  # Create the alert
        
    # except Exception as e:
    #     logger.error(f"Error in maintenance alert check: {e}")
    #     logger.error(traceback.format_exc())
    #     # In case of error, let the alert through by default
    #     return False
