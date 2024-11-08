import json
import requests
import traceback
import urdhva_base


logger = urdhva_base.logger.Logger.getInstance("workflow_process-log")


class Camunda:
    def __init__(self):
        self.camunda_url = urdhva_base.settings.camunda_url
        self.headers = {"Content-Type": "application/json"}

    async def start_workflow(self, payload, key):
        """
        Initiates a workflow using the specified payload and process key.

        :param payload: Dictionary containing the data to be sent to the workflow engine.
        :param key: String representing the process definition key to start.
        :return: JSON response from the workflow engine.
        If the request is successful (status code 200), the response is returned as JSON.
        If there is an exception during the request (e.g., network error, timeout, etc.),
        an error message is printed and None is returned
        """
        url = f" {self.camunda_url}/engine-rest/process-definition/key/{key}/start"

        try:
            response = requests.post(url, data=json.dumps(payload), headers=self.headers)
            response.raise_for_status()
            print(response.json())
            logger.info(response.json())
        except requests.exceptions.RequestException as e:
            print(f"Error starting workflow: {e}")
            logger.error(f"Error starting workflow: {e}")
            print(traceback.format_exc())
            