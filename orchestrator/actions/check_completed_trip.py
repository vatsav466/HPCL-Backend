import urdhva_base
import traceback
import hpcl_ceg_model
import requests
import json

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")

class CheckCompletedTrip:
    async def get_required_variables(self):        
        return ["alert_id"]
    
    async def check_completed_trip(self, params):
        try:
            alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))
            if not isinstance(alert_data, dict):
               alert_data = alert_data.__dict__
            
            truck_number = alert_data.get('vehicle_number','')
              
            if alert_data["interlock_name"] == 'Itdg Admin Blocked':
                print("checking itdg interlock")
                query = f"blocking_status='blocked' and truck_number='{truck_number}'"
                print(query)
                manual_blocked = await hpcl_ceg_model.VtsManualBlocked.get_all(
                    urdhva_base.queryparams.QueryParams(q=query),resp_type='plain'
                )
                print(len(manual_blocked['data']))
                if len(manual_blocked['data']) > 0:
                
                    return True, {"tripCompleted": True}
                
            headers = {
                "Content-Type": "application/json"
            }
            payload = {
                "VehicleRtoNo": truck_number
            }

            response = requests.post(
                urdhva_base.settings.vts_truck_status_url,
                json=payload,
                headers=headers,
                timeout=30
            )

            response.raise_for_status() 
            response_data = response.json()

            logger.info(f"VTS truck status response: {response_data}")

            # If response is valid and status is loaded → NOT completed
            if isinstance(response_data, dict) and response_data.get("TripStatus", "").lower() == "loaded":
                return True, {"tripCompleted": False}
            
            return True, {"tripCompleted": True}

        except Exception as e:
            logger.error(f"Error while checking completed trip: {e}")
            logger.error(traceback.format_exc())
            return False, {"tripCompleted": False}
