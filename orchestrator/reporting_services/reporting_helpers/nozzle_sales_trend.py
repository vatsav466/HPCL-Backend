import os

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import urdhva_base
from charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams

import utilities.connection_mapping as connection_mapping


async def plot_ms_sales_trend(
    trend_data: pl.DataFrame, output_path="/tmp/nozzle_trend_chart.png"
):

    if trend_data is None or trend_data.is_empty():
        raise ValueError("trend_data cannot be empty")

    # -----------------------------
    # PREP DATA
    # -----------------------------

    df = trend_data.with_columns(
        [
            pl.col("transaction_date").dt.strftime("%d-%b").alias("day"),
            (
                (
                    pl.col("ms_power").cast(pl.Float64)
                    / pl.col("ms_total").cast(pl.Float64)
                )
                * 100
            ).alias("conversion"),
        ]
    )
    print("data ---->\n", df)

    # Remove nulls
    df = df.filter(pl.col("ms_total").is_not_null() & pl.col("ms_power").is_not_null())
    print("remove nulls data ---->\n", df)

    # Convert Decimal → Float
    df = df.with_columns(
        [
            pl.col("ms_total").cast(pl.Float64),
            pl.col("ms_power").cast(pl.Float64),
            pl.col("conversion").cast(pl.Float64),
        ]
    )
    print("convert to float ---->\n", df)

    # Clamp conversion to avoid extreme values
    df = df.with_columns(
        [
            pl.when(pl.col("conversion") > 100)
            .then(100)
            .otherwise(pl.col("conversion"))
            .alias("conversion")
        ]
    )
    print("conversion to avoid extreme values ----->\n", df)

    # -----------------------------
    # NUMPY ARRAYS (SAFE)
    # -----------------------------
    days = df["day"].to_numpy()

    ms_total = np.nan_to_num(df["ms_total"].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)
    ms_power = np.nan_to_num(df["ms_power"].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)
    conversion = np.nan_to_num(
        df["conversion"].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0
    )

    x = np.arange(len(days))

    # -----------------------------
    # AVERAGES
    # -----------------------------
    avg_total = float(np.mean(ms_total)) if len(ms_total) > 0 else 0
    avg_conversion = float(np.mean(conversion)) if len(conversion) > 0 else 0

    # -----------------------------
    # FIGURE (SAFE SIZE)
    # -----------------------------
    fig, ax1 = plt.subplots(figsize=(14, 5))

    # -----------------------------
    # BARS
    # -----------------------------
    ax1.bar(x - 0.2, ms_total, width=0.4, color="#5b7db1", label="MS Total")
    ax1.bar(x + 0.2, ms_power, width=0.4, color="#c9c9c9", label="MS Power")

    # -----------------------------
    # LINE
    # -----------------------------
    ax2 = ax1.twinx()
    ax2.plot(
        x, conversion, marker="o", color="#d4aa00", linewidth=2, label="MS % Conversion"
    )

    # -----------------------------
    # AXES
    # -----------------------------
    ax1.set_xticks(x)
    # ax1.set_xticklabels(days)
    ax1.set_xticklabels(days, rotation=45)

    ax2.set_ylim(0, 25)
    ticks = np.arange(0, 26, 5)

    ax2.set_yticks(ticks)
    ax2.set_yticklabels([f"{int(t)}%" for t in ticks])

    # -----------------------------
    # AVERAGE LINES
    # -----------------------------
    ax1.axhline(avg_total, linestyle="--", color="#bfbfbf")
    ax2.axhline(avg_conversion, linestyle=":", color="#d4aa00")

    # -----------------------------
    # LABELS
    # -----------------------------
    offset = max(ms_total) * 0.02 if len(ms_total) > 0 else 1

    for i, v in enumerate(ms_total):
        ax1.text(i - 0.2, v + offset, f"{int(v)}", fontsize=7, ha="center")

    for i, v in enumerate(ms_power):
        ax1.text(i + 0.2, v + offset, f"{int(v)}", fontsize=7, ha="center")

    for i, v in enumerate(conversion):
        # if i % 2 == 0:
        ax2.text(i, float(v) + 0.3, f"{float(v):.1f}%", fontsize=8, ha="center")

    # -----------------------------
    # STYLE
    # -----------------------------
    ax1.grid(axis="y", linestyle="--", alpha=0.3)

    for spine in ["top", "right"]:
        ax1.spines[spine].set_visible(False)
        ax2.spines[spine].set_visible(False)

    start_date = df["transaction_date"].min()
    end_date = df["transaction_date"].max()

    start_label = start_date.strftime("%d-%b")
    end_label = end_date.strftime("%d-%b")
    plt.title(f"MS Total vs Power with Conversion % ({start_label} to {end_label})")

    fig.legend(loc="upper left", bbox_to_anchor=(0.01, 0.90), ncol=3, frameon=False)
    plt.tight_layout(rect=[0, 0, 1, 0.92])

    # -----------------------------
    # SAVE
    # -----------------------------
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Graph saved at: {output_path}")
    return output_path


async def fetch_data():

    nozzle_sales_query_avg = f"""
                        WITH base AS (
                        SELECT
                            "transaction_date",

                            SUM("sales_volume") FILTER (WHERE product_grp = 'MS') AS ms,
                            SUM("sales_volume") FILTER (WHERE product_grp IN ('POWER 99','POWER 95','POWER 100')) AS power,
                            SUM("sales_volume") FILTER (WHERE product_grp = 'HSD') AS hsd,
                            SUM("sales_volume") FILTER (WHERE product_grp = 'TURBO') AS turbo

                        FROM "public".nozzle_sales
                        WHERE "transaction_date" >= DATE '2026-03-01'
                        GROUP BY "transaction_date"
                    ),

                    mar AS (
                        SELECT
                            ROUND((((AVG(ms))/1411.0)/0.89), 2) AS ms,
                            ROUND((((AVG(power))/1411.0)/0.89), 2) AS power,
                            ROUND((((AVG(hsd))/1210.0)/0.89), 2) AS hsd,
                            ROUND((((AVG(turbo))/1210.0)/0.89), 2) AS turbo
                        FROM base
                        WHERE "transaction_date" BETWEEN DATE '2026-03-01' AND DATE '2026-03-19'
                    ),

                    apr AS (
                        SELECT
                            ROUND((((AVG(ms))/1411.0)/0.89), 2) AS ms,
                            ROUND((((AVG(power))/1411.0)/0.89), 2) AS power,
                            ROUND((((AVG(hsd))/1210.0)/0.89), 2) AS hsd,
                            ROUND((((AVG(turbo))/1210.0)/0.89), 2) AS turbo
                        FROM base
                        WHERE "transaction_date" BETWEEN DATE '2026-03-20' AND DATE '2026-03-31'
                    ),

                    yday AS (
                        SELECT
                            ROUND((((AVG(ms))/1411.0)/0.89), 2) AS ms,
                            ROUND((((AVG(power))/1411.0)/0.89), 2) AS power,
                            ROUND((((AVG(hsd))/1210.0)/0.89), 2) AS hsd,
                            ROUND((((AVG(turbo))/1210.0)/0.89), 2) AS turbo
                        FROM base
                        WHERE "transaction_date" BETWEEN DATE '2026-04-01' AND CURRENT_DATE - INTERVAL '1 day'
                    )

                    SELECT
                        -- ================= MS =================
                        ROUND(mar.ms,1) AS "MS-R Normal (Mar1-19)",
                        ROUND(apr.ms,1) AS "MS-R Normal (Mar20-31)",
                        ROUND(yday.ms,1) AS "MS-R Normal (1 Apr-Yday)",

                        ROUND(mar.power,1) AS "MS-R Branded (Mar1-19)",
                        ROUND(apr.power,1) AS "MS-R Branded (Mar20-31)",
                        ROUND(yday.power,1) AS "MS-R Branded (1 Apr-Yday)",

                        ROUND((mar.power / NULLIF(mar.ms + mar.power, 0)) * 100, 1) AS "MS % (Mar1-19)",
                        ROUND((apr.power / NULLIF(apr.ms + apr.power, 0)) * 100, 1) AS "MS % (Mar20-31)",
                        ROUND((yday.power / NULLIF(yday.ms + yday.power, 0)) * 100, 1) AS "MS % (1 Apr-Yday)",

                        ROUND(mar.ms + mar.power, 1) AS "MS Total (Mar1-19)",
                        ROUND(apr.ms + apr.power, 1) AS "MS Total (Mar20-31)",
                        ROUND(yday.ms + yday.power, 1) AS "MS Total (1 Apr-Yday)",

                        -- ================= HSD =================
                        ROUND(mar.hsd,1) AS "HSD-R Normal (Mar1-19)",
                        ROUND(apr.hsd,1) AS "HSD-R Normal (Mar20-31)",
                        ROUND(yday.hsd,1) AS "HSD-R Normal (1 Apr-Yday)",

                        ROUND(mar.turbo,1) AS "HSD-R Branded (Mar1-19)",
                        ROUND(apr.turbo,1) AS "HSD-R Branded (Mar20-31)",
                        ROUND(yday.turbo,1) AS "HSD-R Branded (1 Apr-Yday)",

                        ROUND((mar.turbo / NULLIF(mar.hsd + mar.turbo, 0)) * 100, 1) AS "HSD % (Mar1-19)",
                        ROUND((apr.turbo / NULLIF(apr.hsd + apr.turbo, 0)) * 100, 1) AS "HSD % (Mar20-31)",
                        ROUND((yday.turbo / NULLIF(yday.hsd + yday.turbo, 0)) * 100, 1) AS "HSD % (1 Apr-Yday)",

                        ROUND(mar.hsd + mar.turbo, 1) AS "HSD Total (Mar1-19)",
                        ROUND(apr.hsd + apr.turbo, 1) AS "HSD Total (Mar20-31)",
                        ROUND(yday.hsd + yday.turbo, 1) AS "HSD Total (1 Apr-Yday)"

                    FROM mar, apr, yday;
                    """

    nozzle_trend_query = """
                SELECT
                    transaction_date,
                    ROUND(((SUM("sales_volume") FILTER (WHERE product_grp in ('MS','POWER 99','POWER 95','POWER 100'))/ 1411.0
                            ) / 1000.0
                        ) / 0.89, 2
                        ) AS ms_total,
                    ROUND(((SUM("sales_volume") FILTER (WHERE product_grp in ('POWER 99','POWER 95','POWER 100'))/ 1411.0
                            ) / 1000.0
                        ) / 0.89, 2
                        ) AS ms_power
                FROM public.nozzle_sales
                WHERE transaction_date >= CURRENT_DATE - INTERVAL '30 days'
                    AND transaction_date < CURRENT_DATE
                GROUP BY transaction_date

            """
    nozzle_sync_time_query = (
        """ SELECT MAX(created_at::timestamp) as sync_time FROM nozzle_sales """
    )
    Charts_Connection_Vault_RoutingParams.connection_id = (
        connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    )
    Charts_Connection_Vault_RoutingParams.action = "execute_query"
    function = await charts_connection_vault_routing(
        Charts_Connection_Vault_RoutingParams
    )

    nozzle_sales_avg = await function(query=nozzle_sales_query_avg)
    # nozzle_sales_avg_df = pl.DataFrame(nozzle_sales_avg)
    nozzle_sales_avg_df = pl.DataFrame(nozzle_sales_avg).with_columns(
        [pl.all().cast(pl.Float64)]
    )
    print(
        "nozzle_sales_avg_df = pd.DataFrame(nozzle_sales_avg) ---->\n",
        nozzle_sales_avg_df,
    )
    print("nozzle ---->\n", nozzle_sales_avg_df.to_dicts()[0])
    nozzle_trend = await function(query=nozzle_trend_query)
    nozzle_trend_df = pl.DataFrame(nozzle_trend)
    print("nozzle trend data----> \n", nozzle_trend_df)

    nozzle_trend_chart = await plot_ms_sales_trend(nozzle_trend_df)
    print("nozzle trend chart --->\n", nozzle_trend_chart)

    nozzle_sync_time = await function(query=nozzle_sync_time_query)
    nozzle_sync_time = pl.DataFrame(nozzle_sync_time)
    nozzle_sync_time = nozzle_sync_time.with_columns(
        pl.col("sync_time")
        .dt.replace_time_zone("UTC")
        .dt.convert_time_zone("Asia/Kolkata")
        .dt.strftime("%-I:%M %p")
        .alias("nozzle_sales_sync")
    )
    print("nozzle_sync_time -------------->\n", nozzle_sync_time.to_dicts())

    return {
        "nozzle_sales_avg_df": nozzle_sales_avg_df.to_dicts()[0],
        "nozzle_trend_chart": nozzle_trend_chart,
        "nozzle_sales_sync_time": nozzle_sync_time["nozzle_sales_sync"][0],
    }


async def nozzles_sales_top_performance():

    nozzle_sales_top_query = f""" 
                                SELECT
                                    zone,
                                    region,
                                    sales_area,
                                    sap_id,
                                    location_name,

                                    /* ================= CURRENT MONTH ================= */

                                    ROUND(
                                        SUM(sales_volume) FILTER (
                                            WHERE product_grp IN ('POWER 99', 'POWER 95', 'POWER 100')
                                            AND transaction_date >= 
                                                CASE
                                                    WHEN CURRENT_DATE = date_trunc('month', CURRENT_DATE)::date
                                                    THEN date_trunc('month', CURRENT_DATE - INTERVAL '1 month')
                                                    ELSE date_trunc('month', CURRENT_DATE)
                                                END
                                            AND transaction_date <
                                                CASE
                                                    WHEN CURRENT_DATE = date_trunc('month', CURRENT_DATE)::date
                                                    THEN date_trunc('month', CURRENT_DATE)
                                                    ELSE CURRENT_DATE
                                                END
                                        ) / 1000.0,
                                        2
                                    ) AS current_power_kl,

                                    ROUND(
                                        SUM(sales_volume) FILTER (
                                            WHERE product_grp IN ('MS')
                                            AND transaction_date >= 
                                                CASE
                                                    WHEN CURRENT_DATE = date_trunc('month', CURRENT_DATE)::date
                                                    THEN date_trunc('month', CURRENT_DATE - INTERVAL '1 month')
                                                    ELSE date_trunc('month', CURRENT_DATE)
                                                END
                                            AND transaction_date <
                                                CASE
                                                    WHEN CURRENT_DATE = date_trunc('month', CURRENT_DATE)::date
                                                    THEN date_trunc('month', CURRENT_DATE)
                                                    ELSE CURRENT_DATE
                                                END
                                        ) / 1000.0,
                                        2
                                    ) AS current_ms_kl,

                                    /* ================= LAST MONTH ================= */

                                    ROUND(
                                        SUM(sales_volume) FILTER (
                                            WHERE product_grp IN ('POWER 99', 'POWER 95', 'POWER 100')
                                            AND transaction_date >= 
                                                CASE
                                                    WHEN EXTRACT(MONTH FROM CURRENT_DATE) >= 4
                                                    THEN date_trunc('year', CURRENT_DATE) + INTERVAL '3 month'
                                                    ELSE date_trunc('year', CURRENT_DATE - INTERVAL '1 year') + INTERVAL '3 month'
                                                END
                                            AND transaction_date < CURRENT_DATE
                                        ) / 1000.0,
                                        2
                                    ) AS ytd_power_kl,

                                    ROUND(
                                        SUM(sales_volume) FILTER (
                                            WHERE product_grp = 'MS'
                                            AND transaction_date >= 
                                                CASE
                                                    WHEN EXTRACT(MONTH FROM CURRENT_DATE) >= 4
                                                    THEN date_trunc('year', CURRENT_DATE) + INTERVAL '3 month'
                                                    ELSE date_trunc('year', CURRENT_DATE - INTERVAL '1 year') + INTERVAL '3 month'
                                                END
                                            AND transaction_date < CURRENT_DATE
                                        ) / 1000.0,
                                        2
                                    ) AS ytd_ms_kl,

                                    CASE
                                        WHEN CURRENT_DATE = date_trunc('month', CURRENT_DATE)::date THEN
                                            TO_CHAR(date_trunc('month', CURRENT_DATE - INTERVAL '1 month'), 'Mon''YY')
                                        ELSE
                                            TO_CHAR(date_trunc('month', CURRENT_DATE), 'FMDDth') || ' to ' ||
                                            TO_CHAR(CURRENT_DATE - INTERVAL '1 day', 'FMDDth Mon''YY')
                                    END AS current_date_label,

                                    TO_CHAR(
                                        CASE
                                            WHEN EXTRACT(MONTH FROM CURRENT_DATE) >= 4
                                            THEN date_trunc('year', CURRENT_DATE) + INTERVAL '3 month'
                                            ELSE date_trunc('year', CURRENT_DATE - INTERVAL '1 year') + INTERVAL '3 month'
                                        END,
                                        'DD Mon''YY'
                                    ) || ' to ' ||
                                    TO_CHAR(CURRENT_DATE - INTERVAL '1 day', 'DD Mon''YY') 
                                    AS financial_year_label

                                FROM nozzle_sales
                                WHERE zone is not Null
                                GROUP BY
                                    zone,
                                    region,
                                    sales_area,
                                    sap_id,
                                    location_name;
                        """

    Charts_Connection_Vault_RoutingParams.connection_id = (
        connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    )
    Charts_Connection_Vault_RoutingParams.action = "execute_query"
    function = await charts_connection_vault_routing(
        Charts_Connection_Vault_RoutingParams
    )
    nozzle_sales = await function(query=nozzle_sales_top_query)
    nozzle_sales_df = pl.DataFrame(nozzle_sales)
    print(
        "nozzle_sales_top_df = pd.DataFrame(nozzle_sales_top_bottom) ---->\n",
        nozzle_sales_df.head(5),
    )
    print("count of records in nozzle_sales_top_df ---->\n", nozzle_sales_df.shape[0])

    location_details_query = f"""SELECT DISTINCT sap_id, zone, region, sales_area, name FROM location_master where bu = 'RO' """
    location_data = await urdhva_base.BasePostgresModel.get_aggr_data(
        location_details_query, limit=0
    )
    loc_df = pl.DataFrame(location_data["data"])

    nozzle_sales_df = nozzle_sales_df.join(loc_df, on="sap_id", how="left")
    print("completed the joining with lm")

    # nozzle_sales_top_df = nozzle_sales_df.filter(
    #     (pl.col("current_ms_kl").is_not_null()) &
    #     (pl.col("current_ms_kl") != 0)
    # )

    labels = (
        nozzle_sales_df.select(["current_date_label", "financial_year_label"])
        .unique()
        .to_dicts()[0]
    )
    print("labels ---->\n", labels)

    nozzle_sales_top_df = nozzle_sales_df.filter(pl.col("zone").is_not_null())

    nozzle_sales_top_df = nozzle_sales_top_df.group_by(
        ["zone", "region", "sales_area", "location_name", "sap_id"]
    ).agg(
        [
            pl.sum("current_ms_kl").alias("current_ms_kl"),
            pl.sum("current_power_kl").alias("current_power_kl"),
            (pl.sum("current_ms_kl") + pl.sum("current_power_kl")).alias(
                "current_ms_total_kl"
            ),
            pl.sum("ytd_power_kl").alias("ytd_power_kl"),
            pl.sum("ytd_ms_kl").alias("ytd_ms_kl"),
            (pl.sum("ytd_power_kl") + pl.sum("ytd_ms_kl")).alias("ytd_ms_total_kl"),
        ]
    )

    nozzle_sales_top_df = nozzle_sales_top_df.group_by(
        ["zone", "region", "sales_area", "location_name", "sap_id"]
    ).agg(
        current_power_kl=pl.col("current_power_kl").sum(),
        current_ms_total_kl=pl.col("current_ms_total_kl").sum(),
        current_conversion_pct=(
            pl.col("current_power_kl").sum() / pl.col("current_ms_total_kl").sum()
        )
        * 100,
        ytd_power_kl=pl.col("ytd_power_kl").sum(),
        ytd_ms_total_kl=pl.col("ytd_ms_total_kl").sum(),
        ytd_conversion_pct=(
            pl.col("ytd_power_kl").sum() / pl.col("ytd_ms_total_kl").sum()
        )
        * 100,
    )

    top_3_retail_outlets = (
        nozzle_sales_top_df.filter(pl.col("current_conversion_pct").is_not_null())
        .sort("current_conversion_pct", descending=True)
        .head(3)
    )
    print("top_3_retail_outlets ---->\n", top_3_retail_outlets.to_dicts())

    top_3_sales_areas = nozzle_sales_top_df.group_by(
        ["zone", "region", "sales_area"]
    ).agg(
        current_power_kl_sum=pl.col("current_power_kl").sum(),
        current_ms_total_kl_sum=pl.col("current_ms_total_kl").sum(),
        current_conversion_pct=(
            pl.col("current_power_kl").sum() / pl.col("current_ms_total_kl").sum()
        )
        * 100,
        ytd_power_kl_sum=pl.col("ytd_power_kl").sum(),
        ytd_ms_total_kl_sum=pl.col("ytd_ms_total_kl").sum(),
        ytd_conversion_pct=(
            pl.col("ytd_power_kl").sum() / pl.col("ytd_ms_total_kl").sum()
        )
        * 100,
    )
    print(
        "count of records in top_3_sales_areas before filtering nulls ---->\n",
        top_3_sales_areas.shape[0],
    )
    top_3_sales_areas = (
        top_3_sales_areas.filter(pl.col("current_conversion_pct").is_not_null())
        .sort("current_conversion_pct", descending=True)
        .head(3)
    )
    print("top_3_sales_areas ---->\n", top_3_sales_areas.to_dicts())

    top_3_regions = nozzle_sales_top_df.group_by(["zone", "region"]).agg(
        current_power_kl_sum=pl.col("current_power_kl").sum(),
        current_ms_total_kl_sum=pl.col("current_ms_total_kl").sum(),
        current_conversion_pct=(
            pl.col("current_power_kl").sum() / pl.col("current_ms_total_kl").sum()
        )
        * 100,
        ytd_power_kl_sum=pl.col("ytd_power_kl").sum(),
        ytd_ms_total_kl_sum=pl.col("ytd_ms_total_kl").sum(),
        ytd_conversion_pct=(
            pl.col("ytd_power_kl").sum() / pl.col("ytd_ms_total_kl").sum()
        )
        * 100,
    )
    print(
        "count of records in top_3_regions before filtering nulls ---->\n",
        top_3_regions.shape[0],
    )
    top_3_regions = (
        top_3_regions.filter(pl.col("current_conversion_pct").is_not_null())
        .sort("current_conversion_pct", descending=True)
        .head(3)
    )
    print("top_3_regions ---->\n", top_3_regions.to_dicts())

    top_3_zones = (
        nozzle_sales_top_df.filter(pl.col("zone").is_not_null())
        .group_by(["zone"])
        .agg(
            current_power_kl_sum=pl.col("current_power_kl").sum(),
            current_ms_total_kl_sum=pl.col("current_ms_total_kl").sum(),
            current_conversion_pct=(
                pl.col("current_power_kl").sum() / pl.col("current_ms_total_kl").sum()
            )
            * 100,
            ytd_power_kl_sum=pl.col("ytd_power_kl").sum(),
            ytd_ms_total_kl_sum=pl.col("ytd_ms_total_kl").sum(),
            ytd_conversion_pct=(
                pl.col("ytd_power_kl").sum() / pl.col("ytd_ms_total_kl").sum()
            )
            * 100,
        )
    )
    print(
        "count of records in top_3_zones before filtering nulls ---->\n",
        top_3_zones.shape[0],
    )
    top_3_zones = (
        top_3_zones.filter(pl.col("current_conversion_pct").is_not_null())
        .sort("current_conversion_pct", descending=True)
        .head(3)
    )
    print("top_3_zones ---->\n", top_3_zones.to_dicts())

    return {
        "top_3_retail_outlets": top_3_retail_outlets.to_dicts(),
        "top_3_sales_areas": top_3_sales_areas.to_dicts(),
        "top_3_regions": top_3_regions.to_dicts(),
        "top_3_zones": top_3_zones.to_dicts(),
        "nozzle_present_month": labels["current_date_label"],
        "nozzle_previous_month": labels["financial_year_label"],
    }
