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
    print(f"Inserting {len(data)} rows to {table_name}")
    creds = credential_loader.get_credentials('APP_DB')
    pg_conn = psycopg2.connect(
                host=creds['host'],
                database=creds['database'],
                user=creds['user'],
                password=creds['password'],
                port=int(creds['port']),
                connect_timeout=10
            )    
    table_create_sql = ''
    cur = pg_conn.cursor()
    dtype_dict = {'String':str('text'),'Int64': str('bigint'), 'Int32': str('bigint'), 'Boolean': str('text'), 'Float64': str('double precision'),'Float32': str('double precision'),
                  'Object': str('text'), 'Datetime': str('timestamp'), 'Utf8': str('text'), "Datetime(time_unit='us', time_zone=None)": str('timestamp'), "Datetime(time_unit='ns', time_zone=None)": str('timestamp')}
    
    col_dtype = {col: data[col].dtype for col in data.columns}
    for col, dty in col_dtype.items():
        dty = dtype_dict.get(str(dty))
        table_create_sql += f'"{col}" {dty},'
    table_create_sql = table_create_sql[:-1]
    
    create_table_index = f'CREATE INDEX IF NOT EXISTS "{table_name}_index" ON "{table_name}" ("Date","Plant Name","system_id")'
    table_create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({table_create_sql})'
    print("Creating table if not exists...")
    cur.execute(table_create_sql)
    pg_conn.commit()
    cur.execute(create_table_index)
    pg_conn.commit()

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
        batch_size = 100000  # Process in smaller batches
        for g, split_df in data.group_by(len(data)// batch_size):
            csv_file = f'/tmp/{table_name}_{g}.csv'
            split_df.write_csv(csv_file, separator='~')
            with open(csv_file, 'r') as f:
                cur.copy_expert(query, f)
                pg_conn.commit()
            # Remove the temporary file immediately after using it
            if os.path.exists(csv_file):
                os.remove(csv_file)
                
        cur.close()
        pg_conn.close()
        print(f"-- Data Inserted to {table_name} --")
    except Exception as e:
        print(f"Error inserting data: {str(e)}")
        pg_conn.rollback()  # Rollback on error
        cur.close()
        pg_conn.close()
        raise Exception(e)


def fetch_data(query, getData=False, params=None, timeout=10, query_timeout=30, chunk_size=50000):
    """
    Fetch data from database with both connection and query timeout handling,
    supporting chunked data retrieval for large datasets
    """    
    query  = query.replace(";","")
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
        cursor.execute(f"SET statement_timeout = {query_timeout * 1000};")        
        
    except Exception as e:
        print(f"Database connection error for {params.get('PlantName', 'unknown')}: {str(e)}")
        return pl.DataFrame() if getData else None
        
    try:
        print("-" * 50)
        print(f"Running Query with {query_timeout}s timeout...")
        print(query)
        
        if not getData:
            cursor.execute(query)
            resp = cursor.fetchone()
            cursor.close()
            pg_conn.close()
            return resp[0] if resp else None
        else:
            # For chunked data retrieval
            if "LIMIT" not in query.upper():
                base_query = query.rstrip(';')
                base_query += f" LIMIT {chunk_size} OFFSET "
            else:
                print("Query already contains LIMIT - not using chunking")
                cursor.execute(query)
                data = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                data = pd.DataFrame.from_records(data, columns=columns)
                data = pl.from_pandas(data)
                cursor.close()
                pg_conn.close()
                return data
                
            # Chunked retrieval for large datasets
            all_data = []
            offset = 0
            while True:
                chunk_query = f"{base_query} {offset};"
                print(f"Fetching chunk with offset {offset}, limit {chunk_size}...")
                
                cursor.execute(chunk_query)
                chunk_data = cursor.fetchall()
                
                if not chunk_data:  # No more data
                    break
                    
                print(f"Retrieved {len(chunk_data)} records in this chunk")
                if not all_data:  # First chunk
                    columns = [column[0] for column in cursor.description]
                
                all_data.extend(chunk_data)
                offset += chunk_size
                
                # Break if we got fewer rows than the chunk size
                if len(chunk_data) < chunk_size:
                    break
                    
                # Safety limit to prevent infinite loops
                if offset > 1000000:  # 1 million record limit
                    print("Reached maximum record limit (1M)")
                    break
                    
            print(f'Total Records: {len(all_data)}')
            print("-" * 50)
            
            # Convert to DataFrame
            if all_data:
                data = pd.DataFrame.from_records(all_data, columns=columns)
                data = pl.from_pandas(data)
                cursor.close()
                pg_conn.close()
                return data
            else:
                cursor.close()
                pg_conn.close()
                return pl.DataFrame()
                
    except psycopg2.errors.QueryCanceled:
        print(f"Query timed out after {query_timeout} seconds - skipping this plant")
        cursor.close()
        pg_conn.close()
        return pl.DataFrame() if getData else None
    except Exception as e:
        print(f"Query execution error: {str(e)}")
        cursor.close()
        pg_conn.close()
        return pl.DataFrame() if getData else None


def get_data_chunks(params):
    """Process data retrieval in chunks with better error handling"""
    table_name = "lpg_operations_data"
    plant_name = params['PlantName']
    
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
            print(f"No existing plants found in summary table for {plant_name}")
            first_insertion = True
        elif plant_name.lower() not in plant_check["short_name"].to_list():
            print(f"Plant {plant_name} not found in existing records - first insertion")
            first_insertion = True
        
        # Get max date or use default
        if first_insertion:
            # For first insertion, get only recent data (last 30 days)
            thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            max_date = thirty_days_ago
            print(f"First insertion for {plant_name} using date {max_date} (30 days ago)")
        else:
            query = f""" SELECT MAX(process_date) FROM "lpg_operations_summary" WHERE "short_name"='{plant_name.lower()}'; """    
            max_date = fetch_data(query, getData=False, params=app_db_params)
            if max_date is None:
                # If no max date found, get only recent data (last 7 days)
                seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                max_date = seven_days_ago
                print(f"No max date found for {plant_name}, using date {max_date} (7 days ago)")
        
        # Query without LIMIT - the fetch_data function will handle chunking
        query = f""" 
            SELECT * FROM production_log 
            WHERE "process_date" > '{max_date}'
            ORDER BY "process_date" ASC
        """
        
        # Get data with query timeout and chunking
        print(f"Fetching data for plant {plant_name} with chunking...")
        data = fetch_data(
            query, 
            getData=True, 
            params=params, 
            timeout=10, 
            query_timeout=30,  # Shorter timeout per chunk
            chunk_size=50000   # Smaller chunks
        )
        
        if data is None or data.is_empty():
            print(f"-- No data or query timed out for plant {plant_name} --")
            return False
            
        data = data.with_columns(pl.lit(params["PlantName"]).alias("Plant Name"))
        Date = datetime.datetime.now()
        data = data.with_columns(pl.lit(Date).alias("Date"))
        print(f"Length of data for {plant_name}: {len(data)}")
        
        # Insert data
        insertToDB(data, table_name)
        print(f"Successfully processed plant {plant_name}")
        return True
        
    except Exception as e:
        print(f"Error in get_data for plant {plant_name}: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return False


def process_plant(plant):
    """Process a single plant - to be used with ThreadPoolExecutor"""
    try:
        print(f"Starting processing for plant: {plant['PlantName']}")
        
        params = {
            "PlantName": plant["PlantName"],
            "host": plant["host_ip"],
            "database": plant["db_database"],
            "user": plant["db_user"],
            "password": plant["db_password"],
            "port": 5432
        }
        
        # Set timeout for this plant's processing
        start_time = datetime.datetime.now()
        max_processing_time = datetime.timedelta(minutes=5)
        
        success = get_data_chunks(params)
        
        processing_time = datetime.datetime.now() - start_time
        print(f"Plant {plant['PlantName']} processed in {processing_time.total_seconds():.2f} seconds")
        
        return plant["PlantName"], success
    except Exception as e:
        print(f"Error processing plant {plant['PlantName']}: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return plant["PlantName"], False
    
    
# if __name__=="__main__":
#     try:
#         plants = pl.read_csv("/opt/ceg/algo/orchestrator/sync_services/lpg/LPG_PLANTS_CREDENTIALS.csv")        
#         successful_plants = []
#         failed_plants = []
        
#         # Set up parallel processing
#         max_workers = min(10, len(plants))  # Use up to 10 workers but not more than the number of plants
#         print(f"Processing {len(plants)} plants using {max_workers} parallel workers")
        
#         with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
#             # Submit all plants for processing
#             future_to_plant = {
#                 executor.submit(process_plant, plant): plant["PlantName"] 
#                 for plant in plants.iter_rows(named=True)
#             }
            
#             # Process results as they complete
#             for future in concurrent.futures.as_completed(future_to_plant):
#                 plant_name = future_to_plant[future]
#                 try:
#                     name, success = future.result()
#                     if success:
#                         successful_plants.append(name)
#                         print(f"Successfully processed plant: {name}")
#                     else:
#                         failed_plants.append(name)
#                         print(f"Failed to process plant: {name}")
#                 except Exception as e:
#                     failed_plants.append(plant_name)
#                     print(f"Exception during processing plant {plant_name}: {str(e)}")
        
#         print("*"*50)
#         print(f"-- Data Insertion to lpg_operations_data completed --")
#         print(f"-- Successfully processed {len(successful_plants)} plants: {', '.join(successful_plants)}")
#         print(f"-- Failed to process {len(failed_plants)} plants: {', '.join(failed_plants)}")
#         print("*"*50)
        
#         # Only run summary generation if at least one plant was processed
#         if successful_plants:
#             generate_lpg_operations_summary.generate_summary()
#         else:
#             print("No plants were successfully processed, skipping summary generation")
        
#     except Exception as e:
#         print("*-"*25)
#         print("-- Exception in fetching the operations data -- ")
#         print("Traceback:", traceback.format_exc())
        
#         # Clean up on error - but only if there's a catastrophic failure
#         try:
#             creds = credential_loader.get_credentials('APP_DB')
#             pg_conn = psycopg2.connect(
#                         host=creds["host"],
#                         database=creds["database"],
#                         user=creds["user"],
#                         password=creds["password"],
#                         port=int(creds["port"])
#                     )
#             cursor = pg_conn.cursor()
#             query = f""" TRUNCATE lpg_operations_data; """
#             cursor.execute(query)
#             pg_conn.commit()
#             cursor.close()
#             pg_conn.close()
#             print('-- Removed the data from lpg_operations_data table --')
#         except Exception as cleanup_error:
#             print(f"Error during cleanup: {str(cleanup_error)}")

if __name__=="__main__":
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
        
        plants = pl.read_csv("/opt/ceg/algo/orchestrator/sync_services/lpg/LPG_PLANTS_CREDENTIALS.csv")        
        successful_plants = []
        failed_plants = []
        
        # Set up parallel processing
        max_workers = min(10, len(plants))  # Use up to 10 workers but not more than the number of plants
        print(f"Processing {len(plants)} plants using {max_workers} parallel workers")
        
        # Add a timeout for the entire process
        overall_timeout = 600  # 10 minutes total timeout
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all plants for processing
            futures = {}
            for plant in plants.iter_rows(named=True):
                future = executor.submit(process_plant, plant)
                futures[future] = plant["PlantName"]
            
            # Process results as they complete
            completed_futures = []
            try:
                for future in concurrent.futures.as_completed(futures, timeout=overall_timeout):
                    completed_futures.append(future)
                    plant_name = futures[future]
                    try:
                        name, success = future.result(timeout=60)  # 60-second timeout per plant result
                        if success:
                            successful_plants.append(name)
                            print(f"Successfully processed plant: {name}")
                        else:
                            failed_plants.append(name)
                            print(f"Failed to process plant: {name}")
                    except concurrent.futures.TimeoutError:
                        failed_plants.append(plant_name)
                        print(f"Timeout waiting for result from plant: {plant_name}")
                    except Exception as e:
                        failed_plants.append(plant_name)
                        print(f"Exception during processing plant {plant_name}: {str(e)}")
            except concurrent.futures.TimeoutError:
                # Overall timeout reached
                print(f"Overall timeout of {overall_timeout} seconds reached. Cancelling remaining tasks.")
                # Add any unprocessed plants to failed list
                for future, plant_name in futures.items():
                    if future not in completed_futures:
                        failed_plants.append(plant_name)
                        print(f"Cancelled processing for plant: {plant_name}")
                        future.cancel()
        
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
        
        # Clean up on error - but only if there's a catastrophic failure
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