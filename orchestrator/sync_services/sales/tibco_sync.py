import os
import uuid
import pyodbc
import psycopg2
import traceback
import datetime
import pandas as pd
import polars as pl
import hashlib
import urdhva_base
import sys
import mysql.connector

import orchestrator.notification_manager.notification_factory
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.append("/opt/ceg/algo")
import orchestrator.dbconnector.credential_loader as credential_loader

logger = urdhva_base.logger.Logger.getInstance('tibco_sync_log')


def get_db_connection(params):
    """
    Establish a database connection
    Args:
        params (dict): Database connection parameters
    Returns:
        connection object
    """
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
        if params["connection_type"].lower() == "mssql":
            connection = mysql.connector.connect(
                host=server,
                user=username,
                passwd=password,
                port=port
                #database=database
            )
    print(connection)
    return connection


def insertToDB(data, table_name, indexing_col=()):
    """
    Insert Polars DataFrame to Postgres DB
    """
    data = data.rename({col: col.lower() for col in data.columns})
    # Add engine_id column
    data = data.with_columns(
        pl.struct(data.columns).map_elements(
            lambda row: hashlib.md5("|".join(str(v) for v in row.values()).encode()).hexdigest()
        ).alias("engine_id")
    )

    print(data.schema)

    # Cast Decimal/float types
    for col in data.columns:
        if data.schema[col] in [pl.Float32, pl.Float64]:
            data = data.with_columns(pl.col(col).alias(col))
        if 'Decimal' in str(data.schema[col]):
            data = data.with_columns(pl.col(col).cast(float).alias(col))

    print(data)
    print(data.schema)

    print("-" * 50)
    print(f"-- Inserting Data to {table_name} --")
    print("Length of Data :", len(data))

    # Load Postgres credentials
    creds = credential_loader.get_credentials('APP_DB')
    pg_conn = psycopg2.connect(
        host=creds['host'],
        database=creds['database'],
        user=creds['user'],
        password=creds['password'],
        port=creds['port']
    )
    cur = pg_conn.cursor()

    dtype_dict = {'String': str('text'), 'Int64': str('bigint'), 'Int32': str('bigint'), 'Boolean': str('text'),
                  'Float64': str('double precision'), 'Float32': str('double precision'),
                  #'Float64':'Float64',
                  'Object': str('text'), 'Datetime': str('timestamp'), 'Date': str('timestamp'), 'Utf8': str('text'),
                  "Datetime(time_unit='us', time_zone=None)": str('timestamp'),
                  "Datetime(time_unit='ns', time_zone=None)": str('timestamp'),
                  "Decimal(precision=5, scale=2)": str('double precision')}

    col_dtype = {col: data[col].dtype for col in data.columns}
    table_create_sql = ', '.join(f'"{col}" {dtype_dict.get(str(dty), "text")}' for col, dty in col_dtype.items())
    table_create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({table_create_sql})'
    cur.execute(table_create_sql)
    pg_conn.commit()

    if indexing_col:
        if not isinstance(indexing_col, list):
            indexing_col = [indexing_col]
        # Filter out empty or None values
        valid_cols = [col for col in indexing_col if col]
        if valid_cols:
            columns_formatted = ", ".join(f'"{col}"' for col in valid_cols)
            create_table_index = f'CREATE INDEX IF NOT EXISTS "{table_name}_index" ON "{table_name}" ({columns_formatted})'
            cur.execute(create_table_index)
            pg_conn.commit()

    # Delete existing data
    cur.execute(f'DELETE FROM "{table_name}"')
    pg_conn.commit()

    # Insert data in chunks
    chunk_size = 1000000
    for i in range(0, len(data), chunk_size):
        split_df = data[i:i + chunk_size]
        csv_file = f'/tmp/{table_name}.csv'
        split_df.write_csv(csv_file, separator='~')
        query = f'COPY "{table_name}" FROM STDIN CSV HEADER DELIMITER \'~\';'
        with open(csv_file, 'r') as f:
            cur.copy_expert(query, f)
            pg_conn.commit()
        os.remove(csv_file)

    print(f"-- Data has been inserted to {table_name} --")
    with pg_conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        row_count = cur.fetchone()[0]
        print(f"Total records in {table_name}: {row_count}")

    # Send async email
    #import asyncio
    #from orchestrator.notification_manager.notification_factory import send_sales_sync_email
    #asyncio.run(send_sales_sync_email(table_name, row_count))

    cur.close()
    pg_conn.close()


def get_and_insert_data(cursor, query, params=None):
    """
    Fetch data from source DB and insert into Postgres
    """
    print("-" * 50)
    print("Running Query ...",query)
    cursor.execute(query)
    data = cursor.fetchall()
    print('Total Records :', len(data))
    logger.info(f"Total Records : {len(data)}")

    columns = [column[0] for column in cursor.description]
    data = pd.DataFrame.from_records(data, columns=columns)
    data = data.drop_duplicates()
    data.to_csv('/tmp/data_org_drop.csv', index=False)

    data_polars = pl.from_pandas(data)
    insertToDB(data_polars, params["table_name"])


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

    query = "SELECT * FROM CONN_ENT.SALES_BASED_TRIPS_TILL_DATE"

    connection = get_db_connection(params)
    cursor = connection.cursor()
    get_and_insert_data(cursor, query, params=params)
    cursor.close()
    connection.close()

