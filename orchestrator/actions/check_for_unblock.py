import datetime
from api_manager import dnc_schema_model


class CheckForUnblock:

    async def get_required_variables(self):
        return ["alertid", "days"]
    
    async def checkForVehicleUnblock(self, alert_id, days):

        """
        This function checks if a vehicle is unblocked for a given alert. It calculates the time difference 
        between the current time and the alert's creation time, and if it's less than the specified number of days, 
        it returns the remaining wait time in the format 'PTXMX', where X is the number of minutes. Otherwise, 
        it returns a wait time of 1 minute.
        """
        
        # print("checkForVehicleUnblock", alert_id)
        days = int(days)
        # print("days", days)

        alert_data = await dnc_schema_model.Alerts.get(alert_id)
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        createdTime = alert_data['created']
        currentTime = int(datetime.datetime.now().timestamp())
        timeDiff = int((currentTime - createdTime) / 60)
        waitTime = 1
        if timeDiff < (days * 24 * 60):
            waitTime = (days * 24 * 60) - timeDiff
        totalWaitTime = 'PT' + str(waitTime) + 'M'
        #print("totalWaitTime", totalWaitTime)
        return True, {"waitTime": totalWaitTime}
