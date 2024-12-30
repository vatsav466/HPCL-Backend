import urdhva_base
import json
import copy
import datetime
import traceback
import hpcl_ceg_model
import utilities.interlock_mapping
import utilities.vts_mapping as vts_mapping
import orchestrator.alerting.alert_helper as alert_helper
import orchestrator.alerting.alert_manager as alert_manager
import orchestrator.alerting.alert_factory as alert_factory
import orchestrator.actions.check_violation_count as check_violation_count

logger = urdhva_base.logger.Logger.getInstance('vts_alert_processing')


class VTSAlertManager(alert_factory.AlertFactory):
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
            print("alert_data --> ", alert_data)
            # alert_data -->  {'tl_number': 'MP09HH7297', 'report_duration': '2024-12-2316: 19: 15', 'total_trips': 1, 
            # 'stoppage_violations_count': 1, 'route_deviation_count': 0, 'speed_violation_count': 0, 
            # 'main_supply_removal_count': 0, 'night_driving_count': 0, 'no_halt_zone_count': 0, 
            # 'device_offline_count': 0, 'device_tamper_count': 0, 'approved_by': '', 
            # 'vendor_id': '0027048953', 'location_id': '2539', 'location_type': 'LPG', 'alert_type': 'VTS'}
            
            status, location_details = await alert_helper.get_location_details(alert_data['location_type'], alert_data['location_id'])
            if not status:
                print(f"Error in finding location {alert_data['location_id']} "
                            f"for bu {alert_data['location_type']} - {location_details}")
                logger.info(f"Error in finding location {alert_data['location_id']} "
                            f"for bu {alert_data['location_type']} - {location_details}")
                return
            # Processing alert for each record
            recv_time = datetime.datetime.now(tz=datetime.timezone.utc)
            if isinstance(alert_data, dict):
                alert_records = [alert_data]  # Wrap single record in a list for uniform processing
            elif isinstance(alert_data, list):
                alert_records = alert_data  # Use directly if it's already a list
            else:
                logger.error("Invalid alert_data format. Expected dict or list of dicts.")
                return

            for record in alert_records:
                print("record --> ", record)
                try:
                    for key, details in vts_mapping.vts_interlock_mapping.items():
                        if not record.get(key):
                            continue
                        query = (f"sap_id='{record['location_id']}' and vehicle_number='{record['tl_number']}' "
                                 f"and status='Open' and violation_type='{key}'")
                        data = await hpcl_ceg_model.VTS.get_all(urdhva_base.queryparams.QueryParams(q=query, limit=1),
                                                                resp_type='plain')
                        exception_msg = (f"Vehicle Number - {record['tl_number']}, "
                                         f"Violation Types - {details['description']}, "
                                         f"Exception Date - {recv_time}")
                        if data["data"]:
                            vts_data = data['data'][0]
                            vts_data['violation_count'] += record[key]
                            vts_data.update({"report_duration": record['report_duration'],
                                         "total_trips": record['total_trips'],
                                         "violation_history": vts_data["violation_history"] + [exception_msg]})
                            await hpcl_ceg_model.VTS(**vts_data).modify()
                        else:
                            vts_data = {"bu": record['location_type'], "sap_id": record['location_id'],
                                         "location_name": location_details['name'],
                                         "vehicle_number": record['tl_number'],
                                         "total_trips": record['total_trips'], "status": 'Open',
                                         "violation_history": [exception_msg],
                                         "report_duration": record['report_duration'], 'violation_count': record[key],
                                        'violation_type': key}
                            resp = await hpcl_ceg_model.VTSCreate(**vts_data).create()
                            vts_data['id'] = resp['id']
                        if vts_data['violation_count'] > details['alert_threshold']:
                            altcount = await check_violation_count.CheckViolationCount().check_violation_count(record['location_id'],
                                                                                                            record['location_type'],
                                                                                                            record['tl_number'], key)
                            previousaltCount = await check_violation_count.CheckViolationCount().check_violation_all_count(record['location_id'],
                                                                                                            record['location_type'],
                                                                                                            record['tl_number'], key)
                            alertmsg =[]
                            for key,values in previousaltCount.items():
                                alertmsg.append(key+"Count :%s"% values)

                            altcount = altcount['count']
                            print("altcount",altcount)                                                                                                                                                
                            # TODO Previous month history quarterly 
                            # check all violation function to be implemented                                                                                                           
                            max_limit = int(max(list(details['alerting_rules'].keys())))
                            if altcount > max_limit:
                                altcount = max_limit
                            previous_alert_summary = "; ".join(alertmsg)
                            alert_message = (
                                f"{details['alerting_rules'][str(altcount)]['interlock_name']} Alert for Vehicle: "
                                f"{record['tl_number']} Vendor: {record['vendor_id']} Report_Duration: "
                                f"{record['report_duration']} {key}: {altcount} "
                                f"Previous Alert Summary: {previous_alert_summary}"
                            )
                            alert_history = [
                                {
                                    "action_msg": alert_message,
                                    "action_type": "Created",  # Replace with an appropriate value
                                    "alert_status": "Open",  # Replace with the correct alert status
                                }]
                            vts_alert_data = copy.deepcopy(vts_data)
                            interlock_details = utilities.interlock_mapping.get_interlock_name(
                                alert_data['location_type'], details['alerting_rules'][str(altcount)]['interlock_name'])
                            if not interlock_details:
                                continue
                            vts_alert_data.update(interlock_details)
                            interlocknamecheck = await check_violation_count.CheckViolationCount().check_interlock(record['location_id'],
                                                                                                            record['location_type'],
                                                                                                            record['tl_number'], interlock_details.get("interlock_name",""),key)
                            print("interlock_name_check", interlocknamecheck['interlock_name'])
                            print("interlock_name---->",interlock_details["interlock_name"])
                            if interlocknamecheck and interlocknamecheck['interlock_name']==interlock_details["interlock_name"]:
                                continue
                            vts_alert_data['alert_section'] = 'VTS'
                            vts_alert_data['alert_history'] = alert_history
                            vts_alert_data['clear_count'] = details['alerting_rules'][str(altcount)]['clear_count']
                            await cls.create_alert(vts_alert_data, camunda_url)
                except Exception as e:
                    print(traceback.format_exc())
                    logger.error(f"Exception in processing alert data {e}, Traceback "
                                 f"{traceback.format_exc()}, data {alert_data}")
        except Exception as e:
            print(traceback.format_exc())
            logger.error(f"Exception in processing alert data {e}, Traceback "
                         f"{traceback.format_exc()}, data {alert_data}")

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
