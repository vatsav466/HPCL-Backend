import urdhva_base
import traceback
import hpcl_ceg_enum
import hpcl_ceg_model
import sys
sys.path.append("/opt/ceg/algo/orchestrator")
import utilities.helpers as helpers
import tas_operations.send_rabbitmq as send_rabbitmq
import orchestrator.alerting.alert_factory as alert_create
import tas_operations.find_matching_csv as find_matching_csv


logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class SendWriteCommand:
    async def get_required_variables(self):
        return ["alert_id" , "interrupt"]
    
    # async def handle_write_command(self, params):
    #     """
    #     Handles the write command for the TAS system based on the alert data and interrupt type.

    #     Args:
    #           params (dict): A dictionary containing 'alert_id' and 'interrupt'
    #     """
    #     csv_file_path = "/opt/ceg/algo/orchestrator/tas_operations/write_tag.csv"
    #     # try:
    #     #     alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))
    #     #     if not isinstance(alert_data, dict):
    #     #         alert_data = alert_data.__dict__
    #     #     # Extracting required parameters from alert data
    #     #     interlock_name = alert_data.get('interlock_name')
    #     #     equipment_name = alert_data.get('tas_device_name') or alert_data.get('device_name') # Prioritize tas_device_name
    #     #     sap_id = alert_data.get('sap_id')
    #     #     if not (interlock_name and equipment_name and sap_id):
    #     #         print("missing required fields")
    #     #         return 
    #     #      # Define the matching criteria
    #     #     match_criteria = {
    #     #         "equipment_name": equipment_name,
    #     #         "sap_id": sap_id
    #     #     }
    #     #     # Read the CSV file and find the matching row
    #     #     matched_row = await find_matching_csv.find_matching_row(csv_file_path, match_criteria)

    #     #     if not matched_row:
    #     #         print(f"No matching row found for sap_id :{sap_id} and equipment name : {equipment_name}")
    #     #         return
            
    #     #     # Extracting the tag and write control from the matched row
    #     #     tag = matched_row['tag']
    #     #     interrupt = params.get('interrupt')
    #     #     if interrupt == "shutdown":
    #     #         write_control = matched_row['set']
    #     #     elif interrupt == "open":
    #     #         write_control = matched_row['clear']
    #     #     else:
    #     #         print(f"Invalid interrupt name: {interrupt}")
    #     #         return
    #     #     # Constructing the message body to post rabbit mq

    #     #     message = {
    #     #         "command": "write",
    #     #         "sensor_tag": tag,
    #     #         "value" : str(write_control)
    #     #     }

    #     #     # handle this message playload to publish to rabbit mq
    #     #     status, message = await send_rabbitmq.send_command_rabbitmq(message, queue_name=f'command_write_{sap_id}')
    #     #     if status:
    #     #         return True, message
    #     #     else:
    #     #         return False
        
    #     # except Exception as e:
    #     #     print(f"Error in handle write command: {e}")
    #     #     print(traceback.format_exc())
    #     try:
    #         alert_id = params.get('alert_id')
    #         alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
    #         print("send write command alert_data --> ", alert_data)
    #         if not isinstance(alert_data, dict):
    #             alert_data = alert_data.__dict__

    #         # Extract relevant fields
    #         interlock_name = alert_data.get('interlock_name')
    #         equipment_name = alert_data.get('tas_device_name') or alert_data.get('device_name')
    #         sap_id = alert_data.get('sap_id')

    #         # Check required fields
    #         if not (interlock_name and equipment_name and sap_id):
    #             print("Missing required fields")
    #             return

    #         # If current alert is not already 'BCU Permissive Off_Fail'
    #         # Check if there's an open alert with 'BCU Permissive Off_Fail' for same sap_id
    #         if interlock_name == "BCU Permissive Off_Fail":
    #             open_alert = await hpcl_ceg_model.Alerts.get(alert_id)
    #             print("open_alert ---> ", open_alert)
    #             if open_alert:
    #                 # Update current alert interlock_name
    #                 await hpcl_ceg_model.Alerts(**{"id": alert_id, "interlock_name": "BCU Permissive Off_Fail_DNC"}).modify()
    #                 interlock_name = "BCU Permissive Off_Fail_DNC"

    #         # Define the matching criteria
    #         match_criteria = {
    #             "equipment_name": equipment_name,
    #             "sap_id": sap_id
    #         }

    #         # Read the CSV file and find the matching row
    #         matched_row = await find_matching_csv.find_matching_row(csv_file_path, match_criteria)

    #         if not matched_row:
    #             print(f"No matching row found for sap_id: {sap_id} and equipment name: {equipment_name}")
    #             return

    #         # Extracting the tag and write control from the matched row
    #         tag = matched_row['tag']
    #         interrupt = params.get('interrupt')

    #         if interrupt == "shutdown":
    #             write_control = matched_row['set']
    #         elif interrupt == "open":
    #             write_control = matched_row['clear']
    #         else:
    #             print(f"Invalid interrupt name: {interrupt}")
    #             return

    #         # Constructing the message body to post to RabbitMQ
    #         message = {
    #             "command": "write",
    #             "sensor_tag": tag,
    #             "value": str(write_control)
    #         }

    #         # Send message to RabbitMQ
    #         status, response_message = await send_rabbitmq.send_command_rabbitmq(
    #             message,
    #             queue_name=f'command_write_{sap_id}'
    #         )

    #         if status:
    #             return True, response_message
    #         else:
    #             return False

    #     except Exception as e:
    #         print(f"Error in handle write command: {e}")
    #         print(traceback.format_exc())

  
    async def check_and_create_gantry_alert(self, bu, sap_id, location_name):
        """
        Check conditions and create a new Gantry Permissive Off_DNC alert if needed.
        
        Conditions for creating new alert:
        1. SOP028 alert in open state AND BCU Permissive Off is not present AND BCU Permissive Off_Fail is present with open state
        
        Otherwise, no new alert is needed.
        """
        try:
            # Check for SOP028 alerts in open state
            params = urdhva_base.queryparams.QueryParams(q=f"""bu = '{bu}' and sap_id = '{sap_id}' and sop_id = 'SOP028' and alert_status = 'Open'""")
            sop028_alerts = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')

            # Check for BCU Permissive Off alerts
            params = urdhva_base.queryparams.QueryParams(q=f"""bu = '{bu}' and sap_id = '{sap_id}' and alert_status = 'Open' and interlock_name = 'BCU Permissive Off'""")
            bcu_permissive_off_alerts = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
            
            # Check for open BCU Permissive Off_Fail alerts
            params = urdhva_base.queryparams.QueryParams(q=f"""bu = '{bu}' and sap_id = '{sap_id}' and alert_status = 'Open' and interlock_name = 'BCU Permissive Off_Fail'""")
            bcu_permissive_off_fail_alerts = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
            
            # Decision logic for creating new alert
            create_new_alert = False
            
            # Check if SOP028 alert exists in open state
            has_sop028_open = sop028_alerts.get('data') and len(sop028_alerts.get('data', [])) > 0
            
            # Check if BCU Permissive Off exists
            has_bcu_permissive_off = bcu_permissive_off_alerts.get('data') and len(bcu_permissive_off_alerts.get('data', [])) > 0
            
            # Check if BCU Permissive Off_Fail exists with open state
            has_bcu_permissive_off_fail = bcu_permissive_off_fail_alerts.get('data') and len(bcu_permissive_off_fail_alerts.get('data', [])) > 0
            
            # Condition: SOP028 alert in open state AND BCU Permissive Off is not present AND BCU Permissive Off_Fail is present
            if has_sop028_open and not has_bcu_permissive_off and has_bcu_permissive_off_fail:
                create_new_alert = True
                print("Creating alert: Required conditions met for Gantry Permissive Off_DNC alert")
            else:
                print("No need to create new alert - conditions not met")
                return None
            
            # If we need to create a new alert
            if create_new_alert:
                alert_message = "Gantry Permissive Off_DNC"
                
                # Create new alert data
                alert_data = {
                    "bu": bu,
                    "sap_id": sap_id,
                    "location_name": location_name,
                    "sop_id": "SOP028A",
                    "interlock_name": alert_message,
                    "alert_status": "Open",
                    "alert_state": "InProgress",
                    "severity": "CRITICAL",
                    "alert_section": "TAS",
                    "device_name": "",
                    "return_data": True
                }
                
                # Get Camunda URL
                camunda_url = await helpers.get_camunda_url(bu=bu, sap_id=sap_id, alert_section="TAS")
                
                # Create alert using factory
                status, created_alert = await alert_create.AlertFactory().create_alert(alert_data=alert_data, camunda_url=camunda_url)
                
                if not status or not created_alert:
                    print("Failed to create alert")
                    return None
                    
                # Process the newly created alert
                if isinstance(created_alert, dict):
                    alert_id = created_alert.get("id")
                    if not alert_id:
                        print("Alert ID missing in created alert")
                        return None
                        
                    # Add history to the newly created alert
                    new_alert = await hpcl_ceg_model.Alerts.get(alert_id)
                    
                    if not isinstance(new_alert, dict):
                        new_alert = new_alert.__dict__
                    
                    # Initialize alert_history if it doesn't exist
                    if 'alert_history' not in new_alert:
                        new_alert['alert_history'] = {}
                    
                    new_alert['alert_history']['action_type'] = hpcl_ceg_enum.AlertActionType.Message.value
                    new_alert['alert_history']['action_msg'] = "System Generated alert"
                    
                    # Save the updated alert with history
                    await hpcl_ceg_model.Alerts(**{"id": alert_id, "alert_history": new_alert['alert_history']}).modify()
                    
                    print(f"Successfully created new Gantry Permissive Off_DNC alert with ID: {alert_id}")
                    return alert_id
                
                print("Created alert is not a dictionary")
                return None
        
        except Exception as e:
            print(f"Error in check_and_create_gantry_alert: {e}")
            print(traceback.format_exc())
            return None


    async def handle_write_command(self, params):
        """
        Handle write command for alerts, with improved error handling.
        Creates a new Gantry alert if specific conditions are met.
        """
        csv_file_path = "/Users/mac_1/PycharmProjects/Cloud/dnc_backend_v2/orchestrator/tas_operations/write_tag.csv"
        try:
            alert_id = params.get('alert_id')
            if not alert_id:
                print("Missing alert_id parameter")
                return False, "Missing alert_id parameter"
                
            alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
            print("send write command alert_data --> ", alert_data)
            
            if not alert_data:
                print(f"Alert with ID {alert_id} not found")
                return False, f"Alert with ID {alert_id} not found"
                
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            # Extract relevant fields
            interlock_name = alert_data.get('interlock_name')
            equipment_name = alert_data.get('tas_device_name') or alert_data.get('device_name')
            sap_id = alert_data.get('sap_id')
            bu = alert_data.get('bu')
            location_name = alert_data.get('location_name')

            # Check required fields
            if not (interlock_name and equipment_name and sap_id):
                print("Missing required fields")
                return False, "Missing required fields"

            # Check conditions and create a new alert if needed
            await self.check_and_create_gantry_alert(bu=bu, sap_id=sap_id, location_name=location_name)

            # Define the matching criteria
            match_criteria = {
                "equipment_name": equipment_name,
                "sap_id": sap_id
            }

            # Read the CSV file and find the matching row
            matched_row = await find_matching_csv.find_matching_row(csv_file_path, match_criteria)

            if not matched_row:
                print(f"No matching row found for sap_id: {sap_id} and equipment name: {equipment_name}")
                return False, f"No matching row found for sap_id: {sap_id} and equipment name: {equipment_name}"

            # Extracting the tag and write control from the matched row
            tag = matched_row['tag']
            interrupt = params.get('interrupt')

            if interrupt == "shutdown":
                write_control = matched_row['set']
            elif interrupt == "open":
                write_control = matched_row['clear']
            else:
                print(f"Invalid interrupt name: {interrupt}")
                return False, f"Invalid interrupt name: {interrupt}"

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
                return False, response_message

        except Exception as e:
            print(f"Error in handle write command: {e}")
            print(traceback.format_exc())
            return False, f"Error: {str(e)}"