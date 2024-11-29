import urdhva_base
import json
import datetime
import traceback
import hpcl_ceg_model
import orchestrator.alerting.alert_helper as alert_helper
import orchestrator.alerting.alert_factory as alert_factory
import utilities.interlock_mapping as interlock_mapping
import orchestrator.actions.check_violation_count as check_violation_count

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
            violations=["stoppage_violations_count", "route_deviation_count", "speed_violation_count", "main_supply_removal_count",
                        "night_driving_count", "no_halt_zone_count", "device_offline_count", "device_tamper_count"]
            logger.info(f"alert_data received to create alert {alert_data}")
            current_time = datetime.datetime.now(tz=datetime.timezone.utc)
            for record in alert_data['data']:
                # Retrieve necessary fields from the alert_data
                status, loc_dt = await alert_helper.get_location_details(bu=alert_data['location_type'].value,sap_id=alert_data['location_id'])
                if not status:
                    logger.info(f"Error in finding location {record['location_id']} "
                                f"for bu {record['location_type']} - {loc_dt}")
                    continue
                exception_msg = (f"Vehicle Number - {record['tl_number']}, Report Duration - {record['report_duration']}"
                            f", Total Trips - {record['total_trips']}, Stoppage Violations Count - {record['stoppage_violations_count']}" 
                            f", Route Deviation Count - {record['route_deviation_count']}, Speed Violation Count - {record['speed_violation_count']}"
                            f", Main Supply Removal Count - {record['main_supply_removal_count']}, Night Driving Count - {record['night_driving_count']}"
                            f", Device Offline Count - {record['device_offline_count']}, Device Tamper Count - {record['device_tamper_count']}"
                            f", No Halt Zone Count - {record['no_halt_zone_count']}")
                query = (f"sap_id='{alert_data['location_id']}' and vehicle_number='{record['tl_number']}'")
                data = await hpcl_ceg_model.VTS.get_all(urdhva_base.queryparams.QueryParams(q=query, limit=1), resp_type='plain')
                if len(data['data']):
                    vts_record = data['data'][0]
                    vts_record['violation_history'].append(exception_msg)
                    for violation_type in violations:
                         vts_record[violation_type] += int(record[violation_type])
                         vts_record['report_duration'] = record['report_duration']
                    await hpcl_ceg_model.VTS(**vts_record).modify()
                    for violation_type in violations:
                        violation_count = int(vts_record.get(violation_type, 0))
                        if violation_type in ["night_driving_count", "speed_violation_count", "stoppage_violations_count"] and violation_count >5 or violation_type in ["route_deviation_count", "main_supply_removal_count","no_halt_zone_count", "device_offline_count", "device_tamper_count"] and violation_count >=1:
                            alert_count = await check_violation_count.CheckViolationCount().check_violation_count(vts_record['sap_id'], vts_record['bu'], vts_record['vehicle_number'], violation_type)  
                            #get interlock_name based upon violation_type
                            data = await interlock_mapping.get_interlock_name(vts_record['bu'], violation_type, count = alert_count)
                            future_time = data["block_duration"] * 24 * 60 * 60
                            if data["block_duration"] > 730:
                                future_time = 10 * 365 * 24 * 60 * 60
                            Unblock_time = (current_time + datetime.timedelta(seconds=future_time)).strftime('%d-%m-%Y')
                            violation_history_message = f"Block Duration: {data['block_msg']} From {current_time.strftime('%d-%m-%Y')} to {Unblock_time}"
                            alert_doc = {
                                "sap_id" : vts_record["sap_id"],
                                "bu" : vts_record["bu"],
                                "vehicle_number": vts_record["vehicle_number"],
                                "violation_type": violation_type,
                                "sop_id": data["sop_id"],
                                "interlock_name": data["interlock_name"],
                                "alert_history": violation_history_message
                            }
                            vts_record[violation_type] = 0
                            await hpcl_ceg_model.VTS(**vts_record).modify()
                            await cls.create_alert(alert_doc)
                        
                else:
                    vts_record = {"bu": alert_data['location_type'].value, "sap_id": alert_data['location_id'],
                                  "location_name": loc_dt['name'], "vehicle_number": record['tl_number'],
                                  "total_trips": record['total_trips'], 
                                  "stoppage_violations_count": record['stoppage_violations_count'],
                                  "route_deviation_count": record['route_deviation_count'],
                                  "speed_violation_count": record['speed_violation_count'],
                                  "main_supply_removal_count": record['main_supply_removal_count'],
                                  "night_driving_count": record['night_driving_count'],
                                  "no_halt_zone_count": record['no_halt_zone_count'],
                                  "device_offline_count": record['device_offline_count'],
                                  "device_tamper_count" : record['device_tamper_count'],
                                  "alert_status": 'Open', "violation_history": [exception_msg],
                                  "report_duration": record['report_duration']}
                    await hpcl_ceg_model.VTSCreate(**vts_record).create()
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
            return await cls.close_alert(alert_data)
            
        except Exception as e:
            raise Exception(status_code=500, detail="Error closing alert.") from e