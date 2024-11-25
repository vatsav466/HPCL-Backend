import urdhva_base
import json
import datetime
import hpcl_ceg_model
import orchestrator.alerting.alert_helper as alert_helper
import orchestrator.alerting.alert_factory as alert_factory

logger = urdhva_base.logger.Logger.getInstance('vts_alert_processing')


class VTSAlertManager(alert_factory.AlertFactory):
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
            for record in alert_data['data']:
                # Retrieve necessary fields from the alert_data
                status, loc_dt = await alert_helper.get_location_details(bu=record['BU'],sap_id=record['sap_id'])
                if not status:
                    logger.info(f"Error in finding location {record['location_id']} "
                                f"for bu {record['location_type']} - {location_details}")
                    continue
                exception_msg = (f"TL Number - {record['tl_number']}, Report Duration - {record['report_duration']}"
                            f", Total Trips - {record['total_trips']}, Stoppage Violations Count - {record['stoppage_violations_count']}" 
                            f", Route Deviation Count - {record['route_deviation_count']}, Speed Violation Count - {record['speed_violation_count']}"
                            f", Main Supply Removal Count - {record['main_supply_removal_count']}, Night Driving Count - {record['night_driving_count']}"
                            f", Device Offline Count - {record['device_offline_count']}, Device Tamper Count - {record['device_tamper_count']}")
                
                query = (f"sap_id={record['location_id']} and tl_number='{record['tl_number']}' "
                     f"and status='Open' and violation_type='{record['violation_type']}'")

                data = await hpcl_ceg_model.VTS.get_all(urdhva_base.queryparams.QueryParams(q=query, limit=1))
                if len(data['data']):
                    # Updating existing EM Lock record
                    vts_record = data['data'][0]
                    vts_record['violation_history'].append(exception_msg)
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
            return await cls.close_alert(alert_data)
            
        except Exception as e:
            raise Exception(status_code=500, detail="Error closing alert.") from e

