import urdhva_base
import os
import json
import jinja2
import asyncio
import api_helpers
import hpcl_ceg_model
import urdhva_base.utilities
import urdhva_base.redispool
from types import SimpleNamespace
import orchestrator.notification_manager.notification_factory as notification_factory
from orchestrator.reporting_services.reporting_helpers import get_alert_data, lpg_data, retail_data, sales_data, sod_data, ro_va_cleanliness


def dict_to_object(d):
    """Convert dictionary to object (recursively for nested dictionaries)."""
    if isinstance(d, list):
        return [dict_to_object(i) for i in d]
    if isinstance(d, dict):
        return SimpleNamespace(**{k: dict_to_object(v) for k, v in d.items()})
    return d


async def publish_bi_hourly_report():
    zone_order = ['CEN', 'ECZ', 'EZ', 'NCZ', 'NFZ', 'NWFZ', 'NWZ', 'NZ', 'SCZ', 'SWZ', 'SZ', 'WZ']
    today_date = urdhva_base.utilities.get_present_time().strftime("%Y-%m-%d")
    hour = urdhva_base.utilities.get_present_time().strftime("%H:00")
    intra_dryout_status = await retail_data.get_bi_hourly_intra_dryout()
    dry_out_cond = ("interlock_name = 'Dry Out Each Indent Wise MainFlow' "
                    "AND mark_as_false = true AND interlock_name='Dry Out Each Indent Wise MainFlow' "
                    "AND product_code in ('2811000', '2812000', '2822000') AND dry_out_in_days='1'")
    indent_data = await api_helpers.get_initial_dryout_counts(bu='SOD', conditions=dry_out_cond,
                                                                 dry_out_in_days_query="1",
                                                                 by_zone=True, by_location=False)
    indent_summary = {}
    indent_key_mapping = {"Indent Not Raised": "indents_not_raised", "Indent On Hold": "indents_on_hold",
                   "Indent Raised": "indents_raised", "Pending Indents": "pending_indents",
                   "Valid \\ WIP Indents": "valid_indents"}
    for zone, details in indent_data['zone_data'].items():
        indent_summary[zone] = {"zone":zone}
        for indent_status in details:
            if indent_status.get('section') in indent_key_mapping:
                indent_summary[zone][indent_key_mapping[indent_status['section']]] = indent_status['value']
        indent_summary[zone]['dry_out'] = (indent_summary[zone].get('indents_not_raised', 0) +
                                           indent_summary[zone].get('indents_raised', 0))
    for zone in zone_order:
        if zone not in indent_summary:
            indent_summary[zone] = {"zone":zone, **{value: 0 for _, value in indent_key_mapping.items()}}
        indent_summary[zone]['dry_out'] = (indent_summary[zone].get('indents_not_raised', 0) +
                                           indent_summary[zone].get('indents_raised', 0))
    redis_ins = await urdhva_base.redispool.get_redis_connection()
    existing_data = await redis_ins.hget("dry_out_bi_hourly_report", today_date)
    if not existing_data:
        existing_data = {}
    else:
        existing_data = json.loads(existing_data)
    existing_data[hour] = {"hour": hour, "intra_dryout": intra_dryout_status,
                           "indent_summary": indent_summary}

    summary = []

    for t in sorted(existing_data.keys()):
        summary.append({
            "time": t,
            "data": existing_data[t]['intra_dryout']
        })

    await send_notification(
        template_name="retail_bi_hourly.html",
        to_recipients=["adityapandey@hpcl.in", "venu@algofusiontech.com"],
        subject="Novex Dryout Summary Report",
        cc_recipients=["yesu.p@algofusiontech.com","manohar.v@algofusiontech.com",
                       "gayathri.m@algofusiontech.com","jayaprakash.v@algofusiontech.com",
                       "poojitha.gumma@algofusiontech.com","vamsi.c@algofusiontech.com",
                       "moufikali@algofusiontech.com", "aditya@algofusiontech.com"],
        bcc_recipients=[],
        notification_data={"summary": summary, "time": hour,
                           "zone_summary": [indent_summary[z] for z in zone_order if z in indent_summary]},
        inline_images={
        },
        attachments = []
    )
    await redis_ins.hset("dry_out_bi_hourly_report", today_date, json.dumps(existing_data))


async def send_notification(template_name, to_recipients, subject, cc_recipients=None, bcc_recipients=None, notification_data=None, inline_images=None, attachments=None):
    template_path = os.path.join(
        os.path.dirname(hpcl_ceg_model.__file__),
        '..', 'orchestrator', 'reporting_services',
        'templates', template_name
        )
    with open(template_path, 'r') as f:
        template_data = jinja2.Template(f.read())
    final_data = template_data.render(**notification_data)

    # Send email
    ins = await notification_factory.get_notification_module("email")
    await ins.publish_message(
        subject=subject,
        recipients=to_recipients,
        cc_recipients=cc_recipients or [],
        bcc_recipients=bcc_recipients or [],
        html_content=True,
        body=final_data,
        force_send=True,
        inline_images=inline_images or {},
        attachments=attachments or []
    )


if __name__ == "__main__":
    asyncio.run(publish_bi_hourly_report())
