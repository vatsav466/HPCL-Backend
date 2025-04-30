import urdhva_base
import requests
import asyncio
import traceback
import pandas as pd
import dashboard_studio_model
import api_manager.charts_actions

class Workflows_Deletion:

    async def delete_instance(self, camunda_url, business_key, instance_id, alert_id):
        """
        Deletes a specific process instance from the Camunda engine.

        Args:
            camunda_url (str): The base URL of the Camunda engine.
            instance_id (str): The ID of the process instance to be deleted.

        Raises:
            requests.exceptions.RequestException: If there is an error during the deletion request.
        """

        query_url = f"{camunda_url}/engine-rest/process-instance?businessKey={business_key}"
    
        try:
            response = requests.get(query_url)
            response.raise_for_status()
            instances = response.json()
            if not instances:
                return [f"No running instances found for instance_id: {instance_id}"]
            
            for instance in instances:
                process_instance_id = instance["id"]
                if process_instance_id != instance_id:
                    continue
                # Fetch variables for each instance
                variables_url = f"{camunda_url}/engine-rest/process-instance/{process_instance_id}/variables"
                var_response = requests.get(variables_url)
                var_response.raise_for_status()
                variables = var_response.json()
                # Extract 'priority' value
                alerting_id = variables.get("alert_id", {}).get("value", None)
                if int(alerting_id) == alert_id:
                    delete_url = f"{camunda_url}/engine-rest/process-instance/{process_instance_id}"
                    delete_response = requests.delete(delete_url)
                    delete_response.raise_for_status()
                    print(f"Deleted instance {instance_id} from {camunda_url}")

        except requests.exceptions.RequestException as e:
            print(f"Error deleting instance {instance_id}: {e}")
    
    async def get_camunda_urls(self,alert_section):
        """
        Retrieves a list of Camunda URLs based on the provided alert section.

        Args:
            alert_section (str): The alert section for which Camunda URLs are to be retrieved.

        Returns:
            list: A list of URLs corresponding to the specified alert section.
        """
        urls = []
        if alert_section in ["RO"]:
            camunda_config = urdhva_base.settings.camunda_url_config
            for key, services in camunda_config.items():
                url = f"http://{services['host']}:{services['port']}"
                urls.append(url)

        camunda_configuration = urdhva_base.settings.camunda_configuration
        for key, services in camunda_configuration.items():
            for service in services:
                if service["alert_section"] == alert_section:
                    urls.append(service["url"])
        return urls
    
    async def get_running_instances_in_urls(self,camunda_urls):
        """
        Fetches running instances from multiple Camunda URLs.

        Args:
            camunda_urls (list): A list of Camunda URLs to fetch running instances from.

        Returns:
            dict: A dictionary of business keys mapped to their respective instance IDs and URLs.
        """
        instance_map = {}
        for camunda_url in camunda_urls:
            url = f"{camunda_url}/engine-rest/process-instance"
            try:
                response = requests.get(url)
                response.raise_for_status()
                instances = response.json()

                # Overwrite previous businessKey entries with the latest from the last URL processed
                for instance in instances:
                    if "businessKey" in instance and instance["businessKey"]:
                        instance_id = instance["id"]
                        variables_url = f"{camunda_url}/engine-rest/process-instance/{instance_id}/variables"
                        variables_response = requests.get(variables_url)
                        variables_response.raise_for_status()
                        variables = variables_response.json()
                        alert_id = variables.get("alert_id", {}).get("value", None)

                        #print("variablees--->",variables)
                        instance_map[instance["businessKey"]] = {
                                "id": instance_id,
                                "url": camunda_url,
                                "alert_id": int(alert_id)  # Store variables
                        }

            except requests.exceptions.RequestException as e:
                print(f"Error fetching running instances: {e}")
        return instance_map

    async def delete_running_instances(self, present_alert_ids_in_db, alert_section):
        """
        Deletes running instances from Camunda that are not present in the database.

        Args:
            present_workflow_ids_in_db (list): A list of workflow IDs currently present in the database.
            alert_section (str): The alert section determining which set of Camunda URLs to query.

        This method retrieves running instances from Camunda URLs associated with the given alert section.
        It compares these instances against the provided list of workflow IDs from the database and deletes
        the instances in Camunda that do not exist in the database.
        """
        business_keys = []
        camunda_urls=[]
        present_keys=[]
        camunda_urls = await self.get_camunda_urls(alert_section)
        camunda_urls = list(set(camunda_urls))
        print("camuda_urls--->",camunda_urls)
        runnig_instances_in_urls = await self.get_running_instances_in_urls(camunda_urls)
        for key,details in runnig_instances_in_urls.items():
            if details["alert_id"] not in present_alert_ids_in_db:
                business_keys.append(details["alert_id"])
                if details["url"] in camunda_urls:
                    await self.delete_instance(details["url"],key,details["id"],details["alert_id"])
            else:
                present_keys.append(details["alert_id"])
        present_keys = ", ".join(f"'{id}'" for id in present_keys)
        test = pd.DataFrame({'ListValue': business_keys})
        test.to_csv("/opt/ceg/algo/ListValues.csv", index=False)
        if present_keys:
            query = (f"""select * from alerts """
                    f"where id in ({present_keys}) and "
                    f"alert_section = '{alert_section}'")
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
            function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
            resp = await function(query=query)
            resp = pd.DataFrame(resp)
            resp.to_csv("/opt/ceg/algo/running_instance.csv", index=False)
        
        query = (f"""select * from alerts """
                f"where id not in ({present_keys}) and "
                f"alert_section = '{alert_section}'")
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
        dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        resp = await function(query=query)
        resp = pd.DataFrame(resp)
        resp.to_csv("/opt/ceg/algo/no_running_instances_in_camunda.csv", index=False)


    async def process_workflow_resp(self, workflow_resp):
        """
        Processes a Pandas DataFrame containing workflow records from the database.

        Args:
            workflow_resp (pd.DataFrame): A Pandas DataFrame containing workflow records from the database.

        This method iterates over the rows in the DataFrame and for each row, it
        fetches the list of workflow IDs currently present in the database.
        It then deletes the running instances in Camunda that do not exist in the database.
        """
        for idx,record in workflow_resp.iterrows():
            if record["alert_section"] in ["TAS"]:
                # continue
                query = (f"select * from alerts where alert_section='{record['alert_section']}' and alert_status!='Close'")
                dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
                dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
                function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
                data_resp = pd.DataFrame(resp)
                present_alert_ids_in_db = data_resp["id"].tolist()
                await self.delete_running_instances(present_alert_ids_in_db, record["alert_section"])

    async def instance_removal(self):
        """
        Removes workflow instances that are not present in the database.

        This method fetches distinct alert sections from the alerts table where the alert status is not 'Close'.
        It then processes each workflow response to identify and remove running instances in Camunda that do not
        exist in the database. If no records are found in the alerts table, a message is printed indicating so.

        Exceptions are caught and printed, including tracebacks for debugging purposes.
        """

        try:
            query = "SELECT DISTINCT(alert_section) FROM alerts"
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
            function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
            resp = await function(query=query)

            workflow_resp = pd.DataFrame(resp)

            if not workflow_resp.empty:
                await self.process_workflow_resp(workflow_resp)
            else:
                print("No records found in alerts.")

        except Exception as e:
            print("Exception Occurred While Removing Instances")
            print(e)
            print("Traceback:", traceback.format_exc())

if __name__ == "__main__":
    Workflow = Workflows_Deletion()
    asyncio.run(Workflow.instance_removal())

