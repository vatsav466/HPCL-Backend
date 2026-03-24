import typing
import traceback
import aiofiles
import urdhva_base
from jinja2 import Template
import orchestrator.notification_manager.notification_factory as notification_factory
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("vendor_notification-log")


class VendorEmailNotification:

    def __init__(self):
        """Initialize VendorEmailNotification object"""
        self.params = {}
        self.mail_recipients = []
        self.cc_recipients = []
        self.subject = ""
        self.body = ""

    async def get_required_variables(self):
        """
        Returns a list of required variables for the action.

        Returns:
            list: Required variables
        """
        return [
            "sap_id", "vendor_name", "device_type", "device_name",
            "zone", "bu", "remarks", "status", "messagetype", "location_name",
            "escalationlevel"  # 0=all, 1=level1, 2=level2, 3=level3
        ]

    async def get_vendor_emails(
        self,
        sap_id: str,
        vendor_name: str,
        zone: str,
        bu: str,
        escalationlevel: int
    ) -> tuple[list[str], list[str]]:
        """
        Fetch vendor emails from TasHelpDeskVendorMails table filtered by
        sap_id and vendor_name, then pick recipients based on escalationlevel.
        Also fetches CC recipients from Users table based on SOD roles.

        Args:
            sap_id (str): SAP ID of the asset/equipment
            vendor_name (str): Vendor name to match
            zone (str): Zone for fallback CC query
            bu (str): Business unit for fallback CC query
            escalationlevel (int): 0=all, 1=level1, 2=level2, 3=level3

        Returns:
            tuple[list[str], list[str]]: (mail_recipients, cc_recipients)
        """
        try:
            records = await hpcl_ceg_model.TasHelpDeskVendorMails.get_all(
                 urdhva_base.queryparams.QueryParams(q=f"sap_id='{sap_id}' and vendor_name='{vendor_name}'", limit=0),
                 resp_type="plain"
            )
            
            record_list = records.get("data") if isinstance(records, dict) else records
            if not record_list:
                logger.warning(f"No vendor mail config found | sap_id={sap_id} | vendor_name={vendor_name}")
                return [], []

            level_fields = (
                ["level1", "level2", "level3"]
                if int(escalationlevel) == 0
                else [f"level{escalationlevel}"]
            )

            emails: list[str] = []
            for record in record_list:
                for field in level_fields:
                    value = record.get(field)
                    if value:
                        emails.extend(addr.strip() for addr in value.split(",") if addr.strip())

            unique_emails = list(set(emails))
            logger.info(
                f"Resolved {len(unique_emails)} recipient(s) | "
                f"sap_id={sap_id} | vendor={vendor_name} | escalationlevel={escalationlevel}"
            )

            cc_roles = [
                "Location In-Charge SOD",
                "Maintenance Officer SOD",
                "Plant In-Charge SOD",
                "Planning Officer SOD",
                "Safety Officer SOD",
            ]
            roles_array = "{" + ",".join(cc_roles) + "}"

            cc_query = f"""
                SELECT email
                FROM users
                WHERE '{sap_id}' = ANY(sap_id)
                AND novex_role && '{roles_array}'::varchar[]
                AND email IS NOT NULL
            """
            cc_data = await hpcl_ceg_model.Users.get_aggr_data(cc_query, limit=0)

            if not cc_data or not cc_data.get("data"):
                cc_query = f"""
                    SELECT email
                    FROM users
                    WHERE '{zone}' = ANY(zone)
                    AND '{bu}' = ANY(bu)
                    AND novex_role && '{roles_array}'::varchar[]
                    AND email IS NOT NULL
                """
                cc_data = await hpcl_ceg_model.Users.get_aggr_data(cc_query, limit=0)

            cc_emails: list[str] = []
            if cc_data and cc_data.get("data"):
                cc_emails = list(set(
                    user["email"]
                    for user in cc_data["data"]
                    if user.get("email")
                ))

            logger.info(
                f"Resolved {len(cc_emails)} CC recipient(s) | "
                f"sap_id={sap_id} | zone={zone} | bu={bu}"
            )
            return unique_emails, cc_emails

        except Exception as e:
            logger.exception(f"Error fetching vendor emails from DB: {e}")
            return [], []

    async def read_template(self) -> str:
        """Read HTML template file"""
        try:
            filepath = f"{urdhva_base.settings.template_path}vendor_notification_notify.html"
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
            Tuple[bool, str | dict]: Success status and message/result
        """
        self.params = params

        try:
            sap_id           = params.get("sap_id")
            vendor_name      = params.get("vendor_name")
            device_type      = params.get("device_type")
            device_name      = params.get("device_name")
            zone             = params.get("zone")
            bu               = params.get("bu")
            remarks          = params.get("remarks")
            status           = params.get("status")
            message_type     = params.get("messagetype", "notify")
            location_name    = params.get("location_name", "")
            escalationlevel = int(params.get("escalationlevel", 1))

            # ----------------------------------------------------------------
            # Resolve TO and CC recipients from DB
            # ----------------------------------------------------------------
            self.mail_recipients, self.cc_recipients = await self.get_vendor_emails(
                sap_id=sap_id,
                vendor_name=vendor_name,
                zone=zone,
                bu=bu,
                escalationlevel=escalationlevel,
            )

            if not self.mail_recipients:
                logger.info(
                    f"No vendor emails found | sap_id={sap_id} | "
                    f"vendor={vendor_name} | escalationlevel={escalationlevel}"
                )
                return True, {"msg": "No vendor emails configured"}

            # ----------------------------------------------------------------
            # Read and render template
            # ----------------------------------------------------------------
            template_content = await self.read_template()
            if not template_content:
                return False, "Email template not found"

            self.body = Template(template_content).render(
                sap_id=sap_id,
                vendor_name=vendor_name,
                device_type=device_type,
                device_name=device_name,
                zone=zone,
                bu=bu,
                location_name=location_name,
                remarks=remarks,
                status=status,
                message_type=message_type,
                escalationlevel=escalationlevel,
            )
            self.subject = f"TAS Notification - {device_name} ({sap_id})"

            # ----------------------------------------------------------------
            # Dispatch
            # ----------------------------------------------------------------
            await self._send_notification()
            logger.info(
                f"Vendor email sent | sap_id={sap_id} | vendor={vendor_name} | "
                f"escalation_level={escalationlevel} | "
                f"recipients={self.mail_recipients} | cc={self.cc_recipients}"
            )
            return True, {"msg": "Notification sent successfully"}

        except Exception as e:
            logger.error(f"Vendor notification failed: {e}")
            logger.error(traceback.format_exc())
            return False, str(e)

    async def _send_notification(self):
        """Send email notification via notification factory"""
        try:
            notification_module = await notification_factory.get_notification_module(
                module_type="email"
            )
            await notification_module.publish_message(
                recipients=self.mail_recipients,
                cc_recipients=self.cc_recipients,
                subject=self.subject,
                body=self.body,
                force_send=True,
                html_content=True,
            )
            logger.info(f"Email dispatched to: {self.mail_recipients} | CC: {self.cc_recipients}")

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            raise

    async def handle_vendor_notification(self, params: dict):
        """
        Main entry point called by the Camunda orchestrator.

        Args:
            params (dict): Task parameters from Camunda

        Returns:
            Tuple[bool, str | dict]: Success status and message
        """
        return await self.process(params)