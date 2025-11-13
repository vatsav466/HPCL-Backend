import mysql.connector
import sys
import psycopg2
import polars as pl
sys.path.append("/opt/ceg/algo")
import orchestrator.dbconnector.credential_loader as credential_loader

# ---------- CONFIGURATION ----------
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "password",
    "database": "source_db",
    "port": 3306,
}

SOURCE_TABLE = "CONN_ENT.ZSDCV_AY_INV3_TILL_DATE"
TARGET_TABLE = "sales_trips_till_date"
INCREMENTAL_KEY = "syncdt"  # date
USER_DEFINED_WHERE = (
    "division = '11' AND load_status = '6' AND qty_shortage > '0' AND sales_org = '7000'"
)
CONFLICT_COLUMNS = ["invoice_no", "vehicle_id", "sap_id", "item_no"]

# MySQL → PostgreSQL type mapping
MYSQL_TO_PG_TYPE_MAP = {
    "int": "INTEGER",
    "bigint": "BIGINT",
    "varchar": "VARCHAR",
    "text": "TEXT",
    "datetime": "TIMESTAMP",
    "float": "FLOAT",
    "double": "DOUBLE PRECISION",
    "tinyint": "SMALLINT",
    "decimal": "NUMERIC",
}

ITEM_NAME_MAP = {
    2812000: "HSD",
    4210000: "EBMS 15%",
    4383000: "EBMS 20% P95",
    2815000: "B5 HSD",
    2814000: "EBMS 10%",
    4211000: "EBMS 15 % P95",
    2813000: "EBMS 5%",
    2820000: "B7 HSD",
    2822000: "EBMS 20%",
    3912000: "HSD TURBO",
    3925000: "EBMS 12% POWER",
    3672000: "EBMS 11% P95",
}


# ---------- CONNECTION HELPERS ----------
def get_mysql_connection():
    """Connect to MySQL"""
    return mysql.connector.connect(**credential_loader.get_credentials('TIBCO'))


def get_postgres_connection():
    """Connect to Postgres"""
    return psycopg2.connect(**credential_loader.get_credentials('APP_DB'))


# ---------- MYSQL CHECK HELPERS ----------
def mysql_table_exists(conn, table_name: str) -> bool:
    """Check if MySQL table exists"""
    schema, _, tbl = table_name.partition(".")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name=%s;", (schema, tbl))
    exists = cur.fetchone()[0] > 0
    cur.close()
    return exists


def mysql_table_has_data(conn, table_name: str) -> bool:
    """Check if MySQL table has data"""
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table_name};")
    count = cur.fetchone()[0]
    cur.close()
    return count > 0


# ---------- LOCATION MASTER ----------
def get_location_master_data(pg_conn):
    """Fetch location master data from Postgres"""
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT sap_id, name AS plant_nm, zone AS zone_nm, region, bu AS sbu_nm
        FROM location_master
    """)
    rows = cur.fetchall()
    columns = [col[0].lower() for col in cur.description]
    cur.close()
    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows, schema=columns)


def sync_location_master(pg_conn, df: pl.DataFrame) -> pl.DataFrame:
    """Merge location master data into main DF"""
    lm_df = get_location_master_data(pg_conn)
    if lm_df.is_empty():
        print("⚠️ location_master table returned no data, skipping enrichment.")
        return df

    if "supply_loc" in df.columns:
        df = df.with_columns(pl.col("supply_loc").cast(pl.Utf8).str.replace_all(r"^00+", ""))
    if "sap_id" in lm_df.columns:
        lm_df = lm_df.with_columns(pl.col("sap_id").cast(pl.Utf8).str.replace_all(r"^00+", ""))

    if "supply_loc" in df.columns:
        df = df.join(lm_df, left_on="supply_loc", right_on="sap_id", how="left")
        df = df.rename({"supply_loc": "sap_id"})
        print(f"✅ Enriched with location_master → total rows: {df.height}")
    else:
        print("⚠️ Column 'supply_loc' not found in source data, skipping enrichment.")

    return df


# ---------- TRANSFORMATION HOOK ----------
def enrich_data(pg_conn, df: pl.DataFrame) -> pl.DataFrame:
    """Main enrichment entry"""
    df.columns = [col.lower() for col in df.columns]
    df = sync_location_master(pg_conn, df)
    # You can add more enrichment steps here (e.g. ITEM_NAME_MAP mapping)
    if any(c.lower() == "item_no" for c in df.columns):
        # Handle column name case variations (e.g., ITEM_NO or item_no)
        item_col = next(c for c in df.columns if c.lower() == "item_no")

        df = df.with_columns([
            pl.col(item_col)
            .cast(pl.Int64, strict=False)
            .map_elements(lambda x: ITEM_NAME_MAP.get(int(x)) if x and str(x).isdigit() and int(
                x) in ITEM_NAME_MAP else None)
            .alias("material_group_nm")
        ])
        print(" Added 'material_group_nm' column based on item_no mapping")
    else:
        print(" 'item_no' column not found — skipping material_group_nm mapping")
    return df


# ---------- SYNC HELPERS ----------
def get_last_sync_key(pg_conn, table, key_column):
    with pg_conn.cursor() as cur:
        cur.execute(f'SELECT MAX({key_column}::DATE) FROM "{table}"')
        result = cur.fetchone()
        return result[0] if result and result[0] is not None else None


def fetch_mysql_data(conn, table, key_column, last_key, user_where=None):
    """Fetch incremental + user-filtered data from MySQL"""
    base_query = f"SELECT * FROM {table}"
    conditions = []
    params = []

    if user_where:
        conditions.append(f"({user_where})")

    if last_key is not None:
        conditions.append(f"{key_column} >= %s")
        params.append(last_key)

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    cur = conn.cursor(dictionary=True)
    cur.execute(base_query, params)
    rows = cur.fetchall()
    cur.close()

    if not rows:
        return pl.DataFrame()

    return pl.DataFrame(rows)


def ensure_postgres_columns(pg_conn, df: pl.DataFrame, table: str):
    """Ensure missing columns in Postgres are created"""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            (table.split(".")[-1],),
        )
        existing = {row[0]: row[1] for row in cur.fetchall()}

        for col, dtype in zip(df.columns, df.dtypes):
            if col not in existing:
                pg_type = map_polars_dtype_to_pg(dtype)
                alter_sql = f'ALTER TABLE {table} ADD COLUMN "{col}" {pg_type};'
                print(f"🧩 Adding missing column: {col} ({pg_type})")
                cur.execute(alter_sql)
    pg_conn.commit()


def map_polars_dtype_to_pg(dtype) -> str:
    """Convert Polars dtype to Postgres"""
    if dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64):
        return "BIGINT"
    elif dtype in (pl.Float32, pl.Float64):
        return "DOUBLE PRECISION"
    elif dtype == pl.Utf8:
        return "TEXT"
    elif dtype == pl.Boolean:
        return "BOOLEAN"
    elif dtype in (pl.Datetime, pl.Date):
        return "TIMESTAMP"
    else:
        return "TEXT"

def ensure_unique_constraint(pg_conn, table: str, conflict_columns: list[str]):
    """Ensure a unique constraint exists for the conflict columns in Postgres."""
    constraint_name = f"{table.split('.')[-1]}{''.join(conflict_columns)}_uniq"
    joined_cols = ", ".join(f'"{c}"' for c in conflict_columns)

    with pg_conn.cursor() as cur:
        # Check existing unique indexes/constraints
        cur.execute(
            """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = %s
              AND constraint_type = 'UNIQUE'
            """,
            (table.split(".")[-1],),
        )
        existing_constraints = [r[0] for r in cur.fetchall()]

        if constraint_name not in existing_constraints:
            print(f"⚙️ Creating UNIQUE constraint '{constraint_name}' on ({joined_cols})...")
            alter_sql = f'ALTER TABLE {table} ADD CONSTRAINT {constraint_name} UNIQUE ({joined_cols});'
            cur.execute(alter_sql)
            pg_conn.commit()
            print(f"✅ Unique constraint '{constraint_name}' created.")
        else:
            print(f"✅ Unique constraint '{constraint_name}' already exists.")

def upsert_postgres(pg_conn, df: pl.DataFrame, table: str):
    """Upsert (INSERT ... ON CONFLICT DO UPDATE)"""
    if df.is_empty():
        print("✅ No new data to sync.")
        return
    ensure_unique_constraint(pg_conn, table, conflict_columns=CONFLICT_COLUMNS)
    cols = df.columns
    col_names = ",".join(f'"{c}"' for c in cols)
    placeholders = ",".join(["%s"] * len(cols))
    conflict_cols = ",".join(f'"{c}"' for c in CONFLICT_COLUMNS)
    update_clause = ",".join([f'"{c}" = EXCLUDED."{c}"' for c in cols if c not in CONFLICT_COLUMNS])

    upsert_sql = f"""
        INSERT INTO {table} ({col_names})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_cols}) DO UPDATE
        SET {update_clause};
    """

    data = [tuple(row) for row in df.to_numpy()]
    with pg_conn.cursor() as cur:
        cur.executemany(upsert_sql, data)
    pg_conn.commit()
    print(f"✅ Upserted {df.height} records into {table}.")

def sync_data():
    """Main sync flow"""
    mysql_conn = get_mysql_connection()
    pg_conn = get_postgres_connection()

    try:
        # 1️⃣ Check table existence
        if not mysql_table_exists(mysql_conn, SOURCE_TABLE):
            print(f"⚠️ MySQL table '{SOURCE_TABLE}' does not exist. Skipping sync.")
            return

        # 2️⃣ Check data availability
        if not mysql_table_has_data(mysql_conn, SOURCE_TABLE):
            print(f"⚠️ MySQL table '{SOURCE_TABLE}' has no data. Skipping sync.")
            return

        # 3️⃣ Get last incremental key
        last_key = get_last_sync_key(pg_conn, TARGET_TABLE, INCREMENTAL_KEY)

        print(f"🔑 Last synced key: {last_key}")

        # 4️⃣ Fetch data (with user WHERE)
        df = fetch_mysql_data(mysql_conn, SOURCE_TABLE, INCREMENTAL_KEY, last_key, USER_DEFINED_WHERE)
        print(f"📥 Fetched {df.height} rows from MySQL")

        if df.is_empty():
            print("✅ Nothing new to sync.")
            return

        # 5️⃣ Enrich data
        df = enrich_data(pg_conn, df)

        # 6️⃣ Ensure schema
        ensure_postgres_columns(pg_conn, df, TARGET_TABLE)

        # 7️⃣ Upsert
        upsert_postgres(pg_conn, df, TARGET_TABLE)

    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    sync_data()
