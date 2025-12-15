import urdhva_base
import datetime
import hpcl_ceg_model
import utilities.connection_mapping as connection_mapping
import orchestrator.analytics.dry_out_analysis as dry_out_analysis


async def get_where_clause_condition(filters):
    where_clause = ["interlock_name = 'Dry Out Each Indent Wise MainFlow'", "mark_as_false = true"]
    where_clause.extend(await hpcl_ceg_model.Alerts.get_clause_conditions(
        extra_key_mapping={"sap_id": "terminal_plant_id"}, default_mapping={"bu": "RO"}))
    dry_out_in_days_query = '1'
    tt_count_filter = {}
    for record in filters:
        if record.key == "progress_rate":
            if record.value:
                where_clause.append(f"progress_rate={int(record.value[0])}")
        else:
            if record.value:
                if record.key == 'dry_out_in_days':
                    dry_out_in_days_query = record.value[0]
                if record.key == "plant":
                    record.key = "terminal_plant_id"
                    tt_count_filter.update({record.key: record.value})
                if record.key == "zone":
                    tt_count_filter.update({record.key: record.value})
                if len(record.value) == 1:
                    where_clause.append(f"{record.key}='{record.value[0]}'")
                else:
                    where_clause.append(f"{record.key} in {tuple(record.value)}")
    conditions = ' AND '.join(where_clause)
    return conditions, dry_out_in_days_query, tt_count_filter

async def get_initial_dryout_counts(bu, conditions, dry_out_in_days_query):
    stats_query = "select distinct sap_id, min(progress_rate) as present_stage " \
                  f"from alerts where {conditions} and indent_status not in ('Cancelled', 'Completed', 'TempClosed', 'ProductLowLevel', 'OfflineOrFalseAlarm', 'NotAvailable') " \
                  f"group by sap_id"
    stats_resp = await hpcl_ceg_model.Alerts.get_aggr_data(stats_query, limit=10000)
    where_clause_conditions = ["interlock_name = 'Dry Out Each Indent Wise MainFlow'"]
    where_clause_conditions.extend(await hpcl_ceg_model.Alerts.get_clause_conditions(
        extra_key_mapping={"sap_id": "terminal_plant_id"}))
    _date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    delivered_count = 0
    atg_ack = 0
    if bu == "sod":
        atg_ack = await dry_out_analysis.get_atg_ack_count(dry_out_in_days=str(dry_out_in_days_query))
        delivered_query = f"""SELECT SUM(distinct_count) AS total_count
                                FROM (
                                    SELECT COUNT(DISTINCT sap_id) AS distinct_count
                                    FROM alerts
                                    WHERE {' AND '.join(where_clause_conditions)}
                                    AND indent_status = 'Completed' AND dry_out_in_days = '{dry_out_in_days_query}' 
                                    AND DATE(updated_at) = '{_date}'  -- Use TRUNC to ignore the time part
                                    GROUP BY sap_id
                                ) AS subquery"""
        delivered_count = await hpcl_ceg_model.Alerts.get_aggr_data(delivered_query, limit=10000)
        if delivered_count:
            delivered_count = delivered_count['data'][0].get("total_count", 0) if delivered_count['data'][0].get(
                "total_count") else 0

    top_x_axis = connection_mapping.dry_out_top_x_axis
    stats = {i + 1: 0 for i, _ in enumerate(top_x_axis)}
    for rec in stats_resp['data']:
        if rec['present_stage'] == 0:
            rec['present_stage'] = 1
        if rec['present_stage'] not in stats:
            stats[rec['present_stage']] = 0
        stats[rec['present_stage']] += 1

    stats = [{"section": top_x_axis[key - 1]['name'], "value": value, "serial": key, "condition": "=",
              "group": top_x_axis[key - 1]['group']}
             for key, value in stats.items() if key <= len(top_x_axis)]
    stats.extend([{
        "section": "Indent Raised",
        "value": sum(item['value'] for item in stats if 2 <= item['serial'] <= 10),
        "serial": 13, "condition": "=", "group": "not_raised"
    }, {
        "section": "Valid \\ WIP Indents",
        "value": sum(item['value'] for item in stats if 4 <= item['serial'] <= 10),
        "serial": 14, "condition": "=", "group": "pending"
    }
    # ,{
    #     "section": "EMUnLock",
    #     "value": 0, "serial": 18, "condition": "=", "group": "wip"
    # }
    ])

    updated_stats = []
    for each_stats in stats:
        if each_stats['section'] == 'Delivery Confirmation':
            each_stats['value'] = delivered_count
        if each_stats['section'] == 'ATG Ack':
            each_stats['value'] = atg_ack
        updated_stats.append(each_stats)
    return updated_stats