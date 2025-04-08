import urdhva_base
import orchestrator.analytics.industry_data_normalize as ind
import os
import uuid
import pyodbc
import psycopg2
import traceback
import datetime
import pandas as pd
import polars as pl
import mysql.connector
from dateutil.relativedelta import relativedelta
import orchestrator.dbconnector.credential_loader as credential_loader
import hashlib
import io
import numpy as np
def get_industry_data():
    """
    Getting industry fiscal year level daya from industry_performance.py 
    Once we get the industry data we are inserting that to postgres table industry_performance
    """
    #res = ind.fetch_industry_raw_data(actual=False,history=True)
    res = ind.fetch_industry_raw_data(actual=True,history=False)
    print(res.columns.tolist())
    print(res['VALUE'].sum())
    print(type(res))
    print("cols",res.columns.tolist())
    if 'REGIONCODE' in res.columns.tolist():
        res['REGIONCODE'] = res['REGIONCODE'].astype(int)

   
    res = res.rename(columns = {'VALUE':'netweight_tmt','SBU':'sbu_name','PRODCODE':'productcode','PRODNAME':'productname','ZONE':'zone_name','REGIONCODE':'orgrocd',
        'REGIONNAME':'region_name','FIN_YEAR':'fiscal_year','Co':'company_name','MONTH':'month_name','PSU/PVT':'psu_pvt',
        'Code':'code','DISTCODE':'distcode','Prod1.1':'prod1_1','Prod2':'prod2','STATECODE':'statecode','Co Name':'coname',
        'New Code':'newcode','COMCODE':'comcode','COMNAME':'comname','Prod1':'prod1','CATEGORY':'category',
        'TOTAL':'total','STATENAME':'statename','DISTNAME':'distname','Dist':'dist','COMP_TYPE':'com_type'})
    res.loc[res['company_name'].isin(['HPCL','BPCL','IOCL']),'company_name'] = 'MPSU'
    if 'SBU with district wise' in res.columns:
        del res['SBU with district wise']
    if 'RO' in res.columns:
        del res['RO']
    #res['zone_name'] = res['zone_name'].str.replace('CZ','Central Zone').str.replace('ECZ','East Central Zone').str.replace('EZ','East').str.replace('NCZ','North Central Zone').str.replace('NFZ','North Frontier Zone').str.replace('NWFZ','North West Frontier Zone').str.replace('NWZ','North Western Zone').str.replace('NZ','North').str.replace('SCZ','South Central Zone').str.replace('SWZ','South Western Zone').str.replace('SZ','South').str.replace('WZ','West')
    res = pl.from_pandas(res)
    res.write_csv('/tmp/res.csv')
    if len(res)>0:
        insert_industry_data(res)
def insert_industry_data(res):
    creds = credential_loader.get_credentials('APP_DB')
    table_name = "industry_performance"
    print(len(res))
    pg_conn = psycopg2.connect(
                host=creds['host'],
                database=creds['database'],
                user=creds['user'],
                password=creds['password'],
                port=creds['port']
            )
    
    table_create_sql = ''
    cur = pg_conn.cursor()
    dtype_dict = {'String': str('text'), 'Int64': str('bigint'), 'Int32': str('bigint'), 'Boolean': str('text'),
                  'Float64': str('double precision'), 'Float32': str('double precision'),
                  'Object': str('text'), 'Datetime': str('timestamp'), 'Date': str('timestamp'), 'Utf8': str('text'),
                  "Datetime(time_unit='us', time_zone=None)": str('timestamp'),
                  "Datetime(time_unit='ns', time_zone=None)": str('timestamp'),
                  "Decimal(precision=5, scale=2)": str('double precision'),
                  "Decimal(precision=6, scale=4)": str('double precision'),
                  "Decimal(precision=9, scale=4)": str('double precision'),
                  "Decimal(precision=9, scale=0)": str('double precision'),
                  "Decimal(precision=6, scale=0)": str('double precision'),
                  "Decimal(precision=4, scale=0)": str('double precision'),
                  "Decimal(precision=4, scale=2)": str('double precision'),
                  "Decimal(precision=8, scale=0)": str('double precision'),
                  "Decimal(precision=8, scale=3)": str('double precision'),
                  "Decimal(precision=6, scale=0)": str('double precision'),
                  "Decimal(precision=6, scale=3)": str('double precision'),
                  "Decimal(precision=7, scale=4)": str('double precision'),
                  "Decimal(precision=8, scale=6)": str('double precision'),
                  "Decimal(precision=11, scale=6)": str('double precision'),
                  "Decimal(precision=11, scale=8)": str('double precision'),
                  "Decimal(precision=13, scale=10)": str('double precision'),
                  "Decimal(precision=10, scale=2)": str('double precision'),
                  "Decimal(precision=None, scale=2)": str('double precision'),
                  "Decimal(precision=None, scale=27)": str('double precision'),
                  "Decimal(precision=None, scale=28)": str('double precision')
                  }
    col_dtype = {col: res[col].dtype for col in res.columns}
    for col, dty in col_dtype.items():
        dty = dtype_dict.get(str(dty))
        table_create_sql += f'"{col}" {dty},'
    table_create_sql = table_create_sql[:-1]
    table_create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({table_create_sql})'
    cur.execute(table_create_sql)
    pg_conn.commit()
    sql = f"""SELECT * FROM "{table_name}" LIMIT 1"""
    cur.execute(sql)
    column_names = [desc[0] for desc in cur.description]
    columns = []
    for i in column_names:
        columns.append(i)
    
    res = res.with_columns([pl.col("productname").alias("productname_org")])
    res = res.with_columns([pl.col("prod1").alias("productname")])
    res = res.select(columns)
    pg_conn.commit()
    try:
        query = f'''
        COPY "{table_name}"
        FROM STDIN
        CSV HEADER DELIMITER '~';
        '''
        print(query)
        for g, split_df in res.group_by(len(res)// 10000000):
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

get_industry_data()
