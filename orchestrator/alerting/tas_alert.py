import urdhva_base
import json
import datetime
import traceback
import orchestrator.alerting.alert_helper as alert_helper
import orchestrator.alerting.alert_factory as alert_factory

logger = urdhva_base.logger.Logger.getInstance("tas_alert_processing")


class TASAlertManager(alert_factory.AlertFactory):
    @classmethod
    async def create_bu_alert(cls, alert_data, camunda_url=urdhva_base.settings.camunda_url):
        """
        Create a business unit level alert

        Parameters:
            alert_data (dict): A dictionary containing the data to create the alert
                - bu (str): Business unit
                - sap_id (str): SAP ID
                - sop_id (str): SOP ID
                - staticalert_data (dict): Additional static data to be stored in the alert document
                - deviceId (str): Device ID
                - interlockName (str): Interlock name
                - severity (str): Severity of the alert
                - message (str): Alert message
                - alertHistory (list): List of alert history messages
            camunda_url:

        Returns:
            dict: A dictionary containing the status, message and the created alert document
        """
        try:
            logger.info(f"alert_data received to create alert {alert_data}")
            # Retrieve necessary fields from the alert_data
            status, loc_dt = await alert_helper.get_location_details(bu=alert_data['bu'], sap_id=alert_data['sap_id'])
            if status:
                alert_data['location_data'] = loc_dt
            else:
                logger.info(f"Error getting location details {loc_dt} for {alert_data['bu']} / {alert_data['sap_id']}, "
                            f"Skipping alert creation")
                return {"status": False, "message": f"Location details not found for {alert_data['sap_id']}",
                        "alert_data": None}
            with open(f"/opt/ceg/algo/things_board/device_data/{alert_data['sap_id']}.json") as f:
                device_data = json.load(f)
            device_keys = []
            for rec in device_data["data"]:
                if rec['device_name'] == alert_data['device_name']:
                    for sensor in rec['sensors']:
                        if sensor['sensor_name'] in alert_data:
                            device_keys.append(f"{sensor['sensor_name']}: {alert_data[sensor['sensor_name']]}")
                    break
            device_data = f"{alert_data['device_name']}({", ".join(device_keys)})"
            processed_time = datetime.datetime.now(datetime.timezone.utc)
            alert_data["alert_history"] = [{"processed_time": processed_time.isoformat(),
                                           "allocated_time": processed_time.isoformat(),
                                            "action_msg": f"{alert_data['interlock_name']} Interlock "
                                                          f"created for device {device_data}",
                                            "action_type": "InterlockCreated"}]
            return await cls.create_alert(alert_data)

        except Exception as e:
            print(traceback.format_exc())
            logger.error(e)
            return {"status": False, "message": str(e), "alert_data": None}

    @classmethod
    async def close_bu_alert(cls, alert_data):
        """
        Close a BU level alert asynchronously.

        Parameters:
            alert_data (dict): A dictionary containing the data to close the alert
                - bu (str): Business unit
                - sap_id (str): SAP ID
                - sop_id (str): SOP ID
                - alert_id (str): Unique alert ID

        Returns:
            dict: A dictionary containing the status, message, and the closed alert document.

        Raises:
            Exception: If the alert is not found or there's an error in closing the alert.
        """
        try:
            logger.info(f"Alert data received to close alert: {alert_data}")
            with open(f"/opt/ceg/algo/things_board/device_data/{alert_data['sap_id']}.json") as f:
                device_data = json.load(f)
            device_keys = []
            for rec in device_data["data"]:
                if rec['device_name'] == alert_data['device_name']:
                    for sensor in rec['sensors']:
                        if sensor['sensor_name'] in alert_data:
                            device_keys.append(f"{sensor['sensor_name']}: {alert_data[sensor['sensor_name']]}")
                    break
            device_data = f"{alert_data['device_name']}({", ".join(device_keys)})"
            processed_time = datetime.datetime.now(datetime.timezone.utc)
            alert_data["alert_history"] = [{"processed_time": processed_time.isoformat(),
                                            "allocated_time": processed_time.isoformat(),
                                            "action_msg": f"{alert_data['interlock_name']} Interlock "
                                                          f"cleared for device {device_data}",
                                            "action_type": "InterlockCleared"}]
            return await cls.close_alert(alert_data)
            
        except Exception as e:
            raise Exception(status_code=500, detail="Error closing alert.") from e
