import urdhva_base
import traceback
from orchestrator.alerting.alert_factory import AlertFactory

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class CloseAlert:
    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the action.
        
        Returns:
            list: A list of strings representing the required variables.
        """
        return ["alert_id", "sap_id", "sop_id", "BU", "close", "interlock_name", "interlock_id"]
    
    async def closealert(self, params):
        """
        Closes an alert with the given parameters.
        
        Parameters:
            params (dict): A dictionary containing the parameters for the alert to be closed.
                - alert_id (str): The unique ID of the alert to be closed.
                - sap_id (str): The SAP ID of the alert to be closed.
                - sop_id (str): The SOP ID of the alert to be closed.
                - BU (str): The Business Unit of the alert to be closed.
                - close (bool): A boolean indicating whether to close the alert.
                - interlock_name (str): The name of the interlock to be used.
                - interlock_id (str): The ID of the interlock to be used.
        
        Returns:
            dict: A dictionary containing the status and message of the action.
                - status (str): Either "success" or "error".
                - message (str): A message indicating the result of the action.
        """
        try:
            print("params --> ", params)
            close = params.get("close")
            if not close:
                return {"status": "error", "message": "Invalid close request"}
            return await AlertFactory().close_alert(params)
        
        except Exception as e:
            print(traceback.format_exc())
            logger.error(e)
            return {"status": "error", "message": str(e)}
