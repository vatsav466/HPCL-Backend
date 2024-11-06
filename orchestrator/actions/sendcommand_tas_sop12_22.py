from api_manager import dnc_schema_model
from constants import *
import config
import send_tas_rq_message
import traceback

class SendcommandTasSop1222:

    async def get_required_variables(self):
        return ["alertid", "interrupt"]
    
    async def sendcommand_tas(self, alert_id, interuptName):

        """
        -> It retrieves alert data from a database using dnc_schema_model.Alerts.get(alert_id).
        -> It extracts relevant information from the alert data, such as sap_id, sop_id, and deviceName.
        -> It constructs a message body based on the interrupt name, which can be either "terminateloading" 
        or "unterminateloading".
        -> It sends the message to TAS using send_tas_rq_message.sendTASRQMessage(sap_id, messageBody).
        -> It updates the alert data in the database to reflect the new state (tripped or untripped).
        -> If an exception occurs during this process, it prints an error message and returns a success response anyway.
        """
        
        print('SENDING COMMAND TO TAS FOR AlertId:%s' % alert_id)

        try:
            alert_data = await dnc_schema_model.Alerts.get(alert_id)

            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__
            
            sap_id = alert_data['sapId']
            sop_id = alert_data['sopId']
            deviceName = alert_data['deviceName'].replace(" ", "")
            loadingPointId = (deviceName.split("@")[0]).split("LP")[1]
            if len(loadingPointId) == 1:
                loadingPointId = "0" + loadingPointId

            interuptName = interuptName.lower()
            if interuptName == "terminateloading":
                messageBody = {"tagsData": {tasSopcommands[sop_id].replace("ID", loadingPointId): 1}}
                await send_tas_rq_message.sendTASRQMessage(sap_id, messageBody)
                print("Recieved input for tripping the loading point %s" % str(sap_id))
                alert_data['isTripped'] = True
                data_object = dnc_schema_model.Alerts(**alert_data)
                await data_object.modify()
            
            elif interuptName == "unterminateloading":
                print("Recieved input for untripping the loading point %s" % str(sap_id))
                messageBody = {"tagsData": {tasSopcommands[sop_id].replace("ID", loadingPointId): 0}}
                await send_tas_rq_message.sendTASRQMessage(sap_id, messageBody)
                alert_data['isTripped'] = False
                data_object = dnc_schema_model.Alerts(**alert_data)
                await data_object.modify()
            else:
                print("Unknown interrupt came")

        except Exception as e:
            print("Exception Occured While Sending Command for alert %s ", alert_id)
            print(e)
            print("Traceback %s" % traceback.format_exc())
        
        return True, {"sendcommand": True}

            

















        