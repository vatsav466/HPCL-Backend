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

    async def cal_host_manual_fan_printed(self, data):
        """
        Calculate whether to create an actionable alert based on manual vs auto fan count comparison.
        Returns True if we should close the alert, False if we should keep it open (actionable).
        """
        data = pd.DataFrame(data)
        
        # Get the last record of the day (assuming data is sorted by timestamp)
        if data.empty:
            return False  # No data, no alert needed
        
        # Get the auto fan count and calculate the 5% tolerance
        total_fan_count = data['total_count'].iloc[-1]  # Get the latest record
        total_fan_with_tolerance = total_fan_count * 0.05  # Add 5% tolerance
        
        # Get the manual fan count
        manual_fan_count = data['manual_fan_count'].iloc[-1]
        
        # If manual fan count is greater than auto fan count + tolerance, 
        if manual_fan_count == 0:
            return False, "Manual FAN Count is Zero", "No manual FAN was printed"
        if manual_fan_count > total_fan_with_tolerance:
            return (True, 
                        "Manual FAN printed more than 5% of total TT loaded", 
                        f"{manual_fan_count} is less than {total_fan_with_tolerance} with 5%"
                    )
        elif manual_fan_count < total_fan_with_tolerance:
            return (True, 
                        "Manual FAN printed less than 5% of total TT loaded", 
                        f"{manual_fan_count} is less than {total_fan_with_tolerance} with 5%"
                    )


    async def cal_unauthorized_flow(self, total_net):
        if total_net > 5:
            return True, "Unauthorized flow_BCU"
        return False, ""

    async def create_cancel_tt_report(self, data):
        to_date = urdhva_base.utilities.get_present_time().strftime("%Y-%m-%d")
        query = f"""select id from alerts where interlock_name = 'Cancel TT Reported' and vehicle_number = '{data["vehicle_number"]}' """ \
                f"""and created_at::DATE = '{to_date}'"""
        resp = await hpcl_ceg_model.Alerts.get_aggr_data(query)
        if resp.get("data", []):
            alert_data = await hpcl_ceg_model.Alerts.get(resp.get("data", [])[0]["id"])
            data['alert_id'] = alert_data['external_id']
            action_msg = f"Truck Number: {data['vehicle_number']} \n Compartment Number: {data['device_msg']}"
            input_data = {
                "action_type": "Cancelled",
                "action_msg": data.get("device_msg", "")
            }
            await alert_manager.AlertAction().update_alert_history(
                        input_data=input_data, alert_data=alert_data
                    )
            return True, "Success", data
        
        status, msg = await alert_factory.AlertFactory.create_alert(alert_data)
        return status, msg, data
    
    async def close_created_alert(self, alert_data):
        # Extract alert_id from response (assuming response contains alert_id)
        query = (f"""external_id='{alert_data["alert_id"]}'""")
        params = urdhva_base.queryparams.QueryParams()
        params.limit = 1
        params.q = query
        alert_resp = await hpcl_ceg_model.Alerts.get_all(params)
        
        body =  alert_resp.body
        data = json.loads(body.decode('utf-8'))
        if 'data' in data and data['data']:
            alert_id = data['data'][0]['external_id']
        else:
            print(f"Alert not found for {alert_data['alert_id']}")
            return
        # alert_id = msg.get("alert_id") if isinstance(msg, dict) else None
        # Close Alert
        close_data = {
            'bu': 'TAS',
            'sop_id': alert_data['sop_id'],
            'sap_id': alert_data['sap_id'],
            'interlock_name': alert_data['interlock_name'],
            'alert_id' : alert_data['alert_id']
            
        }
        close_success, close_msg = await alert_factory.AlertFactory.close_alert(close_data)
        print("close_msg :", close_msg)
        if not close_success:
            print(f"Failed to close alert: {close_msg}")

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
                    
                if "transaction_end_time" in record and isinstance(record["transaction_end_time"], str):
                    record["transaction_end_time"] = pd.to_datetime(record["transaction_end_time"])
        print("sample_records --> ", sample_records)
        if not isinstance(sample_records, pl.DataFrame):
            sample_records = pl.DataFrame(sample_records)

        data = sample_records.to_dicts()

        # Check if the model exists in hpcl_ceg_model
        model = getattr(hpcl_ceg_model, table_name, None)
        if model is None:
            raise ValueError(f"Model '{table_name}' not found in hpcl_ceg_model.")

        table_db_name = getattr(model, '__tablename__', table_name)
        if table_db_name == 'host_unauthorised_flow':
            data = [x for x in data if x['nettotalizer'] > 0]

        # Upsert the data - Ensure `await` is used
        status, msg = await model.bulk_update(data, upsert=True, upsert_skip_keys=['alert_created'])  # Use upsert=True if needed
        
        # Get only alert not created records
        to_date = urdhva_base.utilities.get_present_time().strftime("%Y-%m-%d")
        query = f"""select * from "{table_db_name}" where alert_created = false"""
        if table_db_name == 'host_manual_fan_printed':
            query = f"""select * from "{table_db_name}" where date::DATE = '{to_date}' and manual_fan_count !=0 order by date_time asc"""
        resp = await model.get_aggr_data(query)
        
        if table_db_name == 'host_manual_fan_printed':
            to_day = urdhva_base.utilities.get_present_time().strftime("%H")
            if int(to_day) == 19:
                is_close_alert = False
                interlock_name = config['interlock_name'].get(table_name)
                severity = config['severity'].get(table_name, "Medium")
                sop_id = config['sop_id'].get(table_name)
                device_msg = ""

                result = await self.cal_host_manual_fan_printed(resp.get("data", []))

                if isinstance(result, tuple) and len(result) == 3:
                    is_close_alert, interlock_name, device_msg = result

                alert_data = {
                    'bu': 'TAS',
                    'sop_id': sop_id,
                    'sap_id': data[0].get('sap_id'),
                    'interlock_name': interlock_name,
                    'severity': severity,
                    'alert_id': str(uuid.uuid1()),
                    'device_name': data[0].get('bcu_number'),
                    'device_type': 'Gantry',
                    'vehicle_number': data[0].get('truck_number', ''),
                    'device_msg': device_msg
                }

                success, msg = await alert_factory.AlertFactory.create_alert(alert_data)
                print("msg :", msg)
                if is_close_alert:
                    await self.close_created_alert(alert_data=alert_data)
                return {"status": "Table created and alerts processed"}

        if table_db_name == 'host_unauthorised_flow':
            unauthorised_records = resp.get("data", [])
            # Compute the total sum of all nettotalizer values
            total_net = sum(float(record.get("nettotalizer", 0)) for record in unauthorised_records if float(record.get("nettotalizer", 0)) != 0)
            # Extract unique BCU numbers
            bcu_numbers = sorted(set(record.get("bcu_number", "") for record in unauthorised_records))

            # Check if unauthorized flow should be triggered based on total_net
            is_close_alert, interlock_name = await self.cal_unauthorized_flow(total_net)

            # Construct device message
            device_msg = f"BCU Numbers: {', '.join(bcu_numbers)}, Total Net Totalizer: {total_net}"

            # Do something with is_close_alert, interlock_name, device_msg

         # Process each record to create and close alerts
        if resp.get("data", []):
            for record in resp.get("data", []):
                try:
                    # Fetch config based on table name
                    is_close_alert = False
                    interlock_name = config['interlock_name'].get(table_name)
                    severity = config['severity'].get(table_name, "Medium")
                    sop_id = config['sop_id'].get(table_name)
                    device_msg = ""
                    if interlock_name == 'Cancel TT Reported':
                        device_msg = str(record.get("compartment_number", ""))

                    # Extract necessary fields from the record
                    alert_data = {
                        'bu': 'TAS',
                        'sop_id': sop_id,
                        'sap_id': record.get('sap_id'),
                        'interlock_name': interlock_name,
                        'severity': severity,
                        'alert_id': str(uuid.uuid1()),
                        'device_name': record.get('bcu_number'),
                        'device_type': 'Gantry',
                        'vehicle_number': record.get('truck_number', ''),
                        'device_msg': device_msg
                    }

                    # Create Alert
                    if interlock_name == 'Cancel TT Reported':
                        is_close_alert = True
                        success, msg, alert_data = await self.create_cancel_tt_report(alert_data)
                    else:
                        success, msg = await alert_factory.AlertFactory.create_alert(alert_data)
                        print("msg :", msg)
                        if not success:
                            print(f"Failed to create alert: {msg}")
                            continue
                    
                    # Set alert_created = true for alert created record
                    query = f"update {table_db_name} set alert_created = true where id = {record['id']}"
                    await model.update_by_query(query)

                    # Close alert
                    if is_close_alert:
                        await self.close_created_alert(alert_data=alert_data)

                except Exception as e:
                    print(f"Error : {str(e)}")
                    continue

            return {"status": "Table created and alerts processed"}
        else:
            print("Bulk not posted")
            return {"status": "No data to create alert"}
