from api_manager import dnc_schema_model
import datetime
import asyncio

class CheckRoTime:

    async def get_required_variables(self):
        return ["alertid"]
    
    async def checkrotime(self, alert_id):

        """
        This function calculates the remaining wait time for an alert with the given alert_id. 
        It retrieves the alert's creation time and the number of days it should wait, then calculates the 
        time difference between the current time and the creation time. If the time difference is less than 
        the specified number of days, it calculates the remaining wait time and returns it in the format 
        'PTXMX', where X is the number of minutes.
        
        Note that there seems to be a redundant condition if days>=1 which will always be true if days==0 is 
        handled earlier in the code.
        """
        
        alert_data = await dnc_schema_model.Alerts.get(alert_id)

        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        createdTime = alert_data['created']
        days = int(alert_data.get('days', 0))
        if days==0:
            days = 10
        currentTime = int(datetime.datetime.now().timestamp())
        timeDiff = int((currentTime - createdTime) / 60)
        waitTime = 1
        if timeDiff < (days * 24 * 60):
            waitTime = (days * 24 * 60) - timeDiff
        totalWaitTime = 'PT' + str(waitTime) + 'M'
        if days>=1:
            waitTime = (days * 24 * 60)
            totalWaitTime = 'PT' + str(waitTime) + 'M'
        return True, {"waitTime": totalWaitTime}