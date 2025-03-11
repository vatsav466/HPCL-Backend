import os
import sys
import uuid
import pyodbc
import psycopg2
import traceback
import datetime
import socket
import pandas as pd
import polars as pl
from dateutil.relativedelta import relativedelta
sys.path.append("/opt/ceg/algo")
import orchestrator.dbconnector.credential_loader as credential_loader


def insertToDB(data, table_name, indexing_col=[]):
    print("-"*50)
    print(f"-- Inserting Data to {table_name} --")
    print("Length of Data :", len(data))
    for col in data.columns:
        try:
            if not col in ["sap_id"]:
                data = data.with_columns(pl.col(col).fill_null(0).cast(pl.Float64).alias(col))
        except Exception as e:
            continue
    creds = credential_loader.get_credentials('APP_DB')
    pg_conn = psycopg2.connect(
                host=creds['host'],
                database=creds['database'],
                user=creds['user'],
                password=creds['password'],
                port=creds['port']
            )
    table_create_sql = ''
    cur = pg_conn.cursor()
    dtype_dict = {'String':str('text'),'Int64': str('bigint'), 'Int32': str('bigint'), 'Boolean': str('text'), 'Float64': str('double precision'),'Float32': str('double precision'),
                  'Object': str('text'), 'Datetime': str('timestamp'), 'Date': str('timestamp'), 'Utf8': str('text'), "Datetime(time_unit='us', time_zone=None)": str('timestamp'), "Datetime(time_unit='ns', time_zone=None)":str('timestamp'), "Decimal(precision=5, scale=2)": str('double precision')}
    print('Data Types :',data.dtypes)
    col_dtype = {col: data[col].dtype for col in data.columns}
    for col, dty in col_dtype.items():
        dty = dtype_dict.get(str(dty))
        table_create_sql += f'"{col}" {dty},'
    table_create_sql = table_create_sql[:-1]
    if not isinstance(indexing_col, list):
        indexing_col = [indexing_col]
    columns_formatted = ", ".join(f'"{col}"' for col in indexing_col)
    create_table_index = f"""CREATE INDEX IF NOT EXISTS "{table_name}_index" ON "{table_name}" ({columns_formatted})"""
    
    table_create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({table_create_sql})'
    print("-"*50)
    print("table_create_sql :", table_create_sql)
    print("-"*50)    
    cur.execute(table_create_sql)
    pg_conn.commit()
    cur.execute(create_table_index)

    sql = f"""SELECT * FROM "{table_name}" LIMIT 1"""
    cur.execute(sql)
    column_names = [desc[0] for desc in cur.description]
    columns=[]
    for i in column_names:
        columns.append(i)
    data = data.select(columns)
    try:
        query = f'''
        COPY "{table_name}"
        FROM STDIN
        CSV HEADER DELIMITER '~';
        '''
        for g, split_df in data.group_by(len(data)// 10000000):
            csv_file = f'/tmp/{table_name}.csv'
            split_df.write_csv(csv_file, separator='~')
            with open(csv_file, 'r') as f:
                cur.copy_expert(query, f)
                pg_conn.commit()
        cur.close()
        if os.path.exists(f'/tmp/{table_name}.csv'):
            os.remove(f'/tmp/{table_name}.csv')
        print(f"-- Data has been inserted to {table_name} --")
    except Exception as e:
        print("Error :", str(e))
        raise Exception(e)


def fetch_data(query, getData=False, params=None, internal=False):
    """
    Fetch data from database using a SQL query
    Args:
        cursor (pyodbc cursor): Database cursor
        query (str): SQL query to execute
    Returns:
        pandas DataFrame
    """    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((params["host"], params["port"]))
    if not result == 0:
        print(f"Could not Connect to {params["PlantName"]}")
        return pl.DataFrame()
    if params:
        try:
            if internal:
                creds = credential_loader.get_credentials('APP_DB')
                pg_conn = psycopg2.connect(
                            host=creds['host'],
                            database=creds['database'],
                            user=creds['user'],
                            password=creds['password'],
                            port=creds['port']
                        )
            else:
                pg_conn = psycopg2.connect(
                        host=params["host"],
                        database=params["database"],
                        user=params["user"],
                        password=params["password"],
                        port=params["port"]
                    )
            cursor = pg_conn.cursor()
            cursor.execute("SET statement_timeout = 600000;")
        except Exception as e:
            print("Exception :", str(e))
            return pl.DataFrame()
    print("-" * 50)
    print("query -->", query)
    print("-" * 50)
    print("Running Query ...")
    cursor.execute(query)
    if getData:
        data = cursor.fetchall()
        print('Total Records :', len(data))
        columns = [column[0] for column in cursor.description]
        data = pd.DataFrame.from_records(data, columns=columns)
        data = pl.from_pandas(data)
        return data
    else:
        resp = cursor.fetchone()[0]
        return resp

    
def get_cs_rejections(params):
    table_name = "lpg_cs_rejections"
    # query = """ WITH base_data AS (
    #                 SELECT
    #                     system_id,
    #                     process_status,
    #                     COUNT(*) as count,
    #                     DATE_TRUNC('day', process_date) as process_date
    #                 FROM production_log
    #                 WHERE system_id IN (1, 2)
    #                     AND process_id IN (2, 22)
    #                 GROUP BY system_id, process_status, DATE_TRUNC('day', process_date)
    #             ),
    #             aggregated_stats AS (
    #                 SELECT
    #                     process_date,
    #                     SUM(count) as total,
    #                     -- Calculate cylFilled (total - sortout)
    #                     SUM(count) - SUM(CASE 
    #                         WHEN process_status IN (1040, 2064, 1296, 17424, 1048, 4120, 5392,  -- sortout statuses
    #                                             1041, 1042, 2192, 4112, 4113, 5136, 6160)     -- other error statuses
    #                         THEN count 
    #                         ELSE 0 
    #                     END) as cylFilled,
    #                     -- Calculate totalSortout
    #                     SUM(CASE 
    #                         WHEN process_status IN (1040, 2064, 1296, 17424, 1048, 4120, 5392,  -- sortout statuses
    #                                             1041, 1042, 2192, 4112, 4113, 5136, 6160)     -- other error statuses
    #                         THEN count 
    #                         ELSE 0 
    #                     END) as totalSortout,
    #                     -- Calculate commErrorSortout
    #                     SUM(CASE 
    #                         WHEN process_status < 0 OR process_status = 4096 
    #                         THEN count 
    #                         ELSE 0 
    #                     END) as commErrorSortout
    #                 FROM base_data
    #                 GROUP BY process_date
    #             )
    #             SELECT 
    #                 process_date,
    #                 total,
    #                 cylFilled,
    #                 totalSortout,
    #                 commErrorSortout,
    #                 CASE 
    #                     WHEN total > 0 THEN ROUND(CAST(totalSortout AS DECIMAL) / total, 4)
    #                     ELSE 0 
    #                 END as sortOutPercentage
    #             FROM aggregated_stats
    #             ORDER BY process_date; """    
        
    query = f""" SELECT MAX(max_date) from lpg_cs_rejections WHERE "plant"='{params['PlantName']}'; """
    last_date = fetch_data(query, getData=False, params=params, internal=True)
    query = """ SELECT MAX(process_date) from production_log; """
    max_date = fetch_data(query, getData=False, params=params)
    
    query = f""" WITH base_data AS (
                    SELECT
                        system_id,
                        cyl_type,
                        process_status,
                        COUNT(*) as count,
                        DATE_TRUNC('day', process_date) as process_date
                    FROM production_log
                    WHERE system_id IN (1, 2)
                        AND process_id IN (2, 22)
                        AND process_date > '{last_date}'
                    GROUP BY system_id, cyl_type, process_status, DATE_TRUNC('day', process_date)
                ),
                aggregated_stats AS (
                    SELECT
                        process_date,
                        system_id,
                        cyl_type,
                        SUM(count) as total,
                        -- Calculate cylFilled (total - sortout)
                        SUM(count) - SUM(CASE 
                            WHEN process_status IN (1040, 2064, 1296, 17424, 1048, 4120, 5392,  -- sortout statuses
                                                1041, 1042, 2192, 4112, 4113, 5136, 6160)     -- other error statuses
                            THEN count 
                            ELSE 0 
                        END) as cylFilled,
                        -- Calculate totalSortout
                        SUM(CASE 
                            WHEN process_status IN (1040, 2064, 1296, 17424, 1048, 4120, 5392,  -- sortout statuses
                                                1041, 1042, 2192, 4112, 4113, 5136, 6160)     -- other error statuses
                            THEN count 
                            ELSE 0 
                        END) as totalSortout,
                        -- Calculate commErrorSortout
                        SUM(CASE 
                            WHEN process_status < 0 OR process_status = 4096 
                            THEN count 
                            ELSE 0 
                        END) as commErrorSortout
                    FROM base_data
                    GROUP BY process_date, system_id, cyl_type
                )
                SELECT 
                    process_date,
                    system_id,
                    cyl_type,
                    total,
                    cylFilled,
                    totalSortout,
                    commErrorSortout,
                    CASE 
                        WHEN total > 0 THEN ROUND(CAST(totalSortout AS DECIMAL) / total, 4)
                        ELSE 0 
                    END as sortOutPercentage
                FROM aggregated_stats
                ORDER BY process_date, system_id, cyl_type; """            
            
    data = fetch_data(query, getData=True, params=params)
    if data.is_empty():
        return
    data = data.with_columns(pl.lit(params["PlantName"]).alias("plant"))
    data = data.with_columns(pl.lit(params["zone"]).alias("zone"))
    data = data.with_columns(pl.lit(str(params["sap_id"])).alias("sap_id"))
    
    data = data.with_columns(pl.when(
        pl.col("cyl_type").fill_null(0).cast(pl.Int64)==1
        ).then(pl.lit("14.2 KG")
               ).when(pl.col("cyl_type").fill_null(0).cast(pl.Int64)==2
                      ).then(pl.lit("19 KG")).when(pl.col("cyl_type").fill_null(0).cast(pl.Int64)==0).then(pl.lit("5KG")).otherwise(pl.col("cyl_type").cast(pl.Utf8)).alias("cyl_type"))
    
    data = data.with_columns(pl.lit(datetime.datetime.now()).alias("Execution_Date"))    
    data = data.with_columns(pl.lit(max_date).alias("max_date"))
    data = data.with_columns(pl.col("Execution_Date").alias('updated_at'))
    data = data.with_columns(pl.col('updated_at').alias('created_at'))
    data = data.with_columns(pl.col('sap_id').alias('entity_id'))
        
    indexing_col = ["process_date", "zone", "plant"]
    insertToDB(data, table_name, indexing_col)


def get_gd_rejections(params):
    table_name = "lpg_gd_rejections"
    #if params['PlantName'].lower()=='hoshiarpur':
    #    return
    query = f""" SELECT MAX(max_date) from lpg_gd_rejections WHERE "plant"='{params['PlantName']}'; """
    last_date = fetch_data(query, getData=False, params=params, internal=True)
    query = """ SELECT MAX(process_date) from event_log; """
    max_date = fetch_data(query, getData=False, params=params)
    
    query = f""" WITH base_stats AS (
                    SELECT
                        system_id,
                        cyl_type,
                        process_id,
                        process_status,
                        COUNT(*) as count,
                        DATE_TRUNC('day', process_date) as process_date
                    FROM event_log
                    WHERE system_id IN (1, 2)
                        AND process_id IN (3, 23)  -- For GD process
                        AND process_date > '{last_date}'
                    GROUP BY system_id, cyl_type, process_id, process_status, DATE_TRUNC('day', process_date)
                ),
                daily_stats AS (
                    SELECT 
                        process_date,
                        system_id,
                        cyl_type,
                        SUM(count) as total,
                        SUM(CASE 
                            WHEN process_status != 0 THEN count 
                            ELSE 0 
                        END) as sortout
                    FROM base_stats
                    GROUP BY process_date, system_id, cyl_type
                )
                SELECT 
                    process_date,
                    system_id,
                    cyl_type,
                    total,
                    sortout,
                    CASE 
                        WHEN total > 0 THEN ROUND(CAST(sortout AS DECIMAL) / total, 4)
                        ELSE 0
                    END as sortOutPercentage
                FROM daily_stats
                ORDER BY process_date, system_id, cyl_type; """
    data = fetch_data(query, getData=True, params=params)
    if data.is_empty():
        return
    data = data.with_columns(pl.lit(params["PlantName"]).alias("plant"))
    data = data.with_columns(pl.lit(params["zone"]).alias("zone"))
    data = data.with_columns(pl.lit(str(params["sap_id"])).alias("sap_id"))
    data = data.with_columns(pl.when(
        pl.col("cyl_type").fill_null(0).cast(pl.Int64)==1
        ).then(pl.lit("14.2 KG")
               ).when(pl.col("cyl_type").fill_null(0).cast(pl.Int64)==2
                      ).then(pl.lit("19 KG")).otherwise(pl.lit("5 KG")).alias("cyl_type"))
    data = data.with_columns(pl.lit(datetime.datetime.now()).alias("Execution_Date"))    
    data = data.with_columns(pl.lit(max_date).alias("max_date"))
    data = data.with_columns(pl.col("Execution_Date").alias('updated_at'))
    data = data.with_columns(pl.col('updated_at').alias('created_at'))
    data = data.with_columns(pl.col('sap_id').alias('entity_id'))
        
    indexing_col = ["process_date", "zone", "plant"]
    insertToDB(data, table_name, indexing_col)


def get_pt_rejections(params):
    table_name = "lpg_pt_rejections"
    #if params['PlantName'].lower()=='hoshiarpur':
    #    return    
    query = f""" SELECT MAX(max_date) from lpg_pt_rejections WHERE "plant"='{params['PlantName']}'; """
    last_date = fetch_data(query, getData=False, params=params, internal=True)
    query = """ SELECT MAX(process_date) from event_log; """
    max_date = fetch_data(query, getData=False, params=params)
    
    query = f""" WITH base_stats AS (
                    SELECT
                        system_id,
                        cyl_type,
                        process_id,
                        process_status,
                        COUNT(*) as count,
                        DATE_TRUNC('day', process_date) as process_date
                    FROM event_log
                    WHERE system_id IN (1, 2)
                        AND process_id IN (4, 24)  -- For GD process
                        AND process_date > '{last_date}'
                    GROUP BY system_id, cyl_type, process_id, process_status, DATE_TRUNC('day', process_date)
                ),
                daily_stats AS (
                    SELECT 
                        process_date,
                        system_id,
                        cyl_type,
                        SUM(count) as total,
                        SUM(CASE 
                            WHEN process_status != 0 THEN count 
                            ELSE 0 
                        END) as sortout
                    FROM base_stats
                    GROUP BY process_date, system_id, cyl_type
                )
                SELECT 
                    process_date,
                    system_id,
                    cyl_type,
                    total,
                    sortout,
                    CASE 
                        WHEN total > 0 THEN ROUND(CAST(sortout AS DECIMAL) / total, 4)
                        ELSE 0
                    END as sortOutPercentage
                FROM daily_stats
                ORDER BY process_date, system_id, cyl_type; """
    data = fetch_data(query, getData=True, params=params)
    if data.is_empty():
        return
    data = data.with_columns(pl.lit(params["PlantName"]).alias("plant"))
    data = data.with_columns(pl.lit(params["zone"]).alias("zone"))
    data = data.with_columns(pl.lit(str(params["sap_id"])).alias("sap_id"))
    data = data.with_columns(pl.when(
        pl.col("cyl_type").fill_null(0).cast(pl.Int64)==1
        ).then(pl.lit("14.2 KG")
               ).when(pl.col("cyl_type").fill_null(0).cast(pl.Int64)==2
                      ).then(pl.lit("19 KG")).otherwise(pl.lit("5 KG")).alias("cyl_type"))
    data = data.with_columns(pl.lit(datetime.datetime.now()).alias("Execution_Date"))
    data = data.with_columns(pl.lit(max_date).alias("max_date"))
    data = data.with_columns(pl.col("Execution_Date").alias('updated_at'))
    data = data.with_columns(pl.col('updated_at').alias('created_at'))
    data = data.with_columns(pl.col('sap_id').alias('entity_id'))
    
    indexing_col = ["process_date", "zone", "plant"]
    insertToDB(data, table_name, indexing_col)
    
            
if __name__=="__main__":
    plants = pl.read_csv("/opt/ceg/algo/orchestrator/sync_services/lpg/LPG_PLANTS_CREDENTIALS.csv")
    for plant in plants.iter_rows(named=True):
        print("-"*50)
        print(f"Fetching for {plant['PlantName']}")
        params={
        "PlantName": plant["PlantName"],
        "sap_id": plant["erp_id"],
        "zone": plant["zone"],
        "host": plant["host_ip"],
        "database": plant["db_database"],
        "user": plant["db_user"],
        "password": plant["db_password"],
        "port": 5432
        }
        get_cs_rejections(params)
        get_gd_rejections(params)
        get_pt_rejections(params)
