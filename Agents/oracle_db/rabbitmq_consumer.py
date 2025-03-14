import urdhva_base
import json
import pika
import asyncio
import traceback
import numpy as np
import pandas as pd
import hpcl_ceg_model
from postgresql import Postgresql
import utilities.helpers as helpers

class RabbitMQConsumer:
    def __init__(self):
        """Load RabbitMQ configuration from JSON file for the consumer."""
        with open("config.json", "r") as config_file:
            config = json.load(config_file)

        self.rabbitmq_host = config.get('conn_host', '')
        self.rabbitmq_port = int(config.get('conn_port', 5672))
        self.rabbitmq_user = config.get('conn_user', '')
        self.rabbitmq_password = config.get('conn_secret', '')
        self.queue_name = config.get('conn_channel', '')
        self.virtualhost = config.get('conn_vhost', '')

        self.table_rename_map = config.get("rename_tables", {})
        self.column_rename_map = config.get("column_rename", {})

    def rename_table(self, table_name):
        """Rename table based on config mapping."""
        return self.table_rename_map.get(table_name, table_name)

    def rename_columns(self, record):
        """Rename columns based on config mapping."""
        return {self.column_rename_map.get(k, k): v for k, v in record.items()}
    
    async def get_loc_details(self, sap_id):
        """Fetch location details asynchronously."""
        bu = 'TAS'
        return await helpers.get_location_details(bu, sap_id)
        
    async def process_message(self, body):
        """Process received RabbitMQ messages and store them in PostgreSQL asynchronously."""
        try:
            data = json.loads(body)  # Convert JSON string to dict

            if not isinstance(data, dict):
                print(f"⚠ Warning: Expected dict, but got {type(data)}")
                return

            db = Postgresql()

            for table_name, records in data.items():
                new_table_name = self.rename_table(table_name)

                if isinstance(records, list) and all(isinstance(record, dict) for record in records):
                    renamed_records = [self.rename_columns(record) for record in records]

                    print(f"✅ Processing table: {new_table_name} with {len(records)} records")

                    # Convert to DataFrame
                    df = pd.DataFrame(renamed_records)

                    # Convert all float to float, int to int, str to str, datetime to datetime, and handle NaN/Null values
                    for col in df.columns:
                        if df[col].dtype == np.float64 or df[col].dtype == np.float32:
                            df[col] = df[col].astype(float).fillna(0.0)  # Replace NaN with 0.0
                        elif df[col].dtype == np.int64 or df[col].dtype == np.int32:
                            df[col] = df[col].astype(int).fillna(0)  # Replace NaN with 0
                        elif df[col].dtype == object:
                            try:
                                df[col] = pd.to_datetime(df[col])  # Convert valid strings to datetime
                            except Exception:
                                df[col] = df[col].astype(str).fillna("")  # Ensure string type

                    # Fetch location details in bulk and update DataFrame
                    if "sap_id" in df.columns:
                        unique_sap_ids = df["sap_id"].dropna().unique()
                        location_mapping = {sap_id: await self.get_loc_details(sap_id) for sap_id in unique_sap_ids}

                        df["location_name"] = df["sap_id"].map(lambda sap_id: location_mapping.get(sap_id, [None, {}])[1].get("name", ""))
                        df["zone"] = df["sap_id"].map(lambda sap_id: location_mapping.get(sap_id, [None, {}])[1].get("zone", ""))
                    # Convert back to list of dictionaries
                    cleaned_records = df.to_dict(orient="records")
                    for record in cleaned_records:
                        for key, value in record.items():
                            if isinstance(value, pd.Timestamp):
                                record[key] = value.to_pydatetime() if not pd.isna(value) else None 
                            elif isinstance(value, float) and np.isnan(value):
                                record[key] = None  # Replace NaN floats with None
                            elif isinstance(value, int) and np.isnan(value):
                                record[key] = None  # Handle cases where NaN appears in integer fields
                            elif isinstance(value, (float, int)) and key in ["mfm_number", "bcu_number", "stock_code", "current_k_factor", "last_k_factor", "current_meter_factor", "last_meter_factor"]:
                                record[key] = str(value)  # Convert numbers to string format for safe SQL insertion
                    print("cleaned_records --> ", cleaned_records)

                    # Ensure await is used while creating the table
                    await db.create_table("public", new_table_name, cleaned_records)

                else:
                    print(f"⚠ Warning: Invalid data format for {table_name}")
        except Exception as e:
            print(traceback.format_exc())
            print(e)

    def consume_from_rabbitmq(self):
        """Consume messages from RabbitMQ synchronously and process asynchronously."""
        try:
            credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_password)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.rabbitmq_host,
                    port=self.rabbitmq_port,
                    virtual_host=self.virtualhost,
                    credentials=credentials)
            )
            channel = connection.channel()
            channel.queue_declare(queue=self.queue_name, durable=True)

            def callback(ch, method, properties, body):
                """Handle incoming RabbitMQ messages."""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.process_message(body))

            channel.basic_consume(queue=self.queue_name, on_message_callback=callback, auto_ack=True)

            print("Waiting for messages. To exit, press CTRL+C")
            channel.start_consuming()

        except Exception as ex:
            print(traceback.format_exc())
            print(f"Error consuming data from RabbitMQ: {ex}")

if __name__ == "__main__":
    consumer = RabbitMQConsumer()
    consumer.consume_from_rabbitmq()
