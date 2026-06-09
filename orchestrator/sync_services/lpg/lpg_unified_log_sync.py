"""
Unified incremental sync for **event_log** and **production_log** in one module.

This is **not** a calendar-day full-table pull: each run asks the plant DB only for rows
**after the last saved keyset** (or after the latest row already in APP_DB when the
unified cursor is new), so routine runs stay small.

Fixes carried over from analysis of ``event_log_sync`` / ``production_log_sync``:

* **Keyset pagination** on ``(process_date, <native_id>)`` instead of ``LIMIT/OFFSET``,
  avoiding skipped / duplicated rows when the source table changes or many rows share
  the same ``process_date``.
* **Cursor watermark** per (plant, log kind) stores ``(last_process_date, last_source_id)``
  so the window predicate is not ``> max(process_date)`` only (which breaks when many
  rows share one timestamp).
* **Deduplication before insert**: rows already present in APP_DB for the same
  ``sap_id`` + native id are skipped (works with legacy rows that predate ``plan_id``).
* **Safe temp files** for ``COPY`` (unique paths; no shared ``/tmp/production_log_0.csv``
  across threads).
* Adds **plan_id** (ERP id from credentials), **plant_id** (CSV ``id``), and **time_stamp**
  (full-fidelity ``process_date``) on every inserted row.

Uniqueness in practice is ``(sap_id, event_log_id)`` / ``(sap_id, production_log_id)``
because timestamps can collide; ``plan_id`` + ``time_stamp`` are populated for
filtering and reporting.

Environment:

* Plant credentials are loaded from ``lpg_plants_master`` via ``LpgPlantsMaster.get_aggr_data``.
* ``LPG_UNIFIED_CHUNK_SIZE`` — rows per plant fetch (default ``25000``).
* ``LPG_UNIFIED_MAX_CHUNKS`` — safety cap per plant per kind per run (default ``500``).
* ``LPG_UNIFIED_START_TS`` — ISO timestamp only when nothing else defines a resume
  point (default ``2025-08-01T00:00:00``).
* ``LPG_UNIFIED_ALWAYS_DEDUPE`` — if ``1``/``true``, query APP_DB for existing ids on
  every chunk (slower; use if another writer may insert overlapping rows). Default is
  to dedupe only when the resume point comes from legacy/default seeding.
* ``LPG_UNIFIED_SKIP_APP_MAX_SEED`` — if ``1``/``true``, never run the expensive
  ``ORDER BY process_date DESC … LIMIT 1`` scan on APP_DB for resume (use when every
  plant already has a unified or legacy extraction row).
* ``LPG_MAX_WORKERS`` — thread pool size (default ``10``, same scale as legacy sync).
* ``LPG_UNIFIED_SKIP_EXTRA_COL_DDL`` — if ``1``/``true``, do not run ``ALTER TABLE`` for
  ``plan_id`` / ``plant_id`` / ``time_stamp`` (use if columns are already created).
* ``LPG_UNIFIED_DDL_LOCK_TIMEOUT_MS`` — max wait for table locks during ``ADD COLUMN``
  (default ``30000``). Prevents indefinite hangs when the log table is busy.
* ``LPG_UNIFIED_VERBOSE_PLANT_SQL`` — if ``1``/``true``, print full plant SQL and
  per-chunk fetch noise from ``fetch_data`` (default off to reduce I/O and log volume).
* ``LPG_UNIFIED_DEDUPE_ANY_BATCH`` — max ids per APP_DB dedupe probe (default ``12000``).
  Dedupe uses ``= ANY(ARRAY[...]::bigint[])`` plus a composite index on ``(sap_id, *_id)``
  instead of huge ``IN (...)`` lists (lower planner/CPU cost).

**Resume order** (first match wins): stored unified cursor → legacy
``lpg_*_extraction_log.last_extracted_date`` (cheap PK lookup) → only if still unknown,
max row in APP_DB for that ``sap_id`` (can be heavy on huge tables) →
``LPG_UNIFIED_START_TS``. Plant queries always use a **keyset** from that point, not a
full calendar day.

**APP_DB load:** index DDL and ``ALTER … ADD COLUMN`` run **once per process** in
``main()``; each ``COPY`` uses ``ensure_indexes=False`` so six ``CREATE INDEX IF NOT
EXISTS`` checks are not repeated on every chunk (that dominated CPU/time vs legacy).

This module is **self-contained** (no imports from ``lpg_log_daily_reconciliation_sync``).

**Final JSON report** (stdout + temp file) contains:

* ``run`` — ``started_at_utc``, ``finished_at_utc``, ``total_wall_seconds``, plant counts,
  ``totals.event_log_rows_inserted_app_db`` / ``production_log_rows_inserted_app_db``.
* ``plants`` — per plant: ``total_wall_seconds``, nested ``event_log`` and ``production_log``
  each with ``plant_fetch_seconds``, ``app_db_copy_seconds``, ``app_db_dedupe_seconds``,
  ``rows_fetched_from_plant_db``, ``rows_inserted_into_app_db``, ``success``, and on
  failure ``error_message``, ``error_stage``, ``traceback``. ``failure`` on the plant
  object summarises which stage broke.

**APP_DB CPU:** dedupe uses ``ANY(ARRAY[bigint])`` (not giant ``IN`` lists), a composite
index on ``(sap_id, event_log_id)`` / ``(sap_id, production_log_id)``, and the plant’s
open APP connection. Plant SQL echo is off by default; per-chunk ``COPY`` skips extra
logger lines. Set ``LPG_UNIFIED_VERBOSE_PLANT_SQL=1`` only when debugging.

Run::

    python -m orchestrator.sync_services.lpg.lpg_unified_log_sync
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import datetime as dt
import json
import os
import socket
import time
import sys
import tempfile
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
import pandas as pd
import polars as pl
import psycopg2
import urdhva_base

sys.path.append("/opt/ceg/algo")
import hpcl_ceg_model
import orchestrator.dbconnector.credential_loader as credential_loader

logger = urdhva_base.logger.Logger.getInstance("lpg_unified_log_sync")


def _sync_print(msg: str) -> None:
    """Human-readable progress line for operators (always flushed)."""
    print(f"[LPG-SYNC] {msg}", flush=True)


_DTYPE_MAP = {
    "String": "text",
    "Int64": "bigint",
    "Int32": "bigint",
    "Boolean": "text",
    "Float64": "double precision",
    "Float32": "double precision",
    "Object": "text",
    "Datetime": "timestamp",
    "Date": "date",
    "Utf8": "text",
    "Datetime(time_unit='us', time_zone=None)": "timestamp",
    "Datetime(time_unit='ns', time_zone=None)": "timestamp",
}

EVENT_PG_TABLE = "event_log"
EVENT_MYSQL_TABLE = "gd_pt_data"
PROD_PG_TABLE = "production_log"
PROD_MYSQL_TABLE = "production_data"
EVENT_ID_COL = "event_log_id"
PROD_ID_COL = "production_log_id"

CURSOR_TABLE = "lpg_unified_sync_cursor"
TABLE_EXTRACTION_EVENT = "lpg_eventlog_extraction_log"
TABLE_EXTRACTION_PRODUCTION = "lpg_plant_extraction_log"
LogKind = str  # "event" | "production"
ResumeSource = str  # "unified" | "app_max" | "legacy" | "default"


def _app_db_connect():
    creds = credential_loader.get_credentials("APP_DB")
    return psycopg2.connect(
        host=creds["host"],
        database=creds["database"],
        user=creds["user"],
        password=creds["password"],
        port=int(creds["port"]),
        connect_timeout=20,
    )


def _strip_utf8_nulls(data: pl.DataFrame) -> pl.DataFrame:
    out = data
    for col in out.columns:
        if out[col].dtype == pl.Utf8:
            out = out.with_columns(pl.col(col).str.replace_all("\x00", "").alias(col))
    return out


def ensure_lpg_app_log_indexes(conn, table_name: str) -> None:
    cur = conn.cursor()
    try:
        idx_statements = [
            f'CREATE INDEX IF NOT EXISTS "{table_name}_sap_id_index" ON "{table_name}" ("sap_id")',
            f'CREATE INDEX IF NOT EXISTS "{table_name}_pdate_index" ON "{table_name}" ("pdate")',
            f'CREATE INDEX IF NOT EXISTS "{table_name}_system_id_index" ON "{table_name}" ("system_id")',
            f'CREATE INDEX IF NOT EXISTS "{table_name}_process_id_index" ON "{table_name}" ("process_id")',
            f'CREATE INDEX IF NOT EXISTS "{table_name}_process_status_index" ON "{table_name}" ("process_status")',
            f'CREATE INDEX IF NOT EXISTS "{table_name}_cyl_type_index" ON "{table_name}" ("cyl_type")',
        ]
        # Speeds up dedupe probes: WHERE sap_id = ? AND <id> = ANY(array) / IN (...)
        if table_name == EVENT_PG_TABLE:
            idx_statements.append(
                f'CREATE INDEX IF NOT EXISTS "{table_name}_sap_{EVENT_ID_COL}_idx" '
                f'ON "{table_name}" ("sap_id", "{EVENT_ID_COL}")'
            )
        elif table_name == PROD_PG_TABLE:
            idx_statements.append(
                f'CREATE INDEX IF NOT EXISTS "{table_name}_sap_{PROD_ID_COL}_idx" '
                f'ON "{table_name}" ("sap_id", "{PROD_ID_COL}")'
            )
        for idx_sql in idx_statements:
            try:
                cur.execute(idx_sql)
            except Exception:
                pass
        conn.commit()
    finally:
        cur.close()


def copy_dataframe_to_app_table(
    data: pl.DataFrame,
    table_name: str,
    batch_size: int = 50_000,
    *,
    ensure_indexes: bool = True,
    log_rowcount: bool = True,
) -> None:
    if data.is_empty():
        if log_rowcount:
            logger.info("copy_dataframe_to_app_table: empty frame, skip")
        return

    data = _strip_utf8_nulls(data)
    creds = credential_loader.get_credentials("APP_DB")
    conn = psycopg2.connect(
        host=creds["host"],
        database=creds["database"],
        user=creds["user"],
        password=creds["password"],
        port=int(creds["port"]),
        connect_timeout=30,
    )
    cur = conn.cursor()
    try:
        parts: List[str] = []
        for col in data.columns:
            dt_name = _DTYPE_MAP.get(str(data[col].dtype))
            if not dt_name:
                dt_name = "text"
            parts.append(f'"{col}" {dt_name}')
        ddl = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({",".join(parts)})'
        cur.execute(ddl)
        if ensure_indexes:
            ensure_lpg_app_log_indexes(conn, table_name)
        else:
            conn.commit()

        cur.execute(f'SELECT * FROM "{table_name}" LIMIT 1')
        existing_cols = [d[0] for d in cur.description]
        aligned = data
        for c in existing_cols:
            if c not in aligned.columns:
                aligned = aligned.with_columns(pl.lit(None).alias(c))
        aligned = aligned.select(existing_cols)

        copy_sql = f'COPY "{table_name}" FROM STDIN CSV HEADER DELIMITER \'~\''
        n = len(aligned)
        for start in range(0, n, batch_size):
            chunk = aligned.slice(start, min(batch_size, n - start))
            with tempfile.NamedTemporaryFile(
                mode="w+",
                suffix=".csv",
                delete=False,
                encoding="utf-8",
            ) as tmp:
                path = tmp.name
            try:
                chunk.write_csv(path, separator="~")
                with open(path, "r", encoding="utf-8") as fh:
                    cur.copy_expert(copy_sql, fh)
                conn.commit()
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass

        if log_rowcount:
            logger.info('COPY completed for "%s" (%s rows)', table_name, n)
    finally:
        cur.close()
        conn.close()


def fetch_data(
    query: str,
    *,
    getData: bool = False,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
    query_timeout: int = 30,
    chunk_size: int = 50000,
    verbose: bool = False,
):
    """Fetch from plant MySQL or PostgreSQL (socket check, timeouts, optional LIMIT/OFFSET chunks)."""
    if params is None:
        return pl.DataFrame() if getData else None
    query = query.replace(";", "")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((params["host"], int(params["port"])))
        if not result == 0:
            logger.error(
                "Connection timed out to %s:%s after %ss",
                params["host"],
                params["port"],
                timeout,
            )
            print(
                f"Connection timed out to {params['host']}:{params['port']} after {timeout} seconds"
            )
            return pl.DataFrame() if getData else None
    except Exception as e:
        logger.error("Socket connection error: %s", e)
        print(f"Socket connection error: {str(e)}")
        return pl.DataFrame() if getData else None
    finally:
        sock.close()

    try:
        if str(params.get("db_type", "")).lower() == "mysql":
            pg_conn = mysql.connector.connect(
                host=params["host"],
                database=params["database"],
                user=params["user"],
                password=params["password"],
                port=int(params["port"]),
                connection_timeout=timeout,
            )
            cursor = pg_conn.cursor()
            cursor.execute(
                f"SET SESSION max_execution_time = {query_timeout * 1000};"
            )
        else:
            pg_conn = psycopg2.connect(
                host=params["host"],
                database=params["database"],
                user=params["user"],
                password=params["password"],
                port=params["port"],
                connect_timeout=timeout,
            )
            pg_conn.set_session(autocommit=True)
            cursor = pg_conn.cursor()
            cursor.execute(f"SET statement_timeout = {query_timeout * 1000};")

    except Exception as e:
        logger.error(
            "Database connection error for %s: %s",
            params.get("PlantName", "unknown"),
            e,
        )
        print(
            f"Database connection error for {params.get('PlantName', 'unknown')}: {str(e)}"
        )
        return pl.DataFrame() if getData else None

    try:
        if verbose:
            print("-" * 50, flush=True)
            print(f"Running Query with {query_timeout}s timeout...", flush=True)
            print(query, flush=True)

        if not getData:
            cursor.execute(query)
            resp = cursor.fetchone()
            cursor.close()
            pg_conn.close()
            return resp[0] if resp else None
        if "LIMIT" not in query.upper():
            base_query = query.rstrip(";")
            base_query += f" LIMIT {chunk_size} OFFSET "
        else:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [column[0] for column in cursor.description]
            data = pd.DataFrame.from_records(data, columns=columns)
            data = pl.from_pandas(data)
            cursor.close()
            pg_conn.close()
            return data

        all_data = []
        offset = 0
        columns = []
        while True:
            chunk_query = f"{base_query} {offset};"
            cursor.execute(chunk_query)
            chunk_data = cursor.fetchall()

            if not chunk_data:
                break

            if verbose:
                print(f"Retrieved {len(chunk_data)} records in this chunk", flush=True)
            if not all_data:
                columns = [column[0] for column in cursor.description]

            all_data.extend(chunk_data)
            offset += chunk_size

            if len(chunk_data) < chunk_size:
                break

            if offset > 2000000:
                if verbose:
                    print("Reached maximum record limit (1M)", flush=True)
                break

        if verbose:
            print(f"Total Records: {len(all_data)}", flush=True)
            print("-" * 50, flush=True)

        if all_data:
            data = pd.DataFrame.from_records(all_data, columns=columns)
            data = pl.from_pandas(data)
            cursor.close()
            pg_conn.close()
            return data
        cursor.close()
        pg_conn.close()
        return pl.DataFrame()

    except psycopg2.errors.QueryCanceled:
        logger.error(
            "Query timed out after %s seconds - skipping this plant", query_timeout
        )
        print(f"Query timed out after {query_timeout} seconds - skipping this plant")
        cursor.close()
        pg_conn.close()
        return pl.DataFrame() if getData else None
    except Exception as e:
        logger.error("Query execution error: %s", e)
        print(f"Query execution error: {str(e)}")
        cursor.close()
        pg_conn.close()
        return pl.DataFrame() if getData else None


def ensure_cursor_table() -> None:
    conn = _app_db_connect()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {CURSOR_TABLE} (
                plant_name VARCHAR(255) NOT NULL,
                log_kind VARCHAR(32) NOT NULL,
                last_process_date TIMESTAMP NULL,
                last_source_id BIGINT NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (plant_name, log_kind)
            );
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _columns_present_in_public(conn, table: str) -> set:
    """Lowercase column names for ``public.<table>`` (unquoted physical name)."""
    rel = table.replace('"', "").lower()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT a.attname
            FROM pg_catalog.pg_attribute a
            INNER JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
            INNER JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = %s
              AND a.attnum > 0
              AND NOT a.attisdropped
            """,
            (rel,),
        )
        return {str(r[0]).lower() for r in cur.fetchall()}
    finally:
        cur.close()


def ensure_log_extra_columns_conn(conn, table: str) -> None:
    """
    Add ``plan_id`` / ``plant_id`` / ``time_stamp`` only when missing, so routine runs
    do not take ``ALTER`` locks on huge busy tables. Uses ``lock_timeout`` so a
    contended table does not block the whole sync indefinitely.
    """
    if os.environ.get("LPG_UNIFIED_SKIP_EXTRA_COL_DDL", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        logger.info(
            'Skipping extra-column DDL for "%s" (LPG_UNIFIED_SKIP_EXTRA_COL_DDL)',
            table,
        )
        return

    want = ("plan_id", "plant_id", "time_stamp")
    present = _columns_present_in_public(conn, table)
    missing = [c for c in want if c.lower() not in present]
    if not missing:
        logger.info('Extra columns already on "%s"; skipping ALTER', table)
        return

    lock_ms = int(os.environ.get("LPG_UNIFIED_DDL_LOCK_TIMEOUT_MS", "30000"))
    lock_ms = max(1000, min(lock_ms, 600_000))
    ddls = {
        "plan_id": f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS plan_id BIGINT',
        "plant_id": f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS plant_id BIGINT',
        "time_stamp": (
            f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS time_stamp TIMESTAMPTZ'
        ),
    }

    for col in missing:
        cur = conn.cursor()
        try:
            cur.execute("SET lock_timeout TO %s", (f"{lock_ms}ms",))
            cur.execute(ddls[col])
            logger.info('ADD COLUMN %s on "%s" (if not already present)', col, table)
        except psycopg2.errors.LockNotAvailable:
            logger.warning(
                'Lock wait timed out adding %s on "%s" (table busy). '
                "Skip or retry later; set LPG_UNIFIED_DDL_LOCK_TIMEOUT_MS to wait longer.",
                col,
                table,
            )
            conn.rollback()
        except psycopg2.Error as exc:
            logger.warning(
                'Could not add column %s on "%s": %s', col, table, exc.pgerror or exc
            )
            conn.rollback()
        else:
            conn.commit()
        finally:
            cur.close()


def _legacy_extraction_table(kind: LogKind) -> str:
    return (
        TABLE_EXTRACTION_EVENT if kind == "event" else TABLE_EXTRACTION_PRODUCTION
    )


def get_resume_cursor_conn(
    conn,
    plant_name: str,
    kind: LogKind,
    sap_id: str,
    app_table: str,
    id_col: str,
) -> Tuple[dt.datetime, int, ResumeSource]:
    """
    Resume point for plant-server keyset fetch. Uses one transaction/connection to avoid
    extra round-trips. Legacy extraction is checked **before** the heavy APP_DB max row
    query so routine runs avoid sorting large ``event_log`` / ``production_log`` tables.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT last_process_date, last_source_id
            FROM {CURSOR_TABLE}
            WHERE plant_name = %s AND log_kind = %s
            """,
            (plant_name, kind),
        )
        row = cur.fetchone()
        if row and row[0] is not None:
            return pd.Timestamp(row[0]).to_pydatetime(), int(row[1] or 0), "unified"

        leg_table = _legacy_extraction_table(kind)
        try:
            cur.execute(
                f"SELECT last_extracted_date FROM {leg_table} WHERE plant_name = %s",
                (plant_name,),
            )
            leg = cur.fetchone()
            if leg and leg[0] is not None:
                return pd.Timestamp(leg[0]).to_pydatetime(), -1, "legacy"
        except Exception:
            pass

        if os.environ.get("LPG_UNIFIED_SKIP_APP_MAX_SEED", "").lower() not in (
            "1",
            "true",
            "yes",
        ):
            try:
                cur.execute(
                    f"""
                    SELECT process_date, "{id_col}"
                    FROM "{app_table}"
                    WHERE sap_id = %s
                    ORDER BY process_date DESC NULLS LAST, "{id_col}" DESC NULLS LAST
                    LIMIT 1
                    """,
                    (str(sap_id),),
                )
                app = cur.fetchone()
                if app and app[0] is not None and app[1] is not None:
                    return pd.Timestamp(app[0]).to_pydatetime(), int(app[1]), "app_max"
            except Exception:
                pass

        return _default_start_ts(), 0, "default"
    finally:
        cur.close()


def _set_cursor_conn(
    conn,
    plant_name: str,
    kind: LogKind,
    last_ts: Optional[dt.datetime],
    last_id: int,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            INSERT INTO {CURSOR_TABLE}
                (plant_name, log_kind, last_process_date, last_source_id, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (plant_name, log_kind) DO UPDATE SET
                last_process_date = EXCLUDED.last_process_date,
                last_source_id = EXCLUDED.last_source_id,
                updated_at = NOW()
            """,
            (plant_name, kind, last_ts, int(last_id)),
        )
        conn.commit()
    finally:
        cur.close()


def _default_start_ts() -> dt.datetime:
    raw = os.environ.get("LPG_UNIFIED_START_TS", "").strip()
    if raw:
        return pd.Timestamp(raw).to_pydatetime()
    return dt.datetime(2025, 8, 1, 0, 0, 0)


def _source_table(db_type: str, kind: LogKind) -> str:
    is_mysql = str(db_type).lower() == "mysql"
    if kind == "event":
        return EVENT_MYSQL_TABLE if is_mysql else EVENT_PG_TABLE
    return PROD_MYSQL_TABLE if is_mysql else PROD_PG_TABLE


def _id_col(kind: LogKind) -> str:
    return EVENT_ID_COL if kind == "event" else PROD_ID_COL


def _app_table(kind: LogKind) -> str:
    return EVENT_PG_TABLE if kind == "event" else PROD_PG_TABLE


def _build_keyset_query(
    *,
    source_table: str,
    id_col: str,
    cursor_ts: dt.datetime,
    cursor_id: int,
    limit: int,
    db_type: str,
) -> str:
    """Single-chunk query (LIMIT in query → fetch_data returns one DataFrame, no OFFSET)."""
    is_mysql = str(db_type).lower() == "mysql"
    ts_sql = cursor_ts.strftime("%Y-%m-%d %H:%M:%S")
    lim = int(limit)
    if is_mysql:
        return f"""
            SELECT * FROM {source_table}
            WHERE process_date < NOW()
              AND process_date >= '{ts_sql}'
            ORDER BY process_date ASC, {id_col} ASC
            LIMIT {lim}
        """
    return f"""
        SELECT * FROM {source_table}
        WHERE process_date < NOW()
          AND process_date >= '{ts_sql}'
        ORDER BY process_date ASC, {id_col} ASC
        LIMIT {lim}
    """


def _enrich_frame(
    data: pl.DataFrame,
    *,
    plant_name: str,
    sap_id: Any,
    erp_id: Any,
    plant_row_id: Any,
) -> pl.DataFrame:
    if data.is_empty():
        return data
    plan_id = int(erp_id) if erp_id is not None and str(erp_id).strip() != "" else None
    plant_id = int(plant_row_id) if plant_row_id is not None else None
    out = data.with_columns(pl.lit(plant_name).alias("Plant Name"))
    out = out.with_columns(pl.lit(str(sap_id)).alias("sap_id"))
    if "process_date" in out.columns:
        out = out.with_columns(pl.col("process_date").cast(pl.Date).alias("pdate"))
        # Full-resolution event time for analytics (mirrors process_date; APP_DB column timestamptz).
        out = out.with_columns(pl.col("process_date").alias("time_stamp"))
    else:
        out = out.with_columns(pl.lit(None).alias("pdate"))
        out = out.with_columns(pl.lit(None).alias("time_stamp"))
    out = out.with_columns(pl.lit(plan_id).alias("plan_id"))
    out = out.with_columns(pl.lit(plant_id).alias("plant_id"))
    return out


def _bigint_array_sql_literal(ids: List[int]) -> str:
    """
    Build ``ARRAY[...]::bigint[]`` from validated integers only (no string concat from
    untrusted input). Used with ``= ANY(...)`` instead of huge ``IN (...)`` lists, which
    are expensive for the planner and CPU on large ``event_log`` / ``production_log`` tables.
    """
    if not ids:
        return "ARRAY[]::bigint[]"
    return "ARRAY[" + ",".join(str(int(x)) for x in ids) + "]::bigint[]"


def _existing_source_ids(
    app_table: str,
    id_col: str,
    sap_id: str,
    ids: List[Any],
    app_conn=None,
) -> set:
    if not ids:
        return set()
    own_conn = app_conn is None
    conn = app_conn if app_conn is not None else _app_db_connect()
    cur = conn.cursor()
    found: set = set()
    # One array per round-trip; cap literal size (~12k ids keeps SQL under ~150KB).
    batch = int(os.environ.get("LPG_UNIFIED_DEDUPE_ANY_BATCH", "12000"))
    batch = max(500, min(batch, 50_000))
    try:
        for i in range(0, len(ids), batch):
            part = [int(x) for x in ids[i : i + batch]]
            arr = _bigint_array_sql_literal(part)
            cur.execute(
                f"""
                SELECT "{id_col}", process_date FROM "{app_table}"
                WHERE sap_id = %s AND "{id_col}" = ANY({arr})
                """,
                (str(sap_id),),
            )
            for row in cur.fetchall():
                if row[0] is not None:
                    pdt = pd.Timestamp(row[1]) if row[1] is not None else None
                    found.add((int(row[0]), pdt))
        return found
    finally:
        cur.close()
        if own_conn:
            conn.close()


def _filter_new_rows(
    data: pl.DataFrame,
    *,
    app_table: str,
    id_col: str,
    sap_id: str,
    app_conn=None,
) -> pl.DataFrame:
    if data.is_empty() or id_col not in data.columns:
        return data
    ids_series = data[id_col].drop_nulls()
    ids = [int(x) for x in ids_series.to_list()]
    if not ids:
        return data.head(0)
    have = _existing_source_ids(
        app_table, id_col, sap_id, ids, app_conn=app_conn
    )
    if not have:
        return data
    keep: List[bool] = []
    for row in data.iter_rows(named=True):
        rid = row.get(id_col)
        pdt = row.get("process_date")
        if rid is None:
            keep.append(True)
            continue
        key = (int(rid), pd.Timestamp(pdt) if pdt is not None else None)
        keep.append(key not in have)
    return data.filter(pl.Series("_keep", keep))


def _tail_cursor(data: pl.DataFrame, id_col: str) -> Tuple[Optional[dt.datetime], int]:
    if data.is_empty():
        return None, 0
    last = data.tail(1)
    ts = last["process_date"][0]
    rid = last[id_col][0]
    if ts is None or rid is None:
        return None, 0
    ts_py = pd.Timestamp(ts).to_pydatetime()
    return ts_py, int(rid)


def _kind_label(kind: LogKind) -> str:
    return "event_log" if kind == "event" else "production_log"


def sync_one_kind(
    params: Dict[str, Any],
    *,
    plant_row: Dict[str, Any],
    kind: LogKind,
    chunk_size: int,
    max_chunks: int,
    app_conn,
) -> Dict[str, Any]:
    plant_name = params["PlantName"]
    sap_s = str(params["sap_id"])
    id_col = _id_col(kind)
    app_table = _app_table(kind)
    source_table = _source_table(params["db_type"], kind)
    label = _kind_label(kind)
    sql_verbose = os.environ.get("LPG_UNIFIED_VERBOSE_PLANT_SQL", "").lower() in (
        "1",
        "true",
        "yes",
    )

    t_kind_start = time.perf_counter()
    sec_fetch = 0.0
    sec_copy = 0.0
    sec_dedupe = 0.0
    rows_fetched = 0
    rows_inserted = 0

    cur_ts, cur_id, resume_src = get_resume_cursor_conn(
        app_conn, plant_name, kind, sap_s, app_table, id_col
    )

    #fetching before 1 hr of last extracted date
    cur_ts = (cur_ts - dt.timedelta(hours=1)).replace(minute=0,second=0,microsecond=0,)

    always_dedupe = os.environ.get("LPG_UNIFIED_ALWAYS_DEDUPE", "").lower() in (
        "1",
        "true",
        "yes",
    )
    dedupe_chunks = always_dedupe or resume_src in ("legacy", "default")

    _sync_print(
        f"{plant_name} | {label}: starting (resume={resume_src}, "
        f"cursor_ts={cur_ts}, cursor_id={cur_id}, dedupe_against_app_db={dedupe_chunks})"
    )
    logger.info(
        "[%s %s] resume=%s cursor=(%s, %s) dedupe=%s",
        plant_name,
        kind,
        resume_src,
        cur_ts,
        cur_id,
        dedupe_chunks,
    )

    def _fail(
        *,
        message: str,
        stage: str,
        chunks_done: int,
        exc: Optional[BaseException] = None,
    ) -> Dict[str, Any]:
        elapsed = round(time.perf_counter() - t_kind_start, 3)
        out = {
            "kind": kind,
            "log_table": label,
            "ok": False,
            "success": False,
            "error_message": message,
            "error_stage": stage,
            "plant_fetch_seconds": round(sec_fetch, 3),
            "app_db_dedupe_seconds": round(sec_dedupe, 3),
            "app_db_copy_seconds": round(sec_copy, 3),
            "wall_seconds_total": elapsed,
            "rows_fetched_from_plant_db": rows_fetched,
            "rows_inserted_into_app_db": rows_inserted,
            "chunks_processed": chunks_done,
            "resume_source": resume_src,
            "dedupe_each_chunk": dedupe_chunks,
        }
        if exc is not None:
            out["exception_type"] = type(exc).__name__
            out["traceback"] = traceback.format_exc()
        _sync_print(
            f"{plant_name} | {label}: FAILED after {elapsed}s — stage={stage}: {message}"
        )
        return out

    chunks = 0

    while chunks < max_chunks:
        query = _build_keyset_query(
            source_table=source_table,
            id_col=id_col,
            cursor_ts=cur_ts,
            cursor_id=cur_id,
            limit=chunk_size,
            db_type=params["db_type"],
        )
        _sync_print(
            f"{plant_name} | {label}: chunk {chunks + 1}/{max_chunks} — "
            f"fetching up to {chunk_size} rows from plant DB ({source_table})…"
        )
        t_fetch = time.perf_counter()
        chunk = fetch_data(
            query,
            getData=True,
            params=params,
            timeout=15,
            query_timeout=240,
            chunk_size=chunk_size,
            verbose=sql_verbose,
        )
        dt_fetch = time.perf_counter() - t_fetch
        sec_fetch += dt_fetch
        if chunk is None:
            chunk = pl.DataFrame()
        n = len(chunk)
        rows_fetched += n
        chunks += 1
        _sync_print(
            f"{plant_name} | {label}: chunk {chunks} — received {n} rows from plant "
            f"(this fetch: {dt_fetch:.2f}s)"
        )

        if chunk.is_empty():
            _sync_print(
                f"{plant_name} | {label}: no more rows from plant (empty chunk). "
                f"Totals: fetched={rows_fetched}, inserted={rows_inserted}, "
                f"fetch={sec_fetch:.2f}s, copy={sec_copy:.2f}s, dedupe={sec_dedupe:.2f}s"
            )
            break

        if id_col not in chunk.columns:
            logger.error("[%s %s] server result missing %s", plant_name, kind, id_col)
            return _fail(
                message=f"Plant data has no column {id_col!r}",
                stage="validate_plant_columns",
                chunks_done=chunks,
            )

        tail_ts, tail_id = _tail_cursor(chunk, id_col)
        enriched = _enrich_frame(
            chunk,
            plant_name=plant_name,
            sap_id=params["sap_id"],
            erp_id=plant_row.get("erp_id"),
            plant_row_id=plant_row.get("id"),
        )
        if dedupe_chunks:
            t0 = time.perf_counter()
            to_insert = _filter_new_rows(
                enriched,
                app_table=app_table,
                id_col=id_col,
                sap_id=sap_s,
                app_conn=app_conn,
            )
            sec_dedupe += time.perf_counter() - t0
        else:
            to_insert = enriched

        if not to_insert.is_empty():
            _sync_print(
                f"{plant_name} | {label}: inserting {len(to_insert)} rows into APP_DB "
                f'table "{app_table}"…'
            )
            try:
                t0 = time.perf_counter()
                copy_dataframe_to_app_table(
                    to_insert,
                    app_table,
                    ensure_indexes=False,
                    log_rowcount=False,
                )
                sec_copy += time.perf_counter() - t0
                rows_inserted += len(to_insert)
            except Exception as exc:
                logger.exception(
                    "COPY failed plant=%s kind=%s: %s", plant_name, kind, exc
                )
                return _fail(
                    message=str(exc),
                    stage="copy_to_app_db",
                    chunks_done=chunks,
                    exc=exc,
                )
        else:
            _sync_print(
                f"{plant_name} | {label}: chunk {chunks} — all rows already in APP_DB "
                "(dedupe); cursor still advanced"
            )

        # cur_ts, cur_id = tail_ts, tail_id
        # _set_cursor_conn(app_conn, plant_name, kind, cur_ts, cur_id)
        
        # update cursor ONLY after successful insert
        if not to_insert.is_empty():
            cur_ts, cur_id = _tail_cursor(to_insert, id_col,)
            _set_cursor_conn(app_conn, plant_name, kind, cur_ts, cur_id)

        if len(chunk) < chunk_size:
            _sync_print(
                f"{plant_name} | {label}: last page (< {chunk_size} rows). "
                f"Totals: fetched={rows_fetched}, inserted={rows_inserted}"
            )
            break

    elapsed = round(time.perf_counter() - t_kind_start, 3)
    _sync_print(
        f"{plant_name} | {label}: OK in {elapsed}s — "
        f"fetched={rows_fetched}, inserted={rows_inserted}, "
        f"plant_fetch={sec_fetch:.2f}s, app_copy={sec_copy:.2f}s, app_dedupe={sec_dedupe:.2f}s"
    )
    return {
        "kind": kind,
        "log_table": label,
        "ok": True,
        "success": True,
        "error_message": None,
        "error_stage": None,
        "plant_fetch_seconds": round(sec_fetch, 3),
        "app_db_dedupe_seconds": round(sec_dedupe, 3),
        "app_db_copy_seconds": round(sec_copy, 3),
        "wall_seconds_total": elapsed,
        "rows_fetched_from_plant_db": rows_fetched,
        "rows_inserted_into_app_db": rows_inserted,
        "chunks_processed": chunks,
        "resume_source": resume_src,
        "dedupe_each_chunk": dedupe_chunks,
    }


def process_plant(plant_row: Dict[str, Any]) -> Dict[str, Any]:
    wall0 = time.perf_counter()
    params = {
        "PlantName": plant_row["PlantName"],
        "host": plant_row["host_ip"],
        "database": plant_row["db_database"],
        "user": plant_row["db_user"],
        "password": plant_row["db_password"],
        "port": plant_row["port"],
        "db_type": plant_row["db_type"],
        "sap_id": plant_row["erp_id"],
    }
    chunk_size = int(os.environ.get("LPG_UNIFIED_CHUNK_SIZE", "25000"))
    max_chunks = int(os.environ.get("LPG_UNIFIED_MAX_CHUNKS", "500"))

    out: Dict[str, Any] = {
        "plant_name": params["PlantName"],
        "csv_plant_id": plant_row.get("id"),
        "sap_id": str(params["sap_id"]),
        "host_ip": params["host"],
        "db_database": params["database"],
        "db_type": params["db_type"],
        "success": False,
        "total_wall_seconds": 0.0,
        "event_log": {},
        "production_log": {},
        "failure": None,
        "chunk_size": chunk_size,
        "max_chunks_per_kind": max_chunks,
    }

    _sync_print(
        f"=== Plant START: {params['PlantName']} | sap_id={params['sap_id']} | "
        f"host={params['host']} | chunk_size={chunk_size} max_chunks/kind={max_chunks} ==="
    )

    app_conn = None
    try:
        app_conn = _app_db_connect()
        ev = sync_one_kind(
            params,
            plant_row=plant_row,
            kind="event",
            chunk_size=chunk_size,
            max_chunks=max_chunks,
            app_conn=app_conn,
        )
        out["event_log"] = ev
        if not ev.get("ok", False):
            out["failure"] = {
                "where": "event_log",
                "error_message": ev.get("error_message"),
                "error_stage": ev.get("error_stage"),
                "exception_type": ev.get("exception_type"),
                "traceback": ev.get("traceback"),
            }
            out["total_wall_seconds"] = round(time.perf_counter() - wall0, 3)
            _sync_print(
                f"=== Plant END (FAILED): {params['PlantName']} — event_log failed in "
                f"{out['total_wall_seconds']}s ==="
            )
            return out

        pr = sync_one_kind(
            params,
            plant_row=plant_row,
            kind="production",
            chunk_size=chunk_size,
            max_chunks=max_chunks,
            app_conn=app_conn,
        )
        out["production_log"] = pr
        if not pr.get("ok", False):
            out["failure"] = {
                "where": "production_log",
                "error_message": pr.get("error_message"),
                "error_stage": pr.get("error_stage"),
                "exception_type": pr.get("exception_type"),
                "traceback": pr.get("traceback"),
            }
            out["total_wall_seconds"] = round(time.perf_counter() - wall0, 3)
            _sync_print(
                f"=== Plant END (FAILED): {params['PlantName']} — production_log failed in "
                f"{out['total_wall_seconds']}s ==="
            )
            return out

        out["success"] = True
        out["total_wall_seconds"] = round(time.perf_counter() - wall0, 3)
        _sync_print(
            f"=== Plant END (OK): {params['PlantName']} in {out['total_wall_seconds']}s | "
            f"event: fetched={ev.get('rows_fetched_from_plant_db')} inserted="
            f"{ev.get('rows_inserted_into_app_db')} ({ev.get('wall_seconds_total')}s in log sync) | "
            f"production: fetched={pr.get('rows_fetched_from_plant_db')} inserted="
            f"{pr.get('rows_inserted_into_app_db')} ({pr.get('wall_seconds_total')}s in log sync) ==="
        )
    except Exception as exc:
        logger.exception("process_plant failed: %s", exc)
        out["success"] = False
        out["failure"] = {
            "where": "process_plant_unhandled",
            "error_message": str(exc),
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
        }
        out["total_wall_seconds"] = round(time.perf_counter() - wall0, 3)
        _sync_print(
            f"=== Plant END (FAILED): {params['PlantName']} — unhandled error in "
            f"{out['total_wall_seconds']}s: {exc} ==="
        )
    finally:
        if app_conn is not None:
            try:
                app_conn.close()
            except Exception:
                pass
    return out


def main() -> None:
    run_wall0 = time.perf_counter()
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()

    query = """
        SELECT id, sap_id, plant_name, ip_address, port_no, username, password,
               db_name, db_type, zone, region
        FROM lpg_plants_master
        ORDER BY id ASC
    """
    result = asyncio.run(hpcl_ceg_model.LpgPlantsMaster.get_aggr_data(query=query, limit=0))
    rows = result.get("data", []) if result else []
    if not rows:
        raise RuntimeError("No rows found in lpg_plants_master")
    for row in rows:
        if str(row["password"]).startswith("enc#_"):
            row["password"] = urdhva_base.types.Secret(row["password"]).get_secret()

        row["erp_id"] = row.get("sap_id")
        row["PlantName"] = row.get("plant_name")
        row["host_ip"] = row.get("ip_address")
        row["port"] = row.get("port_no")
        row["db_user"] = row.get("username")
        row["db_password"] = row.get("password")
        row["db_database"] = row.get("db_name")
        row["SiteRegion"] = row.get("region")
    plants = pl.from_dicts(rows)
    max_workers = max(1, min(int(os.environ.get("LPG_MAX_WORKERS", "10")), len(plants)))
    n_plants = len(plants)

    _sync_print(
        f"RUN START | UTC {started_at} | plants={n_plants} | workers={max_workers} | "
        "source=lpg_plants_master"
    )

    _sync_print("Step 1/3: Ensuring unified cursor table on APP_DB…")
    ensure_cursor_table()
    _sync_print("Step 1/3: Done (lpg_unified_sync_cursor).")

    _sync_print(
        "Step 2/3: Ensuring extra columns + standard indexes on APP_DB "
        f'("{EVENT_PG_TABLE}", "{PROD_PG_TABLE}")…'
    )
    setup = _app_db_connect()
    try:
        ensure_log_extra_columns_conn(setup, EVENT_PG_TABLE)
        ensure_log_extra_columns_conn(setup, PROD_PG_TABLE)
        ensure_lpg_app_log_indexes(setup, EVENT_PG_TABLE)
        ensure_lpg_app_log_indexes(setup, PROD_PG_TABLE)
    finally:
        setup.close()
    _sync_print("Step 2/3: Done.")

    logger.info(
        "LPG unified sync: source=lpg_plants_master workers=%s chunk=%s",
        max_workers,
        os.environ.get("LPG_UNIFIED_CHUNK_SIZE", "25000"),
    )

    _sync_print(
        f"Step 3/3: Syncing all plants (parallel pool size={max_workers}) — "
        "watch per-plant lines below…"
    )
    results: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [
            ex.submit(process_plant, dict(row)) for row in plants.iter_rows(named=True)
        ]
        for fut in concurrent.futures.as_completed(futs):
            results.append(fut.result())

    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    total_run_s = round(time.perf_counter() - run_wall0, 3)
    ok_n = sum(1 for r in results if r.get("success"))
    fail_n = n_plants - ok_n
    ev_rows = sum(
        int(r.get("event_log", {}).get("rows_inserted_into_app_db") or 0) for r in results
    )
    pr_rows = sum(
        int(r.get("production_log", {}).get("rows_inserted_into_app_db") or 0)
        for r in results
    )

    report: Dict[str, Any] = {
        "run": {
            "started_at_utc": started_at,
            "finished_at_utc": finished_at,
            "total_wall_seconds": total_run_s,
            "plants_in_db": n_plants,
            "plants_succeeded": ok_n,
            "plants_failed": fail_n,
            "max_workers": max_workers,
            "plants_source": "lpg_plants_master",
            "totals": {
                "event_log_rows_inserted_app_db": ev_rows,
                "production_log_rows_inserted_app_db": pr_rows,
            },
        },
        "plants": results,
    }

    summary_path = Path(tempfile.gettempdir()) / f"lpg_unified_sync_{uuid.uuid4().hex[:10]}.json"
    summary_path.write_text(json.dumps(report, default=str, indent=2), encoding="utf-8")

    _sync_print(
        f"RUN END | UTC {finished_at} | total {total_run_s}s | "
        f"ok={ok_n} failed={fail_n} | "
        f"rows inserted — event_log={ev_rows}, production_log={pr_rows}"
    )
    _sync_print(f"Full JSON report written to: {summary_path}")
    logger.info("Wrote summary: %s", summary_path)
    print(json.dumps(report, default=str, indent=2), flush=True)


if __name__ == "__main__":
    _code = 0
    try:
        main()
    except KeyboardInterrupt:
        _code = 130
    except Exception:
        traceback.print_exc()
        _code = 1
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
    if _code:
        sys.exit(_code)
