from api_manager import dnc_schema_model


class CheckExcepStatus:

    async def get_required_variables(self):
        return ["alertid"]

    async def checkExcepstatus(self, alert_id):
        
        """
        Checks the alert history for "Exception" to determine if the exception has been taken or not.

        Retrieves the alert data using the given alert_id and checks the alert's history
        for any items containing the string "Exception". If found, sets exceptaken to True.

        Returns a tuple containing True and a dictionary with the key "excepStatus" 
        set to the value of exceptaken.
        """
        
        exceptaken = False
        try:
            print("Check Exception request raised AlertId:%s" % alert_id)
            alert_data = await dnc_schema_model.Alerts.get(alert_id)

            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            alerthistory = alert_data.get('alertHistory', [])
            for item in alerthistory:
                if "Exception" in item:
                    exceptaken = True
                    break
        except Exception as e:
            print(e)
        return True, {"excepStatus": exceptaken}