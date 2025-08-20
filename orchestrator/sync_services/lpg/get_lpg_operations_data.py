import urdhva_base
import os
import sys
import psycopg2
import pandas as pd
import polars as pl
import socket
import datetime
import traceback
import mysql.connector
import concurrent.futures
import signal
import generate_lpg_operations_summary
sys.path.append("/opt/ceg/algo")
import orchestrator.dbconnector.credential_loader as credential_loader

logger = urdhva_base.logger.Logger.getInstance("lpg_operations_data_sync_log")

def create_extraction_log_table():
    """Create plant_extraction_log table if it doesn't exist"""
    try:
        creds = credential_loader.get_credentials('APP_DB')
        pg_conn = psycopg2.connect(
                    host=creds['host'],
                    database=creds['database'],
                    user=creds['user'],
                    password=creds['password'],
                    port=int(creds['port']),
                    connect_timeout=10
                )
        cur = pg_conn.cursor()

        # Create extraction log table if not exists
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS plant_extraction_log (
            plant_name VARCHAR(255),
            last_extracted_date TIMESTAMP,
            last_processed_date TIMESTAMP,
            extraction_status VARCHAR(50),
            PRIMARY KEY (plant_name)
        );
        """
        cur.execute(create_table_sql)
        pg_conn.commit()
        cur.close()
        pg_conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating extraction log table: {str(e)}")
        print(f"Error creating extraction log table: {str(e)}")
        return False

def get_extraction_date(plant_name, default_days=5):
    """Get the last extracted date for a plant or initialize if not exists"""
    try:
        creds = credential_loader.get_credentials('APP_DB')
        pg_conn = psycopg2.connect(
                    host=creds['host'],
                    database=creds['database'],
                    user=creds['user'],
                    password=creds['password'],
                    port=int(creds['port']),
                    connect_timeout=10
                )
        cur = pg_conn.cursor()

        # Check if plant exists in tracking table
        query = """
        SELECT last_extracted_date FROM plant_extraction_log
        WHERE plant_name = %s
        """
        cur.execute(query, (plant_name,))
        result = cur.fetchone()

        if result:
            last_date = result[0]
            print(f"Found last extracted date for {plant_name}: {last_date}")
        else:
            # Initialize new plant with default date (N days ago)
            # default_date = (datetime.datetime.now() - datetime.timedelta(days=default_days)).strftime("%Y-%m-%d")
            default_date = "2025-04-01"
            insert_query = """
            INSERT INTO plant_extraction_log
            (plant_name, last_extracted_date, last_processed_date, extraction_status)
            VALUES (%s, %s, %s, 'NEW')
            """
            cur.execute(insert_query, (plant_name, default_date, default_date))
            pg_conn.commit()
            last_date = default_date
            print(f"Initialized new plant {plant_name} with default date: {default_date}")

        cur.close()
        pg_conn.close()
        return last_date
    except Exception as e:
        logger.error(f"Error getting extraction date for {plant_name}: {str(e)}")
        print(f"Error getting extraction date for {plant_name}: {str(e)}")
        # Fallback to 7 days ago if there's an error
        return (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")

def update_extraction_log(plant_name, status, max_date=None):
    """Update extraction log after processing a plant"""
    try:
        creds = credential_loader.get_credentials('APP_DB')
        pg_conn = psycopg2.connect(
                    host=creds['host'],
                    database=creds['database'],
                    user=creds['user'],
                    password=creds['password'],
                    port=int(creds['port']),
                    connect_timeout=10
                )
        cur = pg_conn.cursor()

        # Update successful extraction with max date
        if status == "EXTRACTED" and max_date:
            query = """
            UPDATE plant_extraction_log
            SET last_extracted_date = %s,
                extraction_status = %s
            WHERE plant_name = %s
            """
            cur.execute(query, (max_date, status, plant_name))
        # Update after summary generation
        elif status == "PROCESSED":
            query = """
            UPDATE plant_extraction_log
            SET last_processed_date = last_extracted_date,
                extraction_status = %s
            WHERE plant_name = %s
            """
            cur.execute(query, (status, plant_name))
        # Update on failure
        else:
            query = """
            UPDATE plant_extraction_log
            SET extraction_status = %s
            WHERE plant_name = %s
            """
            cur.execute(query, (status, plant_name))

        pg_conn.commit()
        cur.close()
        pg_conn.close()
        print(f"Updated extraction log for {plant_name}: {status}")
        return True
    except Exception as e:
        logger.error(f"Error updating extraction log for {plant_name}: {str(e)}")
        print(f"Error updating extraction log for {plant_name}: {str(e)}")
        return False

def insertToDB(data, table_name):
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
        return True
    except Exception as e:
        logger.error(f"Error inserting data: {str(e)}")
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
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((params["host"], int(params["port"])))
        if not result == 0:
            logger.error(f"Connection timed out to {params['host']}:{params['port']} after {timeout} seconds")
            print(f"Connection timed out to {params['host']}:{params['port']} after {timeout} seconds")
            return pl.DataFrame() if getData else None
    except Exception as e:
        logger.error(f"Socket connection error: {str(e)}")
        print(f"Socket connection error: {str(e)}")
        return pl.DataFrame() if getData else None
    finally:
        sock.close()

    # Database connection with timeout
    try:
        if params["db_type"] == "mysql":
            pg_conn = mysql.connector.connect(
                host=params["host"],
                database=params["database"],
                user=params["user"],
                password=params["password"],
                port=int(params["port"]),
                connection_timeout=timeout
            )
            cursor = pg_conn.cursor()
            # Set statement timeout (in milliseconds) — note: MySQL calls this `max_execution_time`
            cursor.execute(f"SET SESSION max_execution_time = {query_timeout * 1000};")
        else:
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
        logger.error(f"Database connection error for {params.get('PlantName', 'unknown')}: {str(e)}")
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
                if offset > 2000000:  # 2 million record limit
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
        logger.error(f"Query timed out after {query_timeout} seconds - skipping this plant")
        print(f"Query timed out after {query_timeout} seconds - skipping this plant")
        cursor.close()
        pg_conn.close()
        return pl.DataFrame() if getData else None
    except Exception as e:
        logger.error(f"Query execution error: {str(e)}")
        print(f"Query execution error: {str(e)}")
        cursor.close()
        pg_conn.close()
        return pl.DataFrame() if getData else None

def get_data_chunks(params):
    """Process data retrieval in chunks with better error handling"""
    table_name = "lpg_operations_data"
    plant_name = params['PlantName']

    try:
        # Get last extracted date from extraction log
        last_extracted_date = get_extraction_date(plant_name)

        # Query without LIMIT - the fetch_data function will handle chunking
        if params["db_type"] == "mysql":
            production_table = "production_data"
        else:
            production_table = "production_log"
        query = f"""
            SELECT * FROM {production_table}
            WHERE process_date > '{last_extracted_date}' AND process_date < NOW()
            ORDER BY process_date ASC
        """

        # Get data with query timeout and chunking
        print(f"Fetching data for plant {plant_name} with chunking...")
        data = fetch_data(
            query,
            getData=True,
            params=params,
            timeout=15,
            query_timeout=180,  # Shorter timeout per chunk
            chunk_size=25000   # Smaller chunks
        )

        if data is None or data.is_empty():
            logger.error(f"-- No data or query timed out for plant {plant_name} --")
            print(f"-- No data or query timed out for plant {plant_name} --")
            update_extraction_log(plant_name, "NO_DATA")
            return False

        data = data.with_columns(pl.lit(params["PlantName"]).alias("Plant Name"))
        current_date = datetime.datetime.now()
        data = data.with_columns(pl.lit(current_date).alias("Date"))
        print(f"Length of data for {plant_name}: {len(data)}")

        # Get max process_date for updating the extraction log
        if not data.is_empty():
            max_date = data["process_date"].max()
            if max_date:
                print(f"Max process_date for {plant_name}: {max_date}")
            else:
                max_date = last_extracted_date
        else:
            max_date = last_extracted_date

        # Insert data
        if insertToDB(data, table_name):
            # Update extraction log with success and max date
            update_extraction_log(plant_name, "EXTRACTED", max_date)
            print(f"Successfully processed plant {plant_name}")
            return True
        else:
            update_extraction_log(plant_name, "INSERT_FAILED")
            return False

    except Exception as e:
        logger.error(f"Error in get_data for plant {plant_name}: {str(e)}")
        print(f"Error in get_data for plant {plant_name}: {str(e)}")
        print("Traceback:", traceback.format_exc())
        update_extraction_log(plant_name, "FAILED")
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
            "port": plant["port"],
            "db_type": plant["db_type"],
        }

        # Set timeout for this plant's processing
        start_time = datetime.datetime.now()

        success = get_data_chunks(params)

        processing_time = datetime.datetime.now() - start_time
        print(f"Plant {plant['PlantName']} processed in {processing_time.total_seconds():.2f} seconds")

        return plant["PlantName"], success
    except Exception as e:
        logger.error(f"Error processing plant {plant['PlantName']}: {str(e)}")
        print(f"Error processing plant {plant['PlantName']}: {str(e)}")
        print("Traceback:", traceback.format_exc())
        update_extraction_log(plant["PlantName"], "FAILED")
        return plant["PlantName"], False

def update_processed_plants(successful_plants):
    """Update extraction log with processed status after summary generation"""
    try:
        for plant_name in successful_plants:
            update_extraction_log(plant_name, "PROCESSED")
        return True
    except Exception as e:
        logger.error(f"Error updating processed plants: {str(e)}")
        print(f"Error updating processed plants: {str(e)}")
        return False

def generate_summary_wrapper():
    """Wrapper for summary generation with proper error handling"""
    try:
        # Call the existing summary generation function
        generate_lpg_operations_summary.generate_summary()
        return True
    except Exception as e:
        logger.error(f"Error in summary generation: {str(e)}")
        print(f"Error in summary generation: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return False

if __name__=="__main__":
    try:
        # Create extraction log table if not exists
        create_extraction_log_table()
        
        plants = pl.read_csv("/opt/ceg/algo/orchestrator/sync_services/lpg/LPG_PLANTS_CREDENTIALS.csv")
        # plants = plants.filter((pl.col("id") > 50) & (pl.col("id") <= 60))
        print("plants :", plants)
        successful_plants = []
        failed_plants = []

        # Set up parallel processing
        max_workers = min(10, len(plants))  # Use up to 10 workers but not more than the number of plants
        print(f"Processing {len(plants)} plants using {max_workers} parallel workers")

        # Add a timeout for the entire process
        overall_timeout = 1200  # 10 minutes total timeout

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
                            logger.error(f"Failed to process plant: {name}")
                            print(f"Failed to process plant: {name}")
                    except concurrent.futures.TimeoutError:
                        failed_plants.append(plant_name)
                        update_extraction_log(plant_name, "TIMEOUT")
                        print(f"Timeout waiting for result from plant: {plant_name}")
                        logger.error(f"Timeout waiting for result from plant: {plant_name}")
                    except Exception as e:
                        failed_plants.append(plant_name)
                        update_extraction_log(plant_name, "FAILED")
                        logger.error(f"Exception during processing plant {plant_name}: {str(e)}")
                        print(f"Exception during processing plant {plant_name}: {str(e)}")
            except concurrent.futures.TimeoutError:
                # Overall timeout reached
                print(f"Overall timeout of {overall_timeout} seconds reached. Cancelling remaining tasks.")
                logger.error(f"Overall timeout of {overall_timeout} seconds reached. Cancelling remaining tasks.")
                # Add any unprocessed plants to failed list
                for future, plant_name in futures.items():
                    if future not in completed_futures:
                        failed_plants.append(plant_name)
                        update_extraction_log(plant_name, "CANCELLED")
                        print(f"Cancelled processing for plant: {plant_name}")
                        logger.error(f"Cancelled processing for plant: {plant_name}")
                        future.cancel()

        print("*"*50)
        print(f"-- Data Insertion to lpg_operations_data completed --")
        print(f"-- Successfully processed {len(successful_plants)} plants: {', '.join(successful_plants)}")
        print(f"-- Failed to process {len(failed_plants)} plants: {', '.join(failed_plants)}")
        print("*"*50)

        # Only run summary generation if at least one plant was processed
        if successful_plants:
            # Call summary generation
            summary_success = generate_summary_wrapper()
            if summary_success:
                # Update all successful plants as processed
                update_processed_plants(successful_plants)
                print("Summary generation completed successfully")
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
                    logger.error(f"Error during cleanup: {str(cleanup_error)}")
                    print(f"Error during cleanup: {str(cleanup_error)}")
            else:
                logger.error("Summary generation failed")
                print("Summary generation failed")
        else:
            logger.error("No plants were successfully processed, skipping summary generation")
            print("No plants were successfully processed, skipping summary generation")

    except Exception as e:
        print("*-"*25)
        print("-- Exception in fetching the operations data -- ")
        print("Traceback:", traceback.format_exc())
        logger.error(f"Exception in fetching the operations data: {str(e)}")        