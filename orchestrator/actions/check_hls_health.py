import ThingsBoardApi


class CheckHlsHealth:

    async def get_required_variables(self):
        return ["alertid", "deviceId", "sapId"]
    
    async def checkhlshealth(self, alert_id, device_id, sap_id):

        """
        This function checks the HLS (Health, Life, Safety) status of a device with the given device_id 
        using the ThingsBoard API. It returns True and a dictionary indicating whether a shutdown is 
        triggered based on the HLS status. If an exception occurs during the API call, it catches the error, 
        sets the shutdown trigger to False, and prints the error message.
        """
        
        print("Check HLS Health Alertid:%s DeviceId:%s" % (alert_id, device_id))
        try:
            tb = ThingsBoardApi.TB('tas', sap_id)
            tankhlsstatus = await tb.checkHLSDown(device_id) #thingsboard api connection
        except Exception as e:
            tankhlsstatus = False
            print("Exception in getting Current HLS Status : " + str(e))
        return True, {"triggerShutdown": tankhlsstatus}