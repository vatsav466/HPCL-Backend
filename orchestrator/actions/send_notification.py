from typing import Dict, List, Tuple
import datetime
import pytz
import pandas as pd
import json
import pika
from jinja2 import Template
from api_manager import dnc_schema_model

class SendNotification:
    def __init__(self, task):
        """Initialize handler with Camunda external task"""
        self.task = task
        self.alert_data = None
        self.IST = pytz.timezone('Asia/Kolkata')
        self.roles_mapper = Roles.RoleMapper() #TODO : NEED TO WRITE SEPERATE BLOCKS FOR EMAIL AND SMS BASED ON ROLES
        self.update_alert = {}
        self.mail_recipients = []
        self.sms_recipients = []
        self.subject = ""
        self.body = ""
        self.sms = ""
        

    async def process(self):
        """Main processing method that orchestrates the notification flow"""
        try:
            if not await self._load_and_validate_alert():
                return await self._handle_invalid_alert()
                
            if self._should_skip_notification():
                return await self.task.complete()
                
            self._prepare_base_alert_data()
            await self._process_roles_and_users()
            self._process_message_type()
            await self._send_notifications()
            await self._update_alert_status()
            
            return self._create_task_result()
        
        except Exception as e:
            # Log the error or add appropriate error handling
            return self.task.failure(
                error_message="Failed to process notification",
                error_details=str(e),
                max_retries=3,
                retry_timeout=5000
            )

    

    async def _load_and_validate_alert(self) -> bool:
        """Load alert data and validate its existence"""
        alert_id = self.task.get_variable("alertid")
        alert_data = await dnc_schema_model.Alerts.get(alert_id)
        
        if alert_data:
            self.alert_data = alert_data.__dict__ if not isinstance(alert_data, dict) else alert_data
            return True
        return False

    async def _process_roles_and_users(self):
        """Process roles and users for notifications"""
        bu = self.task.get_variable("BU")
        sap_id = self.alert_data.get("plant_id", "")
        message_type = self.task.get_variable("messagetype")
        
        # Get roles based on business unit and message type
        roles = await self._get_roles(bu, sap_id)
        # Prepare recipients and message content
        await self._prepare_recipients(roles)
        await self._prepare_message_content(bu, message_type)


    async def _get_roles(self, bu: str, sap_id: str) -> List[Dict]:
        """Get users based on dynamically generated Redis key using BU, sap_id, and role"""
        roles_key = "roles"  # Assuming all roles data is stored under a single key "roles"
        redis_client = await zolix_base.redispool.get_redis_connection()
        all_roles_data = await redis_client.hgetall(roles_key)
        
        # Filter users based on the dynamic key format
        matching_users = []
        for role_key, role_data in all_roles_data.items():
            # Generate the expected key format
            expected_key = f"{bu}_{sap_id}"
            if role_key.startswith(expected_key):
                user_data = eval(role_data)  # Convert stored JSON string to dictionary if needed
                matching_users.append({
                    "email": user_data.get("email"),
                    "phone": user_data.get("phone")
                })
        
        return matching_users

    async def _prepare_recipients(self, users: List[Dict]):
        """Prepare email and SMS recipients"""
        for user in users:
            if user.get("email"):
                self.mail_recipients.append(user["email"])
            if user.get("phone"):
                self.sms_recipients.append(user["phone"])
                
        self.mail_recipients = list(dict.fromkeys(self.mail_recipients))
        self.sms_recipients = list(dict.fromkeys(self.sms_recipients))


    async def _prepare_message_content(self, bu: str, message_type: str):
        """Prepare message content (subject, body, and SMS)"""
        template_data = {
            **self.base_alert_data,
            "bu": bu,
            "message_type": message_type,
            "alert_details": self.alert_data.get("msg", ""),
            "status": self.update_alert.get("status", "")
        }
        
        # Load templates based on message type and business unit
        templates = await self._load_message_templates(bu, message_type)
        
        # Render templates
        self.subject = Template(templates["subject"]).render(**template_data)
        self.body = Template(templates["body"]).render(**template_data)
        self.sms = Template(templates["sms"]).render(**template_data)


    async def _load_message_templates(self, bu: str, message_type: str) -> Dict[str, str]:
        """Load message templates from configuration or database"""
        # This would typically load from a template store or database
        # For now, returning basic templates
        return {
            "subject": "{{ bu }} Alert: {{ action_msg }} - {{ interlock_name }}",
            "body": """
                Alert Details for {{ plant_location }}
                Alert ID: {{ alert_id }}
                Status: {{ action_msg }}
                Time: {{ date_time }}
                Details: {{ alert_details }}
                """,
            "sms": "{{ bu }} Alert: {{ action_msg }} - {{ interlock_name }} at {{ plant_location }}"
        }


    async def _handle_invalid_alert(self):
        """Handle case when alert is not found"""
        return self.task.failure(
            error_message="task failed",
            error_details="Alert not found",
            max_retries=3,
            retry_timeout=5000
        )
    
    async def _should_skip_notification(self) -> bool:
        """Check if notification should be skipped based on message type and status"""
        message_type = self.task.get_variable("messagetype")
        active_msg = self.alert_data.get("active", False)
        closed_msg = self.alert_data.get("closed", False)
        
        if active_msg and message_type == "active":
            return True
        if closed_msg and message_type == "resolved":
            return True
        return False

    async def _prepare_base_alert_data(self):
        """Prepare basic alert data for notification"""
        curr_time = datetime.datetime.now(self.IST).strftime('%d-%m-%Y %H:%M:%S')
        opened_time = datetime.datetime.fromtimestamp(
            self.alert_data['created'], self.IST).strftime('%d-%m-%Y %H:%M:%S')
        
        self.base_alert_data = {
            "alert_id": self.task.get_variable("alertid"),
            "interlock_name": self._get_interlock_name(),
            "plant_id": self.alert_data.get("sapId", ''),
            "plant_location": self.alert_data["unitName"][:30],
            "date_time": curr_time,
            "opened_time": opened_time,
            "portal_link": "https://ceg.hpcl.co.in",
            "user": self.task.get_variable("user") or '',
            "asset_name": self.alert_data["deviceType"],
            "asset_id": self.alert_data.get("deviceName", self.alert_data["unit"])
        }

    async def _get_interlock_name(self) -> str:
        """Get interlock name from alert data"""
        return self.alert_data.get('sopName', 
            self.alert_data.get("interlockname", self.alert_data.get('msg', '')))

    async def _process_message_type(self):
        """Process notification based on message type"""
        message_type = self.task.get_variable("messagetype")
        processors = {
            "escalation": self._process_escalation,
            "escalate": self._process_escalation,
            "active": self._process_active,
            "notify": self._process_notify,
            "reject": self._process_reject,
            "justified": self._process_justified,
            "resolved": self._process_resolved
        }
        
        processor = processors.get(message_type)
        if processor:
            processor()

    async def _process_escalation(self):
        """Handle escalation type notifications"""
        bu = self.task.get_variable("BU")
        self.base_alert_data["action_msg"] = "ESCALATED"
        
        self.update_alert["status"] = "Escalated"
        self.update_alert["isEscalated"] = True

    async def _process_active(self):
        """Handle active type notifications"""
        self.base_alert_data["action_msg"] = "ACTIVE"

    async def _process_notify(self):
        """Handle notify type notifications"""
        justify = self.task.get_variable("justify", False)
        self._process_approval("REQUEST", justify)

    async def _process_reject(self):
        """Handle reject type notifications"""
        self._process_approval("REQUEST REJECTED", False)

    async def _process_justified(self):
        """Handle justified type notifications"""
        self._process_approval("REQUEST", True)

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
        bu = self.task.get_variable("BU")
        user = self.task.get_variable("user", "").split('@')[0].strip()
        
        action = f"{action_prefix} {'APPROVED' if not justify else ''}"
        self.base_alert_data["action"] = action
        self.base_alert_data["action_msg"] = f"{action} by {user}"
        
        
        self.update_alert["status"] = "Pending Approval" if justify else "Request Approved"

    
    async def _send_notifications(self):
        """Send notifications based on business unit and message type"""
        bu = self.task.get_variable("BU").upper()
        sop_id = self.alert_data.get('sopId')
        
        await self._send_notifications_with_sms(bu)

    async def _send_notifications_with_sms(self, bu: str):
        """Send notifications with SMS based on business unit"""
        message_type = self.task.get_variable("messagetype")
        
        
        if message_type == "active":
            await self._send_lpg_tas_active_notification()
        elif message_type == "resolved":
            await self._send_lpg_tas_resolved_notification()
        elif message_type == 'Resolved':
            await self._send_lpg_tas_other_notification()
        else:
            await self._send_standard_notification()

    async def _send_lpg_tas_active_notification(self):
        """Send notifications for LPG/TAS active messages"""
        await self.roles_mapper.sendEmailWithSMS(
            self.mail_recipients, self.sms_recipients,
            self.subject, self.body, self.sms, True
        )

    async def _send_lpg_tas_resolved_notification(self):
        """Send notifications for LPG/TAS resolved messages"""
        sent_sms = self.alert_data.get('sentsms', '').split(",")
        await self.roles_mapper.sendEmailWithSMS(
            self.mail_recipients, sent_sms,
            self.subject, self.body, self.sms, True
        )

    async def _send_lpg_tas_other_notification(self):
        """Send notifications for other LPG/TAS messages"""
        await self.roles_mapper.sendEmailWithSMS(
            self.mail_recipients, [],
            self.subject, self.body, self.sms, True
        )

    async def _send_standard_notification(self):
        """Send standard notifications"""
        await self.roles_mapper.sendEmailWithSMS(
            self.mail_recipients, self.sms_recipients,
            self.subject, self.body, self.sms, True
        )

    async def _update_alert_status(self):
        """Update alert status in database"""
        alert_id = self.task.get_variable("alertid")
        self.update_alert['_id'] = alert_id
        alert_data = dnc_schema_model.Alerts(**self.update_alert)
        await alert_data.modify()

async def handle_task_notification(self, **task):
    """Main entry point for handling task notifications"""
    handler = SendNotification(task)
    return await handler.process()