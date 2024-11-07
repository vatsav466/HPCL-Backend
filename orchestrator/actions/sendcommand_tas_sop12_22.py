import config
import traceback
import urdhva_base
from constants import *
import send_tas_rq_message
from api_manager import hpcl_cng_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class SendcommandTasSop1222:
    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the SendcommandTasSop1222 action.
        
        This asynchronous function specifies the variables needed to perform the action, 
        which in this case, are the alertid and interrupt variables.
        
        Returns:
            list: A list containing two strings, "alertid" and "interrupt".
        """
        return ["alertid", "interrupt"]
    
    async def sendcommand_tas(self, alert_id, interuptName):
        """
        Sends a command to the TAS (Terminal Automation System) based on the alert ID and interrupt name.

        This asynchronous function retrieves alert data using the given alert_id, extracts relevant information
        such as sap_id, sop_id, and loadingPointId, and sends a command to the TAS depending on the interrupt name.
        If the interrupt name is "terminateloading", it sends a command to trip the loading point. If the interrupt
        name is "unterminateloading", it sends a command to untrip the loading point. The function modifies the 
        alert data to reflect the state change and logs the appropriate actions.

        Args:
            alert_id (str): The ID of the alert to process.
            interuptName (str): The name of the interrupt action to perform.

        Returns:
            tuple: A tuple containing a boolean indicating success, and a dictionary with the key "sendcommand" 
            set to True if the command was sent successfully, or False if an exception occurred.
        """
        try:
            logger.info('SENDING COMMAND TO TAS FOR AlertId:%s' % alert_id)
            alert_data = await hpcl_cng_model.Alerts.get(alert_id)

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
                data_object = hpcl_cng_model.Alerts(**alert_data)
                await data_object.modify()
            
            elif interuptName == "unterminateloading":
                print("Recieved input for untripping the loading point %s" % str(sap_id))
                messageBody = {"tagsData": {tasSopcommands[sop_id].replace("ID", loadingPointId): 0}}
                await send_tas_rq_message.sendTASRQMessage(sap_id, messageBody)
                alert_data['isTripped'] = False
                data_object = hpcl_cng_model.Alerts(**alert_data)
                await data_object.modify()
            else:
                print("Unknown interrupt came")

            return True, {"sendcommand": True}

        except Exception as e:
            print("Traceback %s" % traceback.format_exc())
            logger.error("Exception Occured While Sending Command for alert %s ", alert_id)
            return False, {"sendcommand": False}
        

            

















        