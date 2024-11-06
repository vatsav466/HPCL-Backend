from api_manager import dnc_schema_model

class Update_Status_Exception:

    async def get_required_variables(self):
        return ["alertid"]
    async def updatestatusexception(self, alert_id):

        """
        This code snippet defines an asynchronous function called updatestatusexception that updates 
        the status of an alert in a database. It retrieves the alert data using the dnc_schema_model.Alerts.get 
        method with the provided alert_id. If the alert_data is not a dictionary, it converts it to a dictionary 
        using __dict__. Then, it updates the role, rolelist, status, and finalapproval fields of the alert_data 
        dictionary. It creates a new dnc_schema_model.Alerts object using the modified alert_data and calls the 
        modify method to update the alert in the database. Finally, it returns a tuple containing True and None.
        """
        
        alert_data = await dnc_schema_model.Alerts.get(alert_id)

        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        alert_data['role'] = ''
        alert_data['rolelist'] = []
        alert_data['status'] = 'Exception Approved'
        alert_data['finalapproval'] = True

        data_object = dnc_schema_model.Alerts(**alert_data)
        await data_object.modify()

        return True, None