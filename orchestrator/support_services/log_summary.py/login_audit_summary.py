import urdhva_base
import asyncio
import traceback
import pandas as pd
import charts_actions
import dashboard_studio_model
import orchestrator.notification_manager.notification_factory as notification_factory
import datetime
import pytz
import hpcl_ceg_model


class LogAuditSummaryReport:

    EXCEL_FILENAME = '/tmp/login_audit_summary.xlsx'

    @staticmethod
    def ensure_list(v):
        """Return a list for grouping/exploding. Empty list for NA."""
        if isinstance(v, (list, tuple, set)):
            return list(v)
        if pd.isna(v):
            return []
        return [v]

    async def send_notification(self, body, attachment_path):
        """
        Sends the login audit summary report via email with an Excel attachment.
        """
        try:
            ins = await notification_factory.get_notification_module("email")
            recipients = [["cvmallinath@hpcl.in","sreedhar.maddipati@algofusiontech.com",
                           "purushm@hpcl.in","sachinkwarghane@hpcl.in",
                           "venu@algofusiontech.com","bala@algofusiontech.com","yesu.p@algofusiontech.com", "shrihari.b@algofusiontech.com"]]
            IST = pytz.timezone("Asia/Kolkata")
            today_ist = datetime.datetime.now(IST).strftime("%d-%m-%Y")
            for recipient in recipients:
                await ins.publish_message(
                    subject=f"Users Login Daily Report {today_ist}",
                    recipients=recipient,
                    html_content=True,   # no HTML body
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
                            ula.employee_id,
                            ula.email,
                            u.first_name,
                            u.last_name,
                            u.contact_number,
                            ula.role,
                            u.bu,
                            u.sap_id,
                            u.region,
                            u.zone,
                            u.state,
                            u.sales_area,
                            COUNT(*) AS login_count
                        FROM user_login_audit ula
                        JOIN users u ON ula.employee_id = u.employee_id
                        WHERE
                            (ula.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::DATE = 
                                (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::DATE
                            AND ula.employee_id NOT IN ('admin', 'Admin', 'superadmin')
                            AND ula.employee_id NOT LIKE '9405\\_%'
                        GROUP BY 
                            ula.employee_id,
                            ula.email,
                            u.first_name,
                            u.last_name,
                            u.contact_number,
                            ula.role,
                            u.bu,
                            u.sap_id,
                            u.region,
                            u.zone,
                            u.state,
                            u.sales_area
                        ORDER BY login_count DESC;
                    """)

            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
            function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
            login_audit_resp = await function(query=query)
            audit_resp = pd.DataFrame(login_audit_resp)

            for idx, record in audit_resp.iterrows():
                conditions = []
                if record["bu"] and len(record["bu"]) > 0:
                    conditions.append(f"bu = '{record['bu'][0]}'")
                if record["sap_id"] and len(record["sap_id"]) > 0:
                    conditions.append(f"sap_id = '{record['sap_id'][0]}'")
                if record["region"] and len(record["region"]) > 0:
                    conditions.append(f"region = '{record['region'][0]}'")
                if record["zone"] and len(record["zone"]) > 0:
                    conditions.append(f"zone = '{record['zone'][0]}'")
                if record["state"] and len(record["state"]) > 0:
                    conditions.append(f"state = '{record['state'][0]}'")
                if record["sales_area"] and len(record["sales_area"]) > 0:
                    conditions.append(f"sales_area = '{record['sales_area'][0]}'")
                conditions.append("alert_status != 'Close'")

                # Join all conditions with ' and '
                where_clause = " and ".join(conditions)

                # Compose the full query string
                query = f"select distinct(assigned_user_roles) from alerts where {where_clause}"

                audit_alerts_data = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=1000)
                roles = []
                if len(audit_alerts_data['data']):
                    for data in audit_alerts_data['data']:
                        if len(data['assigned_user_roles']):
                            for role in data['assigned_user_roles']:
                                if role not in roles:
                                    roles.append(role)

                if len(record['role']):
                    for role in roles:
                        if role in record['role']:
                            audit_resp.at[idx, 'action_required'] = 'yes'
                            break
                    else:
                        audit_resp.at[idx, 'action_required'] = 'No'
                else:
                    audit_resp.at[idx, 'action_required'] = 'No'
                

            print("Audit response preview:", audit_resp.head())

            if audit_resp.empty:
                print("No login audit data found for today.")
                return
            
            audit_resp.to_excel(self.EXCEL_FILENAME, index=False)

            # ---------- Build summary by BU & action_required ----------
            audit_resp['bu_list'] = audit_resp['bu'].apply(self.ensure_list)
            exploded = audit_resp.explode('bu_list', ignore_index=True).rename(columns={'bu_list': 'bu_norm'})
            exploded['bu_norm'] = exploded['bu_norm'].fillna('AdminUsers')

            summary_df = (
                exploded.groupby(['bu_norm', 'action_required'], dropna=False)
                .size()
                .reset_index(name='number_of_users_logged_in')
                .rename(columns={'bu_norm': 'bu'})
                .sort_values(['bu', 'action_required'])
            )

            # Build inline-styled HTML table (no <style> block)
            table_style = (
                "border-collapse:collapse; min-width:500px; font-family:Arial, sans-serif; font-size:14px;"
            )
            th_style = "border:1px solid #e0e0e0; padding:8px 12px; background:#2e7d32; color:#ffffff; font-weight:600; text-align:center;"
            td_style = "border:1px solid #e0e0e0; padding:8px 12px; text-align:center;"
            pill_yes = "display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;background:#e8f5e9;color:#1b5e20;border:1px solid #c8e6c9;"
            pill_no = "display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;background:#ffebee;color:#b71c1c;border:1px solid #ffcdd2;"

            # header
            html_rows = []
            html_rows.append(f"<table style='{table_style}'>")
            html_rows.append("<thead><tr>")
            html_rows.append(f"<th style='{th_style}'>BU</th>")
            html_rows.append(f"<th style='{th_style}'>Action Required</th>")
            html_rows.append(f"<th style='{th_style}'>Number of Users Logged In</th>")
            html_rows.append("</tr></thead>")
            html_rows.append("<tbody>")

            # rows
            for _, r in summary_df.iterrows():
                bu = str(r['bu'])
                action = str(r['action_required'])
                count = int(r['number_of_users_logged_in'])
                pill = f"<span style='{pill_yes}'>Yes</span>" if action.lower() == "yes" else f"<span style='{pill_no}'>No</span>"
                html_rows.append("<tr>")
                html_rows.append(f"<td style='{td_style}'>{bu}</td>")
                html_rows.append(f"<td style='{td_style}'>{pill}</td>")
                html_rows.append(f"<td style='{td_style}'>{count}</td>")
                html_rows.append("</tr>")

            html_rows.append("</tbody></table>")
            summary_html_table = "".join(html_rows)

            IST = pytz.timezone("Asia/Kolkata")
            today_ist = datetime.datetime.now(IST).strftime("%d-%m-%Y")
            html_intro = f"<p>Please find the attached for the list of users whoever logged in to the<b>Novex</b> on <b>{today_ist}</b>.</p>"
            body_html = f"{html_intro}<p><b>Summary by BU &amp; Action Required:</b></p>{summary_html_table}"
            await self.send_notification(body_html, self.EXCEL_FILENAME)

        except Exception as e:
            print("Exception occurred while processing login audit summary")
            print(e)
            print("Traceback %s" % traceback.format_exc())


if __name__ == "__main__":
    login_audit_summary = LogAuditSummaryReport()
    asyncio.run(login_audit_summary.log_audit_summary())
