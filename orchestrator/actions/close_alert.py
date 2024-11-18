import urdhva_base
from api_manager import hpcl_ceg_model
from orchestrator.alerting.alert_factory import AlertFactory

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")

class CloseAlert:
    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the action.
        
        Returns:
            list: A list of strings representing the required variables.
        """
        return ["alert_id", "sap_id", "sop_id", "BU", "close"]
    
    async def closealert(self, params):
        print("params --> ", params)
        close = params.get("close")
        if not close:
            return {"status": "error", "message": "Invalid close request"}
        return await AlertFactory().close_alert(params)
        
