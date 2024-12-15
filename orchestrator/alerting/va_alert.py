import urdhva_base
import re
import json
import datetime
import traceback
import utilities.interlock_mapping
import utilities.va_mapping as va_mapping
import orchestrator.alerting.alert_helper as alert_helper
import orchestrator.alerting.alert_factory as alert_factory

logger = urdhva_base.logger.Logger.getInstance("va_alert_processing")


class VAAlertManager(alert_factory.AlertFactory):
    @classmethod
    async def create_bu_alert(cls, alert_data):
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

        Returns:
            dict: A dictionary containing the status, message and the created alert document
        """
        try:
            logger.info(f"alert_data received to create alert {alert_data}")
            '''# alert_alert_data = await hpcl_ceg_model.Alerts.get_all()
            bu_location_type = alert_data['bu']
            sap_id = alert_data['sap_id']
            sop_id = alert_data['sop_id']
            static_alert_data = alert_data.get('staticalert_data', {}) 
        
            staticalert_data': {'alertHistory': [alerthistorymessage],
            'VehicleNumber': doc['TL_Number'],
            'vendor': doc['Vendor_Code'],
            "VendorName": doc['Vendor_Name'],
            "vendormail": vendormail} 
        
            deviceid = alert_data['deviceId']
            interlockname = alert_data['name']'''

            #getting location_id in this form from payload example "location_id": "ACC, Bandra, 11073010, 11073010",
            location_id = alert_data['location_id'].split(",")[-1].strip()
            # match = re.findall(r'\b\d{5,}\b', location_id)
            # location_id = match[-1]
            
            # Retrieve necessary fields from the alert_data
            status, loc_dt = await alert_helper.get_location_details(bu=alert_data['location_type'].value, sap_id=location_id)
            if not status:
                return

            recv_time = datetime.datetime.now(tz=datetime.timezone.utc)
            for record in alert_data['data']:
                try:
                    rediskey = f"{alert_data['location_type'].value}{location_id}{record['device_id'].lower()}"
                    redis_ins = await urdhva_base.redispool.get_redis_connection()
                    if await redis_ins.exists(rediskey):
                           return 
                    # Afredis_ins.setexert
                    await redis_ins.setex(rediskey, 4*60*60, record['device_id'])

                    exception_msg = (f"alert_type - {record['alert_type']},"
                                         f"alert_description - {record['alert_description']},"
                                         f"device_id - {record['device_id']},"
                                         f"video_url - {record['video_url']},"
                                         f"Exception Date - {recv_time}")
                    
                    print("Exception Message",exception_msg)
                    interlock_name = " ".join(re.split(r'[_-]', record['alert_type'])).title() + " " + alert_data['location_type'].value
                    interlock_details = utilities.interlock_mapping.get_interlock_name(
                        alert_data['location_type'].value, interlock_name)
                    
                    if not interlock_details:
                        print("Interlock Details Not Found for this alert_type")
                        return

                    interlock_details.update({"bu": alert_data['location_type'].value,
                                              "location_name": loc_dt['name'],
                                              "sap_id": location_id,
                                              "alert_history": [exception_msg],
                                              "device_id": record['device_id'],
                                              "device_name": record['device_id'],
                                              "message": record['video_url'],
                                              "alert_section": "VA"
                                              })
                    
                    await cls.create_alert(interlock_details)
                except Exception as e:
                    print(traceback.format_exc())
                    logger.error(f"Exception in processing alert data {e}, Traceback "
                                 f"{traceback.format_exc()}, data {alert_data}")

        except Exception as e:
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
            return await cls.close_alert(alert_data)
            
        except Exception as e:
            raise Exception(status_code=500, detail="Error closing alert.") from e
