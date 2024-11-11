import datetime
import pytz
import asyncio
import traceback
import json
import ast
import UrdhvaBase
from api_manager import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class SendCommandLpg:
    async def get_required_variables(self):
        return ["alertid", "interrupt"]
    
    # async def sendRQMessage(queuename, messageBody):
    #     credentials = pika.PlainCredentials(config.rabbitMqUsername, config.rabbitMqPassword)
    #     parameters = pika.ConnectionParameters(config.rabbitMqIp, 5672, '/', credentials, heartbeat=30)
    #     connection = pika.BlockingConnection(parameters)
    #     channel = connection.channel()
    #     channel.queue_declare(queue=queuename)
    #     channel.basic_publish(exchange='', routing_key=queuename, body=json.dumps(messageBody))
    
    async def lpgSendMultiCommand(self, alert_id, sap_id, interuptName):
        try:
            if interuptName not in ['UnTripPlant', 'TripPlant']:
                return False, "Invalid Input"
            # get the alertdata
            alert_data = await hpcl_ceg_model.Alerts.get(alert_id)

            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            altHistory = alert_data['alertHistory']
            IST = pytz.timezone('Asia/Kolkata')
            currentTime = datetime.datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")
            redis_client = await zolix_base.redispool.get_redis_connection()
            trip_key = "LPG_MultiTrip_command_tag"
            tripCmd = await redis_client.hget(trip_key, sap_id)
            tagpath, tagpath1, tvalue = "", "", ""
            if tripCmd:
                tripData = json.loads(tripCmd)
                for key, val in tripData.items():
                    if key == "cmd1":
                        for k, v in val.items():
                            tagpath = k
                            tvalue = v
                    if key == "cmd2":
                        for k, v in val.items():
                            tagpath1 = k
                            tvalue = v
            cmdTags = []
            if not tagpath and not tagpath1:
                return
            if alert_data['deviceName'] in ["OLD/VLD 1", "OLDVLD1", "OLD/VLD1", "OLDVLD 1", "OLD_VLD Communication Loss"]:
                cmdTags.append(tagpath)
            elif alert_data['deviceName'] in ["OLD/VLD 2", "OLDVLD2", "OLD/VLD2", "OLDVLD 2"]:
                cmdTags.append(tagpath1)
            else:
                cmdTags.append(tagpath1)
                cmdTags.append(tagpath)

            if interuptName == "UnTripPlant":
                if str(tvalue) in ["0", "1"]:
                    if str(tvalue) == "0":
                        tvalue = 1
                    else:
                        tvalue = 0
                else:
                    tvalue = not tvalue

            for item in cmdTags:
                tagpath = item
                messageBody = {"tagsData": {tagpath: tvalue}}
                # await self.sendRQMessage(sap_id, messageBody)
                altHistory.append("Plant Trip Command sent : %s : %s At: %s" % (tagpath, str(tvalue), str(currentTime)))
                print("Received input for tripping the plant %s" % str(sap_id))
                for i in range(3):
                    try:
                        alert_data['isTripped'] = True
                        alert_data['alertHistory'] = altHistory
                        data_object = hpcl_ceg_model.Alerts(**alert_data)
                        await data_object.modify()
                        break
                    except Exception as e:
                        print("Exception updating isTripped Error:%s Traceback %s" % (e, traceback.format_exc()))
                        await asyncio.sleep(10)
                else:
                    print("Unknown interrupt came")

        except Exception as e:
            print("Exception Occured While Sending Command for alert %s ", alert_id)
            print(e)
            print("Traceback %s" % traceback.format_exc())


    async def sendcommand_lpg(self, alert_id, interuptName):
        print('SENDING COMMAND TO LPG alertId:%s' % alert_id)
        try:
            redis_client = await zolix_base.redispool.get_redis_connection()
            alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
            if alert_data:
                if not isinstance(alert_data, dict):
                    alert_data = alert_data.__dict__
                else:
                    alert_data = alert_data
            
            else:
                print("Received a interrupt for unknown alert %s" % alert_id)
                return True, {"sendcommand": False}
            
            sap_id = alert_data['sapId']
            if str(sap_id) in ['3408', "3307", "3204", "3108", "3202", "3406", "3305", "3201", "3110"]:
                await self.lpgSendMultiCommand(alert_id, str(sap_id), interuptName)
                return True, {"sendcommand": True}
            
            enabledPlantKey = "LPG-Plant-Enabled-For-Send-command"
            enbPlant = await redis_client.lrange(enabledPlantKey, 0, -1)
            if str(sap_id) not in enbPlant:
                print("sapId : %s Not Enabled for Write Command" % str(sapId))
                return True, {"sendcommand": True}
            key = "LPG-" + sap_id + "-tripCount"
            #tripCmdCount = await redis_client.hget(key, "LPG")
            altHistory = alert_data['alertHistory']
            IST = pytz.timezone('Asia/Kolkata')
            currentTime = datetime.datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")

            tagpath = "Applications.MODBUS.Modbus.CCC_CF_MOTOR_TRIPOUT.Value"
            tagValue = False
            trip_key = "LPG_Trip_command_tag"
            tripCmd = await redis_client.hget(trip_key, sap_id)
            if tripCmd:
                tripData = json.loads(tripCmd)
                for key, val in tripData.items():
                    tagpath = key
                    tagValue = val
            
            if interuptName == "TripPlant":
                messageBody = {"tagsData": {tagpath: tagValue}}
                # await self.sendRQMessage(sap_id, messageBody)
                altHistory.append("Plant Trip Command sent : %s : %s At: %s" % (tagpath, str(tagValue), str(currentTime)))
                print("Received input for tripping the plant %s" % str(sap_id))
                for i in range(3):
                    try:
                        alert_data['isTripped'] = True
                        alert_data['alertHistory'] = altHistory
                        data_object = hpcl_ceg_model.Alerts(**alert_data)
                        await data_object.modify()
                        break
                    except Exception as e:
                        print("Exception updating isTripped Error:%s Traceback %s" % (e, traceback.format_exc()))
                        await asyncio.sleep(10)
            elif interuptName == "UnTripPlant":
                if str(tagValue) in ["0", "1"]:
                    if str(tagValue) == "0":
                        tagValue = 1
                    else:
                        tagValue = 0
                else:
                    tagValue = not tagValue
                print("Recieved input for untripping the plant %s" % str(sap_id))
                altHistory.append("Plant UnTrip Command sent : %s : %s At: %s" % (tagpath, str(tagValue), str(currentTime)))
                messageBody = {"tagsData": {tagpath: tagValue}}
                # await self.sendRQMessage(sap_id, messageBody)
                for i in range(3):
                    try:
                        alert_data['alertHistory'] = altHistory
                        data_object = hpcl_ceg_model.Alerts(**alert_data)
                        await data_object.modify()
                        break
                    except Exception as e:
                        print("Exception updating UnTripPlant Error:%s Traceback %s" % (e, traceback.format_exc()))
                        await asyncio.sleep(10)
            else:
                print("Unknown interrupt came")
        except Exception as e:
            print("Exception Occured While Sending Command for alert %s ", alert_id)
            print(e)
            print("Traceback %s" % traceback.format_exc())
        
        return True, {"sendcommand": True}
