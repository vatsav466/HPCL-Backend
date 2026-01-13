import urdhva_base
import datetime
import pandas as pd
import numpy as np
import urdhva_base.utilities
import matplotlib.pyplot as plt
import utilities.helpers as helpers
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
import orchestrator.reporting_services.lpg_reporting as lpg_reporting


lpg_day_wise_trend_exl_path = ""
monthly_score_path = ""
plant_wise_score_path=""
lpg_va_path = ""
lpg_pq_path = ""


async def get_lpg_rejection():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    query = f""" SELECT count(interlock_name) as total_count FROM alerts where interlock_name in ('O-Ring Leak Rejection','Valve Leak Rejection','Check Scale Rejection') and created_at>='{today}' """
    rejections = await function(query=query)
    if rejections:
        return {"pq_critical_lpg": rejections[-1]["total_count"], "pq_high_lpg": 0}
    return {"pq_critical_lpg": 0, "pq_high_lpg": 0}


async def lpg_top_bottom_score_plants():
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)
    sap_ids = [
        "2662", "2693", "2241", "2935", "2371", "2121", "2520", "2401", "2324", "2811",
        "2435", "2891", "2663", "2314", "2844", "2402", "2455", "2203", "2892", "2504",
        "2248", "2171", "2262", "2655", "2215", "2623", "2204", "2472", "2959", "2921",
        "2330", "2126", "2947", "2539", "2777", "2507", "2829", "2779", "2373", "2657",
        "2949", "2173", "2707", "2568", "2659", "2792", "2660", "2692", "2471", "2731",
        "2630", "2408", "2316", "2117", "2732"
    ]
    sap_ids_str = ", ".join([f"'{sid}'" for sid in sap_ids])
    top_query = f"""WITH plant_avg_scores AS (
                        SELECT
                            sap_id,
                            name AS "Plant Name",
                            zone AS "Zone",
                            region AS "Region",
                            AVG(score) AS avg_score
                        FROM public.performance_score_history
                        WHERE
                            bu = 'LPG'
                            AND zone != ''
                            AND region != ''
                            AND timestamp::DATE >= CASE
                                WHEN date_trunc('day', CURRENT_DATE) = date_trunc('month', CURRENT_DATE)
                                    THEN date_trunc('month', CURRENT_DATE - INTERVAL '1 month')
                                ELSE date_trunc('month', CURRENT_DATE)
                            END
                            AND timestamp::DATE < CURRENT_DATE
                            AND sap_id IN ({sap_ids_str})
                            AND name NOT ILIKE '%RO%'
                        GROUP BY sap_id, name, zone, region
                    ),
                    previous_day_scores AS (
                        SELECT
                            sap_id,
                            ROUND(AVG(score)::numeric, 2) AS prev_day_score
                        FROM public.performance_score_history
                        WHERE
                            bu = 'LPG'
                            AND timestamp::DATE = CURRENT_DATE - INTERVAL '1 day'
                        GROUP BY sap_id
                    )
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY p.avg_score DESC) AS "Sl No",
                        p."Plant Name",
                        p."Zone",
                        p."Region",
                        ROUND(p.avg_score::numeric, 2) AS "Average Score from Month start",
                        COALESCE(pd.prev_day_score, 0) AS "Previous days score"
                    FROM plant_avg_scores p
                    LEFT JOIN previous_day_scores pd
                        ON p.sap_id = pd.sap_id
                    ORDER BY p.avg_score DESC
                    LIMIT 3"""
    
    bottom_query = f"""WITH plant_avg_scores AS (
                        SELECT
                            sap_id,
                            name AS "Plant Name",
                            zone AS "Zone",
                            region AS "Region",
                            AVG(score) AS avg_score
                        FROM public.performance_score_history
                        WHERE
                            bu = 'LPG'
                            AND zone != ''
                            AND region != ''
                            AND timestamp::DATE >= CASE
                                WHEN date_trunc('day', CURRENT_DATE) = date_trunc('month', CURRENT_DATE)
                                    THEN date_trunc('month', CURRENT_DATE - INTERVAL '1 month')
                                ELSE date_trunc('month', CURRENT_DATE)
                            END
                            AND timestamp::DATE < CURRENT_DATE
                            AND sap_id IN ({sap_ids_str})
                            AND name NOT ILIKE '%RO%'
                        GROUP BY sap_id, name, zone, region
                    ),
                    previous_day_scores AS (
                        SELECT
                            sap_id,
                            ROUND(AVG(score)::numeric, 2) AS prev_day_score
                        FROM public.performance_score_history
                        WHERE
                            bu = 'LPG'
                            AND timestamp::DATE = CURRENT_DATE - INTERVAL '1 day'
                        GROUP BY sap_id
                    )
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY p.avg_score ASC) AS "Sl No",
                        p."Plant Name",
                        p."Zone",
                        p."Region",
                        ROUND(p.avg_score::numeric, 2) AS "Average Score from Month start",
                        COALESCE(pd.prev_day_score, 0) AS "Previous days score"
                    FROM plant_avg_scores p
                    LEFT JOIN previous_day_scores pd
                        ON p.sap_id = pd.sap_id
                    ORDER BY p.avg_score ASC
                    LIMIT 3"""
    lpg_avg_score_query = f"""SELECT
                            ROUND(AVG(score)::numeric, 2) AS lpg_average_score
                        FROM public.performance_score_history
                        WHERE sap_id IN ({sap_ids_str})
                        AND timestamp::DATE = CURRENT_DATE - INTERVAL '1 day'"""
    lpg_avg_score_resp = await function(query=lpg_avg_score_query)
    top_resp = await function(query=top_query)
    bottom_resp = await function(query=bottom_query)
    lpg_avg_score_resp = pd.DataFrame(lpg_avg_score_resp)
    if not lpg_avg_score_resp.empty:
        lpg_avg_score_value = lpg_avg_score_resp['lpg_average_score'].iloc[0]
    else:
        lpg_avg_score_value = None  # or 0 or 'N/A'
    top_resp = pd.DataFrame(top_resp)
    bottom_resp = pd.DataFrame(bottom_resp)
    return {"lpg_top_data": top_resp, "lpg_bottom_data": bottom_resp, "lpg_avg_score_resp": lpg_avg_score_value}


def generate_monthly_lpg_score_chart(df, output_path="/tmp/lpg_monthly_score.png"):
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
    output_path="/tmp/lpg_plant_wise_average_score.png"
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


async def get_va_path():
    date = urdhva_base.utilities.get_present_time()

    date_yes = helpers.get_time_stamp_by_delta(
        date, days=1, with_month_start_day=False, date_time_format=None
    )

    month_start = helpers.get_time_stamp_by_delta(
        date_yes, days=0, with_month_start_day=True, date_time_format=None
    )

    date_filter = (
        f"created_at::DATE >= '{month_start.strftime('%Y-%m-%d')}' "
        f"AND created_at::DATE <= '{date_yes.strftime('%Y-%m-%d')}'"
    )

    query = f"""
        SELECT
            location_name AS "Plant Wise VA Alerts",
            COUNT(*) FILTER (WHERE severity = 'Critical') AS "Critical",
            COUNT(*) FILTER (WHERE severity = 'High') AS "High",
            1 AS sort_order
        FROM alerts
        WHERE alert_status = 'Open'
        AND alert_section = 'VA'
        AND {date_filter}
        AND bu = 'LPG'
        AND location_name != ''
        GROUP BY location_name

        UNION ALL

        SELECT
            'Total',
            COUNT(*) FILTER (WHERE severity = 'Critical'),
            COUNT(*) FILTER (WHERE severity = 'High'),
            2 AS sort_order
        FROM alerts
        WHERE alert_status = 'Open'
        AND alert_section = 'VA'
        AND bu = 'LPG'
        AND location_name != ''
        AND {date_filter}

        ORDER BY sort_order
    """

    Charts_Connection_Vault_RoutingParams.connection_id = (
        connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    )
    Charts_Connection_Vault_RoutingParams.action = "execute_query"

    function = await charts_connection_vault_routing(
        Charts_Connection_Vault_RoutingParams
    )
    resp = await function(query=query)

    df = pd.DataFrame(resp)

    # Remove helper column
    df = df.drop(columns=["sort_order"])

    global lpg_va_path
    lpg_va_path = "/tmp/Plant Wise VA Alerts.xlsx"

    with pd.ExcelWriter(lpg_va_path, engine="xlsxwriter") as writer:
        df.to_excel(
            writer,
            sheet_name="Plant Wise VA Alerts",
            index=False,
            startrow=1,
            header=False   #important
        )

        workbook = writer.book
        worksheet = writer.sheets["Plant Wise VA Alerts"]

        header_format = workbook.add_format({
            "bold": True,
            "align": "center",
            "valign": "middle",
            "border": 1
        })

        # Write header ONCE
        for col_num, col_name in enumerate(df.columns):
            worksheet.write(0, col_num, col_name, header_format)
            worksheet.set_column(col_num, col_num, 30)

    return lpg_va_path


async def get_pq_path():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    query = f"""
        SELECT
            location_name AS "Plant Wise PQ Alerts",
            COUNT(*) FILTER (WHERE severity = 'Critical') AS "Critical",
            COUNT(*) FILTER (WHERE severity = 'High') AS "High",
            1 AS sort_order
        FROM alerts
        WHERE alert_section = 'LPG'
        AND created_at>='{today}'
        AND interlock_name IN (
            'O-Ring Leak Rejection',
            'Valve Leak Rejection',
            'Check Scale Rejection'
        )
        GROUP BY location_name

        UNION ALL

        SELECT
            'Total',
            COUNT(*) FILTER (WHERE severity = 'Critical'),
            COUNT(*) FILTER (WHERE severity = 'High'),
            2 AS sort_order
        FROM alerts
        WHERE alert_section = 'LPG'
        AND created_at>='{today}'
        AND interlock_name IN (
            'O-Ring Leak Rejection',
            'Valve Leak Rejection',
            'Check Scale Rejection'
        )
        ORDER BY sort_order
    """

    Charts_Connection_Vault_RoutingParams.connection_id = (
        connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    )
    Charts_Connection_Vault_RoutingParams.action = "execute_query"

    function = await charts_connection_vault_routing(
        Charts_Connection_Vault_RoutingParams
    )
    resp = await function(query=query)

    df = pd.DataFrame(resp)

    # Drop helper column
    df = df.drop(columns=["sort_order"])

    global lpg_pq_path
    lpg_pq_path = "/tmp/Plant Wise PQ Alerts.xlsx"

    with pd.ExcelWriter(lpg_pq_path, engine="xlsxwriter") as writer:
        df.to_excel(
            writer,
            sheet_name="Plant Wise PQ Alerts",
            index=False,
            startrow=1,
            header=False   # IMPORTANT
        )

        workbook = writer.book
        worksheet = writer.sheets["Plant Wise PQ Alerts"]

        header_format = workbook.add_format({
            "bold": True,
            "align": "center",
            "valign": "middle",
            "border": 1
        })

        # Write header ONCE
        for col_num, col_name in enumerate(df.columns):
            worksheet.write(0, col_num, col_name, header_format)
            worksheet.set_column(col_num, col_num, 30)

    return lpg_pq_path


async def get_vts_lpg_blocked_counts():
    # Making sure alerts considering only after May 31st in prod
    date = urdhva_base.utilities.get_present_time()
    date_yes = helpers.get_time_stamp_by_delta(date, days=1, with_month_start_day=False,
                                               date_time_format=None)
    month_start = helpers.get_time_stamp_by_delta(date_yes, days=0, with_month_start_day=True,
                                               date_time_format="%Y-%m-%d")
    date_filter = f"created_at::DATE >= '{month_start}' AND created_at::DATE <= '{date_yes.strftime('%Y-%m-%d')}'" # As per HPCL request changed the date to be in the present month
    lpg_query = f"""SELECT
                        CASE violation_type
                            WHEN 'route_deviation_count'      THEN 'Route Deviation'
                            WHEN 'main_supply_removal_count'  THEN 'Power Disconnection'
                            WHEN 'device_tamper_count'        THEN 'Device Tampering'
                            WHEN 'stoppage_violations_count'  THEN 'Stoppage Violation'
                            WHEN 'night_driving_count'        THEN 'Night Driving Violation'
                            WHEN 'continuous_driving_count'   THEN 'Continuous Driving Violation'
                            WHEN 'speed_violation_count'      THEN 'Speed Violation'
                        END AS "Alert Nature",

                        COUNT(*) FILTER (
                            WHERE alert_section='VTS'
                            AND bu='LPG'
                            AND interlock_name NOT IN ('Itdg Admin Blocked','No VTS No Load')
                            AND {date_filter}
                        ) AS "TTs_Blocked_by_Novex",

                        COUNT(*) FILTER (
                            WHERE alert_section='VTS'
                            AND bu='LPG'
                            AND interlock_name NOT IN ('Itdg Admin Blocked','No VTS No Load')
                            AND {date_filter}
                            AND mark_as_false='true'
                            AND vehicle_unblocked_date IS NOT NULL
                        ) AS "TTs_Manually_Unblocked",

                        COUNT(*) FILTER (
                            WHERE alert_section='VTS'
                            AND bu='LPG'
                            AND interlock_name NOT IN ('Itdg Admin Blocked','No VTS No Load')
                            AND {date_filter}
                            AND mark_as_false='false'
                            AND vehicle_unblocked_date IS NOT NULL
                        ) AS "TTs_Unblocked_as_per_ITDG",

                        COUNT(*) FILTER (
                            WHERE alert_section='VTS'
                            AND bu='LPG'
                            AND interlock_name NOT IN ('Itdg Admin Blocked','No VTS No Load')
                            AND {date_filter}
                            AND vehicle_unblocked_date IS NULL
                        ) AS "TTs_currently_under_Block"

                    FROM alerts
                    WHERE alert_section='VTS'
                    AND bu='LPG'
                    AND interlock_name NOT IN ('Itdg Admin Blocked','No VTS No Load')
                    AND {date_filter}
                    GROUP BY violation_type

                    ORDER BY
                        CASE violation_type
                            WHEN 'route_deviation_count'      THEN 1
                            WHEN 'main_supply_removal_count'  THEN 2
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
    lpg_blocked_data_resp = await function(query=lpg_query)
    lpg_blocked_data_resp = pd.DataFrame(lpg_blocked_data_resp)
    # Extract values from the first (and only) row safely
    if not lpg_blocked_data_resp.empty:
        lpg_blocked_data = {
            "TTs_Blocked_by_Novex_LPG": int(lpg_blocked_data_resp["TTs_Blocked_by_Novex"].sum()),
            "TTs_Manually_Unblocked_LPG": int(lpg_blocked_data_resp["TTs_Manually_Unblocked"].sum()),
            "TTs_currently_under_Block_LPG": int(lpg_blocked_data_resp["TTs_currently_under_Block"].sum()),
            "TTs_Auto_Unblocked_LPG": int(lpg_blocked_data_resp["TTs_Unblocked_as_per_ITDG"].sum())
        }
    else:
        # Default if no data returned
        lpg_blocked_data = {
            "TTs_Blocked_by_Novex_LPG": 0,
            "TTs_Manually_Unblocked_LPG": 0,
            "TTs_currently_under_Block_LPG": 0,
            "TTs_Auto_Unblocked_LPG": 0
        }
    lpg_blocked_data_resp.rename(columns={
        "TTs_Blocked_by_Novex": "TTs Blocked by Novex",
        "TTs_Manually_Unblocked": "TTs Manually Unblocked",
        "TTs_Unblocked_as_per_ITDG": "TTs unblocked as per ITDG",
        "TTs_currently_under_Block": "TTs currently under Block"
    }, inplace=True)

    print('*'*200)
    print(lpg_blocked_data_resp)
    print('*'*200)

    
    lpg_day_wise_trend = await lpg_reporting.get_lpg_day_wise_trends(by_day=True, by_plant=True)
    lpg_day_wise_trend_df = pd.DataFrame(lpg_day_wise_trend)
    # Ensure correct types
    lpg_day_wise_trend_df["timestamp"] = pd.to_datetime(
        lpg_day_wise_trend_df["timestamp"]
    )
    # Pivot: Date vs Plant (SAP ID)
    excel_df = lpg_day_wise_trend_df.pivot_table(
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

    # Write to Exce
    global lpg_day_wise_trend_exl_path
    output_file = "/tmp/LPG Plant Day Wise Trend.xlsx"
    lpg_day_wise_trend_exl_path = output_file
    excel_df.to_excel(
        output_file,
        sheet_name="Day Wise Trend"
    )

    start_date = "2025-06-01"
    end_date = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    time_range = f"{start_date},{end_date}"

    monthly_average_plant_score = await lpg_reporting.get_lpg_day_wise_trends(by_day=False, by_month=True, time_range=time_range)
    monthly_average_plant_score_df = pd.DataFrame(monthly_average_plant_score)
    lpg_monthyl_score_path = generate_monthly_lpg_score_chart(monthly_average_plant_score_df)


    plant_wise_score = await lpg_reporting.get_lpg_day_wise_trends(by_day=False, by_plant=True)
    plant_wise_score_df = pd.DataFrame(plant_wise_score)
    plant_wise_score_df_path = generate_plant_wise_score_chart(plant_wise_score_df)

    zone_wise_cylinder_count = await lpg_reporting.get_zone_wise_cylinder_backlog()
    zone_wise_cylinder_count_df = pd.DataFrame(zone_wise_cylinder_count)

    await get_va_path()
    await get_pq_path()

    return {
        "lpg_blocked_data_resp":lpg_blocked_data, 
        "lpg_blocked_data_resp_violation": lpg_blocked_data_resp,
        "zone_wise_cylinder_count_df": zone_wise_cylinder_count_df,
        "lpg_monthyl_score_path" : lpg_monthyl_score_path,
        "plant_wise_score_df_path" : plant_wise_score_df_path,
        "lpg_day_wise_trend_exl_path": lpg_day_wise_trend_exl_path,
        "lpg_va_path": lpg_va_path,
        "lpg_pq_path": lpg_pq_path
    }