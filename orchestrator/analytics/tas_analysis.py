import urdhva_base
import asyncio
import traceback
import pandas as pd
import charts_actions
import hpcl_ceg_model
import dashboard_studio_model

class Tas_Analysis:

    async def process_tas_resp(self,tas_resp):
        for idx,record in tas_resp.iterrows():
            query = (f"sap_id='{record['sap_id']}' and bu='{record['bu']}' "
                     f"and external_id='{record['external_id']}' "
                     f"and device_name='{record['device_name']}'")
            tas_data = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query),
                                                           resp_type='plain')
            print("tas_data--->",tas_data["data"])
            deleting_ids=[]
            closed_ids=[]
            count=0
            tas_data = list(reversed(tas_data['data']))
            for rec in range(len(tas_data)):
                if not closed_ids and count==(len(tas_data)-1):
                    continue
                elif rec["alert_status"]=="Close":
                    closed_ids.append(rec["unique_id"])
                elif rec["alert_status"]=="Open":
                    deleting_ids.append(rec["unique_id"])
                count+=1
            print(len(deleting_ids))
            deleting_ids = ", ".join(f"'{id}'" for id in deleting_ids)
            query = (f"""delete from alerts """
                     f"where id in ({deleting_ids}) "
                     f"alert_section = 'TAS'")
            print("Query: ", query)
            '''dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
            function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
            print("Query: ", query)
            #resp = await function(query=query)'''

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
            print("Query: ", query)
            resp = await function(query=query)
            tas_resp = pd.DataFrame(resp)
            print("tas_resp--->",tas_resp)
            await self.process_tas_resp(tas_resp)
        except Exception as e:
            print("Exception Occured While Removing Alerts")
            print(e)
            print("Traceback %s" % traceback.format_exc())

if __name__ == "__main__":
    tas = Tas_Analysis()
    asyncio.run(tas.duplicates_removal())