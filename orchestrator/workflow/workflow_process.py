import urdhva_base
import json
import requests
import traceback
import hpcl_ceg_model


logger = urdhva_base.logger.Logger.getInstance("workflow_process_log")


class Camunda:
    def __init__(self):
        self.camunda_url = urdhva_base.settings.camunda_url
        self.headers = {"Content-Type": "application/json"}

    async def start_workflow(self, payload, workflowId):
        """
        Initiates a workflow using the specified payload and process key.

        :param payload: Dictionary containing the data to be sent to the workflow engine.
        :param key: String representing the process definition key to start.
        :return: JSON response from the workflow engine.
        If the request is successful (status code 200), the response is returned as JSON.
        If there is an exception during the request (e.g., network error, timeout, etc.),
        an error message is printed and None is returned
        """
        url = f" {self.camunda_url}/engine-rest/process-definition/key/{workflowId}/start"

        try:
            response = requests.post(url, data=json.dumps(payload), headers=self.headers)
            response.raise_for_status()
            print(response.json())
            logger.info(response.json())
            await self.update_alerts_with_instance_id(payload['variables']['alert_id']['value'], response.json().get("id"))
        except requests.exceptions.RequestException as e:
            print(f"Error starting workflow: {e}")
            logger.error(f"Error starting workflow: {e}")
            print(traceback.format_exc())
    

    async def closeWorkflow(self, workflowId, clustercamunda):
        url = config.rocamundaurl + '/engine-rest/message'
        if clustercamunda:
            url = config.clustercamundaurl + "/engine-rest/message"
        header = {"Content-Type": "application/json", "Accept": "application/json"}
        data = {"messageName": "interLockOk",
                "businessKey": workflowId,
                "variables": {"alertid": {"value": workflowId, "type": "String"},
                            "closed": {"value": True, "type": "Boolean"}}}

        response = requests.request(method="POST", url=url,
                                    data=json.dumps(data), headers=header, verify=False)
        if response.status_code != 200:
            print("Camunda URL:%s" % url)
            print("Camunda DATA:%s" % data)
            print("Camunda close response code: %s text:%s" % (response.status_code, response.text))
        else:
            print("InterLock Ok Successfully Sent to : " + str(workflowId))

    async def update_alerts_with_instance_id(self, alert_id, instance_id):
        alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        alert_data['workflow_instance_id'] = instance_id
        await hpcl_ceg_model.Alerts(**alert_data).modify()
