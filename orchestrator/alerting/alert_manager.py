import urdhva_base
import json
import datetime
from api_manager import hpcl_cng_model, hpcl_cng_enum

logger = urdhva_base.logger.Logger.getInstance("Alerts_Processing")


class AlertManager:

    @staticmethod
    async def create_alert(self, data): 
        try:
            """
            Create an alert based on the given data
            
            Parameters:
                self (AlertManager): The instance of the class
                data (dict): The data to create the alert, it should contain the following keys:
                    - bu (str): Business unit
                    - sapid (str): SAP ID
                    - sopid (str): SOP ID
                    - staticData (dict): Additional static data to be stored in the alert document
                    - deviceId (str): Device ID
                    - name (str): Interlock name
                    - deviceType (str): Device type
                    - deviceName (str): Device name
                    - priority (str): Priority of the alert
                    - message (str): Alert message
                    - alertHistory (list): List of alert history messages
            
            Returns:
                dict: A dictionary containing the status, message and the created alert document
            """
            logger.info(f"Data received to create alert {data}")
            # alert_data = await hpcl_cng_model.Alerts.get_all()
            bu_location_type = data['bu']
            sapid = data['sapid']
            sopid = data['sopid']
            static_data = data.get('staticData', {}) 
            ''' 
            staticData': {'alertHistory': [alerthistorymessage],
            'VehicleNumber': doc['TL_Number'],
            'vendor': doc['Vendor_Code'],
            "VendorName": doc['Vendor_Name'],
            "vendormail": vendormail} 
            '''
            deviceid = data['deviceId']
            interlockname = data['name']
            
            location = {}
            loc_dt = {}
            # query to get the location data from locaiton table
            if bu_location_type.upper() in [bu.value for bu in hpcl_cng_enum.BusinessUnit] and sopid not in data['sopid']:
                redis_key = f"{bu_location_type.upper()}_{sapid}"
                try:
                    # Get the Redis client
                    redis_client = await urdhva_base.redispool.get_redis_connection()
                    # Check if location data exists in Redis using HGET
                    redis_data = await redis_client.hget(f"{bu_location_type.lower()}_master", redis_key)
                    if redis_data:
                        # If data is found in Redis, parse the JSON
                        location_data = json.loads(redis_data)
                        loc_dt = {
                            "state": location_data.get('state', ''),
                            "region": location_data.get('region', ''),
                            "district": location_data.get('district', ''),
                            "city": location_data.get('city', ''),
                        }
                    else:
                        # If data is not in Redis, fall back to database query
                        query = f"bu='%{bu_location_type.upper()}%' AND sap_id='%{sapid}%'"
                        params = urdhva_base.queryparams.QueryParams()
                        params.limit = 100
                        params.fields = None
                        params.q = query
                        params.sort = json.dumps({"updated": -1})
                        # Fetch from database
                        locdata = await hpcl_cng_model.LocationMaster.get_all(params)
                        if locdata:
                            location = locdata[0]
                            loc_dt = {
                                "state": location.state,
                                "region": location.region,
                                "district": location.district,
                                "city": location.city,
                            }
                        else:
                            raise HTTPException(status_code=404, detail="Location data not found in both Redis and database.")
                
                except Exception as e:
                    raise HTTPException(status_code=500, detail="Error fetching location data.") from e

            # Generate alert data
            alert = await hpcl_cng_model.Alerts(
                sop_id=sopid,
                sap_id=sapid,
                alert_id=data['alert_id'],
                interlock_name=interlockname,
                location_name=doc['location_name'],
                alert_type=bu.upper(),
                priority=data['priority'].upper(),
                location_device_id=deviceid,
                alert_status="open",
                device_type=data["deviceType"],
                device_name=data['deviceName'],
                role='',
                district=loc_dt.get('district', ''),
                city=loc_dt.get('city', ''),
                alert_history=data.get('alertHistory', []),
                interlock_id='',  
                closed=False,
                alert_message=data['message']
            )
            
            if static_data:
                for key, value in static_data.items():
                    setattr(alert, key, value)

            data_obj = await hpcl_cng_model.AlertsCreate(**alert)
            await hpcl_cng_model.Alerts.create(data_obj)
            
            # Start workflow if applicable
            if interlockname:
                await start_workflow(alert.alert_id, interlockname, alert.location_device_id, bu_location_type, sapid)
            else:
                logger.info(f"Unable to find Camunda workflow for interlock: {interlockname}, BU: {bu}")

            return {"status": True, "message": "Alert Created Successfully", "data": alert}
        
        except Exception as e:
            logger.exception(e)
            return {"status": False, "message": str(e), "data": None}