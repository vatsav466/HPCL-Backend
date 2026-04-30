import urdhva_base
import hpcl_ceg_model
import traceback
import xlsxwriter
from datetime import datetime
import polars as pl
import charts_actions
import dashboard_studio_model
import utilities.connection_mapping as connection_mapping


zone_map = {
    "CEN": "CENTRAL ZONE",
    "ECZ": "EAST CENTRAL ZONE",
    "EZ": "EAST",
    "NCZ": "NORTH CENTRAL RETAIL",
    "NFZ": "NORTH FRONTIER ZONE",
    "NWF": "NORTH WEST FRONTIER",
    "NWZ": "NORTH WEST RETAIL ZONE",
    "NZ": "NORTH",
    "SCZ": "SOUTH CENTRAL RETAIL",
    "SWZ": "SOUTH WESTERN ZONE",
    "SZ": "SOUTH",
    "WZ": "WEST"
}


async def get_retail_outlet_stockouts(data):
    try:
        current_time = datetime.now()

        where_clause = ["interlock_name = 'Dry Out Each Indent Wise MainFlow'", "dry_out_in_days = '1'", "mark_as_false = 'true'"]
        where_clause.extend(await hpcl_ceg_model.Alerts.get_clause_conditions(
            extra_key_mapping={"sap_id": "terminal_plant_id"}, default_mapping={"bu": "RO"}))
        start_date = None
        end_date = None
        all_conditions = []
        final_where_clause = ""
        if data.cross_filters:
            for filter in data.cross_filters:
                # Handle DATE filter
                if "DATE" in filter.key:
                    if filter.value:
                        dates = filter.value.split(",")
                    elif filter.values:
                        dates = filter.values if isinstance(filter.values, list) else [filter.values]
                    else:
                        continue
                    start_date = dates[0]
                    end_date = datetime.strptime(dates[-1], "%Y-%m-%d").strftime("%Y-%m-%d")
                    continue  # skip to next filter after handling date
                # Handle NON-DATE filters (same logic as filters)
                if filter.values and isinstance(filter.values, list) and len(filter.values) > 0:
                    vals = filter.values
                elif filter.value:
                    vals = filter.value.split(",")
                else:
                    continue
                if len(vals) == 1:
                    condition = f"{filter.key} = '{vals[0]}'"
                else:
                    condition = f"{filter.key} IN {tuple(vals)}"
                all_conditions.append(condition)

        if data.filters:
            conditions = []
            for rec in data.filters:
                # Step 1: Decide source
                if rec.values and isinstance(rec.values, list) and len(rec.values) > 0:
                    vals = rec.values
                elif rec.value:
                    vals = rec.value.split(",")
                else:
                    continue  # skip empty filter
                # Step 2: Build condition
                if len(vals) == 1:
                    condition = f"{rec.key} = '{vals[0]}'"
                else:
                    condition = f"{rec.key} IN {tuple(vals)}"
                conditions.append(condition)
            # Step 3: Merge conditions
            if conditions:
                all_conditions.extend(conditions)
        if where_clause:
            all_conditions.extend(where_clause)
        if all_conditions:
            final_where_clause = " AND " + " AND ".join(all_conditions)

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
                                    {final_where_clause}
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
        
        print("query_unique_alert---->\n", query_unique_alert)
        
        loss_of_sales_query =f"""
                    select rosapcode, product_no, product_name, zonal_name,regional_name,salesarea_name,
                    sum(loss_of_sale) as loss_of_sales,site_name 
                    from "HPCL_HOS".daily_product_dry_out where
                    stock_date::date between '{start_date}' and '{end_date}' 
                    group by rosapcode, product_no, product_name, zonal_name,regional_name,salesarea_name,site_name
                    order by rosapcode
                """
        
        print(" loss of sales query ----->\n", loss_of_sales_query)

        query_resp = await urdhva_base.BasePostgresModel.get_aggr_data(query=query_unique_alert, limit=0)
        query_resp = query_resp.get("data", [])

        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("cris", "1")
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        loss_resp = await function(query=loss_of_sales_query)
        loss_sales_df = pl.DataFrame(loss_resp)

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
        max_df = df.group_by(["Zone", "Region", "Sales Area", "Location ID", "Product Code", "Product Name"]).agg([
            pl.max("full_hours").alias("Max Dry Out Hours")
        ])

        # STEP 3.1: Total Frequency (NEW)
        freq_df = df.group_by(["Zone", "Region", "Sales Area", "Location ID", "Product Code", "Product Name"]).agg([
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
            index=["Zone", "Region", "Sales Area", "Location ID", "Product Code", "Product Name"],
            columns="date_range",
            aggregate_function="sum"
        ).fill_null(0)

        # STEP 8: Rename columns
        rename_dict = {
            col: col.strftime("%d/%m/%y")
            for col in pivot_df.columns
            if isinstance(col, datetime)
        }
        pivot_df = pivot_df.rename(rename_dict)

        # STEP 9: Total hours
        value_cols = [
            col for col in pivot_df.columns
            if col not in ["Zone", "Region", "Sales Area", "Location ID", "Product Code", "Product Name"]
        ]

        # replace 0 with none
        pivot_df = pivot_df.with_columns([
            pl.when(pl.col(col) == 0).then(None).otherwise(pl.col(col)).alias(col)
            for col in value_cols
        ])

        pivot_df = pivot_df.with_columns([
            pl.sum_horizontal(value_cols).alias("Total Dry Out Hours")
        ])

        # STEP 10: Join MAX + Frequency
        pivot_df = pivot_df.join(max_df, on=["Zone", "Region", "Sales Area", "Location ID", "Product Code", "Product Name"], how="left")
        pivot_df = pivot_df.join(freq_df, on=["Zone", "Region", "Sales Area", "Location ID", "Product Code", "Product Name"], how="left")
        
        # -------
        # MS AND HSD
        # -------

        loss_sales_df_mh = loss_sales_df.with_columns([
            pl.when(pl.col("product_name") == "MS").then(pl.lit("MS"))
            .when(pl.col("product_name") == "HSD").then(pl.lit("HSD"))
            .otherwise(pl.lit(None))
            .alias("Product Category")
        ])
        loss_sales_df_mh = loss_sales_df_mh.filter(pl.col("Product Category").is_not_null())
        loss_sales_df_mh = loss_sales_df_mh.group_by(
            ["rosapcode", "zonal_name", "regional_name", "salesarea_name", "Product Category"]
        ).agg([
            pl.sum("loss_of_sales").alias("Loss of Sales")
        ]).rename({
            "rosapcode": "Location ID",
            "zonal_name": "Zone",
            "regional_name": "Region",
            "salesarea_name": "Sales Area"
        })
        pivot_df_mh = pivot_df.with_columns([
            pl.col("Product Name").str.to_uppercase()
        ])

        pivot_df_mh = pivot_df_mh.with_columns([
            pl.when(pl.col("Product Name") == "MS").then(pl.lit("MS"))
            .when(pl.col("Product Name") == "HSD").then(pl.lit("HSD"))
            .otherwise(pl.lit(None))
            .alias("Product Category")
        ])
        pivot_df_mh = pivot_df_mh.filter(pl.col("Product Category").is_not_null())
        pivot_df_mh = pivot_df_mh.with_columns(pl.col("Zone").replace(zone_map))
       
        pivot_df_mh = pivot_df_mh.join(loss_sales_df_mh, on=["Location ID", "Product Category",  "Zone", "Region", "Sales Area"], how="left")
    
        # STEP 11: Final column order
        pivot_df_mh = pivot_df_mh.select(
             ["Zone", "Region", "Sales Area", "Location ID", "Product Category"] +
             ["Total Dry Out Hours", "Max Dry Out Hours", "Total Frequency", "Loss of Sales"] +
             sorted([
                 c for c in pivot_df_mh.columns
                 if c not in [
                     "Zone", "Region", "Sales Area",
                     "Location ID",
                     "Product Category",
                     "Total Dry Out Hours",
                     "Max Dry Out Hours",
                     "Total Frequency", "Loss of Sales"
                 ]
             ]) 
         )
        
        pivot_df_mh = pivot_df_mh.sort(["Zone", "Region", "Sales Area", "Location ID"])
        pivot_df_mh = pivot_df_mh.with_columns(pl.col("Zone").replace(zone_map))
        pivot_df_mh = pivot_df_mh.select(
            ["Zone", "Region", "Sales Area", "Location ID", "Product Category"] +
            ["Total Dry Out Hours", "Max Dry Out Hours", "Total Frequency", "Loss of Sales"] +
            sorted([
                c for c in pivot_df_mh.columns
                if c not in [
                    "Zone", "Region", "Sales Area",
                    "Location ID","Product Category",
                    "Total Dry Out Hours",
                    "Max Dry Out Hours",
                    "Total Frequency",
                    "Loss of Sales",
                    "Product Code",
                    "Product Name"
                ]
            ])
        )
        print(pivot_df_mh.head(10))

        # ---------
        # MS, MS BRAND (POWER 95, 99, 100), HSD, HSD BRAND (TURBO)
        # ---------


        loss_sales_df = loss_sales_df.with_columns([
            pl.when(pl.col("product_name") == "MS").then(pl.lit("MS"))
            .when(pl.col("product_name").is_in(["POWER 95", "POWER 99", "POWER 100"])).then(pl.lit("MS_BRAND"))
            .when(pl.col("product_name") == "HSD").then(pl.lit("HSD"))
            .when(pl.col("product_name") == "TURBO").then(pl.lit("HSD_BRAND"))
            .otherwise(pl.lit("OTHER"))
            .alias("Product Category")
        ])
        loss_sales_df = loss_sales_df.group_by(
            ["rosapcode", "zonal_name", "regional_name", "salesarea_name", "Product Category"]
        ).agg([
            pl.sum("loss_of_sales").alias("Loss of Sales")
        ]).rename({
            "rosapcode": "Location ID",
            "zonal_name": "Zone",
            "regional_name": "Region",
            "salesarea_name": "Sales Area"
        })
        pivot_df = pivot_df.with_columns([
            pl.col("Product Name").str.to_uppercase()
        ])

        pivot_df = pivot_df.with_columns([
            pl.when(pl.col("Product Name") == "MS").then(pl.lit("MS"))
            .when(pl.col("Product Name").is_in(["POWER 95", "POWER 99", "POWER 100"])).then(pl.lit("MS_BRAND"))
            .when(pl.col("Product Name") == "HSD").then(pl.lit("HSD"))
            .when(pl.col("Product Name") == "TURBO").then(pl.lit("HSD_BRAND"))
            .otherwise(pl.lit("OTHER"))
            .alias("Product Category")
        ])
        pivot_df = pivot_df.with_columns(pl.col("Zone").replace(zone_map))
       
        pivot_df = pivot_df.join(loss_sales_df, on=["Location ID", "Product Category",  "Zone", "Region", "Sales Area"], how="left")
    
        # STEP 11: Final column order
        pivot_df = pivot_df.select(
             ["Zone", "Region", "Sales Area", "Location ID", "Product Category"] +
             ["Total Dry Out Hours", "Max Dry Out Hours", "Total Frequency", "Loss of Sales"] +
             sorted([
                 c for c in pivot_df.columns
                 if c not in [
                     "Zone", "Region", "Sales Area",
                     "Location ID",
                     "Product Category",
                     "Total Dry Out Hours",
                     "Max Dry Out Hours",
                     "Total Frequency", "Loss of Sales"
                 ]
             ]) 
         )
        
        pivot_df = pivot_df.sort(["Zone", "Region", "Sales Area", "Location ID"])
        pivot_df = pivot_df.with_columns(pl.col("Zone").replace(zone_map))
        pivot_df = pivot_df.select(
            ["Zone", "Region", "Sales Area", "Location ID", "Product Category"] +
            ["Total Dry Out Hours", "Max Dry Out Hours", "Total Frequency", "Loss of Sales"] +
            sorted([
                c for c in pivot_df.columns
                if c not in [
                    "Zone", "Region", "Sales Area",
                    "Location ID","Product Category",
                    "Total Dry Out Hours",
                    "Max Dry Out Hours",
                    "Total Frequency",
                    "Loss of Sales",
                    "Product Code",
                    "Product Name"
                ]
            ])
        )
        print(pivot_df.head(10))
        
        # STEP 12: Export Excel
        file_path = "/tmp/dry_out_report.xlsx"
        with xlsxwriter.Workbook(file_path) as workbook:

        
            header_format = workbook.add_format({
                "bold": True,
                "font_color": "white",
                "bg_color": "#1C466B",
                "border": 1,
                "align": "center",
                "valign": "vcenter"
            })

            # -------------------
            # Sheet 1 -- MS & HSD
            # -------------------
            ws1 = workbook.add_worksheet("MS_HSD")

            pivot_df_mh.write_excel(workbook=workbook, worksheet="MS_HSD")

            for i, col in enumerate(pivot_df_mh.columns):
                if i < 3:
                    ws1.set_column(i, i, 20)   # FIXED WIDTH for first 3 columns
                else:
                    ws1.set_column(i, i, max(12, len(col) + 2))  # dynamic width

                ws1.write(0, i, col, header_format)
            # -------------------
            # Sheet 2 -- All Products
            # -------------------
            ws2 = workbook.add_worksheet("ALL_PRODUCTS")

            pivot_df.write_excel(workbook=workbook,worksheet="ALL_PRODUCTS")

            for i, col in enumerate(pivot_df.columns):
                if i < 3:
                    ws2.set_column(i, i, 20)   # FIXED WIDTH for first 3 columns
                else:
                    ws2.set_column(i, i, max(12, len(col) + 2))  # dynamic width

                ws2.write(0, i, col, header_format)

        print(f"File saved at: {file_path}")

    except Exception as e:
        print(traceback.format_exc())
        print(f"Error: {e}")
