import urdhva_base
import json
# import pika
import asyncio
import traceback
from orchestrator.alerting.alert_manager import create_alert, close_alert


async def tas_listener(rmsg):
    print(rmsg)
    try:
        print('-' * 12)
        if rmsg['status'] == 'ACTIVE_UNACK':
            alertdata = rmsg['details']['additionalInfo']
            alertdata['severity'] = rmsg['severity']
            alertdata['alert_type'] = rmsg['details']['additionalInfo']['BU']
            alertdata['alert_id'] = rmsg['id']['id']
            print("Create Alert BU:%s SAPID:%s for:%s " % (alertdata.get('BU', ''), alertdata.get('sapid', ''),
                                                        rmsg['type']))
            await create_alert(alertdata)
        elif rmsg['status'] == 'CLEARED_UNACK':
            alertdata = rmsg['details']['additionalInfo']
            print("Close Alert BU:%s SAPID:%s for:%s " % (alertdata.get('BU', ''), alertdata.get('sapid', ''),
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