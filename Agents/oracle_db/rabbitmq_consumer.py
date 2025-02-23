import json
import pika
import traceback
from postgresql import Postgresql

# Load config
with open("config.json", 'r') as config_file:
    config = json.load(config_file)

class RabbitMQConsumer:
    def __init__(self):
        """Load RabbitMQ configuration from JSON file for the consumer."""
        self.rabbitmq_host = config.get('conn_host', '')
        self.rabbitmq_port = int(config.get('conn_port', 5672))
        self.rabbitmq_user = config.get('conn_user', '')
        self.rabbitmq_password = config.get('conn_secret', '')
        self.queue_name = config.get('conn_channel', '')
        self.virtualhost = config.get('conn_vhost', '')

    def consume_from_rabbitmq(self, callback):
        """Consume messages from RabbitMQ and process them with the provided callback."""
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
            channel.basic_consume(queue=self.queue_name, on_message_callback=callback, auto_ack=True)

            print("Waiting for messages. To exit, press CTRL+C")
            channel.start_consuming()
        except Exception as ex:
            print(traceback.format_exc())
            print(f"Error consuming data from RabbitMQ: {ex}")

    def process_message(self, ch, method, properties, body):
        """Process received RabbitMQ messages and store them in PostgreSQL."""
        try:
            data = json.loads(body)  # Convert JSON string to dict

            if not isinstance(data, dict):
                print(f"⚠ Warning: Expected dict, but got {type(data)}")
                return

            db = Postgresql()

            for table_name, records in data.items():
                if isinstance(records, list) and all(isinstance(record, dict) for record in records):
                    print(f"✅ Processing table: {table_name} with {len(records)} records")
                    db.create_table("", table_name, records)
                else:
                    print(f"⚠ Warning: Invalid data format for {table_name}")

        except Exception as e:
            print(f"❌ Error: {e}")
            print(traceback.format_exc())

if __name__ == "__main__":
    consumer = RabbitMQConsumer()
    consumer.consume_from_rabbitmq(consumer.process_message)
