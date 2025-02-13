import asyncio
import datetime
import urdhva_base
import traceback
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class CheckMaintenanceTime:
    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the action.
        
        Returns:
            list: A list of strings representing the required variables.
        """
        return ["alert_id", "days"]
    
    async def checkMaintenancetime(self, params):
        """
        This function checks if the given alert is ready to be unblocked. 
        It retrieves the alert's creation time and the number of days it should wait, 
        then calculates the time difference between the current time and the creation time. 
        If the time difference is less than the specified number of days, it calculates 
        the remaining wait time and returns it in the format 'PTXMX', where X is the 
        number of minutes. Otherwise, it returns a wait time of 1 minute.
        
        Args:
            alert_id (str): The ID of the alert to check.
        
        Returns:
            tuple: A tuple containing a boolean indicating success, and a dictionary with the key 
            "waitTime" set to the value of the calculated wait time.
        """
        try:
            alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))

            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            print("alert_data --> ", alert_data)
            if alert_data.get("alert_section") in ["VTS"]:
                createdTime = alert_data['created_at']
                days = int(alert_data.get('days', 0))
                currentTime = int(datetime.datetime.now().timestamp())
                # Convert createdTime to timestamp if it's a datetime object
                if isinstance(createdTime, datetime.datetime):
                    createdTime = int(createdTime.timestamp())
                timeDiff = int((currentTime - createdTime) / 60)
                waitTime = 1
                if timeDiff < (days * 24 * 60):
                    waitTime = (days * 24 * 60) - timeDiff
                totalWaitTime = 'PT' + str(waitTime) + 'M'
                return True, {"waitTime": totalWaitTime}
            elif alert_data.get("alert_section") in ["TAS"] and alert_data.get('maintenance_time',''):
                maintenance_time = alert_data.get('maintenance_time')
                timestamp = datetime.datetime.fromisoformat(maintenance_time).replace(tzinfo=datetime.timezone.utc)
                current_time = datetime.datetime.now(datetime.timezone.utc)   
                if current_time>timestamp:
                    # Parse the string into a datetime object
                    timestamp = datetime.datetime.strptime(maintenance_time, "%Y-%m-%dT%H:%M:%S")
                    # Subtract 5 days
                    new_timestamp = timestamp - datetime.timedelta(days=5)
                    # Convert back to string in the same format
                    totalWaitTime = new_timestamp.strftime("%Y-%m-%dT%H:%M:%S")
                    #totalWaitTime = '2025-02-04T19:56:20'
                    return True, {"waitTime": totalWaitTime}
                else:
                    # Return current time + 60 seconds
                    current_time_plus_30s = (datetime.datetime.now() + datetime.timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%S")
                    return True, {"waitTime": current_time_plus_30s}
            else:
                totalWaitTime = 'PT1S'
                return True, {"waitTime": totalWaitTime}
            
        except Exception as e:
            print(traceback.format_exc())
            logger.error(e)
            return False
