import urdhva_base
import json
# import pika
import asyncio
import traceback
from orchestrator.alerting.alert_manager import create_alert, close_alert


def fix_additional_info(additional_info):
    for key, value in {"interlockName": "interlock_name", "BU": "bu", "sopid": "sop_id",
                       "plantlocationid": "sap_id", "deviceId": "device_id", "deviceType": "device_type",
                       "deviceName": "device_name", "Sensor_Type":"equipment_type", "Sensor_Name":"equipment_name"}.items():
        if key in additional_info:
            additional_info[value] = additional_info[key]
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

