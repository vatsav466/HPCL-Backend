import os
import csv
import aiofiles
import traceback
import urdhva_base
from jinja2 import Template
import orchestrator.notification_manager.notification_factory as notification_factory

logger = urdhva_base.logger.Logger.getInstance("vendor_notification-log")


class VendorEmailNotification:

    def __init__(self):
        """Initialize VendorEmailNotification object"""
        self.params = None
        self.vendor_email_map = {}
        self.mail_recipients = []
        self.subject = ""
        self.body = ""

    async def get_required_variables(self):
        """
        Returns a list of required variables for the action.
        
        Returns:
            list: Required variables
        """
        return [
            "sap_id", "device_type", "equipment_name", "zone", 
            "remarks", "status", "messagetype","location_name"
        ]

    async def load_vendor_email_csv(self):
        """Load vendor email CSV and return mapping"""
        try:

            current_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(current_dir, "vendor_email.csv")  
            vendor_map = {}
            async with aiofiles.open(csv_path, mode='r') as f:
                content = await f.read()
                csv_reader = csv.DictReader(content.splitlines())

                for row in csv_reader:
                    sap_id = row.get('sap_id', '').strip()
                    vendor_email = row.get('vendor_email', '').strip()

                    if sap_id and vendor_email:
                        vendor_map[sap_id] = vendor_email

            return vendor_map

        except Exception as e:
            logger.error(f"Error loading vendor CSV: {str(e)}")
            return {}

    async def read_template(self, filename: str) -> str:
        """Read HTML template file"""
        try:
            filepath = os.path.join(urdhva_base.settings.template_path, filename)
            async with aiofiles.open(filepath, 'r') as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Error reading template: {str(e)}")
            return ""

    async def process(self, params: dict):
        """
        Main processing method for vendor notifications.
        
        Args:
            params (dict): Dictionary containing task parameters from Camunda
            
        Returns:
            Tuple[bool, str/dict]: Success status and message/result
        """
        self.params = params

        try:
            # Get required variables
            sap_id = self.params.get("sap_id", "")
            device_type = self.params.get("device_type", "")
            equipment_name = self.params.get("equipment_name", "")
            zone = self.params.get("zone", "")
            remarks = self.params.get("remarks", "")
            status = self.params.get("status", "")
            message_type = self.params.get("messagetype", "notify")

            # Load vendor emails
            self.vendor_email_map = await self.load_vendor_email_csv()

            # Check if sap_id matches
            vendor_email = self.vendor_email_map.get(sap_id)
            if not vendor_email:
                logger.info(f"No vendor email for SAP ID: {sap_id}")
                return True, {"msg": "No vendor email configured"}

            self.mail_recipients = [vendor_email]

            # Prepare template data
            template_data = {
                "sap_id": sap_id,
                "device_type": device_type,
                "equipment_name": equipment_name,
                "zone": zone,
                "location_name": self.params.get("location_name", ""),
                "remarks": remarks,
                "status": status,
                "message_type": message_type
            }

            # Load template based on message type
            template_filename = f"vendor_notification_{message_type}.html"
            template_content = await self.read_template(template_filename)

            if not template_content:
                logger.warning(f"Template not found: {template_filename}, using default")
                # Try default template
                template_content = await self.read_template("vendor_notification.html")

            if not template_content:
                return False, "Template not found"

            # Render template
            self.body = Template(template_content).render(**template_data)
            self.subject = f"Notification - {equipment_name} ({sap_id})"

            # Send notification
            await self._send_notification()

            logger.info(f"Vendor notification sent to {vendor_email} for SAP ID: {sap_id}")
            return True, {"msg": "Notification sent successfully", "recipient": vendor_email}

        except Exception as e:
            logger.error(f"Error processing vendor notification: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"Failed to process notification: {str(e)}"

    async def _send_notification(self):
        """Send email notification"""
        try:
            notification_module = await notification_factory.get_notification_module(module_type="email")

            await notification_module.publish_message(
                recipients=self.mail_recipients,
                subject=self.subject,
                body=self.body,
                force_send=True,
                html_content=True
            )

            logger.info(f"Email sent to: {self.mail_recipients}")

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            raise

    async def handle_vendor_notification(self, params: dict):
        """
        Main entry point for handling task notifications from Camunda.
        
        Args:
            params (dict): Dictionary containing task parameters
            
        Returns:
            Tuple[bool, str/dict]: Success status and message
        """
        return await self.process(params)