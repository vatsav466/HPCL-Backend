from api_manager import dnc_schema_model


class EmptyRole:

    async def get_required_variables(self):
        return ["alertid", "maintenance"]
    
    async def emptyrole(self, alert_id, maintenance):

        """
        This function empties the 'role' and 'rolelist' of an alert with the given alert_id, 
        and sets the status to "Under Maintenance" if maintenance is True. It then updates the 
        alert in the database.
        """
        
        alert_data = await dnc_schema_model.Alerts.get(alert_id)
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        alert_data['role'] = ''
        alert_data['rolelist'] = []

        if maintenance:
            alert_data['status'] = "Under Maintenance"

        data_object = dnc_schema_model.Alerts(**alert_data)
        await data_object.modify()
        return True, None