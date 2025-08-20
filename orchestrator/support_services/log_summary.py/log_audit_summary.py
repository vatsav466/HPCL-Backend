import urdhva_base
import asyncio
import traceback
import pandas as pd
import charts_actions
import dashboard_studio_model
import orchestrator.notification_manager.notification_factory as notification_factory
import datetime
import pytz


class LogAuditSummaryReport:

    EXCEL_FILENAME = '/tmp/login_audit_summary.xlsx'

    async def send_notification(self, body, attachment_path):
        """
        Sends the login audit summary report via email with an Excel attachment.
        """
        try:
            ins = await notification_factory.get_notification_module("email")
            recipients = [["cvmallinath@hpcl.in", "purushm@hpcl.in", "sachinkwarghane@hpcl.in", "dinesh.kumar@hpcl.in", 
                           "venu@algofusiontech.com", "sreedhar.maddipati@algofusiontech.com", "santoshkumar.s@algofusiontech.com", 
                           "shrihari.b@algofusiontech.com", "aditya@algofusiontech.com"]]  # List of recipient lists
            IST = pytz.timezone("Asia/Kolkata")
            today_ist = datetime.datetime.now(IST).strftime("%d-%m-%Y")
            for recipient in recipients:
                await ins.publish_message(
                    subject=f"Login Audit Summary Daily Report {today_ist}",
                    recipients=recipient,
                    html_content=False,   # no HTML body
                    body=body,
                    force_send=True,
                    attachments=[attachment_path]
                )
            print("Email notification with attachment sent successfully.")
        except Exception as e:
            print("Exception occurred while sending email notification")
            print(e)
            print("Traceback %s" % traceback.format_exc())

    async def log_audit_summary(self):
        """
        Fetches the login audit summary, saves as Excel, and sends an email notification with attachment.
        """
        try:
            query = ("""
                SELECT 
                    employee_id,
                    email,
                    role,
                    COUNT(*) AS login_count
                FROM user_login_audit
                WHERE
                    (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::DATE = 
                        (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::DATE
                    AND employee_id NOT IN ('admin', 'Admin', 'superadmin')
                    AND employee_id NOT LIKE '9405\\_%'
                GROUP BY employee_id, email, role
                ORDER BY login_count DESC;
            """)
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
            function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
            login_audit_resp = await function(query=query)
            audit_resp = pd.DataFrame(login_audit_resp)
            print("Audit response preview:", audit_resp.head())

            if audit_resp.empty:
                print("No login audit data found for today.")
                return
            audit_resp.to_excel(self.EXCEL_FILENAME, index=False)
            IST = pytz.timezone("Asia/Kolkata")
            today_ist = datetime.datetime.now(IST).strftime("%d-%m-%Y")
            body_text = f"Please find attached the login audit summary for {today_ist}. \n"
            await self.send_notification(body_text, self.EXCEL_FILENAME)

        except Exception as e:
            print("Exception occurred while processing login audit summary")
            print(e)
            print("Traceback %s" % traceback.format_exc())


if __name__ == "__main__":
    login_audit_summary = LogAuditSummaryReport()
    asyncio.run(login_audit_summary.log_audit_summary())
