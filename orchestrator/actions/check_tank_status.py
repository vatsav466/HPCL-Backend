import urdhva_base
from api_manager import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class CheckTankStatus:
    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the CheckRoTime action.
        
        Returns:
            list: A list containing a single string, "alert_id".
        """
        return ["alert_id", "deviceId", "sapId"]

    async def checkTankStatus(self, params):
        try:
            alertid = params.get("alertid")
            print("CHECK TANK STATUS ALERTID:%s" % alertid)
            deviceid = params.get('deviceId')
            sapId = params.get('sapId')
            # tb = ThingsBoardApi.TB('tas', sapId)
            # tankhstatus, pumpStatus = tb.checkTankHLevel(deviceid)
        except:
            tankhstatus, pumpStatus = True, True
        return True, {"shutdownReady": True, "shutdownPump": True}