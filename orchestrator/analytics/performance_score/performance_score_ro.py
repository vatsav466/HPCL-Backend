"""
Retail Outlet (RO) performance score — rules from pi_masters/ro_performance_rules.json.

TEMP: SALES_PERFORMANCE is disabled; NOZZLE_SALES_PATTERN (40%) uses last-30d daily nozzle
pattern (stability) and compares nozzle 30d totals to estimated dryout sales loss.
"""
from __future__ import annotations

import json
import os
import statistics
from typing import Any, Dict, List, Optional, Tuple

import hpcl_ceg_model

import orchestrator.analytics.performance_score.performance_score_factory as performance_score_factory
from orchestrator.analytics.performance_score.performance_score_insights import (
    enhance_result_with_insights,
    generate_summary_insights,
)


def _clamp(score: float) -> float:
    return max(0.0, min(100.0, float(score)))


def score_daily_nozzle_pattern_stability(cv: Optional[float]) -> Tuple[float, str]:
    """
    Last-30d daily nozzle volumes: lower coefficient of variation (std/mean) = steadier pattern = higher score.
    """
    if cv is None:
        return 50.0, "Insufficient daily nozzle data (need ≥3 days with volume); neutral 50."
    c = max(0.0, float(cv))
    s = 100.0 * (1.0 - min(1.0, c))
    return _clamp(s), f"Daily volume CV (std/mean): {c:.4f}; lower is better."


def score_nozzle_vs_sales_loss_share(loss_share: Optional[float]) -> Tuple[float, str]:
    """
    loss_share = estimated dryout loss volume / nozzle 30d total sales volume (0–1+).
    Higher loss share → lower score.
    """
    if loss_share is None:
        return 50.0, "Cannot compare; missing nozzle 30d total or loss estimate."
    r = max(0.0, float(loss_share))
    s = 100.0 * (1.0 - min(1.0, r))
    return _clamp(s), f"Estimated dryout loss volume / nozzle 30d sales = {r:.4f}."


def score_dryout_frequency(count: Optional[float]) -> Tuple[float, str]:
    """§4.1 — Score = 100 − (count × 10), min 0."""
    c = float(count or 0)
    s = 100.0 - (c * 10.0)
    return _clamp(s), f"Dryout events (30d): {c:.0f}; formula 100 − 10×count."


def score_dryout_sales_loss(loss_pct: Optional[float]) -> Tuple[float, str]:
    """§4.2 — Score = 100 − (Loss% × 15)."""
    if loss_pct is None:
        return 50.0, "Dryout sales loss % unavailable; neutral score 50."
    lp = float(loss_pct)
    s = 100.0 - (lp * 15.0)
    return _clamp(s), f"Dryout loss {lp:.2f}% of sales; penalty 15×loss%."


def score_max_dryout_days(max_days: Optional[float]) -> Tuple[float, str]:
    """§4.3 — Score = 100 − (max_days × 20)."""
    d = float(max_days or 0)
    s = 100.0 - (d * 20.0)
    return _clamp(s), f"Max consecutive dryout days (30d window basis): {d:.1f}."


class ROPerformanceScore(performance_score_factory.PerformanceIndex):
    """Retail (RO) weighted score: VA 30% + Nozzle pattern/loss 40% + Dryout 30%."""

    def __init__(self):
        super().__init__()
        self.bu = "RO"
        self.config: Optional[Dict[str, Any]] = None
        self.va_data: Dict[str, Any] = {}

    async def initialize(self):
        base = os.path.dirname(performance_score_factory.__file__)
        path = os.path.join(base, "pi_masters", "ro_performance_rules.json")
        with open(path, encoding="utf-8") as f:
            self.config = json.load(f)

    async def configure_va(self, va_data):
        self.va_data = va_data or {}

    async def generate_performance_index(self, location_id=None):
        module_scores: Dict[str, Any] = {}
        total_weight = sum(m["weightage"] for m in self.config.values())
        for module_name, module in self.config.items():
            fn = getattr(self, f"_compute_{module_name.lower()}_pi_score")
            module_scores[module_name] = await fn(module_name, module, location_id)
        return module_scores, total_weight

    async def _fetch_nozzle_sales_inputs(self, location_id: str) -> Dict[str, Any]:
        """Rolling windows on public.nozzle_sales for one RO sap_id."""
        loc = str(location_id).replace("'", "''")
        query = f"""
        WITH cur AS (
            SELECT COALESCE(SUM(sales_volume), 0)::float8 AS v
            FROM nozzle_sales
            WHERE sap_id = '{loc}'
              AND transaction_date::date >= CURRENT_DATE - INTERVAL '30 days'
              AND transaction_date::date < CURRENT_DATE
        ),
        prev AS (
            SELECT COALESCE(SUM(sales_volume), 0)::float8 AS v
            FROM nozzle_sales
            WHERE sap_id = '{loc}'
              AND transaction_date::date >= CURRENT_DATE - INTERVAL '60 days'
              AND transaction_date::date < CURRENT_DATE - INTERVAL '30 days'
        ),
        ycur AS (
            SELECT COALESCE(SUM(sales_volume), 0)::float8 AS v
            FROM nozzle_sales
            WHERE sap_id = '{loc}'
              AND transaction_date::date >= CURRENT_DATE - INTERVAL '30 days'
              AND transaction_date::date < CURRENT_DATE
        ),
        yprev AS (
            SELECT COALESCE(SUM(sales_volume), 0)::float8 AS v
            FROM nozzle_sales
            WHERE sap_id = '{loc}'
              AND transaction_date::date >= CURRENT_DATE - INTERVAL '395 days'
              AND transaction_date::date < CURRENT_DATE - INTERVAL '365 days'
        )
        SELECT cur.v AS cur_30d, prev.v AS prev_30d, ycur.v AS yoy_cur, yprev.v AS yoy_prev
        FROM cur, prev, ycur, yprev
        """
        try:
            resp = await hpcl_ceg_model.NozzleSales.get_aggr_data(query, limit=0)
            row = (resp.get("data") or [{}])[0]
        except Exception:
            row = {}
        cur_30 = float(row.get("cur_30d") or 0)
        prev_30 = float(row.get("prev_30d") or 0)
        yoy_c = float(row.get("yoy_cur") or 0)
        yoy_p = float(row.get("yoy_prev") or 0)

        growth_pct = None
        if prev_30 > 0:
            growth_pct = (cur_30 - prev_30) / prev_30 * 100.0
        elif cur_30 > 0:
            growth_pct = 100.0

        target = prev_30 * 1.05 if prev_30 > 0 else None
        achievement_pct = (cur_30 / target * 100.0) if target and target > 0 else None

        yoy_pct = None
        if yoy_p > 0:
            yoy_pct = (yoy_c - yoy_p) / yoy_p * 100.0
        elif yoy_c > 0:
            yoy_pct = 100.0

        return {
            "growth_pct": growth_pct,
            "achievement_pct": achievement_pct,
            "yoy_pct": yoy_pct,
            "cur_30d": cur_30,
            "prev_30d": prev_30,
        }

    async def _fetch_dryout_inputs(self, location_id: str, window_days: int = 30) -> Dict[str, Any]:
        loc = str(location_id).replace("'", "''")
        q_freq = f"""
        SELECT COUNT(*)::int AS cnt
        FROM alerts
        WHERE sap_id = '{loc}'
          AND interlock_name = 'Dry Out Each Indent Wise MainFlow'
          AND COALESCE(mark_as_false::text, '') IN ('true', 't', 'True', 'TRUE')
          AND created_at >= NOW() - INTERVAL '{window_days} days'
        """
        q_max = f"""
        SELECT COALESCE(
            MAX(
                CASE
                    WHEN dry_out_in_days ~ '^[0-9]+(\\.[0-9]+)?$'
                    THEN dry_out_in_days::numeric
                    ELSE NULL
                END
            ),
            0
        )::float8 AS max_days
        FROM alerts
        WHERE sap_id = '{loc}'
          AND interlock_name = 'Dry Out Each Indent Wise MainFlow'
          AND created_at >= NOW() - INTERVAL '{window_days} days'
        """
        try:
            fresp = await hpcl_ceg_model.Alerts.get_aggr_data(q_freq, limit=0)
            mresp = await hpcl_ceg_model.Alerts.get_aggr_data(q_max, limit=0)
            cnt = (fresp.get("data") or [{}])[0].get("cnt") or 0
            max_days = (mresp.get("data") or [{}])[0].get("max_days") or 0
        except Exception:
            cnt, max_days = 0, 0

        sales = await self._fetch_nozzle_sales_inputs(location_id)
        total_30 = float(sales.get("cur_30d") or 0)
        est_daily = total_30 / 30.0 if total_30 > 0 else 0.0
        rough_loss_vol = float(cnt) * est_daily
        loss_pct = (rough_loss_vol / total_30 * 100.0) if total_30 > 0 else None
        loss_share = (rough_loss_vol / total_30) if total_30 > 0 else None

        return {
            "dryout_count": float(cnt),
            "max_dryout_days": float(max_days),
            "loss_pct": loss_pct,
            "loss_volume_est": rough_loss_vol,
            "loss_share_vs_nozzle_30d": loss_share,
        }

    async def _fetch_nozzle_daily_volumes_30d(self, location_id: str) -> Tuple[List[float], Optional[float]]:
        """Daily total nozzle sales_volume for last 30 days; return (volumes, cv or None)."""
        loc = str(location_id).replace("'", "''")
        query = f"""
        SELECT transaction_date::date AS d, SUM(sales_volume)::float8 AS vol
        FROM nozzle_sales
        WHERE sap_id = '{loc}'
          AND transaction_date::date >= CURRENT_DATE - INTERVAL '30 days'
          AND transaction_date::date < CURRENT_DATE
        GROUP BY transaction_date::date
        ORDER BY transaction_date::date
        """
        try:
            resp = await hpcl_ceg_model.NozzleSales.get_aggr_data(query, limit=0)
            rows = resp.get("data") or []
        except Exception:
            rows = []
        volumes = [float(r.get("vol") or 0) for r in rows if r.get("vol") is not None]
        if len(volumes) < 3:
            return volumes, None
        mean = statistics.mean(volumes)
        if mean <= 0:
            return volumes, None
        stdev = statistics.stdev(volumes) if len(volumes) > 1 else 0.0
        cv = stdev / mean
        return volumes, cv

    async def _compute_va_score_pi_score(self, name: str, rules: Dict, location_id: str):
        pi_score = []
        for rule in rules["rules"]:
            score = 0.0
            msg = ""
            if rule["model"] == "va_portal":
                if self.va_data:
                    va_overall = float(self.va_data.get("OVERALL_SCORE", 0) or 0)
                    score = round((va_overall * 10.0 * rule["weightage"]) / 100.0, 2)
                    msg = f"VA Portal overall score {va_overall}; scaled to rule weight."
                else:
                    score = 0.0
                    msg = "VA Portal data not available for this location."
            else:
                msg = f"Unknown VA rule model {rule.get('model')}"
            item = {
                "name": rule["name"],
                "score": score,
                "weightage": rule["weightage"],
                "module": rules.get("name", name),
                "msg": msg,
                "details": {},
            }
            item = enhance_result_with_insights(item, rule["model"])
            pi_score.append(item)

        final = sum(s["score"] for s in pi_score)
        final = round((final * rules["weightage"]) / 100.0, 2)
        for rec in pi_score:
            rec["score"] = round(rec["score"], 2)
        module_result = {
            "name": rules.get("name", name),
            "score": final,
            "weightage": rules["weightage"],
            "results": pi_score,
        }
        module_result["insights"] = generate_summary_insights(module_result)
        return module_result

    async def _compute_nozzle_sales_pattern_pi_score(self, name: str, rules: Dict, location_id: str):
        """
        TEMP replacement for SALES_PERFORMANCE: 30d daily nozzle pattern (stability)
        and comparison of nozzle 30d volume vs estimated dryout sales loss volume.
        """
        sales = await self._fetch_nozzle_sales_inputs(location_id)
        dry = await self._fetch_dryout_inputs(location_id, window_days=30)
        volumes, cv = await self._fetch_nozzle_daily_volumes_30d(location_id)

        pi_score = []
        for rule in rules["rules"]:
            model = rule["model"]
            raw = 0.0
            msg = ""
            if model == "nozzle_sales_30d_pattern":
                raw, msg = score_daily_nozzle_pattern_stability(cv)
            elif model == "nozzle_vs_sales_loss":
                share = dry.get("loss_share_vs_nozzle_30d")
                raw, msg = score_nozzle_vs_sales_loss_share(share)
            else:
                raw, msg = 0.0, f"Unknown nozzle pattern model {model}"
            rw = float(rule["weightage"])
            mscore = round((raw * rw) / 100.0, 2)
            item = {
                "name": rule["name"],
                "score": mscore,
                "weightage": rule["weightage"],
                "module": rules.get("name", name),
                "msg": msg,
                "details": {
                    "metric_score_0_100": round(raw, 2),
                    "nozzle_30d_total": sales.get("cur_30d"),
                    "daily_days_observed": len(volumes),
                    "daily_volume_cv": cv,
                    "dryout_loss_volume_est": dry.get("loss_volume_est"),
                    "loss_share_vs_nozzle_30d": dry.get("loss_share_vs_nozzle_30d"),
                },
            }
            item = enhance_result_with_insights(item, model)
            pi_score.append(item)

        section = sum(s["score"] for s in pi_score)
        final = round((section * rules["weightage"]) / 100.0, 2)
        module_result = {
            "name": rules.get("name", name),
            "score": final,
            "weightage": rules["weightage"],
            "results": pi_score,
        }
        module_result["insights"] = generate_summary_insights(module_result)
        return module_result

    async def _compute_dryout_patterns_pi_score(self, name: str, rules: Dict, location_id: str):
        pi_score = []
        for rule in rules["rules"]:
            window = int(rule.get("time_window_days") or 30)
            dry = await self._fetch_dryout_inputs(location_id, window_days=window)
            model = rule["model"]
            raw = 0.0
            msg = ""
            if model == "dryout_frequency_30d":
                raw, msg = score_dryout_frequency(dry.get("dryout_count"))
            elif model == "dryout_sales_loss_30d":
                raw, msg = score_dryout_sales_loss(dry.get("loss_pct"))
            elif model == "max_dryout_days_30d":
                raw, msg = score_max_dryout_days(dry.get("max_dryout_days"))
            else:
                raw, msg = 0.0, f"Unknown dryout model {model}"
            rw = float(rule["weightage"])
            mscore = round((raw * rw) / 100.0, 2)
            item = {
                "name": rule["name"],
                "score": mscore,
                "weightage": rule["weightage"],
                "module": rules.get("name", name),
                "msg": msg,
                "details": {"metric_score_0_100": round(raw, 2), "dryout": dry},
            }
            item = enhance_result_with_insights(item, model)
            pi_score.append(item)

        section = sum(s["score"] for s in pi_score)
        final = round((section * rules["weightage"]) / 100.0, 2)
        module_result = {
            "name": rules.get("name", name),
            "score": final,
            "weightage": rules["weightage"],
            "results": pi_score,
        }
        module_result["insights"] = generate_summary_insights(module_result)
        return module_result
