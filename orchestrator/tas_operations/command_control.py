import urdhva_base
import aio_pika
import json


async def publish_command(sap_id, command, value):
    connection = await aio_pika.connect_robust(
        host=urdhva_base.settings.rabbitmq_host,
        port=urdhva_base.settings.rabbitmq_port,
        virtualhost=urdhva_base.settings.rabbitmq_vhost,
        login=urdhva_base.settings.rabbitmq_username,
        password=urdhva_base.settings.rabbitmq_password
    )
    message = {
        "command": "write",
        "sensor_tag": command,
        "value": f"{value}"
    }
    async with connection:
        channel = await connection.channel()

        # Generate the queue name using sap_id
        queue_name = f'command_write_{sap_id}'
        print(f"Queue name generated: {queue_name}")

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
