import sys
import pyodbc
import importlib
import pandas as pd
import polars as pl
import numpy as np
import mysql.connector
sys.path.append("/opt/ceg/algo")
import orchestrator.dbconnector.credential_loader as credential_loader
import utilities.users_config as users_config


def get_db_connection():
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


def fetch_data(cursor, query, getData=False, params=None):
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
    

def combine_roles(data, _id, role_name):
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


def process_data(data):
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


def main():
    connection = get_db_connection()
    cursor = connection.cursor()
    for bu in ["lpg"]:
        query = getattr(users_config, f"{bu}_query", None)
        if not query:
            return
        data = fetch_data(cursor, query)
        role_master = pd.read_csv("/opt/ceg/algo/novex_role_master.csv")
        data = pd.merge(data, role_master[['novex_role', 'tibco_role']], left_on='ROLE_NAME', right_on='tibco_role', how='left')
        data = combine_roles(data, _id="EMPLOYEE_NUMBER", role_name=["ROLE_NAME", "novex_role"])
        data = process_data(data)
        return data

if __name__ == "__main__":
    df = main()
    print(df.to_string())
    df.to_csv("/opt/ceg/algo/testing_automated_file.csv")