#!/usr/bin/env python3
import os
import sys
import jinja2
import asyncio
import datetime
import urdhva_base
import hpcl_ceg_model
import utilities.helpers as helpers
import orchestrator.notification_manager.notification_factory as notification_factory


async def fetch_tas_onboarded_alert_counts():
    query = """
        SELECT 
            lm.name AS location_name,
            lm.sap_id,
            COALESCE(SUM(CASE WHEN a.alert_status = 'Open' AND LOWER(a.severity) = 'critical' THEN 1 ELSE 0 END), 0) AS open_critical,
            COALESCE(SUM(CASE WHEN a.alert_status = 'Close' AND LOWER(a.severity) = 'critical' THEN 1 ELSE 0 END), 0) AS close_critical,
            COALESCE(SUM(CASE WHEN a.alert_status = 'Open' AND LOWER(a.severity) = 'high' THEN 1 ELSE 0 END), 0) AS open_high,
            COALESCE(SUM(CASE WHEN a.alert_status = 'Close' AND LOWER(a.severity) = 'high' THEN 1 ELSE 0 END), 0) AS close_high,
            COALESCE(SUM(CASE WHEN a.alert_status = 'Open' AND LOWER(a.severity) = 'medium' THEN 1 ELSE 0 END), 0) AS open_medium,
            COALESCE(SUM(CASE WHEN a.alert_status = 'Close' AND LOWER(a.severity) = 'medium' THEN 1 ELSE 0 END), 0) AS close_medium,
            COALESCE(SUM(CASE WHEN a.alert_status = 'Open' AND LOWER(a.severity) = 'low' THEN 1 ELSE 0 END), 0) AS open_low,
            COALESCE(SUM(CASE WHEN a.alert_status = 'Close' AND LOWER(a.severity) = 'low' THEN 1 ELSE 0 END), 0) AS close_low,
            COALESCE(SUM(CASE WHEN a.alert_status IN ('Open', 'Close') THEN 1 ELSE 0 END), 0) AS grand_total
        FROM location_master lm
        LEFT JOIN alerts a ON lm.sap_id = a.sap_id 
            AND a.bu = 'TAS' 
            AND a.alert_section = 'TAS'
            AND a.created_at::DATE = CURRENT_DATE
        WHERE lm.location_onboard = true
        GROUP BY lm.sap_id, lm.name
        ORDER BY lm.name
    """
    resp = await hpcl_ceg_model.Alerts.get_aggr_data(query)
    return resp.get("data", [])


async def get_email_users_by_type(email_type: str, audience: str):
    all_users = await hpcl_ceg_model.DailyEmailNotificationUsers.get_all(resp_type='plain')
    to_recipients = []
    cc_recipients = []
    bcc_recipients = []
    for user in all_users.get("data", []):
        if user.get("audience") == audience and (user.get("email_type") or "").lower() == email_type.lower():
            to_recipients.extend(user.get("to_recipients", []))
            cc_recipients.extend(user.get("cc_recipients", []))
            bcc_recipients.extend(user.get("bcc_recipients", []))
    return {
        "to": list(set(to_recipients)),
        "cc": list(set(cc_recipients)),
        "bcc": list(set(bcc_recipients))
    }


async def send_tas_notification(template_name, to_recipients, subject, cc_recipients=None, bcc_recipients=None, notification_data=None):
    # Find templates directory dynamically relative to this file
    template_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'templates', template_name
    )
    # Fallback to absolute project path if relative path doesn't exist
    if not os.path.exists(template_path):
        template_path = os.path.join(
            os.path.dirname(hpcl_ceg_model.__file__),
            '..', 'orchestrator', 'reporting_services',
            'templates', template_name
        )
    
    with open(template_path, 'r') as f:
        template_data = jinja2.Template(f.read())
    
    final_data = template_data.render(**notification_data)

    tmp_file = f"/tmp/{template_name}"
    with open(tmp_file, 'w') as f:
        f.write(final_data)

    ins = await notification_factory.get_notification_module("email")
    await ins.publish_message(
        subject=subject,
        recipients=to_recipients,
        cc_recipients=cc_recipients or [],
        bcc_recipients=bcc_recipients or [],
        html_content=True,
        body=final_data,
        force_send=True
    )


async def publish_daily_tas_alert_report(email_type, audience):
    date = urdhva_base.utilities.get_present_time()
    report_generated_time = date.strftime('%I:%M %p')
    
    status_data = {
        'today_date': date.strftime('%d-%B-%Y'),
        'report_generated_time': report_generated_time,
        'today_week': date.strftime('%A'),
        'yesterday_date': helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False, date_time_format='%d-%B-%Y'),
        'yesterday_week': helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False, date_time_format='%A'),
        'today': date.strftime('%d-%B-%Y'),
        'yesterday': helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False, date_time_format='%d-%B-%Y'),
    }

    # Fetch daily alert counts location-wise
    tas_counts = await fetch_tas_onboarded_alert_counts()
    status_data.update({"tas_onboarded_counts": tas_counts})

    # Calculate column totals
    totals = {
        "open_critical": sum(int(row.get("open_critical", 0)) for row in tas_counts),
        "close_critical": sum(int(row.get("close_critical", 0)) for row in tas_counts),
        "open_high": sum(int(row.get("open_high", 0)) for row in tas_counts),
        "close_high": sum(int(row.get("close_high", 0)) for row in tas_counts),
        "open_medium": sum(int(row.get("open_medium", 0)) for row in tas_counts),
        "close_medium": sum(int(row.get("close_medium", 0)) for row in tas_counts),
        "open_low": sum(int(row.get("open_low", 0)) for row in tas_counts),
        "close_low": sum(int(row.get("close_low", 0)) for row in tas_counts),
        "grand_total": sum(int(row.get("grand_total", 0)) for row in tas_counts),
    }
    status_data.update({"totals": totals})

    # Fetch recipients dynamically from DailyEmailNotificationUsers table in DB
    recipients = await get_email_users_by_type(email_type=email_type, audience=audience)
    to_recipients = recipients["to"]
    cc_recipients = recipients["cc"]
    bcc_recipients = recipients["bcc"]

    await send_tas_notification(
        template_name="seg6.html",
        to_recipients=to_recipients,
        subject="Novex Daily Report: TAS Location-Wise Alert Summary",
        cc_recipients=cc_recipients,
        bcc_recipients=bcc_recipients,
        notification_data=status_data
    )
    print("TAS Daily Report Email sent successfully.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)
    email_type = sys.argv[1]
    audience = sys.argv[2]
    asyncio.run(publish_daily_tas_alert_report(email_type=email_type, audience=audience))
