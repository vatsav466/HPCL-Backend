import urdhva_base
import json
import datetime
import traceback
import hpcl_ceg_model
import orchestrator.alerting.alert_helper as alert_helper
import orchestrator.alerting.alert_factory as alert_factory
import orchestrator.actions.clear_vts_count as clear_vts_count
import orchestrator.actions.check_trip_count as check_trip_count
import orchestrator.actions.check_interlock_name as check_interlock_name
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
            print(f"alert_data received to create alert {alert_data}")
            logger.info(f"alert_data received to create alert {alert_data}")
            for record in alert_data['data']:
                print("for loop record --> ", record)
                # Retrieve necessary fields from the alert_data
                status, loc_dt = await alert_helper.get_location_details(bu=alert_data['location_type'].value,sap_id=alert_data['location_id'])
                print("status --> ", status)
                print("loc_dt --> ", loc_dt)
                if not status:
                    print(f"Error in finding location {record['location_id']} "
                                f"for bu {record['location_type']} - {loc_dt}")
                    logger.info(f"Error in finding location {record['location_id']} "
                                f"for bu {record['location_type']} - {loc_dt}")
                    continue
                exception_msg = (f"Vehicle Number - {record['tl_number']}, Report Duration - {record['report_duration']}"
                            f", Total Trips - {record['total_trips']}, Stoppage Violations Count - {record['stoppage_violations_count']}" 
                            f", Route Deviation Count - {record['route_deviation_count']}, Speed Violation Count - {record['speed_violation_count']}"
                            f", Main Supply Removal Count - {record['main_supply_removal_count']}, Night Driving Count - {record['night_driving_count']}"
                            f", Device Offline Count - {record['device_offline_count']}, Device Tamper Count - {record['device_tamper_count']}"
                            f", No Halt Zone Count - {record['no_halt_zone_count']}")
                print("exception_msg --> ", exception_msg)
                vts_record = None
                query = (f"sap_id='{alert_data['location_id']}' and vehicle_number='{record['tl_number']}' and alert_status='Open'")
                print("query --> ", query)
                data = await hpcl_ceg_model.VTS.get_all(urdhva_base.queryparams.QueryParams(q=query, limit=1))
                resp_dict = data.__dict__
                print("data --> ", data.__dict__)
                if resp_dict.get('body'):
                    # Decode the byte string to a normal string
                    body_str = resp_dict['body'].decode('utf-8')
                    data = json.loads(body_str)  
                    
                    if len(data['data']):
                        print("into if cond len --> ", len(data['data']))
                        # Updating existing VTS record
                        vts_record = data['data'][0]
                        print("into if cond len --> ", len(data['data']))
                        vts_record['violation_history'].append(exception_msg)
                        print("vts_record --> ", vts_record)
                        for violation_type in ["stoppage_violations_count", "route_deviation_count", "speed_violation_count", "main_supply_removal_count",
                                    "night_driving_count", "no_halt_zone_count", "device_offline_count", "device_tamper_count"]:
                            print("into for loop of violation_type --> ", violation_type)
                            vts_record[violation_type] += int(record[violation_type])
                        vts_record['report_duration'] = record['report_duration']
                        await hpcl_ceg_model.VTS(**vts_record).modify()

                        for violation_type in ["stoppage_violations_count", "route_deviation_count", "speed_violation_count", "main_supply_removal_count",
                                    "night_driving_count", "no_halt_zone_count", "device_offline_count", "device_tamper_count"]:
                            print("into for loop of violation_type --> ", violation_type)
                            violation_count = int(vts_record.get(violation_type, 0))
                            print("into for loop of violation_count --> ", violation_count)
                            if violation_type in ["night_driving_count", "speed_violation_count", "stoppage_violations_count"] and \
                               violation_count >5 or violation_type in ["route_deviation_count", "main_supply_removal_count", 
                                                                        "no_halt_zone_count", "device_offline_count", "device_tamper_count"] \
                                                                        and violation_count >=1:
                                print("into if cond violation_type --> ", violation_type)
                                print("into if cond violation_count --> ", violation_count)
                                #getting the previous alert_count for particular violation based on vehicle_number , violation_type and sap_id
                                alert_count = await check_violation_count.CheckViolationCount.check_violation_count(vts_record['sap_id'], vts_record['vehicle_number'], vts_record['bu'], violation_type)  
                                print("into if cond alert_count --> ", alert_count)
                                #getting the all previous alert_count for this vehicle_number.
                                previous_alert_count = await check_violation_count.CheckViolationCount.check_violation_all_count(vts_record['sap_id'], vts_record['vehicle_number'], vts_record['bu'], violation_type)
                                print("into if cond previous_alert_count --> ", previous_alert_count)
                                alertmsg = []
                                for key, values in previous_alert_count.items():
                                    print("into for loop key,values --> ", key,values)
                                    alertmsg.append(key+"Count :%s"%values)
                                print("into if cond alertmsg --> ", alertmsg)
                                violation_history_message = "%s Alert For Vehicle:%s Report Duration:%s"%(violation_type, vts_record['vehicle_number'], vts_record['record_duration'])
                                print("into if cond violation_history_message --> ", violation_history_message)
                                vts_doc = vts_mapping[key]
                                print("into if cond vts_doc --> ", vts_doc)
                                if vts_doc[alert_count]:
                                    print("into vts doc in if cond --> ", vts_doc[alert_count])
                                    doc = vts_doc[str(alert_count)]
                                    vts_record['interlock_name'] = doc['inetrlock_name']
                                    vts_record['block_duration'] = doc['block_duration']
                                    vts_record['block_msg'] = doc['blck_msg']
                                    vts_record['violation_type'] = violation_type
                                else:
                                    print("into vts doc in else cond --> ", vts_doc)
                                    vts_record['interlock_name'] = vts_doc['inetrlock_name']
                                    vts_record['block_duration'] = vts_doc['block_duration']
                                    vts_record['block_msg'] = vts_doc['blck_msg']
                                    vts_record['violation_type'] = violation_type

                                currentTime = int(datetime.datetime.now().timestamp())
                                #Here Checking the device_name in the vts_record with device_name in the alert table.
                                tripinterlock_name = await check_trip_count.CheckTripCount.check_trip_count(vts_record['sap_id'], vts_record['vehicle_number'], vts_record['location_type'].value, violation_type)

                                device_interlock = vts_record['violation_type'].replace(" ","_")
                                if tripinterlock_name == device_interlock:
                                    continue
                                future_time = vts_record['block_duration'] * 24 * 60 * 60
                                if vts_record['block_duration'] > 730:
                                    future_time = 10 * 365 *24 * 60 * 60
                                UnblockTime = datetime.datetime.fromtimestamp(currentTime + int(future_time)).strftime('%d-%m-%Y')
                                #clearing the count in VTS based on the violation_type
                                await clear_vts_count.ClearVtsCount.clear_vts_count(key, vts_record['tl_number'])
                                #Checking the interlock_name in the Alerts with the Interlock_name in the vts_record
                                truckinterlock = await check_interlock_name.CheckInterlockName.check_interlock_name( vts_record['sap_id'], vts_record['tl_number'], vts_record['location_type'].value, vts_record['interlock_name'])
                                truckidname = vts_record['ineterlock_name'].replace(" ","_")
                                if truckinterlock == truckidname:
                                    continue
                                await cls.create_alert(vts_record)
                    else:
                        print("into else cond --> ", vts_record)
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
                        print("before create --> ", vts_record)
                        await hpcl_ceg_model.VTSCreate(**vts_record).create()

                vts_record['location_data'] = loc_dt

            return await cls.create_alert(vts_record)

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