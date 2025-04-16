import urdhva_base
import traceback
import aio_pika
import json
import asyncio


async def send_command_rabbitmq(self, message, queue_name):
        """
        Sends a command to RabbitMQ.
        This function connects to RabbitMQ, declares a queue, and sends a message to that queue.

        Args:
            message (dict): The message to be sent.
            queue_name (str): The name of the queue to send the message to (should be unique)

        Returns:
            tuple: A tuple containing a boolean indicating success and a message string.
        """
        try:
            connection = await aio_pika.connect_robust(
                host = urdhva_base.settings.rabbitmq_host,
                port = urdhva_base.settings.rabbitmq_port,
                virtualhost = urdhva_base.settings.rabbitmq_vhost,
                login = urdhva_base.settings.rabbitmq_username,
                password = urdhva_base.settings.rabbitmq_password
            )
            async with connection:
                channel = await connection.channel()
                # Generate the queue name using sap_id
                queue_name = queue_name
                print(f"queue name sending to rabbitmq : {queue_name}")
                # Declare the queue
                await channel.declare_queue(queue_name, durable=True)
                # Create and send the message only once
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(message).encode(),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                    ),
                    routing_key=queue_name
                )
                return True, "Command sent to location"
        except Exception as e:
             print(f"Error in send command to rabbitmq: {e}")
             print(traceback.format_exc())