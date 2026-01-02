import urdhva_base
import os
import asyncio
import csv
import json
import time 
import requests
import jinja2
from collections import Counter
import hpcl_ceg_model
from datetime import datetime
from zoneinfo import ZoneInfo
from openpyxl import Workbook
import orchestrator.notification_manager.notification_factory


CAMUNDA_INSTANCES = [
    # LPG PQ Rejections
    {"server_type": "LPG", "host": "10.90.38.219", "port": 8080},
    # RO (Retail Automation)
    {"server_type": "RO", "host": "10.90.38.224", "port": 8080},
    # VTS
    {"server_type": "VTS-TAS", "host": "10.90.38.218", "port": 9092},
    {"server_type": "VTS-LPG", "host": "10.90.38.218", "port": 9093},
    # TAS
    {"server_type": "VTS-TAS", "host": "10.90.38.218", "port": 9094},
    {"server_type": "VTS-LPG", "host": "10.90.38.218", "port": 9095},
    # VA
    {"server_type": "VA-TAS", "host": "10.90.38.219", "port": 9091},
    {"server_type": "VA-RO",  "host": "10.90.38.219", "port": 9090},
    # DryOut
    {"server_type": "DryOut", "host": "10.90.38.217", "port": 9080},
    {"server_type": "DryOut", "host": "10.90.38.217", "port": 9081},
    {"server_type": "DryOut", "host": "10.90.38.217", "port": 9082},
    {"server_type": "DryOut", "host": "10.90.38.217", "port": 9083},
    {"server_type": "DryOut", "host": "10.90.38.217", "port": 9084},
    {"server_type": "DryOut", "host": "10.90.38.217", "port": 9085},
    {"server_type": "DryOut", "host": "10.90.38.217", "port": 9086},
    {"server_type": "DryOut", "host": "10.90.38.217", "port": 9087},
    {"server_type": "DryOut", "host": "10.90.38.217", "port": 9088},
    {"server_type": "DryOut", "host": "10.90.38.217", "port": 9089}
]


header = ["id", "processDefinitionId", "processInstanceId", "executionId", "incidentTimestamp", "incidentType", 
              "activityId", "failedActivityId", "causeIncidentId", "rootCauseIncidentId", "configuration", "incidentMessage",
              "tenantId", "jobDefinitionId", "annotation", "server_type", "host", "port"]


def fetch_incidents():
    """fetching all Camunda incidents from all configured camunda instances"""
    all_incidents = []
    for instance in CAMUNDA_INSTANCES:
        url= f"http://{instance['host']}:{instance['port']}/engine-rest/incident"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            incidents = response.json()
            print("incidents----->", len(incidents) , "\n\n")
            for inc in incidents:
                inc["server_type"] = instance["server_type"]
                inc["host"] = instance["host"]
                inc["port"] = instance["port"]
                all_incidents.append(inc)
                
        except Exception as e:
            print(f"Error in getting incidents information from {instance['host']}:{instance['port']} → {e}")

    return all_incidents


def generate_excel(all_incidents):
    EXCEL_PATH = "/tmp/incident_result.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Camunda Incident"
    ws.append(header)

    for row in all_incidents:
        ws.append([row.get(h) for h in header])

    wb.save(EXCEL_PATH)
    return EXCEL_PATH


def generate_csv(all_incidents):
    CSV_PATH = "/tmp/incident_result.csv"
    with open(CSV_PATH, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow(header)
        for row in all_incidents:
            writer.writerow([row.get(h) for h in header])
        return CSV_PATH


def incident_summary(incidents):
    """
    Creates count of incidents grouped by server_type, host, and port
    """
    counter = Counter()
    summary= []
    for inc in incidents:
        inc["server_type"] = inc["server_type"]
        inc["host"] = inc["host"]
        inc["port"] = inc["port"]
        counter[(inc["server_type"], inc["host"], inc["port"])] += 1
        print("counter count---->", counter)

    for (server_type, host, port), count in counter.items():
        summary.append({
            "server_type": server_type,
            "host": host,
            "port": port,
            "count": count
        })
    
    return summary


async def send_email(template_name, to_recipients, subject, cc_recipients, bcc_recipients, final_data, attachments=None):

    ins = await orchestrator.notification_manager.notification_factory.get_notification_module("email")

    # Load HTML template
    template_path = os.path.join(
        os.path.dirname(hpcl_ceg_model.__file__),
        '..', 'orchestrator', 'reporting_services',
        'templates', template_name
        )

    with open(template_path, "r") as f:
        template = jinja2.Template(f.read())

    html_body = template.render(**final_data)

    # Send email
    await ins.publish_message(
        subject=subject,
        recipients=to_recipients,
        cc_recipients=cc_recipients,
        bcc_recipients=bcc_recipients,
        html_content=True,
        body=html_body,
        force_send=True,
        inline_images={},
        attachments=attachments or []
    )
    print("Email sent successfully")



async def main():
    print("Triggered at:", datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M %p"))
    result = fetch_incidents()
    if not result:
        print(f"No incident triggered")
        return 
    
    excel_path = generate_excel(result)
    csv_path = generate_csv(result)

    summary = incident_summary(result)

    email_data = {
        "generated_time": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M %p"),
        "summary": summary
    }

    await send_email(
        template_name="camunda_incident.html",
        to_recipients=["sreedhar.maddipati@algofusiontech.com","bala@algofusiontech.com"],
        subject="Camunda Incident Alert (Critical)",
        cc_recipients=["venu@algofusiontech.com", "moufikali@algofusiontech.com", "aditya@algofusiontech.com", 
                       "yesu.p@algofusiontech.com", "manohar.v@algofusiontech.com"],
        bcc_recipients=["gayathri.m@algofusiontech.com", "jayaprakash.v@algofusiontech.com", "mohith.p@algofusiontech.com", 
                        "poojitha.gumma@algofusiontech.com", "pawann.k@algofusiontech.com"],
        final_data=email_data, 
        attachments=[csv_path, excel_path]
    )
    

if __name__ == "__main__":
    while True:
        asyncio.run(main())
        time.sleep(3600)

