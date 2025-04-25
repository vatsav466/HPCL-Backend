import urdhva_base
import traceback
import hpcl_ceg_model
import csv
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
        csv_file_path = ""
        try:
            alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__
            # Extracting required parameters from alert data
            interlock_name = alert_data.get('interlock_name')
            equipment_name = alert_data.get('tas_device_name') or alert_data.get('device_name') # Prioritize tas_device_name
            sap_id = alert_data.get('sap_id')
            if not (interlock_name and equipment_name and sap_id):
                print("missing required fields")
                return 
             # Define the matching criteria
            match_criteria = {
                "equipment_name": equipment_name,
                "sap_id": sap_id
            }
            
            # Read the CSV file and find the matching row
            matched_row = await find_matching_csv.find_matching_row(csv_file_path, match_criteria)

            if not matched_row:
                print(f"No matching row found for sap_id :{sap_id} and equipment name : {equipment_name}")
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
            # Constructing the message body to post rabbit mq

            message = {
                "command": "write",
                "sensor_tag": tag,
                "value" : write_control
            }

            # handle this message playload to publish to rabbit mq
            status, message = await send_rabbitmq.send_command_rabbitmq(message, queue_name=f'write_{sap_id}')
            if status:
                return True, message
            else:
                return False
        
        except Exception as e:
            print(f"Error in handle write command: {e}")
            print(traceback.format_exc())

  