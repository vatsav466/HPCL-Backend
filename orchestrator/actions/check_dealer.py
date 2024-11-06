from api_manager import dnc_schema_model

class CheckDealer:

    async def get_required_variables(self):
        return ["alertid"]
    
    async def checkdealer(self, alert_id):
        
        """
        It retrieves the alert data associated with the alert_id using dnc_schema_model.Alerts.get(alert_id), 
        and then checks if the 'Dealer' field in the alert data is True. If it is, the function sets atrSubmitted 
        to True and returns a tuple containing True and a dictionary with the key "atrStatus" set to the value of 
        atrSubmitted
        """
        
        print("checkdealer in k-factor Status AlertId:%s" % alert_id)
        alert_data = await dnc_schema_model.Alerts.get(alert_id)

        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        atrSubmitted = False
        if alert_data['Dealer']== True:
            atrSubmitted = True
        return True, {"atrStatus": atrSubmitted}