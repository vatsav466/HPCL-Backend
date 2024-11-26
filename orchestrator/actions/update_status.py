import urdhva_base
import traceback
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class UpdateStatus:
    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the action.
        
        Returns:
            list: A list of strings representing the required variables.
        """
        return ["alert_id"]
    
    async def updatestatus(self, params): 
        """
        Updates the status of the alert with the given alert_id to "Under Maintenance",
        clears the role and rolelist, and sets final approval to True in the database.

        Args:
            alert_id (str): The id of the alert to be updated.

        Returns:
            tuple: A tuple containing a boolean indicating the success of the operation,
            and None.
        """
        try:
            alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))

            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            alert_data['role'] = ''
            alert_data['rolelist'] = []
            alert_data['status'] = 'Under Maintenance'
            alert_data['finalapproval'] = True

            data_object = hpcl_ceg_model.Alerts(**alert_data)
            await data_object.modify()
            return True, None
        
        except Exception as e:
            print(traceback.format_exc())
            logger.error(e)
            return False, e