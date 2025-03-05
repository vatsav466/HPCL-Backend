import urdhva_base
import datetime
import traceback
import hpcl_ceg_model
import utilities.role_configuration as role_configuration

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class CheckForUnblock:
    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the action.
        
        Returns:
            list: A list of strings representing the required variables.
        """
        return ["alert_id","va_level","escalate_time_block"]
    
    async def checkForVehicleUnblock(self, params):
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
            alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            if alert_data.get("alert_section","") in ["VTS"]:
                escalation_time = params.get("escalate_time_block","")
                totalWaitTime = role_configuration.role_Mapping[alert_data["alert_section"]][alert_data.get("bu","")][alert_data["interlock_name"]]["block_time"][escalation_time]
            print("totalWaittime---------->",totalWaitTime)
            return True, {"waitTime": totalWaitTime}

        except Exception as e:
            print(traceback.format_exc())
            logger.error(e)
            return False