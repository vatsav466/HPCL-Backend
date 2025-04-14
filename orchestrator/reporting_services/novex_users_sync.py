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


async def clear_existing_user(bu):
    creds = credential_loader.get_credentials('APP_DB')
    pg_conn = psycopg2.connect(
                host=creds["host"],
                database=creds["database"],
                user=creds["user"],
                password=creds["password"],
                port=creds["port"]
            )
    query = f""" DELETE FROM users WHERE '{bu.upper()}' = ANY(bu) and manual_user IS FALSE; """
    cursor = pg_conn.cursor()
    cursor.execute(query)
    pg_conn.commit()
    cursor.close()
    pg_conn.close()


async def insert_users(data):
    total_record = len(data)
    for item in data:
        for key in ['bu', 'sap_id', 'region', 'state', 'zone', 'sales_area', 'system_role', 'novex_role']:
            if item[key] == None or item[key] == "":
                item[key] = []
            if isinstance(item[key], str):
                item[key] = ast.literal_eval(item[key])
    count = 1
    for user in data:
        sys.stdout.write(f"\rInserting {count} / {total_record}   ")
        sys.stdout.flush()
        hpcl_ceg_model.UsersCreate(**user)
        await hpcl_ceg_model.UsersCreate(**user).create()
        count += 1


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


async def process_data(data, bu):
    novex_model_col = ["username", "email", "first_name", "last_name", "password", "employee_id",
                       "employee_number", "bu", "sap_id", "system_role", "novex_role", "region",
                       "state", "zone", "sales_area", "is_ad_user", "status","manual_user"]
    data.rename(columns={"EMPLOYEE_NUMBER": "username", "EMPLOYEE_NAME": "first_name",
                                "EMP_EMAIL": "email", "PLANT_CODE": "sap_id", "PLANT_DESC": "region",
                                "Zone": "zone", "ROLE_NAME": "system_role"}, inplace=True)
    if "SALES_GRP" in data.columns and bu.upper()=='LPG':
        sales_master = pd.read_csv("/opt/ceg/algo/orchestrator/reporting_services/lpg_sa_master.csv")
        data['SALES_GRP'] = data['SALES_GRP'].astype(str)
        sales_master['SACode'] = sales_master['SACode'].astype(str)
        data = pd.merge(data, sales_master, left_on='SALES_GRP', right_on='SACode', how='left')
        data.rename(columns={"SAName": "sales_area"}, inplace=True)
    else:
        data["sales_area"] = data["SALES_GROUP_DESC"]
    print("Before dropping empty username :", len(data))
    data = data[data["username"].fillna("") != ""]
    print("After dropping empty username :", len(data))
    for col in ["status", "is_ad_user"]:
        data[col] = True
    data["employee_id"] = data["username"]
    data["manual_user"] = False
    for col in ["username", "sap_id", "employee_id"]:
        data[col] = data[col].fillna(0).astype(np.int64).astype(str)
    data['zone'] = data['zone'].map(reporting_config.zone_map)
    data['last_name'] = data['first_name'].fillna("").apply(lambda x: x.split(" ")[-1] if " " in x else "")
    data['first_name'] = data['first_name'].fillna("").apply(lambda x: x.rstrip(x.split(" ")[-1]) if " " in x else x)
    for col in ["zone", "region", "sap_id", "bu", "sales_area"]:
        if col in data.columns:
            data[col] = data[col].fillna("").astype(str)
            data[col] = '["' + data[col] + '"]'
    
    for _role in ["Zonal", "Zone"]:
        mask = data["novex_role"].astype(str).str.contains(_role, case=False, na=False)
        data.loc[mask, ["sap_id", "region", "sales_area"]] = '[]'
    for _role in ["Regional", "Region"]:
        mask = data["novex_role"].astype(str).str.contains(_role, case=False, na=False)
        data.loc[mask, ["sap_id", "zone", "sales_area"]] = '[]'
    for _role in ["Sales"]:
        mask = data["novex_role"].astype(str).str.contains(_role, case=False, na=False)
        data.loc[mask, ["sap_id", "region", "zone"]] = '[]'
    for _role in ["HQO"]:
        mask = data["novex_role"].astype(str).str.contains(_role, case=False, na=False)
        data.loc[mask, ["sap_id", "zone", "region", "sales_area"]] = '[]'
    for col in ["zone", "region", "sales_area"]:
        data.loc[(data['sap_id'] != '[]'), col] = '[]'

    for col in novex_model_col:
        if not col in data.columns:
            data[col] = ""
    data = data[novex_model_col]
    return data


async def sync_users():
    connection = await get_db_connection()
    cursor = connection.cursor()
    for bu in ["lpg", "tas", "ro"]:
        role_master = pd.read_csv("/opt/ceg/algo/orchestrator/reporting_services/novex_role_master.csv")
        role_master = role_master[role_master["bu"] == str(bu).upper()]
        role_master = role_master.drop_duplicates("tibco_role")
        query = getattr(reporting_config, f"{bu}_query", None)
        if not query:
            return
        roles = role_master['tibco_role'].unique().tolist()
        if roles:
            roles_condition = "ZR.ROLE_NAME IN ({})".format(', '.join([f"'{role}'" for role in roles]))
            query += f" AND {roles_condition}"
        data = await fetch_data(cursor, query)  
        print("Length of Data Before Merge:", len(data))
        data = pd.merge(data, role_master[['novex_role', 'tibco_role']], left_on='ROLE_NAME', right_on='tibco_role', how='left')
        print("Length of Data After Merge:", len(data))
        data = await combine_roles(data, _id="EMPLOYEE_NUMBER", role_name=["ROLE_NAME", "novex_role"])
        data["bu"] = bu.upper()
        data = await process_data(data, bu)
        await clear_existing_user(bu)
        await insert_users(data.to_dict(orient="records"))


if __name__ == "__main__":
    asyncio.run(sync_users())