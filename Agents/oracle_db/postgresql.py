import urdhva_base
import re
import os
import sys
import json
import base64
import typing
import asyncpg
import traceback
import pandas as pd
import polars as pl
import hpcl_ceg_model

with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Extract Oracle credentials and table names
postgresql_config = config["postgresql"]

class BaseAction:
    def __init__(self, params: typing.Dict):
        self.params = params


class Postgresql(BaseAction):
    def __init__(self, params: typing.Dict):
        super().__init__(params)

    async def get_connection(self):
        connection = await asyncpg.connect(
            host=self.params['host'],
            port=self.params['port'],
            user=self.params['user_name'],
            password=self.params['password'],
            database=self.params['database_name']
        )
        return connection

    async def get_default_schema(self):
        return "public"

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
            print(err, traceback.format_exc())
            # traceback.print_exc(file=sys.stdout)
            return {
                "status": False, "message": "Unable to connect to PostgresSQL",
                "data": []
            }

    async def create_table(
        self, schema_name, table_name, 
        sample_records, primary_key=[], unique_key=[], 
        debug=False, **kwargs
    ):
        schema_name = ""
        if not schema_name:
            schema_name = await Postgresql().get_default_schema()

        if not isinstance(sample_records, pl.DataFrame):
            sample_records = pl.DataFrame(sample_records)
        connection = await self.get_connection()
        table_create_sql = ''
        dtype_dict = {'String': str('text'), 'Int64': str('bigint'), 'Int32': str('text'), 'Boolean': str('text'),
                    'Float64': str('double precision'), 'Float32': str('double precision'),
                    'Decimal(precision=5, scale=0)': "numeric(10,0)",
                    'Decimal(precision=None, scale=0)': "numeric(10,0)",
                    'Object': str('text'), 'Datetime': str('timestamp'), 'Utf8': str('text'),
                    "Datetime(time_unit='us', time_zone=None)": str('timestamp'),
                    "Date": str('timestamp'),
                    "Decimal(precision=9, scale=3)": "numeric(10,3)",
                    "Decimal(precision=10, scale=3)": "numeric(10,3)",
                    "Decimal(precision=None, scale=3)": "numeric(10,3)",
                    "Decimal(precision=None, scale=4)": "numeric(10,3)",
                    "Decimal(precision=8, scale=3)": "numeric(10,3)", "Decimal(precision=5, scale=2)": "numeric(10,2)",
                    "Decimal(precision=10, scale=4)": "numeric(10,4)", "Datetime(time_unit='ns', time_zone=None)": str('timestamp')}
        col_dtype = {col: sample_records[col].dtype for col in sample_records.columns}
        print("col_dtype: ", col_dtype)
        for col, dty in col_dtype.items():
            dty = dtype_dict.get(str(dty), 'text')
            if col == 'Json Data':
                dty = str('jsonb')
            if col == 'DC_AMOUNT':
                dty = str('double precision')
            table_create_sql += f'"{col}" {dty},'

        constraint_query = ""
        if primary_key:
            result_string = ', '.join(f'"{s}"' for s in primary_key)
            constraint_query = f'CONSTRAINT pk_{schema_name}_{table_name} PRIMARY KEY ({result_string}),'
        if unique_key:
            result_string = ', '.join(f'"{s}"' for s in unique_key)
            constraint_query = f'CONSTRAINT uk_{schema_name}_{table_name} UNIQUE ({result_string}),'
        if constraint_query:
            table_create_sql = f''' {table_create_sql} {constraint_query}'''
        table_create_sql = table_create_sql[:-1]
        if schema_name:
            table_name = f'''{schema_name}"."{table_name}'''
        table_create_sql = '''CREATE TABLE IF NOT EXISTS "''' + table_name + '''" (''' + table_create_sql + ''')'''
        print("table_create_sql: ", table_create_sql)
        await connection.execute(table_create_sql)
        await self.close_connection(connection)
        # await connection.commit()
        return True


async def main():
    psql = Postgresql(postgresql_config)  # Initialize Oracle connection

if __name__ == "__main__":
    asyncio.run(main())
