from api_manager import dnc_schema_model

class CheckDealerCounter:

    async def get_required_variables(self):
        return ["alertid"]
    
    async def checkdealercounter(self, alert_id):
        
        """
        This function checks if a dealer counter has been submitted for a given alert ID. 
        It retrieves the alert data,extracts the "Dealercount" value, and returns True along with a dictionary 
        indicating whether the dealer counter has been submitted (atrStatus) if the count is 1.
        """

        alert_data = await dnc_schema_model.Alerts.get(alert_id)
        
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        atrSubmitted = False
        dealercount = alert_data.get("Dealercount", 0)
        if dealercount == 1:
            atrSubmitted = True
        return True, {"atrStatus": atrSubmitted}