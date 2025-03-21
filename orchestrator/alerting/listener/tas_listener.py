import urdhva_base
import json
# import pika
import asyncio
import traceback
from orchestrator.alerting.alert_manager import create_alert, close_alert
import os

def load_device_data(sap_id):
    try:
        data_path = f"/opt/ceg/algo/things_board/device_data/{sap_id}.json"
        with open(data_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading device data for SAP ID {sap_id}: {e}")
        return None

def get_sensor_id(device_name, equipment_type, device_data):
    for device in device_data.get("data", []):
        if device.get("device_name") == device_name:
            for sensor in device.get("sensors", []):
                if sensor.get("sensor_type") == equipment_type:
                    return sensor.get("sensor_id")
    return None

def fix_additional_info(additional_info):
    for key, value in {"interlockName": "interlock_name", "BU": "bu", "sopid": "sop_id",
                       "plantlocationid": "sap_id", "deviceId": "device_id", "deviceType": "device_type",
                       "deviceName": "device_name", "Sensor_Type":"equipment_type", "Sensor_Name":"equipment_name"}.items():
        if key in additional_info:
            additional_info[value] = additional_info[key]
    
    sap_id = additional_info.get("sap_id")
    device_name = additional_info.get("device_name")
    equipment_type = additional_info.get("equipment_type")

    if sap_id and device_name and equipment_type:
        device_data = load_device_data(sap_id)
        if device_data:
            sensor_id = get_sensor_id( device_name, equipment_type, device_data)
            if sensor_id:
                additional_info["sensor_id"] = sensor_id
                additional_info["device_name"] = f"{sensor_id}_{device_name}"    
    return additional_info


async def tas_listener(rmsg):
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
            # alertdata['equipment_type'] = rmsg['details']['additionalInfo'].get('sensor_type', '')
            # alertdata['equipment_name'] = rmsg['details']['additionalInfo'].get('sensor_name', '')
            custom_data = rmsg['details']['additionalInfo'].get("customData", {})
            

            alertdata['message'] = ", ".join([f"{key}={value}" for key, value in custom_data.items()])
            print("Create Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
                                                        rmsg['type']))
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


# async def RabbitConsume():
#     qname = 'AlertManager'
#     credentials = pika.PlainCredentials(config.rabbitMqUsername, config.rabbitMqPassword)
#     parameters = pika.ConnectionParameters(config.rabbitMqIp, 5672, '/', credentials)
#     connection = pika.BlockingConnection(parameters)
#     channel = connection.channel()
#     channel.queue_declare(queue=qname)
#     channel.basic_consume(queue=qname, on_message_callback=callback)
#     channel.start_consuming()


# if __name__ == "__main__":
#     asyncio.run(tas_listener())

