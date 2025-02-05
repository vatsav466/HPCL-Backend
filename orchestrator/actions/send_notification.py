import os.path
import typing
import pytz
import aiofiles
import datetime
import traceback
import urdhva_base
from jinja2 import Template
from typing import Dict, List
import hpcl_ceg_model
import hpcl_ceg_enum
from utilities.interlock_template_mapping import (
    InterlockTemplateMapping,
    TemplateMapping
)
from camunda.external_task.external_task import (
    ExternalTask,
    TaskResult
)
import cache_gateway.cache_api_actions as cache_api_actions
import orchestrator.notification_manager.notification_factory as notification_factory

logger = urdhva_base.logger.Logger.getInstance("workflow_process-log")


class SendNotification:
    def __init__(self):
        self.alert_data = None
        self.params = None
        self.IST = pytz.timezone('Asia/Kolkata')
        self.roles_mapper = hpcl_ceg_model.RoleMaster
        self.update_alert = {}
        self.mail_recipients = []
        self.sms_recipients = []
        self.subject = ""
        self.body = ""
        self.sms = ""

    async def get_required_variables(self):
        """
        Returns a list of strings representing the required variables for the action.

        Returns:
            list: A list of strings representing the required variables.
        """
        return [
            "alert_id", "BU", "interlock_name", "interlock_id", "messagetype",
            "msg_subject", "mqofrole", "location_type", "location_device_id",
            "rolemailto", "alert_id", "escalationlevel_inmail", "sap_id", "escalationtime_inmail"
        ]

    async def process(self, params: typing.Dict):
        """
        Process the action.
        """
        self.params = params
        try:
            if not await self._load_and_validate_alert():
                return await self._handle_invalid_alert()

            await self._prepare_base_alert_data()
            await self._process_roles_and_users()
            await self._process_message_type()
            await self._send_notifications()
            await self._update_alert_status()
            return await self._create_task_result()

        except Exception as e:
            logger.error(f"Error during notification process: {str(e)}")
            logger.error(traceback.format_exc())
            return False, "Failed to process notification"

    async def _load_and_validate_alert(self) -> bool:
        """Load alert data and validate its existence"""
        alert_id = self.params.get("alert_id")
        print("alert_id --> ", alert_id)
        alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
        
        if alert_data:
            self.alert_data = alert_data.__dict__ if not isinstance(alert_data, dict) else alert_data
            return True
        return False

    async def _process_roles_and_users(self):
        """Process roles and users for notifications"""
        bu = self.params.get("BU")
        sap_id = self.alert_data.get("sap_id", "")
        message_type = self.params.get("messagetype")
        print("bu --> ", bu)
        print("sap_id --> ", sap_id)
        print("message_type --> ", message_type)
        # Get roles based on business unit and message type
        status, roles = await cache_api_actions.get_location_data(bu, sap_id)
        print("roles --> ", roles)
        self.base_alert_data["email"] = "keerthesrep@algofusiontech.com"
        roles["dealer_email"] = "keerthesrep@algofusiontech.com"
        roles["dealer_phone"] = ""
        # Prepare recipients and message content
        await self._prepare_recipients(roles)
        await self._prepare_message_content(bu, message_type)

    async def _prepare_recipients(self, users: List[Dict]):
        """Prepare email and SMS recipients"""
        print("users --> ", users)
        # for user in users:
        #     print("user ", user)
        if users.get("dealer_email"):
            self.mail_recipients.append(users["dealer_email"])
        if users.get("dealer_phone"):
            self.sms_recipients.append(users["dealer_phone"])
                
        self.mail_recipients = list(dict.fromkeys(self.mail_recipients))
        self.sms_recipients = list(dict.fromkeys(self.sms_recipients))

    async def _prepare_message_content(self, bu: str, message_type: str):
        """Prepare message content (subject, body, and SMS)"""
        template_data = {
            **self.base_alert_data,
            "bu": bu,
            "message_type": message_type,
            "alert_details": self.alert_data.get("msg", ""),
            "status": self.update_alert.get("status", ""),
            "template": eval(f"TemplateMapping.{message_type.upper()}.value")
        }
        
        # Load templates based on message type and business unit
        templates = await self._load_message_templates(template_data['template'])
        print("templates --> ", dir(templates))
        # Render templates
        self.subject = Template(self.params.get("msg_subject")).render(**template_data)
        self.body = Template(templates["body"]).render(**template_data)
        # self.sms = Template(templates["sms"]).render(**template_data)

    async def _load_message_templates(self, template_name: str) -> Dict[str, str]:
        """Load message templates safely."""
        message_type = self.params.get("messagetype", "").upper()

        template_value = getattr(TemplateMapping, message_type, None)
        template = template_value.value if template_value else ""
        print("template --> ", template)
        interlock_value = getattr(InterlockTemplateMapping, template_name.upper(), None)
        body = await self.read_template(interlock_value.value) if interlock_value else ""
        return {"template": template, "body": body}

    async def _handle_invalid_alert(self):
        """Handle case when alert is not found"""
        return False, "Alert not found"
    
    async def _should_skip_notification(self) -> bool:
        """Check if notification should be skipped based on message type and status"""
        message_type = self.params.get("message_type")
        logger.info(f"self.alert_data1: {self.alert_data}")
        active_msg = self.alert_data.get("active", False)
        closed_msg = self.alert_data.get("closed", False)
        
        if active_msg and message_type == "active":
            return True
        if closed_msg and message_type == "resolved":
            return True
        return False

    async def _prepare_base_alert_data(self):
        """Prepare basic alert data for notification"""
        logger.info(f"self.alert_data: {self.alert_data}")
        self.base_alert_data = {
            "alert_id": self.params.get("alert_id"),
            "interlock_name": await self._get_interlock_name(),
            "plant_id": self.alert_data.get("sap_id", ''),
            "plant_location": self.alert_data["location_name"][:30],
            "portal_link": "https://ceg.hpcl.co.in",
            "user": self.params.get("user") or '',
            "asset_name": self.alert_data["device_type"],
            "asset_id": self.alert_data.get("device_name", self.alert_data["location_name"]) # this should be location_id
        }
        return self.base_alert_data

    async def _get_interlock_name(self) -> str:
        """Get interlock name from alert data"""
        return self.alert_data.get('sopName', self.alert_data.get("interlock_name", self.alert_data.get('msg', '')))

    async def _process_escalation(self):
        """Handle escalation type notifications"""
        bu = self.params.get("BU")
        self.base_alert_data["action_msg"] = "ESCALATED"
        self.update_alert["status"] = "Escalated"
        self.update_alert["isEscalated"] = True

    async def _process_active(self):
        """Handle active type notifications"""
        print("_process_active")
        self.base_alert_data["action_type"] = hpcl_ceg_enum.AlertActionType.Active.value
        self.base_alert_data["action_msg"] = self.params.get("msg_subject")

    async def _process_notify(self):
        """Handle notify type notifications"""
        justify = self.params.get("justify", False)
        await self._process_approval("REQUEST", justify)

    async def _process_reject(self):
        """Handle reject type notifications"""
        await self._process_approval("REQUEST REJECTED", False)

    async def _process_justified(self):
        """Handle justified type notifications"""
        await self._process_approval("REQUEST", True)

    async def _process_resolved(self):
        """Handle resolved type notifications"""
        self.base_alert_data.update({
            "action": "CLOSED",
            "reason_closure": "InterLock OK",
            "user": "CEG",
            "action_msg": "CLOSED"
        })
        self.update_alert["status"] = "closed"

    async def _process_approval(self, action_prefix: str, justify: bool):
        """Process approval-related notifications"""
        bu = self.params.get("BU")
        user = self.params.get("user", "").split('@')[0].strip()
        
        action = f"{action_prefix} {'APPROVED' if not justify else ''}"
        self.base_alert_data["action"] = action
        self.base_alert_data["action_msg"] = f"{action} by {user}"

        self.update_alert["status"] = "Pending Approval" if justify else "Request Approved"
    

    async def _process_message_type(self):
        """Process notification based on message type"""
        message_type = self.params.get("messagetype")

        processors = {
            "escalation": self._process_escalation,
            "escalate": self._process_escalation,
            "active": self._process_active,
            "notify": self._process_notify,
            "reject": self._process_reject,
            "justified": self._process_justified,
            "resolved": self._process_resolved
        }
        processor = processors.get(message_type)  # Retrieve the function
        if processor:
            print(f"Executing processor for message_type: {message_type}")
            await processor()  # Call the function asynchronously
        else:
            print(f"Unknown message type: {message_type}")

    async def _send_notifications(self):
        """Send notifications based on business unit and message type"""
        bu = self.params.get("BU").upper()
        sop_id = self.alert_data.get('sop_id')
        print("before _send_notifications_with_sms")
        await self._send_notifications_with_sms(bu)

    async def _send_notifications_with_sms(self, bu: str):
        """Send notifications with SMS based on business unit"""
        message_type = self.params.get("messagetype")
        print("message_type --> ", message_type)
        if message_type == "active":
            await self._send_active_notification()
        elif message_type == "resolved":
            await self._send_resolved_notification()
        elif message_type == 'Resolved':
            await self._send_other_notification()
        else:
            await self._send_standard_notification()

    async def _send_active_notification(self):
        """Send notifications for LPG/TAS active messages"""
        if self.params.get("dealer_phone"):
            await notification_factory.get_notification_module(module_type="sms")
        else:
            notification_module = await notification_factory.get_notification_module(module_type="email")
            res = await notification_module.publish_message(recipients=self.mail_recipients, subject=self.subject, body=self.body, html_content=True)
        return res

    async def _send_resolved_notification(self):
        """Send notifications for LPG/TAS resolved messages"""
        if self.params("dealer_phone"):
            await notification_factory.get_notification_module(
                module_type="sms"
            )
        else:
            await notification_factory.get_notification_module(
                module_type="email"
            ).publish_message(self.mail_recipients, self.subject, self.body)

    async def _send_other_notification(self):
        """Send notifications for other LPG/TAS messages"""
        if self.params("dealer_phone"):
            await notification_factory.get_notification_module(
                module_type="sms"
            )
        else:
            await notification_factory.get_notification_module(
                module_type="email"
            ).publish_message(self.mail_recipients, self.subject, self.body)

    async def _send_standard_notification(self):
        """Send standard notifications"""
        if self.params("dealer_phone"):
            await notification_factory.get_notification_module(
                module_type="sms"
            )
        else:
            await notification_factory.get_notification_module(
                module_type="email"
            ).publish_message(self.mail_recipients, self.subject, self.body)

    async def _update_alert_status(self):
        """Update alert status in database"""
        alert_id = self.params.get("alert_id")
        if self.params.get("escalationlevel_inmail"):
            self.update_alert["action_type"] = self.base_alert_data.get("action_type")
            self.update_alert["action_msg"] = self.base_alert_data["action_msg"]
            self.update_alert['last_escalated_to'] = self.params.get("rolemailto").split(',')
            self.update_alert['assigned_user_roles'] = self.params.get("mqofrole").split(',')
            self.update_alert['last_mailed_to'] = [self.base_alert_data.get("email")] if isinstance(self.base_alert_data.get("email"), str) else self.base_alert_data.get("email")
        else:
            self.update_alert["action_type"] = self.base_alert_data.get("action_type")
            self.update_alert["action_msg"] = self.base_alert_data.get("action_msg")
            self.update_alert['last_notified_to'] = self.params.get("rolemailto").split(',')
            self.update_alert['assigned_user_roles'] = self.params.get("mqofrole").split(',')
            self.update_alert['last_mailed_to'] = self.base_alert_data.get("email")
        alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__
        alert_history = alert_data.get("alert_history") if alert_data.get("alert_history") else []
        # Append the new update to alert history
        alert_history.append(self.update_alert)
        # Assign the updated history back to the alert data
        alert_data["alert_history"] = alert_history
        alert_data["last_escalated_to"] = self.update_alert['last_escalated_to']
        alert_data["assigned_user_roles"] = self.update_alert['assigned_user_roles']
        alert_data["last_mailed_to"] = self.update_alert['last_mailed_to']
        await hpcl_ceg_model.Alerts(**alert_data).modify()

    async def read_template(self, filename: str) -> str:
        """Read template file asynchronously."""
        try:
            filepath = os.path.join(urdhva_base.settings.template_path, filename)
            async with aiofiles.open(filepath, 'r') as f:
                return await f.read()
        except FileNotFoundError:
            logger.error(f"Template file not found: {filename}")
            return ""

    async def handle_task_notification(self, params: typing.Dict):
        """Main entry point for handling task notifications"""
        # handler = SendNotification(task)
        return await self.process(params)

    async def _create_task_result(self):
        if "_sa_instance_state" in self.alert_data.keys():
            del self.alert_data["_sa_instance_state"]
        return True, {"alert_id": self.params['alert_id']}
