import urdhva_base
import polars as pl
from datetime import datetime
from decimal import Decimal
from hpcl_ceg_model import PerformanceScoreHistory


# TAS CATEGORY SET (ONLY for grouping)
TAS_CATEGORIES = {
    "Safety_Interlocks",
    "Gantry_Interlocks",
    "Process_Interlocks",
    "Water_Quantity",
    "Foam_Quantity",
    "Fire_Engines_In_Auto_Mode",
    "Hydrant_Line",
}


# Utility: sanitize numerics (Decimal → float)
def sanitize_records(records):
    return [
        {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}
        for row in records
    ]


# TAS resolver 
def resolve_tas_with_categories(categories):

    tas_categories = [c for c in categories if c["name"] in TAS_CATEGORIES]

    total_score = sum(c.get("score", 0) for c in tas_categories)

    return {
        "name": "TAS",
        "score": round(total_score, 2),
        "categories": [
            {
                "name": c.get("name"),
                "score": c.get("score"),
                "weightage": c.get("weightage"),
                "module": c.get("name"),
                "categories": [
                    {
                        "name": r.get("name"),
                        "score": r.get("score"),
                        "weightage": r.get("weightage"),
                        "module": r.get("module")
                    }
                    for r in c.get("results", [])
                ] if c.get("results") else []
            }
            for c in tas_categories
        ]
    }


# Generic resolver (PQ / VA / VTS / ANY category)
def resolve_category_score(categories, score_type):
    cat = next((c for c in categories if c["name"] == score_type), None)
    if not cat:
        return {"name": score_type, "score": 0.0}

    response = {
        "name": score_type,
        "score": cat.get("score", 0)
    }

    if cat.get("results"):
        response["categories"] = [
            {
                "name": r.get("name"),
                "score": r.get("score"),
                "weightage": r.get("weightage"),
                "module": r.get("module")
            }
            for r in cat["results"]
        ]

    return response

# MAIN API
async def performance_score_daywise_action(data):
    
    # Fetch data
    params = urdhva_base.queryparams.QueryParams(
        q=f"bu = '{data.bu}'",
        limit=0
    )

    resp = await PerformanceScoreHistory.get_all(
        params,
        resp_type="plain"
    )

    records = sanitize_records(resp.get("data", []))
    if not records:
        return {"status": "success", "zones": []}

    
    # Build DataFrame
    df = (
        pl.DataFrame(records, strict=False)
        .with_columns(
            pl.col("created_at")
            .cast(pl.Datetime)
            .dt.date()
            .alias("score_date")
        )
    )

    # Apply filters
    if data.start_date:
        df = df.filter(
            pl.col("score_date")
            >= datetime.strptime(data.start_date, "%Y-%m-%d").date()
        )

    if data.end_date:
        df = df.filter(
            pl.col("score_date")
            <= datetime.strptime(data.end_date, "%Y-%m-%d").date()
        )

    if data.zone:
        df = df.filter(pl.col("zone") == data.zone)

    if data.name:
        df = df.filter(pl.col("name") == data.name)

    if df.is_empty():
        return {"status": "success", "zones": []}

    
    # Grouping: latest record per day
    grouped = (
        df
        .sort("created_at")
        .group_by(["zone", "name", "score_date"])
        .agg(
            pl.col("score").mean().round(2).alias("avg_score"),
            pl.col("category").last(),
            pl.col("created_at").last().alias("last_updated_at")
        )
        .sort(["zone", "name", "score_date"])
        .to_dicts()
    )

    
    # Build response
    zones_map = {}

    for row in grouped:
        zone = row["zone"]
        plant = row["name"]

        if not data.score_type:
            # OVERALL → avg score
            score_data = {
                "name": "OVERALL",
                "score": row["avg_score"]
            }

        elif data.score_type == "TAS":
            score_data = resolve_tas_with_categories(row["category"])

        else:
            score_data = resolve_category_score(
                row["category"],
                data.score_type
            )

        zones_map.setdefault(zone, {}).setdefault(plant, []).append({
            "date": str(row["score_date"]),
            **score_data
        })

    
    # Final response
    return {
        "status": "success",
        "score_type": data.score_type or "OVERALL",
        "zones": [
            {
                "zone": zone,
                "plants": [
                    {
                        "name": plant,
                        "daywise_scores": scores
                    }
                    for plant, scores in plants.items()
                ]
            }
            for zone, plants in zones_map.items()
        ]
    }
