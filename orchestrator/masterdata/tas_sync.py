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

    # df = df[df['EMPLOYEE_NUMBER'].notna()]
    # df = df.fillna('')
    df['BAY_NUMBER'] = df['BAY_NUMBER'].astype(str).apply(lambda x: convert_float_string(x))
    df['bay_number'] = df['BAY_NUMBER']
    df['bcu_number'] = df['BCU_NUMBER']
    df['meter_number'] = df['METER_NUMBER']
    df['timestamp'] = df['TIMESTAMP']
    df['start_totalizer'] = df['START_TOTALIZER'].astype(int)
    df['end_totalizer'] = df['END_TOTALIZER'].astype(int)
    df['net_totalizer'] = df['NET_TOTALIZER'].astype(int)
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%d-%b-%y %I.%M.%S", errors="coerce")

    df = df[['bay_number', 'bcu_number', 'meter_number', 'timestamp', 'start_totalizer', 'end_totalizer', 'net_totalizer']]

    data = df.to_dict(orient='records')

    await hpcl_ceg_model.HostUnauthorisedFlow.bulk_update(data, upsert=False)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"{sys.argv[0]} <FILE PATH>")
        sys.exit(0)
    asyncio.run(sync_users(sys.argv[1]))
