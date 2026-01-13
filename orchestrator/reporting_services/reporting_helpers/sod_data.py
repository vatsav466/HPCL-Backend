import urdhva_base
from decimal import Decimal
import decimal
import traceback
import hpcl_ceg_model
import datetime
import pandas as pd
from datetime import date, timedelta
import polars as pl
import numpy as np
import matplotlib.pyplot as plt
import dateutil.parser as dateutil_parser
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


async def get_vts_sod_blocked_counts():
    # Making sure alerts considering only after May 31st in prod
    date = urdhva_base.utilities.get_present_time()
    date_yes = helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                               date_time_format=None)
    month_start = helpers.get_time_stamp_by_delta(date_yes, days=0, with_month_start_day=True,
                                               date_time_format="%Y-%m-%d")
    date_filter = f"created_at::DATE >= '{month_start}' AND created_at::DATE <= '{date_yes.strftime('%Y-%m-%d')}'" # As per HPCL request changed the date to be in the present month
    sod_query = f"""SELECT
                        CASE violation_type
                            WHEN 'route_deviation_count'      THEN 'Route Deviation'
                            WHEN 'power_disconnection_count'  THEN 'Power Disconnection'
                            WHEN 'device_tamper_count'        THEN 'Device Tampering'
                            WHEN 'stoppage_violations_count'  THEN 'Stoppage Violation'
                            WHEN 'night_driving_count'        THEN 'Night Driving Violation'
                            WHEN 'continuous_driving_count'   THEN 'Continuous Driving Violation'
                            WHEN 'speed_violation_count'      THEN 'Speed Violation'
                        END AS "Alert Nature",

                        COUNT(*) FILTER (
                            WHERE alert_section='VTS'
                            AND bu='TAS'
                            AND interlock_name NOT IN ('Itdg Admin Blocked','No VTS No Load')
                            AND {date_filter}
                        ) AS "TTs_Blocked_by_Novex",

                        COUNT(*) FILTER (
                            WHERE alert_section='VTS'
                            AND bu='TAS'
                            AND interlock_name NOT IN ('Itdg Admin Blocked','No VTS No Load')
                            AND {date_filter}
                            AND mark_as_false='true'
                            AND vehicle_unblocked_date IS NOT NULL
                        ) AS "TTs_Manually_Unblocked",

                        COUNT(*) FILTER (
                            WHERE alert_section='VTS'
                            AND bu='TAS'
                            AND interlock_name NOT IN ('Itdg Admin Blocked','No VTS No Load')
                            AND {date_filter}
                            AND mark_as_false='false'
                            AND vehicle_unblocked_date IS NOT NULL
                        ) AS "TTs_Unblocked_as_per_ITDG",

                        COUNT(*) FILTER (
                            WHERE alert_section='VTS'
                            AND bu='TAS'
                            AND interlock_name NOT IN ('Itdg Admin Blocked','No VTS No Load')
                            AND {date_filter}
                            AND vehicle_unblocked_date IS NULL
                        ) AS "TTs_currently_under_Block"

                    FROM alerts
                    WHERE alert_section='VTS'
                    AND bu='TAS'
                    AND interlock_name NOT IN ('Itdg Admin Blocked','No VTS No Load')
                    AND {date_filter}
                    GROUP BY violation_type

                    ORDER BY
                        CASE violation_type
                            WHEN 'route_deviation_count'      THEN 1
                            WHEN 'power_disconnection_count'  THEN 2
                            WHEN 'device_tamper_count'        THEN 3
                            WHEN 'stoppage_violations_count'  THEN 4
                            WHEN 'night_driving_count'        THEN 5
                            WHEN 'continuous_driving_count'   THEN 6
                            WHEN 'speed_violation_count'      THEN 7
                        END;
                """
    
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    sod_blocked_data_resp = await function(query=sod_query)
    sod_blocked_data_resp = pd.DataFrame(sod_blocked_data_resp)
    
    sod_blocked_data_resp = sod_blocked_data_resp.head(-1)
    # Extract values from the first (and only) row safely

    if not sod_blocked_data_resp.empty:
        sod_blocked_data = {
            "TTs_Blocked_by_Novex_SOD": int(sod_blocked_data_resp["TTs_Blocked_by_Novex"].sum()),
            "TTs_Manually_Unblocked_SOD": int(sod_blocked_data_resp["TTs_Manually_Unblocked"].sum()),
            "TTs_currently_under_Block_SOD": int(sod_blocked_data_resp["TTs_currently_under_Block"].sum()),
            "TTs_Auto_Unblocked_SOD": int(sod_blocked_data_resp["TTs_Unblocked_as_per_ITDG"].sum())
        }
    else:
        # Default if no data returned
        sod_blocked_data = {
            "TTs_Blocked_by_Novex_SOD": 0,
            "TTs_Manually_Unblocked_SOD": 0,
            "TTs_currently_under_Block_SOD": 0,
            "TTs_Auto_Unblocked_SOD": 0
        }
    sod_blocked_data_resp.rename(columns={
        "TTs_Blocked_by_Novex": "TTs Blocked by Novex",
        "TTs_Manually_Unblocked": "TTs Manually Unblocked",
        "TTs_Unblocked_as_per_ITDG": "TTs unblocked as per ITDG",
        "TTs_currently_under_Block": "TTs currently under Block"
    }, inplace=True)

    print('*'*200)
    print(sod_blocked_data_resp)
    print('*'*200)

    
    sod_day_wise_trend = await get_sod_day_wise_trends(by_day=True, by_plant=True)
    sod_day_wise_trend_df = pd.DataFrame(sod_day_wise_trend)
    # Ensure correct types
    sod_day_wise_trend_df["timestamp"] = pd.to_datetime(
        sod_day_wise_trend_df["timestamp"]
    )
    # Pivot: Date vs Plant (SAP ID)
    excel_df = sod_day_wise_trend_df.pivot_table(
        index="timestamp",
        columns="name",
        values="score",
        aggfunc="mean"   # safe if duplicates exist
    )

    # Sort by date
    excel_df = excel_df.sort_index()

    # FORMAT DATE AS "Dec 1", "Dec 2"
    excel_df.index = excel_df.index.strftime("%b %d")

    excel_df.index.name = "Day Wise Score"

    # Write to Excel
    global sod_day_wise_trend_exl_path
    output_file = "/tmp/SOD Plant Day Wise Trend.xlsx"
    sod_day_wise_trend_exl_path = output_file
    excel_df.to_excel(
        output_file,
        sheet_name="Day Wise Trend"
    )

    start_date = "2025-06-01"
    end_date = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    time_range = f"{start_date},{end_date}"

    monthly_average_plant_score = await get_sod_day_wise_trends(by_day=False, by_month=True, time_range=time_range)
    monthly_average_plant_score_df = pd.DataFrame(monthly_average_plant_score)
    sod_monthly_score_path = generate_monthly_sod_score_chart(monthly_average_plant_score_df)


    plant_wise_score = await get_sod_day_wise_trends(by_day=False, by_plant=True)
    plant_wise_score_df = pd.DataFrame(plant_wise_score)
    sod_plant_wise_score_df_path = generate_plant_wise_score_chart(plant_wise_score_df)

    return {
        "sod_blocked_data_resp": sod_blocked_data, 
        "sod_blocked_data_resp_violation": sod_blocked_data_resp,
        "sod_monthly_score_path": sod_monthly_score_path, 
        "sod_plant_wise_score_df_path": sod_plant_wise_score_df_path
    }


def convert_decimal(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal(v) for v in obj]
    return obj


def generate_monthly_sod_score_chart(df, output_path="/tmp/sod_monthly_score.png"):
    """
    df columns required:
        - month (YYYY-MM-DD)
        - score (float)

    Output:
        Saves PNG bar chart to /tmp
    """
    global monthly_score_path
    monthly_score_path = output_path
    # Ensure datetime & correct order
    df = df.copy()
    df["month"] = pd.to_datetime(df["month"])
    df = df.sort_values("month")

    # Format month labels like Jun'25
    month_labels = df["month"].dt.strftime("%b'%y")
    scores = df["score"].tolist()

    # Create figure (matches provided image)
    plt.figure(figsize=(10, 5.2))

    bars = plt.bar(
        month_labels,
        df["score"],
        width=0.45,
        color="#0B4F6C"  # exact dark blue shade
    )

    # Title
    plt.title("Monthly Average of Plant Scores", fontsize=12)

    # Y-axis & grid
    plt.ylim(0, 110)
    plt.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.7)

    # Clean borders
    ax = plt.gca()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # No axis labels (same as image)
    plt.xlabel("")
    plt.ylabel("")

    # Add score values on top of bars
    for bar, score in zip(bars, scores):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 2,
            f"{score:.2f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold"
        )

    # Tight layout
    plt.tight_layout()

    # Save PNG
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path


def generate_plant_wise_score_chart(
    df,
    output_path="/tmp/sod_plant_wise_average_score.png"
):
    """
    df columns required:
        - name
        - score
    """
    global plant_wise_score_path
    plant_wise_score_path = output_path

    # Copy & sort descending
    df = df.copy()
    df = df.sort_values("score", ascending=False).reset_index(drop=True)

    x_labels = df["name"].astype(str).tolist()
    scores = pd.to_numeric(df["score"], errors="coerce").fillna(0)

    # ===== Figure (same feel as dry-out chart) =====
    plt.figure(figsize=(17, 9))

    bars = plt.bar(
        x_labels,
        scores,
        width=0.45,              # same bar thickness
        color="#0B4F6C"
    )

    # ===== Title =====
    plt.title("Plant wise Average Score", fontsize=18, pad=20)

    # ===== Y-axis =====
    max_val = scores.max()
    upper_limit = int(np.ceil(max_val / 10.0) * 10)

    plt.ylim(0, upper_limit + 15)
    plt.yticks(
        np.arange(0, upper_limit + 1, 10),
        fontsize=14
    )

    # ===== Grid (same as dry-out chart) =====
    plt.grid(
        axis="y",
        linestyle="--",
        linewidth=0.6,
        alpha=0.5
    )

    # ===== X-axis formatting (KEY FIX) =====
    plt.xticks(
        rotation=90,
        ha="right",
        fontsize=14
    )

    plt.xlabel("Plant Name", fontsize=16, labelpad=20)
    plt.ylabel("", fontsize=14)

    # ===== FULL BOX BORDER (KEY FIX) =====
    ax = plt.gca()
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.2)

    # ===== Value labels on top of bars =====
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            height + 1,
            f"{height:.1f}",
            ha="center",
            va="bottom",
            rotation=90,
            fontsize=14,
            fontweight="bold"
        )

    # ===== Layout & Save =====
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    return output_path




async def get_sod_day_wise_trends(by_plant=False, by_day=True, by_month=False, time_range=None):
    """
    Generates SOD Day wise Trends based on user selection
    :param by_plant:
    :param by_day:
    :param time_range:
    :return:
    """
    start_time = ""
    end_time = ""
    if time_range is None:
        end_time = helpers.get_time_stamp_by_delta(days=1, with_month_start_day=False)
        start_time = helpers.get_time_stamp_by_delta(dateutil_parser.parse(end_time), with_month_start_day=True)
    else:
        start_time = time_range.split(",")[0]
        end_time = time_range.split(",")[1]
    required_keys = []
    group_by_keys = []
    if by_plant:
        required_keys.append('name')
        group_by_keys.append('name')
    if by_month:
        required_keys.append("DATE_TRUNC('month', timestamp)::DATE As month")
        group_by_keys.append('month')
    elif by_day:
        required_keys.append('timestamp::DATE')
        group_by_keys.append('timestamp::DATE')
    group_by = "" if not required_keys else f""" Group by {','.join(group_by_keys)}"""
    required_keys.append('ROUND(AVG(score), 2) as score')
    order_by = ""
    if by_month:
        order_by = "order by month desc"
    elif by_day:
        order_by = "order by timestamp desc"
    elif by_plant:
        order_by = "order by ROUND(AVG(score), 2) desc"
    query = f"""SELECT {','.join(required_keys)} from performance_score_history where timestamp >= '{start_time}'
            AND bu='TAS' AND timestamp <= '{end_time}' {group_by} {order_by}"""
    print(query)
    resp = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
    resp = resp['data']
    for rec in resp:
        for key in rec:
            if isinstance(rec[key], datetime.datetime) or isinstance(rec[key], datetime.date):
                rec[key] = rec[key].strftime("%Y-%m-%d")
            elif isinstance(rec[key], decimal.Decimal):
                rec[key] = float(rec[key])
    return resp



async def sod_percentage():
    try:
        # Making sure alerts considering only after May 31st in prod
        date = urdhva_base.utilities.get_present_time()
        date_yes = helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False, date_time_format=None)
        month_start = helpers.get_time_stamp_by_delta(date_yes, days=0, with_month_start_day=True, date_time_format="%Y-%m-%d")
        date_filter = f"timestamp::DATE >= '{month_start}' AND timestamp::DATE <= '{date_yes.strftime('%Y-%m-%d')}'" # As per HPCL request changed the date to be in the present month
        query = f"""bu='TAS' AND {date_filter}"""

        print("*" * 200)
        print(query)
        print("*" * 200)

        data = await hpcl_ceg_model.PerformanceScoreHistory.get_all(
            urdhva_base.queryparams.QueryParams(q=query, limit=0),
            resp_type="plain"
        )

        if not data or not data.get("data"):
            print("No data found")
            return None

        # Clean Decimal values
        clean_data = convert_decimal(data["data"])

        # Create initial DataFrame
        performance_data = pl.DataFrame(clean_data, strict=False)

        updated_rows = []

        for row in performance_data.iter_rows(named=True):
            categories = row.get("category", [])

            # Copy original row
            new_row = dict(row)

            for category in categories:
                name = category.get("name")
                score = category.get("score", 0)
                weightage = category.get("weightage", 0)

                if weightage > 0:
                    percentage = (score / weightage) * 100
                    #percentage = round((score / weightage) * 100, 2)
                else:
                    percentage = 0

                # Add category percentage as new column
                new_row[name] = percentage

            updated_rows.append(new_row)

        # Final DataFrame with calculated columns
        final_df = pl.DataFrame(updated_rows, strict=False)

        print("*" * 200)
        print("FINAL DATAFRAME")
        print("*" * 200)
        print(final_df)
        previous_date = date.today() - timedelta(days=1)
        avg_scores_df = (
            final_df
            .group_by(["sap_id", "name"])
            .agg([
                pl.mean("VA").alias("avg_va_score"),
                pl.mean("VTS").alias("avg_vts_score"),
                pl.mean("TAS").alias("avg_tas_score"),
                pl.mean("EMLOCK").alias("avg_emlock_score"),
                pl.mean("Dryouts and Carry forward").alias("avg_dryouts_score"),
                pl.mean("score").alias("avg_overall_score"),
            ]).with_columns(pl.col(pl.Float64).round(2))
        )
        print("avg_scores_df---->", avg_scores_df)

        prev_day_score_df = (
            final_df
            .with_columns(pl.col("timestamp").cast(pl.Date))
            .filter(pl.col("timestamp") == pl.lit(previous_date))
            .group_by(["sap_id", "zone"])
            .agg(
                pl.mean("score").round(2).alias("previous_day_score")
            )
        )

        avg_scores_df = (
            avg_scores_df
            .join(prev_day_score_df, on="sap_id", how="left")
            .with_columns(
                pl.col("previous_day_score").fill_null(0)
            )
        )

        avg_scores_df = avg_scores_df.rename({
            "name": "Plant Name", "zone": "Zone", "avg_va_score": "VA", "avg_vts_score": "VTS", "avg_tas_score": "TAS",
            "avg_emlock_score": "EMLOCKS", "avg_dryouts_score": "DRYOUTS & CARRY FORWARD",
            "avg_overall_score": "Average Score from Month start", "previous_day_score": "Previous days score"
        }).drop(["sap_id", "avg_dryouts_score"], strict=False).with_columns(pl.arange(1, pl.len()+ 1).alias("SI No"))

        avg_scores_df = avg_scores_df.select([
            "SI No", "Plant Name", "Zone", "VA", "VTS", "TAS", "EMLOCKS", "DRYOUTS & CARRY FORWARD",
            "Average Score from Month start", "Previous days score"
        ])
        
        avg_scores_df = avg_scores_df.drop("DRYOUTS & CARRY FORWARD")

        top_3_df = (
            avg_scores_df
            .sort("Average Score from Month start", descending=True)
            .head(10).with_columns(pl.arange(1, pl.len() + 1).alias("SI No"))
        )

        bottom_3_df = (
            avg_scores_df
            .sort("Average Score from Month start")
            .head(3).with_columns(pl.arange(1, pl.len() + 1).alias("SI No"))
        )


        print('*'*200)
        print(prev_day_score_df.sort("sap_id"))
        print('top_3_df',top_3_df)
        print('bottom_3_df',bottom_3_df)
        print('*'*200)
        return {"sod_top_data": top_3_df, "sod_bottom_data": bottom_3_df} 

    except Exception as exc:
        print("\nERROR OCCURRED:")
        traceback.print_exception(
            type(exc), exc, exc.__traceback,
            limit=None, chain=True
        )
        return None

