import os
import sys
import typing
import asyncpg
import traceback
import pandas as pd
import polars as pl
from sshtunnel import SSHTunnelForwarder
from api_manager.hpcl_ceg_model import CredsModel


class BaseAction:
    def __init__(self, params: typing.Dict):
        self.params = params


class Postgresql(BaseAction):
    def __init__(self, params: typing.Dict):
        super().__init__(params)

    async def get_connection(self):
        if 'connection_name' in self.params.keys():
            self.params = await CredsModel.get(self.params['connection_name'])
        if not isinstance(self.params, dict):
            self.params = self.params.__dict__
        if 'credentials' in self.params.keys():
            self.params = self.params['credentials']
        if self.params.get('is_ssh_tunnel', False):
            tunnel = SSHTunnelForwarder(
                (self.params['ssh_tunnel']['host'], self.params['ssh_tunnel']['port']),
                ssh_username=self.params['ssh_tunnel']['user_name'],
                ssh_pkey=self.params['ssh_tunnel']['private_key'] if 'private_key' in self.params['ssh_tunnel'].keys() else None,
                ssh_password=self.params['ssh_tunnel']['password'] if 'password' in self.params['ssh_tunnel'].keys() else None,
                remote_bind_address=(self.params['host'], self.params['port']),
            )
            tunnel.start()
            self.params['host'] = tunnel.local_bind_host
            self.params['port'] = tunnel.local_bind_port
            self.params['tunnel'] = tunnel
        connection = await asyncpg.connect(
            host=self.params['host'],
            port=self.params['port'],
            user=self.params['user_name'],
            password=self.params['password'],
            database=self.params['database_name']
        )
        return connection

    async def close_connection(self, connection):
        if connection:
            await connection.close()
        if 'tunnel' in self.params.keys():
            self.params['tunnel'].stop()

    async def test_connection(self):
        """
        @description:
        :return:
        """
        try:

            connection = await self.get_connection()
            # await connection.close()
            await self.close_connection(connection)
            return {
                "status": True, "message": "Connected to PostgresSQL",
                "data": []
            }
        except asyncpg.PostgresConnectionError as err:
            # logger.error(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": "Unable to connect to PostgresSQL",
                "data": []
            }

    async def get_databases(self, debug=False, **kwargs):
        """
        @description:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            stmt = await connection.prepare("SELECT datname FROM pg_catalog.pg_database")
            columns = [a.name for a in stmt.get_attributes()]
            data = await stmt.fetch()
            data = pd.DataFrame(data, columns=columns)
            # await connection.close()
            await self.close_connection(connection)
            return {
                "status": True, "message": "Connected to PostgresSQL",
                "data": data['datname'].unique().tolist()
            }
        except asyncpg.PostgresConnectionError as err:
            # logger.error(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": "Unable to connect to PostgresSQL",
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
            stmt = await connection.prepare("SELECT schema_name FROM information_schema.schemata")
            columns = [a.name for a in stmt.get_attributes()]
            data = await stmt.fetch()
            data = pd.DataFrame(data, columns=columns)
            # await connection.close()
            await self.close_connection(connection)
            return {
                "status": True, "message": "Connected to PostgresSQL",
                "data": data['schema_name'].unique().tolist()
            }
        except asyncpg.PostgresConnectionError as err:
            # logger.error(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": "Unable to connect to PostgresSQL",
                "data": []
            }

    async def table_name(self, schema_name, debug=False, **kwargs):
        """
        @description:
        :param schema_name:
        :param debug:
        :return:
        """
        try:
            connection = await self.get_connection()
            stmt = await connection.prepare(
                f"""SELECT table_name FROM information_schema.tables WHERE table_schema='{schema_name}'""")
            columns = [a.name for a in stmt.get_attributes()]
            data = await stmt.fetch()
            data = pd.DataFrame(data, columns=columns)
            # await connection.close()
            await self.close_connection(connection)
            return {
                "status": True, "message": "Connected to PostgresSQL",
                "data": data['table_name'].unique().tolist()
            }
        except asyncpg.PostgresConnectionError as err:
            # logger.error(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": "Unable to connect to PostgresSQL",
                "data": []
            }

    async def query_builder(self, schema_name, table_name, condition=None, columns=None, limit=None):
        """
        @description:
        :param schema_name:
        :param table_name:
        :param condition:
        :param columns:
        :param limit:
        :return:
        """
        query = f'''SELECT '''
        if columns:
            query += ", ".join(f'"{item["value"]}" AS "{item["label"]}"' for item in columns)
        else:
            query += '*'
        if schema_name:
            query += f' FROM {schema_name}."{table_name}"'
        else:
            query += f' FROM "{table_name}"'
        if condition:
            query += f' WHERE {condition}'
        if limit:
            query += f' LIMIT {limit}'
        query = f"""{query};"""
        return query

    async def get_data(self, schema_name, table_name, query=None, columns=None, limit=None, debug=False, **kwargs):
        """
        @description:
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
            if query:
                self.params['query'] = query
            else:
                query = await self.query_builder(
                    schema_name=schema_name, table_name=table_name, columns=columns, limit=limit
                )
                # self.params['query'] = f'''select * from {schema_name}."{table_name}";'''
                self.params['query'] = query

            stmt = await connection.prepare(self.params['query'])
            rows = await stmt.fetch()
            column_names = [a.name for a in stmt.get_attributes()]
            df = pd.DataFrame(rows, columns=column_names)
            # await connection.close()
            await self.close_connection(connection)

            if df.empty:
                df = pd.DataFrame(columns=column_names)
            df = pl.from_pandas(df)
            if debug:
                return {
                    "status": True, "message": "Success",
                    "data": df.to_dicts()
                }
            return df
        except Exception as err:
            # logger.error(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": f"Not able to fetch data {err}", "data": []
            }

    async def primary_key(self, schema_name, table_name, debug=False, **kwargs):
        """
        @description:
        :param schema_name:
        :param table_name:
        :return:
        """
        try:
            connection = await self.get_connection()
            stmt = await connection.prepare(
                f"""SELECT column_name FROM information_schema.key_column_usage WHERE table_name = '{table_name}'""")
            columns = [a.name for a in stmt.get_attributes()]
            data = await stmt.fetch()
            data = pd.DataFrame(data, columns=columns)
            # await connection.close()
            await self.close_connection(connection)
            return {
                "status": True, "message": "Connected to PostgresSQL",
                "data": data['column_name'].unique().tolist()
            }
        except asyncpg.PostgresConnectionError as err:
            # logger.error(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": "Unable to connect to PostgresSQL",
                "data": []
            }

    async def column_names(self, schema_name, table_name, debug=False, **kwargs):
        """
        @description:
        :param schema_name:
        :param table_name:
        :return:
        """
        try:
            connection = await self.get_connection()
            stmt = await connection.prepare(
                f"""SELECT column_name FROM information_schema.columns WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'""")
            columns = [a.name for a in stmt.get_attributes()]
            data = await stmt.fetch()
            data = pd.DataFrame(data, columns=columns)
            # await connection.close()
            await self.close_connection(connection)
            return {
                "status": True, "message": "Connected to PostgresSQL",
                "data": data['column_name'].unique().tolist()
            }
        except asyncpg.PostgresConnectionError as err:
            # logger.error(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": "Unable to connect to PostgresSQL",
                "data": []
            }

    async def create_table(self, schema_name, table_name, sample_records, debug=False, **kwargs):
        if not isinstance(sample_records, pl.DataFrame):
            sample_records = pl.DataFrame(sample_records)
        connection = await self.get_connection()
        table_create_sql = ''
        dtype_dict = {'String': str('text'), 'Int64': str('text'), 'Int32': str('text'), 'Boolean': str('text'),
                      'Float64': str('double precision'), 'Float32': str('double precision'),
                      'Object': str('text'), 'Datetime': str('timestamp'), 'Utf8': str('text'),
                      "Datetime(time_unit='us', time_zone=None)": str('timestamp')}
        col_dtype = {col: sample_records[col].dtype for col in sample_records.columns}
        print("col_dtype: ", col_dtype)
        for col, dty in col_dtype.items():
            dty = dtype_dict.get(str(dty))
            if col == 'Json Data':
                dty = str('jsonb')
            if col == 'DC_AMOUNT':
                dty = str('double precision')
            table_create_sql += f'"{col}" {dty},'
        table_create_sql = table_create_sql[:-1]

        table_create_sql = '''CREATE TABLE IF NOT EXISTS "''' + table_name + '''" (''' + table_create_sql + ''')'''
        await connection.execute(table_create_sql)
        # await connection.commit()
        return True

    async def write_data_from_csv(self, records, create_table_name, schema_name='public', **kwargs):
        """
        @description:
        :param records:
        :param create_table_name:
        :param schema_name:
        :return:
        """
        connection = await self.get_connection()
        if not isinstance(records, pl.DataFrame):
            records = pl.DataFrame(records)
        records.write_csv(f"/tmp/{create_table_name}.csv")
        # cur = connection.cursor()
        result = await self.create_table(schema_name, create_table_name, records.head(10))
        await connection.copy_to_table(
            table_name=create_table_name,
            source=f'/tmp/{create_table_name}.csv',
            schema_name=schema_name,
            delimiter='~', header=False,
        )
        os.remove(f"/tmp/{create_table_name}.csv")
        # await connection.close()
        await self.close_connection(connection)
        return {
            "status": True, "message": "Data inserted Successfully", "data": []
        }

    async def write_data(self, records, schema_name, create_table_name, **kwargs):
        """
        @description:
        :param records:
        :param schema_name:
        :param create_table_name:
        :return:
        """
        connection = await self.get_connection()
        if not isinstance(records, pl.DataFrame):
            records = pd.DataFrame(records)
            records = records.astype(str)

        result = await self.create_table(schema_name, create_table_name, records.head(10))
        tuples = [tuple(x) for x in records.values]
        if not records.empty:
            await connection.copy_records_to_table(
                create_table_name,
                schema_name=schema_name,
                records=tuples,
                columns=list(records.columns),
                timeout=10
            )
        # await connection.close()
        await self.close_connection(connection)
        return {
            "status": True, "message": "Data inserted Successfully", "data": []
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
            for column in column_name:
                query = f'''SELECT DISTINCT "{column}" FROM "{schema_name}"."{table_name}"'''
                if where_clause:
                    where_query = ''
                    for key, value in where_clause.items():
                        where_query += f'"{key}" = \'{value}\' AND '
                    where_query = where_query[:-5]
                    if where_query:
                        query = f"""SELECT DISTINCT "{column}" FROM {schema_name}."{table_name}" WHERE {where_query};"""
                stmt = await connection.prepare(
                    query
                )
                data = await stmt.fetch()
                data = pd.DataFrame(data)
                columns_mapping[column] = data[column].unique().tolist()
            # await connection.close()
            await self.close_connection(connection)
            return {
                "status": True, "message": "Connected to PostgresSQL",
                "data": columns_mapping
            }
        except Exception as err:
            print(err)
            traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": "Unable to connect to PostgresSQL",
                "data": []
            }