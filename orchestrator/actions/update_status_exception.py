import urdhva_base
from api_manager import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class Update_Status_Exception:
    async def get_required_variables(self):
        """
        Returns a list of required variables for the Update_Status_Exception action.

        Returns:
            list: A list containing a single string, "alertid".
        """
        return ["alertid"]

    async def updatestatusexception(self, alert_id):        
        """
        Updates the status of the alert with the given alert_id to "Exception Approved",
        sets the role and rolelist to empty string and list, and sets the finalapproval to True.

        Args:
            alert_id (str): The id of the alert to be updated.

        Returns:
            tuple: A tuple containing a boolean indicating the success of the operation,
            and a dictionary with the updated alert data.
        """
        try:
            alert_data = await hpcl_ceg_model.Alerts.get(alert_id)

            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            alert_data['role'] = ''
            alert_data['rolelist'] = []
            alert_data['status'] = 'Exception Approved'
            alert_data['finalapproval'] = True

            data_object = hpcl_ceg_model.Alerts(**alert_data)
            await data_object.modify()
            return True, None
        
        except Exception as e:
            logger.error(e)
            return False, e