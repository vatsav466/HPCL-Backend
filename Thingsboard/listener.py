import os
import json
import aio_pika
import aiohttp
import asyncio
import urdhva_base
import aiofiles

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
    async def load_site_data(site_id):
        """Load site data from a local JSON file."""
        filename = f"/Users/manohar/Documents/GitHub/dnc_backend_v2/things_board/device_data/{site_id}.json"
        if not os.path.exists(filename):
            print(f"Site data file not found: {filename}")
            return None
        try:
            async with aiofiles.open(filename, "r") as file:
                return json.loads(await file.read())
        except Exception as e:
            print(f"Error reading site data file {filename}: {str(e)}")
            return None

    @staticmethod
    async def post_telemetry(device_key, sensor_type, value):
        """Post telemetry data to the ThingsBoard API."""
        headers = {"Content-Type": "application/json"}
        payload = {sensor_type: value}
        telemetry_url = f"{BASE_URL}/api/v1/{device_key}/telemetry"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(telemetry_url, json=payload, headers=headers, ssl=False) as response:
                    if response.status == 200:
                        print(f"Successfully posted telemetry for deviceKey: {device_key}")
                        return True
                    else:
                        print(f"Failed to post telemetry for deviceKey: {device_key}. Status code: {response.status}")
                        return False
        except Exception as e:
            print(f"Error posting telemetry for deviceKey: {device_key}. Error: {str(e)}")
            return False

    @staticmethod
    async def process_tags_data(location_id, tags_data, site_id):
        """Process all tags and post telemetry for all devices."""
        if location_id != site_id:
            print(f"Location ID {location_id} does not match SITE_ID {site_id}. Ignoring message.")
            return False

        site_data = await TelemetryService.load_site_data(site_id)
        if not site_data:
            print(f"No site data found for SITE_ID {site_id}")
            return False

        tasks = []
        for component in site_data['data']:
            device_key = component['device_key']
            for sensor in component['sensors']:
                tag_path = sensor['sensor_tag']
                if tag_path in tags_data:
                    value = tags_data[tag_path]
                    tasks.append(TelemetryService.post_telemetry(device_key, sensor['sensor_name'], value))
                else:
                    print(f"No value found for TagPath: {tag_path} in message.")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return all(result is True for result in results)

async def rabbitmq_listener(sap_id):
    """Handles RabbitMQ connection and message listening asynchronously."""
    queue_name = f"{RABBITMQ_PREFIX_QUEUE}{sap_id}"
    try:
        connection = await aio_pika.connect_robust(
            host=RABBITMQ_HOST, virtualhost=RABBITMQ_VHOST,
            login=RABBITMQ_USER, password=RABBITMQ_PASSWORD
        )
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(queue_name, durable=True)
            print(f"Listening for messages from queue: {queue_name}")
            async for message in queue:
                async with message.process():
                    try:
                        body = json.loads(message.body)
                        print(f"Received message on {queue_name}: {body}")
                        location_id = body.get("location_id")
                        SITE_ID = location_id
                        tags_data = body.get("tags_data", {})
                        success = await TelemetryService.process_tags_data(location_id, tags_data, SITE_ID)
                        if success:
                            print(f"All tags processed successfully for {queue_name}.")
                        else:
                            print(f"Some tags failed to process for {queue_name}.")
                    except Exception as e:
                        print(f"Error processing message on {queue_name}: {str(e)}")
    except Exception as e:
        print(f"Unexpected error in listener for {queue_name}: {e}")

async def main():
    sap_ids = ["1999", "1128", "1919"]  # Add all the SAP IDs you want to listen for
    tasks = [rabbitmq_listener(sap_id) for sap_id in sap_ids]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
