"""
Map decoded Daily C&MD DPR payloads to rows for:

- ``natural_gas_connections_summary`` → :class:`NaturalGasConnectionsSummaryCreate` shape
- ``natural_gas_connections`` → :class:`NaturalGasConnectionsCreate` shape

Schema (see ``hpcl_ceg_model``): ``jv_name``, ``conn_date``, ``new_connection_count``,
``old_connection_count``; connections also ``ga_area``, ``ga_id``, ``state``.

Wide Excel columns (``Period | New/Old …``) are pivoted to one DB row per
(jv_name, conn_date) with paired new/old counts. Period labels are mapped to
``conn_date`` with a fixed calendar (see :func:`period_to_conn_date` docstring).
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

# ---------------------------------------------------------------------------
# Row shapes matching hpcl_ceg_model NaturalGasConnections*Create fields
# ---------------------------------------------------------------------------


class NaturalGasConnectionsSummaryRow(TypedDict):
    jv_name: str
    conn_date: str  # ISO date
    new_connection_count: int
    old_connection_count: int


class NaturalGasConnectionsRow(TypedDict):
    jv_name: str
    conn_date: str
    new_connection_count: int
    old_connection_count: int
    ga_area: str
    ga_id: str
    state: str


_AGGREGATE_ENTITY_NAMES = frozenset(
    {x.lower() for x in ("Total", "Grand Total", "total", "grand total")}
)


def _default_month_tokens() -> Dict[str, int]:
    """Lowercase month names/abbreviations → month number (1–12)."""
    return {
        "january": 1,
        "jan": 1,
        "february": 2,
        "feb": 2,
        "march": 3,
        "mar": 3,
        "april": 4,
        "apr": 4,
        "may": 5,
        "june": 6,
        "jun": 6,
        "july": 7,
        "jul": 7,
        "august": 8,
        "aug": 8,
        "september": 9,
        "sep": 9,
        "sept": 9,
        "october": 10,
        "oct": 10,
        "november": 11,
        "nov": 11,
        "december": 12,
        "dec": 12,
    }


@dataclass(frozen=True)
class PeriodDateMapping:
    """
    Calendar rules for mapping Excel **period** labels to ``conn_date``.

    - ``month_tokens``: substring → month 1–12 (longest match wins).
    - ``cumulative_band_no_ngc`` / ``cumulative_band_ngc``: ``(month, day)`` for
      cumulative slices (disambiguates overlapping bands).
    """

    month_tokens: Dict[str, int] = field(default_factory=_default_month_tokens)
    cumulative_band_no_ngc: Tuple[int, int] = (4, 29)
    cumulative_band_ngc: Tuple[int, int] = (4, 30)


DEFAULT_PERIOD_DATE_MAPPING = PeriodDateMapping()


def _first_month_token(period_lower: str, mapping: PeriodDateMapping) -> Optional[int]:
    """Return month number for the first matching token in ``month_tokens`` (longest first)."""
    for token in sorted(mapping.month_tokens.keys(), key=len, reverse=True):
        if token in period_lower:
            return mapping.month_tokens[token]
    return None


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _parse_ordinal_day_month(
    period: str, report_year: int, mapping: PeriodDateMapping
) -> Optional[date]:
    """
    ``1st April``, ``2nd March``, … using ``month_tokens`` (not a single hardcoded month).
    """
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)\s+([A-Za-z]+)", period, re.I)
    if not m:
        return None
    day = int(m.group(1))
    word = m.group(2).lower()
    month_num: Optional[int] = None
    if word in mapping.month_tokens:
        month_num = mapping.month_tokens[word]
    else:
        for tok in sorted(mapping.month_tokens.keys(), key=len, reverse=True):
            if word.startswith(tok):
                month_num = mapping.month_tokens[tok]
                break
    if month_num is None:
        return None
    last = _last_day_of_month(report_year, month_num)
    day = min(day, last)
    return date(report_year, month_num, day)


def _norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).replace("\n", " ")).strip()


def normalize_metric_column_key(key: str) -> str:
    """Unify minor header variants (e.g. ``Cum`` vs ``Cum.``) for parsing."""
    k = _norm_key(key)
    k = re.sub(r"Cum\.\s+", "Cum ", k, flags=re.I)
    k = re.sub(r"Cum\s+", "Cum ", k, flags=re.I)
    return k


def _parse_metric_key(key: str) -> Optional[Tuple[str, Literal["new", "old"], Literal["metric", "grand_total"]]]:
    k = normalize_metric_column_key(key)
    if re.fullmatch(r"Grand total NGC", k, flags=re.I):
        return ("", "new", "grand_total")  # sentinel; handled separately
    if "|" not in k:
        return None
    left, right = k.split("|", 1)
    period = left.strip()
    r = right.strip().lower()
    # Short keys from daily_cmd_dpr_decode (``Period | new`` / ``Period | old``)
    if r == "new":
        return (period, "new", "metric")
    if r == "old":
        return (period, "old", "metric")
    if "new connection" in r and "gasified" in r:
        return (period, "new", "metric")
    if "old connection" in r and "gasified" in r:
        return (period, "old", "metric")
    return None


def period_to_conn_date(
    period: str,
    *,
    report_year: int = 2026,
    mapping: Optional[PeriodDateMapping] = None,
    include_cumulative_data: bool = False,
) -> Optional[date]:
    """
    Map the left-hand **period** label from the Excel header to a single ``conn_date``.

    Uses :class:`PeriodDateMapping` for month/day rules.

    Check order matters: **cumulative** must be handled before **cum**, because the
    substring ``cum`` appears inside ``cumulative``.

    - **Cumulative …** (e.g. April'26, NGC) → uses ``cumulative_band_*`` only when
      ``include_cumulative_data`` is True; otherwise returns None.
    - **1st April**, **2nd March**, … → ordinal day + month from ``month_tokens``.
    - **Cum MARCH-26**-style (snapshot, not the word *cumulative*) → last day of month
      from the first month token in ``mapping.month_tokens``.

    Pass a custom ``mapping`` to override defaults; adjust ``report_year`` for the workbook year.
    """
    m = mapping or DEFAULT_PERIOD_DATE_MAPPING
    p = _norm_key(period)
    pl = p.lower()

    if "cumulative" in pl:
        if not include_cumulative_data:
            return None
        if "ngc" in pl:
            mo, dy = m.cumulative_band_ngc
            return date(report_year, mo, dy)
        return date(report_year, m.cumulative_band_no_ngc[0], m.cumulative_band_no_ngc[1])

    ord_d = _parse_ordinal_day_month(p, report_year, m)
    if ord_d is not None:
        return ord_d

    if "cum" in pl:
        month_num = _first_month_token(pl, m)
        if month_num is not None:
            ld = _last_day_of_month(report_year, month_num)
            return date(report_year, month_num, ld)

    return None


def _coerce_int(v: Any) -> int:
    if v is None:
        return 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int,)):
        return int(v)
    if isinstance(v, float):
        if v != v:  # NaN
            return 0
        return int(round(v))
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return 0


def _format_ga_id(v: Any) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, float):
        if v != v:
            return ""
        if v == int(v):
            return str(int(v))
        return str(v).rstrip("0").rstrip(".") if "." in str(v) else str(v)
    return str(v).strip()


def _pivot_wide_row_to_date_counts(
    row: Dict[str, Any],
    *,
    report_year: int,
    include_grand_total: bool,
    period_mapping: Optional[PeriodDateMapping] = None,
    include_cumulative_data: bool = False,
) -> Tuple[Dict[date, Dict[str, int]], Optional[int]]:
    """
    Returns (by_date {conn_date: {new, old}}, grand_total_value or None).
    """
    by_date: Dict[date, Dict[str, int]] = {}
    grand_total: Optional[int] = None

    for key, raw in row.items():
        if key in ("entity_name", "company", "_row_index", "ga_id", "ga_area", "state"):
            continue
        k = normalize_metric_column_key(str(key))
        if re.fullmatch(r"Grand total NGC", k, flags=re.I):
            if include_grand_total:
                grand_total = _coerce_int(raw)
            continue
        parsed = _parse_metric_key(str(key))
        if not parsed:
            continue
        period, kind, kind_meta = parsed
        if kind_meta == "grand_total":
            continue
        d = period_to_conn_date(
            period,
            report_year=report_year,
            mapping=period_mapping,
            include_cumulative_data=include_cumulative_data,
        )
        if d is None:
            continue
        by_date.setdefault(d, {"new": 0, "old": 0})
        by_date[d][kind] = _coerce_int(raw)

    return by_date, grand_total


def mis_summary_to_summary_records(
    mis_summary: List[Dict[str, Any]],
    *,
    report_year: int = 2026,
    exclude_aggregates: bool = True,
    period_mapping: Optional[PeriodDateMapping] = None,
    include_cumulative_data: bool = False,
) -> List[NaturalGasConnectionsSummaryRow]:
    """
    ``mis_summary`` rows → ``natural_gas_connections_summary``-shaped dicts
    (``conn_date`` as ISO strings for JSON/ORM).
    """
    out: List[NaturalGasConnectionsSummaryRow] = []
    for row in mis_summary:
        ent = str(row.get("entity_name", "")).strip()
        if not ent:
            continue
        if exclude_aggregates and ent.lower() in _AGGREGATE_ENTITY_NAMES:
            continue

        by_date, _gt = _pivot_wide_row_to_date_counts(
            row,
            report_year=report_year,
            include_grand_total=False,
            period_mapping=period_mapping,
            include_cumulative_data=include_cumulative_data,
        )
        for conn_d, counts in sorted(by_date.items()):
            out.append(
                {
                    "jv_name": ent,
                    "conn_date": conn_d.isoformat(),
                    "new_connection_count": int(counts.get("new", 0)),
                    "old_connection_count": int(counts.get("old", 0)),
                }
            )
    return out


def hpcl_jv_mis_to_connection_records(
    hpcl_jv_mis: List[Dict[str, Any]],
    *,
    report_year: int = 2026,
    period_mapping: Optional[PeriodDateMapping] = None,
    include_cumulative_data: bool = False,
) -> List[NaturalGasConnectionsRow]:
    """
    ``hpcl_jv_mis`` rows → ``natural_gas_connections``-shaped dicts.
    """
    out: List[NaturalGasConnectionsRow] = []
    for row in hpcl_jv_mis:
        company = str(row.get("company", "")).strip()
        ga_area = str(row.get("ga_area", "") or "").strip()
        state = str(row.get("state", "") or "").strip()
        if not company:
            continue

        by_date, _ = _pivot_wide_row_to_date_counts(
            row,
            report_year=report_year,
            include_grand_total=False,
            period_mapping=period_mapping,
            include_cumulative_data=include_cumulative_data,
        )
        ga_id = _format_ga_id(row.get("ga_id"))

        for conn_d, counts in sorted(by_date.items()):
            out.append(
                {
                    "jv_name": company,
                    "conn_date": conn_d.isoformat(),
                    "new_connection_count": int(counts.get("new", 0)),
                    "old_connection_count": int(counts.get("old", 0)),
                    "ga_area": ga_area or "-",
                    "ga_id": ga_id,
                    "state": state or "-",
                }
            )
    return out


def decoded_payload_to_db_records(
    decoded: Dict[str, Any],
    *,
    report_year: int = 2026,
    exclude_summary_aggregates: bool = True,
    period_mapping: Optional[PeriodDateMapping] = None,
    include_cumulative_columns: bool = False,
) -> Dict[str, Any]:
    """
    Full output of :func:`daily_cmd_dpr_decode.decode_daily_cmd_dpr_workbook` → DB-ready lists.

    ``include_cumulative_columns`` should match the same flag passed to decode: when False,
    cumulative period labels are not mapped to ``conn_date`` rows (and are usually absent from
    decoded keys already).

    Returns::

        {
          "natural_gas_connections_summary": [...],
          "natural_gas_connections": [...],
          "report_year": int,
        }
    """
    mis = decoded.get("mis_summary") or []
    jv = decoded.get("hpcl_jv_mis") or []
    cum_data = include_cumulative_columns
    return {
        "natural_gas_connections_summary": mis_summary_to_summary_records(
            mis,
            report_year=report_year,
            exclude_aggregates=exclude_summary_aggregates,
            period_mapping=period_mapping,
            include_cumulative_data=cum_data,
        ),
        "natural_gas_connections": hpcl_jv_mis_to_connection_records(
            jv,
            report_year=report_year,
            period_mapping=period_mapping,
            include_cumulative_data=cum_data,
        ),
        "report_year": report_year,
    }
