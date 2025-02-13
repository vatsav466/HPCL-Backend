import urdhva_base
import json
import datetime
import traceback
import hpcl_ceg_enum
import hpcl_ceg_model
import urdhva_base.redispool
import utilities.interlock_mapping as interlock_mapping
import orchestrator.alerting.alert_helper as alert_helper
from orchestrator.workflow.workflow_process import Camunda
import orchestrator.analytics.vts_analysis as vts_analysis

logger = urdhva_base.logger.Logger.getInstance('alert_factory_log')


class AlertFactory:
    @classmethod
    async def create_bu_alert(cls, alert_data, camunda_url=None):
        """
        For translating bu level data into unique alert format
        """
        ...

    @classmethod
    async def close_bu_alert(cls, alert_data):
        """
        For translating bu level data into unique alert format
        """
        ...

    @classmethod
    async def create_alert(cls, alert_data, camunda_url=urdhva_base.settings.camunda_url):
        """
        For translating device level data into unique alert format and creating it in the database

        Parameters:
            alert_data (dict): A dictionary containing the data to create the alert
                - bu (str): Business unit
                - sopid (str): SOP ID
                - sapid (str): SAP ID
                - interlockName (str): Interlock name
                - severity (str): Severity of the alert
                - message (str): Alert message
                - alertHistory (list): List of alert history messages
                - location_data (dict): Dictionary containing location related data
            camunda_url (String): Camunda connection URL
        Returns:
            dict: A dictionary containing the status, message and the created alert document
        """
        try:
            # print("Alert data:", alert_data)
            bu = alert_data['bu']
            sop_id = alert_data.get('sop_id', '')
            sap_id = alert_data['sap_id']
            interlock_name = alert_data.get('interlock_name', '')
            status, location_data = await alert_helper.get_location_details(bu, sap_id)
            # print("location_data --> ", location_data)
            # if not status:
            #     return False, location_data
            base_data = {
                key: location_data.get(key, '') for key in [
                    'state', 'city', 'zone', 'region', 'district', 'terminal_plant_id',
                    'terminal_plant_name', 'sales_area', 'category'
                ]
            }
            base_data.update({key: alert_data.get(key, '') for key in ['device_id', 'device_type', 'device_name']})
            base_data.update({"sop_id": sop_id, "sap_id": sap_id, "bu": bu,
                              "location_name": location_data.get('name', '')})

            # Create Alert
            alert_id = await alert_helper.get_alert_unique_id(bu, sap_id, sop_id, alert_data.get('device_id'))
            if not alert_data.get('alert_id'):
                alert_data['alert_id'] = alert_id
            unique_id = await alert_helper.get_alert_unique_id(bu, sap_id, sop_id)

            # Generate alert alert_data
            alert_resp = await hpcl_ceg_model.AlertsCreate(**{**base_data,
                                                        'severity': alert_data.get('severity').capitalize() if alert_data.get('severity') else "Medium",
                                                        'alert_status': hpcl_ceg_enum.AlertStatus.Open,
                                                        'alert_state': hpcl_ceg_enum.AlertState.InProgress,
                                                        'unique_id': unique_id, 'alert_section': alert_data.get("alert_section", bu),
                                                        'external_id': alert_data.get('vendor_alert_id', alert_data['alert_id']),
                                                        'interlock_name': interlock_name,
                                                        'interlock_id': '',
                                                        'vehicle_number': alert_data.get('vehicle_number',''),
                                                        'violation_type': alert_data.get('violation_type',''),
                                                        'clear_count': alert_data.get('clear_count',False),
                                                        'alert_history': alert_data.get('alert_history',[]),
                                                        'device_msg': alert_data.get('message', ''),
                                                        'alert_message': alert_data.get('alert_message',''),
                                                        'last_sms_to': [], 'last_mailed_to': [],
                                                        'last_escalated_to': [],
                                                        'last_notified_to': [], 'assigned_to': '',
                                                        'assigned_to_role': '',
                                                        'assigned_users': [], 'assigned_user_roles': [],
                                                        'indent_status': hpcl_ceg_enum.IndentStatus.Pending,
                                                        'dealer_id': str(alert_data.get('dealer_id', '')),
                                                        'product_code': str(alert_data.get('product_code', '')),
                                                        'indent_no': str(alert_data.get('indent_no', '')),
                                                        'workflow_datetime': alert_data.get(
                                                            'workflow_datetime',
                                                            datetime.datetime.now(datetime.UTC)
                                                            .strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"
                                                        ),
                                                        'indent_raised_date': alert_data.get('indent_raised_date', None),
                                                        'dry_out_in_days': str(alert_data.get('dry_out_in_days', '1')),
                                                        'servicing_plant_id': str(alert_data.get('servicing_plant_id', '')),
                                                        'servicing_plant_name': str(alert_data.get('servicing_plant_name', '')),
                                                        'progress_rate': 1,
                                                        'transporter_name': alert_data.get("transporter_name", ""),
                                                        'transporter_code': alert_data.get("transporter_code", ""),
                                                        'vehicle_blocked_start_date': alert_data.get("vehicle_blocked_start_date", None),
                                                        'vehicle_blocked_end_date': alert_data.get("vehicle_blocked_end_date", None),
                                                        'origin_altid': alert_data.get('origin_altid',''),
                                                        'external_timestamp': alert_data.get('alert_timestamp', datetime.datetime.now(datetime.UTC).isoformat()),
                                                        'raw_data': {}}).create()

            redis_ins = await urdhva_base.redispool.get_redis_connection()
            if alert_data.get("alert_section",'') in ["VA"]:
                await redis_ins.setex(alert_data['alert_id'], 3*60*60, alert_resp['id'])
            else:
                await redis_ins.hset("alert_mapping", alert_data['alert_id'], alert_resp['id'])
            payload = {"businessKey": unique_id,
                       "variables": {"alert_id": {"value": alert_resp['id'], "type": "String"},
                                     "interlock_name": {"value": interlock_name, "type": "String"},
                                     "interlock_id": {"value": "", "type": "String"},
                                     "location_device_id": {"value": alert_data.get('device_id', ''), "type": "String"},
                                     "location_type": {"value": bu, "type": "String"},
                                     "sap_id": {"value": sap_id, "type": "String"},
                                     "sop_id": {"value": sop_id, "type": "String"},
                                     "dealer_id": {"value": alert_data.get('dealer_id', ''), "type": "String"},
                                     "product_code": {"value": str(alert_data.get('product_code', '')), "type": "String"},
                                     "workflow_datetime": {"value": alert_data.get(
                                         'workflow_datetime',
                                         datetime.datetime.now(datetime.UTC)
                                         .strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"), "type": "String"},
                                     "indent_no": {"value": alert_data.get('indent_no', ''), "type": "String"},
                                     "indent_raised_date": {"value": alert_data.get('indent_raised_date', ''), "type": "String"},
                                     "terminal_plant_name": {"value": alert_data.get('terminal_plant_name', ''), "type": "String"},
                                     "prod_reqd_dt": {"value": alert_data.get('prod_reqd_dt', ''), "type": "String"},
                                    "terminal_plant_id": {"value": alert_data.get('terminal_plant_id', ''), "type": "String"}}}

            # Create Interlock
            # Start workflow after creating the interlock
            if interlock_name:
                # Create Interlock
                interlock = await hpcl_ceg_model.InterlockCreate(**{**base_data,
                                                                    'interlock_name': interlock_name,
                                                                    'interlock_status': hpcl_ceg_enum.AlertStatus.Open}
                                                                 ).create()

                # Fetch the updated alert data
                alert_data = await hpcl_ceg_model.Alerts.get(alert_resp['id'])

                # Update the interlock ID in the alert
                alert_data.interlock_id = str(interlock['id'])

                # Convert alert_data to a dictionary
                alert_data_dict = alert_data.dict() if hasattr(alert_data, 'dict') else alert_data.__dict__

                # Modify the alert with the updated data
                alert_update = await hpcl_ceg_model.Alerts(**alert_data_dict).modify()

                payload["variables"]["interlock_id"] = {"value": interlock['id'], "type": "String"}
                interlock_name = interlock_mapping.get_interlock_name(bu=bu, interlock_name=interlock_name,sop_id=sop_id)
                workflowid = interlock_name["workflow_name"] if interlock_name["workflow_name"] else interlock_name["interlock_name"]
                workflow_id = interlock_mapping.fmt_il_name(workflowid)
                # Uncomment below line to stop workflow for VA
                if alert_data_dict.get("alert_section") not in ["VA", "VTS"]:
                    await Camunda().start_workflow(payload=payload, workflowId=workflow_id, camunda_url=camunda_url)
                    await redis_ins.hset("alert_camunda_url", str(alert_resp['id']), camunda_url)

                # Updating for VTS Alert history with alert_id
                if alert_data_dict.get("alert_section") == "VTS":
                    await vts_analysis.update_alert_id_to_vts_history(alert_id=str(alert_resp['id']), vts_alert_id=alert_data_dict.get("vts_alert_history_ids", []))

                # if alert_data_dict.get("alert_section") not in ["VA", "VTS"]:
                #     await Camunda().start_workflow(payload=payload, workflowId=workflow_id, camunda_url=camunda_url)
                #     await redis_ins.hset("alert_camunda_url", str(alert_resp['id']), camunda_url)
                # else:
                #     await Camunda().start_workflow(payload=payload, workflowId=workflow_id, camunda_url=camunda_url)
                #     await redis_ins.hset("alert_camunda_url", str(alert_resp['id']), camunda_url)
            else:
                print(f"Unable to find Camunda workflow for interlock: {interlock_name}, BU: {bu}")
                logger.info(f"Unable to find Camunda workflow for interlock: {interlock_name}, BU: {bu}")

            return True, "Alert Created"

        except Exception as e:
            print(traceback.format_exc())
            logger.error(f"Error in alert creation {e}, traceback {traceback.format_exc()}")
            return False, f"Error in alert creation {e}"

    @classmethod
    async def close_alert(cls, alert_data):
        """
        Close Alert and Interlock for the given BU, SOP ID and SAP ID

        Parameters:
            alert_data (dict): A dictionary containing the data to close the alert
                - bu (str): Business unit
                - sop_id (str): SOP ID
                - sap_id (str): SAP ID

        Returns:
            dict: A dictionary containing the status, message and the closed alert document
        """
        print("alert_data close ---> ", alert_data)
        try:
            # il_data = None
            # al_data = None
            if 'BU' in alert_data.keys():
                bu = alert_data['BU']
            else:
                bu = alert_data['bu']
            if 'interlock_id' not in alert_data.keys():
                # Query for Interlock
                query = f"interlock_name='{alert_data['interlock_name']}' AND bu='{bu}' AND sop_id='{alert_data['sop_id']}' AND sap_id='{alert_data['sap_id']}'"
                params = urdhva_base.queryparams.QueryParams()
                params.limit = 1
                params.q = query
                il_resp = await hpcl_ceg_model.Interlock.get_all(params)
                il_data = []
                if il_resp and hasattr(il_resp, '__dict__') and il_resp.__dict__.get('body'):
                    # Decode and parse Interlock response
                    body_str = il_resp.__dict__['body'].decode('utf-8')
                    il_json = json.loads(body_str)
                    il_data = il_json.get("data", [])

                # Query for Alert
                query = f"external_id='{alert_data['alert_id']}'"
                params = urdhva_base.queryparams.QueryParams()
                params.limit = 1
                params.q = query
                alert_resp = await hpcl_ceg_model.Alerts.get_all(params)
                alert_data_list = []
                if alert_resp and hasattr(alert_resp, '__dict__') and alert_resp.__dict__.get('body'):
                    # Decode and parse Alert response
                    body_str = alert_resp.__dict__['body'].decode('utf-8')
                    alert_json = json.loads(body_str)
                    alert_data_list = alert_json.get("data", [])

                # Handle case where both Interlock and Alert are not found
                if not alert_data_list and not il_data:
                    logger.info("Both Interlock and Alert records not found. Skipping closure.")
                    return

                # Modify Interlock if found
                if il_data:
                    interlock = il_data[0]
                    interlock['interlock_status'] = hpcl_ceg_enum.AlertStatus.Close.value
                    data_obj = hpcl_ceg_model.Interlock(**interlock)
                    await data_obj.modify()

                # Modify Alert if found
                if alert_data_list:
                    alert = alert_data_list[0]
                    if alert_data.get("alert_history"):
                        if not alert.get("alert_history"):
                            alert["alert_history"] = alert_data["alert_history"]
                        else:
                            alert_data["alert_history"]["allocated_time"] = alert["alert_history"][-1].get("processed_time")
                            alert["alert_history"].append(alert_data["alert_history"])
                    alert['severity'] = alert_data.get('severity', "Medium").capitalize()
                    alert['alert_status'] = hpcl_ceg_enum.AlertStatus.Close.value
                    alert['alert_state'] = hpcl_ceg_enum.AlertState.Resolved.value
                    alert['interlock_name'] = alert_data.get('interlock_name', '')
                    if il_data:
                        alert['interlock_id'] = str(il_data[0]['id'])
                    data_obj = hpcl_ceg_model.Alerts(**alert)
                    await data_obj.modify()
                    redis_ins = await urdhva_base.redispool.get_redis_connection()
                    await redis_ins.hdel("alert_camunda_url", str(alert['id']))

                print("Interlock and Alert updated successfully.")

            else:
                il_data = await hpcl_ceg_model.Interlock.get(alert_data['interlock_id'])
                if not isinstance(il_data, dict):
                    il_data = il_data.__dict__
                il_data['interlock_status'] = hpcl_ceg_enum.AlertStatus.Close.value
                data_obj = hpcl_ceg_model.Interlock(**il_data)
                await data_obj.modify()
            
                al_data = await hpcl_ceg_model.Alerts.get(alert_data['alert_id'])
                if not isinstance(al_data, dict):
                    al_data = al_data.__dict__
                al_data['alert_status'] = hpcl_ceg_enum.AlertStatus.Close.value
                al_data['alert_state'] = hpcl_ceg_enum.AlertState.Resolved.value
                redis_ins = await urdhva_base.redispool.get_redis_connection()
                if await redis_ins.hexists("alert_mapping", al_data.get('external_id', '')):
                    await redis_ins.hdel("alert_mapping", al_data['external_id'])
                data_obj = hpcl_ceg_model.Alerts(**al_data)
                await data_obj.modify()
                await redis_ins.hdel("alert_camunda_url", str(al_data['id']))
                await redis_ins.close()

            return True, {"status": "Alert Closed"}
        
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            logger.error(f"Error in alert closure {e}, traceback {traceback.format_exc()}")
            return False, f"Error in alert creation {e}"
