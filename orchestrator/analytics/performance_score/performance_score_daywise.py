import urdhva_base
import polars as pl
import json
from datetime import datetime
from decimal import Decimal
from hpcl_ceg_model import PerformanceScoreHistory


TAS_CATEGORIES = {
    "Safety_Interlocks",
    "Gantry_Interlocks",
    "Process_Interlocks",
    "Water_Quantity",
    "Foam_Quantity",
    "Fire_Engines_In_Auto_Mode",
    "Hydrant_Line",
}


def sanitize_records(records):
    return [
        {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}
        for row in records
    ]


def resolve_tas_with_categories(categories):
    tas = next((c for c in categories if c.get("name") == "TAS"), None)

    if not tas or not tas.get("results"):
        return {"categories": []}

    tas_categories = [
        c for c in tas["results"]
        if c.get("name") in TAS_CATEGORIES
    ]

    return {
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
                        "module": r.get("module"),
                    }
                    for r in c.get("results", [])
                ],
            }
            for c in tas_categories
        ]
    }


def add_filters(query_str, key, values):
    if not values:
        return query_str

    if isinstance(values, list):
        query_str += f" AND {key} IN {tuple(values)}"
    else:
        query_str += f" AND {key} = '{values}'"

    return query_str


# ================= MAIN API =================
async def performance_score_daywise_action(data):

    query_str = f"bu = '{data.bu}'"

    if data.start_date:
        query_str += f" AND created_at >= '{data.start_date}'"

    if data.end_date:
        query_str += f" AND created_at <= '{data.end_date}'"

    if data.zone:
        query_str = add_filters(query_str, "zone", data.zone)

    if data.name:
        query_str = add_filters(query_str, "name", data.name)

    params = urdhva_base.queryparams.QueryParams(
        q=query_str,
        limit=0
    )

    resp = await PerformanceScoreHistory.get_all(params, resp_type="plain")
    records = sanitize_records(resp.get("data", []))

    if not records:
        return {"status": "success", "zones": []}

    df = (
        pl.DataFrame(records, strict=False)
        .with_columns(
            pl.col("created_at")
            .cast(pl.Datetime)
            .dt.date()
            .alias("score_date")
        )
    )

    # ================= GROUP =================

    # ================= GROUP =================
    grouped = (
        df.sort("created_at")
        .group_by(["zone", "name", "score_date"])
        .agg(
            pl.col("score").last().alias("db_score"),
            pl.col("category").last()
        )
        .to_dicts()
    )

    zones_map = {}

    # overall
    zone_scores = {}
    plant_scores = {}

    # day-wise
    date_zone_scores = {}
    date_plant_scores = {}

    for row in grouped:
        zone = row["zone"]
        plant = row["name"]
        score_date = str(row["score_date"])
        score_val = row["db_score"]
        category = row["category"]

        if isinstance(category, str):
            category = json.loads(category)

        score_data = {
            "date": score_date,
            "name": "TAS",
            "score": score_val,
            "categories": resolve_tas_with_categories(category or {}).get("categories", [])
        }

        zones_map.setdefault(zone, {}).setdefault(plant, []).append(score_data)

        # ---------- overall ----------
        zone_scores.setdefault(zone, []).append(score_val)
        plant_scores.setdefault((zone, plant), []).append(score_val)

        # ---------- day-wise ----------
        date_zone_scores.setdefault(score_date, {}).setdefault(zone, []).append(score_val)
        date_plant_scores.setdefault(score_date, {}).setdefault(plant, []).append(score_val)

    # ================= OVERALL AVERAGES =================
    zone_avg = round(
        sum(sum(v) / len(v) for v in zone_scores.values()) / len(zone_scores),
        2
    ) if zone_scores else 0

    plant_avg = round(
        sum(sum(v) / len(v) for v in plant_scores.values()) / len(plant_scores),
        2
    ) if plant_scores else 0

    # ================= DAY-WISE ZONE AVG =================
    zone_avg_daywise = [
        {
            "date": date,
            "avg_score": round(
                sum(sum(scores) / len(scores) for scores in zones.values()) / len(zones),
                2
            )
        }
        for date, zones in sorted(date_zone_scores.items())
    ]

    # ================= DAY-WISE PLANT AVG =================
    plant_avg_daywise = [
        {
            "date": date,
            "avg_score": round(
                sum(sum(scores) / len(scores) for scores in plants.values()) / len(plants),
                2
            )
        }
        for date, plants in sorted(date_plant_scores.items())
    ]

    # ================= RESPONSE =================
    return {
        "status": "success",
        "score_type": data.score_type,
        "zone_avg": zone_avg,
        "plant_avg": plant_avg,
        "zone_avg_daywise": zone_avg_daywise,
        "plant_avg_daywise": plant_avg_daywise,
        "zones": [
            {
                "zone": zone,
                "plants": [
                    {
                        "name": plant,
                        "daywise_scores": sorted(scores, key=lambda x: x["date"])
                    }
                    for plant, scores in plants.items()
                ]
            }
            for zone, plants in zones_map.items()
        ]
    }
