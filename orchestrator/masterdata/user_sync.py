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
    df['LOCATION'] = df['LOCATION'].astype(str)
    df['LOCATION'] = df['LOCATION'].apply(lambda x: convert_float_string(x))
    df['EMPLOYEE_NUMBER'] = df['EMPLOYEE_NUMBER'].astype(str)
    df['EMPLOYEE_NUMBER'] = df['EMPLOYEE_NUMBER'].apply(lambda x: convert_float_string(x))
    df['username'] = df['EMPLOYEE_NUMBER']
    df['employee_id'] = df['EMPLOYEE_NUMBER']
    df['sap_id'] = df['LOCATION']
    df['email'] = df['EMP_EMAIL']
    df['first_name'] = df['EMPLOYEE_NAME']
    df['last_name'] = ''
    df['system_role'] = df['ROLE_NAME']
    df['novex_role'] = df['Novex Role']
    df['is_ad_user'] = True
    df['status'] = True
    df['bu'] = df['BU']
    df = df.drop_duplicates(subset=['employee_id'], keep=False)
    for key in ['region', 'state', 'zone', 'sales_area', 'escalation_level']:
        df[key] = ''
    df = df[['region', 'state', 'zone', 'sales_area', 'escalation_level', 'username', 'employee_id', 'sap_id', 'email',
             'first_name', 'last_name', 'system_role', 'novex_role', 'bu', 'status', 'is_ad_user']]
    df = df[df['employee_id'] != '']
    data = df.to_dict(orient='records')
    for record in data:
        for key in ['sap_id', 'bu', 'region', 'state', 'zone', 'sales_area']:
            record[key] = [rec.strip() for rec in record[key].split(",")] if record[key] else []
    await hpcl_ceg_model.Users.bulk_update(data)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"{sys.argv[0]} <FILE PATH>")
        sys.exit(0)
    asyncio.run(sync_users(sys.argv[1]))
