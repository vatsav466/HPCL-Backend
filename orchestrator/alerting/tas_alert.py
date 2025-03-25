import urdhva_base
import json
import httpx
import datetime
import traceback
import hpcl_ceg_model
import utilities.helpers as helpers
import orchestrator.alerting.alert_helper as alert_helper
import cache_gateway.cache_api_actions as cache_api_actions
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
            status, loc_dt = await cache_api_actions.get_location_data(bu=alert_data['bu'], location_id=alert_data['sap_id'])
            #status, loc_dt = await alert_helper.get_location_details(bu=alert_data['bu'], sap_id=alert_data['sap_id'])
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
            device_data = f"{alert_data['device_name']}"
            processed_time = datetime.datetime.now(datetime.timezone.utc)
            alert_data["alert_history"] = [{"processed_time": processed_time.isoformat(),
                                           "allocated_time": processed_time.isoformat(),
                                            "action_msg": f"{alert_data['interlock_name']} Interlock "
                                                          f"created for device {device_data}",
                                            "action_type": "InterlockCreated"}]
            camunda_url = await helpers.get_camunda_url(bu=alert_data['bu'], sap_id=alert_data['sap_id'],
                                                        alert_section="TAS", location_data=loc_dt)
            return await cls.create_alert(alert_data, camunda_url)

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
            alert_data["alert_history"] = {"processed_time": processed_time.isoformat(),
                                           "allocated_time": processed_time.isoformat(),
                                           "action_msg": f"{alert_data['interlock_name']} Interlock "
                                                         f"cleared for device {device_data}",
                                           "action_type": "InterlockCleared"}
            
            query = f"external_id='{alert_data['alert_id']}' and bu='{alert_data['bu']}' and sap_id='{alert_data['sap_id']}' and alert_status='Open'"
            data = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query, limit=1), resp_type='plain')
            alert_id = ''
            if len(data['data']):
                alert_id = data['data'][0]['id']
            else:
                return await cls.close_alert(alert_data)   
            if alert_id:
                tas_alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
                if not isinstance(tas_alert_data, dict):
                    tas_alert_data = tas_alert_data.__dict__
                data = {
                    "messageName": "interLockOk",
                    "businessKey": tas_alert_data['unique_id'],
                    "processVariables": {"alert_id": {"value": alert_id, "type": "String"},
                                  "closed": {"value": True, "type": "Boolean"}}}
                
                url = urdhva_base.settings.camunda_url + "/engine-rest/message"
                url = await helpers.get_camunda_url(bu=alert_data['bu'], sap_id=alert_data['sap_id'],
                                                    alert_section="TAS")
                url += "/engine-rest/message"
                r = httpx.post(url, headers={'Content-Type': 'application/json'}, json=data, verify=False)
                if int(r.status_code / 100) != 2:
                    print(f"Error while sending message to camunda: {r.status_code} - {r.text}")
                else:
                    print("Message sent to camunda")
                    return "Successfully sent message to camunda"
        except Exception as e:
            raise Exception(status_code=500, detail="Error closing alert.") from e
