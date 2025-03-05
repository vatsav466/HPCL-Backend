import urdhva_base
import json
import psycopg2
import polars as pl
import hpcl_ceg_model
import asyncio  # For handling async calls
import orchestrator.alerting.alert_factory as alert_factory


# Path to the JSON file
json_file = "config.json"

try:
    with open(json_file, "r", encoding="utf-8") as file:
        config = json.load(file)
    print("✅ JSON loaded successfully!")

    # Optional: Print some sample data to verify it's loaded correctly
    print(f"Oracle Host: {config['oracle']['host']}")
    print(f"PostgreSQL Database: {config['postgresql']['database_name']}")
    print(f"First Oracle Table: {config['oracle_tables'][0]}")

except json.JSONDecodeError as e:
    print(f"❌ JSON parsing error: {e}")
    config = None  # Prevent using an invalid config
except FileNotFoundError:
    print(f"❌ JSON file not found: {json_file}")
    config = None
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    config = None


class Postgresql:
    def __init__(self):
        """Initialize PostgreSQL connection details."""
        if config is None:
            raise ValueError("❌ Configuration not loaded. Cannot proceed.")
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
        print("sample_records --> ", sample_records)
        if not isinstance(sample_records, pl.DataFrame):
            sample_records = pl.DataFrame(sample_records)

        data = sample_records.to_dicts()

        # Check if the model exists in hpcl_ceg_model
        model = getattr(hpcl_ceg_model, table_name, None)
        if model is None:
            raise ValueError(f"Model '{table_name}' not found in hpcl_ceg_model.")

        # Upsert the data - Ensure `await` is used
        result = await model.bulk_update(data, upsert=True)  # Use upsert=True if needed
        print(result)
        
         # Process each record to create and close alerts
        if result:
          for record in data:
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
                'unique_id': record.get('id')
              }

              # Create Alert
              success, msg = await alert_factory.AlertFactory.create_alert(alert_data)
              if not success:
                  print(f"Failed to create alert: {msg}")
                  continue

              # Close Alert
              close_data = {
                'bu': 'TAS',
                'sop_id': sop_id,
                'sap_id': alert_data['sap_id'],
                'interlock_name': interlock_name,
                  
              }
              close_success, close_msg = await alert_factory.AlertFactory.close_alert(close_data)
              if not close_success:
                  print(f"Failed to close alert: {close_msg}")

            except Exception as e:
             print(f"Error : {str(e)}")
             continue

          return {"status": "Table created and alerts processed"}
        else:
            print("Bulk not posted")