from decimal import Decimal
import traceback
import hpcl_ceg_model
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


def convert_decimal(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal(v) for v in obj]
    return obj


async def sod_percentage():
    try:
        query = f'''bu = 'TAS'
            AND sap_id = '1991'
            AND created_at::date >= date_trunc('month', current_date)
            AND created_at::date < current_date'''
        print('*'*200)
        print(query)
        print('*'*200)
        data = await hpcl_ceg_model.PerformanceScoreHistory.get_all(
                urdhva_base.queryparams.QueryParams(q=query),resp_type='plain')
        print("data---->", data)
        if not data:
            print("No data found")
            return None

        #cleaned = [convert_decimal(row) for row in data]
        rows = data.get("data") or data.get("rows") or []
        print(f"\nExtracted {len(rows)} rows")

        if not rows:
            print("\nNo rows inside 'data'")
            return None

        cleaned = [convert_decimal(row) for row in rows]
        print("cleaned_data---->",cleaned)
        category_rows = []
        for record in cleaned:
            for cat in record.get("category", []):
                category_rows.append({
                    'bu': record.get('bu'),
                    'sap_id': record.get('sap_id'),
                    'timestamp': record.get('timestamp'),
                    'zone': record.get('zone'),
                    'region': record.get('region'),
                    'name': record.get('name'),
                    'score': record.get('score'),
                    'national_score': record.get('national_score'),
                    'rank': record.get('rank'),
                    'id': record.get('id'),
                    'created_at': record.get('created_at'),
                    'update_at': record.get('update_at'),
                    'entity_id': record.get('entity_id'),
                    'category_name': cat.get('name'),
                    'category_score': cat.get('score', 0),
                    'category_weightage': cat.get('weightage', 0)
                })

        if not category_rows:
            print("No category data found")
            return None

        df_cat = pl.DataFrame(category_rows, strict=False)
        # Calculate weighted percentage for each category for score based on weightage
        df_cat = df_cat.with_columns(
            (pl.col("category_score") / pl.col("category_weightage") * 100).alias("weighted_percentage")
        )
        # df_cat.write_csv("/home/novexcategory_data.csv")

        print("\nCategory DataFrame:\n", df_cat)
        
        # Aggregate to find average weighted percentage per category per sap_id
        result = df_cat.group_by(["sap_id", "zone", "category_name"]).agg(pl.col("weighted_percentage").mean().alias("avg_percentage"))
        print("result---->",result)

        # Pivot the result to have categories as columns
        df_pivot = result.pivot(
                index=["sap_id", "zone"],
                columns="category_name",
                values="avg_percentage"
        )
        print("the final result---->",df_pivot)

        # total_category_avg = df_pivot.select(pl.all().exclude("sap_id").mean()).to_dict(as_series=False)
        # Get list of metric columns excluding 'sap_id'
        metric_cols = [c for c in df_pivot.columns if c != "sap_id"]

        # Calculate total average across all categories
        total_category_avg = df_pivot.with_columns(
            pl.mean_horizontal(metric_cols).alias("total_avg")
        )
        print("toatal_category_average---->", total_category_avg)
        top3 = total_category_avg.sort("total_avg", descending=True).head(3)

        # Sort ascending for Bottom 3
        bottom3 = total_category_avg.sort("total_avg").head(3)

        print("Top 3\n", top3)
        print("Bottom 3\n", bottom3)

        return top3, bottom3

    except Exception as exc:
            print("\nERROR OCCURRED:")
            traceback.print_exception(type(exc), exc, exc.__traceback__, limit=None, file=None, chain=True)
            return None