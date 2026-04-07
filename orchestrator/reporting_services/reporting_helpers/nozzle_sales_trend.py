
import urdhva_base
import polars as pl
import charts_actions
import dashboard_studio_model
import utilities.connection_mapping as connection_mapping
from charts_actions import charts_connection_vault_routing
from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
import matplotlib.pyplot as plt
import numpy as np
import os



async def plot_ms_sales_trend(trend_data: pl.DataFrame, output_path="/tmp/nozzle_trend_chart.png"):

    if trend_data is None or trend_data.is_empty():
        raise ValueError("trend_data cannot be empty")

    # -----------------------------
    # PREP DATA
    # -----------------------------

    df = trend_data.with_columns([
        pl.col("transaction_date").dt.day().alias("day"),
        ((pl.col("ms_power").cast(pl.Float64) /
         pl.col("ms_total").cast(pl.Float64))
        * 100
        ).alias("conversion")
        ])
    print("data ---->\n", df)

    # Remove nulls
    df = df.filter(
        pl.col("ms_total").is_not_null() &
        pl.col("ms_power").is_not_null()
    )
    print("remove nulls data ---->\n", df)

    # Convert Decimal → Float
    df = df.with_columns([
        pl.col("ms_total").cast(pl.Float64),
        pl.col("ms_power").cast(pl.Float64),
        pl.col("conversion").cast(pl.Float64)
    ])
    print("convert to float ---->\n", df)

    # Clamp conversion to avoid extreme values
    df = df.with_columns([
        pl.when(pl.col("conversion") > 100)
        .then(100)
        .otherwise(pl.col("conversion"))
        .alias("conversion")
    ])
    print("conversion to avoid extreme values ----->\n", df)

    # -----------------------------
    # NUMPY ARRAYS (SAFE)
    # -----------------------------
    days = df["day"].to_numpy()
    ms_total = np.nan_to_num(df["ms_total"].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)
    ms_power = np.nan_to_num(df["ms_power"].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)
    conversion = np.nan_to_num(df["conversion"].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)

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
    ax2.plot(x, conversion, marker='o',color="#d4aa00", linewidth=2, label="MS % Conversion")

    # -----------------------------
    # AXES
    # -----------------------------
    ax1.set_xticks(x)
    ax1.set_xticklabels(days)

    #ax2.set_ylim(0, max(conversion) * 1.2 if len(conversion) > 0 else 10)
    #ticks = ax2.get_yticks()

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
        ax1.text(i - 0.2, v + offset, f"{int(v)}", fontsize=7, ha='center')

    for i, v in enumerate(ms_power):
        ax1.text(i + 0.2, v + offset, f"{int(v)}", fontsize=7, ha='center')

    for i, v in enumerate(conversion):
        #if i % 2 == 0:
        ax2.text(i, float(v) + 0.3, f"{float(v):.1f}%", fontsize=8, ha='center')

    # -----------------------------
    # STYLE
    # -----------------------------
    ax1.grid(axis='y', linestyle='--', alpha=0.3)

    for spine in ["top", "right"]:
        ax1.spines[spine].set_visible(False)
        ax2.spines[spine].set_visible(False)

    plt.title("MS Total vs Power with Conversion % (Mar 1–19)")

    fig.legend(loc="upper left", bbox_to_anchor=(0.01, 0.90), ncol=3, frameon=False)
    plt.tight_layout(rect=[0, 0, 1, 0.92])

    # -----------------------------
    # SAVE
    # -----------------------------
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"Graph saved at: {output_path}")
    return output_path

async def fetch_data():

    nozzle_sales_query_avg =f"""
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
                            ROUND(((((AVG(ms))/1411.0)/1000.0)/0.89), 2) AS ms,
                            ROUND(((((AVG(power))/1411.0)/1000.0)/0.89), 2) AS power,
                            ROUND(((((AVG(hsd))/1210.0)/1000.0)/0.89), 2) AS hsd,
                            ROUND(((((AVG(turbo))/1210.0)/1000.0)/0.89), 2) AS turbo
                        FROM base
                        WHERE "transaction_date" BETWEEN DATE '2026-03-01' AND DATE '2026-03-19'
                    ),

                    apr AS (
                        SELECT
                            ROUND(((((AVG(ms))/1411.0)/1000.0)/0.89), 2) AS ms,
                            ROUND(((((AVG(power))/1411.0)/1000.0)/0.89), 2) AS power,
                            ROUND(((((AVG(hsd))/1210.0)/1000.0)/0.89), 2) AS hsd,
                            ROUND(((((AVG(turbo))/1210.0)/1000.0)/0.89), 2) AS turbo
                        FROM base
                        WHERE "transaction_date" BETWEEN DATE '2026-03-20' AND CURRENT_DATE - INTERVAL '1 day'
                    ),

                    yday AS (
                        SELECT
                            ROUND(((((SUM(ms))/1411.0)/1000.0)/0.89), 2) AS ms,
                            ROUND(((((SUM(power))/1411.0)/1000.0)/0.89), 2) AS power,
                            ROUND(((((SUM(hsd))/1210.0)/1000.0)/0.89), 2) AS hsd,
                            ROUND(((((SUM(turbo))/1210.0)/1000.0)/0.89), 2) AS turbo
                        FROM base
                        WHERE "transaction_date" = CURRENT_DATE - INTERVAL '1 day'
                    )

                    SELECT
                        -- ================= MS =================
                        ROUND(mar.ms,2) AS "MS-R Normal (Mar1-19)",
                        ROUND(apr.ms,2) AS "MS-R Normal (Mar20-Yday)",
                        ROUND(yday.ms,2) AS "MS-R Normal (Yday)",

                        ROUND(mar.power,2) AS "MS-R Branded (Mar1-19)",
                        ROUND(apr.power,2) AS "MS-R Branded (Mar20-Yday)",
                        ROUND(yday.power,2) AS "MS-R Branded (Yday)",

                        ROUND((mar.power / NULLIF(mar.ms + mar.power, 0)) * 100, 1) AS "MS % (Mar1-19)",
                        ROUND((apr.power / NULLIF(apr.ms + apr.power, 0)) * 100, 1) AS "MS % (Mar20-Yday)",
                        ROUND((yday.power / NULLIF(yday.ms + yday.power, 0)) * 100, 1) AS "MS % (Yday)",

                        ROUND(mar.ms + mar.power, 2) AS "MS Total (Mar1-19)",
                        ROUND(apr.ms + apr.power, 2) AS "MS Total (Mar20-Yday)",
                        ROUND(yday.ms + yday.power, 2) AS "MS Total (Yday)",

                        -- ================= HSD =================
                        ROUND(mar.hsd,2) AS "HSD-R Normal (Mar1-19)",
                        ROUND(apr.hsd,2) AS "HSD-R Normal (Mar20-Yday)",
                        ROUND(yday.hsd,2) AS "HSD-R Normal (Yday)",

                        ROUND(mar.turbo,2) AS "HSD-R Branded (Mar1-19)",
                        ROUND(apr.turbo,2) AS "HSD-R Branded (Mar20-Yday)",
                        ROUND(yday.turbo,2) AS "HSD-R Branded (Yday)",

                        ROUND((mar.turbo / NULLIF(mar.hsd + mar.turbo, 0)) * 100, 1) AS "HSD % (Mar1-19)",
                        ROUND((apr.turbo / NULLIF(apr.hsd + apr.turbo, 0)) * 100, 1) AS "HSD % (Mar20-Yday)",
                        ROUND((yday.turbo / NULLIF(yday.hsd + yday.turbo, 0)) * 100, 1) AS "HSD % (Yday)",

                        ROUND(mar.hsd + mar.turbo, 2) AS "HSD Total (Mar1-19)",
                        ROUND(apr.hsd + apr.turbo, 2) AS "HSD Total (Mar20-Yday)",
                        ROUND(yday.hsd + yday.turbo, 2) AS "HSD Total (Yday)"

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
                WHERE transaction_date BETWEEN DATE '2026-03-01' AND DATE '2026-03-19'
                GROUP BY transaction_date

            """
    Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("hpcl_ceg", "1")
    Charts_Connection_Vault_RoutingParams.action = 'execute_query'
    function = await charts_connection_vault_routing(Charts_Connection_Vault_RoutingParams)


    nozzle_sales_avg = await function(query=nozzle_sales_query_avg)
    #nozzle_sales_avg_df = pl.DataFrame(nozzle_sales_avg)
    nozzle_sales_avg_df = pl.DataFrame(nozzle_sales_avg).with_columns([
        pl.all().cast(pl.Float64)
    ])
    print("nozzle_sales_avg_df = pd.DataFrame(nozzle_sales_avg) ---->\n", nozzle_sales_avg_df)
    print("nozzle ---->\n", nozzle_sales_avg_df.to_dicts()[0])
    nozzle_trend = await function(query= nozzle_trend_query)
    nozzle_trend_df = pl.DataFrame(nozzle_trend)
    print("nozzle trend data----> \n", nozzle_trend_df)

    nozzle_trend_chart = await plot_ms_sales_trend(nozzle_trend_df)
    print("nozzle trend chart --->\n", nozzle_trend_chart)
    return {"nozzle_sales_avg_df": nozzle_sales_avg_df.to_dicts()[0], "nozzle_trend_chart": nozzle_trend_chart}


if __name__ == "__main__":
    import asyncio
    result = asyncio.run(fetch_data())
    print(result)

