import urdhva_base
import json
import copy
import datetime
import traceback
import hpcl_ceg_model
import utilities.interlock_mapping
import utilities.helpers as helpers
import dateutil.parser as dt_parser
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
            # alert_data -->  {'tl_number': 'MP09HH7297', 'report_duration': '2024-12-2316: 19: 15', 'total_trips': 1, 
            # 'stoppage_violations_count': 1, 'route_deviation_count': 0, 'speed_violation_count': 0, 
            # 'main_supply_removal_count': 0, 'night_driving_count': 0, 'no_halt_zone_count': 0, 
            # 'device_offline_count': 0, 'device_tamper_count': 0, 'approved_by': '', 
            # 'vendor_id': '0027048953', 'location_id': '2539', 'location_type': 'LPG', 'alert_type': 'VTS'}
            
            status, location_details = await alert_helper.get_location_details(alert_data['location_type'], alert_data['location_id'])
            if not status:
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
                try:
                    # getting key and details from vts_interlock_mapping from vts_mapping.
                    for key, details in vts_mapping.vts_interlock_mapping.items():
                        if not record.get(key):
                            continue
                        # checking the instance of violation_type(key) from quarter period
                        # whether it is first instance or second instance and so on..... 
                        altcount = await check_violation_count.CheckViolationCount().check_violation_count(record['location_id'],
                                                                                                            record['location_type'],
                                                                                                            record['tl_number'], key)
                        maintenance_time = helpers.get_time_stamp_by_delta(days=15, 
                                            with_month_start_day=False, 
                                            ascending=False,
                                            date_time_format=None).strftime("%Y-%m-%d")
                        maintenance_time = datetime.datetime.strptime(maintenance_time, "%Y-%m-%d")
                        data={}
                        # if it is not first instance then check the frequency of records from the vts_alert_history
                        # within fortnight period and using {key}_instance='' example stoppage_violation_count_instance=''
                        # and stoppage_violation_count>=1 based on bu, location_id and tl_number(vehicle_number).
                        if altcount['count']:
                            query = (f"location_id='{record['location_id']}' and tl_number='{record['tl_number']}' "
                                f"and {key}>=1 and created_at::DATE>'{maintenance_time}' and location_type='{record['location_type']}' "
                                f"and {key}_instance='' and auto_unblock='true'")
                            data = await hpcl_ceg_model.VtsAlertHistory.get_all(urdhva_base.queryparams.QueryParams(q=query),
                                                                resp_type='plain')
                            print("data--->",data)
                        # if it is first instance then check the frequency of records from the vts_alert_history
                        # within fortnight period and using example stoppage_violation_count>=1 based on bu, 
                        # location_id and tl_number(vehicle_number).   
                        else:
                            query = (f"location_id='{record['location_id']}' and tl_number='{record['tl_number']}' "
                                    f"and {key}>=1 and created_at::DATE>'{maintenance_time}' and location_type='{record['location_type']}' "
                                    f"and auto_unblock='true'")
                            data = await hpcl_ceg_model.VtsAlertHistory.get_all(urdhva_base.queryparams.QueryParams(q=query),
                                                                    resp_type='plain')
                        # check violation if frequency of records count greter than the threshold of paricular key
                        if data['count'] > details['alert_threshold']:
                            print("data--->",data)
                            #print("count--->",data['count'])
                            finarResp = {key: []}  # Initialize with an empty list for the key
                            altcount = altcount['count']
                            for item in data['data']:
                                entry = {
                                "created_at": item['created_at'],
                                "vehicle_number": item['tl_number'],
                                }
                                finarResp[key].append(entry)
                            print("finarResp--->", finarResp)
                            max_limit = int(max(list(details['alerting_rules'].keys())))
                            if altcount > max_limit:
                                altcount = max_limit
                            alert_message = (
                                f"{details['alerting_rules'][str(altcount)]['interlock_name']} Alert for Vehicle: "
                                f"{record['tl_number']} Vendor: {record['vendor_id']} Report_Duration: "
                                f"{record['report_duration']} {key}: {altcount} "
                                f"Alert Summary: {finarResp}"
                            )
                            alert_history = [
                                {
                                    "action_msg": alert_message,
                                    "action_type": "Created",  # Replace with an appropriate value
                                    "alert_status": "Open",  # Replace with the correct alert status
                                }]
                            vts_alert_data = {"bu": record['location_type'],
                                            "sap_id": record['location_id'],
                                            "location_name": location_details['name'],
                                            "vehicle_number": record['tl_number'],
                                            "violation_type": key}
                            interlock_details = utilities.interlock_mapping.get_interlock_name(
                                record['location_type'], details['alerting_rules'][str(altcount)]['interlock_name'])
                            if not interlock_details:
                                continue
                            vts_alert_data.update(interlock_details)
                            # checking if alert already is in active or not based on violation_type if already in active
                            # continue
                            tripinterlockname = await check_violation_count.CheckViolationCount().checktripcount(record['location_id'],
                                                                                                                    record['location_type'],
                                                                                                                    record['tl_number'],key)
                            if tripinterlockname and tripinterlockname["violation_type"]==key:
                                logger.info("alert already exists")
                                print("alert already exists")
                                continue
                            # checking if alert already is in active or not based on interlock_name if already in active
                            # then continue.
                            interlocknamecheck = await check_violation_count.CheckViolationCount().check_interlock(record['location_id'],
                                                                                                                    record['location_type'],
                                                                                                                    record['tl_number'],
                                                                                                                    interlock_details.get("interlock_name",""),
                                                                                                                    key)
                            if interlocknamecheck and interlocknamecheck['interlock_name']==interlock_details["interlock_name"]:
                                logger.info("alert already exists")
                                print("alert already exists")
                                continue
                            vts_alert_data.update(interlock_details)
                            vts_alert_data['alert_section'] = 'VTS'
                            vts_alert_data['alert_history'] = alert_history
                            vts_alert_data['clear_count'] = details['alerting_rules'][str(altcount)]['clear_count']
                            vts_alert_data['severity'] = details['severity']
                            for data in data['data']:
                                violation = f"{key}_instance"
                                data[violation]=str(altcount)
                                await hpcl_ceg_model.VtsAlertHistory(**data).modify()
                            
                            vts_alert_payload = {
                                'vendor_id': alert_data['vendor_id'],
                                'location_id': alert_data['location_id'],
                                'location_type': alert_data['location_type'],
                                'data': [
                                    {
                                      'tt_no':record['tl_number'],
                                      'location_name': location_details['name'],
                                      'transporter_name': '',
                                      'transporter_code': alert_data['vendor_id'],
                                      'vehicle_blocked_desc': f"Instance{altcount}: {key}",
                                      'vehicle_blocked_start_date': recv_time.strftime("%Y-%m-%d"),
                                      'vehicle_blocked_end_date': helpers.get_time_stamp_by_delta(days=details['alerting_rules'][str(altcount)]['block_duration'],
                                                                                                  with_month_start_day=False,
                                                                                                  ascending=True,
                                                                                                  date_time_format=None).strftime("%Y-%m-%d"),
                                      'vehicle_blocked_instance_no': f"Instance{altcount}",
                                      'vehicle_blocked_instance_type': key,
                                      'alert_type': 'VTS'
                                    }
                                ]
                            }
                            print('vts_alert_payload----->',vts_alert_payload)
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
