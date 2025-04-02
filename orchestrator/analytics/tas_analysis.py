import urdhva_base
import requests
import asyncio
import traceback
import pandas as pd
import charts_actions
import hpcl_ceg_model
import dashboard_studio_model
import utilities.helpers as helpers

class Tas_Analysis:

    async def delete_instances_by_business_keys(self,camunda_url,business_keys):
        results = {}
        for business_key in business_keys:
            try:
                # Fetch process instances by business key
                search_url = f"{camunda_url}/engine-rest/process-instance"
                #print(search_url)
                params = {"businessKey": business_key}
                response = requests.get(search_url, params=params)
                response.raise_for_status()

                instances = response.json()
                #print("instances-->",instances)
                if not instances:
                    results[business_key] = "No instances found"
                    continue

                # Delete each instance
                for instance in instances:
                    instance_id = instance["id"]
                    delete_url = f"{camunda_url}/engine-rest/process-instance/{instance_id}"
                    delete_response = requests.delete(delete_url)
                    delete_response.raise_for_status()

                results[business_key] = "Deleted successfully"
            except Exception as e:
                results[business_key] = f"Error: {str(e)}"
        
        return results

    async def delete_running_instances(self,bu,sap_id,business_keys):
        camunda_url = await helpers.get_camunda_url(bu=bu, sap_id=sap_id,alert_section="TAS")
        await self.delete_instances_by_business_keys(camunda_url,business_keys)

    async def process_tas_resp(self,tas_resp):
        for idx,record in tas_resp.iterrows():
            query = (f"sap_id='{record['sap_id']}' and bu='{record['bu']}' "
                     f"and external_id='{record['external_id']}' "
                     f"and device_name='{record['device_name']}'")
            tas_data = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query),
                                                           resp_type='plain')
            #print("query-->",query)
            deleting_ids=[]
            closed_ids=[]
            count=0
            tas_data = list(reversed(tas_data['data']))
            for rec in tas_data:
                #print("rec--->",rec)
                if not closed_ids and count == len(tas_data) - 1:
                    if rec["alert_status"]=="Close":
                        closed_ids.append(rec["unique_id"])
                    continue
                elif rec["alert_status"]=="Close":
                    closed_ids.append(rec["unique_id"])
                elif rec["alert_status"]=="Open":
                    deleting_ids.append(rec["unique_id"])
                count+=1
            #print("deleting_ids--->",deleting_ids)
            #print("closed_ids--->",closed_ids)
            deleting_idss = ", ".join(f"'{id}'" for id in deleting_ids)
            if deleting_idss:
                query = (f"""delete from alerts """
                        f"where unique_id in ({deleting_idss}) and "
                        f"alert_section = 'TAS'")
                #print("Query: ", query)
                dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
                dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
                function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
                resp = await function(query=query)
                await self.delete_running_instances(record["bu"],record["sap_id"],deleting_ids)

    async def duplicates_removal(self):
        try:
            query = (f"""select bu,sap_id,external_id,device_name,COUNT(*) AS duplicate_count from alerts """
                    f"where bu = 'TAS' and "
                    f"alert_section = 'TAS' "
                    f"GROUP BY bu,sap_id,external_id,device_name "
                    f"HAVING COUNT(*)>1")
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
            function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
            #print("Query: ", query)
            resp = await function(query=query)
            tas_resp = pd.DataFrame(resp)
            #print("tas_resp--->",tas_resp)
            await self.process_tas_resp(tas_resp)
        except Exception as e:
            print("Exception Occured While Removing Alerts")
            print(e)
            print("Traceback %s" % traceback.format_exc())

if __name__ == "__main__":
    tas = Tas_Analysis()
    asyncio.run(tas.duplicates_removal())