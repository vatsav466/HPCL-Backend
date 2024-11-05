from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
import importlib
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import sys
import config

async def algo_external_task(task: ExternalTask) -> TaskResult:
    variables = task.get_variables()
    module_name = variables.pop('module_name', None)
    class_name = variables.pop('class_name', None)
    function_name = variables.pop('function_name', None)
    try:
        module = importlib.import_module(module_name)
        class_instance = getattr(module, class_name)()
        function = getattr(class_instance, function_name)
        status, data = await function(**variables)
        if status:
            if data:
                return task.complete(data)
            else:
                return task.complete()
        if not status:
            return task.failure(error_message="task failed", error_details="failed task details", max_retries=3, retry_timeout=5000)
    except Exception as e:
        return task.failure(error_message=str(e), error_details=str(e))

# Wrapper function to run async functions synchronously
def run_async_function(async_func, task):
    return asyncio.run(async_func(task))


async def main():
    ENGINE_LOCAL_BASE_URL = config.camundaurl + "/engine-rest"
    # etw = ExternalTaskWorker(10, base_url=ENGINE_LOCAL_BASE_URL, config=default_config)
    topics = ['WorkFlow_Consumer']
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=40)  # Adjust the number of workers as needed
    tasks = []
    count = 0
    for topic in topics:
        etw = ExternalTaskWorker(count, base_url=ENGINE_LOCAL_BASE_URL, config= config.default_config)
        count += 1
        tasks.append(loop.run_in_executor(executor, lambda: etw.subscribe(topic, lambda task: run_async_function(algo_external_task, task))))
    await asyncio.gather(*tasks)

# Run the asyncio event loop
if __name__ == "__main__":
    asyncio.run(main())
