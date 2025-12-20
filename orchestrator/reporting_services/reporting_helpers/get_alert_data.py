import urdhva_base
import utilities.helpers as helpers
import hpcl_ceg_model

async def get_alert_data(alert_section):
    # Making sure alerts considering only after May 31st in prod
    date = urdhva_base.utilities.get_present_time()
    date_yes = helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                               date_time_format=None)
    month_start = helpers.get_time_stamp_by_delta(date_yes, days=0, with_month_start_day=True,
                                               date_time_format="%Y-%m-%d")
    date_filter = f"created_at::DATE >= '{month_start}' AND created_at::DATE <= '{date_yes.strftime('%Y-%m-%d')}'" # As per HPCL request changed the date to be in the present month
    query = f"""SELECT count(alert_section), bu, alert_section, severity FROM alerts where alert_status='Open' and 
    alert_section='{alert_section}' and {date_filter} GROUP BY bu, alert_section, severity"""
    if alert_section in ["VTS"]:
        query = f"""SELECT count(alert_section), bu, alert_section, severity FROM alerts where vehicle_unblocked_date is null and 
                    alert_section='{alert_section}' and {date_filter} GROUP BY bu, alert_section, severity"""
    alerts = await hpcl_ceg_model.Alerts.get_aggr_data(query)
    data = {}
    for alert in alerts['data']:
        if alert["severity"] == "Critical":
            data.update({f"{alert_section.lower()}_critical_{alert['bu'].lower()}": alert["count"]})
        if alert["severity"] == "High":
            data.update({f"{alert_section.lower()}_high_{alert['bu'].lower()}": alert["count"]})
    for severity in ["critical", "high"]:
        for bu in ["lpg", "ro", "tas"]:
            if f"{alert_section.lower()}_{severity}_{bu}" not in data.keys():
                data.update({f"{alert_section.lower()}_{severity}_{bu}": 0})
    return data
