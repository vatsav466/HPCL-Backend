import urdhva_base
import time
import datetime
import traceback
import hpcl_ceg_model
import utilities.helpers as helpers

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")

class AlertEscalationCheck:
    async def get_required_variables(self):
        return ["BU", "sap_id", "sop_id", "device_id", 
                "device_type", "device_name", "alert_id", 
                "interlock_name"]

    async def alert_escalation_check(self, params):
        try:
            interlock_name = params.get('interlock_name', '')
            device_name = params.get('device_name', '')
            current_alert_id = params.get('alert_id', '')
            
            # Clean interlock name for query
            if interlock_name.endswith('_M'):
                interlock_name_for_query = interlock_name[:-2]  # remove last 2 characters
            else:
                interlock_name_for_query = interlock_name
            
            # Check if this is a non-maintenance alert
            if not interlock_name.endswith("Maintenance"):
                print(f"This is a non-maintenance alert for device: {device_name}")
                logger.debug(f"Processing non-maintenance alert for device: {device_name}")
                current_time_str = current_datetime.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                time_24h_after = current_datetime - datetime.timedelta(hours=24)
                time_24h_after_str = time_24h_after.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

                #   Query for maintenance alerts for the same device in the 24h after the current alert
                maintenance_query = (
                    f"""bu = 'TAS' and """
                    f"""alert_section = 'TAS' and """
                    f"""regexp_replace(tas_device_name, '_M$', '') = '{interlock_name_for_query}' and """
                    f"""interlock_name LIKE '%Maintenance%' and """
                    f"""created_at >= '{current_time_str}' and """
                    f"""created_at <= '{time_24h_after_str}' and """
                    f"""alert_id != '{current_alert_id}'"""  # Exclude current alert
                )
                
                print(f"Post-alert maintenance check query: {maintenance_query}")
                logger.debug(f"Post-alert maintenance check query: {maintenance_query}")
                
                maintenance_params = urdhva_base.queryparams.QueryParams(q=maintenance_query)
                maintenance_resp = await hpcl_ceg_model.Alerts.get_all(maintenance_params, resp_type='plain')
                
                if maintenance_resp["data"]:
                    # Found maintenance alerts within 24h after this non-maintenance alert
                    print(f"Found maintenance alerts within 24h after this alert - Escalation is cancelled")
                    logger.info(f"Found maintenance alerts within 24h after this alert - Escalation is cancelled")
                    return None
                
                print(f"No maintenance alerts found within 24h after this alert - Proceeding with escalation")
                logger.info(f"No maintenance alerts found within 24h after this alert - Proceeding with escalation")
            
            # If we got here, no reason to skip the escalation
            logger.info(f"No blocking conditions found - alert will be escalated")
            return True, {"Status": "Escalating to LEVEL-1"}
            
        except Exception as e:
            logger.error(f"Error in alert escalation check: {e}")
            logger.error(traceback.format_exc())
            # In case of error, let the escalation through by default
            return True, {"Status": "Escalating to LEVEL-1"}