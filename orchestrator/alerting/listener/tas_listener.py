# import urdhva_base
# import json
# # import pika
# import asyncio
# import traceback
# from orchestrator.alerting.alert_manager import create_alert, close_alert
# import os


# def load_device_data(sap_id):
#     try:
#         data_path = f"/opt/ceg/algo/things_board/device_data/{sap_id}.json"
#         with open(data_path, 'r') as file:
#             return json.load(file)
#     except Exception as e:
#         print(f"Error loading device data for SAP ID {sap_id}: {e}")
#         return None


# def get_sensor_id(device_name, equipment_type, device_data):
#     for device in device_data.get("data", []):
#         if device.get("device_name") == device_name:
#             for sensor in device.get("sensors", []):
#                 if sensor.get("sensor_type") == equipment_type:
#                     return sensor.get("sensor_id")
#     return None


# def fix_additional_info(additional_info):
#     for key, value in {"interlockName": "interlock_name", "BU": "bu", "sopid": "sop_id",
#                        "plantlocationid": "sap_id", "deviceId": "device_id", "deviceType": "device_type",
#                        "deviceName": "device_name", "Sensor_Type":"equipment_type", "Sensor_Name":"equipment_name"}.items():
#         if key in additional_info:
#             additional_info[value] = additional_info[key]
    
#     sap_id = additional_info.get("sap_id")
#     device_name = additional_info.get("device_name")
#     equipment_type = additional_info.get("equipment_type")

#     #Always include the original device_name as tas_device_name
#     if device_name:
#         additional_info["tas_device_name"] = device_name

#     if sap_id and device_name and equipment_type:
#         device_data = load_device_data(sap_id)
#         if device_data:
#             sensor_id = get_sensor_id( device_name, equipment_type, device_data)
#             if sensor_id:
#                 additional_info["sensor_id"] = sensor_id
#                 additional_info["device_name"] = f"{sensor_id}_{device_name}"    
#     return additional_info


# async def tas_listener(rmsg):
#     print(rmsg)
#     try:
#         if rmsg.get("details") and rmsg["details"].get("additionalInfo"):
#             rmsg["details"]["additionalInfo"] = fix_additional_info(rmsg["details"]["additionalInfo"])
#         print('-' * 12)
#         if rmsg['status'] == 'ACTIVE_UNACK':
#             alertdata = rmsg['details']['additionalInfo']
#             alertdata['severity'] = rmsg['severity']
#             alertdata['alert_type'] = rmsg['details']['additionalInfo']['bu']
#             alertdata['alert_id'] = rmsg['id']['id']
#             # alertdata['equipment_type'] = rmsg['details']['additionalInfo'].get('sensor_type', '')
#             # alertdata['equipment_name'] = rmsg['details']['additionalInfo'].get('sensor_name', '')
#             custom_data = rmsg['details']['additionalInfo'].get("customData", {})
            

#             alertdata['message'] = ", ".join([f"{key}={value}" for key, value in custom_data.items()])
#             print("Create Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
#                                                         rmsg['type']))
#             await create_alert(alertdata)
#         elif rmsg['status'] == 'CLEARED_UNACK':
#             alertdata = rmsg['details']['additionalInfo']
#             alertdata['alert_type'] = rmsg['details']['additionalInfo']['bu']
#             alertdata['alert_id'] = rmsg['id']['id']
#             print("Close Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
#                                                         rmsg['type']))
#             await close_alert(alertdata)
#         else:
#             print("Invalid message received:%s" % rmsg)
#         return True
#     except Exception as e:
#         print(traceback.format_exc())
#         print("Exception in processing RQ message:%s" % e)


# # async def RabbitConsume():
# #     qname = 'AlertManager'
# #     credentials = pika.PlainCredentials(config.rabbitMqUsername, config.rabbitMqPassword)
# #     parameters = pika.ConnectionParameters(config.rabbitMqIp, 5672, '/', credentials)
# #     connection = pika.BlockingConnection(parameters)
# #     channel = connection.channel()
# #     channel.queue_declare(queue=qname)
# #     channel.basic_consume(queue=qname, on_message_callback=callback)
# #     channel.start_consuming()


# if __name__ == "__main__":
# #     asyncio.run(tas_listener())


#     rmsg = {
#     "tenantId": {
#         "entityType": "TENANT",
#         "id": "92026430-bab2-11ef-a2e1-e9d5c168f7f6"
#     },
#     "type": "Tankoverfill Alarm",
#     "originator": {
#         "entityType": "DEVICE",
#         "id": "11484100-f7f9-11ef-a29d-95c64d391b7c"
#     },
#     "severity": "CRITICAL",
#     "status": "ACTIVE_UNACK",
#     "startTs": 1744627317655,
#     "endTs": 1744627317655,
#     "ackTs": 0,
#     "clearTs": 0,
#     "details": {
#         "additionalInfo": {
#             "location_id": "1919",
#             "location_name": "Secunderabad",
#             "plantlocationid": "1919",
#             "plantlocation": "Secunderabad",
#             "bu_id": "79980420-bab4-11ef-89d8-8bef67f22d63",
#             "SAPID": "1919",
#             "BU": "TAS",
#             "MOV_BIO HSD@Secunderabad": 1,
#             "Primary Gauge Level": "0",
#             "TANK LEAKAGE STATUS": "0",
#             "Primary Gauge HIGH": "0",
#             "Primary Gauge HIGH HIGH": "0",
#             "LEVEL SWITCH": "0",
#             "LEVEL SWITCH PROOF OK": "0",
#             "LEVEL SWITCH PROOF FAILED": "0",
#             "RADAR HHH": "0",
#             "RADAR PROOF OK": "0",
#             "RADAR PROOF FAILED": "0",
#             "ROSOV OPEN STATUS IL1": "0",
#             "ROSOV FAIL TO CLOSE STATUS IL1": "0",
#             "ROSOV OPEN STATUS IL2": "0",
#             "ROSOV FAIL TO CLOSE STATUS IL2": "0",
#             "ROSOV OPEN STATUS OL": "0",
#             "ROSOV FAIL TO CLOSE STATUS OL": "0",
#             "ROSOV OPEN STATUS RCL": "0",
#             "ROSOV FAIL TO CLOSE STATUS RCL": "0",
#             "MOV STATUS IL1": "1",
#             "MOV STATUS IL2": "0",
#             "MOV STATUS OL": "0",
#             "MOV STATUS RCL": "0",
#             "RIMSEAL FIRE ALARM": "0",
#             "RIMSEAL FAULT ALARM": "0",
#             "deviceType": "Tank",
#             "deviceName": "51-TT-FR-001C_GASOHOL@Secunderabad",
#             "sap_id": "1919",
#             "interlockName": "HHH alarm from VFT",
#             "unitName": "51-TT-FR-001C_GASOHOL@Secunderabad",
#             "deviceId": "11484100-f7f9-11ef-a29d-95c64d391b7c",
#             "sopid": "SOP001",
#             "alert_category": "Safety",
#             "Sensor_Type": "VFT",
#             "severity": "Critical",
#             "customData": {
#                 "LEVEL SWITCH": "1",
#                 "MOV STATUS IL1": "0",
#                 "ROSOV OPEN STATUS IL1": "1",
#                 "RADAR HHH": "0",
#                 "MOV STATUS IL2": "1",
#                 "ROSOV OPEN STATUS IL2": "0",
#                 "LEVEL SWITCH PROOF FAILED": "0",
#                 "LEVEL SWITCH PROOF OK": "0",
#                 "ROSOV FAIL TO CLOSE STATUS IL1": "0",
#                 "ROSOV FAIL TO CLOSE STATUS IL2": "0",
#                 "ROSOV FAIL TO CLOSE STATUS OL": "0",
#                 "ROSOV FAIL TO CLOSE STATUS RCL": "0",
#                 "Primary Gauge HIGH": "0",
#                 "Primary Gauge HIGH HIGH": "0",
#                 "RADAR PROOF FAILED": "0",
#                 "RADAR PROOF OK": "0",
#                 "TANK LEAKAGE STATUS": "0"
#             },
#             "Sensor_Name": "VFT",
#             "Cause_Effect": "Cause"
#             # "effect_sop_id": ["SOP01A"]
#         }
#     },
#     "propagate": False,
#     "propagateRelationTypes": [],
#     "id": {
#         "entityType": "ALARM",
#         "id": "16d8fa72-191d-11f0-82ca-03bdbba508c1"
#     },
#     "createdTime": 1744627317655,
#     "name": "Tankoverfill Alarm"
# }
#     asyncio.run(tas_listener(rmsg))



import urdhva_base
import os
import json
# import pika
import asyncio
import traceback
import tas_duplicate_alert_check as duplicates_check
import tas_maintenance_alert_check as maintenance_check
from orchestrator.alerting.alert_manager import create_alert, close_alert

logger = urdhva_base.logger.Logger.getInstance("rabbitmq_processing_log")

def load_device_data(sap_id):
    """
    Load the device data for the given SAP ID from the json file.

    Args:
        sap_id (str): The SAP ID of the device

    Returns:
        dict: The device data loaded from the json file
    """
    try:
        data_path = f"/opt/ceg/algo/things_board/device_data/{sap_id}.json"
        with open(data_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading device data for SAP ID {sap_id}: {e}")
        return None

def get_sensor_id(device_name, equipment_type, device_data):
    """
    Get the sensor_id for a given device_name and equipment_type from the device_data

    Args:
        device_name (str): The name of the device
        equipment_type (str): The type of the sensor
        device_data (dict): The device data loaded from the json file

    Returns:
        str: The sensor_id if found, None if not
    """
    for device in device_data.get("data", []):
        if device.get("device_name") == device_name:
            for sensor in device.get("sensors", []):
                if sensor.get("sensor_type") == equipment_type:
                    return sensor.get("sensor_id")
    return None

def fix_additional_info(additional_info):
    """
    Fix the additional info for the alert by converting the keys to the standardized ones.
    If the additional info contains sap_id, device_name and equipment_type, it will load the device data and
    get the sensor_id by calling get_sensor_id. If the sensor_id is found, it will add the sensor_id and device_name
    to the additional info and return it.
    :param additional_info: A dictionary containing the additional info for the alert
    :return: A dictionary containing the fixed additional info
    """
    for key, value in {"interlockName": "interlock_name", "BU": "bu", "sopid": "sop_id", "SAPID": "sap_id",
                       "plantlocationid": "sap_id", "deviceId": "device_id", "deviceType": "device_type",
                       "deviceName": "device_name", "Sensor_Type":"equipment_type", "Sensor_Name":"equipment_name"}.items():
        if key in additional_info:
            additional_info[value] = additional_info[key]
    
    sap_id = additional_info.get("sap_id")
    device_name = additional_info.get("device_name")
    equipment_type = additional_info.get("equipment_type")
    #Always include the original device_name as tas_device_name
    if device_name:
        additional_info["tas_device_name"] = device_name
    if sap_id and device_name and equipment_type:
        device_data = load_device_data(sap_id)
        if device_data:
            sensor_id = get_sensor_id( device_name, equipment_type, device_data)
            if sensor_id:
                additional_info["sensor_id"] = sensor_id
                additional_info["device_name"] = f"{sensor_id}_{device_name}"    
    return additional_info


# async def tas_listener(rmsg):
#     """
#     Process a message from the ThingsBoard Rule Engine.

#     Process a message from the ThingsBoard Rule Engine. The message is expected to be a dictionary
#     containing details about the alarm. The 'status' key in the message is used to determine if the
#     alarm is being created or cleared. If the 'status' key is 'ACTIVE_UNACK', then the alarm is being
#     created and the function calls the create_alert function with the details from the message. If
#     the 'status' key is 'CLEARED_UNACK', then the alarm is being cleared and the function calls the
#     close_alert function with the details from the message. If the 'status' key is anything else, the
#     function prints an error message and returns False.

#     Args:
#         rmsg (dict): A dictionary containing details about the alarm. The dictionary should contain
#             the following keys: 'status', 'details', 'id', 'type', 'severity'.

#     Returns:
#         bool: True if the message was processed successfully, False otherwise.
#     """
#     print(rmsg)
#     try:
#         if rmsg.get("details") and rmsg["details"].get("additionalInfo"):
#             rmsg["details"]["additionalInfo"] = fix_additional_info(rmsg["details"]["additionalInfo"])
#         print('-' * 12)
#         if rmsg['status'] == 'ACTIVE_UNACK':
#             alertdata = rmsg['details']['additionalInfo']

#             # First, check if it's a duplicate
#             is_duplicate = await duplicates_check.duplicate_check(alertdata)
            
#             if is_duplicate:
#                 print(f"Alert already exists (duplicate) for: {alertdata}")
#             else:
#                 # Only check maintenance if not a duplicate
#                 is_maintenance_alert = await maintenance_check.maintenance_alert_check(alertdata)
                
#                 if is_maintenance_alert:
#                     print(f"Maintenance alert already exists for: {alertdata}")
#                 else:
#                     # Valid new alert, proceed to create it
#                     alertdata['severity'] = rmsg['severity']
#                     alertdata['alert_type'] = rmsg['details']['additionalInfo']['bu']
#                     alertdata['alert_id'] = rmsg['id']['id']
#                     custom_data = rmsg['details']['additionalInfo'].get("customData", {})
                    
#                     alertdata['message'] = ", ".join([f"{key}={value}" for key, value in custom_data.items()])
#                     print("Create Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
#                                                                 rmsg['type']))
#                     await create_alert(alertdata)

        # if rmsg['status'] == 'ACTIVE_UNACK':
        #     alertdata = rmsg['details']['additionalInfo']
        #     # Check both duplicate and maintenance alerts
        #     is_duplicate = await duplicates_check.duplicate_check(alertdata)
        #     is_maintenance_alert = await maintenance_check.maintenance_alert_check(alertdata)
            
        #     if not is_duplicate and not is_maintenance_alert:
        #         alertdata['severity'] = rmsg['severity']
        #         alertdata['alert_type'] = rmsg['details']['additionalInfo']['bu']
        #         alertdata['alert_id'] = rmsg['id']['id']
        #         custom_data = rmsg['details']['additionalInfo'].get("customData", {})
                
        #         alertdata['message'] = ", ".join([f"{key}={value}" for key, value in custom_data.items()])
        #         print("Create Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
        #                                                     rmsg['type']))
        #         await create_alert(alertdata)
        #     else:
        #         if is_duplicate:
        #             print(f"Alert already exists (duplicate) for: {alertdata}")
        #         if is_maintenance_alert:
        #             print(f"Maintenance alert already exists for: {alertdata}")
            # if not await duplicates_check.duplicate_check(alertdata):
            #     alertdata['severity'] = rmsg['severity']
            #     alertdata['alert_type'] = rmsg['details']['additionalInfo']['bu']
            #     alertdata['alert_id'] = rmsg['id']['id']
            #     # alertdata['equipment_type'] = rmsg['details']['additionalInfo'].get('sensor_type', '')
            #     # alertdata['equipment_name'] = rmsg['details']['additionalInfo'].get('sensor_name', '')
            #     custom_data = rmsg['details']['additionalInfo'].get("customData", {})
                
            #     alertdata['message'] = ", ".join([f"{key}={value}" for key, value in custom_data.items()])
            #     print("Create Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
            #                                                 rmsg['type']))
            #     await create_alert(alertdata)
            # else:
            #     print(f"Alert already exists for: {alertdata}")
    #     elif rmsg['status'] == 'CLEARED_UNACK':
    #         alertdata = rmsg['details']['additionalInfo']
    #         alertdata['alert_type'] = rmsg['details']['additionalInfo']['bu']
    #         alertdata['alert_id'] = rmsg['id']['id']
    #         print("Close Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
    #                                                     rmsg['type']))
    #         await close_alert(alertdata)
    #     else:
    #         print("Invalid message received:%s" % rmsg)
    #     return True
    # except Exception as e:
    #     print(traceback.format_exc())
    #     print("Exception in processing RQ message:%s" % e)


# async def RabbitConsume():
#     qname = 'AlertManager'
#     credentials = pika.PlainCredentials(config.rabbitMqUsername, config.rabbitMqPassword)
#     parameters = pika.ConnectionParameters(config.rabbitMqIp, 5672, '/', credentials)
#     connection = pika.BlockingConnection(parameters)
#     channel = connection.channel()
#     channel.queue_declare(queue=qname)
#     channel.basic_consume(queue=qname, on_message_callback=callback)
#     channel.start_consuming()

async def tas_listener(rmsg):
    """
    Process a message from the ThingsBoard Rule Engine.

    Process a message from the ThingsBoard Rule Engine. The message is expected to be a dictionary
    containing details about the alarm. The 'status' key in the message is used to determine if the
    alarm is being created or cleared. If the 'status' key is 'ACTIVE_UNACK', then the alarm is being
    created and the function calls the create_alert function with the details from the message. If
    the 'status' key is 'CLEARED_UNACK', then the alarm is being cleared and the function calls the
    close_alert function with the details from the message. If the 'status' key is anything else, the
    function prints an error message and returns False.

    Args:
        rmsg (dict): A dictionary containing details about the alarm. The dictionary should contain
            the following keys: 'status', 'details', 'id', 'type', 'severity'.

    Returns:
        bool: True if the message was processed successfully, False otherwise.
    """
    print(rmsg)
    try:
        if rmsg.get("details") and rmsg["details"].get("additionalInfo"):
            rmsg["details"]["additionalInfo"] = fix_additional_info(rmsg["details"]["additionalInfo"])
        print('-' * 12)
        if rmsg['status'] == 'ACTIVE_UNACK':
            alertdata = rmsg['details']['additionalInfo']
            alertdata['severity'] = rmsg['severity']
            alertdata['alert_type'] = rmsg['details']['additionalInfo']['bu']
            alertdata['alert_id'] = rmsg['id']['id']
            custom_data = rmsg['details']['additionalInfo'].get("customData", {})
            
            alertdata['message'] = ", ".join([f"{key}={value}" for key, value in custom_data.items()])
            print("Create Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
                                                        rmsg['type']))

            # First, check if it's a duplicate
            is_duplicate = await duplicates_check.duplicate_check(alertdata)
            
            if is_duplicate:
                print(f"Alert already exists (duplicate) for: {alertdata}")
            else:
                if alertdata['interlock_name'] in [
                    "VFT_UnderMaintenance", "Secondary Radar_Under Maintenance", 
                    "ROSOV_Under Maintenance", "MOV_Under Maintenance", 
                    "Rim Seal system_Under Maintenance", "Tank_UnderMaintenance"]:
                    print("into maintenance check")
                    await maintenance_check.create_under_maintenance_alert(alertdata)
                else:
                    print("into normal maintenance check")
                    is_maintenance_alert = await maintenance_check.maintenance_alert_check(alertdata)
                    if is_maintenance_alert:
                        print(f"Maintenance alert already exists for: {alertdata}")
                    else:
                        print("not maintenance alert")
                        await create_alert(alertdata)


        elif rmsg['status'] == 'CLEARED_UNACK':
            alertdata = rmsg['details']['additionalInfo']
            alertdata['alert_type'] = rmsg['details']['additionalInfo']['bu']
            alertdata['alert_id'] = rmsg['id']['id']
            print("Close Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
                                                        rmsg['type']))
            await close_alert(alertdata)
        else:
            print("Invalid message received:%s" % rmsg)
        return True
    except Exception as e:
        print(traceback.format_exc())
        print("Exception in processing RQ message:%s" % e)

# if __name__ == "__main__":
#     rmsg = {
#     "tenantId": {
#         "entityType": "TENANT",
#         "id": "92026430-bab2-11ef-a2e1-e9d5c168f7f6"
#     },
#     "type": "Tankoverfill Alarm",
#     "originator": {
#         "entityType": "DEVICE",
#         "id": "11484100-f7f9-11ef-a29d-95c64d391b7c"
#     },
#     "severity": "CRITICAL",
#     "status": "ACTIVE_UNACK",
#     "startTs": 1744627317655,
#     "endTs": 1744627317655,
#     "ackTs": 0,
#     "clearTs": 0,
#     "details": {
#         "additionalInfo": {
#             "location_id": "1919",
#             "location_name": "Secunderabad",
#             "plantlocationid": "1919",
#             "plantlocation": "Secunderabad",
#             "bu_id": "79980420-bab4-11ef-89d8-8bef67f22d63",
#             "SAPID": "1919",
#             "BU": "TAS",
#             "MOV_BIO HSD@Secunderabad": 1,
#             "Primary Gauge Level": "0",
#             "TANK LEAKAGE STATUS": "0",
#             "Primary Gauge HIGH": "0",
#             "Primary Gauge HIGH HIGH": "0",
#             "LEVEL SWITCH": "0",
#             "LEVEL SWITCH PROOF OK": "0",
#             "LEVEL SWITCH PROOF FAILED": "0",
#             "RADAR HHH": "0",
#             "RADAR PROOF OK": "0",
#             "RADAR PROOF FAILED": "0",
#             "ROSOV OPEN STATUS IL1": "0",
#             "ROSOV FAIL TO CLOSE STATUS IL1": "0",
#             "ROSOV OPEN STATUS IL2": "0",
#             "ROSOV FAIL TO CLOSE STATUS IL2": "0",
#             "ROSOV OPEN STATUS OL": "0",
#             "ROSOV FAIL TO CLOSE STATUS OL": "0",
#             "ROSOV OPEN STATUS RCL": "0",
#             "ROSOV FAIL TO CLOSE STATUS RCL": "0",
#             "MOV STATUS IL1": "1",
#             "MOV STATUS IL2": "0",
#             "MOV STATUS OL": "0",
#             "MOV STATUS RCL": "0",
#             "RIMSEAL FIRE ALARM": "0",
#             "RIMSEAL FAULT ALARM": "0",
#             "deviceType": "Tank",
#             "deviceName": "51-TT-FR-001C_GASOHOL@Secunderabad",
#             "sap_id": "1919",
#             "interlockName": "HHH alarm from VFT",
#             "unitName": "51-TT-FR-001C_GASOHOL@Secunderabad",
#             "deviceId": "11484100-f7f9-11ef-a29d-95c64d391b7c",
#             "sopid": "SOP001",
#             "alert_category": "Safety",
#             "Sensor_Type": "VFT",
#             "severity": "Critical",
#             "customData": {
#                 "LEVEL SWITCH": "1",
#                 "MOV STATUS IL1": "0",
#                 "ROSOV OPEN STATUS IL1": "1",
#                 "RADAR HHH": "0",
#                 "MOV STATUS IL2": "1",
#                 "ROSOV OPEN STATUS IL2": "0",
#                 "LEVEL SWITCH PROOF FAILED": "0",
#                 "LEVEL SWITCH PROOF OK": "0",
#                 "ROSOV FAIL TO CLOSE STATUS IL1": "0",
#                 "ROSOV FAIL TO CLOSE STATUS IL2": "0",
#                 "ROSOV FAIL TO CLOSE STATUS OL": "0",
#                 "ROSOV FAIL TO CLOSE STATUS RCL": "0",
#                 "Primary Gauge HIGH": "0",
#                 "Primary Gauge HIGH HIGH": "0",
#                 "RADAR PROOF FAILED": "0",
#                 "RADAR PROOF OK": "0",
#                 "TANK LEAKAGE STATUS": "0"
#             },
#             "Sensor_Name": "VFT",
#             "Cause_Effect": "Cause",
#             "effect_sop_id": ["SOP01A"]
#         }
#     },
#     "propagate": False,
#     "propagateRelationTypes": [],
#     "id": {
#         "entityType": "ALARM",
#         "id": "16d8fa72-191d-11f0-82ca-03bdbba508c1"
#     },
#     "createdTime": 1744627317655,
#     "name": "Tankoverfill Alarm"
# }
#     asyncio.run(tas_listener(rmsg))
#     # asyncio.run(tas_listener())