import urdhva_base
import traceback
import hpcl_ceg_model
import requests
import orchestrator.alerting.alert_manager as alert_manager
from datetime import datetime, timedelta

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


def get_last_ongoing_trip(alert_history):
    """
    Returns the latest OngoingTrip entry from alert_history
    """
    for record in reversed(alert_history or []):
        if record.get("action_type") == "OngoingTrip":
            return record
    return None


class CheckCompletedTrip:
    async def get_required_variables(self):
        return ["alert_id"]

    async def check_completed_trip(self, params):
        try:
            # Fetch alert
            alert_data = await hpcl_ceg_model.Alerts.get(params.get("alert_id"))
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            truck_number = alert_data.get("vehicle_number", "")
            alert_history = alert_data.get("alert_history", [])

            response = requests.post(
                urdhva_base.settings.vts_truck_status_url,
                json={"VehicleRtoNo": truck_number},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            response_data = response.json()

            logger.info(f"VTS truck status response: {response_data}")

            # Only when trip is still loaded
            if response_data.get("action_typeTripStatus", "").lower() == "loaded":
                now_utc = urdhva_base.utilities.get_present_time(utc=True)
                last_ongoing = get_last_ongoing_trip(alert_history)
                if last_ongoing and last_ongoing.get("processed_time"):
                    pt = last_ongoing["processed_time"]
                    last_time = (
                        pt if isinstance(pt, datetime)
                        else datetime.fromisoformat(pt)
                    )
                    # Skip update if checked within last 1 hour
                    if now_utc - last_time < timedelta(hours=1):
                        return True, {"tripCompleted": False}

                # Update alert history
                alert_data["process_time"] = now_utc
                alert_data["action_msg"] = (
                    f"Trip still ongoing to block the truck. Last checked at {now_utc.isoformat()} UTC"
                )
                alert_data["action_type"] = "OngoingTrip"

                await alert_manager.AlertAction().update_alert_history(input_data=alert_data, alert_data=alert_data)
                return True, {"tripCompleted": False}
            
            # Trip not loaded → completed
            return True, {"tripCompleted": True}

        except Exception as e:
            logger.error(f"Error while checking completed trip: {e}")
            logger.error(traceback.format_exc())
            return False, {"tripCompleted": False}
