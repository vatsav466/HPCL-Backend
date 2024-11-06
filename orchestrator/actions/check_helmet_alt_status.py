from api_manager import dnc_schema_model


class CheckHelmetAltStatus:

    async def get_required_variables(self):
        return ["alertid"]
    
    async def checkHelmetAltStatus(self, alert_id):

        """
        This function checks the status of an alert with the given alert_id. It retrieves the alert data, 
        examines its history for specific keywords ("ATR", "Justified by", and "http"), and returns a 
        boolean indicating whether the alert should be closed (closeAlert).
        """
        
        print("CHECK HELMET ATR ALERTID:%s" % alert_id)
        alert_data = await dnc_schema_model.Alerts.get(alert_id)

        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        alerthistory = alert_data.get('alertHistory', [])
        startCounter = False
        closeAlt = True
        for item in alerthistory:
            if "ATR" in item or "Justified by" in item:
                startCounter = True
                closeAlt = True
            if startCounter and "http" in item:
                closeAlt = False
        return True, {"closeAlert": closeAlt}