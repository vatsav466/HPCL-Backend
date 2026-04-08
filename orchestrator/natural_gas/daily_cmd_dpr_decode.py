"""
Decode ``Daily C&MD DPR.xlsx`` layout:

- **MIS Summary**: entity rows under ``Entity Name`` with paired period × (New/Old) metrics.
- **HPCL-JV MIS**: repeated blocks per company (HPCL / HOGPL / BGL); each block has GA rows
  (GA ID, GA Area, State/UTs) and the same metric columns as the summary.

Period bands in the sheet match keys like ``Cum MARCH-26 | new``, ``1st April | old``, …
(not the full Excel subheader text). The standalone **Grand total NGC** column is omitted
by default; pass ``include_grand_total_ngc_column=True`` to include it.

Columns whose period label contains **Cumulative** (e.g. ``Cumulative April'26``,
``Cumulative NGC``) are omitted unless ``include_cumulative_columns=True`` (default ``False``).

Sheet names are matched case-insensitively with whitespace stripped.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Union

import pandas as pd


def _cell_str(v: Any) -> str:
    if v is None or (isinstance(v, float) and (math.isnan(v) or pd.isna(v))):
        return ""
    return str(v).strip()


def _norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\n", " ")).strip()


def _metric_keys_from_headers(
    period_row: pd.Series,
    metric_row: pd.Series,
    metric_col_start: int,
    metric_col_end: Optional[int] = None,
    *,
    short_metric_keys: bool = True,
    include_grand_total_ngc_column: bool = False,
    include_cumulative_columns: bool = False,
) -> Dict[int, str]:
    """
    Map column index -> key from two header rows (period band + New/Old subcolumns).

    - **ffill** is applied only across ``metric_col_start:end`` so the company cell
      in column 0 (e.g. ``HPCL``) does not leak into period labels.
    - Default keys match the workbook bands: ``\"Cum MARCH-26 | new\"``,
      ``\"Cum MARCH-26 | old\"``, … — not the full ``New Connection Done…`` text.
    - The trailing **Grand total NGC** single column (not part of the period grid) is
      omitted unless ``include_grand_total_ngc_column`` is True.
    - Period bands whose label contains **Cumulative** are omitted unless
      ``include_cumulative_columns`` is True (default False).
    """
    end = metric_col_end if metric_col_end is not None else len(period_row)
    pr = period_row.copy()
    seg = pr.iloc[metric_col_start:end].ffill()
    pr.iloc[metric_col_start:end] = seg

    keys: Dict[int, str] = {}
    for j in range(metric_col_start, min(end, len(period_row))):
        p = pr.iloc[j]
        m = metric_row.iloc[j]
        pstr = _norm_key(_cell_str(p)) if pd.notna(p) else ""
        mstr = _norm_key(_cell_str(m)) if pd.notna(m) else ""
        if not pstr and not mstr:
            continue

        ml = mstr.lower()
        # Standalone total column (not New/Old under a period)
        if (
            not include_grand_total_ngc_column
            and "grand total" in ml
            and "ngc" in ml
            and "connection" not in ml
        ):
            continue

        if short_metric_keys:
            if "new connection" in ml and "gasified" in ml:
                key = f"{pstr} | new"
            elif "old connection" in ml and "gasified" in ml:
                key = f"{pstr} | old"
            elif "grand total" in ml and "ngc" in ml:
                key = _norm_key(mstr)
            elif pstr and mstr:
                key = f"{pstr} | {mstr}"
            else:
                key = mstr or pstr
        elif mstr and "grand total" in ml and "ngc" in ml and "connection" not in ml:
            key = _norm_key(mstr)
        elif pstr and mstr:
            key = f"{pstr} | {mstr}"
        else:
            key = mstr or pstr

        if not include_cumulative_columns and pstr and "cumulative" in pstr.lower():
            continue

        keys[j] = key
    return keys


def parse_mis_summary_sheet(
    df: pd.DataFrame,
    *,
    entity_col: int = 1,
    period_row_idx: int = 1,
    metric_row_idx: int = 2,
    data_row_start: int = 3,
    include_grand_total_ngc_column: bool = False,
    include_cumulative_columns: bool = False,
) -> List[Dict[str, Any]]:
    """
    Parse **MIS Summary** sheet: ``Entity Name`` column + Summary metric columns.

    Expects raw ``header=None`` DataFrame from ``pd.read_excel(..., header=None)``.
    """
    if df.shape[0] <= metric_row_idx:
        return []
    period_row = df.iloc[period_row_idx]
    metric_row = df.iloc[metric_row_idx]
    keys = _metric_keys_from_headers(
        period_row,
        metric_row,
        metric_col_start=4,
        include_grand_total_ngc_column=include_grand_total_ngc_column,
        include_cumulative_columns=include_cumulative_columns,
    )

    out: List[Dict[str, Any]] = []
    for i in range(data_row_start, len(df)):
        ent = _cell_str(df.iloc[i, entity_col])
        if not ent:
            continue
        row: Dict[str, Any] = {"entity_name": ent, "_row_index": i}
        for j, name in keys.items():
            if j >= df.shape[1]:
                continue
            v = df.iloc[i, j]
            row[name] = None if pd.isna(v) else v
        out.append(row)
    return out


def parse_hpcl_jv_mis_sheet(
    df: pd.DataFrame,
    *,
    include_grand_total_ngc_column: bool = False,
    include_cumulative_columns: bool = False,
) -> List[Dict[str, Any]]:
    """
    Parse **HPCL-JV MIS**: one record per GA row under each company block (HPCL / HOGPL / BGL).

    Skips embedded mini-summary blocks (where the row after company is not ``GA ID``).
    """
    n = len(df)
    out: List[Dict[str, Any]] = []
    i = 0
    while i < n:
        c0 = _cell_str(df.iloc[i, 0])
        if c0 not in ("HPCL", "HOGPL", "BGL"):
            i += 1
            continue
        if i + 1 >= n:
            break
        next_h = _cell_str(df.iloc[i + 1, 0])
        if next_h != "GA ID":
            i += 1
            continue

        company = c0
        period_row = df.iloc[i]
        metric_row = df.iloc[i + 1]
        keys = _metric_keys_from_headers(
            period_row,
            metric_row,
            metric_col_start=3,
            include_grand_total_ngc_column=include_grand_total_ngc_column,
            include_cumulative_columns=include_cumulative_columns,
        )
        i += 2
        while i < n and _is_blank_leading_cells(df.iloc[i], 3):
            i += 1

        while i < n:
            r = df.iloc[i]
            fs = _cell_str(r[0])
            if fs in ("HPCL", "HOGPL", "BGL"):
                break
            if fs == "Summary":
                break
            if fs in ("Total", "Grand Total"):
                i += 1
                continue
            if fs == "GA ID" or (not fs and not _cell_str(r[1])):
                i += 1
                continue
            rec: Dict[str, Any] = {
                "company": company,
                "ga_id": None if pd.isna(r[0]) else r[0],
                "ga_area": _cell_str(r[1]) or None,
                "state": _cell_str(r[2]) or None,
                "_row_index": i,
            }
            for j, name in keys.items():
                if j >= len(r):
                    continue
                v = r[j]
                rec[name] = None if pd.isna(v) else v
            out.append(rec)
            i += 1
    return out


def _is_blank_leading_cells(row: pd.Series, n_lead: int) -> bool:
    for j in range(min(n_lead, len(row))):
        if pd.notna(row.iloc[j]) and _cell_str(row.iloc[j]):
            return False
    return True


def decode_daily_cmd_dpr_workbook(
    path_or_file: Union[str, Any],
    *,
    include_grand_total_ngc_column: bool = False,
    include_cumulative_columns: bool = False,
) -> Dict[str, Any]:
    """
    Load ``Daily C&MD DPR.xlsx`` and return decoded ``mis_summary`` and ``hpcl_jv_mis`` lists.

    ``path_or_file`` may be a path string or a file-like object (e.g. ``UploadFile.file``).
    """
    xls = pd.ExcelFile(path_or_file)
    mis_name = _find_sheet(xls.sheet_names, "mis summary")
    jv_name = _find_sheet(xls.sheet_names, "hpcl-jv mis")

    result: Dict[str, Any] = {"sheets_present": list(xls.sheet_names)}
    if mis_name:
        raw = pd.read_excel(xls, sheet_name=mis_name, header=None)
        result["mis_summary"] = parse_mis_summary_sheet(
            raw,
            include_grand_total_ngc_column=include_grand_total_ngc_column,
            include_cumulative_columns=include_cumulative_columns,
        )
        result["mis_summary_sheet"] = mis_name
    else:
        result["mis_summary"] = []
        result["mis_summary_sheet"] = None

    if jv_name:
        raw_jv = pd.read_excel(xls, sheet_name=jv_name, header=None)
        result["hpcl_jv_mis"] = parse_hpcl_jv_mis_sheet(
            raw_jv,
            include_grand_total_ngc_column=include_grand_total_ngc_column,
            include_cumulative_columns=include_cumulative_columns,
        )
        result["hpcl_jv_mis_sheet"] = jv_name
    else:
        result["hpcl_jv_mis"] = []
        result["hpcl_jv_mis_sheet"] = None

    return result


def _find_sheet(names: List[str], want_lower: str) -> Optional[str]:
    want = want_lower.strip().lower().replace(" ", "")
    for s in names:
        if s.strip().lower().replace(" ", "") == want:
            return s
    for s in names:
        if want_lower in s.strip().lower():
            return s
    return None


def json_safe_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert numpy/pandas scalars for JSON encoding."""
    out: List[Dict[str, Any]] = []
    for r in records:
        row = {}
        for k, v in r.items():
            if hasattr(v, "item"):
                try:
                    v = v.item()
                except Exception:
                    pass
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                row[k] = None
            else:
                row[k] = v
        out.append(row)
    return out
