import datetime
import calendar
import traceback
import polars as pl
import dashboard_studio_model

from orchestrator.analytics.solar_helpers import SolarHelpers


class SolarCapacity:
    """
    Class for handling solar capacity analytics and dashboard summary operations.
    """

    @classmethod
    async def route_action(cls, data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
        """
        Routes to the appropriate function based on the action parameter.

        Parameters:
        data (Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
            Parameters containing action and other query parameters.

        Returns:
        dict: Response from the called function.
        """
        # Mapping of actions to  handler functions
        function_mapping = {
            "get_total_installed_capacity": cls.get_total_installed_capacity,
            "get_energy_generated": cls.get_energy_generated,
            "get_active_total_plants": cls.get_active_total_plants,
            "get_efficiency": cls.get_efficiency,
            "get_efficiency_last_30_days": cls.get_efficiency_last_30_days
        }

        action = data.action if hasattr(data, 'action') and data.action else "get_total_installed_capacity"

        if action not in function_mapping:
            return {
                "status": "error",
                "message": f"Unknown action: {action}",
                "error": f"Action '{action}' is not supported. Available actions: {list(function_mapping.keys())}"
            }

        try:
            return await function_mapping[action](data)
        except Exception as e:
            print(f"Error in SolarCapacity.route_action for action '{action}': {e}")
            return {
                "status": "error",
                "message": f"Error executing action '{action}'",
                "error": str(e)
            }

    @classmethod
    async def get_total_installed_capacity(cls, data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
        """
        Class method to get solar dashboard summary.
        Reads solar installation data from Excel, enriches with location_master (bu, sap_id, name, zone),
        filters by monitoring status, calculates total installed capacity, and returns the result.

        Parameters:
        data (Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
            Parameters for the solar dashboard summary query.

        Returns:
        dict: Response containing status and total_installed_capacity or error information.
        """
        try:
            # Extract filters and drill_state from data parameter
            filters = getattr(data, 'filters', None)
            drill_state = getattr(data, 'drill_state', '') or ''

            # Get solar master data with location_master enrichment (vlookup to get bu, sap_id, name, zone)
            solar = await SolarHelpers.get_solar_master_data(filters=filters, drill_state=drill_state)

            # Apply filters to the enriched DataFrame (filters on bu, sap_id, name, zone, etc.)
            if filters:
                solar = SolarHelpers.apply_filters_to_dataframe(solar, filters)

            # Filter by monitoring status
            solar = solar.filter(pl.col('Monitoring').cast(pl.Utf8).str.strip_chars().str.to_lowercase() == 'yes')

            total_kw = (solar.select(pl.col('Plant Capacity\r\n  KWp').cast(pl.Float64, strict=False).sum()).item())
            total_mw = (total_kw * 4) / 1000

            return {
                "status": "success",
                "total_installed_capacity": round(total_mw, 2)
            }

        except Exception as e:
            print(f"Error in SolarCapacity.get_total_installed_capacity: {e}")
            return {
                "status": "error",
                "total_installed_capacity": 0,
                "error": str(e)
            }

    @classmethod
    async def get_energy_generated(cls,
                                   data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
        """
        Calculate estimated energy from Excel data.
        Enriches Excel with location_master, then calculates estimated_energy = Plant Capacity * 4 * days_in_month.

        Parameters:
        data (Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
            Parameters for the energy generated query.

        Returns:
        dict: Response containing status and estimated_energy data or error information.
        """
        try:
            # -------------------------------
            # Validate BU
            # -------------------------------
            bu_code = getattr(data, 'bu', None)
            if not bu_code:
                return {
                    "status": "error",
                    "message": "BU code is required",
                    "error": "BU parameter is missing"
                }

            # -------------------------------
            # Filters & Drill State
            # -------------------------------
            filters = getattr(data, 'filters', None)
            drill_state = getattr(data, 'drill_state', '') or ''

            # -------------------------------
            # Extract date range from filters
            # -------------------------------
            filter_start_date, filter_end_date = SolarHelpers.extract_date_range_from_filters(filters)

            # If start date is provided but end date is missing, assume up to today
            if filter_start_date and not filter_end_date:
                filter_end_date = datetime.date.today()
            
            # -------------------------------
            # Year / Month (for default/fallback)
            # -------------------------------
            now = datetime.datetime.now()
            year = getattr(data, 'year', None) or now.year
            month = getattr(data, 'month', None) or now.month

            # ============================================================
            # ESTIMATED ENERGY (Excel)
            # ============================================================
            solar_master = await SolarHelpers.get_solar_master_data(filters=filters, drill_state=drill_state)

            if filters:
                solar_master = SolarHelpers.apply_filters_to_dataframe(solar_master, filters)

            solar_master = solar_master.filter(
                pl.col('Monitoring')
                .cast(pl.Utf8)
                .str.strip_chars()
                .str.to_lowercase() == 'yes'
            )

            solar_master = solar_master.filter(
                pl.col('Plant Capacity\r\n  KWp').is_not_null()
            )

            if solar_master.is_empty():
                return {
                    "status": "error",
                    "message": "No valid plant capacity data found"
                }

            # Calculate days for estimated_energy
            # For estimated_energy: Calculate total days of all months touched by the date range
            # As per user requirement: if range is Dec 3 to Jan 3, it involves Dec and Jan, so days = 31 + 31 = 62
            if filter_start_date and filter_end_date:
                days_for_estimated = 0
                # Iterate from start month to end month
                current_calc_date = filter_start_date.replace(day=1)
                end_calc_date = filter_end_date.replace(day=1)
                
                while current_calc_date <= end_calc_date:
                    _, days_in_month = calendar.monthrange(current_calc_date.year, current_calc_date.month)
                    days_for_estimated += days_in_month
                    # Move to next month
                    # Move to next month manually without relativedelta
                    if current_calc_date.month == 12:
                        current_calc_date = current_calc_date.replace(year=current_calc_date.year + 1, month=1)
                    else:
                        current_calc_date = current_calc_date.replace(month=current_calc_date.month + 1)
            else:
                # Default to current month
                _, days_for_estimated = calendar.monthrange(int(year), int(month))

            estimated_energy = (
                solar_master
                .select(
                    (pl.col('Plant Capacity\r\n  KWp')
                     .cast(pl.Float64, strict=False)
                     .fill_null(0)
                     * 4
                     * days_for_estimated / 1000).sum()
                )
                .item()
            )

            estimated_energy_str = f"{estimated_energy:.2f}" if estimated_energy else "0.00"

            # ============================================================
            # ACTUAL ENERGY (DB)
            # ============================================================
            bu_codes = (
                solar_master
                .select(pl.col("BU Code"))
                .unique()
                .drop_nulls()
                .to_series()
                .cast(pl.Utf8)
                .str.strip_chars()
                .to_list()
            )

            actual_energy_str = "0.00"

            if bu_codes:
                conn = SolarHelpers.get_db_connection(bu=bu_code)
                cursor = conn.cursor()

                bu_codes_sql = "', '".join(bu_codes)

                query = f"""
                        SELECT
                            YEAR(reading_date) AS year,
                            MONTH(reading_date) AS month,
                            PLANT_CD,
                            MIN(day_start_ts) AS TimestampUTC, 
                            SUM(generated_solar_value) AS generated_solar_value
                        FROM (
                            SELECT
                                CAST(TimestampUTC AS DATE) AS reading_date,
                                MIN(TimestampUTC) AS day_start_ts,
                                PLANT_CD,
                                SourceID,
                                MAX(value) - MIN(value) AS generated_solar_value
                            FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                            WHERE QuantityID = '129'
                              AND PLANT_CD IN ('{bu_codes_sql}')
                            GROUP BY
                                CAST(TimestampUTC AS DATE),
                                PLANT_CD,
                                SourceID
                        ) t
                        GROUP BY
                            reading_date,
                            PLANT_CD
                    """

                result_df = await SolarHelpers.fetch_data(
                    cursor,
                    query,
                    getData=True,
                    enrich_with_location=False
                )

                cursor.close()
                conn.close()

                if result_df is not None and not result_df.is_empty():

                    # -------------------------------
                    # VLOOKUP with location_master
                    # -------------------------------
                    result_df = await SolarHelpers.enrich_with_location_master(
                        result_df,
                        join_column="PLANT_CD",
                        filters=filters,
                        drill_state=drill_state
                    )

                    # -------------------------------
                    # Apply drilldown filters
                    # -------------------------------
                    if filters:
                        result_df = SolarHelpers.apply_filters_to_dataframe(result_df, filters)

                    # -------------------------------
                    # Calculate number of days for actual_energy
                    # -------------------------------
                    # Default fallback: use current month days
                    _, default_days = calendar.monthrange(int(year), int(month))
                    days_for_actual = default_days
                    
                    if not result_df.is_empty() and "TimestampUTC" in result_df.columns:
                        if filter_start_date and filter_end_date:
                            # Use date range from filters
                            days_for_actual = (filter_end_date - filter_start_date).days + 1
                        else:
                            # Count unique dates in the filtered data (latest date range)
                            try:
                                # Extract dates from TimestampUTC column and get unique dates
                                dates_df = result_df.select(
                                    pl.col("TimestampUTC").cast(pl.Date).alias("date")
                                ).drop_nulls()
                                
                                if not dates_df.is_empty():
                                    # Get min and max dates
                                    min_date = dates_df.select(pl.col("date").min()).item()
                                    max_date = dates_df.select(pl.col("date").max()).item()
                                    
                                    if min_date and max_date:
                                        # Convert to date objects if needed
                                        if isinstance(min_date, datetime.datetime):
                                            min_date = min_date.date()
                                        if isinstance(max_date, datetime.datetime):
                                            max_date = max_date.date()
                                        
                                        # Calculate days between min and max date
                                        days_for_actual = (max_date - min_date).days + 1
                                    else:
                                        # Fallback: count unique dates
                                        unique_dates = dates_df.select(pl.col("date").unique())
                                        days_for_actual = unique_dates.height if not unique_dates.is_empty() else default_days
                                else:
                                    # No dates found, use default
                                    days_for_actual = default_days
                            except Exception:
                                days_for_actual = default_days

                    # -------------------------------
                    # Final SUM after filters
                    # -------------------------------
                    if not result_df.is_empty():
                        # Calculate actual energy (sum of generated_solar_value in MWh)
                        # generated_solar_value is already the total energy in kWh for the period
                        actual_energy = (
                            result_df
                            .select(
                                (pl.col("generated_solar_value")
                                 .sum()
                                 / 1000)
                            )
                            .item()
                        )
                        actual_energy_str = f"{actual_energy:.2f}" if actual_energy else "0.00"
                    else:
                        pass

            # -------------------------------
            # Calculate Plant Efficiency Percentage
            # -------------------------------
            # User requested Average Efficiency (Mean of individual plant efficiencies)
            efficiency_percentage = 0.0
            efficiency_percentage_str = "0.00"
            
            try:
                if not solar_master.is_empty():
                    # 1. Prepare Estimates per Plant
                    # Estimated = Capacity * 4 * days_for_estimated / 1000
                    estimated_per_plant = (
                        solar_master
                        .select([
                            pl.col("BU Code").alias("PLANT_CD"),
                            (pl.col('Plant Capacity\r\n  KWp').cast(pl.Float64, strict=False).fill_null(0) * 4 * days_for_estimated / 1000).alias("estimated_mwh")
                        ])
                    )

                    # 2. Aggregate Actuals per Plant
                    if not result_df.is_empty():
                         actual_per_plant = (
                             result_df
                             .group_by("PLANT_CD")
                             .agg(pl.col("generated_solar_value").sum().alias("actual_kwh"))
                         )
                    else:
                         # Create empty dataframe with correct schema if no actual data
                         actual_per_plant = pl.DataFrame({"PLANT_CD": [], "actual_kwh": []}, schema={"PLANT_CD": pl.Utf8, "actual_kwh": pl.Float64})

                    # 3. Join
                    merged = estimated_per_plant.join(actual_per_plant, on="PLANT_CD", how="left").fill_null(0)
                    
                    # 4. Calculate Efficiency per plant
                    # Efficiency = (Actual_kWh / 1000) / Estimated_MWh * 100
                    efficiencies = merged.select(
                        pl.when(pl.col("estimated_mwh") > 0)
                        .then(pl.col("actual_kwh") / 1000 / pl.col("estimated_mwh") * 100)
                        .otherwise(0.0)
                        .alias("eff")
                    )
                    
                    # 5. Average Efficiency
                    efficiency_percentage = efficiencies.select(pl.col("eff").mean()).item()
                    efficiency_percentage_str = f"{efficiency_percentage:.2f}" if efficiency_percentage is not None else "0.00"
                    
            except Exception as e:
                print(f"Error calculating average efficiency: {e}")
                efficiency_percentage_str = "0.00"

            return {
                "status": "success",
                "total_records": solar_master.height,
                "estimated_energy": estimated_energy_str,
                "actual_energy": actual_energy_str,
                "efficiency_percentage": efficiency_percentage_str
            }

        except Exception as e:
            print("Error in get_energy_generated:", e)
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e)
            }

    @classmethod
    async def get_efficiency(cls, data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
        """
        Calculate efficiency per plant and categorize into efficiency classifications.
        
        Categories:
        - Exceptional (>100%): Green
        - Normal (90-100%): Blue
        - Underperforming (50-90%): Orange
        - Critical (<50%): Red

        Parameters:
        data (Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
            Parameters for the efficiency query.
            - category (str, optional): If 'zone', returns heatmap data aggregated by zone.

        Returns:
        dict: Response containing efficiency classification counts or heatmap data.
        """
        try:
            bu_code = getattr(data, 'bu', None)
            if not bu_code:
                return {
                    "status": "error",
                    "message": "BU code is required",
                    "error": "BU parameter is missing"
                }

            category = getattr(data, 'category', None)
            filters = getattr(data, 'filters', None)
            drill_state = getattr(data, 'drill_state', '') or ''
            
            filter_start_date, filter_end_date = SolarHelpers.extract_date_range_from_filters(filters)

            now = datetime.datetime.now()
            year = getattr(data, 'year', None) or now.year
            month = getattr(data, 'month', None) or now.month

            # Get solar master data with filters
            solar_master = await SolarHelpers.get_solar_master_data(filters=filters, drill_state=drill_state)
            if filters:
                solar_master = SolarHelpers.apply_filters_to_dataframe(solar_master, filters)

            solar_master = solar_master.filter(
                pl.col('Monitoring').cast(pl.Utf8).str.strip_chars().str.to_lowercase() == 'yes'
            )
            solar_master = solar_master.filter(pl.col('Plant Capacity\r\n  KWp').is_not_null())

            if solar_master.is_empty():
                return {
                    "status": "error",
                    "message": "No valid plant capacity data found"
                }

            # Determine date range for query and estimation
            if filter_start_date and filter_end_date:
                query_start_date = filter_start_date
                query_end_date = filter_end_date
                # Ensure they are date objects
                if isinstance(query_start_date, datetime.datetime):
                    query_start_date = query_start_date.date()
                if isinstance(query_end_date, datetime.datetime):
                    query_end_date = query_end_date.date()
            else:
                # Default to the specific month requested
                query_start_date = datetime.date(int(year), int(month), 1)
                _, last_day = calendar.monthrange(int(year), int(month))
                query_end_date = datetime.date(int(year), int(month), last_day)

            # Calculate days for estimated energy
            days_for_estimated = (query_end_date - query_start_date).days + 1

            # Get BU codes for database query
            bu_codes = (
                solar_master
                .select(pl.col("BU Code"))
                .unique()
                .drop_nulls()
                .to_series()
                .cast(pl.Utf8)
                .str.strip_chars()
                .to_list()
            )

            if not bu_codes:
                return {
                    "status": "success",
                    "exceptional": 0,
                    "normal": 0,
                    "underperforming": 0,
                    "critical": 0
                }

            # Fetch actual energy data from database
            conn = SolarHelpers.get_db_connection(bu=bu_code)
            cursor = conn.cursor()
            bu_codes_sql = "', '".join(bu_codes)

            query = f"""
                SELECT
                    YEAR(reading_date) AS year,
                    MONTH(reading_date) AS month,
                    PLANT_CD,
                    MAX(LocationName) AS LocationName,
                    MIN(day_start_ts) AS TimestampUTC, 
                    SUM(generated_solar_value) AS generated_solar_value
                FROM (
                    SELECT
                        CAST(TimestampUTC AS DATE) AS reading_date,
                        MIN(TimestampUTC) AS day_start_ts,
                        PLANT_CD,
                        SourceID,
                        LocationName,
                        MAX(value) - MIN(value) AS generated_solar_value
                    FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                    WHERE QuantityID = '129'
                      AND PLANT_CD IN ('{bu_codes_sql}')
                      AND CAST(TimestampUTC AS DATE) >= '{query_start_date}'
                      AND CAST(TimestampUTC AS DATE) <= '{query_end_date}'
                    GROUP BY
                        CAST(TimestampUTC AS DATE),
                        PLANT_CD,
                        SourceID,
                        LocationName
                ) t
                GROUP BY
                    YEAR(reading_date),
                    MONTH(reading_date),
                    PLANT_CD
            """

            result_df = await SolarHelpers.fetch_data(cursor, query, getData=True, enrich_with_location=False)
            cursor.close()
            conn.close()

            # Calculate days for actual energy
            _, default_days = calendar.monthrange(int(year), int(month))
            days_for_actual = default_days
            
            if result_df is not None and not result_df.is_empty():
                result_df = await SolarHelpers.enrich_with_location_master(
                    result_df, join_column="PLANT_CD", filters=filters, drill_state=drill_state
                )
                if filters:
                    result_df = SolarHelpers.apply_filters_to_dataframe(result_df, filters)

                if not result_df.is_empty() and "TimestampUTC" in result_df.columns:
                    if filter_start_date and filter_end_date:
                        days_for_actual = (filter_end_date - filter_start_date).days + 1
                    else:
                        try:
                            dates_df = result_df.select(pl.col("TimestampUTC").cast(pl.Date).alias("date")).drop_nulls()
                            if not dates_df.is_empty():
                                min_date = dates_df.select(pl.col("date").min()).item()
                                max_date = dates_df.select(pl.col("date").max()).item()
                                if min_date and max_date:
                                    if isinstance(min_date, datetime.datetime):
                                        min_date = min_date.date()
                                    if isinstance(max_date, datetime.datetime):
                                        max_date = max_date.date()
                                    days_for_actual = (max_date - min_date).days + 1
                        except Exception:
                            pass

            # Calculate efficiency per plant
            # Create a mapping of PLANT_CD to estimated energy from Excel
            estimated_per_plant = {}
            plant_names = {}
            plant_zones = {}
            for row in solar_master.iter_rows(named=True):
                plant_cd = SolarHelpers._clean_plant_code(row.get("BU Code"))
                capacity = row.get('Plant Capacity\r\n  KWp')
                name = row.get('name')
                zone = row.get('zone')
                if plant_cd:
                    plant_names[plant_cd] = name
                    plant_zones[plant_cd] = zone
                    if capacity:
                        try:
                            capacity_float = float(capacity) if capacity else 0.0
                            estimated = (capacity_float * 4 * days_for_estimated / 1000)
                            estimated_per_plant[plant_cd] = estimated
                        except (ValueError, TypeError):
                            pass

            # Calculate actual energy per plant from database
            actual_per_plant = {}
            db_plant_names = {}
            if result_df is not None and not result_df.is_empty():
                for row in result_df.iter_rows(named=True):
                    plant_cd = SolarHelpers._clean_plant_code(row.get("PLANT_CD"))
                    generated = row.get("generated_solar_value")
                    db_name = row.get("LocationName")
                    
                    if plant_cd:
                        if db_name:
                            db_plant_names[plant_cd] = db_name
                            
                        if generated:
                            try:
                                generated_float = float(generated) if generated else 0.0
                                # Actual energy per plant in MWh (same logic as get_energy_generated):
                                # sum of generated_solar_value (kWh) converted to MWh
                                actual = generated_float / 1000.0
                                if plant_cd in actual_per_plant:
                                    actual_per_plant[plant_cd] += actual
                                else:
                                    actual_per_plant[plant_cd] = actual
                            except (ValueError, TypeError):
                                pass

            # Calculate efficiency and categorize
            exceptional = 0
            normal = 0
            underperforming = 0
            critical = 0
            
            exceptional_data = [] 
            normal_data = []
            underperforming_data = []
            critical_data = []
            
            # Data structures for zone-wise aggregation
            zone_aggregation = {}  # {zone: {category: [efficiencies]}}

            # Get plants that exist in both Excel (estimated) and DB (actual) - intersection
            all_plants = set(estimated_per_plant.keys()) & set(actual_per_plant.keys())

            for plant_cd in all_plants:
                estimated = estimated_per_plant.get(plant_cd, 0.0)
                actual = actual_per_plant.get(plant_cd, 0.0)
                # Prioritize solar_master name (from location_master), fallback to DB name, then Unknown
                name = plant_names.get(plant_cd) or db_plant_names.get(plant_cd) or "Unknown"
                zone = plant_zones.get(plant_cd) or "Unknown"
                
                if estimated > 0:
                    efficiency = (actual / estimated) * 100
                else:
                    efficiency = 0.0

                plant_detail = {
                    "LocationName": name,
                    "Plant_cd": plant_cd,
                    "energy_generated": f"{actual:.2f}",
                    "efficiency": f"{efficiency:.2f}"
                }
                
                current_category = ""

                # Categorize
                if efficiency > 100:
                    exceptional += 1
                    exceptional_data.append(plant_detail)
                    current_category = "exceptional"
                elif efficiency >= 95 and efficiency <= 100:
                    normal += 1
                    normal_data.append(plant_detail)
                    current_category = "normal"
                elif efficiency > 50 and efficiency < 90:
                    underperforming += 1
                    underperforming_data.append(plant_detail)
                    current_category = "underperforming"
                else:
                    critical += 1
                    critical_data.append(plant_detail)
                    current_category = "critical"
                
                if category and category.lower() == 'zone':
                    if zone not in zone_aggregation:
                        zone_aggregation[zone] = {
                            "exceptional": [],
                            "exceptional_data": [],
                            "normal": [],
                            "normal_data": [],
                            "underperforming": [],
                            "underperforming_data": [],
                            "critical": [],
                            "critical_data": []
                        }
                    zone_aggregation[zone][current_category].append(efficiency)
                    zone_aggregation[zone][f"{current_category}_data"].append(plant_detail)

            if category and category.lower() == 'zone':
                heatmap_data = []
                # Process zone aggregation to count plants and calculate percentages in each category
                for zone_name, categories in zone_aggregation.items():
                    zone_data = {"zone": zone_name}
                    
                    # Calculate total plants in this zone (only counting the efficiency lists, not the data lists)

                    for cat_name in ["exceptional", "normal", "underperforming", "critical"]:
                        efficiencies = categories.get(cat_name, [])
                        data_list = categories.get(f"{cat_name}_data", [])
                        
                        # Count the number of plants for each efficiency category
                        count = len(efficiencies)
                        
                        zone_data[cat_name] = {
                            "count": count
                        }
                        zone_data[f"{cat_name}_data"] = data_list
                        
                    heatmap_data.append(zone_data)

                # Sort by zone name for consistent display
                heatmap_data.sort(key=lambda x: x['zone'])

                return {
                    "status": "success",
                    "heatmap_data": heatmap_data
                }
            
            elif category and category.lower() == 'plant':
                heatmap_data = []
                # For plant category, we list each plant individually
                # We reuse the detailed data lists we populated

                # Combine all plant details
                all_plant_details = exceptional_data + normal_data + underperforming_data + critical_data

                for plant in all_plant_details:
                    plant_name = plant.get("LocationName")
                    efficiency_val = plant.get("efficiency")

                    # Determine category again or map efficiency to columns
                    # Actually we can just reconstruct the row based on the efficiency value
                    try:
                        eff_float = float(efficiency_val)
                    except (ValueError, TypeError):
                        eff_float = 0.0

                    row = {
                        "plant": plant_name,
                        "exceptional": {"count": 0},
                        "exceptional_data": [],
                        "normal": {"count": 0},
                        "normal_data": [],
                        "underperforming": {"count": 0},
                        "underperforming_data": [],
                        "critical": {"count": 0},
                        "critical_data": []
                    }

                    # Set count to 1 for the appropriate category
                    if eff_float > 100:
                        row["exceptional"] = {"count": 1}
                        row["exceptional_data"] = [plant]
                    elif eff_float >= 95 and eff_float <= 100:
                        row["normal"] = {"count": 1}
                        row["normal_data"] = [plant]
                    elif eff_float > 50 and eff_float < 90:
                        row["underperforming"] = {"count": 1}
                        row["underperforming_data"] = [plant]
                    else:
                        row["critical"] = {"count": 1}
                        row["critical_data"] = [plant]

                    heatmap_data.append(row)

                # Sort by plant name
                heatmap_data.sort(key=lambda x: x['plant'] if x['plant'] else "")

                return {
                    "status": "success",
                    "heatmap_data": heatmap_data,
                    "exceptional_data": exceptional_data,
                    "normal_data": normal_data,
                    "underperforming_data": underperforming_data,
                    "critical_data": critical_data
                }

            return {
                "status": "success",
                "exceptional": exceptional,
                "normal": normal,
                "underperforming": underperforming,
                "critical": critical,
                "exceptional_data": exceptional_data,
                "normal_data": normal_data,
                "underperforming_data": underperforming_data,
                "critical_data": critical_data
            }

        except Exception as e:
            print(f"Error in get_efficiency: {e}")
            traceback.print_exc()
            return {
                "status": "error",
                "exceptional": 0,
                "normal": 0,
                "underperforming": 0,
                "critical": 0,
                "error": str(e)
            }

    @classmethod
    async def get_efficiency_last_30_days(cls, data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
        """
        Calculate daily efficiency and generation data for a date range.
        By default returns last 30 days, but uses date range from filters if provided.
        Returns data suitable for dual-axis charting (Generation & Efficiency Trend).
        
        Parameters:
        data (Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
            Parameters for the efficiency query.
            - bu (str, required): Business unit code
            - filters (list, optional): Filters containing date_filter or date_range to override default 30 days
            
        Returns:
        dict: Response containing daily data with:
            - date: Date string (YYYY-MM-DD)
            - generation: Daily generation in MWh
            - efficiency: Daily efficiency percentage
        """
        try:
            bu_code = getattr(data, 'bu', None)
            if not bu_code:
                return {
                    "status": "error",
                    "message": "BU code is required",
                    "error": "BU parameter is missing"
                }

            filters = getattr(data, 'filters', None)
            drill_state = getattr(data, 'drill_state', '') or ''
            
            # Extract date range from filters if provided
            filter_start_date, filter_end_date = SolarHelpers.extract_date_range_from_filters(filters)
            
            # Use filter date range if available, otherwise default to last 30 days
            if filter_start_date and filter_end_date:
                start_date = filter_start_date
                end_date = filter_end_date
            elif filter_start_date:
                # If only start date provided, use it and default to today as end
                start_date = filter_start_date
                end_date = datetime.date.today()
            elif filter_end_date:
                # If only end date provided, default to 30 days before end date
                end_date = filter_end_date
                start_date = end_date - datetime.timedelta(days=29)  # 30 days including end date
            else:
                # Default to last 30 days
                end_date = datetime.date.today()
                start_date = end_date - datetime.timedelta(days=29)  # 30 days including today
            
            # Get solar master data with filters
            solar_master = await SolarHelpers.get_solar_master_data(filters=filters, drill_state=drill_state)
            if filters:
                solar_master = SolarHelpers.apply_filters_to_dataframe(solar_master, filters)

            solar_master = solar_master.filter(
                pl.col('Monitoring').cast(pl.Utf8).str.strip_chars().str.to_lowercase() == 'yes'
            )
            solar_master = solar_master.filter(pl.col('Plant Capacity\r\n  KWp').is_not_null())

            if solar_master.is_empty():
                return {
                    "status": "error",
                    "message": "No valid plant capacity data found",
                    "data": []
                }

            # Calculate total capacity for estimated energy calculation
            total_capacity_kw = (
                solar_master
                .select(pl.col('Plant Capacity\r\n  KWp').cast(pl.Float64, strict=False).sum())
                .item()
            )

            # Get BU codes for database query
            bu_codes = (
                solar_master
                .select(pl.col("BU Code"))
                .unique()
                .drop_nulls()
                .to_series()
                .cast(pl.Utf8)
                .str.strip_chars()
                .to_list()
            )

            if not bu_codes:
                return {
                    "status": "success",
                    "data": []
                }

            # Fetch daily actual energy data from database for last 30 days
            conn = SolarHelpers.get_db_connection(bu=bu_code)
            cursor = conn.cursor()
            bu_codes_sql = "', '".join(bu_codes)

            query = f"""
                SELECT
                    reading_date,
                    PLANT_CD,
                    MIN(day_start_ts) AS TimestampUTC,
                    SUM(generated_solar_value) AS generated_solar_value
                FROM (
                    SELECT
                        CAST(TimestampUTC AS DATE) AS reading_date,
                        MIN(TimestampUTC) AS day_start_ts,
                        PLANT_CD,
                        SourceID,
                        MAX(value) - MIN(value) AS generated_solar_value
                    FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                    WHERE QuantityID = '129'
                      AND PLANT_CD IN ('{bu_codes_sql}')
                      AND CAST(TimestampUTC AS DATE) >= '{start_date}'
                      AND CAST(TimestampUTC AS DATE) <= '{end_date}'
                    GROUP BY
                        CAST(TimestampUTC AS DATE),
                        PLANT_CD,
                        SourceID
                ) t
                GROUP BY
                    reading_date,
                    PLANT_CD
                ORDER BY
                    reading_date,
                    PLANT_CD
            """

            result_df = await SolarHelpers.fetch_data(cursor, query, getData=True, enrich_with_location=False)
            cursor.close()
            conn.close()

            # Enrich and filter if needed
            if result_df is not None and not result_df.is_empty():
                result_df = await SolarHelpers.enrich_with_location_master(
                    result_df, join_column="PLANT_CD", filters=filters, drill_state=drill_state
                )
                if filters:
                    result_df = SolarHelpers.apply_filters_to_dataframe(result_df, filters)
                
                # Aggregate by date after filtering
                if not result_df.is_empty() and "reading_date" in result_df.columns:
                    result_df = (
                        result_df
                        .group_by("reading_date")
                        .agg([
                            pl.col("generated_solar_value").sum().alias("generated_solar_value"),
                            pl.col("TimestampUTC").min().alias("TimestampUTC")
                        ])
                        .sort("reading_date")
                    )

            # Prepare daily data
            daily_data = []
            
            # Create a mapping of date to generation from result_df
            date_to_generation = {}
            if result_df is not None and not result_df.is_empty():
                for row in result_df.iter_rows(named=True):
                    reading_date = row.get("reading_date")
                    generated_value = row.get("generated_solar_value")
                    
                    # Convert reading_date to date object if needed
                    if isinstance(reading_date, datetime.datetime):
                        reading_date = reading_date.date()
                    elif isinstance(reading_date, str):
                        try:
                            reading_date = datetime.datetime.strptime(reading_date, "%Y-%m-%d").date()
                        except ValueError:
                            continue
                    
                    if reading_date and generated_value:
                        try:
                            # Convert kWh to MWh
                            generation_mwh = float(generated_value) / 1000.0
                            if reading_date in date_to_generation:
                                date_to_generation[reading_date] += generation_mwh
                            else:
                                date_to_generation[reading_date] = generation_mwh
                        except (ValueError, TypeError):
                            pass
            
            # Create a date range for all days in the selected period
            current_date = start_date
            while current_date <= end_date:
                # Get generation for this date
                generation_mwh = date_to_generation.get(current_date, 0.0)
                
                # Calculate estimated energy for this day
                # Estimated = Capacity (KW) * 4 (kWh per KW per day) / 1000 (to MWh)
                estimated_mwh = (total_capacity_kw * 4) / 1000.0 if total_capacity_kw else 0.0
                
                # Calculate efficiency percentage
                if estimated_mwh > 0:
                    efficiency_pct = (generation_mwh / estimated_mwh) * 100.0
                else:
                    efficiency_pct = 0.0
                
                daily_data.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "generation": round(generation_mwh, 2),
                    "efficiency": round(efficiency_pct, 2)
                })
                
                current_date += datetime.timedelta(days=1)

            return {
                "status": "success",
                "data": daily_data
            }

        except Exception as e:
            print(f"Error in get_efficiency_last_30_days: {e}")
            traceback.print_exc()
            return {
                "status": "error",
                "data": [],
                "error": str(e)
            }

    @classmethod
    async def get_active_total_plants(cls,
                                      data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
        """
        Get active and total plants count.
        Total plants: unique sap_id count from Excel
        Active plants: distinct PLANT_CD from database table
        Actual active plants: PLANT_CD from database that match with Excel sap_id

        Parameters:
        data (Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
            Parameters for the query. Must contain 'bu' field.

        Returns:
        dict: Response containing status, total_plants, active_plants, and actual_active_plants count.
        """
        try:
            bu_code = getattr(data, 'bu', None)
            if not bu_code:
                return {
                    "status": "error",
                    "message": "BU code is required",
                    "error": "BU parameter is missing"
                }

            filters = getattr(data, 'filters', None)
            drill_state = getattr(data, 'drill_state', '') or ''

            # Get Excel data with filters applied
            solar = await SolarHelpers.get_solar_master_data(filters=filters, drill_state=drill_state)
            if filters:
                solar = SolarHelpers.apply_filters_to_dataframe(solar, filters)

            bu_code_column = 'BU Code'
            if bu_code_column not in solar.columns:
                return {
                    "status": "error",
                    "message": "BU Code column not found in Excel file",
                    "error": f"Available columns: {list(solar.columns)}"
                }

            # Get and clean unique sap_ids from Excel
            sap_id_list = [
                SolarHelpers._clean_plant_code(code)
                for code in solar.select(pl.col(bu_code_column)).unique().drop_nulls()[bu_code_column].to_list()
                if SolarHelpers._clean_plant_code(code) is not None
            ]

            if not sap_id_list:
                return {
                    "status": "error",
                    "message": "No valid sap_id found in Excel file",
                    "error": "BU Code column is empty or contains no valid values"
                }

            total_plants = len(sap_id_list)

            # Fetch data from database
            conn = SolarHelpers.get_db_connection(bu=bu_code)
            cursor = conn.cursor()

            query = f"""
                SELECT
                    CAST(TimestampUTC AS DATE) AS reading_date,
                    PLANT_CD,
                    SourceID,
                    LocationName,
                    MAX(value) - MIN(value) AS generated_solar_value
                FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                WHERE QuantityID = '129' 
                  AND PLANT_CD IN ('{"', '".join(sap_id_list)}')
                GROUP BY
                    CAST(TimestampUTC AS DATE),
                    PLANT_CD,
                    SourceID,
                    LocationName
            """

            result_df = await SolarHelpers.fetch_data(cursor, query, getData=True, enrich_with_location=False)
            cursor.close()
            conn.close()

            # Process database results
            if result_df is None or result_df.is_empty():
                return {
                    "status": "success",
                    "bu": bu_code,
                    "total_plants": total_plants,
                    "active_plants": 0,
                    "actual_active_plants": 0,
                    "active_plants_list": []
                }

            # Enrich and filter
            result_df = await SolarHelpers.enrich_with_location_master(
                result_df, join_column="PLANT_CD", filters=filters, drill_state=drill_state
            )
            if filters:
                result_df = SolarHelpers.apply_filters_to_dataframe(result_df, filters)

            # Filter active plants (generated_solar_value > 0) and get distinct PLANT_CD + LocationName
            active_plants_df = (
                result_df
                .filter((pl.col("generated_solar_value") > 0) & (pl.col("generated_solar_value").is_not_null()))
                .select([pl.col("PLANT_CD"), pl.col("LocationName")])
                .unique()
                .drop_nulls(subset=["PLANT_CD"])
            )

            # Build active plants list with cleaned PLANT_CD
            active_plants_list = []
            for row in active_plants_df.iter_rows(named=True):
                cleaned_cd = SolarHelpers._clean_plant_code(row.get("PLANT_CD"))
                if cleaned_cd:
                    active_plants_list.append({
                        "PLANT_CD": cleaned_cd,
                        "LocationName": row.get("LocationName") or ""
                    })

            # Calculate counts
            active_plants = len(active_plants_list)
            excel_sap_ids_set = set(sap_id_list)
            db_plant_cds_set = {plant["PLANT_CD"] for plant in active_plants_list}
            matched_plants_set = excel_sap_ids_set.intersection(db_plant_cds_set)
            actual_active_plants = len(matched_plants_set)

            # Filter to matched plants only
            matched_plant_cds = [
                plant for plant in active_plants_list
                if plant["PLANT_CD"] in matched_plants_set
            ]

            return {
                "status": "success",
                "bu": bu_code,
                "total_plants": total_plants,
                "active_plants": active_plants,
                "actual_active_plants": actual_active_plants,
                "active_plants_list": matched_plant_cds
            }

        except Exception as e:
            print(f"Error in SolarCapacity.get_active_total_plants: {e}")
            traceback.print_exc()
            return {
                "status": "error",
                "total_plants": 0,
                "active_plants": 0,
                "actual_active_plants": 0,
                "error": str(e)
            }
