import urdhva_base
import os
import sys
import asyncio
import hpcl_ceg_model
import pandas as pd


def convert_float_string(value):
    try:
        return str(int(float(value.strip()))) if value and value.strip() else ''
    except:
        return value if isinstance(value, str) else f"{value}"


async def sync_users(file_path):
    if not os.path.exists(file_path):
        print(f"Given file {file_path} not exists")
        return

    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
    elif file_path.endswith(".xlsx"):
        df = pd.read_excel(file_path)
    else:
        print(f"Invalid file format")
        return

    df = df[df['EMPLOYEE_NUMBER'].notna()]
    df = df.fillna('')
    df['LOCATION'] = df['LOCATION'].astype(str).apply(lambda x: convert_float_string(x))
    df['EMPLOYEE_NUMBER'] = df['EMPLOYEE_NUMBER'].astype(str).apply(lambda x: convert_float_string(x))
    
    df['username'] = df['EMPLOYEE_NUMBER']
    df['employee_id'] = df['EMPLOYEE_NUMBER']
    df['sap_id'] = df['LOCATION']
    df['email'] = df['EMPLOYEE_EMAIL']
    
    if 'Zone' in df.columns:
        df['zone'] = df['ZONE']
    if 'Region' in df.columns:
        df['region'] = df['REGION']

    df['first_name'] = df['EMPLOYEE_NAME']
    df['last_name'] = ''
    df['system_role'] = df['ROLE_NAME']
    df['novex_role'] = df['NOVEX_ROLE']
    df['bu'] = df['BU']
    df['employee_number'] = df['EMPLOYEE_NUMBER']

    # Fetch existing user records
    existing_users = await hpcl_ceg_model.Users.get_all(resp_type='plain')  # Assuming a method to fetch all users
    print("existing_users --> ", existing_users)
    existing_users_map = {user['employee_id']: user for user in existing_users["data"]}

    df = df.drop_duplicates(subset=['employee_id', 'system_role', 'sap_id'])
    # Ensure required columns exist
    for key in ['region', 'state', 'zone', 'sales_area', 'escalation_level']:
        if key not in df.columns:
            df[key] = ''

    df = df[['region', 'state', 'zone', 'sales_area', 'escalation_level', 'username', 'employee_id', 'sap_id', 'email',
             'first_name', 'last_name', 'system_role', 'novex_role', 'bu']]

    df = df[df['employee_id'] != '']
    # **Aggregate roles, zones, regions, etc. for duplicate employee IDs**
    aggregated_df = (
        df.groupby("employee_id", as_index=False)
        .agg({
            "username": "first",
            "sap_id": lambda x: list(set(x.dropna())),
            "email": "first",
            "first_name": "first",
            "last_name": "first",
            "system_role": lambda x: list(set(x.dropna())),
            "novex_role": lambda x: list(set(x.dropna())),
            "bu": lambda x: list(set(x.dropna())),
            "region": lambda x: list(set(x.dropna())),
            "state": lambda x: list(set(x.dropna())),
            "zone": lambda x: list(set(x.dropna())),
            "sales_area": lambda x: list(set(x.dropna())),
            "escalation_level": lambda x: list(set(x.dropna()))
        })
    )

    data = aggregated_df.to_dict(orient="records")
    # data = df.to_dict(orient='records')

    # Retain `status` and `is_ad_user` for existing users, set `False` for new ones
    for record in data:
        emp_id = record['employee_id']
        if emp_id in existing_users_map:
            record['status'] = existing_users_map[emp_id]['status']
            record['is_ad_user'] = existing_users_map[emp_id]['is_ad_user']
        else:
            record['status'] = True
            record['is_ad_user'] = True

        for key in ['sap_id', 'bu', 'region', 'state', 'zone', 'sales_area']:
            record[key] = [rec.strip() for rec in record[key].split(",")] if record[key] else []

    await hpcl_ceg_model.Users.bulk_update(data, upsert=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"{sys.argv[0]} <FILE PATH>")
        sys.exit(0)
    asyncio.run(sync_users(sys.argv[1]))
