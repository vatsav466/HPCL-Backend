import os
import uuid
import psycopg2
import hashlib
import polars as pl
import urdhva_base
import sys
import mysql.connector
import pandas as pd
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from psycopg2.extras import execute_values

# Add algo path for credential loader
sys.path.append("/opt/ceg/algo")
import orchestrator.dbconnector.credential_loader as credential_loader

logger = urdhva_base.logger.Logger.getInstance('tibco_sync_log')


def get_db_connection(params):
    """Establish a database connection"""
    server = params['host']
    database = params['database']
    username = params['user']
    password = params['password']
    port = params['port']

    if "connection_type" in params:
        if params["connection_type"].lower() == "postgres":
            connection = psycopg2.connect(
                host=server,
                database=database,
                user=username,
                password=password,
                port=port
            )
        elif params["connection_type"].lower() in ["mysql", "mssql"]:
            connection = mysql.connector.connect(
                host=server,
                user=username,
                passwd=password,
                port=port,
                database=database
            )
    return connection


def create_table_from_polars(pg_conn, data, table_name):
    """Automatically create Postgres table based on Polars DataFrame schema"""
    cur = pg_conn.cursor()

    sql_types = {
        pl.Int8: "SMALLINT",
        pl.Int16: "SMALLINT",
        pl.Int32: "INTEGER",
        pl.Int64: "BIGINT",
        pl.Float32: "REAL",
        pl.Float64: "DOUBLE PRECISION",
        pl.Utf8: "TEXT",
        pl.Boolean: "BOOLEAN",
        pl.Date: "DATE",
        pl.Datetime: "TIMESTAMP",
    }

    cols_def = []
    for col, dtype in data.schema.items():
        pg_type = sql_types.get(dtype, "TEXT")
        cols_def.append(f'"{col.lower()}" {pg_type}')
    if "engine_id" not in data.columns:
        cols_def.append('"engine_id" TEXT')

    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(cols_def)});'
    cur.execute(create_sql)
    pg_conn.commit()
    cur.close()
    print(f" Created table structure for '{table_name}' in Postgres.")


def insertToDB_polars(pg_conn, data, table_name):
    """Fast Polars → Postgres INSERT"""
    if data.is_empty():
        print("-- No new rows to insert --")
        return

    data = data.rename({col: col.lower() for col in data.columns})

    # Add engine_id if missing
    if "engine_id" not in data.columns:
        data = data.with_columns(
            pl.struct(data.columns).map_elements(
                lambda row: hashlib.md5("|".join(str(v) for v in row.values()).encode()).hexdigest()
            ).alias("engine_id")
        )

    # Convert float/decimal columns
    for col in data.columns:
        if data.schema[col] in [pl.Float32, pl.Float64] or 'Decimal' in str(data.schema[col]):
            data = data.with_columns(pl.col(col).cast(pl.Float64))

    cols = list(data.columns)
    col_names = ','.join(f'"{c}"' for c in cols)
    insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES %s;'

    cur = pg_conn.cursor()
    chunk_size = 50000
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size].to_pandas()
        values = [tuple(row) for row in chunk.to_numpy()]
        execute_values(cur, insert_sql, values)
        pg_conn.commit()
        print(f"Inserted chunk {i} - {i + len(chunk)}")

    cur.close()
    print(f"-- Insert complete for {table_name} --")


def get_and_insert_data(cursor, query, pg_conn, table_name, batch_size=50000):
    """Fetch source data in batches, merge with location_master, and insert into Postgres"""
    print("-" * 50)
    print("Running Query ...", query)
    cursor.execute(query)

    total_rows = 0
    all_data = []

    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        columns = [col[0] for col in cursor.description]
        data = pl.from_pandas(pd.DataFrame.from_records(rows, columns=columns))
        all_data.append(data)
        total_rows += len(data)

    if not all_data:
        print("No data fetched.")
        return

    full_data = pl.concat(all_data)
    print(f"Total rows fetched: {total_rows}")

    # --- Merge with location_master ---
    full_data = enrich_with_location_master(pg_conn, full_data)
    ITEM_NAME_MAP = {
    2812000: "HSD",
    4210000: "EBMS 15%",
    4383000: "EBMS 20% P95",
    2815000: "B5 HSD",
    2814000:"EBMS 10%",
    4211000: "EBMS 15 % P95",
    2813000: "EBMS 5%",
    2820000: "B7 HSD",
    2822000: "EBMS 20%",
    3912000: "HSD TURBO",
    3925000: "EBMS 12% POWER",
    3672000: "EBMS 11% P95"
    }

    # Only add the column if 'item_no' actually exists
    if any(c.lower() == "item_no" for c in full_data.columns):
        # Handle column name case variations (e.g., ITEM_NO or item_no)
        item_col = next(c for c in full_data.columns if c.lower() == "item_no")

        full_data = full_data.with_columns([
            pl.col(item_col)
            .cast(pl.Int64, strict=False)
            .map_elements(lambda x: ITEM_NAME_MAP.get(int(x)) if x and str(x).isdigit() and int(x) in ITEM_NAME_MAP else None)
            .alias("material_group_nm")
        ])
        print(" Added 'material_group_nm' column based on item_no mapping")
    else:
        print(" 'item_no' column not found — skipping material_group_nm mapping")

    # --- Drop + Recreate table to match merged schema ---
    cur = pg_conn.cursor()
    cur.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;')
    pg_conn.commit()
    cur.close()
    print(f" Dropped and recreated table '{table_name}' with new merged structure.")

    create_table_from_polars(pg_conn, full_data, table_name)

    # --- Insert merged data ---
    insertToDB_polars(pg_conn, full_data, table_name)
    logger.info(f"Total rows processed: {total_rows}")


def check_table_exists(pg_conn, table_name):
    """Check if a table exists in Postgres"""
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name=%s
        );
    """, (table_name,))
    exists = cur.fetchone()[0]
    cur.close()
    return exists


def check_table_empty(pg_conn, table_name):
    """Check if table is empty"""
    cur = pg_conn.cursor()
    cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    count = cur.fetchone()[0]
    cur.close()
    return count == 0


def get_max_syncdt(pg_conn, table_name):
    """Get maximum SYNCDT from Postgres table"""
    cur = pg_conn.cursor()
    cur.execute(f'SELECT MAX(syncdt) FROM "{table_name}" WHERE syncdt IS NOT NULL')
    max_syncdt = cur.fetchone()[0]
    cur.close()

    if not max_syncdt:
        return '1900-01-01 00:00:00'

    if isinstance(max_syncdt, str):
        return max_syncdt
    else:
        return max_syncdt.strftime("%Y-%m-%d %H:%M:%S")


# ---------------- Added Function for Location Master Merge ----------------
def enrich_with_location_master(pg_conn, data):
    """Join data with location_master on SUPPLY_LOC (source) = sap_id (location_master)"""
    print("Fetching and merging with location_master...")

    cur = pg_conn.cursor()
    cur.execute("""
        SELECT sap_id, name AS plant_nm, zone AS zone_nm, region, bu AS sbu_nm
        FROM location_master
    """)
    loc_rows = cur.fetchall()
    columns = [col[0].lower() for col in cur.description]
    cur.close()

    if not loc_rows:
        print(" No records found in location_master")
        return data

    df_location = pl.from_pandas(pd.DataFrame.from_records(loc_rows, columns=columns))

    # Clean keys for joining
    if "SUPPLY_LOC" in data.columns:
        data = data.with_columns(pl.col("SUPPLY_LOC").cast(pl.Utf8).str.replace_all(r"^00+", ""))
    if "sap_id" in df_location.columns:
        df_location = df_location.with_columns(pl.col("sap_id").cast(pl.Utf8).str.replace_all(r"^00+", ""))

    # Merge supply_loc ↔ sap_id
    if "SUPPLY_LOC" in data.columns:
        merged = data.join(df_location, left_on="SUPPLY_LOC", right_on="sap_id", how="left")
        if "SUPPLY_LOC" in merged.columns:
            merged = merged.rename({"SUPPLY_LOC": "sap_id"})
        print(f"Merged with location_master → total rows: {len(merged)}")
        return merged
    else:
        print(" Column 'supply_loc' not found in source data")
        return data


# ---------------- Main Execution ----------------
if __name__ == "__main__":
    # Load source DB credentials
    creds = credential_loader.get_credentials('TIBCO')
    params = {
        "host": creds['host'],
        "database": creds['database'],
        "user": creds['user'],
        "password": creds['password'],
        "port": creds['port'],
        "table_name": "sales_trips_till_date",
        "connection_type": "mysql"
    }

    # Postgres connection
    pg_creds = credential_loader.get_credentials('APP_DB')
    pg_conn = psycopg2.connect(
        host=pg_creds['host'],
        database=pg_creds['database'],
        user=pg_creds['user'],
        password=pg_creds['password'],
        port=pg_creds['port']
    )

    table_name = params["table_name"]
    table_exists = check_table_exists(pg_conn, table_name)

    # Source DB connection
    source_conn = get_db_connection(params)
    source_cursor = source_conn.cursor()

    base_query = """
        SELECT zais.*
        FROM CONN_ENT.ZSDCV_AY_INV3_TILL_DATE AS zais
        WHERE division = '11'
          AND load_status = '6'
          AND (qty_shortage > '0' OR qty_shortage <> '')
          AND sales_org = '7000'
    """

    if not table_exists:
        print(f"Target table '{table_name}' does not exist → creating table structure and dumping all data")

        if params["connection_type"].lower() == "mysql":
            sample_query = base_query + " LIMIT 10"
        elif params["connection_type"].lower() == "mssql":
            sample_query = base_query.replace("SELECT zais.", "SELECT TOP 10 zais.")
        else:
            sample_query = base_query + " FETCH FIRST 10 ROWS ONLY"

        source_cursor.execute(sample_query)
        sample_rows = source_cursor.fetchall()
        columns = [col[0] for col in source_cursor.description]
        sample_data = pl.from_pandas(pd.DataFrame.from_records(sample_rows, columns=columns))

        create_table_from_polars(pg_conn, sample_data, table_name)
        get_and_insert_data(source_cursor, base_query, pg_conn, table_name)

    else:
        is_empty = check_table_empty(pg_conn, table_name)
        if is_empty:
            print(f"Target table '{table_name}' is empty → dumping all data")
            get_and_insert_data(source_cursor, base_query, pg_conn, table_name)
        else:
            print(f"Target table '{table_name}' has data → syncing incrementally based on SYNCDT")

            max_syncdt = get_max_syncdt(pg_conn, table_name)
            print(f"Max SYNCDT in Postgres: {max_syncdt}")

            incremental_query = f"""
                {base_query}
                AND STR_TO_DATE(syncdt, '%Y-%m-%d %H:%i:%s') > STR_TO_DATE('{max_syncdt}', '%Y-%m-%d %H:%i:%s')
            """

            get_and_insert_data(source_cursor, incremental_query, pg_conn, table_name)

    source_cursor.close()
    source_conn.close()
    pg_conn.close()
