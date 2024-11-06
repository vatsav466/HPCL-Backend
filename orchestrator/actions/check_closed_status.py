from api_manager import dnc_schema_model


class CheckClosedStatus:

    async def get_required_variables(self):        
        return ["alertid"]
    
    async def checkClosedstatus(self, alert_id):

        """
        This function checks if an alert with the given alert_id has been closed by searching for the string "CLOSED" 
        in its history. It returns a tuple containing True and a dictionary with the key "closedStatus" set to True 
        if the alert is closed, and False otherwise.
        """
        closeSubmitted = False
        try:
            alert_data = await dnc_schema_model.Alerts.get(alert_id)
            
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            alerthistory = alert_data.get('alertHistory', [])
            for item in alerthistory:
                if "CLOSED" in item:
                    closeSubmitted = True
                    break
        except Exception as e:
            print(e)
        return True, {"closedStatus": closeSubmitted}