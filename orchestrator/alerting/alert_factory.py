import json
import traceback
import urdhva_base
from api_manager import hpcl_ceg_model, hpcl_ceg_enum
from orchestrator.workflow.workflow_process import Camunda
from orchestrator.alerting.alert_helper import get_alert_unique_id
from utilities.tas_interlock_mapping import TASInterlockMapping
from utilities.lpg_interlock_mapping import LPGInterlockMapping
from utilities.va_interlock_mapping import VAInterlockMapping
from utilities.vts_interlock_mapping import VTSInterlockMapping
from utilities.cris_interlock_mapping import CRISInterlockMapping

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
                - BU (str): Business unit
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
            bu = alert_data['BU']
            sop_id = alert_data['sopid']
            sap_id = alert_data['sapid']
            interlock_name = alert_data['interlockName']

            # Create Alert
            uniqueId = await get_alert_unique_id(bu, sop_id)
            # Generate alert alert_data
            alert = hpcl_ceg_model.AlertsCreate(
                bu=bu,
                sap_id=sap_id,
                sop_id=sop_id,
                location_name=bu,
                severity=alert_data['severity'].capitalize(),
                alert_status=hpcl_ceg_enum.AlertStatus.Open,
                alert_state=hpcl_ceg_enum.AlertState.InProgress,
                unique_id=uniqueId,
                alert_section=bu,
                external_id=alert_data.get('alert_id', ''),
                interlock_name=interlock_name,
                interlock_id=interlock_name,
                device_id=alert_data['deviceId'],
                device_type=alert_data["deviceType"],
                device_name=alert_data['deviceName'],
                device_msg=alert_data['message'],
                alert_history=alert_data['location_data'].get('alertHistory', []),
                last_sms_to=[],
                last_mailed_to=[],
                last_escalated_to=[],
                last_notified_to=[],
                assigned_to='',
                assigned_to_role='',
                district=alert_data['location_data'].get('district', ''),
                zone=alert_data['location_data'].get('zone', ''),
                region=alert_data['location_data'].get('region', ''),
                state=alert_data['location_data'].get('state', ''),
                city=alert_data['location_data'].get('city', ''),
                raw_data={}
            )

            resp = await alert.create()

            payload = {"businessKey": alert.external_id,
                "variables": {"alert_id": {"value": resp['id'], "type": "String"},
                              "interlock_name": {"value": alert.interlock_name, "type": "String"},
                              "location_device_id": {"value": alert.device_id, "type": "String"},
                              "location_type": {"value": alert.bu, "type": "String"},
                              "sap_id": {"value": alert.sap_id, "type": "String"},
                              "sop_id": {"value": alert.sop_id, "type": "String"}
                              }}

            # Create Interlock
            # Start workflow after creating the interlock
            if interlock_name:
                # Create Interlock
                interlock = hpcl_ceg_model.InterlockCreate(
                    bu=bu,
                    sop_id=sop_id,
                    sap_id=sap_id,
                    interlock_name=interlock_name,
                    location_name=bu,
                    device_name=alert_data['deviceName'],
                    device_type=alert_data["deviceType"],
                    device_id=alert_data['deviceId'],
                    state=alert_data['location_data'].get('state', ''),
                    city=alert_data['location_data'].get('city', ''),
                    zone=alert_data['location_data'].get('zone', ''),
                    interlock_status=hpcl_ceg_enum.AlertStatus.Open
                )
                await interlock.create()

                workflowId = eval(f"{bu}InterlockMapping.{sap_id}.value")
                await Camunda().start_workflow(payload=payload, workflowId=workflowId)
            else:
                logger.info(f"Unable to find Camunda workflow for interlock: {workflowId}, BU: {bu}")

            return {"status": True, "message": "Alert and Interlock Created Successfully", "alert_data": alert}

        except Exception as e:
            logger.error(e)
            print(e)
            print(traceback.format_exc())
            return {"status": False, "message": str(e), "alert_data": None}

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
            sop_id = alert_data['sop_id']
            sap_id = alert_data['sap_id']

            # Close Interlock
            query = f"bu='{bu}' AND sop_id='{sop_id}' AND sap_id='{sap_id}'"

            params = urdhva_base.queryparams.QueryParams()
            params.limit = 1
            params.q = query
            interlock = await hpcl_ceg_model.InterlockCreate.get_all(params)
            resp = interlock.__dict__
            print("resp --> ", resp)
            if resp.get('body'):
                # Decode the byte string to a normal string
                body_str = resp['body'].decode('utf-8')
                interlock = json.loads(body_str)          
                print("interlock --> ", interlock)  
                il_data = interlock["data"][0]
                il_data['interlock_status'] = hpcl_ceg_enum.AlertStatus.Close
                data_obj = hpcl_ceg_model.Interlock(**il_data)
                await data_obj.modify()

            # Close Alert
            query = f"bu='{bu}' AND sop_id='{sop_id}' AND sap_id='{sap_id}'"
            params = urdhva_base.queryparams.QueryParams()
            params.q = query
            alert = await hpcl_ceg_model.AlertsCreate.get_all(params)
            resp = alert.__dict__
            if resp.get('body'):
                # Decode the byte string to a normal string
                body_str = resp['body'].decode('utf-8')
                alert = json.loads(body_str)            
                al_data = alert["data"][0]
                al_data['alert_status'] = hpcl_ceg_enum.AlertStatus.Close
                data_obj = hpcl_ceg_model.Alerts(**al_data)
                await data_obj.modify()

            return True, {"message":"Alert Closed"}
        
        except Exception as e:
            logger.error(e)
            print(e)
            print(traceback.format_exc())
            return {"status": False, "message": str(e), "alert_data": None}
