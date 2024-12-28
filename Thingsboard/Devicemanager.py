import pandas as pd
import aiohttp  
from api_manager import dnc_schema_model  

class DeviceManager:
    def __init__(self, thingsboard_url, username, password):
        self.thingsboard_url = thingsboard_url
        self.username = username
        self.password = password
        self.token = None  # Will be fetched asynchronously

    async def get_access_token(self):
        login_url = f"{self.thingsboard_url}/api/auth/login"
        async with aiohttp.ClientSession() as session:
            async with session.post(login_url, json={"username": self.username, "password": self.password}) as response:
                if response.status == 200:
                    self.token = (await response.json()).get("token")
                    print("Access token acquired.")
                else:
                    raise Exception(f"Failed to authenticate: {response.status} - {await response.text()}")

    async def create_device_in_thingsboard(self, device_data):
        headers = {
            "Content-Type": "application/json",
            "X-Authorization": f"Bearer {self.token}"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.thingsboard_url}/api/device",
                headers=headers,
                json=device_data
            ) as response:
                if response.status == 200:
                    return True, await response.json()
                else:
                    print(f"Failed to create device in ThingsBoard: {await response.text()}")
                    return False, None

    async def set_server_attributes(self, device_id, server_attr_key, server_attr_value):
        headers = {
            "Content-Type": "application/json",
            "X-Authorization": f"Bearer {self.token}"
        }
        attributes = {server_attr_key: server_attr_value}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.thingsboard_url}/api/plugins/telemetry/DEVICE/{device_id}/SERVER_SCOPE",
                headers=headers,
                json=attributes
            ) as response:
                if response.status == 200:
                    print(f"Server attribute '{server_attr_key}' set for device ID {device_id}.")
                else:
                    print(f"Failed to set server attribute for device ID {device_id}: {await response.text()}")

    async def store_device_in_database(self, device_id,device_data):
        
        location_device = dnc_schema_model.LocationDeviceCreate(**{**device_data, "device_id":device_id})
        await location_device.create()  
        print(f"Device {device_data['name']} stored in the database.")

    async def process_csv(self, file_path):
        try:
            df = pd.read_csv(file_path)
            print("CSV data loaded successfully:")

            if df.empty:
                print("The CSV file is empty.")
                return

            expected_columns = ['name', 'type', 'BU', 'additional_info_key', 'additional_info_value', 
                                'location_name', 'location_id', 'server_attr_key', 'server_attr_value']
            
            missing_columns = [col for col in expected_columns if col not in df.columns]
            if missing_columns:
                print(f"Missing columns in CSV: {missing_columns}")
                return

            for _, row in df.iterrows():
                device_data = {
                    "name": row['name'],
                    "type": row['type'],
                    "BU": row['BU'],
                    "additional_info_key": row['additional_info_key'],
                    "additional_info_value": row['additional_info_value'],
                    "location_name": row['location_name'],
                    "location_id": row['location_id'],
                    "server_attr_key": row['server_attr_key'],
                    "server_attr_value": row['server_attr_value']
                }

                tb_device_data = {
                    "name": device_data["name"],
                    "type": device_data["type"],
                    "additionalInfo": {
                        device_data["additional_info_key"]: device_data["additional_info_value"],
                        "BU": device_data["BU"],
                        "plantlocation": device_data["location_name"],
                        "plantlocationid": device_data["location_id"]
                    }
                }

                status, tb_response = await self.create_device_in_thingsboard(tb_device_data)
                if status:
                    device_id = tb_response["id"]["id"]  
                    await self.set_server_attributes(device_id, device_data["server_attr_key"], device_data["server_attr_value"])
                    await self.store_device_in_database(device_id,device_data)  
                else:
                    print(f"Failed to create device: {device_data['name']}")

        except pd.errors.EmptyDataError:
            print("The CSV file appears to be empty. Please provide a valid file.")
        except FileNotFoundError:
            print(f"File not found at path: {file_path}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

import asyncio

if __name__ == "__main__":
    THINGSBOARD_URL = "http://localhost:8081"
    USERNAME = "tenant@thingsboard.org"
    PASSWORD = "tenant"

    async def main():
        device_manager = DeviceManager(THINGSBOARD_URL, USERNAME, PASSWORD)
        await device_manager.get_access_token()
        csv_file_path = "/Users/manohar/Documents/Thingsboard Works/devicedata2.csv"  
        await device_manager.process_csv(csv_file_path)

    asyncio.run(main())
