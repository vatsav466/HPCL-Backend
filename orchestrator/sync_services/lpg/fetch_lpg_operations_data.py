import os
import sys
import psycopg2
import pandas as pd
import polars as pl
import socket
import datetime
import traceback
import concurrent.futures
import generate_lpg_operations_summary
sys.path.append("/opt/ceg/algo")
import orchestrator.dbconnector.credential_loader as credential_loader

def insertToDB(data, table_name):
    print("Length of Data : ", len(data))
    creds = credential_loader.get_credentials('APP_DB')
    pg_conn = psycopg2.connect(
                host=creds['host'],
                database=creds['database'],
                user=creds['user'],
                password=creds['password'],
                port=int(creds['port'])
            )    
    table_create_sql = ''
    cur = pg_conn.cursor()
    dtype_dict = {'String':str('text'),'Int64': str('bigint'), 'Int32': str('bigint'), 'Boolean': str('text'), 'Float64': str('double precision'),'Float32': str('double precision'),
                  'Object': str('text'), 'Datetime': str('timestamp'), 'Utf8': str('text'), "Datetime(time_unit='us', time_zone=None)": str('timestamp'), "Datetime(time_unit='ns', time_zone=None)": str('timestamp')}
    print('Data Types :',data.dtypes)
    col_dtype = {col: data[col].dtype for col in data.columns}
    for col, dty in col_dtype.items():
        dty = dtype_dict.get(str(dty))
        table_create_sql += f'"{col}" {dty},'
    table_create_sql = table_create_sql[:-1]
    
    create_table_index = f'CREATE INDEX IF NOT EXISTS "{table_name}_index" ON "{table_name}" ("Date","Plant Name","system_id")'
    table_create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({table_create_sql})'
    print("table_create_sql :", table_create_sql)
    cur.execute(table_create_sql)
    pg_conn.commit()
    cur.execute(create_table_index)

    sql = f"""SELECT * FROM "{table_name}" LIMIT 1"""
    cur.execute(sql)
    column_names = [desc[0] for desc in cur.description]
    columns=[]
    for i in column_names:
        columns.append(i)
    for col in columns:
        if not col in data.columns:
            data = data.with_columns(pl.lit(0).alias(col))
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
        print(f"-- Data Inserted to {table_name} --")
    except Exception as e:
        print("Error :", str(e))
        raise Exception(e)


def fetch_data(query, getData=False, params=None):
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
        return pl.DataFrame()
    if params:
        try:
            pg_conn = psycopg2.connect(
                    host=params["host"],
                    database=params["database"],
                    user=params["user"],
                    password=params["password"],
                    port=params["port"]
                )
            cursor = pg_conn.cursor()
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

    
def get_data(params):
    table_name = "lpg_operations_data"
    
    first_insertion = False
    query = """ SELECT DISTINCT("short_name") FROM "lpg_operations_summary"; """
    creds = credential_loader.get_credentials('APP_DB')
    app_db_params={
            "host": creds["host"],
            "database": creds["database"],
            "user": creds["user"],
            "password": creds["password"],
            "port": int(creds["port"])
            }
    plant_check = fetch_data(query, getData=True, params=app_db_params)
    if params['PlantName'].lower() not in plant_check["short_name"]:
        first_insertion = True
    
    query = f""" SELECT MAX(process_date) FROM "lpg_operations_summary" WHERE "short_name"='{params['PlantName'].lower()}'; """    
    max_date = fetch_data(query, getData=False, params=app_db_params)
    
    query = f""" SELECT * FROM production_log WHERE "process_date" > '{max_date}' """
    if first_insertion:
        max_date = datetime.datetime.now().strftime("%Y-%m-%d")
        query = f""" SELECT * FROM production_log WHERE "process_date" >= '{max_date}' """
    
    data = fetch_data(query, getData=True, params=params)
    if data.is_empty():
        print(f"-- Could not insert data to {table_name} --")
        return
    data = data.with_columns(pl.lit(params["PlantName"]).alias("Plant Name"))
    Date = datetime.datetime.now()
    data = data.with_columns(pl.lit(Date).alias("Date"))
    print("Length of  data:", len(data))
    insertToDB(data, table_name)
    
if __name__=="__main__":
    try:
        plants = pl.read_csv("/opt/ceg/algo/orchestrator/sync_services/lpg/LPG_PLANTS_CREDENTIALS.csv")        
        for plant in plants.iter_rows(named=True):
            try:
                # if plant["PlantName"].lower() == 'indore':
                #     continue
                print("plant :", plant["PlantName"])
                print("-"*50)
                print(f"Fetching for {plant['PlantName']}")
                params={
                "PlantName": plant["PlantName"],
                "host": plant["host_ip"],
                "database": plant["db_database"],
                "user": plant["db_user"],
                "password": plant["db_password"],
                "port": 5432
                }
                get_data(params)
            except Exception as e:
                if "psycopg2.OperationalError" in str(e):
                    print(f"-- OperationalError while fetching data for {plant["PlantName"]} --")
                    print("Traceback :", traceback.format_exc())
                    continue
                else:
                    raise Exception(e)
        print("*"*50)
        print("-- Data Insertion to lpg_operations_data completed --")
        print("*"*50)
        generate_lpg_operations_summary.generate_summary()
    except Exception as e:
        print("*-"*25)
        print("-- Exception in fetching the operations data -- ")
        print("Traceback :", traceback.format_exc())
        creds = credential_loader.get_credentials('APP_DB')
        pg_conn = psycopg2.connect(
                    host=creds["host"],
                    database=creds["database"],
                    user=creds["user"],
                    password=creds["password"],
                    port=int(creds["port"])
                )
        cursor = pg_conn.cursor()
        query = f""" TRUNCATE lpg_operations_data; """
        cursor.execute(query)
        pg_conn.commit()
        cursor.close()
        pg_conn.close()
        print('-- Removed the data from lpg_operations_data table --')