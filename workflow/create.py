import camunda_manager
import random
import asyncio  # Import asyncio for running the async main function

async def create():
    tagmap = {
        'send_notification': 'SAMPLE1',
        'send_notification2': 'SAMPLE2',
        'send_notification3': 'SAMPLE3'
    }
    random_key = random.choice(list(tagmap.keys()))  # Select a random key
    data = {"variables": {"executing": {"value": random_key, "type": "String"}}}
    await camunda_manager.Camunda().start_workflow(data, tagmap[random_key])

async def main():
    await create()

if __name__ == "__main__":
    asyncio.run(main())  # Use asyncio.run to execute the async main function
