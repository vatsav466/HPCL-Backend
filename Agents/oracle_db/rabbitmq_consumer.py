import urdhva_base
import json
import pika
import traceback
from orchestrator.connection_vault.databases.postgresql import Postgresql

class RabbitMQConsumer:
    def __init__(self, config_path="config.json"):
        """
        Load RabbitMQ configuration from JSON file for the consumer.
        """
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)

        self.rabbitmq_host = config.get('conn_host', '')
        self.rabbitmq_port = int(config.get('conn_port', 5672))  # Default RabbitMQ port
        self.rabbitmq_user = config.get('conn_user', '')
        self.rabbitmq_password = config.get('conn_secret', '')
        self.queue_name = config.get('conn_channel', '')

    def consume_from_rabbitmq(self, callback):
        """
        Consume messages from RabbitMQ and process them with the provided callback.
        """
        try:
            credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_password)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.rabbitmq_host, port=self.rabbitmq_port, credentials=credentials)
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
        """
        Callback function to process RabbitMQ messages.
        """
        try:
            data = json.loads(body)
            changed_data = data.get("changed_data", [])

            if not changed_data:
                print("No data to process.")
                return
            else:
                Postgresql().create_table()
            
            print(f"Received data: {changed_data}")

            # Here, you can add database insertion logic.

        except Exception as e:
            print(traceback.format_exc())

# Example Usage
if __name__ == "__main__":
    consumer = RabbitMQConsumer()
    consumer.consume_from_rabbitmq(consumer.process_message)
