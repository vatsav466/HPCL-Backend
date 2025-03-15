import sys
import ast
import pyodbc
import asyncio
import psycopg2
import importlib
import urdhva_base
import pandas as pd
import polars as pl
import numpy as np
import mysql.connector
sys.path.append("/opt/ceg/algo")
import utilities.users_config as users_config
# import api_manager.hpcl_ceg_model as hpcl_ceg_model
import orchestrator.dbconnector.credential_loader as credential_loader


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


async def clear_existing_user(bu):
    creds = credential_loader.get_credentials('APP_DB')
    pg_conn = psycopg2.connect(
                host=creds["host"],
                database=creds["database"],
                user=creds["user"],
                password=creds["password"],
                port=creds["port"]
            )
    query = f""" DELETE FROM users WHERE bu={bu} and manual_user IS FALSE """
    cursor = pg_conn.cursor()
    cursor.execute(query)
    pg_conn.commit()
    cursor.close()
    pg_conn.close()    


async def insert_users(data):
    total_record = len(data)
    for item in data:
        for key in ['bu', 'sap_id', 'region', 'state', 'zone', 'sales_area', 'system_role', 'novex_role']:
            if isinstance(item[key], str):
                item[key] = ast.literal_eval(item[key])
            if item[key] == None:
                item[key] = []
    count = 1
    for user in data:
        print("-*"*10)
        print(f"Inserting {count} / {total_record}")
        print("Users :", user)
        hpcl_ceg_model.UsersCreate(**user)
        await hpcl_ceg_model.UsersCreate(**user).create()


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
    novex_model_col = ["username", "email", "first_name", "last_name", "password", "employee_id",
                       "employee_number", "bu", "sap_id", "system_role", "novex_role", "region",
                       "state", "zone", "sales_area", "escalation_level", "is_ad_user", "status"]
    data.rename(columns={"EMPLOYEE_NUMBER": "username", "EMPLOYEE_NAME": "first_name",
                                "EMP_EMAIL": "email", "PLANT_CODE": "sap_id", "PLANT_DESC": "region",
                                "Zone": "zone", "ROLE_NAME": "system_role"}, inplace=True)
    print("Before dropping empty username :", len(data))
    data = data[data["username"].fillna("") != ""]
    print("After dropping empty username :", len(data))
    for col in ["status", "is_ad_user"]:
        data[col] = True
    for col in ["username", "sap_id"]:
        data[col] = data[col].fillna(0).astype(np.int64)
    data['zone'] = data['zone'].map(users_config.zone_map)
    data['last_name'] = data['first_name'].fillna("").apply(lambda x: x.split(" ")[-1] if " " in x else "")
    data['first_name'] = data['first_name'].fillna("").apply(lambda x: x.rstrip(x.split(" ")[-1]) if " " in x else x)
    for col in ["zone", "region", "sap_id", "bu", "sales_area"]:
        if col in data.columns:
            data[col] = data[col].fillna("").astype(str)
            data[col] = '["' + data[col] + '"]'
    for col in novex_model_col:
        if not col in data.columns:
            data[col] = ""
    data = data[novex_model_col]
    return data


async def sync_users():
    connection = await get_db_connection()
    cursor = connection.cursor()
    for bu in ["lpg"]:
        query = getattr(users_config, f"{bu}_query", None)
        if not query:
            return
        data = await fetch_data(cursor, query)
        role_master = pd.read_csv("/opt/ceg/algo/novex_role_master.csv")
        data = pd.merge(data, role_master[['novex_role', 'tibco_role']], left_on='ROLE_NAME', right_on='tibco_role', how='left')
        data = await combine_roles(data, _id="EMPLOYEE_NUMBER", role_name=["ROLE_NAME", "novex_role"])
        data = await process_data(data)
        print(data)
        # await clear_existing_user(bu)
        # await insert_users(data.to_dict(orient="records"))


if __name__ == "__main__":
    sync_users()