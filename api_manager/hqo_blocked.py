import polars as pl
import urdhva_base
from hpcl_ceg_model import Alerts
import re
import unicodedata
import json
import asyncio
from fastapi.responses import StreamingResponse

# =====================================================
# EXCEL CONFIG (LOAD ONCE AT STARTUP)
# =====================================================
EXCEL_PATH = "/home/novex/Copy_of_Novex_Report-TAS.xlsx"
SHEET_NAME = "Alerts summary report"

_sop_df = pl.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)

# Strip column names (CRITICAL)
_sop_df = _sop_df.rename(
    {c: c.strip() for c in _sop_df.columns}
)

# Rename columns
_sop_df = _sop_df.rename({
    "Event / Alarm name": "event_name",
    "Reason": "reason",
    "Impact": "impact",
    "Action required for alert closer": "action_required",
    "Backend Interlock Check points": "backend_rules"
})

# Forward fill event name
_sop_df = _sop_df.with_columns(
    pl.col("event_name").forward_fill()
)

# =====================================================
# STRONG NORMALIZATION (EXCEL + DB SAFE)
# =====================================================
def normalize_exact(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u00A0\u2000-\u200F\u202F\u205F\u3000]", " ", text)
    text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)

    return text

# PREPARE SOP DATA
_sop_df = _sop_df.with_columns(
    pl.col("event_name")
    .cast(pl.Utf8)
    .map_elements(normalize_exact)
    .alias("norm_event")
)

# Backend rules → list[str]
_sop_df = _sop_df.with_columns(
    pl.col("backend_rules")
    .fill_null("")
    .map_elements(
        lambda x: [r.strip() for r in str(x).split(",") if r.strip()]
    )
)

# BACKEND INTERLOCK CHECK (ANY MATCH)
async def check_any_interlock_exists(
    interlock_names: list[str],
    start_date: str,
    end_date: str
) -> bool:

    if not interlock_names:
        return False

    names = ",".join(f"'{n}'" for n in interlock_names)

    query = (
        f"interlock_name IN ({names}) "
        "AND alert_status = 'Open' "
        "AND bu = 'TAS' "
        f"AND created_at::date BETWEEN '{start_date}' AND '{end_date}'"
    )

    params = urdhva_base.queryparams.QueryParams(q=query, limit=1)
    resp = await Alerts.get_all(params, resp_type="plain")

    return bool(resp.get("data"))

# SOP RESOLUTION LOGIC (CLEAN & FAST)
async def resolve_sop_logic(
    interlock_name: str,
    start_date: str,
    end_date: str
) -> dict:

    norm_alert = normalize_exact(interlock_name)

    #  EXACT MATCH
    sop_rows = _sop_df.filter(
        pl.col("norm_event") == norm_alert
    )

    #  FALLBACK CONTAINS
    if sop_rows.height == 0:
        sop_rows = _sop_df.filter(
            pl.col("norm_event").str.contains(norm_alert, literal=True)
            | pl.col("norm_event").str.contains(norm_alert.replace("_", " "), literal=True)
            | pl.col("norm_event").str.contains(norm_alert.replace(" ", "_"), literal=True)
        )

    if sop_rows.height == 0:
        return {
            "reason": "No SOP defined",
            "impact": "Operational / monitoring alert",
            "action_required": "Escalate to Safety / Operations"
        }

    #  BACKEND RULE PRIORITY
    for row in sop_rows.iter_rows(named=True):
        if row["backend_rules"]:
            if await check_any_interlock_exists(
                row["backend_rules"], start_date, end_date
            ):
                return {
                    "reason": row["reason"],
                    "impact": row["impact"],
                    "action_required": row["action_required"]
                }

    # SOP WITHOUT BACKEND RULE
    fallback_rows = sop_rows.filter(
        pl.col("backend_rules").list.len() == 0
    )

    if fallback_rows.height > 0:
        row = fallback_rows.row(0, named=True)
        return {
            "reason": row["reason"],
            "impact": row["impact"],
            "action_required": row["action_required"]
        }

    #  FINAL FALLBACK
    return {
        "reason": "False alert from TAS system",
        "impact": "No supporting backend interlocks detected",
        "action_required": "Verify alert source and instrumentation"
    }

# STREAMING PAGINATION FUNCTION (AS GIVEN)
async def streaming_data(df: pl.DataFrame):
    batch_size = 10000
    total = df.height

    async def json_generator():
        for i in range(0, total, batch_size):
            yield json.dumps(df.slice(i, batch_size).to_dicts())
            await asyncio.sleep(0.1)

    return StreamingResponse(
        json_generator(),
        media_type="application/json"
    )

# MAIN SERVICE FUNCTION (STREAMING RESPONSE)
async def get_blocked_trucks_service(start_date: str, end_date: str):

    alert_query = (
        "alert_status = 'Open' "
        "AND bu = 'TAS' "
        f"AND created_at::date BETWEEN '{start_date}' AND '{end_date}'"
    )

    alert_params = urdhva_base.queryparams.QueryParams(
        q=alert_query,
        limit=0
    )

    alert_params.fields = [
        "unique_id",
        "alert_status",
        "interlock_name",
        "location_name",
        "created_at"
    ]

    alerts_resp = await Alerts.get_all(alert_params, resp_type="plain")
    alerts_data = alerts_resp.get("data", [])

    result = []

    for alert in alerts_data:
        sop_result = await resolve_sop_logic(
            alert.get("interlock_name"),
            start_date,
            end_date
        )

        result.append({
            "unique_id": alert.get("unique_id"),
            "alert_status": alert.get("alert_status"),
            "interlock_name": alert.get("interlock_name"),
            "location_name": alert.get("location_name"),
            "created_at": alert.get("created_at"),
            "reason": sop_result["reason"],
            "impact": sop_result["impact"],
            "action_required": sop_result["action_required"]
        })

    # Convert result → Polars DataFrame
    df = pl.DataFrame(result).with_columns(
        pl.col("created_at")
        .cast(pl.Datetime)
        .dt.strftime("%Y-%m-%dT%H:%M:%S")
    )

    return await streaming_data(df)
