import json
import psycopg2
import polars as pl

# Load config
with open("config.json", 'r') as config_file:
    config = json.load(config_file)

psql = config['postgresql']

class Postgresql:
    def __init__(self):
        """Initialize PostgreSQL connection details."""
        self.params = psql

    def get_connection(self):
        """Establish a synchronous PostgreSQL connection."""
        return psycopg2.connect(
            host=self.params['host'],
            port=self.params['port'],
            user=self.params['user_name'],
            password=self.params['password'],
            dbname=self.params['database_name']
        )

    def get_default_schema(self):
        """Return the default schema."""
        return "public"

    def create_table(self, schema_name, table_name, sample_records, primary_key=[], unique_key=[]):
        """Create a table dynamically based on sample records and insert data."""
        schema_name = schema_name or self.get_default_schema()

        if not isinstance(sample_records, pl.DataFrame):
            sample_records = pl.DataFrame(sample_records)

        connection = self.get_connection()
        cursor = connection.cursor()

        dtype_dict = {
            'String': 'text', 'Int64': 'bigint', 'Int32': 'integer', 'Boolean': 'boolean',
            'Float64': 'double precision', 'Float32': 'double precision',
            'Datetime': 'timestamp', 'Utf8': 'text'
        }

        col_dtype = {col: dtype_dict.get(str(sample_records[col].dtype), 'text') for col in sample_records.columns}

        table_create_sql = ", ".join(f'"{col}" {dtype}' for col, dtype in col_dtype.items())

        if primary_key:
            pk_fields = ', '.join(f'"{s}"' for s in primary_key)
            table_create_sql += f', CONSTRAINT pk_{table_name} PRIMARY KEY ({pk_fields})'

        if unique_key:
            uk_fields = ', '.join(f'"{s}"' for s in unique_key)
            table_create_sql += f', CONSTRAINT uk_{table_name} UNIQUE ({uk_fields})'

        full_table_name = f'"{schema_name}"."{table_name}"'
        create_table_sql = f'CREATE TABLE IF NOT EXISTS {full_table_name} ({table_create_sql})'

        try:
            print(f"Executing SQL: {create_table_sql}")
            cursor.execute(create_table_sql)
            connection.commit()
        except Exception as e:
            print(f"❌ Error creating table: {e}")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()

        # Insert data after table creation
        self.insert_data(schema_name, table_name, sample_records)

    def insert_data(self, schema_name, table_name, records):
        """
        Insert data into PostgreSQL table with upsert (INSERT ON CONFLICT DO UPDATE) 
        using all columns as conflict keys.
        """
        if not isinstance(records, pl.DataFrame) or records.is_empty():
            print(f"⚠ Warning: No records to insert into {table_name}.")
            return

        schema_name = schema_name or self.get_default_schema()
        connection = self.get_connection()
        cursor = connection.cursor()

        columns = records.columns
        values_placeholder = ', '.join(['%s'] * len(columns))

        # Generate the conflict clause using all columns
        conflict_target = ", ".join([f'"{col}"' for col in columns])
        update_assignments = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in columns])

        insert_query = f'INSERT INTO "{schema_name}"."{table_name}" ({", ".join([f'"{col}"' for col in columns])}) VALUES ({values_placeholder})'
        
        # Use ON CONFLICT with a unique constraint that includes all columns
        upsert_query = f"""
            {insert_query}
            ON CONFLICT ({conflict_target}) DO UPDATE 
            SET {update_assignments}
        """

        try:
            values = [tuple(row) for row in records.iter_rows()]
            cursor.executemany(upsert_query, values)
            connection.commit()
            print(f"✅ {len(values)} records upserted into {table_name}")
        except Exception as e:
            print(f"❌ Error upserting data: {e}")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()

