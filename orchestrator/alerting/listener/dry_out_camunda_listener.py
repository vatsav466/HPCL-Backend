import urdhva_base
import sys
import json
import asyncio
import traceback
import urdhva_base.redispool
from orchestrator.actions.indentwise_dry_out import IndentDryOut

logger = urdhva_base.Logger.getInstance("dry_out_camunda_listener.log")


class DryOutCamundaListener:
    def __init__(self, connector_name, queue_name):
        self.connector_name = connector_name
        self.queue_name = queue_name

    async def listener(self):
        queue_ins = urdhva_base.redispool.RedisQueue(self.queue_name)
        while True:
            try:
                task = await queue_ins.get(timeout=60)
                if task:
                    await self.process_task(json.loads(task))
            except Exception as e:
                if 'Timeout reading' not in str(e):
                    print(f"Exception in dry-out task process {e}, {traceback.format_exc()}")
                    logger.error(f"Exception in dry-out task process {e}, {traceback.format_exc()}")

    async def process_task(self, task):
        location_id = task['sap_id']
        product_id = task['product_code']
        print(f"Location: {location_id} Product: {product_id}")
        # Todo:-
        # Get All non cancelled indents from IMS
        await IndentDryOut().check_raised_indent(task)



def usage():
    print(f"Usage:- python {sys.argv[0]} <connector_name> <queue_name>{sys.argv[0]}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Invalid arguments")
        usage()
        sys.exit(-1)
    asyncio.run(DryOutCamundaListener(sys.argv[1], "dry_out_camunda_queue").listener())
