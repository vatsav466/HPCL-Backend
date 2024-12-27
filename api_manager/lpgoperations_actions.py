import urdhva_base
from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import psycopg2
import datetime
import pandas as pd
import polars as pl

router = fastapi.APIRouter(prefix='/lpgoperations')


def get_data(query):
    pg_conn = psycopg2.connect(urdhva_base.settings.db_urls["postgres_async"][0])
    cursor = pg_conn.cursor()
    cursor.execute(query)    
    data = cursor.fetchall()    
    columns = [column[0] for column in cursor.description]
    data = pd.DataFrame.from_records(data, columns=columns)
    if data.empty:        
        return pl.DataFrame()
    data = pl.from_pandas(data)
    return data


# Action get_productions_rate
@router.post('/get_productions_rate', tags=['LpgOperations'])
async def lpgoperations_get_productions_rate(data: Lpgoperations_Get_Productions_RateParams):
    query = """ SELECT * FROM lpg_operations """
    if not data.days == 0:
        start_date = (datetime.datetime.now() - datetime.timedelta(days=data.days)).strftime('%Y-%m-%d')
        query = f""" SELECT * FROM lpg_operations WHERE process_date >= '{start_date}' """
    df = get_data(query)    
    df = df.rename({"short_name":"plant"})
    if df.is_empty():
        return {"data": []}
    group_col = [data.dimension]
    if data.daywise == True:
        group_col = ["process_date", data.dimension]
    df = df.group_by(group_col
                     ).agg(pl.col("productivity_normal_production"
                                  ).mean().round(2)).rename({"productivity_normal_production": "production"})
    _sort = ["production"] + group_col
    df = df.sort(_sort, descending=True)
    if not data.top == 0:
        df = df.head(data.top)
    if not data.bottom == 0:
        df = df.tail(data.bottom)
    return {"data": df.to_dicts()}


# Action get_productivity_rate
@router.post('/get_productivity_rate', tags=['LpgOperations'])
async def lpgoperations_get_productivity_rate(data: Lpgoperations_Get_Productivity_RateParams):
    query = """ SELECT * FROM lpg_operations """
    if not data.days == 0:
        start_date = (datetime.datetime.now() - datetime.timedelta(days=data.days)).strftime('%Y-%m-%d')
        query = f""" SELECT * FROM lpg_operations WHERE process_date >= '{start_date}' """
    df = get_data(query)   
    df = df.rename({"short_name":"plant"})
    if df.is_empty():
        return {"data": []}
    if data.daywise == True:
        group_col = ["process_date", data.dimension]
    df = df.group_by(group_col
                     ).agg(pl.col("productivity_normal_productivity"
                                  ).mean().round(2)).rename({"productivity_normal_productivity": "productivity"})
    _sort = ["productivity"] + group_col
    df = df.sort(_sort, descending=True)
    if not data.top == 0:
        df = df.head(data.top)
    if not data.bottom == 0:
        df = df.tail(data.bottom)
    return {"data": df.to_dicts()}
