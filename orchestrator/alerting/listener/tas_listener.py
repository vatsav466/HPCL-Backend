import json
# import pika
import asyncio
from orchestrator.alerting.alert_manager import create_alert, close_alert


async def tas_listener():
    # rmsg = {
    #             'id': {
    #                 'entityType': 'ALARM',
    #                 'id': '59358eaa-e63c-4bb7-a6cb-9d93f3aa5fe4'
    #             },
    #             'createdTime': 1731158003250,
    #             'tenantId': {
    #                 'entityType': 'TENANT',
    #                 'id': '63047880-9e7e-11ef-b675-7b97434ac894'
    #             },
    #             'customerId': {
    #                 'entityType': 'CUSTOMER',
    #                 'id': '04dd5bb0-9e9b-11ef-b5e6-6160ba8389b4'
    #             },
    #             'type': 'Tank2Lowlevel',
    #             'originator': {
    #                 'entityType': 'DEVICE',
    #                 'id': 'd5c6bff0-9e96-11ef-b5e6-6160ba8389b4'
    #             },
    #             'severity': 'CRITICAL',
    #             'acknowledged': False,
    #             'cleared': False,
    #             'assigneeId': None,
    #             'startTs': 1731158003205,
    #             'endTs': 1731158003205,
    #             'ackTs': 0,
    #             'clearTs': 0,
    #             'assignTs': 0,
    #             'propagate': False,
    #             'propagateToOwner': False,
    #             'propagateToTenant': False,
    #             'propagateRelationTypes': [
                    
    #             ],
    #             'originatorName': 'FireWaterlevel1',
    #             'originatorLabel': 'FireWaterlevel1',
    #             'assignee': None,
    #             'name': 'Tank2Lowlevel',
    #             'status': 'ACTIVE_UNACK',
    #             'details': {
    #                 'additionalInfo': {
    #                     'gateway': False,
    #                     'overwriteActivityTime': False,
    #                     'description': '',
    #                     'interlockName': 'HealthinessofFireWaterLevelsinTanks',
    #                     'message': 'WatervolumeintheTank2isbelowthreshold',
    #                     'unitName': 'FireWaterlevel1',
    #                     'plantlocation': 'bng',
    #                     'plantlocationid': '11bng',
    #                     'BU': 'LPG',
    #                     'sapid': 'sap123',
    #                     'sopid': 'SOP004',
    #                     'deviceId': 'd5c6bff0-9e96-11ef-b5e6-6160ba8389b4',
    #                     'deviceName': 'Tank2-FireWaterlevel1',
    #                     'deviceType': 'FireWaterTank'
    #                 }
    #             }
    #         }
    rmsg = json.loads(alert_body)
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
        # ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print("Exception in processing RQ message:%s" % e)


def RabbitConsume():
    qname = 'AlertManager'
    credentials = pika.PlainCredentials(config.rabbitMqUsername, config.rabbitMqPassword)
    parameters = pika.ConnectionParameters(config.rabbitMqIp, 5672, '/', credentials)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue=qname)
    channel.basic_consume(queue=qname, on_message_callback=callback)
    channel.start_consuming()


if __name__ == "__main__":
    asyncio.run(tas_listener())
