from api_manager import dnc_schema_model


class UpdateStatus:

    async def get_required_variables(self):
        return ["alertid"]
    
    async def updatestatus(self, alert_id):

        """
        This asynchronous function updates an alert's status to "Under Maintenance" in a database, 
        clearing its role and rolelist, and setting final approval to True.
        """
        
        alert_data = await dnc_schema_model.Alerts.get(alert_id)

        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        alert_data['role'] = ''
        alert_data['rolelist'] = []
        alert_data['status'] = 'Under Maintenance'
        alert_data['finalapproval'] = True

        data_object = dnc_schema_model.Alerts(**alert_data)
        await data_object.modify()
        
        return True, None