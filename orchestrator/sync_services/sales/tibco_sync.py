import os
import uuid
import psycopg2
import hashlib
import polars as pl
import urdhva_base
import sys
import mysql.connector
import pandas as pd
import time
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from psycopg2.extras import execute_values

sys.path.append("/opt/ceg/algo")
import orchestrator.dbconnector.credential_loader as credential_loader

logger = urdhva_base.logger.Logger.getInstance('tibco_sync_log')


# ---------------- SAFE EXECUTION WITH RETRY ----------------
def safe_execute(cursor, query, max_retries=5, wait_time=15):
    """Execute query with retry if MySQL is overloaded"""
    for attempt in range(max_retries):
        try:
            cursor.execute(query)
            return
        except mysql.connector.Error as e:
            # Error 2435 → Too many queries queued
            if e.errno == 2435:
                print(f"[Warning] DB overloaded. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                raise  # re-raise other errors immediately
    raise Exception("Failed after multiple retries — DB queue still full.")


# ---------------- DATABASE CONNECTION ----------------
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
        elif params["connection_type"].lower() == "mssql":
            connection = mysql.connector.connect(
                host=server,
                user=username,
                passwd=password,
                port=port,
                database=database
            )
    return connection


# ---------------- CREATE TABLE ----------------
def create_table_from_source(pg_conn, data, table_name):
    """Create Postgres table dynamically based on Polars dataframe schema"""
    if data.is_empty():
        print("No data available to infer table schema.")
        return

    cur = pg_conn.cursor()
    cols = []
    for name, dtype in data.schema.items():
        if dtype == pl.Utf8:
            sql_type = "TEXT"
        elif dtype in [pl.Int64, pl.Int32]:
            sql_type = "BIGINT"
        elif dtype in [pl.Float64, pl.Float32]:
            sql_type = "DOUBLE PRECISION"
        elif dtype == pl.Boolean:
            sql_type = "BOOLEAN"
        elif dtype in [pl.Datetime, pl.Date]:
            sql_type = "TIMESTAMP"
        else:
            sql_type = "TEXT"
        cols.append(f'"{name.lower()}" {sql_type}')

    # Always add engine_id column if missing
    if "engine_id" not in [c.lower() for c in data.columns]:
        cols.append('"engine_id" TEXT')

    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(cols)});'
    cur.execute(create_sql)
    pg_conn.commit()
    cur.close()
    print(f"Created table {table_name} with {len(cols)} columns")


# ---------------- INSERT DATA ----------------
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

    # Cast float/decimal
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


# ---------------- FETCH AND INSERT ----------------
def get_and_insert_data(cursor, query, pg_conn, table_name, df_location, batch_size=50000):
    """Fetch source data in batches, merge with location_master, and insert into Postgres"""
    print("-" * 50)
    print("Running Query ...", query)

    # ✅ Use safe_execute here
    safe_execute(cursor, query)

    total_rows = 0
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break

        columns = [col[0].lower() for col in cursor.description]
        df_main = pd.DataFrame.from_records(rows, columns=columns)

        print(f"Fetched batch of {len(df_main)} rows from source")

        # Merge source batch with location_master on plant_cd == sap_id
        merged_df = df_main.merge(df_location, left_on='plant_cd', right_on='sap_id', how='left')

        # Ensure BU, SAP_ID, Zone, Region columns exist
        for col in ["bu", "sap_id", "region", "zone"]:
            if col not in merged_df.columns:
                merged_df[col] = None

        print("Merged batch preview:")
        print(merged_df.head(5))

        # Convert merged DataFrame to Polars
        data = pl.from_pandas(merged_df)

        # Ensure table exists
        create_table_from_source(pg_conn, data, table_name)

        # Insert merged data
        insertToDB_polars(pg_conn, data, table_name)
        total_rows += len(data)
        print(f"Merged and inserted {len(data)} rows in this batch")

    print(f"Total rows processed and merged: {total_rows}")
    logger.info(f"Total rows processed and merged: {total_rows}")


# ---------------- TABLE UTILITIES ----------------
def check_table_exists(pg_conn, table_name):
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
    cur = pg_conn.cursor()
    cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    count = cur.fetchone()[0]
    cur.close()
    return count == 0


def get_max_syncdt(pg_conn, table_name):
    cur = pg_conn.cursor()
    cur.execute(f'SELECT MAX(syncdt) FROM "{table_name}"')
    max_syncdt = cur.fetchone()[0]
    cur.close()
    return max_syncdt


# ---------------- MAIN EXECUTION ----------------
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
        "connection_type": "mssql"
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

    # Fetch location_master once and reuse
    print("Fetching location_master from Postgres ...")
    loc_cur = pg_conn.cursor()
    loc_cur.execute("SELECT sap_id, bu, region, zone FROM location_master")
    loc_rows = loc_cur.fetchall()
    loc_columns = [col[0].lower() for col in loc_cur.description]
    df_location = pd.DataFrame.from_records(loc_rows, columns=loc_columns)
    loc_cur.close()
    print(f"Location Master loaded with {len(df_location)} records")

    # Source DB connection
    source_conn = get_db_connection(params)
    source_cursor = source_conn.cursor()

    if not table_exists:
        print("Target table does not exist → creating and dumping all data")
        source_cursor.execute("SELECT * FROM CONN_ENT.SALES_BASED_TRIPS_TILL_DATE LIMIT 100")
        sample_rows = source_cursor.fetchall()
        columns = [col[0].lower() for col in source_cursor.description]
        sample_data = pl.from_pandas(pd.DataFrame.from_records(sample_rows, columns=columns))
        merged_sample = pd.DataFrame(sample_data.to_pandas()).merge(
            df_location, left_on='plant_cd', right_on='sap_id', how='left'
        )
        data_sample = pl.from_pandas(merged_sample)
        create_table_from_source(pg_conn, data_sample, table_name)
        query = "SELECT * FROM CONN_ENT.SALES_BASED_TRIPS_TILL_DATE"
        get_and_insert_data(source_cursor, query, pg_conn, table_name, df_location)
    else:
        is_empty = check_table_empty(pg_conn, table_name)
        if is_empty:
            print("Target table is empty → dumping all data")
            query = "SELECT * FROM CONN_ENT.SALES_BASED_TRIPS_TILL_DATE"
            get_and_insert_data(source_cursor, query, pg_conn, table_name, df_location)
        else:
            print("Target table has data → syncing incrementally based on SYNCDT")
            max_syncdt = get_max_syncdt(pg_conn, table_name)
            if max_syncdt is None:
                max_syncdt = '1900-01-01 00:00:00'
            print(f"Max SYNCDT in Postgres: {max_syncdt}")
            query = f"""
                SELECT * FROM CONN_ENT.SALES_BASED_TRIPS_TILL_DATE 
                WHERE syncdt > '{max_syncdt}'
            """
            get_and_insert_data(source_cursor, query, pg_conn, table_name, df_location)

    source_cursor.close()
    source_conn.close()
    pg_conn.close()
