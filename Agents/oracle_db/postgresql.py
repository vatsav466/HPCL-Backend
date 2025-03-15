import urdhva_base
import re
import json
import uuid
import asyncio
import psycopg2
import numpy as np
import pandas as pd
import polars as pl
import hpcl_ceg_model
from datetime import datetime, date
import orchestrator.alerting.alert_factory as alert_factory


# Path to the JSON file
json_file = "config.json"

try:
    with open(json_file, "r", encoding="utf-8") as file:
        config = json.load(file)
    print("JSON loaded successfully!")

    # Optional: Print some sample data to verify it's loaded correctly
    print(f"Oracle Host: {config['oracle']['host']}")
    print(f"PostgreSQL Database: {config['postgresql']['database_name']}")
    print(f"First Oracle Table: {config['oracle_tables'][0]}")

except json.JSONDecodeError as e:
    print(f"JSON parsing error: {e}")
    config = None  # Prevent using an invalid config
except FileNotFoundError:
    print(f"JSON file not found: {json_file}")
    config = None
except Exception as e:
    print(f"Unexpected error: {e}")
    config = None

class Postgresql:
    def __init__(self):
        """Initialize PostgreSQL connection details."""
        if config is None:
            raise ValueError("Configuration not loaded. Cannot proceed.")
        self.params = config['postgresql']

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

    async def create_table(self, schema_name, table_name, sample_records, primary_key=[], unique_key=[]):
        """Create a table and upsert sample records."""
        for record in sample_records:
            if "date" in record and isinstance(record["date"], str):
                try:
                    record["date"] = date.fromisoformat(record["date"])
                except ValueError:
                    # Alternative parsing if not in ISO format
                    record["date"] = pd.to_datetime(record["date"]).date()
            
            if "date_time" in record and isinstance(record["date_time"], str):
                try:
                    record["date_time"] = datetime.fromisoformat(record["date_time"])
                except ValueError:
                    # Alternative parsing if not in ISO format
                    record["date_time"] = pd.to_datetime(record["date_time"])
            
            for key, value in record.items():
                if value is None or (isinstance(value, float) and np.isnan(value)) or value is pd.NaT:
                    record[key] = None
                if key == "timestamp" and isinstance(value, str):  # Convert timestamp properly
                    record[key] = pd.to_datetime(value)  # Converts to datetime
                # Add these checks to your existing function
                if "created_date" in record and isinstance(record["created_date"], str):
                    record["created_date"] = pd.to_datetime(record["created_date"])

                if "cancelled_date" in record and isinstance(record["cancelled_date"], str):
                    record["cancelled_date"] = pd.to_datetime(record["cancelled_date"])

                if "entry_time" in record and isinstance(record["entry_time"], str):
                    record["entry_time"] = pd.to_datetime(record["entry_time"])

                if "exit_time" in record and isinstance(record["exit_time"], str):
                    record["exit_time"] = pd.to_datetime(record["exit_time"])
        print("sample_records --> ", sample_records)
        if not isinstance(sample_records, pl.DataFrame):
            sample_records = pl.DataFrame(sample_records)

        data = sample_records.to_dicts()

        # Check if the model exists in hpcl_ceg_model
        model = getattr(hpcl_ceg_model, table_name, None)
        if model is None:
            raise ValueError(f"Model '{table_name}' not found in hpcl_ceg_model.")

        # Upsert the data - Ensure `await` is used
        status, msg = await model.bulk_update(data, upsert=True, upsert_skip_keys=['alert_created'])  # Use upsert=True if needed
        # Get only alert not created records
        table_db_name = getattr(model, '__tablename__', table_name)
        query = f"""select * from "{table_db_name}" where alert_created = false"""
        resp = await model.get_aggr_data(query)
        
         # Process each record to create and close alerts
        if resp.get("data", []):
            for record in resp.get("data", []):
                try:
                    # Fetch config based on table name
                    interlock_name = config['interlock_name'].get(table_name)
                    severity = config['severity'].get(table_name, "Medium")
                    sop_id = config['sop_id'].get(table_name)

                    # Extract necessary fields from the record
                    alert_data = {
                        'bu': 'TAS',
                        'sop_id': sop_id,
                        'sap_id': record.get('sap_id'),
                        'interlock_name': interlock_name,
                        'severity': severity,
                        'alert_id': str(uuid.uuid1()),
                        'device_name': record.get('bcu_number'),
                        'device_type': 'Gantry'
                    }

                    # Create Alert
                    success, msg = await alert_factory.AlertFactory.create_alert(alert_data)
                    print("msg :", msg)
                    if not success:
                        print(f"Failed to create alert: {msg}")
                        continue
                    
                    # Set alert_created = true for alert created record
                    query = f"update {table_db_name} set alert_created = true where id = {record['id']}"
                    await model.update_by_query(query)

                    # Extract alert_id from response (assuming response contains alert_id)
                    query = (f"external_id='{alert_data['alert_id']}'")
                    params = urdhva_base.queryparams.QueryParams()
                    params.limit = 1
                    params.q = query
                    alert_resp = await hpcl_ceg_model.Alerts.get_all(params)
                    
                    body =  alert_resp.body
                    data = json.loads(body.decode('utf-8'))
                    if 'data' in data and data['data']:
                        alert_id = data['data'][0]['external_id']
                    else:
                        print(f'Alert not found for {alert_data['alert_id']}')
                        continue
                    # alert_id = msg.get("alert_id") if isinstance(msg, dict) else None
                    # Close Alert
                    close_data = {
                        'bu': 'TAS',
                        'sop_id': sop_id,
                        'sap_id': alert_data['sap_id'],
                        'interlock_name': interlock_name,
                        'alert_id' : alert_id
                        
                    }
                    close_success, close_msg = await alert_factory.AlertFactory.close_alert(close_data)
                    print("close_msg :", close_msg)
                    if not close_success:
                        print(f"Failed to close alert: {close_msg}")

                except Exception as e:
                    print(f"Error : {str(e)}")
                    continue

            return {"status": "Table created and alerts processed"}
        else:
            print("Bulk not posted")
