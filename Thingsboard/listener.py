import os
import json
import pika
import requests
import threading
import sys


# Configuration
RABBITMQ_HOST = '10.90.38.167'
RABBITMQ_VHOST = 'hpcl_ceg'
RABBITMQ_USER = 'hpcl_ceg'
RABBITMQ_PASSWORD = 'algo#ceg@4321'
RABBITMQ_PREFIX_QUEUE = "command_listener_"
SITE_ID = "1999"
BASE_URL = "http://10.90.38.164:8080"


class TelemetryService:
    """Handles telemetry data posting to ThingsBoard."""

    @staticmethod
    def load_site_data(site_id):
        """Load site data from a local JSON file."""
        filename = f"/Users/manohar/Documents/GitHub/dnc_backend_v2/things_board/device_data/{site_id}.json"
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
        """Post telemetry data to the ThingsBoard API."""
        headers = {"Content-Type": "application/json"}
        payload = {sensor_type: value}
        telemetry_url = f"{BASE_URL}/api/v1/{device_key}/telemetry"
        try:
            response = requests.post(telemetry_url, json=payload, headers=headers, verify=False)
            if response.status_code == 200:
                print(f"Successfully posted telemetry for deviceKey: {device_key}")
                return True
            else:
                print(f"Failed to post telemetry for deviceKey: {device_key}. Status code: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error posting telemetry for deviceKey: {device_key}. Error: {str(e)}")
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
                    print(f"No value found for TagPath: {tag_path} in message.")
                    all_success = False
        return all_success


class RabbitMQListener:
    """Handles RabbitMQ connection and message listening."""

    def __init__(self, sap_id):
        self.queue_name = f"{RABBITMQ_PREFIX_QUEUE}{sap_id}"
        self.sap_id = sap_id
        self.site_id = SITE_ID

    def on_message(self, ch, method, properties, body):
        """Callback to handle incoming messages."""
        try:
            message = json.loads(body)
            print(f"Received message on {self.queue_name}: {message}")
            location_id = message.get("location_id")
            tags_data = message.get("tags_data", {})
            success = TelemetryService.process_tags_data(location_id, tags_data, self.site_id)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            if success:
                print(f"All tags processed successfully for {self.queue_name}.")
            else:
                print(f"Some tags failed to process for {self.queue_name}.")
        except Exception as e:
            print(f"Error processing message on {self.queue_name}: {str(e)}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def start(self):
        """Start listening to the RabbitMQ queue."""
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    virtual_host=RABBITMQ_VHOST,
                    credentials=credentials
                )
            )
            channel = connection.channel()
            channel.queue_declare(queue=self.queue_name, durable=True)

            print(f"Listening for messages from queue: {self.queue_name}")
            channel.basic_consume(queue=self.queue_name, on_message_callback=self.on_message, auto_ack=False)
            channel.start_consuming()
        except Exception as e:
            print(f"Unexpected error in listener for {self.queue_name}: {e}")
            sys.exit(1)


def main():
    sap_ids = ["1999", "2000", "2001"]  # Add all the SAP IDs you want to listen for
    try:
        threads = []
        for sap_id in sap_ids:
            listener = RabbitMQListener(sap_id)
            thread = threading.Thread(target=listener.start)
            thread.start()
            threads.append(thread)

        print("All RabbitMQ listeners started.")
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("Listeners interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
