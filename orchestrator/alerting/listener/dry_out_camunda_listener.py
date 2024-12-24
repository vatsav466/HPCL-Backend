import urdhva_base
import sys
import json
import asyncio
import urdhva_base.redispool


class DryOutCamundaListener:
    def __init__(self, connector_name, queue_name):
        self.connector_name = connector_name
        self.queue_name = queue_name

    async def listener(self):
        queue_ins = urdhva_base.redispool.RedisQueue(self.queue_name)
        while True:
            task = await queue_ins.get(timeout=60)
            if task:
                await self.process_task(json.loads(task))

    async def process_task(self, task):
        location_id = task['sap_id']
        product_id = task['product_id']
        print(f"Location: {location_id} Product: {product_id}")
        # Todo:-
        # Get All non cancelled indents from IMS
        indents = []
        for indent in indents:
            if indent["status"] == "CANCELLED":
                continue
            # Check alert created or not for loction/product/indent
            # If not created create alert


def usage():
    print(f"Usage:- python {sys.argv[0]} <connector_name> <queue_name>{sys.argv[0]}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Invalid arguments")
        usage()
        sys.exit(-1)
    asyncio.run(DryOutCamundaListener(sys.argv[1], "dry_out_camunda_queue").listener())
