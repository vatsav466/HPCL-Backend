import urdhva_base
import polars as pl
from datetime import datetime
from decimal import Decimal
from hpcl_ceg_model import PerformanceScoreHistory


# Utility: normalize numerics for Polars
def sanitize_records(records):

    clean_records = []

    for idx, row in enumerate(records):
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, Decimal):
                clean_row[k] = float(v)
            elif k == "score" and isinstance(v, int):
                clean_row[k] = float(v)
            else:
                clean_row[k] = v
        clean_records.append(clean_row)

    return clean_records


async def performance_score_daywise_action(data):

    
    # Fetch data (BU is dynamic)
    bu = data.bu  

    params = urdhva_base.queryparams.QueryParams(
        q=f"bu = '{bu}'",
        limit=0
    )

    resp = await PerformanceScoreHistory.get_all(
        params,
        resp_type="plain"
    )

    records = resp.get("data", [])

    if not records:
        return {"status": "success", "zones": []}


    # Sanitize numerics

    records = sanitize_records(records)

    df = pl.DataFrame(records, strict=False)

    # Prepare score_date column
    df = df.with_columns(
        pl.col("created_at")
        .cast(pl.Datetime)
        .dt.date()
        .alias("score_date")
    )

    # Read filters
    name_filter = data.name or None
    zone_filter = data.zone or None
    start_date = data.start_date or None
    end_date = data.end_date or None

    # Apply date filters
    if start_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        df = df.filter(pl.col("score_date") >= start_date)

    if end_date:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        df = df.filter(pl.col("score_date") <= end_date)

    # Apply name / zone filters
    if name_filter:
        df = df.filter(pl.col("name") == name_filter)

    if zone_filter:
        df = df.filter(pl.col("zone") == zone_filter)

    if df.is_empty():
        return {"status": "success", "zones": []}

    # Ensure score is Float64
    df = df.with_columns(
        pl.col("score").cast(pl.Float64)
    )

    # Day-wise aggregation
    df = (
        df
        .group_by(["zone", "name", "score_date"])
        .agg(
            pl.col("score").mean().round(2).alias("score")
        )
        .sort(["zone", "name", "score_date"])
    )

    # Build response
    zones = []

    for zone in df.select("zone").unique().to_series():

        zone_df = df.filter(pl.col("zone") == zone)
        plants = []

        for name in zone_df.select("name").unique().to_series():

            plant_df = zone_df.filter(pl.col("name") == name)

            daywise_scores = [
                {
                    "date": str(row["score_date"]),
                    "score": float(row["score"])
                }
                for row in plant_df.to_dicts()
            ]

            plants.append({
                "name": name,
                "daywise_scores": daywise_scores
            })

        zones.append({
            "zone": zone,
            "plants": plants
        })

    return {
        "status": "success",
        "zones": zones
    }

