import os
import sys
import psycopg2
import pandas as pd
import polars as pl
import socket
import datetime
import traceback
import concurrent.futures
import signal
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


def fetch_data(query, getData=False, params=None, timeout=10, query_timeout=30):
    """
    Fetch data from database with both connection and query timeout handling
    """    
    # Check connection with timeout
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)  # Connection timeout
    try:
        result = sock.connect_ex((params["host"], int(params["port"])))
        if not result == 0:
            print(f"Connection timed out to {params['host']}:{params['port']} after {timeout} seconds")
            return pl.DataFrame() if getData else None
    except Exception as e:
        print(f"Socket connection error: {str(e)}")
        return pl.DataFrame() if getData else None
    finally:
        sock.close()  # Properly close the socket
        
    # Database connection with timeout
    try:
        pg_conn = psycopg2.connect(
                host=params["host"],
                database=params["database"],
                user=params["user"],
                password=params["password"],
                port=params["port"],
                connect_timeout=timeout  # Connection timeout
            )
        pg_conn.set_session(autocommit=True)  # Enable autocommit for timeout settings
        cursor = pg_conn.cursor()
        
        # Set statement timeout at the connection level (milliseconds)
        cursor.execute(f"SET statement_timeout = {query_timeout * 300000};")        
        
    except Exception as e:
        print(f"Database connection error for {params.get('PlantName', 'unknown')}: {str(e)}")
        return pl.DataFrame() if getData else None
        
    try:
        print("-" * 50)
        print(f"Running Query with {query_timeout}s timeout...")
        print(query)
        
        cursor.execute(query)
        
        if getData:
            data = cursor.fetchall()
            print('Total Records :', len(data))
            print("-" * 50)
            columns = [column[0] for column in cursor.description]
            data = pd.DataFrame.from_records(data, columns=columns)
            data = pl.from_pandas(data)
            return data
        else:
            resp = cursor.fetchone()
            return resp[0] if resp else None
    except psycopg2.errors.QueryCanceled:
        print(f"Query timed out after {query_timeout} seconds - skipping this plant")
        return pl.DataFrame() if getData else None
    except Exception as e:
        print(f"Query execution error: {str(e)}")
        return pl.DataFrame() if getData else None
    finally:
        cursor.close()
        pg_conn.close()

    
def get_data(params):
    table_name = "lpg_operations_data"
    
    try:
        first_insertion = False
        creds = credential_loader.get_credentials('APP_DB')
        app_db_params={
                "host": creds["host"],
                "database": creds["database"],
                "user": creds["user"],
                "password": creds["password"],
                "port": int(creds["port"])
                }
        
        # Check if this plant exists in summary table
        query = """ SELECT DISTINCT("short_name") FROM "lpg_operations_summary"; """
        plant_check = fetch_data(query, getData=True, params=app_db_params)
        
        if plant_check is None or plant_check.is_empty():
            print(f"No existing plants found in summary table for {params['PlantName']}")
            first_insertion = True
        elif params['PlantName'].lower() not in plant_check["short_name"]:
            print(f"Plant {params['PlantName']} not found in existing records - first insertion")
            first_insertion = True
        
        # Get max date or use default
        if first_insertion:
            max_date = datetime.datetime.now().strftime("%Y-%m-%d")
            print(f"First insertion for {params['PlantName']} using date {max_date}")
        else:
            query = f""" SELECT MAX(process_date) FROM "lpg_operations_summary" WHERE "short_name"='{params['PlantName'].lower()}'; """    
            max_date = fetch_data(query, getData=False, params=app_db_params)
            if max_date is None:
                max_date = datetime.datetime.now().strftime("%Y-%m-%d")
                print(f"No max date found for {params['PlantName']}, using current date {max_date}")
        
        # For large tables, try to limit data or use chunking
        query = f""" 
            SELECT * FROM production_log 
            WHERE "process_date" > '{max_date}'
            ORDER BY "process_date" ASC
            LIMIT 1000000;  -- Set a reasonable limit to prevent giant queries
        """
        
        if first_insertion:
            # For first insertion, we might want to get less historical data
            # to ensure it completes in a reasonable time
            query = f""" 
                SELECT * FROM production_log 
                WHERE "process_date" >= '{max_date}'
                ORDER BY "process_date" ASC
                LIMIT 500000;  -- More conservative limit for first run
            """
        
        # Get data with query timeout (60 seconds)
        print(f"Fetching data for plant {params['PlantName']} with timeout...")
        data = fetch_data(query, getData=True, params=params, timeout=10, query_timeout=60)
        
        if data is None or data.is_empty():
            print(f"-- No data or query timed out for plant {params['PlantName']} --")
            return
            
        data = data.with_columns(pl.lit(params["PlantName"]).alias("Plant Name"))
        Date = datetime.datetime.now()
        data = data.with_columns(pl.lit(Date).alias("Date"))
        print(f"Length of data for {params['PlantName']}: {len(data)}")
        
        # Insert data
        insertToDB(data, table_name)
        print(f"Successfully processed plant {params['PlantName']}")
        
    except Exception as e:
        print(f"Error in get_data for plant {params['PlantName']}: {str(e)}")
        print("Traceback:", traceback.format_exc())
        raise
    
if __name__=="__main__":
    try:
        plants = pl.read_csv("/opt/ceg/algo/orchestrator/sync_services/lpg/LPG_PLANTS_CREDENTIALS.csv")        
        successful_plants = []
        failed_plants = []
        
        # Process plants sequentially but with timeouts
        for plant in plants.iter_rows(named=True):
            try:
                print("-*"*40)
                print(f"Processing plant: {plant['PlantName']}")
                
                params={
                    "PlantName": plant["PlantName"],
                    "host": plant["host_ip"],
                    "database": plant["db_database"],
                    "user": plant["db_user"],
                    "password": plant["db_password"],
                    "port": 5432
                }
                
                # Process with timeout using signal handler (Unix-only solution)
                def timeout_handler(signum, frame):
                    raise TimeoutError(f"Processing timed out for {plant['PlantName']}")
                
                # Set 3-minute timeout for entire plant processing
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(180)  # 3 minutes
                
                try:
                    get_data(params)
                    successful_plants.append(plant["PlantName"])
                    print(f"Successfully processed plant: {plant['PlantName']}")
                except TimeoutError as te:
                    print(f"TIMEOUT: {str(te)}")
                    failed_plants.append(plant["PlantName"])
                except Exception as e:
                    if "psycopg2.OperationalError" in str(e):
                        print(f"-- OperationalError while fetching data for {plant['PlantName']} --")
                        print("Traceback:", traceback.format_exc())
                        failed_plants.append(plant["PlantName"])
                        continue
                    else:
                        print(f"Error processing plant {plant['PlantName']}: {str(e)}")
                        failed_plants.append(plant["PlantName"])
                finally:
                    signal.alarm(0)  # Reset the alarm
                    
            except Exception as e:
                print(f"Outer exception processing plant {plant['PlantName']}: {str(e)}")
                failed_plants.append(plant["PlantName"])
                continue
        
        print("*"*50)
        print(f"-- Data Insertion to lpg_operations_data completed --")
        print(f"-- Successfully processed {len(successful_plants)} plants: {', '.join(successful_plants)}")
        print(f"-- Failed to process {len(failed_plants)} plants: {', '.join(failed_plants)}")
        print("*"*50)
        
        # Only run summary generation if at least one plant was processed
        if successful_plants:
            generate_lpg_operations_summary.generate_summary()
        else:
            print("No plants were successfully processed, skipping summary generation")
        
    except Exception as e:
        print("*-"*25)
        print("-- Exception in fetching the operations data -- ")
        print("Traceback:", traceback.format_exc())
        
        # Clean up on error
        try:
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
        except Exception as cleanup_error:
            print(f"Error during cleanup: {str(cleanup_error)}")