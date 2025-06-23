import sys
import ast
import time
import asyncio
import psycopg2
import pandas as pd
import mysql.connector
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from functools import partial
sys.path.append("/opt/ceg/algo")
import api_manager.hpcl_ceg_model as hpcl_ceg_model
import orchestrator.dbconnector.credential_loader as credential_loader
import orchestrator.reporting_services.reporting_config as reporting_config


async def get_db_connection():
    """
    Establish a database connection
    Args:
        connection_string (str): Database connection string
    Returns:
        pyodbc connection
    """
    creds = credential_loader.get_credentials('TIBCO')
    connection = mysql.connector.connect(
                host=creds['host'],
                user=creds['user'],
                passwd=creds['password'],
                port=creds['port'],
                database=creds['database']
            )
    return connection


async def fetch_data(cursor, query, getData=False, params=None):
    """
    Fetch data from database using a SQL query
    Args:
        cursor (pyodbc cursor): Database cursor
        query (str): SQL query to execute
    Returns:
        pandas DataFrame
    """        
    print("-" * 50)
    print("query -->", query)
    print("-" * 50)
    print("Running Query ...")
    cursor.execute(query)
    data = cursor.fetchall()
    print('Total Records :', len(data))
    columns = [column[0] for column in cursor.description]
    data = pd.DataFrame.from_records(data, columns=columns)
    return data


async def clear_existing_location_master(bu):
    creds = credential_loader.get_credentials('APP_DB')
    pg_conn = psycopg2.connect(
                host=creds["host"],
                database=creds["database"],
                user=creds["user"],
                password=creds["password"],
                port=creds["port"]
            )
    query = f""" DELETE FROM location_master WHERE bu='{bu.upper()}' AND location_onboard IS FALSE; """
    cursor = pg_conn.cursor()
    cursor.execute(query)
    pg_conn.commit()
    cursor.close()
    pg_conn.close()
    

async def insert_users(data):
    for item in data:
        for key in ['sales_area_1']:
            if key in item.keys():
                if item[key] == None or item[key] == "":
                    item[key] = []
                elif isinstance(item[key], str):
                    item[key] = ast.literal_eval(item[key])
    await hpcl_ceg_model.LocationMaster.bulk_update(data, upsert=True)

async def combine_roles(data, _id, role_name):
    """
    Combine the different roles of single users into list of roles and removes the duplicates
    Arg:
        data : Pandas DataFrame
        _id : Column Name of employee_id
        role_name:  Column Name of role name
    Return:
         data : Pandas Dataframe
    """
    print("length of data before combine :", len(data))
    aggregation_dict = {col: (lambda x: str(list(set(x)))) for col in role_name}
    grouped = data.groupby(_id).agg(aggregation_dict).reset_index()
    data = data.drop_duplicates(_id, keep="first")
    for col in role_name:
        del data[col]
    data = pd.merge(data, grouped, on=_id, how="left")
    print("length of data after combine :", len(data))
    return data


async def process_data(data):
    data.rename(columns=reporting_config._rename, inplace=True)
    if all(col in data.columns for col in ["ADDRESS1","ADDRESS2","ADDRESS3","ADDRESS4","ADDRESS5"]):
        data['address'] = data[["ADDRESS1", "ADDRESS2", "ADDRESS3", "ADDRESS4", "ADDRESS5"]].fillna('').agg(' '.join, axis=1)
    elif all(col in data.columns for col in ["land_mark","location","pincode"]):
        data["address"] = data["land_mark"].astype(str) + " " + data["location"].astype(str) + " " + data["pincode"].astype(str)
    
    data['health_status'] = "Normal"
    data['is_active'] = True
    if "sap_id" in data.columns:
        data = data.drop_duplicates('sap_id', keep='first')
    for col, _type in reporting_config.location_master_schema.items():
        if not col in data.columns:
            if _type.lower() == 'varchar':
                data[col] = ""
            elif _type.lower() == 'boolean':
                data[col] = False
            elif _type.lower() == 'timestamp':
                data[col] = None
            elif _type.lower() == 'integer':
                data[col] = 0
    for col, _type in reporting_config.location_master_schema.items():
        if _type.lower() == 'varchar':
            data[col] = data[col].fillna("")
    if "email" in data.columns:
        data["email"] = data["email"].fillna("").astype(str)
    data = data[list(reporting_config.location_master_schema.keys())]
    data['zone'] = data['zone'].map(reporting_config.zone_map)
    print("Before dropping blank Zone :", len(data))
    data = data[data["zone"].fillna("") != ""]
    print("After dropping blank Zone :", len(data))
    return data


async def sync_location_master():
    connection = await get_db_connection()
    cursor = connection.cursor()
    for config in reporting_config.location_configs:
        data = await fetch_data(cursor, config.get("query"))
        for col in ["PLANT", "REPORTING_OFFICE"]:
            if col in data.columns:
                data[col] = data[col].fillna(0).astype(str).replace('',0).astype(int).astype(str)
        for col in ["RO_CODE", "SALES_OFFICE_DESC", "SALES_GROUP_DESC"]:
            if config.get("reporting_office_query", None) and col in data.columns:
                del data[col]
        if config.get("reporting_office_query", None):
            data_ro = await fetch_data(cursor, config.get("reporting_office_query"))
            data_ro = await combine_roles(data_ro, _id="RO_CODE", role_name=["SALES_GROUP_DESC"])
            data = pd.merge(data, data_ro[["RO_CODE", "SALES_OFFICE_DESC", "SALES_GROUP_DESC"]],
                            left_on="REPORTING_OFFICE", right_on="RO_CODE", how="left")
        data["bu"] = config.get("bu", "").upper()
        data = await process_data(data)
        await clear_existing_location_master(config.get("bu", ""))
        await insert_users(data.to_dict(orient="records"))


if __name__=="__main__":
    asyncio.run(sync_location_master())