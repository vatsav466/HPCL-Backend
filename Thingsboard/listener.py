import urdhva_base
import os
import json
import pika
import requests
import threading
import sys
import time

# Configuration
RABBITMQ_HOST = urdhva_base.settings.rabbitmq_host
RABBITMQ_VHOST = urdhva_base.settings.rabbitmq_vhost
RABBITMQ_USER = urdhva_base.settings.rabbitmq_username
RABBITMQ_PASSWORD = urdhva_base.settings.rabbitmq_password
RABBITMQ_PREFIX_QUEUE = urdhva_base.settings.rabbitmq_queue
BASE_URL = urdhva_base.settings.things_board_url

class TelemetryService:
    """Handles telemetry data posting to ThingsBoard."""

    @staticmethod
    def load_site_data(site_id):
        """Load site data from a local JSON file."""
        filename = f"/opt/ceg/algo/things_board/device_data/{site_id}.json"
        if not os.path.exists(filename):
            print(f"Site data file not found: {filename}")
            return None
        try:
            with open(filename, "r") as file:
                return json.load(file)
        except Exception as e:
            print(f"Error reading site data file {filename}: {str(e)}")
            return None

    @staticmethod
    def post_telemetry(device_key, sensor_type, value):
        """Post telemetry data to the ThingsBoard API ."""
        headers = {"Content-Type": "application/json"}
        payload = {sensor_type: value}
        telemetry_url = f"{BASE_URL}/api/v1/{device_key}/telemetry"

        try:
           response = requests.post(telemetry_url, json=payload, headers=headers, timeout=10, verify=False)
           if response.status_code == 200:
             print(f"Telemetry posted for {device_key}: {sensor_type} -> {value}")
             return True
           else:
            print(f"Failed telemetry post for {device_key}. Status: {response.status_code} ")
        except requests.exceptions.RequestException as e:
           print(f"Network issue posting telemetry for {device_key}: {e}")

        return False

    @staticmethod
    def process_tags_data(location_id, tags_data, site_id):
        """Process all tags and post telemetry for all devices."""
        if location_id != site_id:
            print(f"Location ID {location_id} does not match SITE_ID {site_id}. Ignoring message.")
            return False

        site_data = TelemetryService.load_site_data(site_id)
        if not site_data:
            print(f"No site data found for SITE_ID {site_id}")
            return False

        all_success = True
        for component in site_data['data']:
            device_key = component['device_key']
            for sensor in component['sensors']:
                tag_path = sensor['sensor_tag']
                if tag_path in tags_data:
                    value = tags_data[tag_path]
                    success = TelemetryService.post_telemetry(device_key, sensor['sensor_name'], value)
                    if not success:
                        all_success = False
                else:
                    print(f"Missing TagPath: {tag_path} in message. Available tags: {list(tags_data.keys())}")
                    all_success = False
        return all_success


class RabbitMQListener:
    """Handles RabbitMQ connection and message listening with auto-reconnect."""

    def __init__(self, sap_id):
        self.queue_name = f"{RABBITMQ_PREFIX_QUEUE}{sap_id}"
        self.sap_id = sap_id
        self.reconnect_attempts = 0

    def connect(self):
        """Establish a RabbitMQ connection with retries."""
        while True:
            try:
                # print(f"Connecting to RabbitMQ queue: {self.queue_name} (Attempt {self.reconnect_attempts+1})...")
                credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=RABBITMQ_HOST,
                        virtual_host=RABBITMQ_VHOST,
                        credentials=credentials,
                        heartbeat=30,  # Send a heartbeat every 30 seconds
                        blocked_connection_timeout=300,  # Avoid blocking indefinitely
                    )
                )
                return connection
            except pika.exceptions.AMQPConnectionError as e:
                print(f"RabbitMQ connection failed for {self.queue_name}: {e}. Retrying in {2**self.reconnect_attempts} seconds...")
                time.sleep(2**self.reconnect_attempts)  # Exponential backoff
                self.reconnect_attempts += 1
            except Exception as e:
                print(f"Unexpected error while connecting to RabbitMQ: {e}")
                time.sleep(5)  # Wait before retrying

    def on_message(self, ch, method, properties, body):
        """Callback to handle incoming messages."""
        try:
            message = json.loads(body)
            print(f"Received message on {self.queue_name}: {message}")

            location_id = message.get("location_id")
            tags_data = message.get("tags_data", {})

            success = TelemetryService.process_tags_data(location_id, tags_data, location_id)

            ch.basic_ack(delivery_tag=method.delivery_tag)
            if success:
                print(f"All tags processed successfully for {self.queue_name}.")
            else:
                print(f"Some tags failed to process for {self.queue_name}.")
        except Exception as e:
            print(f"Error processing message on {self.queue_name}: {str(e)}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def start(self):
        """Start listening to the RabbitMQ queue with auto-reconnect."""
        while True:
            try:
                connection = self.connect()
                channel = connection.channel()
                channel.queue_declare(queue=self.queue_name, durable=True)

                print(f"Listening on queue: {self.queue_name}")
                channel.basic_consume(queue=self.queue_name, on_message_callback=self.on_message, auto_ack=False)
                channel.start_consuming()
            except (pika.exceptions.AMQPConnectionError, pika.exceptions.ChannelClosedByBroker) as e:
                print(f"RabbitMQ connection lost for {self.queue_name}: {e}. Reconnecting...")
                time.sleep(5)  # Wait before reconnecting
            except Exception as e:
                print(f"Unexpected error in listener for {self.queue_name}: {e}")
                time.sleep(5)


def main():
    sap_ids = ["1999", "1128", "2001", "11919"]  # Add all the SAP IDs you want to listen for
    threads = []
    for sap_id in sap_ids:
        listener = RabbitMQListener(sap_id)
        thread = threading.Thread(target=listener.start, daemon=True)
        thread.start()
        threads.append(thread)

    print("All RabbitMQ listeners started.")
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
