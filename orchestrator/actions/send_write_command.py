import urdhva_base
import traceback
import hpcl_ceg_model
import sys
sys.path.append("/opt/ceg/algo/orchestrator")
import tas_operations.send_rabbitmq as send_rabbitmq
import tas_operations.find_matching_csv as find_matching_csv

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class SendWriteCommand:
    async def get_required_variables(self):
        return ["alert_id" , "interrupt"]
    
    async def handle_write_command(self, params):
        """
        Handles the write command for the TAS system based on the alert data and interrupt type.

        Args:
              params (dict): A dictionary containing 'alert_id' and 'interrupt'
        """
        csv_file_path = "/opt/ceg/algo/orchestrator/tas_operations/write_tag.csv"
        # try:
        #     alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))
        #     if not isinstance(alert_data, dict):
        #         alert_data = alert_data.__dict__
        #     # Extracting required parameters from alert data
        #     interlock_name = alert_data.get('interlock_name')
        #     equipment_name = alert_data.get('tas_device_name') or alert_data.get('device_name') # Prioritize tas_device_name
        #     sap_id = alert_data.get('sap_id')
        #     if not (interlock_name and equipment_name and sap_id):
        #         print("missing required fields")
        #         return 
        #      # Define the matching criteria
        #     match_criteria = {
        #         "equipment_name": equipment_name,
        #         "sap_id": sap_id
        #     }
        #     # Read the CSV file and find the matching row
        #     matched_row = await find_matching_csv.find_matching_row(csv_file_path, match_criteria)

        #     if not matched_row:
        #         print(f"No matching row found for sap_id :{sap_id} and equipment name : {equipment_name}")
        #         return
            
        #     # Extracting the tag and write control from the matched row
        #     tag = matched_row['tag']
        #     interrupt = params.get('interrupt')
        #     if interrupt == "shutdown":
        #         write_control = matched_row['set']
        #     elif interrupt == "open":
        #         write_control = matched_row['clear']
        #     else:
        #         print(f"Invalid interrupt name: {interrupt}")
        #         return
        #     # Constructing the message body to post rabbit mq

        #     message = {
        #         "command": "write",
        #         "sensor_tag": tag,
        #         "value" : str(write_control)
        #     }

        #     # handle this message playload to publish to rabbit mq
        #     status, message = await send_rabbitmq.send_command_rabbitmq(message, queue_name=f'command_write_{sap_id}')
        #     if status:
        #         return True, message
        #     else:
        #         return False
        
        # except Exception as e:
        #     print(f"Error in handle write command: {e}")
        #     print(traceback.format_exc())
        try:
            alert_id = params.get('alert_id')
            alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
            print("send write command alert_data --> ", alert_data)
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            # Extract relevant fields
            interlock_name = alert_data.get('interlock_name')
            equipment_name = alert_data.get('tas_device_name') or alert_data.get('device_name')
            sap_id = alert_data.get('sap_id')

            # Check required fields
            if not (interlock_name and equipment_name and sap_id):
                print("Missing required fields")
                return

            # If current alert is not already 'BCU Permissive Off_Fail'
            # Check if there's an open alert with 'BCU Permissive Off_Fail' for same sap_id
            if interlock_name == "BCU Permissive Off_Fail":
                open_alert = await hpcl_ceg_model.Alerts.get(alert_id)
                print("open_alert ---> ", open_alert)
                if open_alert:
                    # Update current alert interlock_name
                    await hpcl_ceg_model.Alerts(**{"id": alert_id, "interlock_name": "BCU Permissive Off_Fail_DNC"}).modify()
                    interlock_name = "BCU Permissive Off_Fail_DNC"

            # Define the matching criteria
            match_criteria = {
                "equipment_name": equipment_name,
                "sap_id": sap_id
            }

            # Read the CSV file and find the matching row
            matched_row = await find_matching_csv.find_matching_row(csv_file_path, match_criteria)

            if not matched_row:
                print(f"No matching row found for sap_id: {sap_id} and equipment name: {equipment_name}")
                return

            # Extracting the tag and write control from the matched row
            tag = matched_row['tag']
            interrupt = params.get('interrupt')

            if interrupt == "shutdown":
                write_control = matched_row['set']
            elif interrupt == "open":
                write_control = matched_row['clear']
            else:
                print(f"Invalid interrupt name: {interrupt}")
                return

            # Constructing the message body to post to RabbitMQ
            message = {
                "command": "write",
                "sensor_tag": tag,
                "value": str(write_control)
            }

            # Send message to RabbitMQ
            status, response_message = await send_rabbitmq.send_command_rabbitmq(
                message,
                queue_name=f'command_write_{sap_id}'
            )

            if status:
                return True, response_message
            else:
                return False

        except Exception as e:
            print(f"Error in handle write command: {e}")
            print(traceback.format_exc())

  