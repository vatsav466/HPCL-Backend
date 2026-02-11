import urdhva_base
import polars as pl
import hpcl_ceg_model
import json
from datetime import timedelta



async def fetch_host_tables_as_dfs(data):

    # ---------------------------
    # Build base conditions
    # ---------------------------
    conditions = []

    if data.filters:
        for f in data.filters:

            if not f.value:
                continue

            # -----------------------
            # Handle date range
            # -----------------------
            if f.key == "start_date":

                start_date = f.value if isinstance(f.value, str) else f.value[0]

                end_date_obj = next(
                    (x.value for x in data.filters if x.key == "end_date" and x.value),
                    None
                )

                end_date = (
                    end_date_obj if isinstance(end_date_obj, str)
                    else end_date_obj[0] if end_date_obj else None
                )

                if start_date and end_date:
                    conditions.append(
                        f"created_at::date BETWEEN '{start_date}' AND '{end_date}'"
                    )

                continue

            if f.key == "end_date":
                continue

            # -----------------------
            # Other filters
            # -----------------------
            if isinstance(f.value, str):

                #  If comma separated string → split it
                if "," in f.value:
                    clean_values = [v.strip() for v in f.value.split(",") if v.strip()]
                else:
                    clean_values = [f.value]

            else:
                clean_values = [v for v in f.value if v]

            if not clean_values:
                continue

            if f.cond == "=":
                if len(clean_values) == 1:
                    conditions.append(f"{f.key} = '{clean_values[0]}'")
                else:
                    values = ", ".join(f"'{v}'" for v in clean_values)
                    conditions.append(f"{f.key} IN ({values})")

            elif f.cond == "!=":
                if len(clean_values) == 1:
                    conditions.append(f"{f.key} != '{clean_values[0]}'")
                else:
                    values = ", ".join(f"'{v}'" for v in clean_values)
                    conditions.append(f"{f.key} NOT IN ({values})")

    query_str = " AND ".join(conditions) if conditions else "1=1"

    params = urdhva_base.queryparams.QueryParams(q=query_str, limit=0)

    alerts_query = (
        "alert_section = 'TAS'"
        "AND equipment_name = 'BCU'"
        "AND interlock_name NOT ILIKE '%BCU Permissive Off%'"
    )
    if conditions:
        alerts_query += " AND " + " AND ".join(conditions)

    alerts_params = urdhva_base.queryparams.QueryParams(
        q=alerts_query,
        fields=json.dumps([
            "sap_id", "location_name", "device_name",
            "device_type", "created_at",
            "equipment_name", "interlock_name",
            "vehicle_number"
        ])
    )
    alerts_params.limit = 0

    day_end_params = urdhva_base.queryparams.QueryParams(
        q=query_str,
        fields=json.dumps([
            "created_at", "bcu_number","bay_number","invoiced_qty",
            "bcu_net_totalizer", "mfm_net_totalizer","bcu_start_totalizer","bcu_end_totalizer"
        ])
    )
    day_end_params.limit = 0

    # ---------------------------
    # Fetch Data (UNCHANGED)
    # ---------------------------
    bay_resp = await hpcl_ceg_model.HostBayReAssignment.get_all(params, resp_type="plain")
    local_loaded_resp = await hpcl_ceg_model.HostLocalLoadedTts.get_all(params, resp_type="plain")
    over_loaded_resp = await hpcl_ceg_model.HostOverLoadedTts.get_all(params, resp_type="plain")
    day_end_resp = await hpcl_ceg_model.HostDayEndDetails.get_all(day_end_params, resp_type="plain")
    alerts_resp = await hpcl_ceg_model.Alerts.get_all(alerts_params, resp_type="plain")

    bay_df = pl.DataFrame(bay_resp.get("data", []))
    local_loaded_df = pl.DataFrame(local_loaded_resp.get("data", []))
    over_loaded_df = pl.DataFrame(over_loaded_resp.get("data", []))
    day_end_df = pl.DataFrame(day_end_resp.get("data", []))
    alerts_df = pl.DataFrame(alerts_resp.get("data", []))


    total_bcu_count = 0
    total_active_bays_count = 0

    day_end_df = day_end_df.with_columns([
    pl.col("bcu_start_totalizer").cast(pl.Float64),
    pl.col("bcu_end_totalizer").cast(pl.Float64),
    ])

    grouped_df = (day_end_df.group_by(["bay_number", "bcu_number"]).agg([
            pl.col("bcu_start_totalizer").sum().alias("sum_start"),
            pl.col("bcu_end_totalizer").sum().alias("sum_end"),
        ])
        .with_columns((pl.col("sum_end") - pl.col("sum_start")).abs().alias("total_difference")))
    total_bcu_count = grouped_df.height
    total_active_bays_count = grouped_df.filter(pl.col("total_difference") > 100).height

    # Add table_name column to dataframes that have data
    if len(bay_df) > 0:
        bay_df = bay_df.with_columns(pl.lit('HostBayReAssignment').alias("table_name"))
        bay_df = bay_df.filter(pl.col("reassigned_bay").is_not_null() & (pl.col("reassigned_bay") != ""))
    if len(local_loaded_df) > 0:
        local_loaded_df = local_loaded_df.with_columns(pl.lit('HostLocalLoaded').alias("table_name"))
    if len(over_loaded_df) > 0:
        over_loaded_df = over_loaded_df.with_columns(pl.lit('HostOverLoaded').alias("table_name"))

    # Process alerts_df if it has data
    if len(alerts_df) > 0:
        alerts_df = alerts_df.unique(subset=["vehicle_number", "created_at"])
        if "device_name" in alerts_df.columns:
            alerts_df = alerts_df.with_columns(pl.col("device_name").str.extract(r"BC-(\d{2})", 1).alias("bay_number"))

    if len(day_end_df) > 0 and "bcu_number" in day_end_df.columns:
        day_end_df = day_end_df.with_columns(pl.col("bcu_number").str.extract(r"BC-(\d+)", 1).alias("bay_number_extracted"))

    # Rename bay_number to assigned_bay if column exists
    if len(local_loaded_df) > 0 and "bay_number" in local_loaded_df.columns:
        local_loaded_df = local_loaded_df.rename({'bay_number': 'assigned_bay', 'recipe_name': 'product_name'})
    if len(over_loaded_df) > 0 and "bay_number" in over_loaded_df.columns:
        over_loaded_df = over_loaded_df.rename({'bay_number': 'assigned_bay'})

    # Combine dataframes
    combined_df = pl.concat([bay_df, local_loaded_df, over_loaded_df], how="diagonal_relaxed")

    # Only proceed with processing if combined_df has data
    if len(combined_df) > 0:
        
        if "truck_number" in combined_df.columns:
            combined_df = combined_df.filter((pl.col("truck_number").str.len_chars() >= 9) & pl.col("truck_number").str.contains(r"[A-Z]") & 
                pl.col("truck_number").str.contains(r"[0-9]") & pl.col("truck_number").str.contains(r"^[A-Z0-9]+$"))

        if "loaded_qty" in combined_df.columns:
            combined_df = combined_df.with_columns(pl.col("loaded_qty").sum().over(["truck_number", "created_at"]).alias("cumulative_loaded_qty"))
        
        combined_df = combined_df.unique(subset=["truck_number", "created_at"])

        alerts_count_list = []
        gantry_count_list = []
        bay_alerts_count_list = []
        mfm_vs_bcu_list = []
        bcu_vs_invoice_list = []
        
        for i in range(len(combined_df)):
            current_time = combined_df[i, "created_at"]
            current_date = current_time.date()  # Extract only the date
            current_bay = str(combined_df[i, "assigned_bay"]).zfill(2) 
            
            # Calculate Alerts_Count
            if len(alerts_df) > 0:
                filtered = alerts_df.filter(
                    (pl.col("created_at").cast(pl.Date) == current_date) &
                    (pl.col("equipment_name") == "BCU") &
                    (pl.col("bay_number") == current_bay)
                )
                alerts_count_list.append(len(filtered))
            else:
                alerts_count_list.append(0)
            
            # Calculate Gantry Permissive off Count
            if len(alerts_df) > 0:
                filtered = alerts_df.filter(
                    (pl.col("created_at").cast(pl.Date) == current_date) &
                    (pl.col("equipment_name") == "BCU") &
                    (pl.col("bay_number") == current_bay) &
                    (pl.col("interlock_name") == "Gantry Permissive Off")
                )
                gantry_count_list.append(len(filtered))
            else:
                gantry_count_list.append(0)
            
            
            # Calculate MFM VS BCU
            difference = 0
            if len(day_end_df) > 0:
                filtered = day_end_df.filter(
                    (pl.col("created_at").cast(pl.Date) == current_date) &
                    (pl.col("bay_number_extracted") == current_bay)
                )
                if len(filtered) > 0:
                    bcu_sum = filtered["bcu_net_totalizer"].sum()
                    mfm_sum = filtered["mfm_net_totalizer"].sum()
                    difference = mfm_sum - bcu_sum
            mfm_vs_bcu_list.append(difference)

             # Calculate BCU VS INVOICE
            bcu_vs_invoice_difference = 0
            if len(combined_df) > 0 and "invoiced_qty" in combined_df.columns:
                # Get invoiced_qty for current truck
                current_invoiced_qty = combined_df[i, "invoiced_qty"] if "invoiced_qty" in combined_df.columns else 0
                
                # Get BCU totalizer for current bay and date
                if len(day_end_df) > 0:
                    filtered = day_end_df.filter(
                        (pl.col("created_at").cast(pl.Date) == current_date) &
                        (pl.col("bay_number_extracted") == current_bay)
                    )
                    if len(filtered) > 0:
                        bcu_sum = filtered["bcu_net_totalizer"].sum()
                        bcu_vs_invoice_difference = bcu_sum - (current_invoiced_qty if current_invoiced_qty else 0)
            bcu_vs_invoice_list.append(bcu_vs_invoice_difference)
        
        # Add all calculated columns
        combined_df = combined_df.with_columns(pl.Series("Alerts_Count", alerts_count_list))
        combined_df = combined_df.with_columns(pl.Series("Gantry_Permissive_off_Count", gantry_count_list))
        combined_df = combined_df.with_columns(pl.Series("MFM_VS_BCU", mfm_vs_bcu_list))
        combined_df = combined_df.with_columns(pl.Series("BCU_VS_INVOICE", bcu_vs_invoice_list))
        combined_df = combined_df.with_columns(pl.lit('NO').alias('Cross checked ManuallyAP system'))   

        if "table_name" in combined_df.columns and "loaded_qty" in combined_df.columns and "required_qty" in combined_df.columns:
            combined_df = combined_df.with_columns(pl.when(pl.col('table_name') == 'HostOverLoaded').then(pl.col('loaded_qty') - pl.col('required_qty'))
                .otherwise(None).alias('overloaded_qty'))

        if len(combined_df) > 0:
            combined_df = combined_df.with_columns(
                pl.col("created_at").cast(pl.Date).alias("created_date")
            )
            
            combined_df = combined_df.filter(pl.col("assigned_bay").is_not_null() & (pl.col("assigned_bay") != ""))            
            combined_df = combined_df.unique(
                subset=["table_name", "created_date", "truck_number", "load_number"],
                keep="first"
            ).drop("created_date")
            
        required_columns = [
            'truck_number', 'created_at', 'zone', 'sap_id', 'location_name', 'load_number',
            'product_name', 'required_qty', 'loaded_qty', 'overloaded_qty', 
            'cumulative_loaded_qty', 'assigned_bay', 'reassigned_bay', 'table_name']

        for col in required_columns:
            if col not in combined_df.columns:
                combined_df = combined_df.with_columns(pl.lit(None).alias(col))

        combined_df = combined_df[['truck_number', 'created_at', 'zone' ,'sap_id', 'location_name','load_number', 'product_name', 'required_qty', 'loaded_qty','overloaded_qty','cumulative_loaded_qty', 'assigned_bay', 'reassigned_bay', 
                                'Alerts_Count', 'Gantry_Permissive_off_Count', 'MFM_VS_BCU','BCU_VS_INVOICE', 'Cross checked ManuallyAP system', 'table_name']]
   
    # combined_df.write_csv("/Users/algofusion/Downloads/all_data_after_tesing.csv")

    return combined_df, alerts_df, day_end_df, total_bcu_count, total_active_bays_count

# if _name_ == "_main_":
    # asyncio.run(fetch_host_tables_as_dfs())