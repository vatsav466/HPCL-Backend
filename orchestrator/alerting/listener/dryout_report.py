import urdhva_base
import asyncio
import datetime
import pandas as pd
from jinja2 import Template
from orchestrator.notification_manager.notify_email import *
import orchestrator.alerting.listener.sync_ro_ims_report as sync_ro_ims_report
import gzip
import os


def read_template(filename, data):
    with open(filename, 'r') as f:
        html_string = f.read()
    j2_template = Template(html_string)
    body=j2_template.render(data)
    return body


def save_as_csv_gz(df, file_path):
    """Save DataFrame directly as compressed CSV (.csv.gz) — much smaller than Excel"""
    gz_path = file_path + ".gz"
    with gzip.open(gz_path, 'wt', encoding='utf-8') as f:
        df.to_csv(f, index=False)
    return gz_path


async def generate_dryout_report():
    report_time = urdhva_base.utilities.get_present_time()
    report_time = report_time.strftime("%Y-%B-%d_%H_%M_%S")
    data = await sync_ro_ims_report._get_dry_out_ims_report("1")
    df = pd.DataFrame(data)
    data_1 = await sync_ro_ims_report._get_dry_out_ims_report("2")
    df_1 = pd.DataFrame(data_1)

    dry_out_gz = save_as_csv_gz(df, f"/tmp/dry_out_report_{report_time}.csv")
    intra_day_gz = save_as_csv_gz(df_1, f"/tmp/intra_day_dry_out_report_{report_time}.csv")
    to_email = ['gauravyadav1@hpcl.in', 'rameshyadav.p@hpcl.in', 'venu@algofusiontech.com', 'pampanaboyina.rekha@hpcl.in', 'yesu.p@algofusiontech.com']
    notify_email = NotifyEMail()
    data = {"report_time": report_time, "portal_link": "https://novex.hpcl.co.in"}
    resp = await notify_email.publish_message(
        **{
            'recipients': to_email,
            'subject': f"Dry Out Report as on {report_time}",
            'body': read_template("/opt/ceg/algo/orchestrator/notification_templates/dryout_report.html",
                                  data=data),
            'attachments': [dry_out_gz, intra_day_gz],
            'html_content': True,
            'force_send': True
        }
    )
    print("Email Resp: ", resp)
    # Cleanup
    os.remove(dry_out_gz)
    os.remove(intra_day_gz)


if __name__ == "__main__":
    print(f"Executing dry-out alert creation at {datetime.datetime.now(datetime.timezone.utc)}")
    asyncio.run(generate_dryout_report())