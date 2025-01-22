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
import hashlib

def get_db_connection(params):
    """
    Establish a database connection
    Args:
        connection_string (str): Database connection string
    Returns:
        pyodbc connection
    """
    server = params['host']
    database = params['database']
    username = params['username']
    password = params["password"]
    port = params["port"]
    if "connection_type" in params:
        if params["connection_type"].lower() == "postgres":
            connection = psycopg2.connect(
                host=server,
                database=database,
                user=username,
                password=password,
                port=port
            )
        if params["connection_type"].lower() == "mssql":
            connection = mysql.connector.connect(
                host=server,
                user=username,
                passwd=password,
                port=port
                #database=database
            )
    print(connection)
    return connection


def insertToDB(data, table_name, indexing_col=()):
    data.write_csv(f"/tmp/table_name.csv",separator='~')
    '''
    for col in data.columns:
        try:
            data = data.with_columns(pl.col(col).fill_null(0).cast(pl.float64).alias(col))
            data = data.with_columns(pl.col(col).round(2).alias(col))
        except Exception as e:
            print("Couldn't convert to Integer :", col)
            continue
    '''
    for col in data.columns:
        if data.schema[col] in [pl.Float32, pl.Float64]:
            data = data.with_columns(pl.col(col).round(2).alias(col))

    print(data)
    print(data.schema)
    data.write_csv(f"/tmp/table_name1.csv",separator='~')
    print("-" * 50)
    print(f"-- Inserting Data to {table_name} --")
    print("Length of Data :", len(data))
    pg_conn = psycopg2.connect(
        host="10.90.38.162",
        database="hpcl_ceg",
        user="ceg_user",
        password="TTNqetkiJLPM50jC",
        port=5432
    )
    table_create_sql = ''
    cur = pg_conn.cursor()
    dtype_dict = {'String': str('text'), 'Int64': str('bigint'), 'Int32': str('bigint'), 'Boolean': str('text'),
                  'Float64': str('double precision'), 'Float32': str('double precision'),
                  'Object': str('text'), 'Datetime': str('timestamp'), 'Date': str('timestamp'), 'Utf8': str('text'),
                  "Datetime(time_unit='us', time_zone=None)": str('timestamp'),
                  "Datetime(time_unit='ns', time_zone=None)": str('timestamp'),
                  "Decimal(precision=5, scale=2)": str('double precision')}
    print('Data Types :', data.dtypes)
    col_dtype = {col: data[col].dtype for col in data.columns}
    for col, dty in col_dtype.items():
        dty = dtype_dict.get(str(dty))
        table_create_sql += f'"{col}" {dty},'
    table_create_sql = table_create_sql[:-1]
    if not isinstance(indexing_col, list):
        indexing_col = [indexing_col]
    columns_formatted = ", ".join(f'"{col}"' for col in indexing_col)
    create_table_index = f"""CREATE INDEX IF NOT EXISTS "{table_name}_index" ON "{table_name}" ({columns_formatted})"""

    table_create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({table_create_sql})'

    print("-" * 50)
    print("table_create_sql :", table_create_sql)
    print("-" * 50)
    cur.execute(table_create_sql)
    cur.execute(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS engine_id_sales ON "{table_name}" (engine_id);

    """)
    '''
    try:
       cur.execute(f"""
        ALTER TABLE "{table_name}" ADD constraint "engine_id_sales" UNIQUE (engine_id);


      """)
    except Exception as e:
        pg_conn.rollback()
    '''
    pg_conn.commit()
    print(columns_formatted)
    #cur.execute(create_table_index)

    sql = f"""SELECT * FROM "{table_name}" LIMIT 1"""
    cur.execute(sql)
    column_names = [desc[0] for desc in cur.description]
    columns = []
    for i in column_names:
        columns.append(i)
    data = data.select(columns)
    #data.write_csv('/tmp/sales_data.csv')
    print(data)
    data.write_csv(f"/tmp/table_name.csv",separator='~')
    pg_conn.commit()

    temp_table = 'sample_sales'

    cur.execute(f"""
    CREATE TEMP TABLE {temp_table} (LIKE  "{table_name}" INCLUDING ALL);
""")
    copy_query = f"""
    COPY {temp_table}
    FROM STDIN
    CSV HEADER DELIMITER '~';
"""

    data.write_csv(f"/tmp/{table_name}.csv",separator='~')
    with open(f"/tmp/{table_name}.csv", "r") as f:
            cur.copy_expert(copy_query, f)

    print(len(data))
    #data = data.unique(subset=['engine_id'])
    print(len(data))
    #exit()
    pg_conn.commit()
    conflict_column = "engine_id"
    update_cols = [col for col in columns if col != conflict_column]
    set_clause = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in update_cols])
    columns = ['"'+col+'"' for col in columns]
    print("columns",columns)
    cur.execute(f'select count(*) FROM "{temp_table}"')
    print(f'select count(*) FROM "{temp_table}"')

    data = cur.fetchall()
    print("temp table data")
    print(data)
    cur.execute(f"""
        INSERT INTO "{table_name}" ({', '.join(columns)})
        SELECT {', '.join(columns)}
        FROM {temp_table}
        ON CONFLICT ("engine_id")
        DO UPDATE SET {set_clause}
    """)
    pg_conn.commit()
    cur.close()
    exit()
 
    try:
        query = f'''
        COPY "{table_name}"
        FROM STDIN
        CSV HEADER DELIMITER '~';
        '''
        for g, split_df in data.group_by(len(data) // 10000000):
            csv_file = f'/tmp/{table_name}.csv'
            print("*"*50)
            print("length ",len(split_df))
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


def get_and_insert_data(cursor, query, params=None):
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
    
    data.to_csv('/tmp/actual_sales_data.csv',index = False)
    '''
    pg_conn = psycopg2.connect(
        host="10.90.38.162",
        database="hpcl_ceg",
        user="ceg_user",
        password="TTNqetkiJLPM50jC",
        port=5432
    )
    cur = pg_conn.cursor()
    cur.execute(f"""
    select * FROM "MOM_LEVEL_SALES" 
    """)
    rows = cur.fetchall()
    columns = [column[0] for column in cur.description]
    data = pd.DataFrame.from_records(rows, columns=columns)
    data.to_csv('/tmp/mom.csv',index = False)
    '''
    cursor.execute(f'SELECT * FROM PS.EDW_SALES_ORG_DIM')
    data1 = cursor.fetchall()
    data1_columns = [column[0] for column in cursor.description]
    data1 = pd.DataFrame.from_records(data1,columns = data1_columns)
    for col in data[['SBU_CD','SA_CD']]:
        data[col] = data[col].fillna('0').astype(str).apply(lambda x:x.split('.')[0] if '.' in x else x)
    for col in data1[['ORG_SA_CD']]:
        data1[col] = data1[col].fillna('0').astype(str)
    
    data = data.merge(data1[['ORG_SBU_CD','ORG_SBU_NM','ORG_ZONE_CD','ORG_ZONE_NM','ORG_RO_CD','ORG_RO_NM','ORG_SA_CD','ORG_SA_NM']],left_on = ['SBU_CD','ZONE_CD','RO_CD','SA_CD'],
             right_on = ['ORG_SBU_CD','ORG_ZONE_CD','ORG_RO_CD','ORG_SA_CD'],how = 'left',indicator=True)




    data = data.rename(columns={'SBU_CD':'SBU','ZONE_CD':'ZONE','RO_CD':'REGION','SA_CD':'SA','ORG_SBU_NM':'SBU_Name',
                        'ORG_ZONE_NM':'Zone_Name','ORG_RO_NM':'Region_Name','ORG_SA_NM':'SalesArea_Name'})
    if '_merge in data.columns.tolist()':
       del data['_merge'] 
    print(data['SBU_Name'].unique().tolist())
    data['SBU_Name'] = data['SBU_Name'].fillna('0').astype(str).apply(lambda x:x.split()[-1] if len(x.split()) >=3 else x)
    print(data['SBU_Name'].unique().tolist())
    print(len(data[data['SBU_Name'] == '0']))
    data.to_csv('/tmp/data.csv',index = False)

    print(data1.columns)
    data.to_csv('/tmp/data.csv',index = False)
    data1.to_csv('/tmp/data1.csv',index = False)
    data = pl.from_pandas(data)
    print("*" * 50)
    print("Data Schema", data.schema)
    print("*" * 50)
    print(len(data))
   # data.write_csv('/tmp/sales_data.csv')
    #data = data.with_columns(pl.col("total_sales").cast(pl.Float64)).round(0)
    '''
    data = data.with_columns(
    pl.col("total_sales").cast(pl.Float64).round(0).alias("total_sales")
)
    '''
    data = data.with_columns(
    pl.col("total_sales").cast(pl.Float64).alias("total_sales")
)
    grouped = data.group_by(["month_name", "fiscal_year"]).agg(
    pl.col("total_sales").sum().alias("sum_total_sales")
    )
    pivoted = grouped.pivot(
    values="sum_total_sales",
    index="month_name",
    columns="fiscal_year"
).rename({"2023-2024": "sales_2023_2024", "2024-2025": "sales_2024_2025"})
    pivoted = pivoted.with_columns(
    pl.when(pl.col("sales_2023_2024") == 0)
    .then(100)  # If previous year's sales are 0, set percentage_change to 100
    .when(pl.col("sales_2024_2025") == 0)
    .then(0)  # If current year's sales are 0, set percentage_change to 0
    .otherwise(
        (pl.col("sales_2024_2025") - pl.col("sales_2023_2024"))
        / pl.col("sales_2023_2024")
        * 100
    )
    .alias("percentage_change"))
    #pivoted = pivoted.sort(["fiscal_year", "month_name"])
    pivoted = pivoted.with_columns(
    pl.col("sales_2024_2025")
    .shift(-1)
    .fill_nan(0)  # Fill None values with 0 (or another value as needed)
    .alias("sales_2024_2025_next_month")
)
    pivoted = pivoted.join(
    grouped, 
    on="month_name", 
    how="left"
)
    print("columns",pivoted.columns)
    print(len(data))
    print(pivoted.columns)
    print(pivoted)
    #data = data.join(pivoted.select(["month_name", "percentage_change","sum_total_sales"]), on=["month_name",'total_sales','month_year'], how="left")
    #below line is working one
    #data = data.join(pivoted.select(["month_name", "percentage_change"]), on=["month_name"], how="left")
    data = data.join(
    #pivoted.select(["month_name", "fiscal_year", "sum_total_sales", "percentage_change"]),on = ["month_name","fiscal_year"],how = 'left')
    pivoted.select(["month_name", "fiscal_year", "sum_total_sales", "percentage_change"]),on = ["month_name","fiscal_year"],how = 'left')
    print(len(data))
    #data = data.with_columns(pl.col("percentage_change").cast(pl.Int64, strict=False))
    '''
    data = data.with_columns((
    pl.col("percentage_change")
    .cast(pl.Int64, strict=False).cast(pl.Utf8))
    #.alias("percentage_change")
    + pl.lit('%')).alias("percentage_change")
)
    '''
    data = data.with_columns(
    (
        (pl.col("percentage_change")
        .cast(pl.Int64, strict=False)
        .cast(pl.Utf8))
        + pl.lit('%')
    ).alias("percentage_change")
)

    print(data.columns)

    #insertToDB(data, params["table_name"], indexing_col=params["indexing_col"])
    print(len(data))
    data.write_csv('/tmp/sales_data.csv')
    print(len(data))
    data = data.unique(maintain_order=True)
    print(len(data))
    data = data.with_columns(
    pl.struct(data.columns).map_elements(
        lambda row: hashlib.md5("|".join(str(v) for v in row.values()).encode()).hexdigest()
    ).alias("engine_id")
)
    data.write_csv(f"/tmp/unique_name.csv",separator='~')
    print(len(data))
    data = data.unique(subset = ['engine_id'],maintain_order=True)
    print(len(data))
    insertToDB(data, params["table_name"])


if __name__ == "__main__":
    params = {
        "host": '10.90.144.96',
        "database": 'CONN_ENT',
        "username": 'USER_ADMIN_CE',
        "password": "Pwd#_aDMINCE@2023",
        "port": 3306,
        "table_name": "MOM_LEVEL_SALES_SYNC",
        "connection_type": "mssql"
       # "indexing_col": ["Plantcd", "Itemcode", "DaysCover"]
    }

    query = """SELECT ZS.Plant AS Plantcd,
             ZS.UNRESTRICTED_STOCK_VALUE AS Stock_value,
             IM.itemcode AS Itemcode,
             IM.ITEMNAME AS Itemname,
             ZV.Invoice_date,
             SUM(ZV.Qty_Shipped) AS Qty_Shipped,
             CASE
                 WHEN Qty_Shipped = 0 THEN NULL
                 ELSE Stock_value / Qty_Shipped
             END AS DaysCover
      FROM ZPPCV_STOCK_INV_STG ZS
      INNER JOIN ZSDCV_TIEM_MAST_STG IM ON ZS.MATERIAL_NUMBER = IM.ITEMCODE
      INNER JOIN PS.EDW_PLANT_DIM ZP ON ZS.PLANT = ZP.plant_cd
      AND ZP.CODE2 = 'LUB'
      LEFT OUTER JOIN VW_AY_INV3_LUBES_STG ZV ON ZS.plant = ZV.supply_loc
      WHERE ZV.invoice_Date BETWEEN ADDDATE(CURRENT_DATE, -365) AND CURRENT_DATE
      GROUP BY ZS.Plant,
               ZS.UNRESTRICTED_STOCK_VALUE,
               IM.itemcode,
               IM.ITEMNAME,
               ZV.Invoice_date"""
    query  = """
            WITH UniqueTSD AS (

    SELECT DISTINCT 

        PRODUCT, 

        SA, 

        ProductName,SBU_Name,Zone_Name,Region_Name,SalesArea_Name

    FROM 

        CONN_ENT.TARGET_SALES_DATA

)

SELECT 

    edw.*, 

    tsd.PRODUCT, 

    tsd.SA, 

    tsd.ProductName,

    tsd.SBU_Name,

    tsd.Zone_Name,

    tsd.Region_Name,

    tsd.SalesArea_Name

FROM 

    PS.EDW_PRIMARY_SALES_FACT edw

LEFT JOIN 

    UniqueTSD tsd 

ON 

    edw.MATERIAL_GROUP_CD = tsd.PRODUCT 

    AND edw.SA_CD = tsd.SA; 
    """
    query= """
    WITH fiscal_year_bounds AS (
    -- Define the bounds for fiscal years dynamically
    SELECT 
        DATE(CONCAT(YEAR(CURDATE()) - 1, '-04-01')) AS start_of_fy_2023_2024,
        DATE(CONCAT(YEAR(CURDATE()), '-03-31')) AS end_of_fy_2023_2024,
        DATE(CONCAT(YEAR(CURDATE()), '-04-01')) AS start_of_fy_2024_2025,
        DATE(CONCAT(YEAR(CURDATE()) + 1, '-03-31')) AS end_of_fy_2024_2025
),
month_range AS (
    -- Generate a list of all months between April 2023 and March 2025
    SELECT 
        DATE_ADD(fy.start_of_fy_2023_2024, INTERVAL seq MONTH) AS month
    FROM 
        fiscal_year_bounds fy,
        (SELECT 0 AS seq UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3
         UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7
         UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11
         UNION ALL SELECT 12 UNION ALL SELECT 13 UNION ALL SELECT 14 UNION ALL SELECT 15
         UNION ALL SELECT 16 UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL SELECT 19
         UNION ALL SELECT 20 UNION ALL SELECT 21 UNION ALL SELECT 22 UNION ALL SELECT 23) AS seq_table
    WHERE 
        DATE_ADD(fy.start_of_fy_2023_2024, INTERVAL seq MONTH) <= fy.end_of_fy_2024_2025
),
sales_data AS (
    -- Aggregate total sales by month and additional columns
    SELECT
        CAST(CONCAT(SUBSTRING(INVOICE_DATE_YYYYMMDD, 1, 6), '01') AS DATE) AS month,
        SBU_CD,
        ZONE_CD,
        ORDER_COMPANY AS RO_CD,
        SA_CD,
        MATERIAL_CD,
        SUM(NET_WEIGHT / 1000000) AS total_sales
    FROM 
        PS.EDW_PRIMARY_SALES_FACT
    GROUP BY 
        CAST(CONCAT(SUBSTRING(INVOICE_DATE_YYYYMMDD, 1, 6), '01') AS DATE),
        SBU_CD,
        ZONE_CD,
        RO_CD,
        SA_CD,
        MATERIAL_CD
),
joined_data AS (
    -- Join the generated month range with the aggregated sales data
    SELECT
        mr.month,
        sd.SBU_CD,
        sd.ZONE_CD,
        sd.RO_CD,
        sd.SA_CD,
        sd.MATERIAL_CD,
        COALESCE(sd.total_sales, 0) AS total_sales
    FROM 
        month_range mr
    LEFT JOIN 
        sales_data sd ON mr.month = sd.month
)
SELECT 
    -- Month Name
    DATE_FORMAT(month, '%M') AS month_name,  -- Month name (e.g., January)
    
    -- Month Number (Sequential across fiscal years)
    CASE 
        WHEN MONTH(month) >= 4 THEN MONTH(month) - 3  -- Fiscal month number (April = 1, May = 2, ...)
        ELSE MONTH(month) + 9  -- For January to March (e.g., Jan = 10, Feb = 11, Mar = 12)
    END AS fiscal_month,

    -- Additional Grouped Columns
    SBU_CD,
    ZONE_CD,
    RO_CD,
    SA_CD,
    MATERIAL_CD,

    -- Total Sales
    total_sales,

    -- Fiscal Year Logic
    CASE 
        WHEN month BETWEEN 
            (SELECT start_of_fy_2023_2024 FROM fiscal_year_bounds)
            AND 
            (SELECT end_of_fy_2023_2024 FROM fiscal_year_bounds)
        THEN '2023-2024'  -- Assign fiscal year 2023-2024 for months between April 2023 and March 2024
        WHEN month BETWEEN 
            (SELECT start_of_fy_2024_2025 FROM fiscal_year_bounds)
            AND 
            (SELECT end_of_fy_2024_2025 FROM fiscal_year_bounds)
        THEN '2024-2025'  -- Assign fiscal year 2024-2025 for months between April 2024 and March 2025
    END AS fiscal_year,

    -- New Date Column: Combining the Month and Fiscal Year as Date type
    CAST(CONCAT(YEAR(month), '-', LPAD(MONTH(month), 2, '0'), '-01') AS DATE) AS month_year

FROM 
    joined_data
ORDER BY 
    month, SBU_CD, ZONE_CD, RO_CD, SA_CD, MATERIAL_CD LIMIT 300000;
    """
    query = f"""
        WITH fiscal_year_bounds AS (
    -- Dynamically calculate the bounds for the current and previous fiscal years
    SELECT 
        CASE 
            WHEN MONTH(CURDATE()) < 4 THEN 
                CONCAT(YEAR(CURDATE()) - 2, '-04-01')  -- Start of the previous fiscal year
            ELSE 
                CONCAT(YEAR(CURDATE()) - 1, '-04-01')  -- Start of the current fiscal year
        END AS start_of_previous_fiscal_year,
        CASE 
            WHEN MONTH(CURDATE()) < 4 THEN 
                CONCAT(YEAR(CURDATE()) - 1, '-03-31')  -- End of the previous fiscal year
            ELSE 
                CONCAT(YEAR(CURDATE()), '-03-31')      -- End of the current fiscal year
        END AS end_of_previous_fiscal_year,
        CASE 
            WHEN MONTH(CURDATE()) < 4 THEN 
                CONCAT(YEAR(CURDATE()) - 1, '-04-01')  -- Start of the current fiscal year
            ELSE 
                CONCAT(YEAR(CURDATE()), '-04-01')      -- Start of the next fiscal year
        END AS start_of_current_fiscal_year,
        CASE 
            WHEN MONTH(CURDATE()) < 4 THEN 
                CONCAT(YEAR(CURDATE()), '-03-31')      -- End of the current fiscal year
            ELSE 
                CONCAT(YEAR(CURDATE()) + 1, '-03-31')  -- End of the next fiscal year
        END AS end_of_current_fiscal_year
),
month_range AS (
    -- Generate a list of months dynamically for both fiscal years
    SELECT 
        DATE_ADD(fb.start_of_previous_fiscal_year, INTERVAL seq MONTH) AS month
    FROM 
        fiscal_year_bounds fb,
        (SELECT 0 AS seq UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3
         UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7
         UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11
         UNION ALL SELECT 12 UNION ALL SELECT 13 UNION ALL SELECT 14 UNION ALL SELECT 15
         UNION ALL SELECT 16 UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL SELECT 19
         UNION ALL SELECT 20 UNION ALL SELECT 21 UNION ALL SELECT 22 UNION ALL SELECT 23) AS seq_table
    WHERE 
        DATE_ADD(fb.start_of_previous_fiscal_year, INTERVAL seq MONTH) <= fb.end_of_current_fiscal_year
),
sales_data AS (
    -- Aggregate total sales by month and additional columns
    SELECT
        CAST(CONCAT(SUBSTRING(INVOICE_DATE_YYYYMMDD, 1, 6), '01') AS DATE) AS month,
        SBU_CD,
        ZONE_CD,
        ORDER_COMPANY AS RO_CD,
        SA_CD,
        MATERIAL_CD,
        MATERIAL_GROUP_CD,
        SUM(NET_WEIGHT / 1000000) AS total_sales
    FROM 
        PS.EDW_PRIMARY_SALES_FACT
    GROUP BY 
        CAST(CONCAT(SUBSTRING(INVOICE_DATE_YYYYMMDD, 1, 6), '01') AS DATE),
        SBU_CD,
        ZONE_CD,
        RO_CD,
        SA_CD,
        MATERIAL_CD,
        MATERIAL_GROUP_CD
),
joined_data AS (
    -- Join the generated month range with the aggregated sales data
    SELECT
        mr.month,
        sd.SBU_CD,
        sd.ZONE_CD,
        sd.RO_CD,
        sd.SA_CD,
        sd.MATERIAL_CD,
        MATERIAL_GROUP_CD,
        COALESCE(sd.total_sales, 0) AS total_sales
    FROM 
        month_range mr
    LEFT JOIN 
        sales_data sd ON mr.month = sd.month
)
SELECT 
    -- Month Name
    DATE_FORMAT(month, '%M') AS month_name,  -- Month name (e.g., January)
    
    -- Month Number (Sequential across fiscal years)
    CASE 
        WHEN MONTH(month) >= 4 THEN MONTH(month) - 3  -- Fiscal month number (April = 1, May = 2, ...)
        ELSE MONTH(month) + 9  -- For January to March (e.g., Jan = 10, Feb = 11, Mar = 12)
    END AS fiscal_month,

    -- Additional Grouped Columns
    SBU_CD,
    ZONE_CD,
    RO_CD,
    SA_CD,
    MATERIAL_CD,
    MATERIAL_GROUP_CD,

    -- Total Sales
    total_sales,

    -- Fiscal Year Logic
    CASE 
        WHEN month BETWEEN 
            (SELECT start_of_previous_fiscal_year FROM fiscal_year_bounds)
            AND 
            (SELECT end_of_previous_fiscal_year FROM fiscal_year_bounds)
        THEN CONCAT(YEAR(month) - 1, '-', YEAR(month))  -- Assign fiscal year dynamically
        WHEN month BETWEEN 
            (SELECT start_of_current_fiscal_year FROM fiscal_year_bounds)
            AND 
            (SELECT end_of_current_fiscal_year FROM fiscal_year_bounds)
        THEN CONCAT(YEAR(month), '-', YEAR(month) + 1)  -- Assign fiscal year dynamically
    END AS fiscal_year,

    -- New Date Column: Combining the Month and Fiscal Year as Date type
    CAST(CONCAT(YEAR(month), '-', LPAD(MONTH(month), 2, '0'), '-01') AS DATE) AS month_year

FROM 
    joined_data 
ORDER BY 
    month, SBU_CD, ZONE_CD, RO_CD, SA_CD, MATERIAL_CD;





    """
    query = f"""

    WITH fiscal_year_bounds AS
  (-- Dynamically calculate the bounds for the current and previous fiscal years
 SELECT CASE
            WHEN MONTH(CURDATE()) < 4 THEN CONCAT(YEAR(CURDATE()) - 2, '-04-01') -- Start of the previous fiscal year

            ELSE CONCAT(YEAR(CURDATE()) - 1, '-04-01') -- Start of the current fiscal year

        END AS start_of_previous_fiscal_year,
        CASE
            WHEN MONTH(CURDATE()) < 4 THEN CONCAT(YEAR(CURDATE()) - 1, '-03-31') -- End of the previous fiscal year

            ELSE CONCAT(YEAR(CURDATE()), '-03-31') -- End of the current fiscal year

        END AS end_of_previous_fiscal_year,
        CASE
            WHEN MONTH(CURDATE()) < 4 THEN CONCAT(YEAR(CURDATE()) - 1, '-04-01') -- Start of the current fiscal year

            ELSE CONCAT(YEAR(CURDATE()), '-04-01') -- Start of the next fiscal year

        END AS start_of_current_fiscal_year,
        CASE
            WHEN MONTH(CURDATE()) < 4 THEN CONCAT(YEAR(CURDATE()), '-03-31') -- End of the current fiscal year

            ELSE CONCAT(YEAR(CURDATE()) + 1, '-03-31') -- End of the next fiscal year

        END AS end_of_current_fiscal_year),
                                                       month_range AS
  (-- Generate a list of months dynamically for both fiscal years
 SELECT DATE_ADD(fb.start_of_previous_fiscal_year, INTERVAL seq MONTH) AS MONTH
   FROM fiscal_year_bounds fb,

     (SELECT 0 AS seq
      UNION ALL SELECT 1
      UNION ALL SELECT 2
      UNION ALL SELECT 3
      UNION ALL SELECT 4
      UNION ALL SELECT 5
      UNION ALL SELECT 6
      UNION ALL SELECT 7
      UNION ALL SELECT 8
      UNION ALL SELECT 9
      UNION ALL SELECT 10
      UNION ALL SELECT 11
      UNION ALL SELECT 12
      UNION ALL SELECT 13
      UNION ALL SELECT 14
      UNION ALL SELECT 15
      UNION ALL SELECT 16
      UNION ALL SELECT 17
      UNION ALL SELECT 18
      UNION ALL SELECT 19
      UNION ALL SELECT 20
      UNION ALL SELECT 21
      UNION ALL SELECT 22
      UNION ALL SELECT 23) AS seq_table
   WHERE DATE_ADD(fb.start_of_previous_fiscal_year, INTERVAL seq MONTH) <= fb.end_of_current_fiscal_year ),
                                                       sales_data AS
  (-- Aggregate total sales by month and additional columns
 SELECT CAST(CONCAT(SUBSTRING(INVOICE_DATE_YYYYMMDD, 1, 6), '01') AS DATE) AS MONTH,
        SBU_CD,
        ZONE_CD,
        ORDER_COMPANY AS RO_CD,
        SA_CD,
        MATERIAL_CD,
        MATERIAL_GROUP_CD,
        SUM(NET_WEIGHT / 1000000) AS total_sales
   FROM PS.EDW_PRIMARY_SALES_FACT
   GROUP BY CAST(CONCAT(SUBSTRING(INVOICE_DATE_YYYYMMDD, 1, 6), '01') AS DATE),
            SBU_CD,
            ZONE_CD,
            RO_CD,
            SA_CD,
            MATERIAL_CD,
            MATERIAL_GROUP_CD),
                                                       joined_data AS
  (-- Join the generated month range with the aggregated sales data
 SELECT mr.month,
        sd.SBU_CD,
        sd.ZONE_CD,
        sd.RO_CD,
        sd.SA_CD,
        sd.MATERIAL_CD,
        MATERIAL_GROUP_CD,
        COALESCE(sd.total_sales, 0) AS total_sales
   FROM month_range mr
   LEFT JOIN sales_data sd ON mr.month = sd.month)
SELECT -- Month Name
 DATE_FORMAT(MONTH, '%M') AS month_name, -- Month name (e.g., January)
 -- Month Number (Sequential across fiscal years)
 CASE
     WHEN MONTH(MONTH) >= 4 THEN MONTH(MONTH) - 3 -- Fiscal month number (April = 1, May = 2, ...)

     ELSE MONTH(MONTH) + 9 -- For January to March (e.g., Jan = 10, Feb = 11, Mar = 12)

 END AS fiscal_month, -- Additional Grouped Columns
 SBU_CD,
 ZONE_CD,
 RO_CD,
 SA_CD,
 MATERIAL_CD,
 MATERIAL_GROUP_CD, -- Total Sales
 total_sales, -- Fiscal Year Logic
CASE
    -- For dates from January to March, assign the previous calendar year as the start of the fiscal year
    WHEN MONTH(MONTH) BETWEEN 1 AND 3 THEN 
        CONCAT(YEAR(MONTH) - 1, '-', YEAR(MONTH))
    -- For dates from April to December, assign the current calendar year as the start of the fiscal year
    WHEN MONTH(MONTH) BETWEEN 4 AND 12 THEN 
        CONCAT(YEAR(MONTH), '-', YEAR(MONTH) + 1)
END AS fiscal_year,
 CAST(CONCAT(YEAR(MONTH), '-', LPAD(MONTH(MONTH), 2, '0'), '-01') AS DATE) AS month_year
FROM joined_data
ORDER BY month_year DESC;



    """




    connection = get_db_connection(params)
    cursor = connection.cursor()
    get_and_insert_data(cursor, query, params=params)

