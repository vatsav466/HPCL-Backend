import datetime
import calendar
import traceback
import hashlib
import json
import functools
import io
import os
import pandas as pd
import urdhva_base
import polars as pl
import dashboard_studio_model
from fastapi.responses import StreamingResponse
from urdhva_base.ttl_cache import InMemTTLCache
import datetime ,time

from orchestrator.analytics.solar_helpers import SolarHelpers

SOLAR_CACHE_INSTANCES = {}
def with_solar_cache(key_prefix: str, expiration: int = 900):
    """
    Decorator to cache the result of a function using InMemTTLCache.
    Uses a hash of the 'data' parameter to generate a unique cache instance.
    """
    def _normalize_filter_obj(f):
        """
        Convert filter objects (dicts / pydantic-like) into a stable, sortable dict.
        We intentionally keep only the commonly used fields so cache keys are stable.
        """
        if f is None:
            return None
        if isinstance(f, dict):
            obj = f
        else:
            # best-effort for pydantic / attr objects
            obj = {k: getattr(f, k, None) for k in ("key", "cond", "value", "op")}

        # Normalize to a stable subset + stringified values
        return {
            "key": str(obj.get("key") or ""),
            "cond": str(obj.get("cond") or ""),
            "value": obj.get("value"),
            "op": str(obj.get("op") or ""),
        }

    def _normalize_filters(filters):
        if not filters:
            return []
        norm = [_normalize_filter_obj(f) for f in filters]
        norm = [x for x in norm if x is not None]
        # Sort for stability (order of filters in request should not affect cache key)
        norm.sort(key=lambda x: (x.get("key") or "", x.get("cond") or "", str(x.get("value") or ""), x.get("op") or ""))
        return norm

    def _norm_scalar(v):
        # Treat empty strings like None to avoid cache-key churn ("", None)
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s != "" else None
        return v

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(cls, data, *args, **kwargs):
            try:
                debug = os.getenv("SOLAR_CACHE_DEBUG", "").strip() in ("1", "true", "True", "yes", "YES")
                t0 = time.time() if debug else None
                cache_params = {
                    "bu": _norm_scalar(getattr(data, 'bu', None)),
                    "category": _norm_scalar(getattr(data, 'category', None)),
                    "filters": _normalize_filters(getattr(data, 'filters', None)),
                    "drill_state": _norm_scalar(getattr(data, 'drill_state', None)),
                    "year": _norm_scalar(getattr(data, 'year', None)),
                    "month": _norm_scalar(getattr(data, 'month', None)),
                    "action": _norm_scalar(getattr(data, 'action', None)),
                    # download responses differ (StreamingResponse vs JSON)
                    "is_download": getattr(data, 'is_download', False),
                    # include cross_filters/limit/time_grain if present, but normalize for stability
                    "cross_filters": _normalize_filters(getattr(data, 'cross_filters', None)),
                    "limit": _norm_scalar(getattr(data, 'limit', None)),
                    "time_grain": _norm_scalar(getattr(data, 'time_grain', None)),
                }
                # Serialize params to string
                cache_string = json.dumps(cache_params, sort_keys=True, default=str)
                # Create hash
                instance_key = f"{key_prefix}:{hashlib.md5(cache_string.encode()).hexdigest()}"

                # Define the fetch function (closure capturing current args)
                async def fetch_data():
                    return await func(cls, data, *args, **kwargs)

                # Get or create cache instance
                created = False
                if instance_key not in SOLAR_CACHE_INSTANCES:
                    # Create new cache instance
                    SOLAR_CACHE_INSTANCES[instance_key] = InMemTTLCache(
                        ttl_seconds=expiration,
                        fetch_function=fetch_data
                    )
                    created = True

                # Retrieve from cache
                # use a static key "result" because the uniqueness is handled by the instance_key
                cache = SOLAR_CACHE_INSTANCES[instance_key]
                result = await cache.get("result")
                if debug:
                    dt_ms = int((time.time() - t0) * 1000)
                    print(f"[SOLAR_CACHE] key={key_prefix} {'MISS(create)' if created else 'HIT'} dt={dt_ms}ms")
                return result

            except Exception as e:
                print(f"Error in caching wrapper for {key_prefix}: {e}")
                # Fallback to direct call in case of cache error
                return await func(cls, data, *args, **kwargs)
        return wrapper
    return decorator


class SolarCapacity:
    """
    Class for handling solar capacity analytics and dashboard summary operations.
    """

    @staticmethod
    def _get_solar_generation_base_query(plant_codes_sql: str, date_filter_sql: str) -> str:
        """
        Returns the common CTEs (base, w, calc1) for solar generation queries.
        """
        return f"""
            WITH base AS (
                SELECT
                    PLANT_CD,
                    SourceID,
                    TimestampUTC,

                    -- combine cumulative energy PER SOURCE
                    SUM(CASE WHEN QuantityID = 129 THEN Value END) AS Energy_Cumulative_kWh,

                    -- instantaneous values
                    MAX(CASE WHEN QuantityID = 544 THEN Value END) AS Solar_kW,
                    MAX(CASE WHEN QuantityID = 540 THEN Value END) AS Grid_Freq_Hz,
                    MAX(LocationName) AS LocationName

                FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                WHERE PLANT_CD IN ('{plant_codes_sql}')
                    AND LOWER(SourceName) NOT LIKE '%total%'
                    AND QuantityID IN (129, 544, 540)
                    {date_filter_sql}
                GROUP BY
                    PLANT_CD,
                    SourceID,
                    TimestampUTC
            ),

            w AS (
                SELECT
                    b.*,
                    DATEADD(MINUTE, 330, b.TimestampUTC) AS TimestampIST,
                    CAST(DATEADD(MINUTE, 330, b.TimestampUTC) AS DATE) AS DayKey_IST,

                    LAG(b.Energy_Cumulative_kWh)
                        OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                        AS Prev_Energy_Cumulative_kWh,

                    LAG(b.Solar_kW)
                        OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                        AS Prev_Solar_kW,

                    LEAD(b.TimestampUTC)
                        OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                        AS NextTimestampUTC
                FROM base b
            ),

            calc1 AS (
                SELECT
                    *,

                    CASE
                        -- IGNORE energy during power outage
                        WHEN ISNULL(Grid_Freq_Hz, 0) <= 0.01 THEN 0

                        WHEN Energy_Cumulative_kWh IS NULL THEN 0
                        WHEN Prev_Energy_Cumulative_kWh IS NULL THEN 0
                        WHEN Energy_Cumulative_kWh < Prev_Energy_Cumulative_kWh THEN 0
                        WHEN (Energy_Cumulative_kWh - Prev_Energy_Cumulative_kWh) > 100 THEN 0

                        ELSE Energy_Cumulative_kWh - Prev_Energy_Cumulative_kWh
                    END AS SolarGen_kWh_entry
                FROM w
            )
        """

    @staticmethod
    def _get_solar_insights_base_query(bu_codes_sql: str, date_filter_sql: str) -> str:
        """
        Returns the CTEs (base, w, calc1) based on get_insights logic.
        Used for get_energy_generated_new.
        """
        return f"""
            WITH base AS (
                    SELECT
                        PLANT_CD,
                        SourceID,
                        TimestampUTC,

                        -- combine cumulative energy PER SOURCE
                        SUM(CASE WHEN QuantityID = 129 THEN Value END) AS Energy_Cumulative_kWh,
                        -- MAX(CASE WHEN QuantityID = 544 THEN Value END) AS Solar_kW,
                        COALESCE(
                            MAX(CASE WHEN QuantityID = 544 THEN NULLIF(Value,0) END),
                            MAX(CASE WHEN QuantityID = 518 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 519 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 520 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 515 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 516 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 517 THEN NULLIF(ABS(Value),0) END)
                        ) AS Solar_kW,

                        MAX(CASE WHEN QuantityID = 540 THEN Value END) AS Grid_Freq_Hz,
                        MAX(LocationName) AS LocationName

                    FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                    WHERE   PLANT_CD IN ('{bu_codes_sql}')
                        AND LOWER(SourceName) NOT LIKE '%total%'
                        AND QuantityID IN (129,540,544,518,519,520,515,516,517)
                        {date_filter_sql}
                        AND DATEPART(SECOND, DATEADD(MINUTE, 330, TimestampUTC)) = 0
                        AND DATEPART(MINUTE, DATEADD(MINUTE, 330, TimestampUTC)) % 15 = 0
                    GROUP BY
                        PLANT_CD,
                        SourceID,
                        TimestampUTC
                ),

                w AS (
                    SELECT
                        b.*,
                        DATEADD(MINUTE, 330, b.TimestampUTC) AS TimestampIST,
                        CAST(DATEADD(MINUTE, 330, b.TimestampUTC) AS DATE) AS DayKey_IST,
                        CAST(DATEADD(MINUTE,330,b.TimestampUTC) AS TIME) AS TimeIST,

                        LAG(b.Energy_Cumulative_kWh)
                            OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                            AS Prev_Energy_Cumulative_kWh,

                        LAG(b.Solar_kW)
                            OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                            AS Prev_Solar_kW,

                        LEAD(b.TimestampUTC)
                            OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                            AS NextTimestampUTC
                    FROM base b
                ),

                calc1 AS (
                    SELECT
                        *,

                        CASE
                            -- IGNORE energy during power outage
                            WHEN ISNULL(Grid_Freq_Hz, 0) <= 0.01 THEN 0

                            WHEN Energy_Cumulative_kWh IS NULL THEN 0
                            WHEN Prev_Energy_Cumulative_kWh IS NULL THEN 0
                            WHEN Energy_Cumulative_kWh < Prev_Energy_Cumulative_kWh THEN 0
                            WHEN (Energy_Cumulative_kWh - Prev_Energy_Cumulative_kWh) > 100 THEN 0

                            ELSE Energy_Cumulative_kWh - Prev_Energy_Cumulative_kWh
                        END AS SolarGen_kWh_entry,

                        CASE
                            WHEN NextTimestampUTC IS NULL THEN 0.0
                            ELSE DATEDIFF(SECOND, TimestampUTC, NextTimestampUTC) / 3600.0
                        END AS IntervalHours,

                        CASE
                            WHEN COUNT(Solar_kW)
                                 OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) > 0
                            THEN 1 ELSE 0
                        END AS SolarKW_Available_Flag
                    FROM w
                )
        """

    @staticmethod
    def _get_solar_insights_window_query(bu_codes_sql: str, date_filter_sql: str) -> str:
        """
        Returns the CTEs (base, w, calc1, calc, calc_window) based on get_insights logic.
        """
        return f"""
            WITH base AS (
                    SELECT
                        PLANT_CD,
                        SourceID,
                        TimestampUTC,

                        -- combine cumulative energy PER SOURCE
                        SUM(CASE WHEN QuantityID = 129 THEN Value END) AS Energy_Cumulative_kWh,
                        COALESCE(
                            MAX(CASE WHEN QuantityID = 544 THEN NULLIF(Value,0) END),
                            MAX(CASE WHEN QuantityID = 518 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 519 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 520 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 515 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 516 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 517 THEN NULLIF(ABS(Value),0) END)
                        ) AS Solar_kW,

                        MAX(CASE WHEN QuantityID = 540 THEN Value END) AS Grid_Freq_Hz,
                        MAX(LocationName) AS LocationName

                    FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                    WHERE   PLANT_CD IN ('{bu_codes_sql}')
                        AND LOWER(SourceName) NOT LIKE '%total%'
                        AND QuantityID IN (129,540,544,518,519,520,515,516,517)
                        {date_filter_sql}
                        AND DATEPART(SECOND, DATEADD(MINUTE, 330, TimestampUTC)) = 0
                        AND DATEPART(MINUTE, DATEADD(MINUTE, 330, TimestampUTC)) % 15 = 0
                    GROUP BY
                        PLANT_CD,
                        SourceID,
                        TimestampUTC
                ),

                w AS (
                    SELECT
                        b.*,
                        DATEADD(MINUTE, 330, b.TimestampUTC) AS TimestampIST,
                        CAST(DATEADD(MINUTE, 330, b.TimestampUTC) AS DATE) AS DayKey_IST,
                        CAST(DATEADD(MINUTE,330,b.TimestampUTC) AS TIME) AS TimeIST,

                        LAG(b.Energy_Cumulative_kWh)
                            OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                            AS Prev_Energy_Cumulative_kWh,

                        LAG(b.Solar_kW)
                            OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                            AS Prev_Solar_kW,

                        LEAD(b.TimestampUTC)
                            OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                            AS NextTimestampUTC
                    FROM base b
                ),

                calc1 AS (
                    SELECT
                        *,

                        CASE
                            -- IGNORE energy during power outage
                            WHEN ISNULL(Grid_Freq_Hz, 0) <= 0.01 THEN 0

                            WHEN Energy_Cumulative_kWh IS NULL THEN 0
                            WHEN Prev_Energy_Cumulative_kWh IS NULL THEN 0
                            WHEN Energy_Cumulative_kWh < Prev_Energy_Cumulative_kWh THEN 0
                            WHEN (Energy_Cumulative_kWh - Prev_Energy_Cumulative_kWh) > 100 THEN 0

                            ELSE Energy_Cumulative_kWh - Prev_Energy_Cumulative_kWh
                        END AS SolarGen_kWh_entry,

                        CASE
                            WHEN NextTimestampUTC IS NULL THEN 0.0
                            ELSE DATEDIFF(SECOND, TimestampUTC, NextTimestampUTC) / 3600.0
                        END AS IntervalHours,

                        CASE
                            WHEN COUNT(Solar_kW)
                                 OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) > 0
                            THEN 1 ELSE 0
                        END AS SolarKW_Available_Flag
                    FROM w
                ),

                calc AS (
                    SELECT
                        *,

                        CASE
                            WHEN ISNULL(Grid_Freq_Hz, 0) <= 0.01 THEN 1 ELSE 0
                        END AS PowerOutageFlag,

                        CASE
                            WHEN SolarKW_Available_Flag = 1 AND Solar_kW > 0.6 THEN 1
                            WHEN SolarKW_Available_Flag = 0 AND ISNULL(SolarGen_kWh_entry, 0) > 0 THEN 1
                            ELSE 0
                        END AS SolarWindowFlag,

                        CASE
                            WHEN ISNULL(Grid_Freq_Hz, 0) > 0.01
                             AND (
                                    (SolarKW_Available_Flag = 1 AND Solar_kW > 0.6)
                                 OR (SolarKW_Available_Flag = 0 AND ISNULL(SolarGen_kWh_entry, 0) > 0)
                                 )
                            THEN 1 ELSE 0
                        END AS SolarGeneratingFlag,

                        CASE
                            WHEN ISNULL(Grid_Freq_Hz, 0) > 0.01
                             AND (
                                    (SolarKW_Available_Flag = 1 AND Solar_kW <= 0.6)
                                 OR (SolarKW_Available_Flag = 0 AND ISNULL(SolarGen_kWh_entry, 0) = 0)
                                 )
                            THEN 1 ELSE 0
                        END AS SolarZeroWhileGridOnFlag,

                        CASE
                            WHEN SolarKW_Available_Flag = 1
                                 AND Solar_kW >= 0.5
                            THEN 1

                            WHEN SolarKW_Available_Flag = 0
                                 AND ISNULL(SolarGen_kWh_entry, 0) > 0.5                          
                                 AND LAG(ISNULL(SolarGen_kWh_entry, 0))
                                     OVER (PARTITION BY PLANT_CD, SourceID ORDER BY TimestampUTC) = 0
                            THEN 1

                            ELSE 0
                        END AS SolarStartFlag,

                        CASE
                            WHEN SolarKW_Available_Flag = 1
                                 AND ISNULL(Prev_Solar_kW, 0) > 0.25
                                 AND ISNULL(Solar_kW, 0) <= 0.5

                            THEN 1

                            WHEN SolarKW_Available_Flag = 0
                                 AND ISNULL(SolarGen_kWh_entry, 0) < 0.25

                                 AND LAG(ISNULL(SolarGen_kWh_entry, 0))
                                     OVER (PARTITION BY PLANT_CD, SourceID ORDER BY TimestampUTC) > 0
                            THEN 1

                            ELSE 0
                        END AS SolarEndFlag
                    FROM calc1
                ),

                calc_window AS (
                    SELECT
                        *,
                        MIN(CASE WHEN SolarStartFlag = 1 THEN TimestampUTC END)
                            OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarStart_UTC,

                        MIN(CASE 
                            WHEN SolarStartFlag = 1 
                             AND CAST(TimestampIST AS TIME) >= '05:30:00'
                            THEN TimestampIST 
                        END)
                        OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarStart_IST,

                        MAX(CASE WHEN SolarEndFlag = 1 THEN TimestampUTC END)
                            OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarEnd_UTC,

                        MAX(CASE 
                            WHEN SolarGeneratingFlag = 1
                             AND CAST(TimestampIST AS TIME) >= '05:30:00'
                            THEN TimestampIST 
                        END)
                        OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarEnd_IST
                    FROM calc
                )
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
            "get_active_inactive_total_plants": cls.get_active_inactive_total_plants,
            "get_solar_summary": cls.get_solar_summary,
            "get_efficiency": cls.get_efficiency,
            "get_efficiency_last_30_days": cls.get_efficiency_last_30_days,
            "get_insights": cls.get_insights,
            "get_overall_insights": cls.get_overall_insights,
            "get_energy_generated_new": cls.get_energy_generated_new
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
    @with_solar_cache("solar_total_installed_capacity", 900)
    async def get_total_installed_capacity(cls,
                                           data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
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
            if "DOC" in solar.columns:
                solar = solar.filter(
                    pl.col("DOC")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.to_lowercase() != "pending"
                )

            total_kw = (solar.select(pl.col('Plant Capacity').cast(pl.Float64, strict=False).sum()).item())

            return {
                "status": "success",
                "total_installed_capacity": round(total_kw, 2)
            }

        except Exception as e:
            print(f"Error in SolarCapacity.get_total_installed_capacity: {e}")
            return {
                "status": "error",
                "total_installed_capacity": 0,
                "error": str(e)
            }

    @classmethod
    @with_solar_cache("solar_energy_generated", 900)
    async def get_energy_generated_new(cls,
                                   data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
        """
        Calculate estimated energy from Excel data.
        Enriches Excel with location_master, then calculates estimated_energy = Plant Capacity * 4 * number_of_days.

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

            if "DOC" in solar_master.columns:
                solar_master = solar_master.filter(
                    pl.col("DOC")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.to_lowercase() != "pending"
                )

            solar_master = solar_master.filter(
                pl.col('Plant Capacity').is_not_null()
            )

            if solar_master.is_empty():
                return {
                    "status": "error",
                    "message": "No valid plant capacity data found"
                }

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

            result_df = None
            if bu_codes:
                conn = SolarHelpers.get_db_connection(bu=bu_code)
                cursor = conn.cursor()

                bu_codes_sql = "', '".join(bu_codes)

                # -------------------------------
                # Date filter SQL
                # -------------------------------
                date_filter_sql = ""
                if filter_start_date:
                    date_filter_sql += (
                        " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                        f">= '{filter_start_date}'"
                    )

                if filter_end_date:
                    date_filter_sql += (
                        " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                        f"<= '{filter_end_date}'"
                    )

                query = f"""
                {cls._get_solar_generation_base_query(bu_codes_sql, date_filter_sql)}

                SELECT
                    YEAR(DayKey_IST) AS year,
                    MONTH(DayKey_IST) AS month,
                    PLANT_CD,
                    MIN(TimestampUTC) AS TimestampUTC, 
                    SUM(SolarGen_kWh_entry) AS generated_solar_value
                FROM calc1
                GROUP BY
                    DayKey_IST,
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
                    # VLOOKUP with location_master
                    result_df = await SolarHelpers.enrich_with_location_master(
                        result_df,
                        join_column="PLANT_CD",
                        filters=filters,
                        drill_state=drill_state
                    )

            # -------------------------------
            # Calculate number of days for BOTH Estimated and Actual
            # -------------------------------
            # Default fallback: use current month days
            _, default_days = calendar.monthrange(int(year), int(month))
            days_count = default_days

            if filter_start_date and filter_end_date:
                # Use date range from filters
                days_count = (filter_end_date - filter_start_date).days + 1
            elif result_df is not None and not result_df.is_empty() and "TimestampUTC" in result_df.columns:
                # Calculate from DB timestamps if filters are missing
                try:
                    dates_df = result_df.select(
                        pl.col("TimestampUTC").cast(pl.Date).alias("date")
                    ).drop_nulls()

                    if not dates_df.is_empty():
                        min_date = dates_df.select(pl.col("date").min()).item()
                        max_date = dates_df.select(pl.col("date").max()).item()

                        if min_date and max_date:
                            if isinstance(min_date, datetime.datetime):
                                min_date = min_date.date()
                            if isinstance(max_date, datetime.datetime):
                                max_date = max_date.date()
                            days_count = (max_date - min_date).days + 1
                        else:
                            unique_dates = dates_df.select(pl.col("date").unique())
                            days_count = unique_dates.height if not unique_dates.is_empty() else default_days
                except Exception as e:
                    print(f"Error calculating days from DB: {e}")
                    pass

            # ============================================================
            # Calculate Estimated Energy (using days_count)
            # ============================================================
            total_plant_capacity = (
                solar_master
                .select(
                    pl.col('Plant Capacity')
                    .cast(pl.Float64, strict=False)
                    .fill_null(0)
                    .sum()
                )
                .item()
            )

            # Identify matched SAP IDs (those present in the DB results)
            matched_sap_ids = set()
            if result_df is not None and not result_df.is_empty():
                try:
                    # distinct PLANT_CD from result_df
                    unique_plants = result_df.select(pl.col("PLANT_CD")).unique().to_series().to_list()
                    for p_cd in unique_plants:
                        if p_cd:
                            matched_sap_ids.add(str(p_cd).strip())
                except Exception as e:
                    print(f"Error extracting matched SAP IDs: {e}")

            # Calculate estimated energy ONLY for matched plants
            if matched_sap_ids:
                estimated_energy = (
                    solar_master
                    .filter(pl.col("BU Code").cast(pl.Utf8).str.strip_chars().is_in(matched_sap_ids))
                    .select(
                        (pl.col('Plant Capacity')
                        .cast(pl.Float64, strict=False)
                        .fill_null(0)
                        * 4
                        * days_count).sum()
                    )
                    .item()
                ) or 0.0
            else:
                estimated_energy = 0.0

            estimated_energy_str = f"{estimated_energy:.2f}" if estimated_energy else "0.00"

            # ============================================================
            # Calculate Actual Energy
            # ============================================================
            actual_energy_str = "0.00"
            actual_energy = 0.0

            if result_df is not None and not result_df.is_empty():
                # Calculate actual energy (sum of generated_solar_value in MWh)
                actual_energy = (
                    result_df
                    .select(
                        (pl.col("generated_solar_value")
                         .sum())
                    )
                    .item()
                )
                actual_energy_str = f"{actual_energy:.2f}" if actual_energy else "0.00"

            # -------------------------------
            # Calculate Plant Efficiency Percentage
            # -------------------------------
            efficiency_percentage = 0.0

            if estimated_energy and estimated_energy > 0:
                efficiency_percentage = (actual_energy / estimated_energy) * 100

            efficiency_percentage_str = f"{efficiency_percentage:.2f}"

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

    @staticmethod
    def _calculate_today_estimated_energy(
            aggregated_df,
            plant_cap_map,
            avg_window_map,
            return_per_plant: bool = False
    ):
        total_estimated_energy = 0.0
        total_actual_energy = 0.0
        total_plant_capacity_hour = 0.0

        estimated_per_plant = {} if return_per_plant else None
        actual_per_plant = {} if return_per_plant else None

        # -----------------------------
        # Current IST time
        # -----------------------------
        now = (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).time()

        solar_start = datetime.time(5, 30)
        solar_end = datetime.time(19, 30)

        if now < solar_start:
            elapsed_hours = 0
        elif now > solar_end:
            elapsed_hours = 14
        else:
            elapsed_hours = (
                                    datetime.datetime.combine(datetime.datetime.today(), now) -
                                    datetime.datetime.combine(datetime.datetime.today(), solar_start)
                            ).total_seconds() / 3600

        print("DEBUG: elapsed_hours =", elapsed_hours)

        # -----------------------------
        # Loop per plant
        # -----------------------------
        for row in aggregated_df.iter_rows(named=True):

            p_cd = SolarHelpers._clean_plant_code(row["PLANT_CD"])
            actual_e = float(row["total_actual_day"] or 0.0)
            window_h = float(row["window_h"] or 0.0)
            cap = plant_cap_map.get(p_cd, 0.0)

            total_actual_energy += actual_e
            if return_per_plant:
                actual_per_plant[p_cd] = actual_per_plant.get(p_cd, 0.0) + actual_e

            if cap > 0 and window_h > 0:
                total_plant_capacity_hour += cap * window_h

            avg_window = avg_window_map.get(p_cd)

            if not avg_window:
                avg_window = 14

            if window_h == 0:
                window_h = elapsed_hours

            if cap > 0:
                per_hour_energy = cap / avg_window
                per_slot_energy = per_hour_energy * 0.25
                slots_elapsed = int(window_h / 0.25)

                estimated_energy = per_slot_energy * slots_elapsed * 4
                total_estimated_energy += estimated_energy
                if return_per_plant:
                    estimated_per_plant[p_cd] = estimated_per_plant.get(p_cd, 0.0) + estimated_energy

        resp = {
            "total_estimated_energy": total_estimated_energy,
            "total_actual_energy": total_actual_energy,
            "total_plant_capacity_hour": total_plant_capacity_hour
        }
        if return_per_plant:
            resp["estimated_per_plant"] = estimated_per_plant
            resp["actual_per_plant"] = actual_per_plant
        return resp

    @staticmethod
    def _build_estimated_energy_per_plant(
            solar_master,
            days_count: int
    ):
        """
        Build per-plant estimated energy map from solar master (Excel/location_master enriched).

        Estimated Energy (kWh) = Plant Capacity (kW) * 4 (kWh/kW/day) * days_count

        Returns:
            tuple:
                estimated_per_plant (dict[str, float])
                plant_names (dict[str, Any])
                plant_zones (dict[str, Any])
        """
        plant_capacities = {}
        plant_names = {}
        plant_zones = {}

        # Aggregate plant capacity per BU Code / PLANT_CD (normalized)
        for row in solar_master.iter_rows(named=True):
            plant_cd = SolarHelpers._clean_plant_code(row.get("BU Code"))
            if not plant_cd:
                continue

            plant_names[plant_cd] = row.get("name")
            plant_zones[plant_cd] = row.get("zone")

            capacity = row.get("Plant Capacity")
            if capacity is None:
                continue

            try:
                capacity_float = float(capacity) if capacity else 0.0
            except (ValueError, TypeError):
                continue

            plant_capacities[plant_cd] = plant_capacities.get(plant_cd, 0.0) + capacity_float

        estimated_per_plant = {
            plant_cd: (capacity * 4 * days_count)
            for plant_cd, capacity in plant_capacities.items()
        }

        return estimated_per_plant, plant_names, plant_zones

        # ============================================================
        # MAIN FUNCTION
        # ============================================================
    @classmethod
    @with_solar_cache("solar_energy_generated_new", 900)
    async def get_energy_generated(cls, data):

        try:
            bu_code = getattr(data, 'bu', None)
            if not bu_code:
                return {
                    "status": "error",
                    "message": "BU code is required"
                }

            filters = getattr(data, 'filters', None)
            drill_state = getattr(data, 'drill_state', '') or ''

            filter_start_date, filter_end_date = SolarHelpers.extract_date_range_from_filters(filters)

            # Detect today filter
            is_today_filter = False
            today_date = datetime.date.today()

            if filters:
                for f in filters:
                    f_cond = str((f.get("cond") if isinstance(f, dict) else getattr(f, "cond", "")) or "").lower()
                    f_val = str((f.get("value") if isinstance(f, dict) else getattr(f, "value", "")) or "").lower()

                    if f_cond == "date_filter" and f_val == "t":
                        is_today_filter = True
                        break

            if not is_today_filter and filter_start_date == today_date and filter_end_date == today_date:
                is_today_filter = True

            if filter_start_date and not filter_end_date:
                filter_end_date = datetime.date.today()

            # ============================================================
            # GET SOLAR MASTER
            # ============================================================
            solar_master = await SolarHelpers.get_solar_master_data(filters=filters, drill_state=drill_state)

            if filters:
                solar_master = SolarHelpers.apply_filters_to_dataframe(solar_master, filters)

            solar_master = solar_master.filter(
                pl.col('Monitoring').cast(pl.Utf8).str.to_lowercase() == 'yes'
            )
            solar_master = solar_master.filter(pl.col("DOC").cast(pl.Utf8).str.strip_chars().str.to_lowercase() != "pending")

            solar_master = solar_master.filter(pl.col('Plant Capacity').is_not_null())

            if solar_master.is_empty():
                return {"status": "error", "message": "No valid plant capacity"}

            bu_codes = (
                solar_master.select(pl.col("BU Code"))
                .unique()
                .drop_nulls()
                .to_series()
                .cast(pl.Utf8)
                .map_elements(lambda x: SolarHelpers._clean_plant_code(x))
                .to_list()
            )

            total_actual_energy = 0.0
            total_estimated_energy = 0.0
            total_plant_capacity_hour = 0.0

            if bu_codes:
                conn = SolarHelpers.get_db_connection(bu=bu_code)
                cursor = conn.cursor()

                bu_codes_sql = "', '".join(bu_codes)

                # ============================================================
                # TODAY LOGIC
                # ============================================================
                if is_today_filter:

                    # 7-day avg window
                    today_date = datetime.date.today()
                    seven_days_end = today_date - datetime.timedelta(days=1)
                    seven_days_start = seven_days_end - datetime.timedelta(days=6)

                    date_filter_7d = f"""
                        AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE)
                        BETWEEN '{seven_days_start}' AND '{seven_days_end}'
                    """

                    query_7d = f"""
                    {cls._get_solar_insights_window_query(bu_codes_sql, date_filter_7d)}
                    SELECT PLANT_CD, DayKey_IST,
                    (DATEDIFF(SECOND, SolarStart_IST, SolarEnd_IST)/3600.0)+0.75 AS SolarWindowHours_IST
                    FROM calc_window
                    """

                    df_7d = await SolarHelpers.fetch_data(cursor, query_7d, getData=True)

                    avg_window_map = {}
                    if df_7d is not None and not df_7d.is_empty():
                        avg_df = df_7d.group_by("PLANT_CD").agg(
                            pl.col("SolarWindowHours_IST").mean().alias("avg_window")
                        )
                        for r in avg_df.iter_rows(named=True):
                            avg_window_map[str(r["PLANT_CD"]).strip()] = r["avg_window"]

                    # MAIN QUERY
                    date_filter_sql = (
                        " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                        f"= '{today_date}'"
                    )

                    query_main = f"""
                    {cls._get_solar_insights_window_query(bu_codes_sql, date_filter_sql)}
                    SELECT
                        PLANT_CD,
                        DayKey_IST,
                        SUM(SolarGen_kWh_entry) AS actual_energy_day,
                        (DATEDIFF(SECOND, SolarStart_IST, SolarEnd_IST)/3600.0)+0.75 AS SolarWindowHours_IST
                    FROM calc_window
                    GROUP BY PLANT_CD, DayKey_IST, SolarStart_IST, SolarEnd_IST
                    """

                    result_df = await SolarHelpers.fetch_data(cursor, query_main, getData=True)
                    cursor.close()
                    conn.close()

                    if result_df is not None and not result_df.is_empty():

                        plant_cap_map = {}
                        for row in solar_master.iter_rows(named=True):
                            p_cd = SolarHelpers._clean_plant_code(row["BU Code"])
                            cap = float(row["Plant Capacity"] or 0)
                            plant_cap_map[p_cd] = plant_cap_map.get(p_cd, 0) + cap

                        aggregated_df = result_df.group_by(["PLANT_CD", "DayKey_IST"]).agg([
                            pl.col("actual_energy_day").sum().alias("total_actual_day"),
                            pl.col("SolarWindowHours_IST").first().alias("window_h")
                        ])

                        # 🔥 CALL NEW FUNCTION
                        calc = cls._calculate_today_estimated_energy(
                            aggregated_df,
                            plant_cap_map,
                            avg_window_map
                        )

                        total_estimated_energy = calc["total_estimated_energy"]
                        total_actual_energy = calc["total_actual_energy"]
                        total_plant_capacity_hour = calc["total_plant_capacity_hour"]

                # ============================================================
                # NON-TODAY LOGIC
                # ============================================================
                else:
                    date_filter_sql = ""

                    if filter_start_date:
                        date_filter_sql += (
                            " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                            f">= '{filter_start_date}'"
                        )

                    if filter_end_date:
                        date_filter_sql += (
                            " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                            f"<= '{filter_end_date}'"
                        )

                    query_main = f"""
                    {cls._get_solar_generation_base_query(bu_codes_sql, date_filter_sql)}
                    SELECT PLANT_CD, DayKey_IST,
                    SUM(SolarGen_kWh_entry) AS generated_solar_value
                    FROM calc1
                    GROUP BY DayKey_IST, PLANT_CD
                    """

                    result_df = await SolarHelpers.fetch_data(cursor, query_main, getData=True)
                    cursor.close()
                    conn.close()

                    if result_df is not None and not result_df.is_empty():

                        plant_cap_map = {}
                        for row in solar_master.iter_rows(named=True):
                            p_cd = SolarHelpers._clean_plant_code(row["BU Code"])
                            cap = float(row["Plant Capacity"] or 0)
                            plant_cap_map[p_cd] = plant_cap_map.get(p_cd, 0) + cap

                        days_count = (
                                                 filter_end_date - filter_start_date).days + 1 if filter_start_date and filter_end_date else 1

                        for p_cd in result_df["PLANT_CD"].unique():
                            cap = plant_cap_map.get(SolarHelpers._clean_plant_code(p_cd), 0)
                            total_estimated_energy += cap * 4 * days_count

                        total_actual_energy = float(result_df["generated_solar_value"].sum())

            efficiency = (total_actual_energy / total_estimated_energy * 100) if total_estimated_energy else 0

            return {
                "status": "success",
                "estimated_energy": f"{total_estimated_energy:.2f}",
                "actual_energy": f"{total_actual_energy:.2f}",
                "efficiency_percentage": f"{efficiency:.2f}",
                "cumulative_plant_capacity_hour": f"{total_plant_capacity_hour:.2f}"
            }

        except Exception as e:
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    @classmethod
    @with_solar_cache("solar_efficiency", 900)
    async def get_efficiency(cls, data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
        """
        Calculate efficiency per plant and categorize into efficiency classifications.

        Categories:
        - Exceptional (>95%): Green
        - Normal (85-95%): Blue
        - Underperforming (50-85%): Orange
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

            # Detect today filter (same logic as get_energy_generated_new)
            is_today_filter = False
            today_date = datetime.date.today()
            if filters:
                for f in filters:
                    f_cond = str((f.get("cond") if isinstance(f, dict) else getattr(f, "cond", "")) or "").lower()
                    f_val = str((f.get("value") if isinstance(f, dict) else getattr(f, "value", "")) or "").lower()
                    if f_cond == "date_filter" and f_val == "t":
                        is_today_filter = True
                        break
            if not is_today_filter and filter_start_date == today_date and filter_end_date == today_date:
                is_today_filter = True

            # If start date is provided but end date is missing, assume up to today
            if filter_start_date and not filter_end_date:
                filter_end_date = datetime.date.today()

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
            solar_master = solar_master.filter(pl.col('Plant Capacity').is_not_null())

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

            # For "today", use the window query so estimation can use solar window/elapsed logic
            result_df = None
            if is_today_filter:
                # 7-day avg window map (exclude today)
                seven_days_end = today_date - datetime.timedelta(days=1)
                seven_days_start = seven_days_end - datetime.timedelta(days=6)

                date_filter_7d = f"""
                    AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE)
                    BETWEEN '{seven_days_start}' AND '{seven_days_end}'
                """

                query_7d = f"""
                {cls._get_solar_insights_window_query(bu_codes_sql, date_filter_7d)}
                SELECT PLANT_CD, DayKey_IST,
                (DATEDIFF(SECOND, SolarStart_IST, SolarEnd_IST)/3600.0)+0.75 AS SolarWindowHours_IST
                FROM calc_window
                """

                df_7d = await SolarHelpers.fetch_data(cursor, query_7d, getData=True)

                avg_window_map = {}
                if df_7d is not None and not df_7d.is_empty():
                    avg_df = df_7d.group_by("PLANT_CD").agg(
                        pl.col("SolarWindowHours_IST").mean().alias("avg_window")
                    )
                    for r in avg_df.iter_rows(named=True):
                        avg_window_map[str(r["PLANT_CD"]).strip()] = r["avg_window"]

                # Today's window + actual energy
                date_filter_today = (
                    " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                    f"= '{today_date}'"
                )

                query_today = f"""
                {cls._get_solar_insights_window_query(bu_codes_sql, date_filter_today)}
                SELECT
                    PLANT_CD,
                    DayKey_IST,
                    SUM(SolarGen_kWh_entry) AS actual_energy_day,
                    (DATEDIFF(SECOND, SolarStart_IST, SolarEnd_IST)/3600.0)+0.75 AS SolarWindowHours_IST
                FROM calc_window
                GROUP BY PLANT_CD, DayKey_IST, SolarStart_IST, SolarEnd_IST
                """

                result_df = await SolarHelpers.fetch_data(cursor, query_today, getData=True, enrich_with_location=False)

            else:
                # Date filtering for SQL query
                date_filter_sql = ""
                if query_start_date:
                    date_filter_sql += (
                        " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                        f">= '{query_start_date}'"
                    )

                if query_end_date:
                    date_filter_sql += (
                        " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                        f"<= '{query_end_date}'"
                    )
    
                query = f"""
                    {cls._get_solar_generation_base_query(bu_codes_sql, date_filter_sql)}

                    SELECT
                        YEAR(DayKey_IST) AS year,
                        MONTH(DayKey_IST) AS month,
                        PLANT_CD,
                        MAX(LocationName) AS LocationName,
                        MIN(TimestampUTC) AS TimestampUTC, 
                        SUM(SolarGen_kWh_entry) AS generated_solar_value
                    FROM calc1
                    GROUP BY
                        DayKey_IST,
                        PLANT_CD
                """

                result_df = await SolarHelpers.fetch_data(cursor, query, getData=True, enrich_with_location=False)

            cursor.close()
            conn.close()

            # Calculate days for estimated energy AND actual energy (Consistent Logic)
            _, default_days = calendar.monthrange(int(year), int(month))
            days_count = default_days

            if result_df is not None and not result_df.is_empty():
                result_df = await SolarHelpers.enrich_with_location_master(
                    result_df, join_column="PLANT_CD", filters=filters, drill_state=drill_state
                )
                # if filters:
                #     result_df = SolarHelpers.apply_filters_to_dataframe(result_df, filters)

            if filter_start_date and filter_end_date:
                days_count = (filter_end_date - filter_start_date).days + 1
            elif is_today_filter:
                days_count = 1
            elif result_df is not None and not result_df.is_empty() and "TimestampUTC" in result_df.columns:
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
                            days_count = (max_date - min_date).days + 1
                        else:
                            unique_dates = dates_df.select(pl.col("date").unique())
                            days_count = unique_dates.height if not unique_dates.is_empty() else default_days
                except Exception as e:
                    print(f"Error calculating days from DB: {e}")
                    pass

            # Calculate efficiency per plant
            # For today-filter, use _calculate_today_estimated_energy() so estimation uses elapsed/window logic.
            if is_today_filter and result_df is not None and not result_df.is_empty():
                # Meta (names/zones) from solar master
                _, plant_names, plant_zones = cls._build_estimated_energy_per_plant(
                    solar_master=solar_master,
                    days_count=days_count
                )

                # Plant capacity map for today estimation
                plant_cap_map = {}
                for row in solar_master.iter_rows(named=True):
                    p_cd = SolarHelpers._clean_plant_code(row.get("BU Code"))
                    cap = float(row.get("Plant Capacity") or 0)
                    if p_cd:
                        plant_cap_map[p_cd] = plant_cap_map.get(p_cd, 0.0) + cap

                aggregated_df = result_df.group_by(["PLANT_CD", "DayKey_IST"]).agg([
                    pl.col("actual_energy_day").sum().alias("total_actual_day"),
                    pl.col("SolarWindowHours_IST").first().alias("window_h")
                ])

                calc = cls._calculate_today_estimated_energy(
                    aggregated_df,
                    plant_cap_map,
                    avg_window_map,
                    return_per_plant=True
                )

                estimated_per_plant = calc.get("estimated_per_plant") or {}
                actual_per_plant = calc.get("actual_per_plant") or {}
                db_plant_names = {}
            else:
                estimated_per_plant, plant_names, plant_zones = cls._build_estimated_energy_per_plant(
                    solar_master=solar_master,
                    days_count=days_count
                )
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
                                    actual = generated_float
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
                    "efficiency": f"{efficiency:.2f}",
                    "estimated_energy": f"{estimated:.2f}"
                }

                current_category = ""

                # Categorize
                if efficiency > 95:
                    exceptional += 1
                    exceptional_data.append(plant_detail)
                    current_category = "exceptional"
                elif efficiency >= 85 and efficiency <= 95:
                    normal += 1
                    normal_data.append(plant_detail)
                    current_category = "normal"
                elif efficiency >= 50 and efficiency < 85:
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
                # For plant category, list each plant individually
                # Combine all plant details
                all_plant_details = exceptional_data + normal_data + underperforming_data + critical_data

                for plant in all_plant_details:
                    plant_name = plant.get("LocationName")
                    efficiency_val = plant.get("efficiency")

                    # Determine category again or map efficiency to columns
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
                    if eff_float > 95:
                        row["exceptional"] = {"count": 1}
                        row["exceptional_data"] = [plant]
                    elif eff_float >= 85 and eff_float <= 95:
                        row["normal"] = {"count": 1}
                        row["normal_data"] = [plant]
                    elif eff_float >= 50 and eff_float < 85:
                        row["underperforming"] = {"count": 1}
                        row["underperforming_data"] = [plant]
                    else:
                        row["critical"] = {"count": 1}
                        row["critical_data"] = [plant]

                    # Add estimated_energy to the plant data within heatmap_data
                    for cat_data_key in ["exceptional_data", "normal_data", "underperforming_data", "critical_data"]:
                        if row[cat_data_key]:
                            row[cat_data_key][0]["estimated_energy"] = plant.get("estimated_energy")

                    heatmap_data.append(row)

                # Sort by plant name
                heatmap_data.sort(key=lambda x: x['plant'] if x['plant'] else "")

                return {
                    "status": "success",
                    "heatmap_data": heatmap_data
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
    @with_solar_cache("solar_efficiency_last_30_days", 900)
    async def get_efficiency_last_30_days(cls,
                                          data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
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

            # Ensure they are date objects for consistent SQL string formatting
            if isinstance(start_date, datetime.datetime):
                start_date = start_date.date()
            if isinstance(end_date, datetime.datetime):
                end_date = end_date.date()

            # Get solar master data with filters
            solar_master = await SolarHelpers.get_solar_master_data(filters=filters, drill_state=drill_state)
            if filters:
                solar_master = SolarHelpers.apply_filters_to_dataframe(solar_master, filters)

            solar_master = solar_master.filter(
                pl.col('Monitoring').cast(pl.Utf8).str.strip_chars().str.to_lowercase() == 'yes'
            )
            solar_master = solar_master.filter(pl.col('Plant Capacity').is_not_null())

            if solar_master.is_empty():
                return {
                    "status": "error",
                    "message": "No valid plant capacity data found",
                    "data": []
                }

            # Build per-plant estimated energy for 1 day (kWh) using the shared estimation helper.
            # We'll sum per-date based on plants that actually have generation that day.
            estimated_1day_per_plant, _, _ = cls._build_estimated_energy_per_plant(
                solar_master=solar_master,
                days_count=1
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

            today_date = datetime.date.today()
            include_today = start_date <= today_date <= end_date

            # Date filtering for SQL query
            date_filter_sql = ""
            if start_date:
                date_filter_sql += (
                    " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                    f">= '{start_date}'"
                )
            if end_date:
                date_filter_sql += (
                    " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                    f"<= '{end_date}'"
                )

            query = f"""
                {cls._get_solar_generation_base_query(bu_codes_sql, date_filter_sql)}

                SELECT
                    CAST(DayKey_IST AS DATE) AS reading_date,
                    PLANT_CD,
                    MIN(TimestampUTC) AS TimestampUTC,
                    SUM(SolarGen_kWh_entry) AS generated_solar_value
                FROM calc1
                GROUP BY
                    DayKey_IST,
                    PLANT_CD
                ORDER BY
                    DayKey_IST,
                    PLANT_CD
            """

            result_df = await SolarHelpers.fetch_data(cursor, query, getData=True, enrich_with_location=False)

            # ------------------------------------------------------------
            # If the selected range includes today, fetch today's window-hours
            # data so estimated energy can use _calculate_today_estimated_energy.
            # ------------------------------------------------------------
            avg_window_map = {}
            today_window_df = None
            if include_today:
                seven_days_end = today_date - datetime.timedelta(days=1)
                seven_days_start = seven_days_end - datetime.timedelta(days=6)

                date_filter_7d = f"""
                    AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE)
                    BETWEEN '{seven_days_start}' AND '{seven_days_end}'
                """
                query_7d = f"""
                {cls._get_solar_insights_window_query(bu_codes_sql, date_filter_7d)}
                SELECT PLANT_CD, DayKey_IST,
                (DATEDIFF(SECOND, SolarStart_IST, SolarEnd_IST)/3600.0)+0.75 AS SolarWindowHours_IST
                FROM calc_window
                """
                df_7d = await SolarHelpers.fetch_data(cursor, query_7d, getData=True)
                if df_7d is not None and not df_7d.is_empty():
                    avg_df = df_7d.group_by("PLANT_CD").agg(
                        pl.col("SolarWindowHours_IST").mean().alias("avg_window")
                    )
                    for r in avg_df.iter_rows(named=True):
                        avg_window_map[str(r["PLANT_CD"]).strip()] = r["avg_window"]

                date_filter_today = (
                    " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                    f"= '{today_date}'"
                )
                query_today = f"""
                {cls._get_solar_insights_window_query(bu_codes_sql, date_filter_today)}
                SELECT
                    PLANT_CD,
                    DayKey_IST,
                    SUM(SolarGen_kWh_entry) AS actual_energy_day,
                    (DATEDIFF(SECOND, SolarStart_IST, SolarEnd_IST)/3600.0)+0.75 AS SolarWindowHours_IST
                FROM calc_window
                GROUP BY PLANT_CD, DayKey_IST, SolarStart_IST, SolarEnd_IST
                """
                today_window_df = await SolarHelpers.fetch_data(cursor, query_today, getData=True, enrich_with_location=False)

            cursor.close()
            conn.close()

            # Enrich and filter if needed
            generation_df = None
            if result_df is not None and not result_df.is_empty():
                generation_df = await SolarHelpers.enrich_with_location_master(
                    result_df, join_column="PLANT_CD", filters=filters, drill_state=drill_state
                )
                # if filters:
                #     generation_df = SolarHelpers.apply_filters_to_dataframe(generation_df, filters)

                # Aggregate by date after filtering
                if not generation_df.is_empty() and "reading_date" in generation_df.columns:
                    result_df = (
                        generation_df
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
                            generation_mwh = float(generated_value)
                            if reading_date in date_to_generation:
                                date_to_generation[reading_date] += generation_mwh
                            else:
                                date_to_generation[reading_date] = generation_mwh
                        except (ValueError, TypeError):
                            pass

            # Create a date range for all days in the selected period
            current_date = start_date
            while current_date <= end_date:
                # Get generation for this date (kWh)
                generation_kwh = date_to_generation.get(current_date, 0.0)

                # Calculate estimated energy for this day:
                # sum( per-plant estimated for 1 day ) for plants that have generation on that date
                estimated_kwh = 0.0
                if include_today and current_date == today_date and today_window_df is not None and not today_window_df.is_empty():
                    # Today: use window/elapsed estimation
                    plant_cap_map = {}
                    for row in solar_master.iter_rows(named=True):
                        p_cd = SolarHelpers._clean_plant_code(row.get("BU Code"))
                        cap = float(row.get("Plant Capacity") or 0)
                        if p_cd:
                            plant_cap_map[p_cd] = plant_cap_map.get(p_cd, 0.0) + cap

                    aggregated_today = today_window_df.group_by(["PLANT_CD", "DayKey_IST"]).agg([
                        pl.col("actual_energy_day").sum().alias("total_actual_day"),
                        pl.col("SolarWindowHours_IST").first().alias("window_h")
                    ])

                    calc = cls._calculate_today_estimated_energy(
                        aggregated_today,
                        plant_cap_map,
                        avg_window_map
                    )
                    estimated_kwh = float(calc.get("total_estimated_energy") or 0.0)
                    # Keep generation aligned with the same data used for estimation
                    generation_kwh = float(calc.get("total_actual_energy") or generation_kwh or 0.0)
                else:
                    if generation_df is not None and not generation_df.is_empty():
                        plants_with_generation = (
                            generation_df
                            .filter(pl.col("reading_date") == current_date)
                            .get_column("PLANT_CD")
                            .unique()
                            .to_list()
                        )

                        for p in plants_with_generation:
                            p_cd = SolarHelpers._clean_plant_code(p)
                            estimated_kwh += float(estimated_1day_per_plant.get(p_cd, 0.0) or 0.0)

                # Calculate efficiency percentage
                if estimated_kwh > 0:
                    efficiency_pct = (generation_kwh / estimated_kwh) * 100.0
                else:
                    efficiency_pct = 0.0

                daily_data.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "generation": round(generation_kwh, 2),
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
    @with_solar_cache("solar_active_total_plants", 900)
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
            solar = solar.filter(pl.col('Monitoring').cast(pl.Utf8).str.strip_chars().str.to_lowercase() == 'yes')
            if "DOC" in solar.columns:
                solar = solar.filter(
                    pl.col("DOC")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.to_lowercase() != "pending"
                )
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
            sap_id_list = []
            total_plants_list = []
            plant_capacity_map = {}

            # Use unique based on BU Code to ensure distinct plants
            if bu_code_column in solar.columns:
                unique_solar = solar.unique(subset=[bu_code_column])

                for row in unique_solar.iter_rows(named=True):
                    code = row.get(bu_code_column)
                    cleaned_cd = SolarHelpers._clean_plant_code(code)
                    if cleaned_cd:
                        sap_id_list.append(cleaned_cd)

                        # Get capacity
                        capacity = row.get('Plant Capacity')
                        try:
                            capacity_val = float(capacity) if capacity is not None else 0.0
                        except (ValueError, TypeError):
                            capacity_val = 0.0

                        plant_capacity_map[cleaned_cd] = capacity_val

                        total_plants_list.append({
                            "PLANT_CD": cleaned_cd,
                            "LocationName": row.get("name") or "",
                            "Plant_Capacity": capacity_val
                        })

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
                SELECT DISTINCT
                    PLANT_CD
                FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                WHERE QuantityID = '129' 
                  AND LOWER(SourceName) NOT LIKE '%total%'
                  AND PLANT_CD IN ('{"', '".join(sap_id_list)}')
            """

            result_df = await SolarHelpers.fetch_data(cursor, query, getData=True, enrich_with_location=False)
            cursor.close()
            conn.close()

            # Process database results
            if result_df is None or result_df.is_empty():
                for plant in total_plants_list:
                    plant["status"] = "Not connected"
                return {
                    "status": "success",
                    "bu": bu_code,
                    "total_plants": total_plants,
                    "active_plants": 0,
                    "actual_active_plants": 0,
                    "active_plants_list": [],
                    "total_plants_list": total_plants_list
                }

            # Enrich and filter
            result_df = await SolarHelpers.enrich_with_location_master(
                result_df, join_column="PLANT_CD", filters=filters, drill_state=drill_state
            )
            if filters:
                result_df = SolarHelpers.apply_filters_to_dataframe(result_df, filters)
            print("result_df: ", result_df.columns)

            active_plants_df = (
                result_df
                .select([pl.col("PLANT_CD"), pl.col("name")])
                .unique()
                .drop_nulls(subset=["PLANT_CD"])
            )
            print("active_plants_df: ", active_plants_df)

            # Build active plants list with cleaned PLANT_CD
            active_plants_list = []
            for row in active_plants_df.iter_rows(named=True):
                cleaned_cd = SolarHelpers._clean_plant_code(row.get("PLANT_CD"))
                if cleaned_cd:
                    active_plants_list.append({
                        "PLANT_CD": cleaned_cd,
                        "LocationName": row.get("name") or "",
                        "Plant_Capacity": plant_capacity_map.get(cleaned_cd, 0.0),
                        "status": "Connected"
                    })

            # Calculate counts
            active_plants = len(active_plants_list)
            excel_sap_ids_set = set(sap_id_list)
            db_plant_cds_set = {plant["PLANT_CD"] for plant in active_plants_list}
            matched_plants_set = excel_sap_ids_set.intersection(db_plant_cds_set)
            actual_active_plants = len(matched_plants_set)

            # Update total_plants_list status
            inactive_plants_list = []
            for plant in total_plants_list:
                if plant["PLANT_CD"] in matched_plants_set:
                    plant["status"] = "Connected"
                else:
                    plant["status"] = "Not connected"
                    inactive_plants_list.append(plant)

            # Filter to matched plants only
            matched_plant_cds = [
                plant for plant in active_plants_list
                if plant["PLANT_CD"] in matched_plants_set
            ]

            inactive_plants_count = len(inactive_plants_list)

            return {
                "status": "success",
                "bu": bu_code,
                "total_plants": total_plants,
                "active_plants": active_plants,
                "actual_active_plants": actual_active_plants,
                "inactive_plants": inactive_plants_count,
                "active_plants_list": matched_plant_cds,
                "inactive_plants_list": inactive_plants_list,
                "total_plants_list": total_plants_list
            }

        except Exception as e:
            print(f"Error in SolarCapacity.get_active_total_plants: {e}")
            traceback.print_exc()
            return {
                "status": "error",
                "total_plants": 0,
                "active_plants": 0,
                "actual_active_plants": 0,
                "active_plants_list": [],
                "total_plants_list": [],
                "error": str(e)
            }

    @classmethod
    @with_solar_cache("solar_active_inactive_total_plants", 900)
    async def get_active_inactive_total_plants(
            cls,
            data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams
    ):
        """
        Get active, inactive, and total plants count.

        Total plants: unique sap_id count from Excel (capacity summed per plant)
        Active plants: distinct PLANT_CD from database table for a given date range
        Inactive plants: distinct PLANT_CD from database table but not for a given date range
        Not connected plants: sap_id present in Excel but not in the database
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

            # -------------------------------
            # Fetch Excel Data
            # -------------------------------
            solar = await SolarHelpers.get_solar_master_data(
                filters=filters,
                drill_state=drill_state
            )

            solar = solar.filter(
                pl.col('Monitoring')
                .cast(pl.Utf8)
                .str.strip_chars()
                .str.to_lowercase() == 'yes'
            )

            if "DOC" in solar.columns:
                solar = solar.filter(
                    pl.col("DOC")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.to_lowercase() != "pending"
                )

            if filters:
                solar = SolarHelpers.apply_filters_to_dataframe(solar, filters)

            bu_code_column = 'BU Code'

            if bu_code_column not in solar.columns:
                return {
                    "status": "error",
                    "message": "BU Code column not found in Excel file",
                    "error": f"Available columns: {list(solar.columns)}"
                }

            # -------------------------------
            # CLEAN + GROUP + SUM CAPACITY
            # -------------------------------

            # Clean plant code
            solar = solar.with_columns(
                pl.col(bu_code_column)
                .map_elements(lambda x: SolarHelpers._clean_plant_code(x))
                .alias("CLEAN_PLANT_CD")
            )

            # Ensure capacity is numeric
            if "Plant Capacity" in solar.columns:
                solar = solar.with_columns(
                    pl.col("Plant Capacity")
                    .cast(pl.Float64, strict=False)
                    .fill_null(0.0)
                )
            else:
                solar = solar.with_columns(
                    pl.lit(0.0).alias("Plant Capacity")
                )

            # Group by cleaned plant code and sum capacity
            grouped_solar = (
                solar
                .filter(pl.col("CLEAN_PLANT_CD").is_not_null())
                .group_by("CLEAN_PLANT_CD")
                .agg([
                    pl.col("Plant Capacity").sum().alias("Total_Plant_Capacity"),
                    pl.col("name").first().alias("LocationName")
                ])
            )

            excel_sap_ids = set()
            total_plants_list = []

            for row in grouped_solar.iter_rows(named=True):
                plant_cd = row.get("CLEAN_PLANT_CD")
                if plant_cd:
                    excel_sap_ids.add(plant_cd)
                    total_plants_list.append({
                        "PLANT_CD": plant_cd,
                        "LocationName": row.get("LocationName") or "",
                        "Plant_Capacity": row.get("Total_Plant_Capacity") or 0.0
                    })

            total_plants = len(excel_sap_ids)

            # -------------------------------
            # DATABASE FETCH
            # -------------------------------

            if not excel_sap_ids:
                return {
                    "status": "success",
                    "bu": bu_code,
                    "total_plants": 0,
                    "active_plants": 0,
                    "inactive_plants": 0,
                    "not_connected_plants": 0,
                    "active_plants_list": [],
                    "inactive_plants_list": [],
                    "not_connected_plants_list": [],
                    "total_plants_list": []
                }

            conn = SolarHelpers.get_db_connection(bu=bu_code)
            cursor = conn.cursor()

            plant_list_sql = "', '".join(excel_sap_ids)

            # 1️All DB Plants (Ever Connected)
            all_db_plants_query = f"""
                SELECT DISTINCT PLANT_CD
                FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                WHERE PLANT_CD IN ('{plant_list_sql}')
            """

            all_db_plants_df = await SolarHelpers.fetch_data(
                cursor,
                all_db_plants_query,
                getData=True,
                enrich_with_location=False
            )

            all_db_plant_cds = set()

            if all_db_plants_df is not None and not all_db_plants_df.is_empty():
                all_db_plant_cds = {
                    SolarHelpers._clean_plant_code(cd)
                    for cd in all_db_plants_df["PLANT_CD"].to_list()
                    if cd is not None
                }

            # Active Plants (Date Filter Applied)
            filter_start_date, filter_end_date = \
                SolarHelpers.extract_date_range_from_filters(filters)

            date_filter_sql = ""

            if filter_start_date:
                date_filter_sql += f"""
                    AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE)
                    >= '{filter_start_date}'
                """

            if filter_end_date:
                date_filter_sql += f"""
                    AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE)
                    <= '{filter_end_date}'
                """

            active_plants_query = f"""
                SELECT DISTINCT PLANT_CD
                FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                WHERE QuantityID = '129'
                AND LOWER(SourceName) NOT LIKE '%total%'
                AND PLANT_CD IN ('{plant_list_sql}')
                {date_filter_sql}
            """

            active_plants_df = await SolarHelpers.fetch_data(
                cursor,
                active_plants_query,
                getData=True,
                enrich_with_location=False
            )

            cursor.close()
            conn.close()

            active_plant_cds = set()

            if active_plants_df is not None and not active_plants_df.is_empty():
                active_plant_cds = {
                    SolarHelpers._clean_plant_code(cd)
                    for cd in active_plants_df["PLANT_CD"].to_list()
                    if cd is not None
                }

            # -------------------------------
            # Categorization
            # -------------------------------

            active_plants = []
            inactive_plants = []
            not_connected_plants = []

            for plant in total_plants_list:
                plant_cd = plant["PLANT_CD"]

                if plant_cd in active_plant_cds:
                    plant["status"] = "Active"
                    active_plants.append(plant)

                elif plant_cd in all_db_plant_cds:
                    plant["status"] = "Inactive"
                    inactive_plants.append(plant)

                else:
                    plant["status"] = "Not connected"
                    not_connected_plants.append(plant)

            return {
                "status": "success",
                "bu": bu_code,
                "total_plants": total_plants,
                "active_plants": len(active_plants),
                "inactive_plants": len(inactive_plants),
                "not_connected_plants": len(not_connected_plants),
                "active_plants_list": active_plants,
                "inactive_plants_list": inactive_plants,
                "not_connected_plants_list": not_connected_plants,
                "total_plants_list": total_plants_list
            }

        except Exception as e:
            print(f"Error in SolarCapacity.get_active_inactive_total_plants: {e}")
            traceback.print_exc()

            return {
                "status": "error",
                "error": str(e)
            }
    @classmethod
    @with_solar_cache("solar_solar_summary", 900)
    async def get_solar_summary(
            cls,
            data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams
    ):
        """
        Get solar summary including:
        bu, zone, sap_id, name, Plant capacity,
        estimated energy, actual energy, efficiency,
        status (Active / Inactive / Not connected)
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

            filter_start_date, filter_end_date = SolarHelpers.extract_date_range_from_filters(filters)
            if filter_start_date and not filter_end_date:
                filter_end_date = datetime.date.today()

            now = datetime.datetime.now()
            year = getattr(data, 'year', None) or now.year
            month = getattr(data, 'month', None) or now.month

            # ---------------------------
            # EXCEL DATA
            # ---------------------------
            solar = await SolarHelpers.get_solar_master_data(
                filters=filters,
                drill_state=drill_state
            )

            if "Monitoring" in solar.columns:
                solar = solar.filter(
                    pl.col("Monitoring")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.to_lowercase() == "yes"
                )
            if "DOC" in solar.columns:
                solar = solar.filter(
                    pl.col("DOC")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.to_lowercase() != "pending"
                )
            if filters:
                solar = SolarHelpers.apply_filters_to_dataframe(solar, filters)

            bu_code_column = 'BU Code'
            if bu_code_column not in solar.columns:
                return {"status": "error", "message": "BU Code column not found"}

            # Aggregate capacity per sap_id
            plant_capacities = {}
            plant_details = {}

            for row in solar.iter_rows(named=True):
                sap_id = SolarHelpers._clean_plant_code(row.get(bu_code_column))
                if not sap_id:
                    continue

                try:
                    capacity_val = float(row.get("Plant Capacity") or 0.0)
                except:
                    capacity_val = 0.0

                plant_capacities[sap_id] = \
                    plant_capacities.get(sap_id, 0.0) + capacity_val

                if sap_id not in plant_details:
                    plant_details[sap_id] = {
                        "bu": row.get("BU") or bu_code,
                        "zone": row.get("Zone") or row.get("zone") or "",
                        "name": row.get("name") or ""
                    }

            sap_ids = list(plant_capacities.keys())

            if not sap_ids:
                return {"status": "success", "summary": []}

            # ---------------------------
            # DATABASE CONNECTION
            # ---------------------------
            conn = SolarHelpers.get_db_connection(bu=bu_code)
            cursor = conn.cursor()

            sap_ids_sql = "', '".join(sap_ids)

            # Plants ever connected (exist in DB)
            query_connected = f"""
                SELECT DISTINCT PLANT_CD
                FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                WHERE PLANT_CD IN ('{sap_ids_sql}')
            """

            connected_df = await SolarHelpers.fetch_data(
                cursor, query_connected, getData=True, enrich_with_location=False
            )

            connected_sap_ids = set()
            if connected_df is not None and not connected_df.is_empty():
                for row in connected_df.iter_rows(named=True):
                    cd = SolarHelpers._clean_plant_code(row["PLANT_CD"])
                    if cd:
                        connected_sap_ids.add(cd)

            #  Generation in selected date range (Active)
            #  NOTE: Keep this endpoint fast: use simple estimated energy = capacity * 4 * days_count.
            date_filter_sql = ""
            if filter_start_date:
                date_filter_sql += (
                    f" AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) >= '{filter_start_date}'"
                )
            if filter_end_date:
                date_filter_sql += (
                    f" AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) <= '{filter_end_date}'"
                )

            query_energy = f"""
                {cls._get_solar_generation_base_query(sap_ids_sql, date_filter_sql)}

                SELECT
                    PLANT_CD,
                    SUM(SolarGen_kWh_entry) AS generated_solar_value
                FROM calc1
                GROUP BY PLANT_CD
            """

            result_df = await SolarHelpers.fetch_data(
                cursor, query_energy, getData=True, enrich_with_location=False
            )

            actual_map = {}
            if result_df is not None and not result_df.is_empty():
                for row in result_df.iter_rows(named=True):
                    cd = SolarHelpers._clean_plant_code(row["PLANT_CD"])
                    val = row["generated_solar_value"] or 0.0
                    if cd:
                        actual_map[cd] = val

            cursor.close()
            conn.close()

            active_sap_ids = set(actual_map.keys())

            # ---------------------------
            # DAYS CALCULATION
            # ---------------------------
            _, default_days = calendar.monthrange(int(year), int(month))
            days_count = default_days

            if filter_start_date and filter_end_date:
                days_count = (filter_end_date - filter_start_date).days + 1

            # ---------------------------
            # BUILD SUMMARY
            # ---------------------------
            summary_list = []

            for sap_id, capacity_val in plant_capacities.items():
                estimated_val = capacity_val * 4 * days_count
                actual = float(actual_map.get(sap_id, 0.0) or 0.0)

                efficiency = (actual / estimated_val) * 100 if estimated_val > 0 else 0.0

                # STATUS LOGIC
                if sap_id in active_sap_ids:
                    status = "Online"
                elif sap_id in connected_sap_ids:
                    status = "Offline"
                else:
                    status = "Not connected"

                details = plant_details.get(sap_id, {})

                summary_list.append({
                    "bu": details.get("bu"),
                    "zone": details.get("zone"),
                    "sap_id": sap_id,
                    "name": details.get("name"),
                    "Plant_Capacity": round(capacity_val, 2),
                    "estimated_energy": round(estimated_val, 2),
                    "actual_energy": round(actual, 2),
                    "efficiency": round(efficiency, 2),
                    "status": status
                })

            if getattr(data, 'is_download', False):
                df_pd = pd.DataFrame(summary_list)

                # Format column names for Excel
                df_pd = df_pd.rename(columns={
                    "bu": "BU",
                    "zone": "Zone",
                    "sap_id": "SAP ID",
                    "name": "Name",
                    "Plant_Capacity": "Plant Capacity (kW)",
                    "estimated_energy": "Estimated Energy (kWh)",
                    "actual_energy": "Actual Energy (kWh)",
                    "efficiency": "Efficiency (%)",
                    "status": "Status"
                })

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"Solar_Summary_{timestamp}.xlsx"

                output = io.BytesIO()
                # Use openpyxl as it's in requirements.txt
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_pd.to_excel(writer, index=False, sheet_name='Solar Summary')

                output.seek(0)
                headers = {
                    "Content-Disposition": f'attachment; filename="{file_name}"'
                }
                return StreamingResponse(
                    output,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers
                )

            return {
                "status": "success",
                "summary": summary_list
            }

        except Exception as e:
            print(f"Error in SolarCapacity.get_solar_summary: {e}")
            traceback.print_exc()
            return {
                "status": "error",
                "summary": [],
                "error": str(e)
            }

    @classmethod
    @with_solar_cache("solar_insights", 900)
    async def get_insights(
            cls,
            data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams
    ):
        try:
            filters = getattr(data, 'filters', None)
            drill_state = getattr(data, 'drill_state', '') or ''
            bu_code = getattr(data, 'bu', None)

            # -------------------------------------------------
            # Date range
            # -------------------------------------------------
            filter_start_date, filter_end_date = SolarHelpers.extract_date_range_from_filters(filters)
            if filter_start_date and not filter_end_date:
                filter_end_date = datetime.date.today()

            now = datetime.datetime.now()
            year = getattr(data, 'year', None) or now.year
            month = getattr(data, 'month', None) or now.month

            # -------------------------------------------------
            # Solar master
            # -------------------------------------------------
            solar_master = await SolarHelpers.get_solar_master_data(
                filters=filters,
                drill_state=drill_state
            )

            if isinstance(solar_master, dict):
                return {
                    "status": "error",
                    "message": solar_master.get("message", "Error fetching solar master"),
                    "error": solar_master.get("error", "Unknown error")
                }

            if filters:
                solar_master = SolarHelpers.apply_filters_to_dataframe(solar_master, filters)

            if "Monitoring" in solar_master.columns:
                solar_master = solar_master.filter(
                    pl.col("Monitoring")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.to_lowercase() == "yes"
                )

            if "DOC" in solar_master.columns:
                solar_master = solar_master.filter(
                    pl.col("DOC")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.to_lowercase() != "pending"
                )

            if "Plant Capacity" in solar_master.columns:
                solar_master = solar_master.filter(pl.col("Plant Capacity").is_not_null())

            if solar_master.is_empty():
                return {"status": "success", "data": []}

            # -------------------------------------------------
            # BU codes
            # -------------------------------------------------
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
                return {"status": "success", "data": []}

            bu_codes_sql = "', '".join(bu_codes)

            # -------------------------------------------------
            # Date filter SQL
            # -------------------------------------------------
            date_filter_sql = ""
            # if filter_start_date:
            #     date_filter_sql += f" AND TimestampUTC >= '{filter_start_date}'"
            # if filter_end_date:
            #     next_day = filter_end_date + datetime.timedelta(days=1)
            #     date_filter_sql += f" AND TimestampUTC < '{next_day}'"
            if filter_start_date:
                date_filter_sql += (
                    " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                    f">= '{filter_start_date}'"
                )

            if filter_end_date:
                date_filter_sql += (
                    " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                    f"<= '{filter_end_date}'"
                )

            # -------------------------------------------------
            # query
            # -------------------------------------------------
            query = f"""
            {cls._get_solar_insights_base_query(bu_codes_sql, date_filter_sql)}

            , calc AS (
                    SELECT
                        *,

                        CASE
                            WHEN ISNULL(Grid_Freq_Hz, 0) <= 0.01 THEN 1 ELSE 0
                        END AS PowerOutageFlag,

                        CASE
                            WHEN SolarKW_Available_Flag = 1 AND Solar_kW > 0.6 THEN 1
                            WHEN SolarKW_Available_Flag = 0 AND ISNULL(SolarGen_kWh_entry, 0) > 0 THEN 1
                            ELSE 0
                        END AS SolarWindowFlag,

                        CASE
                            WHEN ISNULL(Grid_Freq_Hz, 0) > 0.01
                             AND CAST(TimestampIST AS TIME) >= '05:00:00'
                             AND (
                                    (SolarKW_Available_Flag = 1 AND Solar_kW > 0.6)
                                 OR (SolarKW_Available_Flag = 0 AND ISNULL(SolarGen_kWh_entry, 0) > 0)
                                 )
                            THEN 1 ELSE 0
                        END AS SolarGeneratingFlag,

                        CASE
                            WHEN ISNULL(Grid_Freq_Hz, 0) > 0.01
                             AND (
                                    (SolarKW_Available_Flag = 1 AND Solar_kW <= 0.6)
                                 OR (SolarKW_Available_Flag = 0 AND ISNULL(SolarGen_kWh_entry, 0) = 0)
                                 )
                            THEN 1 ELSE 0
                        END AS SolarZeroWhileGridOnFlag,

                        CASE
                            WHEN SolarKW_Available_Flag = 1
                                 AND Solar_kW >= 0.5
                            THEN 1

                            WHEN SolarKW_Available_Flag = 0
                                 AND ISNULL(SolarGen_kWh_entry, 0) > 0.5                          
                                 AND LAG(ISNULL(SolarGen_kWh_entry, 0))
                                     OVER (PARTITION BY PLANT_CD, SourceID ORDER BY TimestampUTC) = 0
                            THEN 1

                            ELSE 0
                        END AS SolarStartFlag,

                        CASE
                            WHEN SolarKW_Available_Flag = 1
                                 AND ISNULL(Prev_Solar_kW, 0) > 0.25
                                 AND ISNULL(Solar_kW, 0) <= 0.5

                            THEN 1

                            WHEN SolarKW_Available_Flag = 0
                                 AND ISNULL(SolarGen_kWh_entry, 0) < 0.25

                                 AND LAG(ISNULL(SolarGen_kWh_entry, 0))
                                     OVER (PARTITION BY PLANT_CD, SourceID ORDER BY TimestampUTC) > 0
                            THEN 1

                            ELSE 0
                        END AS SolarEndFlag
                    FROM calc1
                ),

                calc_window AS (
                    SELECT
                        *,
                        MIN(CASE WHEN SolarStartFlag = 1 THEN TimestampUTC END)
                            OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarStart_UTC,

                        MIN(CASE 
                                WHEN SolarStartFlag = 1 
                                 AND CAST(TimestampIST AS TIME) >= '05:30:00'
                                THEN TimestampIST 
                            END)
                        OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarStart_IST,

                        MAX(CASE WHEN SolarEndFlag = 1 THEN TimestampUTC END)
                            OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarEnd_UTC,

                        MAX(CASE 
                                WHEN SolarGeneratingFlag = 1
                                 AND CAST(TimestampIST AS TIME) >= '05:30:00'
                                THEN TimestampIST 
                            END)
                        OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarEnd_IST
                    FROM calc
                )

                SELECT
                    PLANT_CD,
                    SourceID,
                    TimestampUTC,
                    TimestampIST,
                    LocationName,
                    Energy_Cumulative_kWh,
                    Solar_kW,
                    Grid_Freq_Hz,
                    SolarGen_kWh_entry,
                    PowerOutageFlag,
                    (IntervalHours *
                    CASE 
                            WHEN SolarGeneratingFlag = 1 
                             AND CAST(TimestampIST AS TIME) >= '05:00:00'
                            THEN 1 ELSE 0
                        END
                    ) AS SolarGenHours_entry,
                    CASE
                        WHEN TimestampUTC >= SolarStart_UTC AND TimestampUTC <= SolarEnd_UTC
                        THEN (IntervalHours * PowerOutageFlag)
                        ELSE 0
                    END AS OutageDuringSolarHours_entry,
                    SUM(ISNULL(SolarGen_kWh_entry, 0))
                        OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarGen_kWh_day,
                    SUM(IntervalHours * SolarGeneratingFlag)
                        OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarGenHours_day,
                    SUM(CASE
                        WHEN TimestampUTC >= SolarStart_UTC AND TimestampUTC <= SolarEnd_UTC
                        THEN (IntervalHours * PowerOutageFlag)
                        ELSE 0
                    END) OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS OutageDuringSolarHours_day,
                    SolarStart_UTC,
                    SolarStart_IST,
                    SolarEnd_UTC,
                    SolarEnd_IST,
                    CASE 
                        WHEN SolarStart_IST IS NOT NULL 
                         AND SolarEnd_IST IS NOT NULL
                        THEN (DATEDIFF(
                                SECOND,
                                SolarStart_IST,
                                SolarEnd_IST
                              ) / 3600.0) + 0.75
                        ELSE NULL
                    END AS SolarWindowHours_IST
                FROM calc_window
                ORDER BY SourceID, TimestampUTC;

            """

            conn = SolarHelpers.get_db_connection(bu=bu_code)
            cursor = conn.cursor()
            result_df = await SolarHelpers.fetch_data(cursor, query, getData=True, enrich_with_location=False)
            cursor.close()
            conn.close()

            if result_df.is_empty():
                return {"status": "success", "data": []}

            # -------------------------------------------------
            # Days count
            # -------------------------------------------------
            _, default_days = calendar.monthrange(int(year), int(month))
            days_count = default_days
            if filter_start_date and filter_end_date:
                days_count = (filter_end_date - filter_start_date).days + 1

            # -------------------------------------------------
            # Final calculations (FLOAT SAFE)
            # -------------------------------------------------
            insights = []

            for plant_cd in result_df.select(pl.col("PLANT_CD").unique()).to_series().to_list():
                plant_df = result_df.filter(pl.col("PLANT_CD") == plant_cd)

                location_name = (
                        plant_df
                        .select(pl.col("LocationName").first())
                        .item() or ""
                )

                # solar_window_hours_list = (
                #     plant_df
                #     .select(pl.col("SolarWindowHours_IST").cast(pl.Float64).unique())
                #     .to_series()
                #     .drop_nulls()
                #     .to_list()
                # )

                power_outage_hours_list = (
                    plant_df
                    .filter(pl.col("OutageDuringSolarHours_day") > 0)  # keep only > 0
                    .select(pl.col("OutageDuringSolarHours_day").cast(pl.Float64))
                    .to_series()
                    .drop_nulls()
                    .to_list()
                )

                actual_energy = float(plant_df.select(pl.col("SolarGen_kWh_entry").sum()).item() or 0)

                generation_hours = float(plant_df.select(pl.col("SolarGenHours_entry").sum()).item() or 0)
                # power_outage_hours = float(plant_df.select(pl.col("OutageDuringSolarHours_day").sum()).item() or 0)
                power_outage_hours = float(plant_df.select(pl.col("OutageDuringSolarHours_entry").sum()).item() or 0)
                plant_capacity = float(
                    solar_master
                    .filter(pl.col("BU Code").cast(pl.Utf8).str.strip_chars() == str(plant_cd))
                    .select(pl.col("Plant Capacity").cast(pl.Float64).fill_null(0).sum())
                    .item() or 0
                )

                estimated_energy = plant_capacity * 4 * days_count
                # solar_window_hours = solar_window_hours_list[0] if solar_window_hours_list else 0
                solar_window_hours = (
                        plant_df
                        .select([
                            pl.col("SolarStart_IST"),
                            pl.col("SolarWindowHours_IST").cast(pl.Float64)
                        ])
                        .drop_nulls(subset=["SolarStart_IST"])
                        .unique(subset=["SolarStart_IST"])
                        .select(pl.col("SolarWindowHours_IST").sum())
                        .item() or 0
                )
                export_available_hour = abs(solar_window_hours - power_outage_hours)

                if solar_window_hours is not None and solar_window_hours > 0:
                    grid_availability_percentage = ((
                                                                solar_window_hours - power_outage_hours) / solar_window_hours) * 100
                    loss_of_power_outage = estimated_energy * (power_outage_hours / solar_window_hours)
                    adjusted_expected = estimated_energy * (
                            export_available_hour / solar_window_hours
                    )
                else:
                    grid_availability_percentage = 0
                    loss_of_power_outage = 0
                    adjusted_expected = 0

                loss_of_power_outage_percentage = (
                    (loss_of_power_outage / estimated_energy) * 100
                    if estimated_energy else 0
                )

                dust_loss = max(0, adjusted_expected - actual_energy)
                dust_loss_percentage = (
                    (dust_loss / adjusted_expected) * 100
                    if adjusted_expected else 0
                )

                efficiency_percentage = (
                    (actual_energy / adjusted_expected) * 100
                    if adjusted_expected else 0
                )

                solar_window_hours_mean = (
                        plant_df
                        .select([
                            pl.col("SolarStart_IST"),
                            pl.col("SolarWindowHours_IST").cast(pl.Float64)
                        ])
                        .drop_nulls(subset=["SolarStart_IST"])
                        .unique(subset=["SolarStart_IST"])
                        .select(pl.col("SolarWindowHours_IST").mean())
                        .item() or 0
                )
                SolarGenHours_day_mean = (
                        plant_df
                        .select(pl.col("SolarGenHours_day").mean())
                        .item() or 0
                )
                OutageDuringSolarHours_day_mean = (
                        plant_df
                        .select(pl.col("OutageDuringSolarHours_day").mean())
                        .item() or 0
                )
                export_available_hour_mean = abs(solar_window_hours_mean - OutageDuringSolarHours_day_mean)

                insights.append({
                    "sap_id": str(plant_cd),
                    "LocationName": location_name,
                    "actual_energy": round(actual_energy, 2),
                    "estimated_energy": round(estimated_energy, 2),
                    "energy_generation_hours": round(SolarGenHours_day_mean, 2),
                    "solar_window_hours": round(solar_window_hours_mean,2),
                    "export_available_hour": round(export_available_hour_mean,2),
                    "power_outage": round(OutageDuringSolarHours_day_mean, 2),
                    "adjusted_expected": round(adjusted_expected, 2),
                    "loss_of_power_outage": round(loss_of_power_outage, 2),
                    "loss_of_power_outage_percentage": round(loss_of_power_outage_percentage, 2),
                    "efficiency_estimated_actual_percentage": round(efficiency_percentage, 2),
                    "loss_dust_soil_percentage": round(dust_loss_percentage, 2),
                    "total_loss": round(dust_loss_percentage + loss_of_power_outage_percentage, 2),
                    "grid_availability_percentage": round(grid_availability_percentage, 2)
                })

            if getattr(data, 'is_download', False):
                df_pd = pd.DataFrame(insights)

                # Format column names for Excel
                df_pd = df_pd.rename(columns={
                    "sap_id": "SAP ID",
                    "LocationName": "Location Name",
                    "actual_energy": "Actual Energy (kWh)",
                    "estimated_energy": "Estimated Energy (kWh)",
                    "energy_generation_hours": "Energy Generation Hours",
                    "solar_window_hours": "Solar Window Hours",
                    "export_available_hour": "Export Available Hour",
                    "power_outage": "Power Outage (Hours)",
                    "adjusted_expected": "Adjusted Expected (kWh)",
                    "loss_of_power_outage": "Loss of Power Outage (kWh)",
                    "loss_of_power_outage_percentage": "Loss of Power Outage (%)",
                    "efficiency_estimated_actual_percentage": "Efficiency (%)",
                    "loss_dust_soil_percentage": "Loss Dust/Soil (%)",
                    "total_loss": "Total Loss (%)",
                    "grid_availability_percentage": "Grid Availability (%)"
                })

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"Solar_Insights_{timestamp}.xlsx"

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_pd.to_excel(writer, index=False, sheet_name='Solar Insights')

                output.seek(0)
                headers = {
                    "Content-Disposition": f'attachment; filename="{file_name}"'
                }
                return StreamingResponse(
                    output,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers
                )
            return {
                "status": "success",
                "data": insights
            }

        except Exception as e:
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e)
            }

    @classmethod
    @with_solar_cache("solar_overall_insights", 900)
    async def get_overall_insights(cls, data: dashboard_studio_model.Solarpanelcleaning_Get_Solar_Dashboard_SummaryParams):
        try:
            filters = getattr(data, 'filters', None)
            drill_state = getattr(data, 'drill_state', '') or ''
            bu_code = getattr(data, 'bu', None)

            # -------------------------------------------------
            # Date range
            # -------------------------------------------------
            filter_start_date, filter_end_date = SolarHelpers.extract_date_range_from_filters(filters)
            if filter_start_date and not filter_end_date:
                filter_end_date = datetime.date.today()

            now = datetime.datetime.now()
            year = getattr(data, 'year', None) or now.year
            month = getattr(data, 'month', None) or now.month

            # -------------------------------------------------
            # Solar master
            # -------------------------------------------------
            solar_master = await SolarHelpers.get_solar_master_data(
                filters=filters,
                drill_state=drill_state
            )

            if isinstance(solar_master, dict):
                return {
                    "status": "error",
                    "message": solar_master.get("message", "Error fetching solar master"),
                    "error": solar_master.get("error", "Unknown error")
                }

            if filters:
                solar_master = SolarHelpers.apply_filters_to_dataframe(solar_master, filters)

            if "Monitoring" in solar_master.columns:
                solar_master = solar_master.filter(
                    pl.col("Monitoring")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.to_lowercase() == "yes"
                )

            if "DOC" in solar_master.columns:
                solar_master = solar_master.filter(
                    pl.col("DOC")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.to_lowercase() != "pending"
                )

            if "Plant Capacity" in solar_master.columns:
                solar_master = solar_master.filter(pl.col("Plant Capacity").is_not_null())

            if solar_master.is_empty():
                return {"status": "success", "data": []}

            # -------------------------------------------------
            # BU codes
            # -------------------------------------------------
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
                return {"status": "success", "data": []}

            bu_codes_sql = "', '".join(bu_codes)

            # -------------------------------------------------
            # Date filter SQL
            # -------------------------------------------------
            date_filter_sql = ""
            if filter_start_date:
                date_filter_sql += (
                    " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                    f">= '{filter_start_date}'"
                )

            if filter_end_date:
                date_filter_sql += (
                    " AND CAST(DATEADD(MINUTE, 330, TimestampUTC) AS DATE) "
                    f"<= '{filter_end_date}'"
                )

            # -------------------------------------------------
            # query
            # -------------------------------------------------
            query = f"""
                        WITH base AS (
                    SELECT
                        PLANT_CD,
                        SourceID,
                        TimestampUTC,

                        -- combine cumulative energy PER SOURCE
                        SUM(CASE WHEN QuantityID = 129 THEN Value END) AS Energy_Cumulative_kWh,
                        -- MAX(CASE WHEN QuantityID = 544 THEN Value END) AS Solar_kW,
                        COALESCE(
                            MAX(CASE WHEN QuantityID = 544 THEN NULLIF(Value,0) END),
                            MAX(CASE WHEN QuantityID = 518 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 519 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 520 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 515 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 516 THEN NULLIF(ABS(Value),0) END),
                            MAX(CASE WHEN QuantityID = 517 THEN NULLIF(ABS(Value),0) END)
                        ) AS Solar_kW,

                        MAX(CASE WHEN QuantityID = 540 THEN Value END) AS Grid_Freq_Hz,
                        MAX(LocationName) AS LocationName

                    FROM ION_Data.dbo.vw_PMEAnalyticsConsolidated_SOLAR
                    WHERE   PLANT_CD IN ('{bu_codes_sql}')
                        AND LOWER(SourceName) NOT LIKE '%total%'
                        AND QuantityID IN (129,540,544,518,519,520,515,516,517)
                         {date_filter_sql}
                        AND DATEPART(SECOND, DATEADD(MINUTE, 330, TimestampUTC)) = 0
                        AND DATEPART(MINUTE, DATEADD(MINUTE, 330, TimestampUTC)) % 15 = 0
                    GROUP BY
                        PLANT_CD,
                        SourceID,
                        TimestampUTC
                ),

                w AS (
                    SELECT
                        b.*,
                        DATEADD(MINUTE, 330, b.TimestampUTC) AS TimestampIST,
                        CAST(DATEADD(MINUTE, 330, b.TimestampUTC) AS DATE) AS DayKey_IST,
                        CAST(DATEADD(MINUTE,330,b.TimestampUTC) AS TIME) AS TimeIST,

                        LAG(b.Energy_Cumulative_kWh)
                            OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                            AS Prev_Energy_Cumulative_kWh,

                        LAG(b.Solar_kW)
                            OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                            AS Prev_Solar_kW,

                        LEAD(b.TimestampUTC)
                            OVER (PARTITION BY b.PLANT_CD, b.SourceID ORDER BY b.TimestampUTC)
                            AS NextTimestampUTC
                    FROM base b
                ),

                calc1 AS (
                    SELECT
                        *,

                        CASE
                            -- IGNORE energy during power outage
                            WHEN ISNULL(Grid_Freq_Hz, 0) <= 0.01 THEN 0

                            WHEN Energy_Cumulative_kWh IS NULL THEN 0
                            WHEN Prev_Energy_Cumulative_kWh IS NULL THEN 0
                            WHEN Energy_Cumulative_kWh < Prev_Energy_Cumulative_kWh THEN 0
                            WHEN (Energy_Cumulative_kWh - Prev_Energy_Cumulative_kWh) > 100 THEN 0

                            ELSE Energy_Cumulative_kWh - Prev_Energy_Cumulative_kWh
                        END AS SolarGen_kWh_entry,

                        CASE
                            WHEN NextTimestampUTC IS NULL THEN 0.0
                            ELSE DATEDIFF(SECOND, TimestampUTC, NextTimestampUTC) / 3600.0
                        END AS IntervalHours,

                        CASE
                            WHEN COUNT(Solar_kW)
                                 OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) > 0
                            THEN 1 ELSE 0
                        END AS SolarKW_Available_Flag
                    FROM w
                )
        

            , calc AS (
                    SELECT
                        *,

                        CASE
                            WHEN ISNULL(Grid_Freq_Hz, 0) <= 0.01 THEN 1 ELSE 0
                        END AS PowerOutageFlag,

                        CASE
                            WHEN SolarKW_Available_Flag = 1 AND Solar_kW > 0.6 THEN 1
                            WHEN SolarKW_Available_Flag = 0 AND ISNULL(SolarGen_kWh_entry, 0) > 0 THEN 1
                            ELSE 0
                        END AS SolarWindowFlag,

                        CASE
                            WHEN ISNULL(Grid_Freq_Hz, 0) > 0.01
                             AND CAST(TimestampIST AS TIME) >= '05:00:00'
                             AND (
                                    (SolarKW_Available_Flag = 1 AND Solar_kW > 0.6)
                                 OR (SolarKW_Available_Flag = 0 AND ISNULL(SolarGen_kWh_entry, 0) > 0)
                                 )
                            THEN 1 ELSE 0
                        END AS SolarGeneratingFlag,

                        CASE
                            WHEN ISNULL(Grid_Freq_Hz, 0) > 0.01
                             AND (
                                    (SolarKW_Available_Flag = 1 AND Solar_kW <= 0.6)
                                 OR (SolarKW_Available_Flag = 0 AND ISNULL(SolarGen_kWh_entry, 0) = 0)
                                 )
                            THEN 1 ELSE 0
                        END AS SolarZeroWhileGridOnFlag,

                        CASE
                            WHEN SolarKW_Available_Flag = 1
                                 AND Solar_kW >= 0.5
                            THEN 1

                            WHEN SolarKW_Available_Flag = 0
                                 AND ISNULL(SolarGen_kWh_entry, 0) > 0.5                          
                                 AND LAG(ISNULL(SolarGen_kWh_entry, 0))
                                     OVER (PARTITION BY PLANT_CD, SourceID ORDER BY TimestampUTC) = 0
                            THEN 1

                            ELSE 0
                        END AS SolarStartFlag,

                        CASE
                            WHEN SolarKW_Available_Flag = 1
                                 AND ISNULL(Prev_Solar_kW, 0) > 0.25
                                 AND ISNULL(Solar_kW, 0) <= 0.5

                            THEN 1

                            WHEN SolarKW_Available_Flag = 0
                                 AND ISNULL(SolarGen_kWh_entry, 0) < 0.25

                                 AND LAG(ISNULL(SolarGen_kWh_entry, 0))
                                     OVER (PARTITION BY PLANT_CD, SourceID ORDER BY TimestampUTC) > 0
                            THEN 1

                            ELSE 0
                        END AS SolarEndFlag
                    FROM calc1
                ),

                calc_window AS (
                    SELECT
                        *,
                        MIN(CASE WHEN SolarStartFlag = 1 THEN TimestampUTC END)
                            OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarStart_UTC,

                        MIN(CASE 
                                WHEN SolarStartFlag = 1 
                                 AND CAST(TimestampIST AS TIME) >= '05:30:00'
                                THEN TimestampIST 
                            END)
                        OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarStart_IST,

                        MAX(CASE WHEN SolarEndFlag = 1 THEN TimestampUTC END)
                            OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarEnd_UTC,

                        MAX(CASE 
                                WHEN SolarGeneratingFlag = 1
                                 AND CAST(TimestampIST AS TIME) >= '05:30:00'
                                THEN TimestampIST 
                            END)
                        OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarEnd_IST
                    FROM calc
                )

                SELECT
                    PLANT_CD,
                    SourceID,
                    TimestampUTC,
                    TimestampIST,
                    LocationName,
                    Energy_Cumulative_kWh,
                    Solar_kW,
                    Grid_Freq_Hz,
                    SolarGen_kWh_entry,
                    PowerOutageFlag,
                    (IntervalHours *
                    CASE 
                        WHEN SolarGeneratingFlag = 1 
                         AND CAST(TimestampIST AS TIME) >= '05:00:00'
                        THEN 1 ELSE 0
                    END
                ) AS SolarGenHours_entry,
                    CASE
                        WHEN TimestampUTC >= SolarStart_UTC AND TimestampUTC <= SolarEnd_UTC
                        THEN (IntervalHours * PowerOutageFlag)
                        ELSE 0
                    END AS OutageDuringSolarHours_entry,
                    SUM(ISNULL(SolarGen_kWh_entry, 0))
                        OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarGen_kWh_day,
                    SUM(IntervalHours * SolarGeneratingFlag)
                        OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS SolarGenHours_day,
                    SUM(CASE
                        WHEN TimestampUTC >= SolarStart_UTC AND TimestampUTC <= SolarEnd_UTC
                        THEN (IntervalHours * PowerOutageFlag)
                        ELSE 0
                    END) OVER (PARTITION BY PLANT_CD, SourceID, DayKey_IST) AS OutageDuringSolarHours_day,
                    SolarStart_UTC,
                    SolarStart_IST,
                    SolarEnd_UTC,
                    SolarEnd_IST,
                    CASE 
                        WHEN SolarStart_IST IS NOT NULL 
                         AND SolarEnd_IST IS NOT NULL
                        THEN (DATEDIFF(
                                SECOND,
                                SolarStart_IST,
                                SolarEnd_IST
                              ) / 3600.0) + 0.75
                        ELSE NULL
                    END AS SolarWindowHours_IST
                FROM calc_window
                ORDER BY SourceID, TimestampUTC;

                        """
            print("Insight Query: ", query)

            conn = SolarHelpers.get_db_connection(bu=bu_code)
            cursor = conn.cursor()
            result_df = await SolarHelpers.fetch_data(cursor, query, getData=True, enrich_with_location=False)
            cursor.close()
            conn.close()

            if result_df.is_empty():
                return {"status": "success", "data": []}

            # -------------------------------------------------
            # Days count
            # -------------------------------------------------
            _, default_days = calendar.monthrange(int(year), int(month))
            days_count = default_days
            if filter_start_date and filter_end_date:
                days_count = (filter_end_date - filter_start_date).days + 1

            # -------------------------------------------------
            # Final calculations (FLOAT SAFE)
            # -------------------------------------------------

            plant_df = result_df

            power_outage_hours_list = (
                plant_df
                .filter(pl.col("OutageDuringSolarHours_day") > 0)  # keep only > 0
                .select(pl.col("OutageDuringSolarHours_day").cast(pl.Float64))
                .to_series()
                .drop_nulls()
                .to_list()
            )

            actual_energy = float(plant_df.select(pl.col("SolarGen_kWh_entry").sum()).item() or 0)

            generation_hours = float(plant_df.select(pl.col("SolarGenHours_entry").sum()).item() or 0)
            # power_outage_hours = float(plant_df.select(pl.col("OutageDuringSolarHours_day").sum()).item() or 0)
            power_outage_hours = float(plant_df.select(pl.col("OutageDuringSolarHours_entry").sum()).item() or 0)
            # Identify matched SAP IDs (those present in the DB results)
            matched_sap_ids = set()
            if result_df is not None and not result_df.is_empty():
                try:
                    # distinct PLANT_CD from result_df
                    unique_plants = result_df.select(pl.col("PLANT_CD")).unique().to_series().to_list()
                    for p_cd in unique_plants:
                        if p_cd:
                            matched_sap_ids.add(str(p_cd).strip())
                except Exception as e:
                    print(f"Error extracting matched SAP IDs: {e}")

            # Calculate estimated energy ONLY for matched plants
            if matched_sap_ids:
                estimated_energy = (
                    solar_master
                    .filter(pl.col("BU Code").cast(pl.Utf8).str.strip_chars().is_in(matched_sap_ids))
                    .select(
                        (pl.col('Plant Capacity')
                        .cast(pl.Float64, strict=False)
                        .fill_null(0)
                        * 4
                        * days_count).sum()
                    )
                    .item()
                ) or 0.0
            else:
                estimated_energy = 0.0
            # solar_window_hours = solar_window_hours_list[0] if solar_window_hours_list else 0
            solar_window_hours = (
                    plant_df
                    .select([
                        pl.col("SolarStart_IST"),
                        pl.col("SolarWindowHours_IST").cast(pl.Float64)
                    ])
                    .drop_nulls(subset=["SolarStart_IST"])
                    .unique(subset=["SolarStart_IST"])
                    .select(pl.col("SolarWindowHours_IST").sum())
                    .item() or 0
            )
            export_available_hour = abs(solar_window_hours - power_outage_hours)

            if solar_window_hours is not None and solar_window_hours > 0:
                grid_availability_percentage = ((solar_window_hours - power_outage_hours) / solar_window_hours) * 100
                loss_of_power_outage = estimated_energy * (power_outage_hours / solar_window_hours)
                adjusted_expected = estimated_energy * (
                        export_available_hour / solar_window_hours
                )
            else:
                grid_availability_percentage = 0
                loss_of_power_outage = 0
                adjusted_expected = 0

            loss_of_power_outage_percentage = (
                (loss_of_power_outage / estimated_energy) * 100
                if estimated_energy else 0
            )

            # dust_loss = max(0, adjusted_expected - actual_energy)
            dust_loss = abs(adjusted_expected - actual_energy)
            dust_loss_percentage = (
                (dust_loss / adjusted_expected) * 100
                if adjusted_expected else 0
            )

            efficiency_percentage = (
                (actual_energy / adjusted_expected) * 100
                if adjusted_expected else 0
            )
            solar_window_hours_mean = (
                    plant_df
                    .select([
                        pl.col("SolarStart_IST"),
                        pl.col("SolarWindowHours_IST").cast(pl.Float64)
                    ])
                    .drop_nulls(subset=["SolarStart_IST"])
                    .unique(subset=["SolarStart_IST"])
                    .select(pl.col("SolarWindowHours_IST").mean())
                    .item() or 0
            )

            SolarGenHours_day_mean = (
                    plant_df
                    .select(pl.col("SolarGenHours_day").mean())
                    .item() or 0
            )

            OutageDuringSolarHours_day_mean = (
                    plant_df
                    .select(pl.col("OutageDuringSolarHours_day").mean())
                    .item() or 0
            )

            export_available_hour_mean = abs(solar_window_hours_mean - OutageDuringSolarHours_day_mean)

            insights = {
                "actual_energy": round(actual_energy, 2),
                "estimated_energy": round(estimated_energy, 2),
                "energy_generation_hours": round(SolarGenHours_day_mean, 2),
                "solar_window_hours": round(solar_window_hours_mean,2),
                "export_available_hour": round(export_available_hour_mean,2),
                "power_outage": round(OutageDuringSolarHours_day_mean, 2),
                "adjusted_expected": round(adjusted_expected, 2),
                "loss_of_power_outage": round(loss_of_power_outage, 2),
                "loss_of_power_outage_percentage": round(loss_of_power_outage_percentage, 2),
                "efficiency_estimated_actual_percentage": round(efficiency_percentage, 2),
                "loss_dust_soil_percentage": round(dust_loss_percentage, 2),
                "total_loss": round(dust_loss_percentage + loss_of_power_outage_percentage, 2),
                "grid_availability_percentage": round(grid_availability_percentage, 2)
            }

            return {
                "status": "success",
                "data": insights
            }

        except Exception as e:
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e)
            }
