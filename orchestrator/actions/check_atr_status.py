from api_manager import dnc_schema_model


class CheckAtrStatus:

    async def get_required_variables(self):
        return ["alertid"]
    
    async def checkATRStatus(self, alert_id):

        """
        This is an asynchronous function checkATRStatus that checks if an Alert To Resume (ATR) has been submitted 
        for a given alert_id. It retrieves the alert data, checks the alert history for keywords "ATR" or 
        "Justified by", and returns a tuple with a boolean indicating whether an ATR has been submitted.
        """
        
        print("Check ATR Status AlertId:%s" % alert_id)
        alert_data = await dnc_schema_model.Alerts.get(alert_id)

        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        atrSubmitted = False

        alerthistory = alert_data.get('alertHistory', [])
        for item in alerthistory:
            if "ATR" in item or "Justified by" in item:
                atrSubmitted = True
                break
        return True, {"atrStatus": atrSubmitted}