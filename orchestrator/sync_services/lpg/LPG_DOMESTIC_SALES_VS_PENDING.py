import os
import uuid
import glob
import pyodbc
import psycopg2
import traceback
import datetime
import pandas as pd
import polars as pl
from dateutil.relativedelta import relativedelta


def get_db_connection():
    """
    Establish a database connection
    Args:
        connection_string (str): Database connection string
    Returns:
        pyodbc connection
    """
    server = 'CDCMSPRODDB5.JADE.HPCL.IN'
    database = 'HPGASDB'
    username = 'Algofusion_Read_Digital'
    password = 'DiGi#25_11_tal_NErve24'
    port = 16193
        
    connection = pyodbc.connect(
            'DRIVER={ODBC Driver 18 for SQL Server};'
            f'Server={server},{port};'
            f'Database={database};'
            f'UID={username};'
            f'PWD={password};'
            'TrustServerCertificate=yes;MARS_Connection=yes;',
        )
    return connection


def _get_data(cursor, query):
    try:
        cursor.execute(query)
        batch_size = 100000
        count = 0
        output_path = "/opt/ceg/algo/INPUT"
        print(datetime.datetime.now())
        while count < 51:            
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            column_names = [desc[0] for desc in cursor.description]
            df = pd.DataFrame({column: [row[i] for row in rows] for i, column in enumerate(column_names)})
            # Convert the 'EMAIL_BODY' column to utf-16 encoding
            # Write the DataFrame to a CSV file
            outfile_path = os.path.join(output_path, f"outfile{count}.csv")
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            df.to_csv(outfile_path, index=False)            
            print("Total Records Feteched :", batch_size*count)
            count += 1

        df = pl.DataFrame()
        for each_file in glob.glob(
                output_path + '/' + "outfile*.csv"
        ):
            df = pl.concat([df, pl.read_csv(each_file, truncate_ragged_lines=True, infer_schema_length=0)])

        if df.is_empty():
            df = pl.DataFrame()       
        return df
    except Exception as err:
        print(err)
        print(traceback.print_exc())


def fetch_data(cursor, query, getData=False, params=None):
    """
    Fetch data from database using a SQL query
    Args:
        cursor (pyodbc cursor): Database cursor
        query (str): SQL query to execute
    Returns:
        pandas DataFrame
    """
    if params:
        pg_conn = psycopg2.connect(
                host=params["host"],
                database=params["database"],
                user=params["user"],
                password=params["password"],
                port=params["port"]
            )
        cursor = pg_conn.cursor()
        
    print("-" * 50)
    print("query -->", query)
    print("-" * 50)
    print("Running Query ...")
    cursor.execute(query)
    if getData:
        data = cursor.fetchall()
        print('Total Records :', len(data))
        columns = [column[0] for column in cursor.description]
        data = pd.DataFrame.from_records(data, columns=columns)
        data = pl.from_pandas(data)
        return data
    if params:
        pg_conn.commit()
        cursor.close()
        pg_conn.close()


def insertToDB(data, table_name, indexing_col=()):        
    for col in data.columns:
        if col in ["sales_volume", "pendings_volume", "bookings_volume"]:
            data = data.with_columns(pl.col(col).fill_null(0).cast(pl.Float64).alias(col))
            continue
        try:
            data = data.with_columns(pl.col(col).fill_null(0).cast(pl.Int64).alias(col))
        except Exception as e:
            print("Couldn't convert to Integer :", col)
            continue
    print("-"*50)
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
    dtype_dict = {'String':str('text'),'Int64': str('bigint'), 'Int32': str('bigint'), 'Boolean': str('text'), 'Float64': str('double precision'),'Float32': str('double precision'),
                  'Object': str('text'), 'Datetime': str('timestamp'), 'Utf8': str('text'), "Datetime(time_unit='us', time_zone=None)": str('timestamp'), "Datetime(time_unit='ns', time_zone=None)":str('timestamp'), "Decimal(precision=5, scale=2)": str('double precision')}
    print('Data Types :',data.dtypes)
    col_dtype = {col: data[col].dtype for col in data.columns}
    for col, dty in col_dtype.items():
        dty = dtype_dict.get(str(dty))
        table_create_sql += f'"{col}" {dty},'
    table_create_sql = table_create_sql[:-1]
        
    columns_formatted = ", ".join(f'"{col}"' for col in indexing_col)
    create_table_index = f"""CREATE INDEX IF NOT EXISTS "{table_name}_index" ON "{table_name}" ({columns_formatted})"""
    
    table_create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({table_create_sql})'
    
    print("-"*50)
    print("table_create_sql :", table_create_sql)
    print("-"*50)
    
    cur.execute(table_create_sql)
    pg_conn.commit()
    cur.execute(create_table_index)

    sql = f"""SELECT * FROM "{table_name}" LIMIT 1"""
    cur.execute(sql)
    column_names = [desc[0] for desc in cur.description]
    columns=[]
    for i in column_names:
        columns.append(i)
    data = data.select(columns)
    try:
        query = f'''
        COPY "{table_name}"
        FROM STDIN
        CSV HEADER DELIMITER '~';
        '''
        for g, split_df in data.group_by(len(data)// 10000000):
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


def _merge_data(left_df, right_df, left_on, right_on, how, suffixes="_right", indicator=False):
        '''
        Merging and getting the matched and unmatched indicator
        '''
        new_names = [f"{x}_tmp" for x in left_on]
        left_df = left_df.with_columns(pl.col(x).alias(y) for x,y in zip(left_on, new_names))
        right_df = right_df.with_columns(pl.col(x).alias(y) for x,y in zip(right_on, new_names))
        
        left_df = left_df.with_columns(left_merge=pl.lit("Left"))
        right_df = right_df.with_columns(right_merge=pl.lit("Right"))
        
        final_df = left_df.join(
            right_df, on=new_names, how=how, suffix=suffixes
        ).drop(new_names)
        if indicator:
            final_df = (final_df.with_columns(
                    _merge=pl.when((pl.col('left_merge').is_not_null()) & (pl.col("right_merge").is_null()))
                    .then(pl.lit('left_only'))
                    .when((pl.col('left_merge').is_null()) & (pl.col("right_merge").is_not_null()))
                    .then(pl.lit('right_only'))
                    .otherwise(pl.lit('both'))
                    .alias('_merge')
                )
            )
        final_df = final_df.drop(["left_merge", "right_merge"])
        return  final_df


def calculate_ageing(df):
    df = df.with_columns(pl.lit(0).alias("Total_Pending"))
    for col in df.columns:
        if col.startswith("Pending"):
            df = df.with_columns(pl.col("Total_Pending") + pl.col(col).fill_null(0).cast(pl.Int64).alias("Total_Pending"))
    
    pending_1_3_days = [f"Pending_{x}D" for x in range(1, 4)]
    pending_4_7_days = [f"Pending_{x}D" for x in range(4, 8)]
    pending_8_15_days = [f"Pending_{x}D" for x in range(8, 16)]
            
    df = df.with_columns(pending_1_3_days=pl.sum_horizontal(pending_1_3_days))
    df = df.with_columns(pending_4_7_days=pl.sum_horizontal(pending_4_7_days))
    df = df.with_columns(pending_8_15_days=pl.sum_horizontal(pending_8_15_days))
    return df


def get_pending_vs_delivered_data():
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """ IF OBJECT_ID('TEMPDB..#Group', 'U') is not null DROP table #Group """
    fetch_data(cursor, query)
    query = """ IF OBJECT_ID('TEMPDB..#Order', 'U') is not null DROP table #Order """
    fetch_data(cursor, query)
    query = """ SELECT DISTINCT DG.GroupCode INTO #Group						
                FROM DCMs.tblDistributorMaster DM WITH(NOLOCK)						
                    INNER JOIN DCMs.tblDistributorGroupDetails DG WITH(NOLOCK) ON DM.DistributorId=DG.DistributorId;
            """
    fetch_data(cursor, query)
    query = """ CREATE TABLE #Order (
                OrderRefNo	numeric(17,0),
                OrderQuantity	int,
                Distributorid int,
                OrderDate	datetime,
                OrderStatusCode	varchar(5),
                OrderSourceCode	varchar(5),
                ConsumerType	varchar(5),
                Pricecode	varchar(5),
                IsPrepaid char(1),
                CylType varchar(4),
                ActualDeliveryDate DATE
            ); """
    fetch_data(cursor, query)
    query = """ DECLARE	@vGroupCode VARCHAR(2),  				
			    @vCmd NVARCHAR(4000)

                WHILE EXISTS (SELECT TOP 1 1 FROM #Group)						
                BEGIN
                    SELECT TOP 1 @vGroupCode=GroupCode FROM #Group
                    SET @vCmd = NULL
                                        
                    SET @vCmd = 'SELECT  ROD.OrderRefNo,ROD.OrderQuantity,ROD.Distributorid,
                    ROD.OrderDate,ROD.OrderStatusCode,ROD.OrderSourceCode,
                    CASE WHEN ROD.Naturecode=''16'' THEN ''PMUY'' ELSE ''NPMUY'' END,
                    ROD.Pricecode,
                    CASE WHEN RPD.TransactionReferenceNumber IS NOT NULL THEN ''Y'' ELSE ''N'' END,
                    CASE WHEN ROD.Pricecode IN (''22'',''24'') THEN ''C142'' ELSE ''C5'' END,
                    ROD.ActualDeliveryDate
                    FROM DCMs.tblRefillOrderDtls$'+@vGroupCode+' ROD WITH(NOLOCK)
                    LEFT OUTER JOIN esv.tblRefillPaymentDtls RPD  with(nolock)
                    ON RPD.OrderRefNo = ROD.OrderRefNo AND RPD.PaymentStatus=''SUCCESS''
                    WHERE ROD.Naturecode NOT IN (''3'',''4'')
                    AND ROD.OrderStatusCode !=''CNCL''
                    AND (ROD.ActualDeliveryDate IS NULL
                    OR 	 CONVERT(DATE,ROD.OrderDate,120) >= CONVERT(DATE,GETDATE()-1,120)
                    OR 	ROD.ActualDeliveryDate >= CONVERT(DATE,GETDATE()-1,120))
                    AND ROD.Pricecode IN (''22'',''24'',''163'',''162'')'
                                        
                    INSERT INTO #Order
                    (OrderRefNo,OrderQuantity,Distributorid,OrderDate,OrderStatusCode,
                    OrderSourceCode,ConsumerType,Pricecode,IsPrepaid,CylType,ActualDeliveryDate)
                    EXEC sp_executesql @vCmd
                                        
                    DELETE FROM #Group WHERE GroupCode=@vGroupCode
                    --SELECT COUNT(1) PendingGroups FROM #Group
                END
            """
    fetch_data(cursor, query)
    query = """ INSERT INTO #Order
                    (OrderRefNo,OrderQuantity,Distributorid,OrderDate,OrderStatusCode,
                    OrderSourceCode,ConsumerType,Pricecode,IsPrepaid,CylType,ActualDeliveryDate)
                SELECT  ROD.OrderRefNo,ROD.OrderQuantity,ROD.Distributorid,
                    ROD.OrderDate,ROD.OrderStatusCode,ROD.OrderSourceCode,
                    CASE WHEN ROD.Naturecode='16' THEN 'PMUY' ELSE 'NPMUY' END,
                    ROD.Pricecode,
                    CASE WHEN RPD.TransactionReferenceNumber IS NOT NULL THEN 'Y' ELSE 'N' END,
                    CASE WHEN ROD.Pricecode IN ('22','24') THEN 'C142' ELSE 'C5' END,
                    ROD.ActualDeliveryDate
                    FROM DCMs.tblRefillOrderDtls ROD WITH(NOLOCK)
                    LEFT OUTER JOIN esv.tblRefillPaymentDtls RPD  with(nolock)
                    ON RPD.OrderRefNo = ROD.OrderRefNo AND RPD.PaymentStatus='SUCCESS'
                    WHERE ROD.Naturecode NOT IN ('3','4')
                    AND ROD.OrderStatusCode !='CNCL'
                    AND (ROD.ActualDeliveryDate IS NULL
                    OR 	 CONVERT(DATE,ROD.OrderDate,120) >= CONVERT(DATE,GETDATE()-1,120)
                    OR 	ROD.ActualDeliveryDate >= CONVERT(DATE,GETDATE()-1,120))
                    AND ROD.Pricecode IN ('22','24','163','162')
            """
    fetch_data(cursor, query)    
    query = """
            SELECT DM.JDEDistributorCode,						
            O.ConsumerType	,O.IsPrepaid,O.CylType,O.OrderSourceCode,					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=0 THEN O.OrderQuantity ELSE 0 END) [Pending_0D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=1 THEN O.OrderQuantity ELSE 0 END) [Pending_1D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=2 THEN O.OrderQuantity ELSE 0 END) [Pending_2D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=3 THEN O.OrderQuantity ELSE 0 END) [Pending_3D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=4 THEN O.OrderQuantity ELSE 0 END) [Pending_4D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=5 THEN O.OrderQuantity ELSE 0 END) [Pending_5D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=6 THEN O.OrderQuantity ELSE 0 END) [Pending_6D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=7 THEN O.OrderQuantity ELSE 0 END) [Pending_7D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=8 THEN O.OrderQuantity ELSE 0 END) [Pending_8D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=9 THEN O.OrderQuantity ELSE 0 END) [Pending_9D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=10 THEN O.OrderQuantity ELSE 0 END) [Pending_10D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=11 THEN O.OrderQuantity ELSE 0 END) [Pending_11D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=12 THEN O.OrderQuantity ELSE 0 END) [Pending_12D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=13 THEN O.OrderQuantity ELSE 0 END) [Pending_13D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=14 THEN O.OrderQuantity ELSE 0 END) [Pending_14D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())=15 THEN O.OrderQuantity ELSE 0 END) [Pending_15D],					
                SUM(CASE WHEN O.ActualDeliveryDate IS NULL AND DATEDIFF(d,O.OrderDate,GETDATE())>15 THEN O.OrderQuantity ELSE 0 END) [Pending_Beyond15D],					
                SUM(CASE WHEN CONVERT(DATE,O.OrderDate,120) = CONVERT(DATE,GETDATE()-1,120) THEN O.OrderQuantity ELSE 0 END) BookingReceivedYesterday,					
                SUM(CASE WHEN O.ActualDeliveryDate = CONVERT(DATE,GETDATE()-1,120) THEN O.OrderQuantity ELSE 0 END) TotalSalesYesterday,					
                SUM(CASE WHEN CONVERT(DATE,O.OrderDate,120) = CONVERT(DATE,GETDATE(),120) THEN O.OrderQuantity ELSE 0 END) BookingReceivedToday,					
                SUM(CASE WHEN O.ActualDeliveryDate = CONVERT(DATE,GETDATE(),120) THEN O.OrderQuantity ELSE 0 END) TotalSalesToday					
                FROM #Order O WITH(NOLOCK)					
                INNER JOIN DCMs.tblDistributorMaster DM WITH(NOLOCK) ON O.Distributorid=DM.DistributorId					
            GROUP BY DM.JDEDistributorCode,O.ConsumerType,O.IsPrepaid,O.CylType,O.OrderSourceCode
            Order BY DM.JDEDistributorCode,O.ConsumerType,O.IsPrepaid,O.CylType,O.OrderSourceCode
            """
    data = fetch_data(cursor, query, getData=True)
        
    query = """ DROP TABLE #Order; """
    fetch_data(cursor, query)
    query = """ DROP TABLE #Group; """
    fetch_data(cursor, query)
    
    data = data.with_columns(System_Idx=pl.lit(""))
    data = data.with_columns(pl.col('System_Idx').map_elements(lambda x: str(uuid.uuid4().hex)))
        
    tblDistributorMaster = """ SELECT * FROM DCMs.tblDistributorMaster; """
    tblDistributorMaster = fetch_data(cursor, tblDistributorMaster, getData=True)
    
    tblDistributorMaster = tblDistributorMaster.with_columns(pl.col("JDEDistributorCode").fill_null(0).cast(pl.Int64).alias("JDEDistributorCode"))
    data = data.with_columns(pl.col("JDEDistributorCode").fill_null(0).cast(pl.Int64).alias("JDEDistributorCode"))
    # Getting SACode
    data = _merge_data(
        left_df=data, 
        right_df=tblDistributorMaster.select(["JDEDistributorCode", "DistributorName", "SACode", "StateCode", "DistrictCode", "TalukaCode", "CityCode"]), 
        left_on=["JDEDistributorCode"], 
        right_on=["JDEDistributorCode"], 
        how="left", 
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
    
    tblSAMaster = """ SELECT * FROM DCMs.tblSAMaster; """
    tblSAMaster = fetch_data(cursor, tblSAMaster, getData=True)
    
    # Getting SAName
    data = _merge_data(
        left_df=data, 
        right_df=tblSAMaster.select(["SACode", "ROCode", "SAName"]),
        left_on=["SACode"], 
        right_on=["SACode"], 
        how="left", 
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
        
    tblROMaster =  """ SELECT * FROM DCMs.tblROMaster; """
    tblROMaster = fetch_data(cursor, tblROMaster, getData=True)
    
    # Getting ROName
    data = _merge_data(
        left_df=data, 
        right_df=tblROMaster.select(["ROCode", "ZOCode", "ROName"]),
        left_on=["ROCode"], 
        right_on=["ROCode"],
        how="left", 
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
    
    tblZOMaster =  """ SELECT * FROM DCMs.tblZOMaster; """
    tblZOMaster = fetch_data(cursor, tblZOMaster, getData=True)
    
    # Getting ZOName
    data = _merge_data(
        left_df=data, 
        right_df=tblZOMaster.select(["ZOCode", "ZOName"]),
        left_on=["ZOCode"], 
        right_on=["ZOCode"], 
        how="left", 
        suffixes="_y",
        indicator=False
    )
        
    query = """ SELECT LookupCode,LookupValue FROM  dcms.tbllookupmaster WITH (nolock) WHERE LookupTypeCode='RefillOrderSourceCode' """
    get_source_details = fetch_data(cursor, query, getData=True)
    data = _merge_data(
        left_df=data,
        right_df=get_source_details,
        left_on=["OrderSourceCode"],
        right_on=["LookupCode"],
        how="left",
        suffixes="_y",
        indicator=False
    ).rename({"LookupValue": "OrderSourceName"})
    data = data.drop("LookupCode")
    
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
                
    connection.close()
    data = calculate_ageing(data)
    
    zoneMap = {
            "LPG - NORTH WEST ZONE": "NWZ",
            "LPG - NORTH ZONE": "NZ",
            "LPG - WEST ZONE": "WZ",
            "LPG - SOUTH CENTRAL ZONE": "SCZ",
            "LPG - SOUTH ZONE": "SZ",
            "LPG - NORTH CENTRAL ZONE": "NCZ",
            "LPG - EAST ZONE": "EZ"
            }
    
    data = data.with_columns(pl.col("ZOName").str.strip_chars().replace(zoneMap).alias("ZOName"))
    data = data.with_columns(pl.lit(datetime.datetime.now() - relativedelta(days=1)).alias("Execution_Date"))
    data = data.with_columns(pl.col("Execution_Date").dt.strftime("%B").alias("Execution_Month"))
    data = data.with_columns(pl.col("Execution_Date").dt.strftime("%Y").alias("Execution_Year"))
    data = data.with_columns(pl.col("Execution_Date").dt.strftime("%b-%Y").alias("Month-Year"))

    print("-"*25)
    print("Length of data Before Drop :", len(data))
    data = data.unique("System_Idx")
    data = data.drop("System_Idx")
    print("Length of data After Drop :", len(data))
    print("-"*25)
    insertToDB(data, "LPG_SALES_SUMMARY_DATA", indexing_col=("JDEDistributorCode", "ConsumerType", "IsPrepaid", "CylType"))
    
    data = data.with_columns(
        pl.when(
            pl.col("CylType").fill_null("") == "C142"
            ).then(pl.col("TotalSalesYesterday") * 14.2
        ).when(
            pl.col("CylType").fill_null("") == "C5"
            ).then(pl.col("TotalSalesYesterday") * 5).alias("sales_volume"))
    
    data = data.with_columns(
        pl.when(
            pl.col("CylType").fill_null("") == "C142"
            ).then(pl.col("BookingReceivedYesterday") * 14.2
        ).when(
            pl.col("CylType").fill_null("") == "C5"
            ).then(pl.col("BookingReceivedYesterday") * 5).alias("bookings_volume"))
    
    data = data.with_columns(
        pl.when(
            pl.col("CylType").fill_null("") == "C142"
            ).then(pl.col("Total_Pending") * 14.2
        ).when(
            pl.col("CylType").fill_null("") == "C5"
            ).then(pl.col("Total_Pending") * 5).alias("pendings_volume"))
    
    # New Changes
    month_map = {
                "April": 1,
                "May": 2,
                "June": 3,
                "July": 4,
                "August": 5,
                "September": 6,
                "October": 7,
                "November": 8,
                "December": 9,
                "January": 10,
                "February": 11,
                "March": 12
            }
    data = data.with_columns(pl.col("Execution_Month").replace(month_map).alias("Month_Number"))
    data = data.with_columns([
                        pl.when(pl.col("Execution_Date").dt.month() >= 4)
                        .then(pl.format("{}-{}",
                            pl.col("Execution_Date").dt.year(),
                            pl.col("Execution_Date").dt.year() + 1))
                        .otherwise(pl.format("{}-{}",
                            pl.col("Execution_Date").dt.year() - 1,
                            pl.col("Execution_Date").dt.year()))
                        .alias("Financial_Year")
                    ])
    for col in data.columns:
        data = data.rename({col: col.replace("-","_")})
    data = data.rename({"Execution_Month": "Month"})
    insertToDB(data, "lpg_cdcms_sales_summary", indexing_col=["ZOName", "Financial_Year", "Month", "Execution_Date"])
    
    # Inserting fresh data to today's table
    trunc_query = """ TRUNCATE lpg_todays_cdcms_sales_summary; """
    fetch_data(cursor, trunc_query, getData=False, params={
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            })
    insertToDB(data, "lpg_todays_cdcms_sales_summary", indexing_col=["ZOName"])
    
    # Updating monthly summary to monthly table
    monthly_query = """ 
                    SELECT 
                        "DistributorName", "ZOName", "ROName", "SAName", "ConsumerType", "CylType", "Month", "Execution_Year", "Month_Number", "Financial_Year",
                        SUM("TotalSalesYesterday") AS "TotalSalesYesterday", SUM("BookingReceivedYesterday") AS "BookingReceivedYesterday", 
                        SUM("sales_volume") AS "sales_volume", SUM("bookings_volume") AS "bookings_volume"
                    FROM
                        "lpg_cdcms_sales_summary"
                    GROUP BY
                        "DistributorName", "ZOName", "ROName", "SAName", "ConsumerType", "CylType", "Month", "Execution_Year", "Month_Number", "Financial_Year"
                    """
    trunc_query = """ TRUNCATE lpg_monthly_cdcms_sales_summary; """
    fetch_data(cursor, trunc_query, getData=False, params={
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            })
    monthly_data = fetch_data(cursor, monthly_query, getData=True, params={
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            })
    
    month_to_quarter = {
                    'April': 'Quarter-1', 'May': 'Quarter-1', 'June': 'Quarter-1',
                    'July': 'Quarter-2', 'August': 'Quarter-2', 'September': 'Quarter-2',
                    'October': 'Quarter-3', 'November': 'Quarter-3', 'December': 'Quarter-3',
                    'January': 'Quarter-4', 'February': 'Quarter-4', 'March': 'Quarter-4'
                }
    monthly_data = monthly_data.with_columns(pl.col("Month").replace(month_to_quarter).alias("Quarter"))
    
    insertToDB(monthly_data, "lpg_monthly_cdcms_sales_summary", indexing_col=["Month", "ZOName"])
    return data
        

def process_subsidy_data(data, cursor, code=""):
    query = """ SELECT * FROM CLDP_PFMS.tblRefillResponseBatchHeader """
    tblRefillResponseBatchHeader = fetch_data(cursor, query, getData=True)
        
    data = _merge_data(
        left_df=data,
        right_df=tblRefillResponseBatchHeader.select(["PFMS_Batch_ID", "Bank_Debit_Date"]),
        left_on=["PFMS_Batch_ID"],
        right_on=["PFMS_Batch_ID"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    
    if code == "payment":               
        query = """ SELECT * FROM "Subsidy_PaymentErrorMaster" """
        PaymentErrorCodeMaster = fetch_data(cursor, query, getData=True, params={
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            })
        # Getting PaymentError Description
        data = _merge_data(
            left_df=data, 
            right_df=PaymentErrorCodeMaster, 
            left_on=["PaymentErrorCode"], 
            right_on=["Code"], 
            how="left", 
            suffixes="_y",
            indicator=False
        )
    
    if code == "exception":
        # INNER JOIN CLDP_PFMS.tblCLDPErrorMaster E With(nolock) ON E.EXCEPTION_CODE = D.Exception_Code;
        query = """ SELECT * FROM "Subsidy_ExceptionMaster" """
        ExceptionMaster = fetch_data(cursor, query, getData=True, params={
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            })    
        
        # Getting Exception Name and Description
        data = _merge_data(
            left_df=data, 
            right_df=ExceptionMaster, 
            left_on=["Exception_Code"], 
            right_on=["EXCEPTION_CODE"],
            how="left", 
            suffixes="_y",
            indicator=False
        )
        
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
    
    tblDistributorMaster = """ SELECT * FROM DCMs.tblDistributorMaster; """
    tblDistributorMaster = fetch_data(cursor, tblDistributorMaster, getData=True)
    
    tblDistributorMaster = tblDistributorMaster.with_columns(pl.col("JDEDistributorCode").fill_null(0).cast(pl.Int64).alias("JDEDistributorCode"))
    data = data.with_columns(pl.col("Distributor_Code").fill_null(0).cast(pl.Int64).alias("Distributor_Code"))
    # Getting SACode
    data = _merge_data(
        left_df=data, 
        right_df=tblDistributorMaster.select(["JDEDistributorCode", "SACode", "StateCode"]),
        left_on=["Distributor_Code"],
        right_on=["JDEDistributorCode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
    
    tblSAMaster = """ SELECT * FROM DCMs.tblSAMaster; """
    tblSAMaster = fetch_data(cursor, tblSAMaster, getData=True)
    
    # Getting SAName
    data = _merge_data(
        left_df=data, 
        right_df=tblSAMaster.select(["SACode", "ROCode", "SAName"]),
        left_on=["SACode"], 
        right_on=["SACode"], 
        how="left", 
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
        
    tblROMaster =  """ SELECT * FROM DCMs.tblROMaster; """
    tblROMaster = fetch_data(cursor, tblROMaster, getData=True)
    
    # Getting ROName
    data = _merge_data(
        left_df=data, 
        right_df=tblROMaster.select(["ROCode", "ZOCode", "ROName"]),
        left_on=["ROCode"], 
        right_on=["ROCode"],
        how="left", 
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
    
    tblZOMaster =  """ SELECT * FROM DCMs.tblZOMaster; """
    tblZOMaster = fetch_data(cursor, tblZOMaster, getData=True)
    
    # Getting ZOName
    data = _merge_data(
        left_df=data, 
        right_df=tblZOMaster.select(["ZOCode", "ZOName"]),
        left_on=["ZOCode"], 
        right_on=["ZOCode"], 
        how="left", 
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
    data = data.with_columns(pl.col("Booking_Date").cast(pl.Utf8).map_elements(lambda x: datetime.datetime.strptime(x, "%Y-%m-%d")).alias("Booking_Date"))
    return data


def get_subsidy_failure_statistics():
    connection = get_db_connection()
    cursor = connection.cursor()
        
    query = """ SELECT 
                    CAST(Booking_Date AS DATE) AS Booking_Date, 
                    Exception_Code, 
                    Distributor_Code, 
                    Payment_IsDigital, 
                    Subsidy_Status, 
                    Product_Code, 
                    Consumer_Scheme,
                    COUNT(1) AS Refills,
                    COUNT(DISTINCT LPG_ID) AS Consumers,
                    PFMS_Batch_ID
                FROM CLDP_PFMS.tblDailyRefillBatchDetails D WITH (NOLOCK)
                WHERE Delivery_Date_Time >= '2024-10-01'
                    AND Exception_Code IS NOT NULL
                GROUP BY 
                    CAST(Booking_Date AS DATE),
                    Distributor_Code, 
                    Payment_IsDigital, 
                    Subsidy_Status, 
                    Product_Code, 
                    Consumer_Scheme,
                    Exception_Code,
                    PFMS_Batch_ID; """
    
    # data = _get_data(cursor, query)
    # INNER JOIN CLDP_PFMS.tblRefillResponseBatchHeader H With(nolock) ON H.PFMS_Batch_ID = D.PFMS_Batch_ID;
    # INNER JOIN CLDP_PFMS.tblCLDPErrorMaster E With(nolock) ON E.EXCEPTION_CODE = D.Exception_Code;
    # Commenting this for temporory
    exception_data = fetch_data(cursor, query, getData=True)
    
    query = """ SELECT 
                    CAST(Booking_Date AS DATE) AS Booking_Date, 
                    PaymentErrorCode,
                    Distributor_Code, 
                    Payment_IsDigital, 
                    Subsidy_Status, 
                    Product_Code, 
                    Consumer_Scheme,
                    COUNT(1) AS Refills,
                    COUNT(DISTINCT LPG_ID) AS Consumers,
                    PFMS_Batch_ID
                FROM CLDP_PFMS.tblDailyRefillBatchDetails D WITH (NOLOCK)
                WHERE Delivery_Date_Time >= '2024-10-01'
                    AND Payout_Status = 'FL'
                GROUP BY 
                    CAST(Booking_Date AS DATE), 
                    PaymentErrorCode,
                    Distributor_Code, 
                    Payment_IsDigital, 
                    Subsidy_Status, 
                    Product_Code, 
                    Consumer_Scheme,
                    PFMS_Batch_ID; """
    
    payment_error_data = fetch_data(cursor, query, getData=True)
    
    exception_data = process_subsidy_data(exception_data, cursor, "exception")
    payment_error_data = process_subsidy_data(payment_error_data, cursor, "payment")
            
    insertToDB(exception_data, "lpg_domestic_subsidy_exception", indexing_col=("Consumer_Scheme","Booking_Date","Product_Code"))    
    insertToDB(payment_error_data, "lpg_domestic_subsidy_payment_failure", indexing_col=("Consumer_Scheme","Booking_Date","Product_Code"))


def get_subsidy_central_stats():
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """ SELECT
                    D.Distributor_Code,
                    D.Consumer_Scheme,
                    CASE
                        WHEN MONTH(H.Bank_Debit_Date) >= 4 THEN
                            CONCAT(YEAR(H.Bank_Debit_Date), '-', YEAR(H.Bank_Debit_Date) + 1)
                        ELSE
                            CONCAT(YEAR(H.Bank_Debit_Date) - 1, '-', YEAR(H.Bank_Debit_Date))
                    END AS Financial_Year,
                    DATENAME(MONTH, H.Bank_Debit_Date) AS Month_Name,
                    COUNT(D.Refill_Id) AS Transaction_Count,
                    SUM(D.Net_Amt_Payable) AS SubsidyAmount,
                    COUNT(DISTINCT D.LPG_ID) AS Consumer_Count
                FROM
                    CLDP_PFMS.tblDailyRefillBatchDetails D WITH(NOLOCK)
                    INNER JOIN CLDP_PFMS.tblRefillResponseBatchHeader H WITH(NOLOCK)
                    ON H.PFMS_Batch_ID = D.PFMS_Batch_ID
                WHERE
                    D.Payout_Status = 'SU'
                GROUP BY
                    D.Consumer_Scheme,
                    D.Distributor_Code,
                    CASE
                        WHEN MONTH(H.Bank_Debit_Date) >= 4 THEN
                            CONCAT(YEAR(H.Bank_Debit_Date), '-', YEAR(H.Bank_Debit_Date) + 1)
                        ELSE
                            CONCAT(YEAR(H.Bank_Debit_Date) - 1, '-', YEAR(H.Bank_Debit_Date))
                    END,
                    DATENAME(MONTH, H.Bank_Debit_Date),
                    MONTH(H.Bank_Debit_Date)
                ORDER BY
                    Financial_Year,
                    MONTH(H.Bank_Debit_Date) """
    data = fetch_data(cursor, query, getData=True)
    data = data.with_columns(System_Idx=pl.lit(""))
    data = data.with_columns(pl.col('System_Idx').map_elements(lambda x: str(uuid.uuid4().hex)))

    tblDistributorMaster = """ SELECT * FROM DCMs.tblDistributorMaster; """
    tblDistributorMaster = fetch_data(cursor, tblDistributorMaster, getData=True)

    tblDistributorMaster = tblDistributorMaster.with_columns(pl.col("JDEDistributorCode").fill_null(0).cast(pl.Int64).alias("JDEDistributorCode"))
    data = data.with_columns(pl.col("Distributor_Code").fill_null(0).cast(pl.Int64).alias("JDEDistributorCode"))
    # Getting SACode
    data = _merge_data(
        left_df=data,
        right_df=tblDistributorMaster.select(["JDEDistributorCode", "DistributorName", "SACode", "StateCode", "DistrictCode", "TalukaCode", "CityCode"]),
        left_on=["JDEDistributorCode"],
        right_on=["JDEDistributorCode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)

    tblSAMaster = """ SELECT * FROM DCMs.tblSAMaster; """
    tblSAMaster = fetch_data(cursor, tblSAMaster, getData=True)

    # Getting SAName
    data = _merge_data(
        left_df=data,
        right_df=tblSAMaster.select(["SACode", "ROCode", "SAName"]),
        left_on=["SACode"],
        right_on=["SACode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)

    tblROMaster =  """ SELECT * FROM DCMs.tblROMaster; """
    tblROMaster = fetch_data(cursor, tblROMaster, getData=True)

    # Getting ROName
    data = _merge_data(
        left_df=data,
        right_df=tblROMaster.select(["ROCode", "ZOCode", "ROName"]),
        left_on=["ROCode"],
        right_on=["ROCode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)

    tblZOMaster =  """ SELECT * FROM DCMs.tblZOMaster; """
    tblZOMaster = fetch_data(cursor, tblZOMaster, getData=True)

    # Getting ZOName
    data = _merge_data(
        left_df=data,
        right_df=tblZOMaster.select(["ZOCode", "ZOName"]),
        left_on=["ZOCode"],
        right_on=["ZOCode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    zoneMap = {
            "LPG - NORTH WEST ZONE": "NWZ",
            "LPG - NORTH ZONE": "NZ",
            "LPG - WEST ZONE": "WZ",
            "LPG - SOUTH CENTRAL ZONE": "SCZ",
            "LPG - SOUTH ZONE": "SZ",
            "LPG - NORTH CENTRAL ZONE": "NCZ",
            "LPG - EAST ZONE": "EZ"
            }
    month_order = {'April': 0, 'May': 1, 'June': 2, 'July': 3, 'August': 4, 'September': 5,
                   'October': 6, 'November': 7, 'December': 8, 'January': 9, 'February': 10, 'March': 11}
    
    data = data.with_columns(pl.col("ZOName").str.strip_chars().replace(zoneMap).alias("ZOName"))
    data = data.with_columns(pl.lit(datetime.datetime.now()).alias("Execution_Date"))
    data = data.with_columns(pl.col("Month_Name").replace(month_order).alias("month_number"))
    data = data.rename({"Consumer_Scheme": "ConsumerType", "Month_Name": "Month"})
    data = data.unique("System_Idx")
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
    
    trunc_query = """ TRUNCATE lpg_cdcms_subsidy_central; """
    fetch_data(cursor, trunc_query, getData=False, params={
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            })
    insertToDB(data, "lpg_cdcms_subsidy_central", indexing_col=("ZOName", "Financial_Year", "Month"))
    print(data)


def calculate_financial_year(df):
    """
    Calculate financial year based on month number and year.
    Financial year starts in April (month_number 0) and ends in March (month_number 11)
    """
    df = df.with_columns([
        pl.col("month_number").cast(pl.Int64).alias("month_number"),
        pl.col("Year").cast(pl.Int64).alias("Year")
    ])
    return df.with_columns([
        pl.when(pl.col("month_number").cast(pl.Int64) <= 8)
        .then(
            pl.concat_str([
                pl.col("Year").cast(pl.Utf8),
                pl.lit("-"),
                (pl.col("Year") + 1).cast(pl.Utf8)
            ])
        )
        .otherwise(
            pl.concat_str([
                (pl.col("Year") - 1).cast(pl.Utf8),
                pl.lit("-"),
                pl.col("Year").cast(pl.Utf8)
            ])
        )
        .alias("Financial_Year")
    ])

def get_subsidy_state_stats():
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """ SELECT 
                    D.Distributor_Code,
                    D.Consumer_Scheme,
                    CASE
                        WHEN MONTH(H.Bank_Debit_Date) >= 4 THEN
                            CONCAT(YEAR(H.Bank_Debit_Date), '-', YEAR(H.Bank_Debit_Date) + 1)
                        ELSE
                            CONCAT(YEAR(H.Bank_Debit_Date) - 1, '-', YEAR(H.Bank_Debit_Date))
                    END AS Financial_Year,
                    DATENAME(MONTH, H.Bank_Debit_Date) AS Month_Name,
                    COUNT(D.Refill_Id) AS Transaction_Count,
                    SUM(D.Net_Amt_Payable) AS SubsidyAmount,
                    COUNT(DISTINCT D.LPG_ID) AS Consumer_Count
                FROM 
                    CLDP_PFMS.tblStateRefillBatchDetails D WITH(NOLOCK)
                    INNER JOIN CLDP_PFMS.tblRefillResponseBatchHeader H WITH(NOLOCK)
                    ON H.PFMS_Batch_ID = D.PFMS_Batch_ID
                WHERE 
                    D.Payout_Status = 'SU'
                GROUP BY 
                    D.Consumer_Scheme,
                    D.Distributor_Code,
                    CASE
                        WHEN MONTH(H.Bank_Debit_Date) >= 4 THEN
                            CONCAT(YEAR(H.Bank_Debit_Date), '-', YEAR(H.Bank_Debit_Date) + 1)
                        ELSE
                            CONCAT(YEAR(H.Bank_Debit_Date) - 1, '-', YEAR(H.Bank_Debit_Date))
                    END,
                    DATENAME(MONTH, H.Bank_Debit_Date),
                    MONTH(H.Bank_Debit_Date)
                ORDER BY 
                    Financial_Year,
                    MONTH(H.Bank_Debit_Date) """


    data = fetch_data(cursor, query, getData=True)
    print(data)
    data = data.with_columns(System_Idx=pl.lit(""))
    data = data.with_columns(pl.col('System_Idx').map_elements(lambda x: str(uuid.uuid4().hex)))

    tblDistributorMaster = """ SELECT * FROM DCMs.tblDistributorMaster; """
    tblDistributorMaster = fetch_data(cursor, tblDistributorMaster, getData=True)

    tblDistributorMaster = tblDistributorMaster.with_columns(pl.col("JDEDistributorCode").fill_null(0).cast(pl.Int64).alias("JDEDistributorCode"))
    data = data.with_columns(pl.col("Distributor_Code").fill_null(0).cast(pl.Int64).alias("JDEDistributorCode"))
    # Getting SACode
    data = _merge_data(
        left_df=data,
        right_df=tblDistributorMaster.select(["JDEDistributorCode", "DistributorName", "SACode", "StateCode", "DistrictCode", "TalukaCode", "CityCode"]),
        left_on=["JDEDistributorCode"],
        right_on=["JDEDistributorCode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)

    tblSAMaster = """ SELECT * FROM DCMs.tblSAMaster; """
    tblSAMaster = fetch_data(cursor, tblSAMaster, getData=True)

    # Getting SAName
    data = _merge_data(
        left_df=data,
        right_df=tblSAMaster.select(["SACode", "ROCode", "SAName"]),
        left_on=["SACode"],
        right_on=["SACode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)

    tblROMaster =  """ SELECT * FROM DCMs.tblROMaster; """
    tblROMaster = fetch_data(cursor, tblROMaster, getData=True)

    # Getting ROName
    data = _merge_data(
        left_df=data,
        right_df=tblROMaster.select(["ROCode", "ZOCode", "ROName"]),
        left_on=["ROCode"],
        right_on=["ROCode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)

    tblZOMaster =  """ SELECT * FROM DCMs.tblZOMaster; """
    tblZOMaster = fetch_data(cursor, tblZOMaster, getData=True)

    # Getting ZOName
    data = _merge_data(
        left_df=data,
        right_df=tblZOMaster.select(["ZOCode", "ZOName"]),
        left_on=["ZOCode"],
        right_on=["ZOCode"],
        how="left",
        suffixes="_y",
        indicator=False
    )

    zoneMap = {
            "LPG - NORTH WEST ZONE": "NWZ",
            "LPG - NORTH ZONE": "NZ",
            "LPG - WEST ZONE": "WZ",
            "LPG - SOUTH CENTRAL ZONE": "SCZ",
            "LPG - SOUTH ZONE": "SZ",
            "LPG - NORTH CENTRAL ZONE": "NCZ",
            "LPG - EAST ZONE": "EZ"
            }

    month_order = {'April': 0, 'May': 1, 'June': 2, 'July': 3, 'August': 4, 'September': 5,
                   'October': 6, 'November': 7, 'December': 8, 'January': 9, 'February': 10, 'March': 11}
    data = data.with_columns(pl.col("ZOName").str.strip_chars().replace(zoneMap).alias("ZOName"))
    data = data.with_columns(pl.lit(datetime.datetime.now()).alias("Execution_Date"))
    data = data.with_columns(pl.col("Month_Name").replace(month_order).alias("month_number"))
    data = data.rename({"Consumer_Scheme": "ConsumerType", "Month_Name": "Month"})
    data = data.unique("System_Idx")
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
    trunc_query = """ TRUNCATE lpg_cdcms_subsidy_state; """
    fetch_data(cursor, trunc_query, getData=False, params={
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            })

    insertToDB(data, "lpg_cdcms_subsidy_state", indexing_col=("ZOName", "Financial_Year", "Month"))


def get_new_connection_data():
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """ SELECT dm.JDEDistributorCode,
                CASE WHEN CM.NatureCode NOT IN ('16') THEN 'PMUY' ELSE 'NPMUY' END AS ConsumerType,
                FORMAT(csi.SVDate, 'yyyy-MM') MMYYYY,FORMAT(csi.SVDate, 'MMM-yyyy') MonthYear,COUNT(1) AS new_connection
                FROM DCMS.tblConsumerMaster CM WITH(NOLOCK)
                INNER JOIN DCMS.tblConsumerSVInfo CSI WITH(NOLOCK) ON CM.UniqueconsumerId = CSI.UniqueconsumerId
                INNER JOIN DCMS.tblDistributorMaster dm WITH(NOLOCK) ON dm.DistributorId = cm.DistributorID
                WHERE (SVTypeCode ='SVNEW' OR SVTypeCode='SVRECON' AND SVSubTypeCode='SV03')
                            AND CM.NatureCode NOT IN (3,4,10)
                            AND CSI.SVDate >='2023-04-01'
                            AND CSI.SVDate <GETDATE()
                GROUP BY  dm.JDEDistributorCode,CASE WHEN CM.NatureCode NOT IN ('16') THEN 'PMUY' ELSE 'NPMUY' END,
                FORMAT(csi.SVDate, 'yyyy-MM') ,FORMAT(csi.SVDate, 'MMM-yyyy') """
    data = fetch_data(cursor, query, getData=True)
    data = data.with_columns(System_Idx=pl.lit(""))
    data = data.with_columns(pl.col('System_Idx').map_elements(lambda x: str(uuid.uuid4().hex)))

    tblDistributorMaster = """ SELECT * FROM DCMs.tblDistributorMaster; """
    tblDistributorMaster = fetch_data(cursor, tblDistributorMaster, getData=True)

    tblDistributorMaster = tblDistributorMaster.with_columns(pl.col("JDEDistributorCode").fill_null(0).cast(pl.Int64).alias("JDEDistributorCode"))
    data = data.with_columns(pl.col("JDEDistributorCode").fill_null(0).cast(pl.Int64).alias("JDEDistributorCode"))
    # Getting SACode
    data = _merge_data(
        left_df=data,
        right_df=tblDistributorMaster.select(["JDEDistributorCode", "DistributorName", "SACode", "StateCode", "DistrictCode", "TalukaCode", "CityCode"]),
        left_on=["JDEDistributorCode"],
        right_on=["JDEDistributorCode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)

    tblSAMaster = """ SELECT * FROM DCMs.tblSAMaster; """
    tblSAMaster = fetch_data(cursor, tblSAMaster, getData=True)

    # Getting SAName
    data = _merge_data(
        left_df=data,
        right_df=tblSAMaster.select(["SACode", "ROCode", "SAName"]),
        left_on=["SACode"],
        right_on=["SACode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)

    tblROMaster =  """ SELECT * FROM DCMs.tblROMaster; """
    tblROMaster = fetch_data(cursor, tblROMaster, getData=True)

    # Getting ROName
    data = _merge_data(
        left_df=data,
        right_df=tblROMaster.select(["ROCode", "ZOCode", "ROName"]),
        left_on=["ROCode"],
        right_on=["ROCode"],
        how="left",
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)

    tblZOMaster =  """ SELECT * FROM DCMs.tblZOMaster; """
    tblZOMaster = fetch_data(cursor, tblZOMaster, getData=True)

    # Getting ZOName
    data = _merge_data(
        left_df=data,
        right_df=tblZOMaster.select(["ZOCode", "ZOName"]),
        left_on=["ZOCode"],
        right_on=["ZOCode"],
        how="left",
        suffixes="_y",
        indicator=False
    )

    zoneMap = {
            "LPG - NORTH WEST ZONE": "NWZ",
            "LPG - NORTH ZONE": "NZ",
            "LPG - WEST ZONE": "WZ",
            "LPG - SOUTH CENTRAL ZONE": "SCZ",
            "LPG - SOUTH ZONE": "SZ",
            "LPG - NORTH CENTRAL ZONE": "NCZ",
            "LPG - EAST ZONE": "EZ"
            }

    data = data.unique("System_Idx")
    month_order = {'Apr': 0, 'May': 1, 'Jun': 2, 'Jul': 3, 'Aug': 4, 'Sep': 5,
                   'Oct': 6, 'Nov': 7, 'Dec': 8, 'Jan': 9, 'Feb': 10, 'Mar': 11}
    data = data.with_columns(pl.col("ZOName").str.strip_chars().replace(zoneMap).alias("ZOName"))
    data = data.with_columns(pl.lit(datetime.datetime.now()).alias("Execution_Date"))

    data = data.with_columns(pl.col("MonthYear").str.split("-").list.get(0).alias("Month"))
    data = data.with_columns(pl.col("MonthYear").str.split("-").list.get(1).alias("Year"))
    data = data.with_columns(pl.col("Month").replace(month_order).alias("month_number"))

    data = calculate_financial_year(data)

    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)

    trunc_query = """ TRUNCATE lpg_cdcms_nc_data; """
    fetch_data(cursor, trunc_query, getData=False, params={
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            })
    insertToDB(data, "lpg_cdcms_nc_data", indexing_col=("ZOName", "MonthYear"))
    print(data)
    

def get_consumer_statistics():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    query = """ SELECT * FROM MISC.tblConsumerSummary; """
    data = fetch_data(cursor, query, getData=True)    
    data = data.with_columns(System_Idx=pl.lit(""))
    data = data.with_columns(pl.col('System_Idx').map_elements(lambda x: str(uuid.uuid4().hex)))
    
    tblDistributorMaster = """ SELECT * FROM DCMs.tblDistributorMaster; """
    tblDistributorMaster = fetch_data(cursor, tblDistributorMaster, getData=True)
    
    tblDistributorMaster = tblDistributorMaster.with_columns(pl.col("JDEDistributorCode").fill_null(0).cast(pl.Int64).alias("JDEDistributorCode"))
    data = data.with_columns(pl.col("DistributorCode").fill_null(0).cast(pl.Int64).alias("DistributorCode"))
    # Getting SACode
    data = _merge_data(
        left_df=data, 
        right_df=tblDistributorMaster.select(["JDEDistributorCode", "SACode", "StateCode"]), 
        left_on=["DistributorCode"], 
        right_on=["JDEDistributorCode"], 
        how="left", 
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
    
    tblSAMaster = """ SELECT * FROM DCMs.tblSAMaster; """
    tblSAMaster = fetch_data(cursor, tblSAMaster, getData=True)
    
    # Getting SAName
    data = _merge_data(
        left_df=data, 
        right_df=tblSAMaster.select(["SACode", "ROCode", "SAName"]),
        left_on=["SACode"], 
        right_on=["SACode"], 
        how="left", 
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
        
    tblROMaster =  """ SELECT * FROM DCMs.tblROMaster; """
    tblROMaster = fetch_data(cursor, tblROMaster, getData=True)
    
    # Getting ROName
    data = _merge_data(
        left_df=data, 
        right_df=tblROMaster.select(["ROCode", "ZOCode", "ROName"]),
        left_on=["ROCode"], 
        right_on=["ROCode"],
        how="left", 
        suffixes="_y",
        indicator=False
    )
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)
    
    tblZOMaster =  """ SELECT * FROM DCMs.tblZOMaster; """
    tblZOMaster = fetch_data(cursor, tblZOMaster, getData=True)
    
    # Getting ZOName
    data = _merge_data(
        left_df=data, 
        right_df=tblZOMaster.select(["ZOCode", "ZOName"]),
        left_on=["ZOCode"], 
        right_on=["ZOCode"], 
        how="left", 
        suffixes="_y",
        indicator=False
    )
            
    data = data.with_columns(
        pl.when(
            (pl.col("ConsumerCategory").fill_null("") == "A") &
            (pl.col("RelationshipStatus").fill_null("") == "A") &
            (pl.col("RelationshipSubStatus").str.contains("1A|2A|3A|4A"))
        ).then(pl.lit("Domestic")
        ).when(
            (pl.col("ConsumerCategory").fill_null("")=="D") &
        (pl.col("RelationshipStatus").fill_null("") == "A") &
        (pl.col("RelationshipSubStatus").str.contains("1A|2A|3A|4A"))
        ).then(pl.lit("NonDomestic")
        ).otherwise(pl.lit("Others")).alias("Category"))

    data = data.with_columns(
        pl.when(
            (pl.col("ConsumerCategory").fill_null("") == "A") &
            (pl.col("RelationshipStatus").fill_null("") == "A") &
            (pl.col("TypeofConsumer").fill_null("").cast(pl.Utf8) == "1") &
            (pl.col("RelationshipSubStatus").str.contains("1A|2A|3A|4A"))
        ).then(pl.lit("PMUY")
        ).when(
            (pl.col("ConsumerCategory").fill_null("") == "A") &
            (pl.col("RelationshipStatus").fill_null("") == "A") &
            (pl.col("TypeofConsumer").fill_null("").cast(pl.Utf8) == "2") &
            (pl.col("RelationshipSubStatus").str.contains("1A|2A|3A|4A"))
        ).then(pl.lit("NPMUY")
        ).otherwise(pl.lit("Others")).alias("SubCategory"))

    data = data.with_columns(
        pl.when(
            (pl.col("ConsumerCategory").fill_null("") == "A") &
            (pl.col("RelationshipStatus").fill_null("") == "A") &
            (pl.col("TypeofConsumer").fill_null("").cast(pl.Utf8) == "1") &
            (pl.col("RelationshipSubStatus").str.contains("1A|2A|3A|4A"))
        ).then(pl.lit("Active")
        ).when(
            (pl.col("ConsumerCategory").fill_null("") == "A") &
            (pl.col("RelationshipStatus").fill_null("") == "A") &
            (pl.col("TypeofConsumer").fill_null("").cast(pl.Utf8) == "2") &
            (pl.col("RelationshipSubStatus").str.contains("1A"))
        ).then(pl.lit("Active")
        ).otherwise(pl.lit("InActive")).alias("CategoryStatus"))
            
    for col in data.columns:
        if col.endswith("_y"):
            data = data.drop(col)    
    
    data = data.with_columns((pl.col("ConsumerCount").fill_null(0).cast(pl.Int64) - pl.col("eKYCCompleted").fill_null(0).cast(pl.Int64)).alias("eKYCPending"))
            
    zoneMap = {
            "LPG - NORTH WEST ZONE": "NWZ",
            "LPG - NORTH ZONE": "NZ",
            "LPG - WEST ZONE": "WZ",
            "LPG - SOUTH CENTRAL ZONE": "SCZ",
            "LPG - SOUTH ZONE": "SZ",
            "LPG - NORTH CENTRAL ZONE": "NCZ",
            "LPG - EAST ZONE": "EZ"
            }
    data = data.with_columns(pl.col("ZOName").alias("ZoneNames"))
    data = data.with_columns(pl.col("ZOName").str.strip_chars().replace(zoneMap).alias("ZOName"))
    
    trunc_query = ''' TRUNCATE TABLE "LPG_CONSUMERS_SUMMARY";  '''
    pg_conn = psycopg2.connect(
                host="10.90.38.162",
                database="hpcl_ceg",
                user="ceg_user",
                password="TTNqetkiJLPM50jC",
                port=5432
            )
    cur = pg_conn.cursor()
    cur.execute(trunc_query)
    pg_conn.commit()
    cur.close()
    pg_conn.close()
    
    print("-"*25)
    print("Length of data Before Drop :", len(data))
    data = data.unique("System_Idx")
    data = data.drop("System_Idx")
    print("Length of data After Drop :", len(data))
    print("-"*25)
    
    insertToDB(data, "LPG_CONSUMERS_SUMMARY", indexing_col=("ZOName", "RelationshipStatus", "RelationshipSubStatus", "ConsumerCategory", "CylinderType"))
    data = data.with_columns(pl.lit(datetime.datetime.now()).alias("Execution_Datetime"))
    data = data.with_columns(pl.col("Execution_Datetime").dt.strftime('%Y-%m-%d').map_elements(lambda x: datetime.datetime.strptime(x,'%Y-%m-%d')).alias("Execution_Date"))
    insertToDB(data, "LPG_CONSUMERS_OVERALL_SUMMARY", indexing_col=("ZOName", "Execution_Date", "RelationshipSubStatus", "ConsumerCategory", "CylinderType"))
    print(data)
                
if __name__=="__main__":
    get_pending_vs_delivered_data()
    get_consumer_statistics()
    get_new_connection_data()    
    get_subsidy_state_stats()
    get_subsidy_central_stats()