import urdhva_base
import traceback
import hpcl_ceg_model
import sys
sys.path.append("/opt/ceg/algo/orchestrator")
from datetime import datetime, timedelta

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")

class TasUpdateProofTest:

    async def get_required_variables(self):
        return ["alert_id"]
    
    async def check_proof_test(self, params):
        """
        Check and update the proof test data in the tas_proof_test table.
        If the data already exists, update the proof_test_created_at and next_proof_test_date.
        Otherwise, insert a new record.
        """
        try:
            # Get the alert data
            alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__

            # Extracting required parameters from alert data
            interlock_name = alert_data.get('interlock_name')
            equipment_name = alert_data.get('tas_device_name') or alert_data.get('device_name')
            device_id = alert_data.get('device_id')
            created_at = alert_data.get('created_at')
            sap_id = alert_data.get('sap_id')

            if not (interlock_name and equipment_name and sap_id and created_at):
                print("Missing required fields")

            # Convert created_at to a datetime object
            created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")

            # Calculate the next proof test date (90 days from created_at)
            next_proof_test_date = created_at + timedelta(days=90)

            # Check if the record already exists in the tas_proof_test table
            interlock_names = ["Proof Test_VFT_Success", "Proof Test_Secondary Radar Guage_Success"]

            for interlock_name in interlock_names:
                #check if the record already exists in the tas_proof_test table
                query = f"""
                    SELECT * FROM tas_proof_test
                    WHERE device_name = '{equipment_name}' AND sap_id = '{sap_id}' AND device_id = '{device_id}' AND interlock_name = '{interlock_name}'
                """
                existing_record = await hpcl_ceg_model.TasProofTest.get_aggr_data(query)

            if existing_record.get("data", []):
                existing_record["proof_test_created_at"] = created_at.strftime("%Y-%m-%d %H:%M:%S")
                existing_record["next_proof_test_date"] = next_proof_test_date.strftime("%Y-%m-%d %H:%M:%S")
                data_obj = hpcl_ceg_model.TasProofTest(**existing_record)
                await data_obj.modify()
                # Update the existing record
                # update_query = f"""
                #     UPDATE tas_proof_test
                #     SET proof_test_created_at = '{created_at.strftime("%Y-%m-%d %H:%M:%S")}',
                #         next_proof_test_date = '{next_proof_test_date.strftime("%Y-%m-%d %H:%M:%S")}'
                #     WHERE device_name = '{equipment_name}' AND sap_id = '{sap_id} AND device_id = '{device_id} AND interlock_name = '{interlock_name}'
                # """
                # call update query query execute function for tas_proof_test
                # await hpcl_ceg_model.TasProofTest.update_by_query(update_query)
                print(f"Updated proof test record for device: {equipment_name}, SAP ID: {sap_id}")
                return True , {"message": "Moved to next block"}
            else:
                data = {
                    "interlock_name": interlock_name,
                    "equipment_name": equipment_name,
                    "device_id": device_id,
                    "sap_id": sap_id,
                    "proof_test_created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "next_proof_test_date": next_proof_test_date
                }
                await hpcl_ceg_model.TasProofTestCreate(**data).create()

                # # Insert a new record
                # insert_query = f"""
                #     INSERT INTO tas_proof_test (device_name, device_id, sap_id, interlock_name, proof_test_created_at, next_proof_test_date)
                #     VALUES ('{equipment_name}', {device_id}, '{sap_id}', {interlock_name}, '{created_at.strftime("%Y-%m-%d %H:%M:%S")}', '{next_proof_test_date.strftime("%Y-%m-%d %H:%M:%S")}')
                # """
                # # call insert query  execute function for tas_proof_test
                # print(f"Inserted new proof test record for device: {equipment_name}, SAP ID: {sap_id}")
                return True, { "message": "Moved to next block"}

        except Exception as e:
            logger.error(f"Error in check_proof_test: {traceback.format_exc()}")
            print(f"Error in check_proof_test: {traceback.format_exc()}")
            return  False,  {"message": "An error occurred while processing the proof test"}