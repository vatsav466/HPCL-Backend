import sys
import json
import base64
import typing
import asyncio
import cx_Oracle
import traceback
import pandas as pd
import polars as pl
from rabbitmq_producer import RabbitMQProducer
from sshtunnel import SSHTunnelForwarder

# Set stdout encoding to UTF-8 to handle non-ASCII characters
sys.stdout.reconfigure(encoding='utf-8')

dtype_map = {
            'String': 'VARCHAR2(255)',
            'Int64': 'NUMBER',
            'Int32': 'NUMBER',
            'Boolean': 'NUMBER(1)',
            'Float64': 'NUMBER',
            'Float32': 'NUMBER',
            'Object': 'VARCHAR2(4000)',
            'Datetime': 'DATE',
            'Utf8': 'NVARCHAR2(255)',
            "Datetime(time_unit='us', time_zone=None)": 'DATE'
        }

with open("config.json", "r", encoding="utf-8") as config_file:
    config = json.load(config_file)

# Extract Oracle credentials and table names
oracle_config = config["oracle"]
table_names = config["oracle_tables"]
sap_id = config["sap_id"]

class BaseAction:
    def __init__(self, params: typing.Dict, sleep_duration=30):
        self.params = params
        self.previous_data = set()
        self.sleep_duration = sleep_duration


class Oracle(BaseAction):
    def __init__(self, params: typing.Dict):
        super().__init__(params)

    async def get_connection(self):
        self.params['dns'] = f"{self.params['host']}:{self.params['port']}"

        if self.params.get('sid', ''):
            self.params['dns'] += f"/{self.params['sid']}"
        elif self.params.get('service_name', ''):
            self.params['dns'] += f"/{self.params['service_name']}"
        elif self.params.get('database_name', ''):
            self.params['dns'] += f"/{self.params['database_name']}"
        
        # Set client character set to AL32UTF8 to support all Unicode characters
        connection = cx_Oracle.connect(
            self.params["user_name"],
            self.params["password"],
            self.params["dns"],
            encoding="UTF-8",
            nencoding="UTF-8"
        )
        return connection

    async def get_default_schema(self):
        return None

    async def close_connection(self, connection):
        if connection:
            connection.close()
        if 'tunnel' in self.params.keys():
            self.params['tunnel'].stop()

    async def test_connection(self):
        try:
            connection = await self.get_connection()
            await self.close_connection(connection)
            return {
                "status": True, "message": "Connected to Oracle",
                "data": []
            }
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": "Unable to connect to Oracle",
                "data": []
            }

    async def get_schema(self, debug=False, **kwargs):
        """
        @description:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT username FROM sys.all_users")
            row = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            df = pd.DataFrame({column: [row[i] for row in row] for i, column in enumerate(column_names)})
            await self.close_connection(connection)
            print(df['USERNAME'].unique().tolist())
            df.to_csv("schema-list.csv", index=False)
            return {
                "status": True, "message": "Success",
                "data": df['USERNAME'].unique().tolist()
            }
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": f"Not able to connect {err}", "data": None
            }

    async def table_name(self, schema_name, debug=False, **kwargs):
        """
        @description:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            cursor = connection.cursor()
            cursor.execute(f"""SELECT table_name FROM all_tables WHERE OWNER = '{schema_name}'""")
            row = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            df = pd.DataFrame({column: [row[i] for row in row] for i, column in enumerate(column_names)})
            await self.close_connection(connection)
            print(df['TABLE_NAME'].unique().tolist())
            df.to_csv("tables_list.csv", index=False)
            return {
                "status": True, "message": "Success",
                "data": df['TABLE_NAME'].unique().tolist()
            }
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": f"Not able to connect {err}", "data": None
            }

    async def primary_key(self, schema_name, table_name, debug=False, **kwargs):
        """
        @description:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            cursor = connection.cursor()
            cursor.execute(f"SELECT DISTINCT cols.COLUMN_NAME FROM all_constraints cons, "
                           f"all_cons_columns cols WHERE cols.TABLE_NAME = '{table_name}' "
                           f"AND cons.CONSTRAINT_TYPE = 'P' AND cons.STATUS ='ENABLED'")
            row = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            df = pd.DataFrame({column: [row[i] for row in row] for i, column in enumerate(column_names)})
            await self.close_connection(connection)
            return {
                "status": True, "message": "Success",
                "data": df['COLUMN_NAME'].unique().tolist()
            }
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": f"Not able to connect {err}", "data": None
            }

    async def column_names(self, schema_name, table_name, debug=False, **kwargs):
        """
        @description:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            cursor = connection.cursor()
            cursor.execute(f"""SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE TABLE_NAME='{table_name}'""")
            row = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            df = pd.DataFrame({column: [row[i] for row in row] for i, column in enumerate(column_names)})
            await self.close_connection(connection)
            return {
                "status": True, "message": "Success",
                "data": df['COLUMN_NAME'].unique().tolist()
            }
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": f"Not able to connect {err}", "data": None
            }

    async def create_table(self, schema_name, table_name, table_schema, debug=False, **kwargs):
        """
        @description:
        :param schema_name:
        :param table_name:
        :param table_schema:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            cursor = connection.cursor()
            table_create_sql = ''
            for col, dty in table_schema.items():
                table_create_sql += f'"{col}" {dty}, '
            table_create_sql = table_create_sql[:-1]
            table_create_sql = f"""CREATE TABLE {schema_name}.{table_name} ({table_create_sql})"""
            list_table = await self.table_name(schema_name)
            if table_name not in list_table.get("data", []):
                cursor.execute(table_create_sql)
                connection.commit()
            await self.close_connection(connection)
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)

    async def write_data_from_csv(self, *records, schema_name, table_name, debug=False, **kwargs):
        """
        @description:
        :param records:
        :param schema_name:
        :param table_name:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            cursor = connection.cursor()
            records = records[0]
            if not isinstance(records, pl.DataFrame):
                records = pl.DataFrame(records)

            table_schema: typing.Dict[str, str] = {}
            for c in list(records.columns):
                dtype = str(records[c].dtype)
                if dtype not in dtype_map:
                    table_schema[c] = "text"
                else:
                    table_schema[c] = dtype_map[dtype]

            await self.create_table(schema_name, table_name, table_schema)

            csv_file = f"/tmp/{table_name}.csv"
            records.write_csv(csv_file)
            sql = f"""
            LOAD DATA INFILE '{csv_file}'
            INTO TABLE {schema_name}.{table_name}
            FIELDS TERMINATED BY ','
            OPTIONALLY ENCLOSED BY '"'
            TRAILING NULLCOLS
            """
            cursor.execute(sql)
            connection.commit()
            await self.close_connection(connection)
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)

    async def write_data(self, *records, schema_name, table_name, debug=False, **kwargs):
        """
        @description:
        :param records:
        :param schema_name:
        :param table_name:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            cursor = connection.cursor()
            records = records[0]
            if not isinstance(records, pl.DataFrame):
                records = pl.DataFrame(records)
            query = f"INSERT INTO {schema_name}.{table_name} ({', '.join(records.columns)}) VALUES ({', '.join([':' + col for col in records.columns])})"
            cursor.executemany(query, records.to_dicts())
            connection.commit()
            await self.close_connection(connection)
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)

    async def get_data(
            self,
            table_name,
            query=None,
            columns=None,
            limit=None,
            debug=False,
            schema_name=None,
            **kwargs
    ):
        """
        @description:
        :param args:
        :param schema_name:
        :param table_name:
        :param query:
        :param columns:
        :param limit:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            cursor = connection.cursor()
            if query:
                cursor.execute(query)
            elif schema_name:
                cursor.execute(f"SELECT * FROM {schema_name}.{table_name}")
            else:
                cursor.execute(f"SELECT * FROM {table_name}")
            batch_size = 1000000
            final_df = pd.DataFrame()
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                column_names = [desc[0] for desc in cursor.description]
                df = pd.DataFrame({column: [row[i] for row in rows] for i, column in enumerate(column_names)})
                final_df = pd.concat([final_df, df])
            await self.close_connection(connection)
            if debug:
                return {
                    "status": True, "message": "Success", "data": final_df.to_dict(orient='records')
                }
            
            # Carefully handle encoding when writing to file
            try:
                print("Saving data for table:", table_name)
                final_df.to_csv(f"{table_name}.csv", mode='a', index=False, header=False, encoding='utf-8')
                print(f"Data saved to {table_name}.csv")
            except UnicodeEncodeError:
                print(f"Warning: Encoding issue when saving {table_name}.csv - trying alternate encoding")
                final_df.to_csv(f"{table_name}.csv", mode='a', index=False, header=False, encoding='utf-8-sig')
                
            return pl.from_pandas(final_df)
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": f"Not able to fetch data {err}", "data": []
            }

    async def get_distinct_values(self, schema_name, table_name, column_name, where_clause=None, debug=False, **kwargs):
        """
        @description:
        :param schema_name:
        :param table_name:
        :param column_name:
        :param where_clause:
        :param debug:
        :return:
        """
        try:
            columns_mapping = dict()
            connection = await self.get_connection()
            cursor = connection.cursor()
            for column in column_name:
                query = f'''SELECT DISTINCT "{column}" FROM {schema_name}."{table_name}"'''
                if where_clause:
                    where_query = ''
                    for key, value in where_clause.items():
                        where_query += f'"{key}" = \'{value}\' AND '
                    where_query = where_query[:-5]
                    if where_query:
                        query = f'''SELECT DISTINCT "{column}" FROM {schema_name}."{table_name}" WHERE {where_query}'''
                cursor.execute(query)
                rows = cursor.fetchall()
                list_columns = [desc[0] for desc in cursor.description]
                df = pd.DataFrame({col: [row[i] for row in rows] for i, col in enumerate(list_columns)})
                columns_mapping[column] = df[column].unique().tolist()
            await self.close_connection(connection)
            return {
                "status": True, "message": "Success",
                "data": columns_mapping
            }
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": f"Not able to fetch data {err}", "data": []
            }

    async def execute_query(self, query, debug=False, **kwargs):
        """
        @description:
        :param query:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            cursor = connection.cursor()
            cursor.execute(query)
            records = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            records = {column: [record[i] for record in records] for i, column in enumerate(column_names)}
            records = pd.DataFrame(records)
            await self.close_connection(connection)
            return records.to_dict(orient='records')
        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)
            raise err


class DataMonitor:
    def __init__(self, oracle, table_names, sleep_duration=10):
        self.oracle = oracle
        self.table_names = table_names
        self.sleep_duration = sleep_duration
        self.previous_data = {}  # Initialize as an empty dictionary, not a list
        self.table_queries = table_queries or {}

    async def compare_and_send(self, current_data):
        """
        Compare current data with previous data and send only changed records to RabbitMQ.
        """
        try:
            # Check if current_data is None or empty
            if not current_data:
                print("Warning: No data received to compare. Skipping comparison.")
                return
                
            changed_data = {}  # To store only changed records per table

            for table_name, records in current_data.items():
                if not isinstance(records, list):  # Ensure records are lists
                    print(f"Warning: Expected list for table {table_name}, but got {type(records)}")
                    continue
                
                # Get previous records (if any) for the same table
                previous_records = self.previous_data.get(table_name, [])

                # Find new records (in current_data but not in previous_data)
                new_records = [record for record in records if record not in previous_records]

                if new_records:
                    changed_data[table_name] = new_records  # Store only changed records
            if "HOST_MANUALFANPRINTED" in changed_data:
                for record in changed_data["HOST_MANUALFANPRINTED"]:
                    record["date"] = datetime.date()
                    record["date_time"] = datetime.datetime.now().isoformat()
            # Send only changed records
            if changed_data:
                await RabbitMQProducer().send_to_rabbitmq(changed_data)  # Added await
                print(f"Sent changed data to RabbitMQ for tables: {list(changed_data.keys())}")
            else:
                print("No changes detected. Nothing to send.")
            
            # Update previous_data with the current data
            self.previous_data = current_data.copy()

        except Exception as e:
            print(traceback.format_exc())
            print(f"Error in compare_and_send: {e}")

    async def fetch_data(self):
        """
        Fetch data asynchronously from Oracle tables.
        """
        try:
            tasks = {
                table: self.oracle.get_data(query=f"SELECT *, TO_CHAR(timestamp, 'YYYY-MM-DD') AS timestamp FROM {table}", table_name=table) 
                if table == "HOST_UNAUTHORIZEDFLOW" 
                else self.oracle.get_data(table_name=table, query=query) if query 
                else self.oracle.get_data(table_name=table)
                for table, query in self.table_queries.items()
            }

            # Use asyncio.gather on the values
            result = await asyncio.gather(*tasks.values())

            # Maintain table names with results
            results = dict(zip(tasks.keys(), result))


            # Safe printing with error handling
            try:
                print("Number of results:", len(results))  # Just print the count, not the actual data
            except UnicodeEncodeError:
                print("Note: Unable to print results due to encoding issues")

            processed_results = {}

            for table, item in zip(self.table_names, results):
                if isinstance(item, dict):  # Handle error messages
                    print(f"Error in {table}:", item.get("message", "Unknown error"))
                    continue  # Skip errors
                
                if isinstance(item, pl.DataFrame) and item.shape[0] > 0:  # Skip empty DataFrames
                    try:
                        records = item.to_dicts()
                        
                        # Add sap_id to each record
                        for record in records:
                            record["sap_id"] = sap_id  
                        
                        processed_results[table] = records  # Store data under table name
                    except Exception as e:
                        print(f"Error processing data for table {table}: {e}")
            
            # Safe printing for processed results
            try:
                print(f"Processed data for {len(processed_results)} tables: {list(processed_results.keys())}")
            except UnicodeEncodeError:
                print(f"Processed data for {len(processed_results)} tables (names not printable due to encoding)")
                
            return processed_results  # Return as a dictionary
        except Exception as e:
            print(traceback.format_exc())
            print(f"Error in fetch_data: {e}")
            return {}  # Return empty dict on error, not None

    async def run(self):
        """
        Periodically check Oracle DB for data changes
        """
        try:
            print("Starting data monitoring...")
            while True:
                print(f"Fetching data (checking every {self.sleep_duration} seconds)")
                current_data = await self.fetch_data()
                
                # Only compare if we have data
                if current_data:
                    await self.compare_and_send(current_data)
                else:
                    print("No data fetched, skipping comparison")
                    
                await asyncio.sleep(self.sleep_duration)
        except Exception as e:
            print(traceback.format_exc())
            print(f"Error in run: {e}")
            # Restart the monitoring after a delay
            print("Restarting monitoring in 30 seconds...")
            await asyncio.sleep(30)
            await self.run()

async def main():
    oracle = Oracle(oracle_config)  # Initialize Oracle connection
    monitor = DataMonitor(oracle, table_names, sleep_duration=10)
    await monitor.run()  # Start monitoring

if __name__ == "__main__":
    asyncio.run(main())