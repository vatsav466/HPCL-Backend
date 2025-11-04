import sys

import urdhva_base
import os
import asyncio
import datetime
import pandas as pd
from dateutil.relativedelta import relativedelta

query_day_wise = """
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
    e.dryout_day,
    lm.zone,
    lm.region,
    lm.sales_area,
    lm.sap_id,
    lm.name,
    e.product_code
"""
query_unique_alert = """
SELECT
    lm.zone AS "Zone",
    lm.region AS "Region",
    lm.sales_area AS "Sales Area",
    lm.sap_id AS "Location ID",
    lm.name AS "Location Name",

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
             THEN TRUE
        ELSE FALSE
    END AS "Indent Raised",
    CASE
        WHEN e.indent_raised_date IS NOT NULL AND e.dry_out_start_time IS NOT NULL
             AND e.dry_out_start_time >= e.indent_raised_date THEN TRUE
        ELSE FALSE
    END AS "Indent Raised Before Dryout",

    e.indent_raised_date AS "Indent Raised Date",
    e.indent_status AS "Indent Status",
    e.indent_no AS "Indent No",

    -- Dryout Start Time: latest of created_at or dry_out_start_time
    GREATEST(e.created_at, e.dry_out_start_time) AS "Dryout Start Time",
    
    -- Dryout End Time: only for closed alerts
    MAX(
        CASE
            WHEN e.alert_status = 'Close' THEN COALESCE(e.dry_out_end_time, e.closed_at, e.updated_at)
            ELSE NULL
        END
    ) AS "Dryout End Time",
    

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
        df = pd.DataFrame(records[rec_start:rec_start+step])
        df.to_excel(f'/home/novex/dry_out_report/dry_out_report_{index}.xlsx', index=False)
        index += 1

if __name__ == "__main__":
    total_months = 6
    if len(sys.argv) > 1:
        try:
            total_months = int(sys.argv[1])
        except ValueError:
            ...
    asyncio.run(fetch_dry_out_report(total_months))