import os
import ast
import traceback
import polars as pl
import aiofiles
import urdhva_base
from jinja2 import Template
import orchestrator.notification_manager.notification_factory as notification_factory

logger = urdhva_base.logger.Logger.getInstance("vendor_notification-log")


class VendorEmailNotification:

    def __init__(self):
        """Initialize VendorEmailNotification object"""
        self.params = {}
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
                "remarks", "status", "messagetype", "location_name"
               ]
   
    async def load_vendor_email_csv(self, sap_id: str) -> list[str]:
        """Load vendor emails for a given SAP ID from CSV"""
        try:
            csv_path = os.path.join(os.path.dirname(__file__), "vendor_email.csv")
            
            df = pl.read_csv(csv_path, truncate_ragged_lines=True).with_columns(pl.col("sap_id").cast(pl.Utf8))
            row = (df.filter(pl.col("sap_id") == sap_id).select("vendor_email")
                   .to_series()
                   .to_list()
                )

            emails = []
            for val in row:
                try:
                    emails.extend(ast.literal_eval(val))
                except Exception:
                    logger.error(f"Invalid vendor_email skipped: {val}")

            return list(set(emails))  # remove duplicates

        except Exception as e:
            logger.exception(f"Error loading vendor email CSV: {e}")
            return []


    async def read_template(self, filename: str) -> str:
        """Read HTML template file"""
        try:
            filepath = os.path.join(urdhva_base.settings.template_path, filename)
            async with aiofiles.open(filepath, "r") as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Template read error: {e}")
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
            sap_id = params.get("sap_id")
            device_type = params.get("device_type")
            equipment_name = params.get("equipment_name")
            zone = params.get("zone")
            remarks = params.get("remarks")
            status = params.get("status")
            message_type = params.get("messagetype", "notify")
            location_name = params.get("location_name", "")

            # Load vendor emails
            self.mail_recipients = await self.load_vendor_email_csv(sap_id)


            if not self.mail_recipients:
                logger.info(f"No vendor emails configured for SAP ID {sap_id}")
                return True, {"msg": "No vendor emails configured"}

            # Template data
            template_data = {
                "sap_id": sap_id,
                "device_type": device_type,
                "equipment_name": equipment_name,
                "zone": zone,
                "location_name": location_name,
                "remarks": remarks,
                "status": status,
                "message_type": message_type
            }

            # Load template
            template_name = f"vendor_notification_{message_type}.html"
            template_content = await self.read_template(template_name)

            if not template_content:
                template_content = await self.read_template("vendor_notification.html")

            if not template_content:
                return False, "Email template not found"

            # Render
            self.body = Template(template_content).render(**template_data)
            self.subject = f"TAS Notification - {equipment_name} ({sap_id})"

            # Send mail
            await self._send_notification()
            logger.info(f"Vendor email sent | SAP ID={sap_id} | Recipients={self.mail_recipients}")
            return True, {"msg": "Notification sent successfully"}

        except Exception as e:
            logger.error(f"Vendor notification failed: {e}")
            logger.error(traceback.format_exc())
            return False, str(e)

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