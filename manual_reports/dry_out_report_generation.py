import math

import urdhva_base
import os
import sys
import pytz
import json
import asyncio
import datetime
import numpy as np
import pandas as pd
import polars as pl
from dateutil.relativedelta import relativedelta

query_unique_alert = """
SELECT
    lm.zone AS "Zone",
    lm.region AS "Region",
    lm.sales_area AS "Sales Area",
    lm.sap_id AS "Location ID",
    lm.name AS "Location Name",
    e.id as "Alert ID",
    e.alert_history,

    -- Dryout Start Time: latest of created_at or dry_out_start_time
    GREATEST(e.created_at, e.dry_out_start_time) AS "Dryout Start Time",

    -- Dryout End Time: only for closed alerts
    MAX(
        CASE
            WHEN e.alert_status = 'Close' THEN COALESCE(e.dry_out_end_time, e.closed_at, e.updated_at)
            ELSE NULL
        END
    ) AS "Dryout End Time",

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
    END AS "Product Name",

    -- ✅ Rule 1: Indent Raised true only if dryout_day >= indent_raised_date
    CASE
        WHEN e.indent_no IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS "Indent Raised",

    -- ✅ Rule 2: Indent Raised Before Dryout kept True only if dry_out_start_time >= indent_raised_date
    CASE
        WHEN e.indent_raised_date IS NOT NULL AND e.dry_out_start_time IS NOT NULL
             AND e.dry_out_start_time >= e.indent_raised_date THEN TRUE
        ELSE FALSE
    END AS "Indent Raised Before Dryout",

    -- ✅ Rule 3: Indent Raised Date kept only if dryout_day >= indent_raised_date
    e.indent_raised_date AS "Indent Raised Date",

    -- ✅ Rule 4: Indent Status complex logic
    CASE
        WHEN e.indent_raised_date IS NULL THEN 'IndentNotRaised'
        WHEN e.indent_status IN ('TempClosed','ProductLowLevel','OfflineOrFalseAlarm') THEN 'Cancelled'
        ELSE e.indent_status
    END AS "Indent Status",

    -- ✅ Rule 5: Closure Status (same as Indent Status)
    CASE
        WHEN e.indent_raised_date IS NULL and e.alert_status = 'Close' THEN
            CASE
                WHEN e.indent_status IN ('Completed') THEN 'False Alarm'
                ELSE e.indent_status
            END
        ELSE e.indent_status
    END AS "Closure Status",

    -- ✅ Rule 6: Indent No kept only if indent_raised_date <= dryout_day
    e.indent_no AS "Indent No",

    -- Total Dryout Hours:
    ROUND(AVG(
        EXTRACT(
            EPOCH FROM (
                CASE
                    WHEN e.alert_status = 'Close'
                        THEN COALESCE(e.dry_out_end_time, e.closed_at, e.updated_at) - COALESCE(e.dry_out_start_time, e.created_at)
                    ELSE (NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') - e.created_at
                END
            )
        ) / 3600
    ), 2) AS "Total Dryout Hours"

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
      AND date_trunc('day', COALESCE(closed_at, updated_at, NOW())) >= '{start_date}'
      AND date_trunc('day', created_at) <= '{end_date}'
      AND product_code IN ('2811000', '2812000', '2822000')
      AND dry_out_in_days = '1'
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
    e.created_at
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

query_day_wise_old = """
SELECT
    lm.zone AS "Zone",
    lm.region AS "Region",
    lm.sales_area AS "Sales Area",
    lm.sap_id AS "Location ID",
    lm.name AS "Location Name",

    e.dryout_day AS "Date",
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
    END AS "Product Name",

    CASE
        WHEN e.indent_raised_date IS NOT NULL
             AND e.dryout_day >= e.indent_raised_date::date THEN TRUE
        ELSE FALSE
    END AS "Indent Raised",

    e.indent_raised_date AS "Indent Raised Date",
    e.indent_status AS "Indent Status",
    e.indent_no AS "Indent No",

    -- Dryout End Time: only for closed alerts
    MAX(
        CASE
            WHEN e.alert_status = 'Close' THEN COALESCE(e.dry_out_end_time, e.closed_at, e.updated_at)
            ELSE NULL
        END
    ) AS "Dryout End Time",

    -- Dryout Start Time: latest of created_at or dry_out_start_time
    GREATEST(e.created_at, e.dry_out_start_time) AS "Dryout Start Time",

    -- Total Dryout Hours:
    -- If closed -> difference between end_time and created_at
    -- If open   -> difference between current time (IST) and created_at
    ROUND(AVG(
        EXTRACT(
            EPOCH FROM (
                CASE
                    WHEN e.alert_status = 'Close'
                        THEN COALESCE(e.dry_out_end_time, e.closed_at, e.updated_at) - COALESCE(e.dry_out_start_time, e.created_at)
                    ELSE (NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') - e.created_at
                END
            )
        ) / 3600
    ), 2) AS "Total Dryout Hours"

FROM (
    SELECT
        sap_id,
        product_code,
        indent_status,
        indent_no,
        indent_raised_date AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS indent_raised_date,
        created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS created_at,
        closed_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS closed_at,
        updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS updated_at,
        dry_out_start_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS dry_out_start_time,
        dry_out_end_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS dry_out_end_time,
        alert_status,

        generate_series(
            GREATEST(
                date_trunc('day', created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date,
                '{start_date}'::date
            ),
            LEAST(
                date_trunc(
                    'day',
                    COALESCE(
                        closed_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata',
                        updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata',
                        NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata'
                    )
                )::date,
                '{end_date}'::date
            ),
            interval '1 day'
        )::date AS dryout_day

    FROM alerts
    WHERE interlock_name = 'Dry Out Each Indent Wise MainFlow'
      AND bu = 'RO'
      AND date_trunc('day', COALESCE(closed_at, updated_at, NOW())) >= '{start_date}'
      AND date_trunc('day', created_at) <= '{end_date}'
      AND product_code IN ('2811000', '2812000', '2822000')
      AND dry_out_in_days = '1'
) AS e

JOIN location_master lm
    ON e.sap_id = lm.sap_id

GROUP BY
    lm.zone,
    lm.region,
    lm.sales_area,
    lm.sap_id,
    lm.name,
    e.dryout_day,
    e.indent_raised_date,
    e.dry_out_start_time,
    e.dry_out_end_time,
    e.indent_status,
    e.indent_no,
    e.product_code,
    e.created_at
ORDER BY
    lm.zone
"""
query_day_wise = """
SELECT
    lm.zone AS "Zone",
    lm.region AS "Region",
    lm.sales_area AS "Sales Area",
    lm.sap_id AS "Location ID",
    lm.name AS "Location Name",
    e.alert_history,
    e.dryout_day AS "Date",
    
    -- Dryout Start Time: latest of created_at or dry_out_start_time
    GREATEST(e.created_at, e.dry_out_start_time) AS "Dryout Start Time",
    
    -- Dryout End Time: only for closed alerts
    MAX(
        CASE
            WHEN e.alert_status = 'Close' THEN COALESCE(e.dry_out_end_time, e.closed_at, e.updated_at)
            ELSE NULL
        END
    ) AS "Dryout End Time",
    
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
    END AS "Product Name",

    -- ✅ Rule 1: Indent Raised true only if dryout_day >= indent_raised_date
    CASE
        WHEN e.indent_raised_date IS NOT NULL
             AND e.dryout_day >= e.indent_raised_date::date THEN TRUE
        ELSE FALSE
    END AS "Indent Raised",
    
    -- ✅ Rule 2: Indent Raised Before Dryout kept True only if dry_out_start_time >= indent_raised_date
    CASE
        WHEN e.indent_raised_date IS NOT NULL AND e.dry_out_start_time IS NOT NULL
             AND e.dry_out_start_time >= e.indent_raised_date THEN TRUE
        ELSE FALSE
    END AS "Indent Raised Before Dryout",

    -- ✅ Rule 3: Indent Raised Date kept only if dryout_day >= indent_raised_date
    CASE
        WHEN e.indent_raised_date IS NOT NULL
             AND e.dryout_day >= e.indent_raised_date::date THEN e.indent_raised_date
        ELSE NULL
    END AS "Indent Raised Date",

    -- ✅ Rule 4: Indent Status complex logic
    CASE
        WHEN e.indent_raised_date IS NULL THEN
            CASE
                WHEN e.indent_status IN ('TempClosed','ProductLowLevel','OfflineOrFalseAlarm') THEN 'Cancelled'
                ELSE 'IndentNotRaised'
            END
        WHEN e.dryout_day < e.indent_raised_date::date THEN 'IndentNotRaised'
        WHEN e.indent_status IN ('TempClosed','ProductLowLevel','OfflineOrFalseAlarm') THEN 'Cancelled'
        ELSE e.indent_status
    END AS "Indent Status",

    -- ✅ Rule 5: Closure Status (same as Indent Status)
    CASE
        WHEN e.indent_raised_date IS NULL and e.alert_status = 'Close' and e.dryout_day < e.indent_raised_date::date THEN
            CASE
                WHEN e.indent_status IN ('TempClosed','ProductLowLevel','OfflineOrFalseAlarm') THEN 'False Alarm'
                ELSE e.indent_status
            END
        WHEN e.dryout_day < e.indent_raised_date::date THEN 'IndentNotRaised'
        WHEN e.indent_status IN ('TempClosed','ProductLowLevel','OfflineOrFalseAlarm') THEN 'Cancelled'
        ELSE e.indent_status
    END AS "Closure Status",

    -- ✅ Rule 6: Indent No kept only if indent_raised_date <= dryout_day
    CASE
        WHEN e.indent_raised_date IS NOT NULL
             AND e.dryout_day >= e.indent_raised_date::date THEN e.indent_no
        ELSE NULL
    END AS "Indent No",

    -- Total Dryout Hours:
    ROUND(AVG(
        EXTRACT(
            EPOCH FROM (
                CASE
                    WHEN e.alert_status = 'Close'
                        THEN COALESCE(e.dry_out_end_time, e.closed_at, e.updated_at) - COALESCE(e.dry_out_start_time, e.created_at)
                    ELSE (NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') - e.created_at
                END
            )
        ) / 3600
    ), 2) AS "Total Dryout Hours"

FROM (
    SELECT
        sap_id,
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
        alert_status,

        generate_series(
            GREATEST(
                date_trunc('day', GREATEST(created_at, dry_out_start_time) AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date,
                '{start_date}'::date
            ),
            LEAST(
                date_trunc(
                    'day',
                    COALESCE(
                        closed_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata',
                        updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata',
                        NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata'
                    )
                )::date,
                '{end_date}'::date
            ),
            interval '1 day'
        )::date AS dryout_day

    FROM alerts
    WHERE interlock_name = 'Dry Out Each Indent Wise MainFlow'
      AND bu = 'RO'
      AND date_trunc('day', COALESCE(closed_at, updated_at, NOW())) >= '{start_date}'
      AND date_trunc('day', created_at) <= '{end_date}'
      AND product_code IN ('2811000', '2812000', '2822000')
      AND dry_out_in_days = '1'
) AS e

JOIN location_master lm
    ON e.sap_id = lm.sap_id

GROUP BY
    lm.zone,
    lm.region,
    lm.sales_area,
    lm.sap_id,
    lm.name,
    e.alert_history,
    e.dryout_day,
    e.alert_status,
    e.indent_raised_date,
    e.dry_out_start_time,
    e.dry_out_end_time,
    e.indent_status,
    e.indent_no,
    e.product_code,
    e.created_at
ORDER BY
    lm.zone,
    lm.region,
    lm.sales_area,
    lm.sap_id,
    e.product_code,
    e.dry_out_start_time,
    e.dry_out_end_time
"""


'''
you can include cancel_time, user_cancel, indent_hold_release_time, indent_delivery_date, Indent_executed_datetime

indent_delivery_date - action_msg: Indent Delivered, processed_time
indent_hold_release_time - action_msg: Indent On Hold Released, processed_time
cancel_time - action_msg: Indent Cancelled, processed_time
'''

mapping = {"Indent Delivered": {"action_msg": "Indent Delivered", "time": "processed_time"},
               "Indent On Hold Released": {"action_msg": "Indent On Hold Released", "time": "ims_datetime"},
               "Indent Cancelled": {"action_msg": "Indent Cancelled", "time": "processed_time"}}


def get_column_data(record, key):
    if key not in mapping:
        return None

    mpa_data = mapping[key]

    # Parse string to JSON if needed
    if isinstance(record, str):
        try:
            record = json.loads(record)
        except json.JSONDecodeError:
            return None
    if not isinstance(record, list):
        return None
    for rec in record:
        if rec.get("action_msg") == mpa_data.get("action_msg"):
            ts = rec.get(mpa_data.get("time"))
            if not ts:
                return None
            try:
                if mpa_data['time'] == 'ims_datetime':
                    return datetime.datetime.fromisoformat(ts).replace(tzinfo=None)
                # Parse timestamp safely
                utc_time = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if utc_time.tzinfo is None:
                    # Assume UTC if timezone missing
                    utc_time = utc_time.replace(tzinfo=pytz.UTC)

                # Convert UTC → IST
                ist_time = utc_time.astimezone(pytz.timezone("Asia/Kolkata"))
                # Return timezone-naive datetime (Excel safe)
                return ist_time.replace(tzinfo=None)
            except Exception as e:
                print(f"Time parse error for {ts}: {e}")
                return None

    return None


async def fetch_dry_out_report(total_months):
    if not os.path.exists('/home/novex/dry_out_report'):
        os.makedirs('/home/novex/dry_out_report')
    start_date = (datetime.datetime.today() - datetime.timedelta(days=total_months*30))
    start_date = start_date.replace(day=1, minute=0, hour=0,second=0, microsecond=0)
    end_date = datetime.datetime.today().replace(minute=0, hour=0,second=0, microsecond=0)
    current = start_date
    records = []
    while current < end_date:
        month_start = current
        # Get the first day of the next month
        next_month = current + relativedelta(months=1)
        # End of this month (exclusive end_date for queries)
        month_end = next_month - datetime.timedelta(seconds=1)

        print(f"Processing month: {month_start.strftime('%B %Y')} "
              f"({month_start.date()} to {month_end.date()})")
        query_rebuilt = query_unique_alert.format(start_date=str(month_start), end_date=str(month_end))
        resp = await urdhva_base.postgresmodel.BasePostgresModel.get_aggr_data(query_rebuilt, limit=1000000)
        print(resp['total'])
        if len(resp['data']) == 0:
            break
        records.extend(resp['data'])
        current = next_month
        # df = pd.DataFrame(resp['data'])
        # df.to_excel(f'/home/novex/dry_out_report/dry_out_report_{month_start.month}-{month_start.day}_{month_end.month}-{month_end.day}.xlsx', index=False)
    index = 1
    step = 1000000
    for rec_start in range(0, len(records), step):
        df = pl.DataFrame(records[rec_start:rec_start+step])
        # Generate computed columns from alert_history using mapping
        for key in mapping:
            df = df.with_columns(
                pl.Series(
                    name=key,
                    values=[get_column_data(x, key) for x in df["alert_history"].to_list()]
                )
            )

        # Drop alert_history column
        df = df.drop("alert_history")

        # Indent Cancelled = None if Indent No is empty else keep as is
        df = df.with_columns(
            pl.when(pl.col("Indent No").is_null() | (pl.col("Indent No") == ""))
            .then(None)
            .otherwise(pl.col("Indent Cancelled"))
            .alias("Indent Cancelled")
        )

        # Indent Cancelled = None if Indent No is empty else keep as is
        df = df.with_columns(
            pl.when(pl.col("Indent No").is_null() | (pl.col("Indent No") == ""))
            .then(None)
            .otherwise(pl.col("Indent Delivered"))
            .alias("Indent Delivered")
        )

        # If Indent Status == 'Cancelled' and Indent Cancelled is null, use Dryout End Time
        df = df.with_columns(
            pl.when(
                (pl.col("Indent Status") == "Cancelled") & (pl.col("Indent Cancelled").is_null())
            )
            .then(pl.col("Dryout End Time"))
            .otherwise(pl.col("Indent Cancelled"))
            .alias("Indent Cancelled")
        )
        df = df.unique(subset=['Alert ID'])

        # Save to Excel
        output_path = f"/home/novex/dry_out_report/dry_out_report_{index}.xlsx"
        df.write_excel(output_path)
        index += 1

if __name__ == "__main__":
    total_months = 6
    if len(sys.argv) > 1:
        try:
            total_months = int(sys.argv[1])
        except ValueError:
            ...
    asyncio.run(fetch_dry_out_report(total_months))