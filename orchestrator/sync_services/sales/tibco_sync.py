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
        elif params["connection_type"].lower() == "mssql":
            connection = mysql.connector.connect(
                host=server,
                user=username,
                passwd=password,
                port=port,
            )
    return connection


def insertToDB_polars(pg_conn, data, table_name):
    """
    Fast Polars → Postgres INSERT
    """
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


def get_and_insert_data(cursor, query, pg_conn, table_name, batch_size=50000):
    """Fetch source data in batches and insert into Postgres"""
    print("-" * 50)
    print("Running Query ...", query)
    cursor.execute(query)

    total_rows = 0
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        columns = [col[0] for col in cursor.description]
        data = pl.from_pandas(pd.DataFrame.from_records(rows, columns=columns))
        insertToDB_polars(pg_conn, data, table_name)
        total_rows += len(data)

    print(f"Total rows processed: {total_rows}")
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
    cur.execute(f'SELECT MAX(syncdt) FROM "{table_name}"')
    max_syncdt = cur.fetchone()[0]
    cur.close()
    return max_syncdt


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

    # Source DB connection
    source_conn = get_db_connection(params)
    source_cursor = source_conn.cursor()

    if not table_exists:
        print("Target table does not exist → creating and dumping all data")
        query = "SELECT * FROM CONN_ENT.SALES_BASED_TRIPS_TILL_DATE"
        get_and_insert_data(source_cursor, query, pg_conn, table_name)
    else:
        is_empty = check_table_empty(pg_conn, table_name)
        if is_empty:
            print("Target table is empty → dumping all data")
            query = "SELECT * FROM CONN_ENT.SALES_BASED_TRIPS_TILL_DATE"
            get_and_insert_data(source_cursor, query, pg_conn, table_name)
        else:
            print("Target table has data → syncing incrementally based on SYNCDT")

            # Get max syncdt from Postgres
            max_syncdt = get_max_syncdt(pg_conn, table_name)
            if max_syncdt is None:
                print("no maximum date in table")  # fallback if table empty

            print(f"Max SYNCDT in Postgres: {max_syncdt}")

            # Fetch only new/updated rows from source
            query = f"""
                SELECT * FROM CONN_ENT.SALES_BASED_TRIPS_TILL_DATE 
                WHERE syncdt > '{max_syncdt}'
            """
            get_and_insert_data(source_cursor, query, pg_conn, table_name)

    source_cursor.close()
    source_conn.close()
    pg_conn.close()

