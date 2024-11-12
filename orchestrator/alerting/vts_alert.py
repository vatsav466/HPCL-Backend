import json
import urdhva_base
from api_manager import hpcl_ceg_model
import utilities.bu_key_mapping as bu_key_mapping
import orchestrator.alerting.alert_factory as alert_factory

logger = urdhva_base.logger.Logger.getInstance('vts_alert_processing')


class VTSAlertManager(alert_factory.AlertFactory):
    @classmethod
    async def _fetch_location_data(cls, alert_data):
        """
        Fetches location data based on the provided alert data, either from Redis cache
        or from the database if not present in Redis.

        Parameters:
        alert_data (dict): A dictionary containing alert information with keys:
            - 'BU' (str): Business unit type.
            - 'sapid' (str): SAP ID for the location.

        Returns:
        dict: A dictionary containing location details with keys:
            - 'state' (str): State of the location.
            - 'region' (str): Region of the location.
            - 'district' (str): District of the location.
            - 'city' (str): City of the location.

        Raises:
        Exception: If location data is not found in both Redis and the database, or if
        there is an error in fetching the data.
        """
        try:
            bu_location_type = alert_data['bu']
            sap_id = alert_data['sap_id']
            loc_dt = {}

            redis_key = f"{bu_location_type.upper()}_{sap_id}"
            try:
                # Get the Redis client
                redis_client = await urdhva_base.redispool.get_redis_connection()
                # Check if location data exists in Redis
                redis_data = await redis_client.hget(f"{bu_location_type.lower()}_master", redis_key)
                if redis_data:
                    location_alert_data = json.loads(redis_data)
                    loc_dt = {
                        "state": location_alert_data.get('state', ''),
                        "region": location_alert_data.get('region', ''),
                        "district": location_alert_data.get('district', ''),
                        "city": location_alert_data.get('city', ''),
                    }
                else:
                    # Fallback to database query if not in Redis
                    query = f"bu='%{bu_location_type.upper()}%' AND sap_id='%{sap_id}%'"
                    params = urdhva_base.queryparams.QueryParams()
                    params.limit = 100
                    params.fields = None
                    params.q = query
                    params.sort = json.dumps({"updated": -1})
                    
                    # Fetch from database
                    localert_data = await hpcl_ceg_model.LocationMaster.get_all(params)
                    if localert_data:
                        location = localert_data[0]
                        loc_dt = {
                            "state": location.state,
                            "region": location.region,
                            "district": location.district,
                            "city": location.city,
                        }
                    else:
                        raise Exception(status_code=404, detail="Location data not found in Redis or database.")
                
            except Exception as e:
                raise Exception(status_code=500, detail="Error fetching location data.") from e

            return loc_dt

        except Exception as e:
            logger.error(e)
            raise e

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
            # alert_alert_data = await hpcl_ceg_model.Alerts.get_all()
            bu_location_type = alert_data['bu']
            sap_id = alert_data['sap_id']
            sop_id = alert_data['sop_id']
            static_alert_data = alert_data.get('staticalert_data', {}) 
            ''' 
            staticalert_data': {'alertHistory': [alerthistorymessage],
            'VehicleNumber': doc['TL_Number'],
            'vendor': doc['Vendor_Code'],
            "VendorName": doc['Vendor_Name'],
            "vendormail": vendormail} 
            '''
            deviceid = alert_data['deviceId']
            interlockname = alert_data['name']
            
            # Retrieve necessary fields from the alert_data
            loc_dt = cls._fetch_location_data(alert_data)
            alert_data['location_data'] = loc_dt
        
            return cls.create_alert(alert_data)

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
            
            # Retrieve necessary fields from the alert_data
            bu_location_type = alert_data['bu']
            sap_id = alert_data['sap_id']
            sop_id = alert_data['sop_id']
            alert_id = alert_data['alert_id']

            # Query Redis or the alert database to locate the alert
            
            query = f"sop_id='%{sop_id}%' AND sap_id='%{sap_id}%' AND alert_id='%{alert_id}%'"
            params = urdhva_base.queryparams.QueryParams()
            params.q = query
            existing_alerts = await hpcl_ceg_model.Alerts.get_all(params)
            
            if existing_alerts:
                alert = existing_alerts[0]
                alert['alert_status'] = 'closed'
                # alert.closed = True
                # alert.close_reason = close_reason
                data_obj = hpcl_ceg_model.Alerts(**alert)
                await data_obj.modify()
                logger.info(f"Alert {alert_id} closed successfully in database.")
            else:
                raise Exception(status_code=404, detail="Alert not found in both Redis and alert database.")

                return {"status": True, "message": "Alert closed successfully", "alert_data": alert}
            
        except Exception as e:
            raise Exception(status_code=500, detail="Error closing alert.") from e

