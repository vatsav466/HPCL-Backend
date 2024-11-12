import json
import urdhva_base
from api_manager import hpcl_ceg_model
import utilities.bu_key_mapping as bu_key_mapping
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
            loc_dt = await alert_helper.get_location_details(bu=bu_location_type,sap_id=sap_id)
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
