import urdhva_base
from ingestion_api_enum import *
from ingestion_api_model import *
import fastapi
from fastapi import Request
from orchestrator.alerting.alert_manager import create_alert, close_alert
import uuid
import hpcl_ceg_model
import traceback
import pytz
from orchestrator.alerting.listener.tas_duplicate_alert_check import duplicate_loss_of_comm_check


router = fastapi.APIRouter(prefix='/tas')


ist = pytz.timezone('Asia/Kolkata')


# Action get_agent_service_status
@router.post('/get_agent_service_status', tags=['TAS'])
async def tas_get_agent_service_status( data: Tas_Get_Agent_Service_StatusParams):
        if data:
            sap_id = data.sap_id
            status = data.status
            message = data.message
            now = datetime.datetime.now(ist).isoformat()

        if status == "success":
            redis_client = await urdhva_base.redispool.get_redis_connection()
            await redis_client.hset("tas_agent_up_status", sap_id, now )# update the current date
            

        if status == "failed":
            query = f"""
                SELECT name FROM location_master
                WHERE bu = 'TAS' AND sap_id = '{sap_id}' AND location_onboard = true                  
            """
            location_name = await hpcl_ceg_model.LocationMaster.get_aggr_data(query)
            if location_name.get("data", []):
                location_name = location_name["data"][0].get("name")
            else:
                location_name = None    

            data1 = {
                "sap_id": sap_id,
                "status": status,
                "message": message,
                "location_name": location_name
            }

            await TasAgentServiceStatusCreate(**data1).create()

# Action get_agent_comm_status
@router.post('/get_agent_comm_status', tags=['TAS'])
async def tas_get_agent_comm_status( data: Tas_Get_Agent_Comm_StatusParams):
         
    if data:
        
        sap_id = data.sap_id
        status = data.status
        message = data.message
        opcda_status = data.opcda_status
        data_receiving_status = data.data_receiving_status
        configuration_healthy = data.configuration_healthy
        last_opc_failure = data.last_opc_failure
        last_rabbit_failure = data.last_rabbit_failure

        # get the location_name by using the location_master table use boolean column for sap_id location_onboard is true 
        # we need to fetch only that data
        
        query = f"""
                    SELECT name FROM location_master
                    WHERE bu = 'TAS' AND sap_id = '{sap_id}' AND location_onboard = true                  
                    """
        location_name = await hpcl_ceg_model.LocationMaster.get_aggr_data(query)
        if location_name.get("data", []):
            location_name = location_name["data"][0].get("name")
        else:
            location_name = None

        data1 = {
            "sap_id": sap_id,
            "status": status,
            "message": message,
            "opcda_status": opcda_status,
            "data_receiving_status": data_receiving_status,
            "configuration_healthy": configuration_healthy,
            "last_opc_failure": last_opc_failure,
            "last_rabbit_failure": last_rabbit_failure,
            "location_name": location_name
            }
        print("Data to be saved:", data1)

        await TasAgentCommStatusCreate(**data1).create()

        if status == "failed":
                
                processed_time = datetime.datetime.now(datetime.timezone.utc)
                alert_history = [{
                                "processed_time": processed_time.isoformat(),
                                "allocated_time": processed_time.isoformat(),
                                "action_msg": message,
                                "action_type": "InterlockCreated",
                            }]
                
                alert_data = {
                        "bu" : "TAS",
                        "sap_id": sap_id,
                        "sop_id": "SOP099",
                        "interlock_name" : "Loss Of Communication",
                        "device_name" : "Novex Communication Loss",
                        "alert_type": "TAS",
                        "device_type": message,
                        "severity": "critical",
                        "alert_id": str(uuid.uuid1()),
                        "alert_history": alert_history,
                                
                        }
                
                is_duplicate = await duplicate_loss_of_comm_check(alert_data)
                if is_duplicate:                     
                    success = await create_alert(alert_data)
                    if success:
                            print(f"Alert created successfully for device: {alert_data['device_name']}")
                    else:
                            print(f"Failed to create alert for device: {alert_data['device_name']}")

        if status == "success":
                #close alert
                query =f"device_name = 'Novex Communication Loss' and bu = 'TAS' and  sap_id = '{sap_id}' and alert_section = 'TAS' and alert_status != 'Close'"
                params = urdhva_base.queryparams.QueryParams(q=query, limit=0)
                resp = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
                if not resp.get("data"):
                    print("No alerts found to close.")
                    return
                else:
                    for alert in resp["data"]:
                        processed_time = datetime.datetime.now(datetime.timezone.utc)
                        alert_history = [{
                                    "processed_time": processed_time.isoformat(),
                                    "allocated_time": processed_time.isoformat(),
                                    "action_msg": message,
                                    "action_type": "InterlockCleared",
                                }]
                        alert_data = {
                                "bu": alert.get("bu"),
                                "sap_id": alert.get("sap_id"),
                                "sop_id": alert.get("sop_id"),
                                "alert_type": 'TAS',
                                "interlock_name": alert.get("interlock_name", ""),
                                "alert_id": alert.get("external_id", ""),
                                "device_name": alert.get("device_name", ""),
                                "alert_history": alert_history,
                            }
                        
                        try:
                            success = await close_alert(alert_data)
                            print(f"Closed alert with external_id: {alert_data["alert_id"]} | Success: {success}")
                        except Exception as e:
                            print(f"Error closing alert with external_id: {alert_data["alert_id"]} | Exception: {e}")
                            print(traceback.format_exc())
