# import urdhva_base
# import re
# import json
# import uuid
# import asyncio
# import psycopg2
# import numpy as np
# import pandas as pd
# import polars as pl
# import hpcl_ceg_model
# from datetime import datetime, date
# import orchestrator.alerting.alert_manager as alert_manager
# import orchestrator.alerting.alert_factory as alert_factory


# # Path to the JSON file
# json_file = "config.json"

# try:
#     with open(json_file, "r", encoding="utf-8") as file:
#         config = json.load(file)
#     print("JSON loaded successfully!")

#     # Optional: Print some sample data to verify it's loaded correctly
#     print(f"Oracle Host: {config['oracle']['host']}")
#     print(f"PostgreSQL Database: {config['postgresql']['database_name']}")
#     print(f"First Oracle Table: {config['oracle_tables'][0]}")

# except json.JSONDecodeError as e:
#     print(f"JSON parsing error: {e}")
#     config = None  # Prevent using an invalid config
# except FileNotFoundError:
#     print(f"JSON file not found: {json_file}")
#     config = None
# except Exception as e:
#     print(f"Unexpected error: {e}")
#     config = None

# class Postgresql:
#     def __init__(self):
#         """Initialize PostgreSQL connection details."""
#         if config is None:
#             raise ValueError("Configuration not loaded. Cannot proceed.")
#         self.params = config['postgresql']

#     def get_connection(self):
#         """Establish a synchronous PostgreSQL connection."""
#         return psycopg2.connect(
#             host=self.params['host'],
#             port=self.params['port'],
#             user=self.params['user_name'],
#             password=self.params['password'],
#             dbname=self.params['database_name']
#         )

#     def get_default_schema(self):
#         """Return the default schema."""
#         return "public"

#     async def cal_host_manual_fan_printed(self, data):
#         """
#         Calculate whether to create an actionable alert based on manual vs auto fan count comparison.
#         Returns True if we should close the alert, False if we should keep it open (actionable).
#         """
#         data = pd.DataFrame(data)
        
#         # Get the last record of the day (assuming data is sorted by timestamp)
#         if data.empty:
#             return False  # No data, no alert needed
        
#         # Get the auto fan count and calculate the 5% tolerance
#         total_fan_count = data['total_count'].iloc[-1]  # Get the latest record
#         total_fan_with_tolerance = total_fan_count * 0.05  # Add 5% tolerance
        
#         # Get the manual fan count
#         manual_fan_count = data['manual_fan_count'].iloc[-1]
        
#         # If manual fan count is greater than auto fan count + tolerance, 
#         if manual_fan_count == 0:
#             return False, "Manual FAN Count is Zero", "No manual FAN was printed"
#         if manual_fan_count != 0 and manual_fan_count > total_fan_with_tolerance:
#             return (True, 
#                         "Manual FAN printed more than 5% of total TT loaded", 
#                         f"{manual_fan_count} is less than {total_fan_with_tolerance} with 5%"
#                     )
#         elif manual_fan_count != 0 and manual_fan_count < total_fan_with_tolerance:
#             return (True, 
#                         "Manual FAN printed less than 5% of total TT loaded", 
#                         f"{manual_fan_count} is less than {total_fan_with_tolerance} with 5%"
#                     )


#     async def cal_unauthorized_flow(self, total_net):
#         if total_net > 5:
#             return True, "Unauthorized flow_BCU"
#         return None, None

#     async def create_cancel_tt_report(self, data):
#         to_date = urdhva_base.utilities.get_present_time(True).strftime("%Y-%m-%d")
#         query = f"""select id from alerts where interlock_name = 'Cancel TT Reported' and vehicle_number = '{data["vehicle_number"]}' and tt_load_number = '{data["tt_load_number"]}' """ \
#                 f"""and created_at::DATE = '{to_date}'"""
#         print("create_cancel_tt_report: ", query)
#         resp = await hpcl_ceg_model.Alerts.get_aggr_data(query)
#         print("Resp: ", resp)
#         if resp.get("data", []):
#             alert_data = await hpcl_ceg_model.Alerts.get(resp.get("data", [])[0]["id"])
#             if not isinstance(alert_data, dict):
#                 alert_data = alert_data.__dict__
#             data['alert_id'] = alert_data['external_id']
#             action_msg = f"Load Number: {data['tt_load_number']} with Truck Number: {data['vehicle_number']} and Compartment Number: {data['device_msg']}"
#             input_data = {
#                 "action_type": "Cancelled",
#                 "action_msg": action_msg
#             }
#             await alert_manager.AlertAction().update_alert_history(
#                         input_data=input_data, alert_data=alert_data
#                     )
#             return True, "Success", data
        
#         status, msg = await alert_factory.AlertFactory.create_alert(data)
#         return status, msg, data
    
#     async def create_bay_reasignment_report(self, data):
#         to_date = urdhva_base.utilities.get_present_time(True).strftime("%Y-%m-%d")
#         query = f"""select id from alerts where interlock_name = 'Bay reassignment' and vehicle_number = '{data["vehicle_number"]}' and tt_load_number = '{data["tt_load_number"]}' """ \
#                 f"""and created_at::DATE = '{to_date}'"""
#         resp = await hpcl_ceg_model.Alerts.get_aggr_data(query)
#         if resp.get("data", []):
#             alert_data = await hpcl_ceg_model.Alerts.get(resp.get("data", [])[0]["id"])
#             if not isinstance(alert_data, dict):
#                 alert_data = alert_data.__dict__
#             data['alert_id'] = alert_data['external_id']
#             action_msg = f"Truck Number: {data['vehicle_number']} and Compartment Number: {data['device_msg']}"
#             input_data = {
#                 "action_type": "BayReAssigned",
#                 "action_msg": action_msg
#             }
#             await alert_manager.AlertAction().update_alert_history(
#                         input_data=input_data, alert_data=alert_data
#                     )
#             return True, "Success", data
        
#         status, msg = await alert_factory.AlertFactory.create_alert(data)
#         return status, msg, data
    
#     async def close_created_alert(self, alert_data):
#         # Extract alert_id from response (assuming response contains alert_id)
#         query = (f"""external_id='{alert_data["alert_id"]}'""")
#         params = urdhva_base.queryparams.QueryParams()
#         params.limit = 1
#         params.q = query
#         alert_resp = await hpcl_ceg_model.Alerts.get_all(params)
        
#         body =  alert_resp.body
#         data = json.loads(body.decode('utf-8'))
#         if 'data' in data and data['data']:
#             alert_id = data['data'][0]['external_id']
#         else:
#             print(f"Alert not found for {alert_data['alert_id']}")
#             return
#         # alert_id = msg.get("alert_id") if isinstance(msg, dict) else None
#         # Close Alert
#         close_data = {
#             'bu': 'TAS',
#             'sop_id': alert_data['sop_id'],
#             'sap_id': alert_data['sap_id'],
#             'interlock_name': alert_data['interlock_name'],
#             'alert_id' : alert_data['alert_id']
            
#         }
#         close_success, close_msg = await alert_factory.AlertFactory.close_alert(close_data)
#         print("close_msg :", close_msg)
#         if not close_success:
#             print(f"Failed to close alert: {close_msg}")

#     async def create_table(self, schema_name, table_name, sample_records, primary_key=[], unique_key=[]):
#         """Create a table and upsert sample records."""
#         for record in sample_records:
#             if "date" in record and isinstance(record["date"], str):
#                 try:
#                     record["date"] = date.fromisoformat(record["date"])
#                 except ValueError:
#                     # Alternative parsing if not in ISO format
#                     record["date"] = pd.to_datetime(record["date"]).date()
            
#             if "date_time" in record and isinstance(record["date_time"], str):
#                 try:
#                     record["date_time"] = datetime.fromisoformat(record["date_time"])
#                 except ValueError:
#                     # Alternative parsing if not in ISO format
#                     record["date_time"] = pd.to_datetime(record["date_time"])
            
#             for key, value in record.items():
#                 if value is None or (isinstance(value, float) and np.isnan(value)) or value is pd.NaT:
#                     record[key] = None
#                 if key == "timestamp" and isinstance(value, str):  # Convert timestamp properly
#                     record[key] = pd.to_datetime(value)  # Converts to datetime
#                 # Add these checks to your existing function
#                 if "created_date" in record and isinstance(record["created_date"], str):
#                     record["created_date"] = pd.to_datetime(record["created_date"])

#                 if "cancelled_date" in record and isinstance(record["cancelled_date"], str):
#                     record["cancelled_date"] = pd.to_datetime(record["cancelled_date"])

#                 if "entry_time" in record and isinstance(record["entry_time"], str):
#                     record["entry_time"] = pd.to_datetime(record["entry_time"])

#                 if "exit_time" in record and isinstance(record["exit_time"], str):
#                     record["exit_time"] = pd.to_datetime(record["exit_time"])
                    
#                 if "transaction_end_time" in record and isinstance(record["transaction_end_time"], str):
#                     record["transaction_end_time"] = pd.to_datetime(record["transaction_end_time"])
                
#                 if "bay_reassignment_time" in record and isinstance(record["bay_reassignment_time"], str):
#                     record["bay_reassignment_time"] = pd.to_datetime(record["bay_reassignment_time"])
                
#                 if "current_k_factor" in record:
#                     try:
#                         record["current_k_factor"] = round(float(record["current_k_factor"]), 2) if record["current_k_factor"] else None
#                     except (ValueError, TypeError):
#                         record["current_k_factor"] = None  # Handle invalid values

#                 if "current_meter_factor" in record:
#                     try:
#                         record["current_meter_factor"] = round(float(record["current_meter_factor"]), 2) if record["current_meter_factor"] else None
#                     except (ValueError, TypeError):
#                         record["current_meter_factor"] = None  # Handle invalid values

#         print("sample_records --> ", sample_records)
#         if not isinstance(sample_records, pl.DataFrame):
#             sample_records = pl.DataFrame(sample_records)

#         data = sample_records.to_dicts()

#         # Check if the model exists in hpcl_ceg_model
#         model = getattr(hpcl_ceg_model, table_name, None)
#         if model is None:
#             raise ValueError(f"Model '{table_name}' not found in hpcl_ceg_model.")

#         table_db_name = getattr(model, '__tablename__', table_name)
#         if table_db_name == 'host_unauthorised_flow':
#             data = [x for x in data if x['nettotalizer'] > 0]
        
#         if table_db_name == 'host_manual_fan_printed':
#             # Get unique SAP IDs from the input data
#             unique_sap_ids = list(set(x['sap_id'] for x in data))
            
#             # Prepare a list to store final data to be processed
#             final_processed_data = []

#             # Process each unique SAP ID separately
#             for specific_sap_id in unique_sap_ids:
#                 # Filter data for this specific SAP ID
#                 sap_id_data = [x for x in data if x['sap_id'] == specific_sap_id]
                
#                 # Filter out zero manual_fan_count records for regular processing
#                 non_zero_records = [x for x in sap_id_data if x['manual_fan_count'] > 0]
                
#                 # If no non-zero records, handle end of day scenario
#                 to_day = urdhva_base.utilities.get_present_time().strftime("%H")
#                 if int(to_day) == 18 and not non_zero_records:
#                     # Check if we have any non-zero records for today for this specific SAP ID
#                     to_date = urdhva_base.utilities.get_present_time().strftime("%Y-%m-%d")
#                     check_query = f"""select count(*) from "{table_db_name}" where date::DATE = '{to_date}' and sap_id = '{specific_sap_id}' and manual_fan_count != 0"""
#                     check_resp = await model.get_aggr_data(check_query)
                    
#                     # If no non-zero records exist, find a zero record
#                     if check_resp.get("data") and check_resp.get("data")[0].get("count", 0) == 0:
#                         # Find the latest zero record from original data for this SAP ID
#                         zero_records = [
#                             x for x in sample_records.to_dicts() 
#                             if x['manual_fan_count'] == 0 and x['sap_id'] == specific_sap_id
#                         ]
                        
#                         if zero_records:
#                             # Sort by date_time and get the latest
#                             zero_records.sort(key=lambda x: x.get('date_time', ''), reverse=True)
#                             final_processed_data.append(zero_records[0])
#                 else:
#                     # Add non-zero records for this SAP ID
#                     final_processed_data.extend(non_zero_records)

#             # Update data to be the final processed data
#             data = final_processed_data

#             # Rest of your existing code remains the same
#             print("data for manual fan printed --> ", data)
#         status, msg = await model.bulk_update(data, upsert=True, upsert_skip_keys=['alert_created']) 

#         #     # Filter out zero manual_fan_count records for regular processing
#         #     data = [x for x in data if x['manual_fan_count'] > 0]
#         #     print("data --> ", data)
#         #     # Only if no non-zero records and it's end of day (18:00), include a zero record if available
#         #     to_day = urdhva_base.utilities.get_present_time().strftime("%H")
#         #     if int(to_day) == 18 and not any(x['manual_fan_count'] != 0 for x in data):
#         #         # Check if we have any non-zero records for today in the database
#         #         to_date = urdhva_base.utilities.get_present_time().strftime("%Y-%m-%d")
#         #         check_query = f"""select count(*) from "{table_db_name}" where date::DATE = '{to_date}' and manual_fan_count != 0"""
#         #         check_resp = await model.get_aggr_data(check_query)
                
#         #         # If no non-zero records exist for today, find a zero record to include
#         #         if check_resp.get("data") and check_resp.get("data")[0].get("count", 0) == 0:
#         #             # Find the latest zero record from original data
#         #             zero_records = [x for x in sample_records.to_dicts() if x['manual_fan_count'] == 0]
#         #             if zero_records:
#         #                 # Sort by date_time and get the latest
#         #                 zero_records.sort(key=lambda x: x.get('date_time', ''), reverse=True)
#         #                 data.append(zero_records[0])  # Add the latest zero record
#         #     print("data for manual fan printed --> ", data)
#         # status, msg = await model.bulk_update(data, upsert=True, upsert_skip_keys=['alert_created'])  # Use upsert=True if needed
        
#         # Get only alert not created records
#         to_date = urdhva_base.utilities.get_present_time().strftime("%Y-%m-%d")
#         query = f"""select * from "{table_db_name}" where alert_created = false"""
#         if table_db_name == 'host_manual_fan_printed':
#             query = f"""select * from "{table_db_name}" where date::DATE = '{to_date}' and manual_fan_count !=0 order by date_time asc"""
#         resp = await model.get_aggr_data(query)

#         if table_db_name == 'host_manual_fan_printed':
#             to_date = urdhva_base.utilities.get_present_time().strftime("%Y-%m-%d")
#             #if int(to_day) == 19:
#             # Only get records with non-zero manual_fan_count for alert processing
#             query = f"""select * from "{table_db_name}" where date::DATE = '{to_date}' and manual_fan_count != 0 and alert_created = false order by date_time asc"""
#             resp = await model.get_aggr_data(query)
            
#             if resp.get("data", []):
#                 # Process alerts for non-zero records
#                 for record in resp.get("data", []):
#                     is_close_alert = False
#                     interlock_name = config['interlock_name'].get(table_name)
#                     severity = config['severity'].get(table_name, "Medium")
#                     sop_id = config['sop_id'].get(table_name)
#                     device_msg = ""

#                     # Calculate alert status
#                     result = await self.cal_host_manual_fan_printed([record])
                    
#                     if isinstance(result, tuple) and len(result) == 3:
#                         is_close_alert, interlock_name, device_msg = result

#                     # Prepare alert data
#                     alert_data = {
#                         'bu': 'TAS',
#                         'sop_id': sop_id,
#                         'sap_id': record.get('sap_id'),
#                         'interlock_name': interlock_name,
#                         'severity': severity,
#                         'alert_id': str(uuid.uuid1()),
#                         'device_name': record.get('bcu_number'),
#                         'device_type': 'Gantry',
#                         'vehicle_number': record.get('truck_number', ''),
#                         'device_msg': device_msg
#                     }

#                     # Create alert for non-zero records
#                     success, msg = await alert_factory.AlertFactory.create_alert(alert_data)
#                     print("Alert created msg:", msg)
                    
#                     # Close alert if needed
#                     if is_close_alert:
#                         await self.close_created_alert(alert_data=alert_data)
                        
#                     # Mark record as processed
#                     query = f"update {table_db_name} set alert_created = true where id = {record['id']}"
#                     await model.update_by_query(query)
                    
#                 return {"status": "Table updated and alerts processed for non-zero records"}
#             else:
#                 return {"status": "No non-zero records to process for alerts"}

#         if table_db_name == 'host_unauthorised_flow':
#             unauthorised_records = resp.get("data", [])
#             # Compute the total sum of all nettotalizer values
#             total_net = sum(float(record.get("nettotalizer", 0)) for record in unauthorised_records if float(record.get("nettotalizer", 0)) != 0)
#             # Extract unique BCU numbers
#             bcu_numbers = sorted(set(record.get("bcu_number", "") for record in unauthorised_records))

#             # Check if unauthorized flow should be triggered based on total_net
#             is_close_alert, interlock_name = await self.cal_unauthorized_flow(total_net)

#             # Construct device message
#             device_msg = f"BCU Numbers: {', '.join(bcu_numbers)}, Total Net Totalizer: {total_net}"

#             # Create and close the alert if needed
#             if unauthorised_records and is_close_alert:
#                 # Use the first record for necessary data
#                 first_record = unauthorised_records[0]
#                 alert_data = {
#                     'bu': 'TAS',
#                     'sop_id': config['sop_id'].get(table_name),
#                     'sap_id': first_record.get('sap_id'),
#                     'interlock_name': interlock_name,
#                     'severity': config['severity'].get(table_name, "Medium"),
#                     'alert_id': str(uuid.uuid1()),
#                     'device_name': ', '.join(bcu_numbers),  # Since we're dealing with multiple BCUs
#                     'device_type': 'Gantry',
#                     'vehicle_number': '',  # This might need to be populated appropriately
#                     'device_msg': device_msg
#                 }
                
#                 # Create Alert
#                 success, msg = await alert_factory.AlertFactory.create_alert(alert_data)
#                 print("msg :", msg)
                
#                 # Close alert if needed
#                 if success and is_close_alert:
#                     await self.close_created_alert(alert_data=alert_data)
                    
#                 # Update all records as alert_created = true
#                 for record in unauthorised_records:
#                     query = f"update {table_db_name} set alert_created = true where id = {record['id']}"
#                     await model.update_by_query(query)
                    
#                 return {"status": "Unauthorized flow alerts processed"}

#          # Process each record to create and close alerts
#         if resp.get("data", []):
#             for record in resp.get("data", []):
#                 try:
#                     # Fetch config based on table name
#                     is_close_alert = False
#                     interlock_name = config['interlock_name'].get(table_name)
#                     severity = config['severity'].get(table_name, "Medium")
#                     sop_id = config['sop_id'].get(table_name)
#                     device_msg = ""
#                     if interlock_name == 'Cancel TT Reported':
#                         device_msg = f"For Compartment_Number: {record.get('compartment_number', '')}".strip()
                    
#                     if interlock_name == 'Bay reasignment':
#                         device_msg = f"For Load Number: {record.get('load_number', '')} the ReAssigned Bay: {record.get('reassigned_bay', '')}".strip()

#                     # Extract necessary fields from the record
#                     alert_data = {
#                         'bu': 'TAS',
#                         'sop_id': sop_id,
#                         'sap_id': record.get('sap_id'),
#                         'interlock_name': interlock_name,
#                         'severity': severity,
#                         'alert_id': str(uuid.uuid1()),
#                         'device_name': record.get('bcu_number'),
#                         'device_type': 'Gantry',
#                         'vehicle_number': record.get('truck_number', ''),
#                         'tt_load_number': record.get('load_number', ''),
#                         'device_msg': device_msg
#                     }

#                     # Create Alert
#                     if interlock_name == 'Cancel TT Reported':
#                         is_close_alert = True
#                         success, msg, alert_data = await self.create_cancel_tt_report(alert_data)
#                     elif interlock_name == 'Bay reassignment':
#                         is_close_alert = True
#                         success, msg, alert_data = await self.create_bay_reasignment_report(alert_data)
#                     else:
#                         success, msg = await alert_factory.AlertFactory.create_alert(alert_data)
#                         print("msg :", msg)
#                         is_close_alert = True
#                         if not success:
#                             print(f"Failed to create alert: {msg}")
#                             return {"status": False, "message": f"Failed {e}", "data": []}
                    
#                     # Set alert_created = true for alert created record
#                     query = f"update {table_db_name} set alert_created = true where id = {record['id']}"
#                     await model.update_by_query(query)

#                     # Close alert
#                     if is_close_alert:
#                         await self.close_created_alert(alert_data=alert_data)

#                 except Exception as e:
#                     print(f"Error : {str(e)}")
#                     return {"status": False, "message": f"Failed {e}", "data": []}

#             return {"status": "Table created and alerts processed"}
#         else:
#             print("Bulk not posted")
#             return {"status": "No data to create alert"}




import urdhva_base
import re
import json
import uuid
import asyncio
import psycopg2
import numpy as np
import pandas as pd
import polars as pl
import hpcl_ceg_model
from datetime import datetime, date
import orchestrator.alerting.alert_manager as alert_manager
import orchestrator.alerting.alert_factory as alert_factory


# Path to the JSON file
json_file = "config.json"

try:
    with open(json_file, "r", encoding="utf-8") as file:
        config = json.load(file)
    print("JSON loaded successfully!")

    # Optional: Print some sample data to verify it's loaded correctly
    print(f"Oracle Host: {config['oracle']['host']}")
    print(f"PostgreSQL Database: {config['postgresql']['database_name']}")
    print(f"First Oracle Table: {config['oracle_tables'][0]}")

except json.JSONDecodeError as e:
    print(f"JSON parsing error: {e}")
    config = None  # Prevent using an invalid config
except FileNotFoundError:
    print(f"JSON file not found: {json_file}")
    config = None
except Exception as e:
    print(f"Unexpected error: {e}")
    config = None

class Postgresql:
    def __init__(self):
        """Initialize PostgreSQL connection details."""
        if config is None:
            raise ValueError("Configuration not loaded. Cannot proceed.")
        self.params = config['postgresql']

    def get_connection(self):
        """Establish a synchronous PostgreSQL connection."""
        return psycopg2.connect(
            host=self.params['host'],
            port=self.params['port'],
            user=self.params['user_name'],
            password=self.params['password'],
            dbname=self.params['database_name']
        )

    def get_default_schema(self):
        """Return the default schema."""
        return "public"

    # async def cal_host_manual_fan_printed(self, data):
    #     """
    #     Calculate whether to create an actionable alert based on manual vs auto fan count comparison.
    #     Returns True if we should close the alert, False if we should keep it open (actionable).
    #     """
    #     data = pd.DataFrame(data)
        
    #     # Get the last record of the day (assuming data is sorted by timestamp)
    #     if data.empty:
    #         return False  # No data, no alert needed
        
    #     # Get the auto fan count and calculate the 5% tolerance
    #     total_fan_count = data['total_count'].iloc[-1]  # Get the latest record
    #     total_fan_with_tolerance = total_fan_count * 0.05  # Add 5% tolerance
        
    #     # Get the manual fan count
    #     manual_fan_count = data['manual_fan_count'].iloc[-1]
        
    #     # If manual fan count is greater than auto fan count + tolerance, 
    #     if manual_fan_count == 0:
    #         return False, "Manual FAN Count is Zero", "No manual FAN was printed"
    #     if manual_fan_count != 0 and manual_fan_count > total_fan_with_tolerance:
    #         return (True, 
    #                     "Manual FAN printed more than 5% of total TT loaded", 
    #                     f"{manual_fan_count} is less than {total_fan_with_tolerance} with 5%"
    #                 )
    #     elif manual_fan_count != 0 and manual_fan_count < total_fan_with_tolerance:
    #         return (True, 
    #                     "Manual FAN printed less than 5% of total TT loaded", 
    #                     f"{manual_fan_count} is less than {total_fan_with_tolerance} with 5%"
    #                 )


    async def cal_host_manual_fan_printed(self, data):
        """
        Calculate whether to create an actionable alert based on manual vs auto fan count comparison.
        Returns True if we should create an alert, False if no alert is needed.
        """
        data = pd.DataFrame(data)
        
        # Get the last record of the day (assuming data is sorted by timestamp)
        if data.empty:
            return False, "No data", "No data available for analysis"
        
        # Get the total fan count and manual fan count
        total_fan_count = data['total_count'].iloc[-1]  # Get the latest record
        manual_fan_count = data['manual_fan_count'].iloc[-1]
        
        # If no manual fans printed, no alert needed
        if manual_fan_count == 0:
            return False, "No alert needed", "No manual FAN was printed"
        
        # Calculate percentage of manual fans compared to total
        if total_fan_count > 0:  # Avoid division by zero
            manual_percentage = (manual_fan_count / total_fan_count) * 100
        else:
            return True, "Alert: Division by zero", "Total count is zero but manual count exists"
        
        # Create alert if manual percentage exceeds 5%
        if manual_percentage > 5:
            return True, "Alert: Manual FAN printed more than 5% of total", f"Manual percentage: {manual_percentage:.2f}% exceeds threshold of 5%"
        else:
            return False, "No alert needed", f"Manual percentage: {manual_percentage:.2f}% is within threshold of 5%"


    async def cal_unauthorized_flow(self, total_net):
        if total_net > 5:
            return True, "Unauthorized flow_BCU"
        return None, None

    async def create_cancel_tt_report(self, data):
        to_date = urdhva_base.utilities.get_present_time(True).strftime("%Y-%m-%d")
        query = f"""select id from alerts where interlock_name = 'Cancel TT Reported' and vehicle_number = '{data["vehicle_number"]}' and tt_load_number = '{data["tt_load_number"]}' """ \
                f"""and created_at::DATE = '{to_date}'"""
        print("create_cancel_tt_report: ", query)
        resp = await hpcl_ceg_model.Alerts.get_aggr_data(query)
        print("Resp: ", resp)
        if resp.get("data", []):
            alert_data = await hpcl_ceg_model.Alerts.get(resp.get("data", [])[0]["id"])
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__
            data['alert_id'] = alert_data['external_id']
            action_msg = f"Load Number: {data['tt_load_number']} with Truck Number: {data['vehicle_number']} and Compartment Number: {data['device_msg']}"
            input_data = {
                "action_type": "Cancelled",
                "action_msg": action_msg
            }
            await alert_manager.AlertAction().update_alert_history(
                        input_data=input_data, alert_data=alert_data
                    )
            return True, "Success", data
        
        status, msg = await alert_factory.AlertFactory.create_alert(data)
        return status, msg, data
    
    async def create_bay_reasignment_report(self, data):
        to_date = urdhva_base.utilities.get_present_time(True).strftime("%Y-%m-%d")
        query = f"""select id from alerts where interlock_name = 'Bay reassignment' and vehicle_number = '{data["vehicle_number"]}' and tt_load_number = '{data["tt_load_number"]}' """ \
                f"""and created_at::DATE = '{to_date}'"""
        resp = await hpcl_ceg_model.Alerts.get_aggr_data(query)
        if resp.get("data", []):
            alert_data = await hpcl_ceg_model.Alerts.get(resp.get("data", [])[0]["id"])
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__
            data['alert_id'] = alert_data['external_id']
            action_msg = f"Truck Number: {data['vehicle_number']} and Compartment Number: {data['device_msg']}"
            input_data = {
                "action_type": "BayReAssigned",
                "action_msg": action_msg
            }
            await alert_manager.AlertAction().update_alert_history(
                        input_data=input_data, alert_data=alert_data
                    )
            return True, "Success", data
        
        status, msg = await alert_factory.AlertFactory.create_alert(data)
        return status, msg, data
    
    async def close_created_alert(self, alert_data):
        # Extract alert_id from response (assuming response contains alert_id)
        query = (f"""external_id='{alert_data["alert_id"]}'""")
        params = urdhva_base.queryparams.QueryParams()
        params.limit = 1
        params.q = query
        alert_resp = await hpcl_ceg_model.Alerts.get_all(params)
        
        body =  alert_resp.body
        data = json.loads(body.decode('utf-8'))
        if 'data' in data and data['data']:
            alert_id = data['data'][0]['external_id']
        else:
            print(f"Alert not found for {alert_data['alert_id']}")
            return
        # Close Alert
        close_data = {
            'bu': 'TAS',
            'sop_id': alert_data['sop_id'],
            'sap_id': alert_data['sap_id'],
            'interlock_name': alert_data['interlock_name'],
            'alert_id' : alert_data['alert_id']
            
        }
        close_success, close_msg = await alert_factory.AlertFactory.close_alert(close_data)
        print("close_msg :", close_msg)
        if not close_success:
            print(f"Failed to close alert: {close_msg}")

    async def create_table(self, schema_name, table_name, sample_records, primary_key=[], unique_key=[]):
        """Create a table and upsert sample records."""
        for record in sample_records:
            if "date" in record and isinstance(record["date"], str):
                try:
                    record["date"] = date.fromisoformat(record["date"])
                except ValueError:
                    # Alternative parsing if not in ISO format
                    record["date"] = pd.to_datetime(record["date"]).date()
            
            if "date_time" in record and isinstance(record["date_time"], str):
                try:
                    record["date_time"] = datetime.fromisoformat(record["date_time"])
                except ValueError:
                    # Alternative parsing if not in ISO format
                    record["date_time"] = pd.to_datetime(record["date_time"])
            
            for key, value in record.items():
                if value is None or (isinstance(value, float) and np.isnan(value)) or value is pd.NaT:
                    record[key] = None
                if key == "timestamp" and isinstance(value, str):  # Convert timestamp properly
                    record[key] = pd.to_datetime(value)  # Converts to datetime
                # Add these checks to your existing function
                if "created_date" in record and isinstance(record["created_date"], str):
                    record["created_date"] = pd.to_datetime(record["created_date"])
                
                if "date_time" in record and isinstance(record["date_time"], str):
                    record["date_time"] = pd.to_datetime(record["date_time"])

                if "cancelled_date" in record and isinstance(record["cancelled_date"], str):
                    record["cancelled_date"] = pd.to_datetime(record["cancelled_date"])

                if "entry_time" in record and isinstance(record["entry_time"], str):
                    record["entry_time"] = pd.to_datetime(record["entry_time"])

                if "exit_time" in record and isinstance(record["exit_time"], str):
                    record["exit_time"] = pd.to_datetime(record["exit_time"])
                    
                if "transaction_end_time" in record and isinstance(record["transaction_end_time"], str):
                    record["transaction_end_time"] = pd.to_datetime(record["transaction_end_time"])
                
                if "bay_reassignment_time" in record and isinstance(record["bay_reassignment_time"], str):
                    record["bay_reassignment_time"] = pd.to_datetime(record["bay_reassignment_time"])
                
                if "current_k_factor" in record:
                    try:
                        record["current_k_factor"] = round(float(record["current_k_factor"]), 2) if record["current_k_factor"] else None
                    except (ValueError, TypeError):
                        record["current_k_factor"] = None  # Handle invalid values

                if "current_meter_factor" in record:
                    try:
                        record["current_meter_factor"] = round(float(record["current_meter_factor"]), 2) if record["current_meter_factor"] else None
                    except (ValueError, TypeError):
                        record["current_meter_factor"] = None  # Handle invalid values

        if not isinstance(sample_records, pl.DataFrame):
            sample_records = pl.DataFrame(sample_records)

        # Group data by SAP ID
        data_by_sap_id = {}
        for record in sample_records.to_dicts():
            sap_id = record.get('sap_id', '1128')
            if sap_id not in data_by_sap_id:
                data_by_sap_id[sap_id] = []
            data_by_sap_id[sap_id].append(record)

        # Check if the model exists in hpcl_ceg_model
        model = getattr(hpcl_ceg_model, table_name, None)
        if model is None:
            raise ValueError(f"Model '{table_name}' not found in hpcl_ceg_model.")

        table_db_name = getattr(model, '__tablename__', table_name)
        
        # Process data for each SAP ID
        for sap_id, sap_id_data in data_by_sap_id.items():
            processed_data = sap_id_data

            # Specific processing for different table types
            if table_db_name == 'host_unauthorised_flow':
                processed_data = [x for x in processed_data if x['nettotalizer'] > 0]
            
            # if table_db_name == 'host_manual_fan_printed':
            #     # Step 1: Check if we need to process EOD record
            #     current_hour = urdhva_base.utilities.get_present_time().strftime("%H")
            #     current_date = urdhva_base.utilities.get_present_time().strftime("%Y-%m-%d")
            #     is_eod = int(current_hour) == 18
                
            #     # Step 2: Get the latest record for this SAP ID from the database
            #     check_query = f"""SELECT manual_fan_count 
            #         FROM "{table_db_name}" 
            #         WHERE date::DATE = '{current_date}' 
            #         AND sap_id = '{sap_id}' 
            #         ORDER BY date_time DESC
            #     """
            #     latest_record_resp = await urdhva_base.BasePostgresModel.get_aggr_data(check_query)
                
            #     # Step 3: Process the current data
            #     filtered_data = []  # Use a different variable name here
                
            #     for record in sap_id_data:  # Use the original sap_id_data here
            #         current_manual_count = record.get('manual_fan_count', 0)
                    
            #         # Determine if we should insert this record
            #         insert_record = False
                    
            #         # Case 1: Record has non-zero manual count
            #         if current_manual_count > 0:
            #             # Check if manual count changed from the last record
            #             if not latest_record_resp.get("data") or current_manual_count != latest_record_resp.get("data")[0].get("manual_fan_count"):
            #                 insert_record = True
                    
            #         # Case 2: EOD record with zero manual count (only if no non-zero records exist for the day)
            #         elif is_eod:
            #             # Check if we have any non-zero records for today
            #             zero_check_query = f"""SELECT COUNT(*) 
            #                 FROM "{table_db_name}" 
            #                 WHERE date::DATE = '{current_date}' 
            #                 AND sap_id = '{sap_id}' 
            #                 AND manual_fan_count > 0
            #             """
            #             zero_check_resp = await urdhva_base.BasePostgresModel.get_aggr_data(zero_check_query)
                        
            #             if zero_check_resp.get("data") and zero_check_resp.get("data")[0].get("count", 0) == 0:
            #                 # No non-zero records for today, insert the last zero record
            #                 # Find the latest zero record from original data
            #                 zero_records = [x for x in sap_id_data if x.get('manual_fan_count', 0) == 0]
            #                 if zero_records:
            #                     # Sort by date_time and get the latest
            #                     zero_records.sort(key=lambda x: x.get('date_time', ''), reverse=True)
            #                     insert_record = True
            #                     record = zero_records[0]  # Use the latest zero record
                    
            #         if insert_record:
            #             filtered_data.append(record)
                
            #     # After processing, update processed_data with our filtered results
            #     processed_data = filtered_data

            if table_db_name == 'host_manual_fan_printed':
                # Step 1: Check the current time
                current_time = urdhva_base.utilities.get_present_time()
                current_date = current_time.strftime("%Y-%m-%d")
                
                # Step 2: Get the latest record for this SAP ID from the database
                check_query = f"""SELECT manual_fan_count, auto_fan_count, total_count, date_time
                    FROM "{table_db_name}" 
                    WHERE date::DATE = '{current_date}' 
                    AND sap_id = '{sap_id}' 
                    ORDER BY date_time DESC
                """
                latest_record_resp = await urdhva_base.BasePostgresModel.get_aggr_data(check_query)
                
                # Step 3: Process the current data
                filtered_data = []
                
                # Handle the case where no data is available in sap_id_data (data might have been removed)
                if not sap_id_data:
                    # If we have previous records, insert a record indicating data removal
                    if latest_record_resp.get("data"):
                        # Create a "data removed" record based on the latest record
                        latest_record = latest_record_resp.get("data")[0]
                        removal_record = {
                            'manual_fan_count': 0,
                            'auto_fan_count': 0,
                            'total_count': 0,
                            'sap_id': sap_id,
                            'date': current_date,
                            'date_time': current_time.isoformat(),
                            'location_name': latest_record.get('location_name', 'UNKNOWN'),
                            'zone': latest_record.get('zone', 'UNKNOWN'),
                            'data_removed': True  # Add a flag to indicate data was removed
                        }
                        filtered_data.append(removal_record)
                else:
                    for record in sap_id_data:
                        current_manual_count = record.get('manual_fan_count', 0)
                        current_auto_count = record.get('auto_fan_count', 0)
                        current_total_count = record.get('total_count', 0)
                        
                        # Ensure record has a data_removed flag (set to False)
                        record['data_removed'] = False
                        
                        # Determine if we should insert this record
                        insert_record = False
                        
                        # If no previous record exists, always insert
                        if not latest_record_resp.get("data"):
                            insert_record = True
                        else:
                            latest_record = latest_record_resp.get("data")[0]
                            latest_manual_count = latest_record.get("manual_fan_count", 0)
                            latest_auto_count = latest_record.get("auto_fan_count", 0)
                            latest_total_count = latest_record.get("total_count", 0)
                            latest_time = datetime.fromisoformat(latest_record.get("date_time"))
                            
                            # Case 1: Any of the counts changed
                            if (current_manual_count != latest_manual_count or 
                                current_auto_count != latest_auto_count or 
                                current_total_count != latest_total_count):
                                insert_record = True
                            
                            # Case 2: It's been more than 1 hour since last record (same data but insert periodically)
                            # Convert the datetime strings to datetime objects
                            current_time_obj = datetime.fromisoformat(record.get('date_time'))
                            time_diff = current_time_obj - latest_time
                            
                            # If more than 1 hour has passed, insert record even if data is the same
                            if time_diff.total_seconds() > 3600:  # 3600 seconds = 1 hour
                                insert_record = True
                            
                            # Case 3: Previous record was marked as "data_removed"
                            if latest_record.get("data_removed", False):
                                insert_record = True
                        
                        if insert_record:
                            filtered_data.append(record)
                
                # After processing, update processed_data with our filtered results
                processed_data = filtered_data
                
                # Add logging for debugging purposes
                print(f"Processing {len(processed_data)} records for host_manual_fan_printed for SAP ID {sap_id}")
            # Bulk update for this SAP ID's data
            status, msg = await model.bulk_update(processed_data, upsert=True, upsert_skip_keys=['alert_created'])

            # Alert processing logic remains the same, but with SAP ID specific filtering
            to_date = urdhva_base.utilities.get_present_time().strftime("%Y-%m-%d")
            
            # Common query with SAP ID filter
            query = f"""select * from "{table_db_name}" where alert_created = false and sap_id = '{sap_id}'"""
            
            # Specific modifications for certain table types
            if table_db_name == 'host_manual_fan_printed':
                query = f"""select * from "{table_db_name}" where date::DATE = '{to_date}' and manual_fan_count !=0 and sap_id = '{sap_id}' and alert_created = false order by date_time asc"""
            
            if table_db_name == 'host_unauthorised_flow':
                query = f"""select * from "{table_db_name}" where alert_created = false and sap_id = '{sap_id}' and nettotalizer > 0"""

            resp = await model.get_aggr_data(query)

            # Existing alert processing logic for manual_fan_printed
            # Alert processing logic
            if table_db_name == 'host_manual_fan_printed':
                # Query to get only non-zero manual fan count records that need processing
                query = f"""SELECT * FROM "{table_db_name}" 
                    WHERE date::DATE = '{to_date}' 
                    AND manual_fan_count > 0
                    AND sap_id = '{sap_id}' 
                    AND alert_created = false 
                    ORDER BY date_time ASC
                """
                
                # Process alerts for non-zero records
                if resp.get("data", []):
                    for record in resp.get("data", []):
                        is_close_alert = False
                        interlock_name = config['interlock_name'].get(table_name)
                        severity = config['severity'].get(table_name, "Medium")
                        sop_id = config['sop_id'].get(table_name)
                        device_msg = ""

                        # Calculate alert status
                        result = await self.cal_host_manual_fan_printed([record])
                        
                        if isinstance(result, tuple) and len(result) == 3:
                            is_close_alert, interlock_name, device_msg = result
                        
                        print("device_msg --> ", device_msg)
                        # Prepare alert data
                        alert_data = {
                            'bu': 'TAS',
                            'sop_id': sop_id,
                            'sap_id': record.get('sap_id'),
                            'interlock_name': interlock_name,
                            'severity': severity,
                            'alert_id': str(uuid.uuid1()),
                            'device_name': record.get('bcu_number'),
                            'device_type': 'Gantry',
                            'vehicle_number': record.get('truck_number', ''),
                            'device_msg': device_msg
                        }

                        # Create alert for non-zero records
                        success, msg = await alert_factory.AlertFactory.create_alert(alert_data)
                        
                        # Close alert if needed
                        if is_close_alert:
                            await self.close_created_alert(alert_data=alert_data)
                            
                        # Mark record as processed
                        query = f"UPDATE {table_db_name} SET alert_created = true WHERE id = {record['id']}"
                        await model.update_by_query(query)
                    
                    return {"status": "Table updated and alerts processed for non-zero records"}
                else:
                    return {"status": "No non-zero records to process for alerts"}

            # Alert processing for unauthorized flow
            if table_db_name == 'host_unauthorised_flow':
                unauthorised_records = resp.get("data", [])
                # Compute the total sum of all nettotalizer values
                total_net = sum(float(record.get("nettotalizer", 0)) for record in unauthorised_records if float(record.get("nettotalizer", 0)) != 0)
                # Extract unique BCU numbers
                bcu_numbers = sorted(set(record.get("bcu_number", "") for record in unauthorised_records))

                # Check if unauthorized flow should be triggered based on total_net
                is_close_alert, interlock_name = await self.cal_unauthorized_flow(total_net)

                # Construct device message
                device_msg = f"BCU Numbers: {', '.join(bcu_numbers)}, Total Net Totalizer: {total_net}"

                # Create and close the alert if needed
                if unauthorised_records and is_close_alert:
                    # Use the first record for necessary data
                    first_record = unauthorised_records[0]
                    alert_data = {
                        'bu': 'TAS',
                        'sop_id': config['sop_id'].get(table_name),
                        'sap_id': first_record.get('sap_id'),
                        'interlock_name': interlock_name,
                        'severity': config['severity'].get(table_name, "Medium"),
                        'alert_id': str(uuid.uuid1()),
                        'device_name': ', '.join(bcu_numbers),  # Since we're dealing with multiple BCUs
                        'device_type': 'Gantry',
                        'vehicle_number': '',  # This might need to be populated appropriately
                        'device_msg': device_msg
                    }
                    
                    # Create Alert
                    success, msg = await alert_factory.AlertFactory.create_alert(alert_data)
                    print("msg :", msg)
                    
                    # Close alert if needed
                    if success and is_close_alert:
                        await self.close_created_alert(alert_data=alert_data)
                        
                    # Update all records as alert_created = true
                    for record in unauthorised_records:
                        query = f"update {table_db_name} set alert_created = true where id = {record['id']}"
                        await model.update_by_query(query)
                        
                    return {"status": "Unauthorized flow alerts processed"}

            # Existing alert processing for other table types
            if resp.get("data", []):
                for record in resp.get("data", []):
                    try:
                        # Fetch config based on table name
                        is_close_alert = False
                        interlock_name = config['interlock_name'].get(table_name)
                        severity = config['severity'].get(table_name, "Medium")
                        sop_id = config['sop_id'].get(table_name)
                        device_msg = ""
                        if interlock_name == 'Cancel TT Reported':
                            device_msg = f"For Compartment_Number: {record.get('compartment_number', '')}".strip()
                        
                        elif interlock_name == 'Bay reasignment':
                            device_msg = f"For Load Number: {record.get('load_number', '')} the ReAssigned Bay: {record.get('reassigned_bay', '')}".strip()

                        # Extract necessary fields from the record
                        alert_data = {
                            'bu': 'TAS',
                            'sop_id': sop_id,
                            'sap_id': record.get('sap_id'),
                            'interlock_name': interlock_name,
                            'severity': severity,
                            'alert_id': str(uuid.uuid1()),
                            'device_name': record.get('bcu_number'),
                            'device_type': 'Gantry',
                            'vehicle_number': record.get('truck_number', ''),
                            'tt_load_number': record.get('load_number', ''),
                            'device_msg': device_msg
                        }

                        # Create Alert
                        if interlock_name == 'Cancel TT Reported':
                            is_close_alert = True
                            success, msg, alert_data = await self.create_cancel_tt_report(alert_data)
                        elif interlock_name == 'Bay reassignment':
                            is_close_alert = True
                            success, msg, alert_data = await self.create_bay_reasignment_report(alert_data)
                        else:
                            success, msg = await alert_factory.AlertFactory.create_alert(alert_data)
                            print("msg :", msg)
                            is_close_alert = True
                            if not success:
                                print(f"Failed to create alert: {msg}")
                                return {"status": False, "message": f"Failed {e}", "data": []}
                        
                        # Set alert_created = true for alert created record
                        query = f"update {table_db_name} set alert_created = true where id = {record['id']}"
                        await model.update_by_query(query)

                        # Close alert
                        if is_close_alert:
                            await self.close_created_alert(alert_data=alert_data)

                    except Exception as e:
                        print(f"Error : {str(e)}")
                        return {"status": False, "message": f"Failed {e}", "data": []}

                return {"status": "Table created and alerts processed"}
            else:
                print("Bulk not posted")
                return {"status": "No data to create alert"}

        return {"status": "Table created and alerts processed for all SAP IDs"}