import urdhva_base
import json
import traceback
import hpcl_ceg_enum
import api_manager
import utilities.interlock_mapping as interlock_mapping
import orchestrator.alerting.alert_helper as alert_helper
from orchestrator.workflow.workflow_process import Camunda

logger = urdhva_base.logger.Logger.getInstance('alert_factory_log')


class AlertFactory:
    @classmethod
    async def create_bu_alert(cls, alert_data):
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
    async def create_alert(cls, alert_data):
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

        Returns:
            dict: A dictionary containing the status, message and the created alert document
        """
        try:
            bu = alert_data['bu']
            sop_id = alert_data['sop_id']
            sap_id = alert_data['sap_id']
            interlock_name = alert_data['interlock_name']
            status, location_data = await alert_helper.get_location_details(bu, sap_id)
            if not status:
                return False, location_data
            base_data = {key: location_data.get(key) for key in ['state', 'city', 'zone', 'region', 'district']}
            base_data.update({key: alert_data.get(key, '') for key in ['device_id', 'device_type', 'device_name']})
            base_data.update({"sop_id": sop_id, "sap_id": sap_id, "bu": bu,
                              "location_name": location_data.get('name', '')})

            # Create Alert
            alert_id = await alert_helper.get_alert_unique_id(bu, sap_id, sop_id, alert_data.get('device_id'))
            unique_id = await alert_helper.get_alert_unique_id(bu, sop_id)

            # Generate alert alert_data
            resp = await api_manager.hpcl_ceg_model.AlertsCreate(**{**base_data,
                                                        'severity': alert_data.get('severity', "Critical").capitalize(),
                                                        'alert_status': hpcl_ceg_enum.AlertStatus.Open,
                                                        'alert_state': hpcl_ceg_enum.AlertState.InProgress,
                                                        'unique_id': unique_id, 'alert_section': bu,
                                                        'external_id': alert_data.get('alert_id', alert_id),
                                                        'interlock_name': interlock_name,
                                                        'interlock_id': interlock_name,
                                                        'alert_history': [],
                                                        'device_msg': alert_data.get('message', ''),
                                                        'last_sms_to': [], 'last_mailed_to': [],
                                                        'last_escalated_to': [],
                                                        'last_notified_to': [], 'assigned_to': '',
                                                        'assigned_to_role': '',
                                                        'raw_data': {}}).create()

            payload = {"businessKey": alert_data.get('alert_id', ''),
                       "variables": {"alert_id": {"value": resp['id'], "type": "String"},
                                     "interlock_name": {"value": interlock_name, "type": "String"},
                                     "interlock_id": {"value": "", "type": "String"},
                                     "location_device_id": {"value": alert_data.get('device_id', ''), "type": "String"},
                                     "location_type": {"value": bu, "type": "String"},
                                     "sap_id": {"value": sap_id, "type": "String"},
                                     "sop_id": {"value": sop_id, "type": "String"}
                                     }}

            # Create Interlock
            # Start workflow after creating the interlock
            if interlock_name:
                # Create Interlock
                interlock = await api_manager.hpcl_ceg_model.InterlockCreate(**{**base_data,
                                                                    'interlock_status': hpcl_ceg_enum.AlertStatus.Open}
                                                                 ).create()
                payload["variables"]["interlock_id"] = {"value": resp['id'], "type": "String"}

                # Todo:- Need to add interlock mapping
                work_flow_id = eval(f"{bu}InterlockMapping.{sap_id}.value")
                await Camunda().start_workflow(payload=payload, workflowId=work_flow_id)
            else:
                logger.info(f"Unable to find Camunda workflow for interlock: {interlock_name}, BU: {bu}")

            return True, "Alert Created"

        except Exception as e:
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
        try:
            bu = alert_data['BU']
            if 'interlock_id' in alert_data.keys() and alert_data['interlock_id']:
                il_data = await api_manager.hpcl_ceg_model.Interlock.get(alert_data['interlock_id'])
                if not isinstance(il_data, dict):
                    il_data = il_data.__dict__
                il_data['interlock_status'] = hpcl_ceg_enum.AlertStatus.Close.value
                data_obj = api_manager.hpcl_ceg_model.Interlock(**il_data)
                await data_obj.modify()
            else:
                logger.info(f"Unable to find Interlock: {alert_data['interlock_name']}, BU: {bu}")

            al_data = await api_manager.hpcl_ceg_model.AlertsCreate.get(alert_data['alert_id'])
            if not isinstance(al_data, dict):
                al_data = al_data.__dict__
            al_data['alert_status'] = hpcl_ceg_enum.AlertStatus.Close.value
            al_data['alert_state'] = hpcl_ceg_enum.AlertState.Resolved.value
            data_obj = api_manager.hpcl_ceg_model.Alerts(**al_data)
            await data_obj.modify()

            return True, "Alert Closed"
        
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            logger.error(f"Error in alert closure {e}, traceback {traceback.format_exc()}")
            return False, f"Error in alert creation {e}"
