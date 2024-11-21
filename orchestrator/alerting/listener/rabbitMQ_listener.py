import urdhva_base
import json
import asyncio
import aio_pika
import tas_listener

async def on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """
    Callback for processing received messages.
    """
    async with message.process(ignore_processed=True):
        try:
            # Process the message
            payload = json.loads(message.body.decode())
            await tas_listener.tas_listener(payload)
            print(f"Received message: {payload}")
        except Exception as e:
            print(traceback.format_exc())
            print(f"Error processing message: {e}")
        # Manual acknowledgment is not needed if auto_ack=True.

async def consume_message():
    """
    Asynchronous consumer to read messages from RabbitMQ queue.
    """
    try:
        # Connect to RabbitMQ server
        connection = await aio_pika.connect_robust(
            host=urdhva_base.settings.rabbitmq_host["host"],
            port=urdhva_base.settings.rabbitmq_port["port"],
            login=urdhva_base.settings.rabbitmq_username["username"],
            password=urdhva_base.settings.rabbitmq_password["password"],
            virtualhost=urdhva_base.settings.rabbitmq_vhost["vhost"],
        )

        async with connection:
            # Create a channel
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=1)

            # Declare the queue (idempotent)
            queue = await channel.declare_queue(
                name=urdhva_base.settings.rabbitmq_queue["queue"],
                durable=True,
            )

            # Start consuming messages
            print(f"Waiting for messages in queue: '{urdhva_base.settings.rabbitmq_queue['queue']}'")
            await queue.consume(on_message, no_ack=urdhva_base.settings.rabbitmq_auto_ack["auto_ack"])

            # Keep the consumer running
            await asyncio.Future()  # Runs indefinitely until interrupted

    except aio_pika.exceptions.AMQPConnectionError as e:
        print(f"Connection error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(consume_message())
