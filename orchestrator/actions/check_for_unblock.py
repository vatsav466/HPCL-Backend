import datetime
import urdhva_base
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class CheckForUnblock:
    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the action.
        
        Returns:
            list: A list of strings representing the required variables.
        """
        return ["alert_id", "days"]
    
    async def checkForVehicleUnblock(self, alert_id, days):
        """
        This function checks if the given alert is ready to be unblocked. 
        It retrieves the alert's creation time and the number of days it should wait, 
        then calculates the time difference between the current time and the creation time. 
        If the time difference is less than the specified number of days, it calculates 
        the remaining wait time and returns it in the format 'PTXMX', where X is the 
        number of minutes. Otherwise, it returns a wait time of 1 minute.
        
        Args:
            alert_id (str): The ID of the alert to check.
            days (str): The number of days the alert should wait before being unblocked.
        
        Returns:
            tuple: A tuple containing a boolean indicating success, and a dictionary with the key 
            "waitTime" set to the value of the calculated wait time.
        """
        try:
            days = int(days)

            alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            createdTime = alert_data['created']
            currentTime = int(datetime.datetime.now().timestamp())
            timeDiff = int((currentTime - createdTime) / 60)
            waitTime = 1
            if timeDiff < (days * 24 * 60):
                waitTime = (days * 24 * 60) - timeDiff
            totalWaitTime = 'PT' + str(waitTime) + 'M'
            return True, {"waitTime": totalWaitTime}

        except Exception as e:
            logger.error(e)
            return False