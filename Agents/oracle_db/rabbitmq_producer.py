import json
import pika
import traceback
import pandas as pd

class RabbitMQProducer:
    def __init__(self, config_path="config.json"):
        """
        Load RabbitMQ configuration from JSON file for the producer.
        """
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)

        self.rabbitmq_host = config.get('conn_host', '')
        self.rabbitmq_port = int(config.get('conn_port', 5672))  # Default RabbitMQ port
        self.rabbitmq_user = config.get('conn_user', '')
        self.rabbitmq_password = config.get('conn_secret', '')
        self.queue_name = config.get('conn_channel', '')
        self.virtualhost = config.get('conn_vhost', 'hpcl_ceg')

    def send_to_rabbitmq(self, data):
        """
        Send a list of dictionaries to RabbitMQ queue.
        """
        print("Into send_to_rabbitmq", data)
        try:
            print("Into try block")
            credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_password)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.rabbitmq_host,
                    port=self.rabbitmq_port,
                    virtual_host=self.virtualhost,
                    credentials=credentials
                )
            )
            print("After connection")
            channel = connection.channel()
            channel.queue_declare(queue=self.queue_name, durable=True)

            # Convert list of dictionaries to JSON
            message = json.dumps(data, default=str)  # Convert datetime objects to string

            channel.basic_publish(exchange='', routing_key=self.queue_name, body=message)
            connection.close()
            print("Message sent to RabbitMQ successfully.")
        except Exception as ex:
            print(traceback.format_exc())
            print(f"Error sending data to RabbitMQ: {ex}")
