import urdhva_base
import re
import json
import httpx
import datetime
import hpcl_ceg_model
from jinja2 import Template
import utilities.helpers as helpers
import orchestrator.alerting.ro_alert as ro_alert
import orchestrator.alerting.va_alert as va_alert
import orchestrator.alerting.vts_alert as vts_alert
import orchestrator.alerting.tas_alert as tas_alert
import orchestrator.alerting.lpg_alert as lpg_alert
import orchestrator.analytics.va_analysis as va_analysis
import orchestrator.alerting.emlock_alert as emlock_alert
from orchestrator.notification_manager.notify_email import *


async def create_alert(alert_data, camunda_url=urdhva_base.settings.camunda_url):
    """
    Create an alert based on input alert data. This function delegates the actual creation of the alert to the specific
    alert manager (e.g. ROAlertManager, VAAlertManager, etc.) based on the 'alert_type' field in the input alert data.

    Parameters:
        alert_data (dict): A dictionary containing the data to create the alert.
        camunda_url (String): Camunda Connection String.

    Returns:
        dict: A dictionary containing the status, message and the created alert document.
    """
    # print("into create alert", alert_data)
    alert_type = alert_data['alert_type']
    return await eval(f"{alert_type.lower()}_alert.{alert_type}AlertManager").create_bu_alert(alert_data, camunda_url)


async def close_alert(alert_data):
    """
    Close an alert based on input alert data. This function delegates the actual closure of the alert to the specific alert manager (e.g. ROAlertManager, VAAlertManager, etc.) based on the 'alert_type' field in the input alert data.

    Parameters:
        alert_data (dict): A dictionary containing the data to close the alert.

    Returns:
        dict: A dictionary containing the status, message and the closed alert document.
    """
    # print("alert_data for close alert", alert_data)
    alert_type = alert_data['alert_type']
    return await eval(f"{alert_type.lower()}_alert.{alert_type}AlertManager").close_bu_alert(alert_data)


async def close_va_alert(alert_data, input_data):
    """
    Args:
        alert_data:
        input_data:

    Returns:
    """
    if not isinstance(alert_data, dict):
        alert_data = alert_data.__dict__
    if not input_data.get("doc_link", ""):
        input_data["doc_link"] = await get_doc_link_from_alert_history(alert_data)
    action_code = "VALID"
    if input_data.get("action_type") == 'InvalidAlert':
        action_code = 'INVALID'
    if input_data.get("action_type") == 'FalseAlert':
        action_code = 'FALSE'
    params = {
        "AlarmId": alert_data['external_id'],
        "Status": "CLOSED",
        "AcknowledgedBy": input_data.get("acknowledged_by", "1234"),
        "ActionCode": action_code,
        "ActionReason": input_data.get("rca_reason", "Other"),
        "ActionCategory": input_data.get("category", "Others"),
        "doc_link": input_data.get("doc_link", ""),
        "ActionDescription": input_data.get("action_description", "")
    }
    return await va_analysis.close_va_alerts(params)


async def get_doc_link_from_alert_history(alert_data):
    """

    Args:
        alert_data:

    Returns:

    """
    for alert_history in alert_data.get("alert_history", []):
        if alert_history.get("doc_link", ""):
            return alert_history.get("doc_link", "")
    return ""


def read_template(filename, data):
    with open(filename, 'r') as f:
        html_string = f.read()
    j2_template = Template(html_string)
    body=j2_template.render(data)
    return body


async def va_alert_closer(alert_data, input_data):
    """

    Args:
        alert_data:
        input_data:

    Returns:

    """
    resp = await close_va_alert(alert_data, input_data)
    if not isinstance(alert_data, dict):
        alert_data = alert_data.__dict__
    close_alert_data = {}
    close_alert_data['alert_type'] = alert_data['alert_section']
    close_alert_data['bu'] = alert_data['bu']
    close_alert_data['alert_id'] = alert_data['id']
    close_alert_data['interlock_id'] = alert_data['interlock_id']
    await close_alert(close_alert_data)
    print(f"VA Alert resp {resp}")


async def vts_alert_closer(alert_data, input_data):
    """

    Args:
        alert_data:
        input_data:

    Returns:

    """
    # resp = await close_va_alert(alert_data, input_data)
    if not isinstance(alert_data, dict):
        alert_data = alert_data.__dict__
    close_alert_data = {}
    close_alert_data['alert_type'] = alert_data['alert_section']
    close_alert_data['bu'] = alert_data['bu']
    close_alert_data['alert_id'] = alert_data['id']
    close_alert_data['interlock_id'] = alert_data['interlock_id']
    await close_alert(close_alert_data)
    data = {}
    data['interlock_name'] = alert_data['interlock_name']
    data['asset_name'] = "violation_type"
    data['asset_id'] = ""
    data['plant_location'] = alert_data['location_name']
    data['plant_id'] = alert_data['sap_id']
    data['opened_time'] = alert_data['created_at'].strftime('%d-%m-%Y %H:%M:%S')
    data['user'] = 'Novex User'
    data['reason_closure'] = input_data.get("action_description", "")
    data['portal_link'] = "https://ceg.hpcl.co.in"
    notify_email = NotifyEMail()
    notify_email.publish_message(
        **{
            'to_emails': ['venu@algofusiontech.com', 'santoshkumar.s@algofusiontech.com'],
            'subject': f"VTS Alert Closed FOR {close_alert_data['bu']} BU And {alert_data['sap_id']} SAP ID",
            'body': read_template("/opt/ceg/algo/orchestrator/notification_templates/interlock_alert_closure.html", data=data)
        }
    )
    print(f"VTS Alert Closed")


class AlertAction:
    @classmethod
    async def update_alert_data(cls, input_data):
        """
        Function to update alert data, Either reject or approve or justify or override
        :param input_data:
        :return:
        """
        print("input_data --> ", input_data)
        function_map = {"Justification": "justify_alert", "Rejected": "reject_alert", "Approved": "approve_alert",
                        "Override": "override_alert", "interLockOk": "interlock_ok_alert", 
                        "excApprovalTimeExp": "exc_approval_time_exp_alert", "Message": "message_alert",
                        "Raised": "raised_alert", "Cancelled": "cancel_alert", "Allocated": "allocate_alert",
                        "SentToSap": "sent_to_sap_alert", "OrderPlaced": "order_placed_alert",
                        "Created": "created_alert", "Tripped": "tripped_alert", "VTS": "vts_alert",
                        "AcceptClose": "accept_close", "InvalidAlert": "invalid_alert", "FalseAlert": "false_alert", "ValidAlert": "valid_alert"}
        event_tag_map = {"Justification": "is_justify", "Approved": "is_approved", "AcceptClose": "accept", "InvalidAlert": "invalid"}
        alert_id = input_data['alert_id']
        if input_data['doc_link']:
            input_data['doc_link'] = await helpers.get_doc_link(input_data['doc_link'])
        input_data.update({"event_tags": {event_tag_map.get(input_data['action_type'], "is_approved"): True}})
        try:
            alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
        except Exception as e:
            print("Exception in getting alert data:%s" % e)
            return False, "Provided alert id is not valid"

        # Validating whether user has access permissions for the provided action
        # status, resp, email = await cls.verify_user_access_permissions(alert_data.bu, alert_data.sap_id,
        #                                                                input_data['action_type'])
        # if not status:
        #     return status, resp

        # This creates a regular expression pattern to match anything within < and >,
        # which includes HTML tags like <div>, <span>, <br>, etc.
        # The .*? ensures a non-greedy match, meaning it will stop at the first closing >
        # rather than consuming everything until the last >
        condition = re.compile('<.*?>')
        input_data["action_msg"] = re.sub(condition, '', input_data["action_msg"])

        # get the function name
        function_name = function_map.get(input_data['action_type'], None)
        if function_name:
            await cls.update_alert_history(input_data, alert_data)
            # call the function
            # return await getattr(cls, function_name)(input_data, alert_data)

            # For testing added below 3 lines
            meg_resp = await getattr(cls, function_name)(input_data, alert_data)
            # if input_data.get("alert_section", "") == 'VA':
            # if input_data.get("alert_section", "") == 'VA' and input_data.get("action_type", "") not in ["Justification", "Rejected"]:
            if input_data.get("alert_section", "") == 'VA' and input_data.get("action_type", "") in ["Approved"]:
                await va_alert_closer(alert_data, input_data)

            if input_data.get("alert_section", "") == 'VTS' and input_data.get("action_type", "") in ["Approved"]:
                await vts_alert_closer(alert_data, input_data)
            return meg_resp
        return False, "Alert action is not valid"

    @classmethod
    async def update_alert_history(cls, input_data, alert_data):
        """
        Function to update alert data, Either reject or approve or justify or override
        :param input_data:
        :param alert_data:
        :return:
        """
        # Todo:- here we have to write all the generic functionality like updating the alert data,
        #  history, fetching users, roles, ...
        # print("input_data for alert--> ", input_data)
        alert_history = alert_data.get('alert_history', []) if isinstance(alert_data, dict) else getattr(alert_data, 'alert_history', [])
        # alert_history = alert_data.alert_history
        # print("alert_history --> ", alert_history)
        # allocated_time = alert_data.updated_at
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__
        if isinstance(alert_data, dict):
            allocated_time = alert_data.get('updated_at', datetime.datetime.now(datetime.timezone.utc))
        else:
            allocated_time = alert_data.updated_at if hasattr(alert_data, 'updated_at') else datetime.datetime.now(datetime.timezone.utc)
        
        if alert_history and alert_history[-1].get("processed_time"):
            allocated_time = alert_history[-1]["processed_time"]
        processed_time = datetime.datetime.now(datetime.timezone.utc)
        event_tags = input_data.get("event_tags", {})
        if not event_tags:
            event_tags = {}
        # Append the updated alert history with the converted datetime strings
        alert_history.append({"allocated_time": allocated_time.isoformat() if isinstance(allocated_time, datetime.datetime) else allocated_time,
                            "processed_time": processed_time.isoformat(), "action_type": input_data["action_type"],
                            "action_msg": input_data["action_msg"], "mail_sent_to": "",
                            "ims_datetime": input_data.get("ims_datetime", ""),
                            "prod_reqd_dt": input_data.get("prod_reqd_dt", ""),
                            "doc_link": input_data.get("doc_link", ""),
                            "atr_uploaded": event_tags.get("is_atr_uploaded", False),
                            "maintenance_exception": event_tags.get("is_maintenance_exception", False), 
                            "revocation": event_tags.get("is_revocation", False),
                            "no_exception": event_tags.get("no_exception", False),
                            "is_approved": event_tags.get("is_approved", False),
                            "is_exc_approval_time_exp": event_tags.get("is_exc_approval_time_exp", False),
                            "is_raised": event_tags.get("is_raised", False),
                            "is_cancelled": event_tags.get("is_cancelled", False),
                            "is_allocated": event_tags.get("is_allocated", False),
                            "is_sent_to_sap": event_tags.get("is_sent_to_sap", False),
                            "is_order_placed": event_tags.get("is_order_placed", False),
                            "is_created": event_tags.get("is_created", False),
                            "is_r1_swipe": event_tags.get("is_r1_swipe", False),
                            "is_r2_swipe": event_tags.get("is_r2_swipe", False),
                            "is_r3_swipe": event_tags.get("is_r3_swipe", False),
                            "is_vts": event_tags.get("is_vts", False),
                            "is_delivered": event_tags.get("is_delivered", False),
                            "is_tripped": event_tags.get("is_tripped", False),
                            "is_justify": event_tags.get("is_justify", False)     
                        })
        # print("alert_history before update --> ", alert_history)
        # Modify the alert with the updated alert_history
        # Handle alert_data based on whether it is a dictionary or object
        alert_id = alert_data.get('id') if isinstance(alert_data, dict) else getattr(alert_data, 'id', None)
        
        if not alert_id:
            raise ValueError("Alert data does not have an 'id' field.")

        # Modify the alert with the updated alert_history
        await hpcl_ceg_model.Alerts(**{"id": alert_id, "alert_history": alert_history}).modify()
        # await hpcl_ceg_model.Alerts(**{"id": alert_data.id, "alert_history": alert_history}).modify()

    @classmethod
    def get_exception_message(cls, exception):
        """
        Function to get the exception message
        :param exception:
        :return:
        """
        exception_msg = {}
        if not exception:
            return exception_msg
        key_map = {"is_maintenance_exception": {"name": "isMaintenanceException", "type": "Boolean"},
                   "is_atr_uploaded": {"name": "isAtrUploaded", "type": "Boolean"},
                   "is_revocation": {"name": "isRevocation", "type": "Boolean"},
                   "no_exception": {"name": "noException", "type": "Boolean"},
                   "is_approved": {"name": "approved", "type": "Boolean"},
                   "is_exc_approval_time_exp": {"name": "isExcApprovalTimeExp", "type": "Boolean"},
                   "is_raised": {"name": "raised", "type": "Boolean"},
                   "is_cancelled": {"name": "cancelled", "type": "Boolean"},
                   "is_allocated": {"name": "allocated", "type": "Boolean"},
                   "is_sent_to_sap": {"name": "sentToSAP", "type": "Boolean"},
                   "is_order_placed": {"name": "orderPlaced", "type": "Boolean"},
                   "is_created": {"name": "created", "type": "Boolean"},
                   "is_r1_swipe": {"name": "r1Swipe", "type": "Boolean"},
                   "is_r2_swipe": {"name": "r2Swipe", "type": "Boolean"},
                   "is_r3_swipe": {"name": "r3Swipe", "type": "Boolean"},
                   "is_vts": {"name": "vts", "type": "Boolean"},
                   "is_delivered": {"name": "delivered", "type": "Boolean"},
                   "is_tripped": {"name": "tripped", "type": "Boolean"},
                   "is_justify": {"name": "justify", "type": "Boolean"}
                   }
        return {value['name']: {'type': 'Boolean', 'value': exception.get(key, False)}
                for key, value in key_map.items()}

    @classmethod
    async def publish_to_camunda(cls, input_data, alert_data, action_type, msg=None):
        """
        Function to generate camunda message
        :param input_data:
        :param alert_data:
        :param action_type:
        :param msg:
        :return:
        """
        process_variables = cls.get_exception_message(input_data.get("event_tags", {}))
        process_variables.update({"override_days": {"type": "String", "value": input_data.get('days', '')},
                                  "msg": {"type": "String", "value": msg},
                                  "action_type": {"type": "String", "value": action_type}})
        print("process_variables: ", process_variables)
        messaged_data = {
            "messageName": action_type,
            "businessKey": alert_data.unique_id,
            "processVariables": process_variables
        }
        # print("messaged_data: ", messaged_data)
        # Posting data to camunda
        url = helpers.get_camunda_url(
            bu=alert_data.bu,
            sap_id=alert_data.sap_id,
            alert_section=alert_data.alert_section
        )
        url = urdhva_base.settings.camunda_url + "/engine-rest/message"
        r = httpx.post(url, headers={'Content-Type': 'application/json'}, json=messaged_data, verify=False)

        if int(r.status_code / 100) != 2:
            print(f"Error while sending message to camunda: {r.status_code} - {r.text}")
        else:
            print("Message sent to camunda")
        return True, "Successfully sent message to camunda"

    @classmethod
    async def verify_user_access_permissions(cls, bu, sap_id, action_type):
        """
        Function to verify whether the user has access for the provided action
        :return: <bool> <string>
        """
        session_details = urdhva_base.context.context.get("rpt", {})
        email = session_details.get('email', '')
        # todo:- Need to update whether user has access or not for this particular BU, sapId and ActionType
        return True, "", email

    @classmethod
    async def reject_alert(cls, input_data, alert_data):
        """
        Function to reject an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "Reject")

    @classmethod
    async def approve_alert(cls, input_data, alert_data):
        """
        Function to approve an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "Approved")

    @classmethod
    async def justify_alert(cls, input_data, alert_data):
        """
        Function to justify an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        if input_data.get("alert_section","") in ["TAS"] and input_data.get("days",0):
            # Add 30 days to the current time
            maintenance_time = helpers.get_time_stamp_by_delta(days=input_data.get("days",0), 
                                            with_month_start_day=False, 
                                            ascending=True,
                                            date_time_format=None).strftime("%Y-%m-%dT%H:%M:%S")
            alert_id = alert_data.get('id') if isinstance(alert_data, dict) else getattr(alert_data, 'id', None)
            if not alert_id:
                raise ValueError("Alert data does not have an 'id' field.")

            await hpcl_ceg_model.Alerts(**{"id": alert_id, "maintenance_time": maintenance_time}).modify()
        return await cls.publish_to_camunda(input_data, alert_data, "Justification")

    @classmethod
    async def override_alert(cls, input_data, alert_data):
        """
        Function to override an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "Override")

    @classmethod
    async def message_alert(cls, input_data, alert_data):
        """
        Function to override an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "Message")

    @classmethod
    async def interlock_ok_alert(cls, input_data, alert_data):
        """
        Function to override an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "interLockOk")
    
    @classmethod
    async def exc_approval_time_exp_alert(cls, input_data, alert_data):
        """
        Function to override an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "excApprovalTimeExp")

    @classmethod
    async def raised_alert(cls, input_data, alert_data):
        """
        Function to raise an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "Raised")

    @classmethod
    async def cancel_alert(cls, input_data, alert_data):
        """
        Function to cancel an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "Cancelled")

    @classmethod
    async def allocate_alert(cls, input_data, alert_data):
        """
        Function to allocate an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "Allocated")

    @classmethod
    async def sent_to_sap_alert(cls, input_data, alert_data):
        """
        Function to allocate an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "SentToSap")

    @classmethod
    async def order_placed_alert(cls, input_data, alert_data):
        """
        Function to allocate an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "OrderPlaced")

    @classmethod
    async def created_alert(cls, input_data, alert_data):
        """
        Function to allocate an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "Created")

    @classmethod
    async def delivered_alert(cls, input_data, alert_data):
        """
        Function to allocate an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "Delivered")

    @classmethod
    async def r1_swipe_alert(cls, input_data, alert_data):
        """
        Function to R1 Swipe an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "R1Swipe")

    @classmethod
    async def r2_swipe_alert(cls, input_data, alert_data):
        """
        Function to R2 Swipe an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "R2Swipe")

    @classmethod
    async def r3_swipe_alert(cls, input_data, alert_data):
        """
        Function to R3 Swipe an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "R3Swipe")

    @classmethod
    async def accept_close(cls, input_data, alert_data):
        """
                Function to Accept and Close an alert
                :param input_data:
                :param alert_data:
                :return:
                """
        return await cls.publish_to_camunda(input_data, alert_data, "AcceptClose")

    @classmethod
    async def invalid_alert(cls, input_data, alert_data):
        """
                Function to Accept and Close an alert
                :param input_data:
                :param alert_data:
                :return:
                """
        return await cls.publish_to_camunda(input_data, alert_data, "Invalid")

    @classmethod
    async def valid_alert(cls, input_data, alert_data):
        """
                Function to Accept and Close an alert
                :param input_data:
                :param alert_data:
                :return:
                """
        return await cls.publish_to_camunda(input_data, alert_data, "Valid")

    @classmethod
    async def false_alert(cls, input_data, alert_data):
        """
                Function to Accept and Close an alert
                :param input_data:
                :param alert_data:
                :return:
                """
        return await cls.publish_to_camunda(input_data, alert_data, "FalseAlert")
    
    @classmethod
    async def tripped_alert(cls, input_data, alert_data):
        """
        Function to R4 Swipe an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "Tripped")

    @classmethod
    async def vts_alert(cls, input_data, alert_data):
        """
        Function to VTS an alert
        :param input_data:
        :param alert_data:
        :return:
        """
        return await cls.publish_to_camunda(input_data, alert_data, "VTS")
