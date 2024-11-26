import urdhva_base
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")

class UpdateDealerStatus:
    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the action.
        
        Returns:
            list: A list containing a single string, "alert_id".
        """
        return ["alert_id"]
    
    async def updatedealerstatus(self, alert_id): 
        """
        Updates the dealer and SO status for a given alert to False.

        This asynchronous function retrieves alert data using the provided alert_id.
        It ensures the data is in dictionary format, sets the 'Dealer' and 'SO' fields
        to False, and updates the alert in the database.

        Args:
            alert_id: The ID of the alert to update.

        Returns:
            A tuple where the first element is a boolean indicating the success of
            the operation, and the second element is None on success or an error
            message on failure.
        """
        try:
            alert_data = await hpcl_ceg_model.Alerts.get(alert_id)

            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            alert_data['Dealer'] = False
            alert_data['SO'] = False
            data_object = hpcl_ceg_model.Alerts(**alert_data)
            await data_object.modify()
            return True, None
        
        except Exception as e:
            logger.error(e)
            return False, e