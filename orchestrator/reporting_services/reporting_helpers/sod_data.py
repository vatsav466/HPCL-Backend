import urdhva_base
import datetime
import pandas as pd
import urdhva_base.utilities
import utilities.helpers as helpers
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams


async def get_tas_alerts():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    query = f""" SELECT count(interlock_name) as total_count, severity FROM alerts where bu='TAS' and created_at>='{today}' and alert_status='Open' GROUP BY severity; """
    alerts = await function(query=query)
    data = {}
    if alerts:
        for alert in alerts:
            if alert["severity"] == "Critical":
                data = {"tas_critical_sod": alert["total_count"]}
            if alert["severity"] == "High":
                data = {"tas_high_sod": alert["total_count"]}
    for key in ["tas_critical_sod", "tas_high_sod"]:
        if key not in data.keys():
            data.update({key: 0})
    return data


async def get_vts_tas_blocked_counts():
    # Making sure alerts considering only after May 31st in prod
    date = urdhva_base.utilities.get_present_time()
    date_yes = helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                               date_time_format=None)
    month_start = helpers.get_time_stamp_by_delta(date_yes, days=0, with_month_start_day=True,
                                               date_time_format="%Y-%m-%d")
    date_filter = f"created_at::DATE >= '{month_start}' AND created_at::DATE <= '{date_yes.strftime('%Y-%m-%d')}'" # As per HPCL request changed the date to be in the present month
    tas_query = f"""SELECT
                        COUNT(*) FILTER (WHERE alert_section='VTS'
                                        AND bu='TAS'
                                        AND interlock_name != 'Itdg Admin Blocked'
                                        AND {date_filter})
                            AS "TTs_Blocked_by_Novex_TAS",

                        COUNT(*) FILTER (WHERE alert_section='VTS'
                                        AND bu='TAS'
                                        AND {date_filter}
                                        AND mark_as_false = 'true'
                                        AND interlock_name != 'Itdg Admin Blocked'
                                        AND vehicle_unblocked_date IS NOT NULL)
                            AS "TTs_Manually_Unblocked_TAS",

                        COUNT(*) FILTER (WHERE alert_section='VTS'
                                        AND bu='TAS'
                                        AND {date_filter}
                                        AND interlock_name != 'Itdg Admin Blocked'
                                        AND vehicle_unblocked_date IS NULL)
                            AS "TTs_currently_under_Block_TAS",

                        COUNT(*) FILTER (WHERE alert_section='VTS'
                                        AND bu='TAS'
                                        AND {date_filter}
                                        AND mark_as_false = 'false'
                                        AND interlock_name != 'Itdg Admin Blocked'
                                        AND vehicle_unblocked_date IS NOT NULL)
                            AS "TTs_Auto_Unblocked_TAS"

                    FROM alerts;"""
    
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    tas_blocked_data_resp = await function(query=tas_query)
    tas_blocked_data_resp = pd.DataFrame(tas_blocked_data_resp)
    # Extract values from the first (and only) row safely
    if not tas_blocked_data_resp.empty:
        row = tas_blocked_data_resp.iloc[0]
        tas_blocked_data = {
            "TTs_Blocked_by_Novex_TAS": int(row.get("TTs_Blocked_by_Novex_TAS", 0)),
            "TTs_Manually_Unblocked_TAS": int(row.get("TTs_Manually_Unblocked_TAS", 0)),
            "TTs_currently_under_Block_TAS": int(row.get("TTs_currently_under_Block_TAS", 0)),
            "TTs_Auto_Unblocked_TAS": int(row.get("TTs_Auto_Unblocked_TAS", 0))
        }
    else:
        # Default if no data returned
        tas_blocked_data = {
            "TTs_Blocked_by_Novex_TAS": 0,
            "TTs_Manually_Unblocked_TAS": 0,
            "TTs_currently_under_Block_TAS": 0,
            "TTs_Auto_Unblocked_TAS": 0
        }
    return tas_blocked_data