import urdhva_base
import re
import datetime
import traceback
import hpcl_ceg_model
from orchestrator.alerting.alert_manager import create_alert, close_alert

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

        # Extract tas_device_name
        if re.match(r'^[A-Z]+-\d+_', original_device_name):
            tas_device_name = original_device_name.split('_', 1)[1]
        else:
            tas_device_name = original_device_name

        # Always check Tank_Under Maintenance first
        # maintenance_query = (
        #     f"""bu = 'TAS' and """
        #     f"""sap_id != '{alert_data.get('sap_id', '')}' and """
        #     f"""alert_section = 'TAS' and """
        #     f"""device_id = '{alert_data.get('device_id', '')}' and """
        #     f"""tas_device_name = '{tas_device_name}' and """
        #     f"""device_type = '{alert_data.get('device_type', '')}' and """
        #     f"""interlock_name = 'Tank_Under Maintenance' and """
        #     f"""alert_status != 'Close'"""
        # )
        # print(f"Checking if tank is under maintenance with query: {maintenance_query}")
        # logger.debug(f"Checking if tank is under maintenance with query: {maintenance_query}")
        # maintenance_params = urdhva_base.queryparams.QueryParams(q=maintenance_query)
        # maintenance_resp = await hpcl_ceg_model.Alerts.get_all(maintenance_params, resp_type='plain')

        # if maintenance_resp["data"]:
        #     print(f"Tank under maintenance - skipping alert for {current_equipment_name}")
        #     logger.info(f"Tank under maintenance - skipping alert for {current_equipment_name}")
        #     return True  # Skip alert creation if tank is under maintenance

        # # Now, if equipment is in related list and tank is not under maintenance, allow the alert
        # if current_equipment_name in related_equipment_names:
        #     print(f"Skipping Alert creation - for {current_equipment_name} as Tank is under Maintenance")
        #     logger.info(f"Skipping Alert creation - for {current_equipment_name} as Tank is under Maintenance")
        #     return True  # Allow alert creation

        # New logic: Check for alerts with maintenance interlock for the same equipment_name
        interlock_name = alert_data.get('interlock_name', '')
        if tas_device_name.endswith('_M'):
            tas_device_name_for_query = tas_device_name[:-2]  # remove last 2 characters
        else:
            tas_device_name_for_query = tas_device_name
        # Only perform this check if the current alert's interlock name does NOT end with "Maintenance"
        if not interlock_name.endswith("Maintenance"):
            print(f"Checking for maintenance alerts for equipment: {current_equipment_name}")
            logger.debug(f"Checking for maintenance alerts for equipment: {current_equipment_name}")
            
            # Query for any alerts with the same equipment_name where interlock_name ends with "Maintenance"
            equipment_maintenance_query = (
                f"""bu = 'TAS' and """
                f"""sap_id = '{alert_data.get('sap_id', '')}' and """
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
        logger.info(f"No blocking conditions found - alert will be created")
        return False  # Create the alert
        
    except Exception as e:
        logger.error(f"Error in maintenance alert check: {e}")
        logger.error(traceback.format_exc())
        # In case of error, let the alert through by default
        return False

async def close_tas_workflow(alert_data):
    print(f"Closing camunda workflow for alert_id: {alert_data['id']}")
    data = {
        "messageName": "Message",
        "businessKey": alert_data['unique_id'],
        "processVariables": {"alert_id": {"value": alert_data['id'], "type": "String"},
                                "closed": {"value": True, "type": "Boolean"}}}

    url = await helpers.get_camunda_url(bu=alert_data['bu'], sap_id=alert_data['sap_id'],
                                        alert_section="TAS")
    url += "/engine-rest/message"
    try:
        r = httpx.post(url, headers={'Content-Type': 'application/json'}, json=data, verify=False)
        if int(r.status_code / 100) != 2:
            print(f"Error while sending message to camunda: {r.status_code} - {r.text}")
        else:
            print("Message sent to camunda")
    except Exception as e:
        logger.error(f"Exception in closing camunda flow {e} for alert_id {alert_data['id']}, "
                        f"business_key {alert_data['unique_id']}")
    await close_alert(alert_data=alert_data)

async def create_under_maintenance_alert(alert_data):
    print(f"Under maintenance alert - creating alert for {alert_data['tas_device_name']}")
    if alert_data['interlock_name'] == 'Tank_UnderMaintenance':
        print(f"maintenance alert - creating alert for {alert_data['tas_device_name']}")
        maintenance_query = (
                f"""bu = 'TAS' and """
                f"""sap_id = '{alert_data.get('sap_id', '')}' and """
                f"""alert_section = 'TAS' and """
                f"""device_id = '{alert_data.get('device_id', '')}' and """
                f"""created_at >= NOW() - INTERVAL '5 minutes' and """
                # f"""tas_device_name = '{tas_device_name}' and """
                # f"""device_type = '{alert_data.get('device_type', '')}' and """
                # f"""interlock_name = 'Tank_Under Maintenance' and """
                f"""alert_status != 'Close'"""
            )
        maintenance_params = urdhva_base.queryparams.QueryParams(q=maintenance_query)
        print("maintenance_query --> ", maintenance_query)

        maintenance_resp = await hpcl_ceg_model.Alerts.get_all(maintenance_params, resp_type='plain')
        print("maintenance_resp --> ", maintenance_resp)

        if maintenance_resp["data"]:
            print(f"Under maintenance alert - creating alert for {maintenance_resp["data"]}")
            for data in maintenance_resp["data"]:
                print(f"Under maintenance alert - creating alert for {data}")
                print("into close_tas_workflow")
                await close_tas_workflow(data)
            
            await create_alert(alert_data=alert_data)
    
    if alert_data['interlock_name'] != 'Tank_UnderMaintenance':
        print(f"not tank maintenance alert - creating alert for {alert_data['tas_device_name']}")
        maintenance_query = (
                f"""bu = 'TAS' and """
                f"""sap_id = '{alert_data.get('sap_id', '')}' and """
                f"""alert_section = 'TAS' and """
                f"""device_id = '{alert_data.get('device_id', '')}' and """
                # f"""tas_device_name = '{tas_device_name}' and """
                # f"""device_type = '{alert_data.get('device_type', '')}' and """
                f"""interlock_name = 'Tank_Under Maintenance' and """
                f"""alert_status != 'Close'"""
            )
        maintenance_params = urdhva_base.queryparams.QueryParams(q=maintenance_query)
        maintenance_resp = await hpcl_ceg_model.Alerts.get_all(maintenance_params, resp_type='plain')
        if maintenance_resp['data']:
            print(f"not tank Under maintenance alert - creating alert for {maintenance_resp['data']}")
            print(f"Tank Under Maintenance {alert_data}")
        else:
            await create_alert(alert_data=alert_data)