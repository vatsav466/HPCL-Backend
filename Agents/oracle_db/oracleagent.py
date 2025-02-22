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

with open("config.json", "r") as config_file:
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
        connection = cx_Oracle.connect(
            self.params["user_name"],
            self.params["password"],
            self.params["dns"]
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
            connection = self.get_connection()
            # connection.close()
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
            # connection.close()
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
            # connection.close()
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
            # connection.close()
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
            # connection.close()
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
            # cursor.close()
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
            # cursor.close()
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
            # cursor.close()
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
            # cursor.close()
            await self.close_connection(connection)
            if debug:
                return {
                    "status": True, "message": "Success", "data": final_df.to_dict(orient='records')
                }
            print("final_df ", final_df)
            final_df.to_csv(f"{table_name}.csv", mode='a', index=False, header=False)
            print("files are genarated")
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
            # print("execute query: ", query)
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
        self.previous_data = []

    async def compare_and_send(self, current_data):
        """
        Compare current data with previous data and send only changed records to RabbitMQ
        """
        # Find new records (records in current_data but not in previous_data)
        try:
            new_records = [record for record in current_data if record not in self.previous_data]

            if new_records:
                RabbitMQProducer().send_to_rabbitmq(new_records)  # Ensure async call
            print("test data", current_data)
            self.previous_data = current_data  # Update previous data
            print("self.previous_data  ", self.previous_data)
        
        except Exception as e:
            print(traceback.format_exc())
            print(e)

    async def fetch_data(self):
        """
        Fetch data asynchronously from Oracle tables.
        """
        try:
            tasks = [self.oracle.get_data(table_name=table) for table in self.table_names]
            results = await asyncio.gather(*tasks)

            print("results ---> ", results)  # Debugging output

            processed_results = {}
            sap_id = self.config.get("sap_id")  # Fetch sap_id from config

            for table, item in zip(self.table_names, results):
                if isinstance(item, dict):  # Handle error messages
                    print(f"Error in {table}:", item)
                    continue  # Skip errors
                
                if isinstance(item, pl.DataFrame) and item.shape[0] > 0:  # Skip empty DataFrames
                    records = item.to_dicts()
                    
                    # Add sap_id to each record
                    for record in records:
                        record["sap_id"] = sap_id  
                    
                    processed_results[table] = records  # Store data under table name
            
            print("processed_results --> ", processed_results)
            return processed_results  # Return as a dictionary
        except Exception as e:
            print(traceback.format_exc())
            print(e)

    async def run(self):
        """
        Periodically check Oracle DB for data changes
        """
        try:
            while True:
                print("after 30 seconds")
                current_data = await self.fetch_data()
                await self.compare_and_send(current_data)
                await asyncio.sleep(self.sleep_duration)
                print("check every 30 seconds")
        except Exception as e:
            print(traceback.format_exc())
            print(e)

async def main():
    oracle = Oracle(oracle_config)  # Initialize Oracle connection
    monitor = DataMonitor(oracle, table_names, sleep_duration=10)
    await monitor.run()  # Start monitoring

if __name__ == "__main__":
    asyncio.run(main())
