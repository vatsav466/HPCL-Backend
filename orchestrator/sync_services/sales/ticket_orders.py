import mysql.connector
import psycopg2
import polars as pl
import sys
import urdhva_base
import orchestrator.dbconnector.credential_loader as credential_loader


TARGET_TABLE = "pm_orders"


# ---------- CONNECTIONS ----------
def get_mysql_conn():
    return mysql.connector.connect(**credential_loader.get_credentials("TIBCO"))


def get_pg_conn():
    return psycopg2.connect(**credential_loader.get_credentials("APP_DB"))


# ---------- FETCH ACTIVE ORDERS ----------
def fetch_active_orders(mysql_conn):
    cur = mysql_conn.cursor(dictionary=True)
    cur.execute("""
        SELECT *
        FROM CONN_ENT.ZPMCV_ORDER_STG
        WHERE SYSTEM_STATUS_DESC != 'Technically completed'
        AND ORDER_TYPE = 'PM03'
        AND planning_plant BETWEEN 1000 AND 2000
    """)
    rows = cur.fetchall()
    cur.close()

    if not rows:
        return pl.DataFrame()

    df = pl.from_dicts(
        [{k: None if v is None else str(v) for k, v in row.items()} for row in rows],
        infer_schema_length=None
    )
    df.columns = [c.lower() for c in df.columns]
    return df


# ---------- CREATE TABLE ----------
def create_table_if_not_exists(pg_conn, df):
    cols = ", ".join([f'"{c}" TEXT' for c in df.columns])

    with pg_conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
                {cols},
                UNIQUE(order_no)
            )
        """)
    pg_conn.commit()


# ---------- DELETE COMPLETED ORDERS ----------
def delete_completed_orders(pg_conn, mysql_conn):
    cur = mysql_conn.cursor()
    cur.execute("""
        SELECT order_no
        FROM CONN_ENT.ZPMCV_ORDER_STG
        WHERE SYSTEM_STATUS_DESC = 'Technically completed'
        AND ORDER_TYPE = 'PM03'
        AND planning_plant BETWEEN 1000 AND 2000
    """)
    rows = cur.fetchall()
    cur.close()

    if not rows:
        print("No completed orders found in source")
        return

    order_list = [r[0] for r in rows]

    with pg_conn.cursor() as pg_cur:
        pg_cur.execute(
            f"DELETE FROM {TARGET_TABLE} WHERE order_no = ANY(%s)",
            (order_list,)
        )

    pg_conn.commit()
    print(f"Deleted {len(order_list)} completed orders from target")


# ---------- UPSERT ----------
def upsert_orders(pg_conn, df):
    if df.is_empty():
        print("No active orders to sync")
        return

    cols = df.columns
    col_list = ",".join([f'"{c}"' for c in cols])
    placeholders = ",".join(["%s"] * len(cols))

    update_clause = ",".join(
        [f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "order_no"]
    )

    sql = f"""
        INSERT INTO {TARGET_TABLE} ({col_list})
        VALUES ({placeholders})
        ON CONFLICT (order_no)
        DO UPDATE SET {update_clause}
    """

    data = df.rows()

    with pg_conn.cursor() as cur:
        cur.executemany(sql, data)

    pg_conn.commit()
    print(f"Upserted {df.height} active orders")


# ---------- MAIN SYNC ----------
def sync_pm_orders():
    mysql_conn = get_mysql_conn()
    pg_conn = get_pg_conn()

    try:
        print("Fetching active PM orders from source...")
        df = fetch_active_orders(mysql_conn)

        if df.is_empty():
            print("No active records found in source")
            return

        print("Ensuring target table exists...")
        create_table_if_not_exists(pg_conn, df)

        print("Deleting completed orders from target...")
        delete_completed_orders(pg_conn, mysql_conn)

        print("Upserting active orders...")
        upsert_orders(pg_conn, df)

        print("PM ORDER SYNC COMPLETED SUCCESSFULLY")

    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    sync_pm_orders()