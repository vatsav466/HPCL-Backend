import urdhva_base
from api_manager import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class CheckAtrStatus:
    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the action.
        
        Returns:
            list: A list of strings representing the required variables.
        """
        return ["alert_id"]
    
    async def checkATRStatus(self, alert_id):
        """
        Checks if an ATR has been submitted for a given alert ID.

        Retrieves the alert data associated with the alert_id using hpcl_ceg_model.Alerts.get(alert_id), 
        and then checks if the alert history contains the string "ATR" or "Justified by". 
        If it does, the function sets atrSubmitted to True and returns a tuple containing True and a 
        dictionary with the key "atrStatus" set to the value of atrSubmitted.

        Args:
            alert_id (str): The ID of the alert to check.

        Returns:
            tuple: A tuple containing a boolean indicating success, and a dictionary with the key "atrStatus" 
            set to the value of atrSubmitted.
        """
        try:
            logger.info("Check ATR Status alert_id:%s" % alert_id)
            alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__
            atrSubmitted = False
            alerthistory = alert_data.get('alertHistory', [])
            for item in alerthistory:
                if "ATR" in item or "Justified by" in item:
                    atrSubmitted = True
                    break
            return True, {"atrStatus": atrSubmitted}
        
        except Exception as e:
            logger.error(e)
            return False, {"atrStatus": "False"}