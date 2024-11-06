from api_manager import dnc_schema_model


class UpdateDealerStatus:

    async def get_required_variables(self):
        return ["alertid"]
    
    async def updatedealerstatus(self, alert_id):

        """
        This code snippet defines an asynchronous function called updatedealerstatus that updates 
        the status of an alert. It retrieves the alert data using the dnc_schema_model.Alerts.get 
        method and sets the 'Dealer' and 'SO' fields to False. It then creates a new Alerts object 
        using the modified alert data and calls the modify method to update the alert in the database. 
        Finally, it returns a tuple containing True and None.
        """
        
        alert_data = await dnc_schema_model.Alerts.get(alert_id)

        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        alert_data['Dealer'] = False
        alert_data['SO'] = False
        data_object = dnc_schema_model.Alerts(**alert_data)
        await data_object.modify()
        return True, None