import asyncio
import urdhva_base
import traceback
from datetime import datetime, date as date_cls
import polars as pl
import charts_actions
import dashboard_studio_model
import utilities.connection_mapping as connection_mapping

from orchestrator.field_force.territory_mapping.product_mapping import product_mapping


def _ims_to_cris_product_no(ims: str | None) -> str | None:
    if ims is None:
        return None
    key = str(ims).strip()
    entry = product_mapping.get(key)
    if not entry:
        return None
    cris = entry.get("CRIS")
    return str(cris).strip() if cris is not None else None


def _parse_report_date_header(col) -> date_cls | None:
    """
    Pivot date columns may be: Python date/datetime, or strings dd/mm/yy or YYYY-MM-DD.
    """
    if isinstance(col, date_cls):
        return col
    s = str(col).strip()
    for fmt in ("%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10] if fmt == "%Y-%m-%d" else s, fmt).date()
        except ValueError:
            continue
    return None


def _is_transient_pool_error(exc: BaseException) -> bool:
    """True when DB/PgBouncer refused a new connection — worth retrying after a short wait."""
    msg = (str(exc) or "").lower()
    return any(
        p in msg
        for p in (
            "max_client_conn",
            "no more connections",
            "too many connections",
            "too many clients",
            "remaining connection slots",
        )
    )


def _date_cols_from_pivot(df: pl.DataFrame) -> list[str]:
    """Column names that are calendar dates (dry-out hour grid), excluding metrics."""
    skip = {
        "Location ID",
        "Product Code",
        "Total Dry Out Hours",
        "Max Dry Out Hours",
        "Total Frequency",
        "Average Sales",
        "Lost Of Sale",
    }
    out: list[str] = []
    for c in df.columns:
        if c in skip:
            continue
        if _parse_report_date_header(c) is not None:
            out.append(c)
    return out


async def _fetch_cris_daily_product_dry_out(start_date: str, end_date: str) -> pl.DataFrame:
    """
    CRIS HPCL_HOS.daily_product_dry_out — keys: rosapcode, product_no, stock_date.
    DB column is last_month_avg_sale (not lost_*); loss_of_sale.
    """
    # One row per (rosapcode, product_no, day): duplicate source rows (e.g. site/tank) are averaged,
    # not stacked — avoids join inflation when summing loss_of_sale.
    query = f"""
        SELECT
            rosapcode::text AS rosapcode,
            product_no::text AS product_no,
            stock_date::date AS stock_date,
            AVG(last_month_avg_sale)::float8 AS last_month_avg_sale,
            AVG(loss_of_sale)::float8 AS loss_of_sale
        FROM "HPCL_HOS".daily_product_dry_out
        WHERE stock_date::date >= '{start_date}'::date
          AND stock_date::date <= '{end_date}'::date
        GROUP BY rosapcode, product_no, stock_date::date
    """
    rows = None
    last_exc: BaseException | None = None
    for attempt in range(3):
        try:
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = (
                connection_mapping.connection_mapping.get("cris", "2")
            )
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = "execute_query"
            fn = await charts_actions.charts_connection_vault_routing(
                dashboard_studio_model.Charts_Connection_Vault_RoutingParams
            )
            rows = await fn(query=query)
            break
        except Exception as exc:
            last_exc = exc
            if attempt < 2 and _is_transient_pool_error(exc):
                await asyncio.sleep(2.0 * (attempt + 1))
                continue
            raise
    if rows is None:
        assert last_exc is not None
        raise last_exc
    if not rows:
        return pl.DataFrame(
            schema={
                "rosapcode": pl.Utf8,
                "product_no": pl.Utf8,
                "stock_date": pl.Date,
                "last_month_avg_sale": pl.Float64,
                "loss_of_sale": pl.Float64,
            }
        )
    cris = pl.DataFrame(rows)
    # Normalise driver column names to snake_case
    cris = cris.rename({c: c.lower() for c in cris.columns})
    need = {"rosapcode", "product_no", "stock_date", "last_month_avg_sale", "loss_of_sale"}
    missing = need - set(cris.columns)
    if missing:
        raise RuntimeError(
            f"CRIS daily_product_dry_out missing columns {missing}. "
            f"Got: {list(cris.columns)}"
        )
    return cris.select(
        [
            pl.col("rosapcode").cast(pl.Utf8).str.strip_chars().alias("rosapcode"),
            pl.col("product_no").cast(pl.Utf8).str.strip_chars().alias("product_no"),
            pl.col("stock_date").cast(pl.Date),
            pl.col("last_month_avg_sale").cast(pl.Float64, strict=False).alias("last_month_avg_sale"),
            pl.col("loss_of_sale").cast(pl.Float64, strict=False).alias("loss_of_sale"),
        ]
    )


def _merge_cris_into_pivot(
    pivot_df: pl.DataFrame,
    cris_df: pl.DataFrame,
    date_cols: list[str],
    report_start_date: str | None = None,
) -> pl.DataFrame:
    """
    Join CRIS on (rosapcode, product_no, stock_date) per report day.

    Lost Of Sale / Average Sales must NOT sum across the whole month (that inflated totals vs
    a single-day DB check). We take CRIS metrics for the **earliest stock_date** in the report
    that has CRIS data for that Location + Product (aligns with e.g. WHERE stock_date = month start).
    """
    if not date_cols or cris_df.is_empty():
        return pivot_df

    cris_keys = cris_df.group_by(["rosapcode", "product_no", "stock_date"]).agg(
        [
            pl.col("last_month_avg_sale").mean().alias("_avg_sale"),
            pl.col("loss_of_sale").mean().alias("_loss_sale"),
        ]
    )

    long = pivot_df.unpivot(
        index=["Location ID", "Product Code"],
        on=date_cols,
        variable_name="date_str",
        value_name="_dryout_cell",
    )
    long = long.with_columns(
        [
            pl.col("date_str")
            .map_elements(
                lambda s: _parse_report_date_header(s),
                return_dtype=pl.Date,
            )
            .alias("stock_date"),
            pl.col("Location ID").cast(pl.Utf8).str.strip_chars().alias("rosapcode"),
            pl.col("Product Code")
            .cast(pl.Utf8)
            .map_elements(
                lambda s: _ims_to_cris_product_no(s),
                return_dtype=pl.Utf8,
            )
            .alias("product_no"),
        ]
    )
    long = long.filter(pl.col("stock_date").is_not_null())

    long = long.join(
        cris_keys,
        on=["rosapcode", "product_no", "stock_date"],
        how="left",
    )

    # Rows with CRIS data for this location/product/day
    with_cris = long.filter(pl.col("_loss_sale").is_not_null() | pl.col("_avg_sale").is_not_null())
    if with_cris.is_empty():
        return pivot_df

    # Prefer CRIS row for report period start (same as typical DB: WHERE stock_date = 'YYYY-MM-01').
    # Else earliest day with data. Never sum all days (that matched ~18k vs ~224 for one day).
    start_d: date_cls | None = None
    if report_start_date:
        try:
            start_d = datetime.strptime(report_start_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            start_d = None

    if start_d is not None:
        at_start = with_cris.filter(pl.col("stock_date") == start_d)
        if not at_start.is_empty():
            picked = at_start.group_by(["Location ID", "Product Code"]).agg(
                [
                    pl.col("_avg_sale").mean().alias("Average Sales"),
                    pl.col("_loss_sale").mean().alias("Lost Of Sale"),
                ]
            )
            return pivot_df.join(picked, on=["Location ID", "Product Code"], how="left")

    pick = with_cris.group_by(["Location ID", "Product Code"]).agg(
        pl.col("stock_date").min().alias("_pick_date")
    )
    picked = (
        with_cris.join(pick, on=["Location ID", "Product Code"], how="inner")
        .filter(pl.col("stock_date") == pl.col("_pick_date"))
        .group_by(["Location ID", "Product Code"])
        .agg(
            [
                pl.col("_avg_sale").mean().alias("Average Sales"),
                pl.col("_loss_sale").mean().alias("Lost Of Sale"),
            ]
        )
    )
    return pivot_df.join(picked, on=["Location ID", "Product Code"], how="left")


async def get_retail_outlet_stockouts():
    try:
        start_date = '2026-03-01'
        end_date = '2026-03-31'

        current_time = datetime.now()

        query_unique_alert = f"""
                                SELECT
                                    lm.zone AS "Zone",
                                    lm.region AS "Region",
                                    lm.sales_area AS "Sales Area",
                                    lm.sap_id AS "Location ID",
                                    lm.name AS "Location Name",
                                    e.id as "Alert ID",
                                    e.alert_history,
                                    e.indent_no as "Indent No",
                                    e.closed_at as "Closed At",
                                    e.updated_at as "Updated At",

                                    -- Dryout Start Time: latest of created_at or dry_out_start_time
                                    e.dry_out_start_time AS "Dryout Start Time",

                                    -- Dryout End Time: only for closed alerts
                                    e.dry_out_end_time as "Dryout End Time",

                                    e.product_code AS "Product Code",

                                    CASE e.product_code
                                        WHEN '2811000' THEN 'MS'
                                        WHEN '2812000' THEN 'HSD'
                                        WHEN '3912000' THEN 'TURBO'
                                        WHEN '2822000' THEN 'E20'
                                        WHEN '3672000' THEN 'POWER 95'
                                        WHEN '2816000' THEN 'POWER 99'
                                        WHEN '3373000' THEN 'POWER 100'
                                        ELSE e.product_code
                                    END AS "Product Name"

                                FROM (
                                    SELECT
                                        sap_id,
                                        id,
                                        product_code,
                                        indent_status,
                                        indent_no,
                                        alert_history,
                                        indent_raised_date,
                                        created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS created_at,
                                        closed_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS closed_at,
                                        updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS updated_at,
                                        dry_out_start_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS dry_out_start_time,
                                        dry_out_end_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS dry_out_end_time,
                                        alert_status
                                    FROM alerts
                                    WHERE interlock_name = 'Dry Out Each Indent Wise MainFlow'
                                    AND bu = 'RO'
                                    AND product_code IN ('2811000', '2812000', '3912000','2822000','3672000','2816000','3373000')
                                    AND dry_out_in_days = '1'
                                    -- Interval starts before or at timestamp
                                    AND dry_out_start_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata'
                                            >= '{start_date}'

                                    -- Interval ends after timestamp OR has no end
                                    AND (
                                        COALESCE(dry_out_end_time, closed_at, updated_at) IS NULL
                                        OR COALESCE(dry_out_end_time, closed_at, updated_at) <= '{end_date}'
                                    )
                                ) AS e

                                JOIN location_master lm
                                    ON e.sap_id = lm.sap_id

                                GROUP BY
                                    lm.zone,
                                    lm.region,
                                    lm.sales_area,
                                    lm.sap_id,
                                    lm.name,
                                    e.id,
                                    e.alert_history,
                                    e.alert_status,
                                    e.indent_raised_date,
                                    e.dry_out_start_time,
                                    e.dry_out_end_time,
                                    e.indent_status,
                                    e.indent_no,
                                    e.product_code,
                                    e.created_at,
                                    e.updated_at,
                                    e.closed_at
                                ORDER BY
                                    lm.zone,
                                    lm.region,
                                    lm.sales_area,
                                    lm.sap_id,
                                    e.product_code,
                                    e.dry_out_start_time,
                                    e.dry_out_end_time,
                                    e.indent_raised_date
                                """

        query_resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=query_unique_alert, limit=0)
        query_resp = query_resp.get("data", [])

        if not query_resp:
            print("No data found")
            return

        df = pl.DataFrame(query_resp)

        # STEP 1: Prepare timestamps
        df = df.with_columns([
            pl.col("Dryout Start Time").cast(pl.Datetime),
            pl.coalesce([
                pl.col("Dryout End Time"),
                pl.col("Closed At"),
                pl.col("Updated At"),
                pl.lit(current_time)
            ]).alias("end_time")
        ])

        # STEP 2: FULL HOURS
        df = df.with_columns([
            pl.when(pl.col("end_time") > pl.col("Dryout Start Time"))
            .then((pl.col("end_time") - pl.col("Dryout Start Time")).dt.total_seconds() / 3600)
            .otherwise(0)
            .alias("full_hours")
        ])

        # STEP 3: Max Hours
        max_df = df.group_by(["Location ID", "Product Code"]).agg([
            pl.max("full_hours").alias("Max Dry Out Hours")
        ])

        #  STEP 3.1: Total Frequency (NEW)
        freq_df = df.group_by(["Location ID", "Product Code"]).agg([
            pl.n_unique("Alert ID").alias("Total Frequency")
        ])

        # STEP 4: Expand day-wise
        df_expanded = df.with_columns([
            pl.date_ranges(
                pl.col("Dryout Start Time").dt.date(),
                pl.col("end_time").dt.date(),
                interval="1d"
            ).alias("date_range")
        ]).explode("date_range")

        df_expanded = df_expanded.filter(pl.col("date_range").is_not_null())

        # STEP 5: Daily overlap
        df_expanded = df_expanded.with_columns([
            pl.max_horizontal([
                pl.col("Dryout Start Time"),
                pl.col("date_range").cast(pl.Datetime)
            ]).alias("start"),

            pl.min_horizontal([
                pl.col("end_time"),
                (pl.col("date_range") + pl.duration(days=1)).cast(pl.Datetime)
            ]).alias("end")
        ])

        # STEP 6: Daily hours
        df_expanded = df_expanded.with_columns([
            pl.when(pl.col("end") > pl.col("start"))
            .then((pl.col("end") - pl.col("start")).dt.total_seconds() / 3600)
            .otherwise(0)
            .alias("hours")
        ])

        # STEP 7: Pivot
        pivot_df = df_expanded.pivot(
            values="hours",
            index=["Location ID", "Product Code"],
            columns="date_range",
            aggregate_function="sum"
        ).fill_null(0)

        # STEP 8: Rename date columns to dd/mm/yy (pivot keys are date/datetime, not only datetime)
        rename_dict = {
            col: col.strftime("%d/%m/%y")
            for col in pivot_df.columns
            if isinstance(col, date_cls)
        }
        pivot_df = pivot_df.rename(rename_dict)

        # STEP 9: Total hours
        value_cols = [
            col for col in pivot_df.columns
            if col not in ["Location ID", "Product Code"]
        ]

        pivot_df = pivot_df.with_columns([
            pl.sum_horizontal(value_cols).alias("Total Dry Out Hours")
        ])

        # STEP 10: Join MAX + Frequency
        pivot_df = pivot_df.join(max_df, on=["Location ID", "Product Code"], how="left")
        pivot_df = pivot_df.join(freq_df, on=["Location ID", "Product Code"], how="left")

        # STEP 10.5: CRIS — "HPCL_HOS".daily_product_dry_out (rosapcode, product_no, stock_date)
        dryout_date_cols = _date_cols_from_pivot(pivot_df)
        try:
            cris_df = await _fetch_cris_daily_product_dry_out(start_date, end_date)
            if not cris_df.is_empty():
                cris_df = cris_df.unique(
                    subset=["rosapcode", "product_no", "stock_date"],
                    keep="first",
                )
                pivot_df = _merge_cris_into_pivot(
                    pivot_df, cris_df, dryout_date_cols, report_start_date=start_date
                )
        except Exception:
            traceback.print_exc()
            print(
                "CRIS daily_product_dry_out enrichment skipped or failed; "
                "continuing without Average Sales / Lost Of Sale columns."
            )

        # STEP 11: Final column order — dates, then totals, then two CRIS columns at the end
        dryout_date_cols_sorted = sorted(
            dryout_date_cols,
            key=lambda c: _parse_report_date_header(c) or date_cls.min,
        )
        cris_tail = ["Average Sales", "Lost Of Sale"]
        ordered = (
            ["Location ID", "Product Code"]
            + dryout_date_cols_sorted
            + ["Total Dry Out Hours", "Max Dry Out Hours", "Total Frequency"]
            + [c for c in cris_tail if c in pivot_df.columns]
        )
        pivot_df = pivot_df.select([c for c in ordered if c in pivot_df.columns])

        print(pivot_df.head(10))

        # STEP 12: Export Excel
        file_path = "/tmp/dry_out_report.xlsx"
        pivot_df.write_excel(file_path)

        print(f"File saved at: {file_path}")

    except Exception as e:
        print(traceback.format_exc())
        print(f"Error: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(get_retail_outlet_stockouts())
