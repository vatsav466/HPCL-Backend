import sys
import json
import base64
import typing
import asyncio
import cx_Oracle
import traceback
import pandas as pd
import polars as pl
import pyarrow as pa
from rabbitmq_producer import RabbitMQProducer
from sshtunnel import SSHTunnelForwarder
import time

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

# Load config file
with open("config.json", "r", encoding="utf-8") as config_file:
    config = json.load(config_file)

# Extract Oracle credentials and table configs
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
                
            # Convert DataFrame to Polars, ensuring correct data types
            # try:
            #     return pl.from_pandas(final_df, use_pyarrow=True)
            # except Exception as e:
            #     print("Error converting DataFrame with PyArrow:", e)

            # Convert columns manually if PyArrow fails
            for col in final_df.columns:
                if pd.api.types.is_integer_dtype(final_df[col]):
                    final_df[col] = final_df[col].astype("int64")  # Convert nullable int to standard int
                elif pd.api.types.is_float_dtype(final_df[col]):
                    final_df[col] = final_df[col].astype("float64")
                elif pd.api.types.is_object_dtype(final_df[col]):
                    final_df[col] = final_df[col].astype("string")

            return pl.from_pandas(final_df)

        except Exception as e:
            print(f"Error fetching data for {table_name}: {e}")
            return None

        except cx_Oracle.Error as err:
            print(err)
            traceback.print_exc(file=sys.stdout)
            return pl.DataFrame()

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




import time
import asyncio
import traceback
import sys
import polars as pl  # Assuming data is fetched as polars DataFrame

class DataMonitor:
    def __init__(self, oracle, table_configs, sleep_duration=10):
        self.oracle = oracle
        self.table_configs = table_configs
        self.table_names = list(table_configs.keys())
        self.sleep_duration = sleep_duration
        self.previous_data = {}  
        self.last_full_dump_time = {}  
        self.last_send_time = {}  
        self.accumulated_changes = {}  
        self.last_sent_record = {}  

        current_time = time.time()
        for table in table_configs:
            self.last_full_dump_time[table] = current_time - table_configs[table].get("max_full_dump", 3000) + 10
            self.last_send_time[table] = current_time
            self.accumulated_changes[table] = []  
            self.last_sent_record[table] = None  

    async def incremental_check(self, table_name, current_records, check_columns):
        """Check for incremental changes in monitored columns."""
        try:
            if not current_records:
                print(f"No data found for table {table_name}")
                return []
            
            if table_name not in self.previous_data:
                return current_records  # First-time, send all data

            previous_records = self.previous_data[table_name]
            if not previous_records:
                return current_records  # First-time, send all data

            previous_dict = {self._create_record_key(record, check_columns): record for record in previous_records}

            changed_records = []
            for current in current_records:
                key_fields = self._create_record_key(current, check_columns)

                if key_fields not in previous_dict:
                    changed_records.append(current)
                    continue

                previous = previous_dict[key_fields]
                for col in check_columns:
                    if col in current and col in previous and self.is_significant_change(current[col], previous[col]):
                        changed_records.append(current)
                        break

            return changed_records
        except Exception as e:
            print(f"Error in incremental_check for {table_name}: {e}")
            traceback.print_exc()
            return []

    async def default_check(self, table_name, current_records):
        """Check for new records in non-incremental tables."""
        try:
            if not current_records:
                return []

            if table_name not in self.previous_data:
                return current_records

            previous_records = self.previous_data[table_name]
            if not previous_records:
                return current_records

            previous_dict = {self._create_record_key(record): record for record in previous_records}
            return [record for record in current_records if self._create_record_key(record) not in previous_dict]

        except Exception as e:
            print(f"Error in default_check for {table_name}: {e}")
            traceback.print_exc()
            return []

    async def fetch_data(self):
        """Fetch data asynchronously from Oracle tables."""
        all_data = {}

        try:
            tasks = [self.oracle.get_data(table_name=table) for table in self.table_names]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for table_name, result in zip(self.table_names, results):
                try:
                    if isinstance(result, Exception):
                        print(f"Error fetching data for {table_name}: {str(result)}")
                        all_data[table_name] = []
                        continue

                    if isinstance(result, dict) and "message" in result:
                        print(f"Error fetching data for {table_name}: {result.get('message')}")
                        all_data[table_name] = []
                        continue

                    if isinstance(result, pl.DataFrame) and result.shape[0] > 0:
                        all_data[table_name] = result.to_dicts()
                    else:
                        all_data[table_name] = []

                except Exception as e:
                    print(f"Error processing data for {table_name}: {e}")
                    traceback.print_exc()
                    all_data[table_name] = []

            return all_data
        except Exception as e:
            print(f"Error in fetch_data: {e}")
            traceback.print_exc()
            return {}

    async def compare_and_send(self, current_data):
        """Compare current data with previous data and send only changes."""
        try:
            if not current_data:
                return

            current_time = time.time()
            changed_data = {}

            for table_name, records in current_data.items():
                config = self.table_configs.get(table_name, {})
                interval = config.get("interval", 60)
                max_full_dump = config.get("max_full_dump", 3000)
                last_send = self.last_send_time.get(table_name, 0)
                last_full_dump = self.last_full_dump_time.get(table_name, 0)
                incremental = config.get("incremental", False)

                if max_full_dump > 0 and (current_time - last_full_dump) >= max_full_dump:
                    changed_data[table_name] = records
                    self.last_full_dump_time[table_name] = current_time
                    self.last_send_time[table_name] = current_time
                    self.accumulated_changes[table_name] = []
                    self.last_sent_record[table_name] = None
                    continue

                if incremental:
                    check_columns = config.get("increment_check", [])
                    new_records = await self.incremental_check(table_name, records, check_columns)

                    if self.last_sent_record.get(table_name) is not None:
                        new_records = [r for r in new_records if not self._records_equal(r, self.last_sent_record[table_name])]

                    if new_records and (current_time - last_send) >= interval:
                        changed_data[table_name] = [new_records[0]]
                        self.last_sent_record[table_name] = new_records[0]
                        self.last_send_time[table_name] = current_time

                else:
                    new_records = await self.default_check(table_name, records)
                    if new_records:
                        self.accumulated_changes.setdefault(table_name, []).extend(new_records)

                        if (current_time - last_send) >= interval and self.accumulated_changes.get(table_name):
                            changed_data[table_name] = self.accumulated_changes[table_name]
                            self.accumulated_changes[table_name] = []
                            self.last_send_time[table_name] = current_time

            if changed_data:
                RabbitMQProducer().send_to_rabbitmq(changed_data)

            for table_name, records in current_data.items():
                if records:
                    self.previous_data[table_name] = records

        except Exception as e:
            print(f"Error in compare_and_send: {e}")
            traceback.print_exc()

    def _create_record_key(self, record, exclude_columns=None):
        """Create a hashable key from a record dictionary."""
        if exclude_columns is None:
            exclude_columns = []
        return tuple(sorted((k, str(v)) for k, v in record.items() if k not in exclude_columns))

    def is_significant_change(self, value1, value2):
        """Strict comparison for numbers, ensuring even small changes are detected."""
        if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
            return abs(value1 - value2) > 1e-6
        return value1 != value2  

    def _records_equal(self, record1, record2):
        """Compare two records for equality."""
        if record1 is None or record2 is None:
            return record1 is record2
        if set(record1.keys()) != set(record2.keys()):
            return False
        for key in record1:
            if self.is_significant_change(record1[key], record2[key]):
                return False
        return True

    async def run(self):
        while True:
            try:
                current_data = await self.fetch_data()
                if current_data:
                    await self.compare_and_send(current_data)
                await asyncio.sleep(self.sleep_duration)
            except Exception as e:
                print(f"Error in run loop: {e}")
                traceback.print_exc()
                await asyncio.sleep(30)


async def main():
    try:
        oracle = Oracle(oracle_config)  # Initialize Oracle connection using your existing class
        
        # Test connection
        connection_test = await oracle.test_connection()
        if connection_test.get("status", False):
            print("Successfully connected to Oracle database")
        else:
            print(f"Failed to connect to Oracle: {connection_test.get('message', 'Unknown error')}")
            return
        
        # Initialize and run monitor
        monitor = DataMonitor(oracle, table_names, sleep_duration=10)
        await monitor.run()
        
    except Exception as e:
        print(f"Fatal error in main: {e}")
        traceback.print_exc(file=sys.stdout)
if __name__ == "__main__":
    asyncio.run(main())