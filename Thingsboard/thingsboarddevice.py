import pandas as pd
import json
import requests


class ThingsBoardDeviceCreation:
    def __init__(self, excel_file_path, thingsboard_url, username, password):
        """
        Initialize the ThingsBoardDeviceCreation class.

        :param excel_file_path: str, path to the Excel file
        :param thingsboard_url: str, base URL of the ThingsBoard server
        :param username: str, username for authentication
        :param password: str, password for authentication
        """
        self.excel_file_path = excel_file_path
        self.thingsboard_url = thingsboard_url
        self.username = username
        self.password = password
        self.auth_token = None

    def get_auth_token(self):
        """
        Authenticate and retrieve the auth token from ThingsBoard.

        :return: str, the authentication token.
        """
        url = f"{self.thingsboard_url}/api/auth/login"
        headers = {"Content-Type": "application/json"}
        payload = {
            "username": self.username,
            "password": self.password
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            self.auth_token = response.json().get("token")
            print(f"Authentication successful. Token received: {self.auth_token}")
            return self.auth_token
        except requests.RequestException as e:
            print(f"Error authenticating: {e}")
            return None

    def load_excel_data(self):
        """
        Load Excel data and convert it into JSON format.

        :return: List of dictionaries representing Excel rows, or None if an error occurs.
        """
        try:
            df = pd.read_excel(self.excel_file_path)
            return json.loads(df.to_json(orient="records"))
        except Exception as e:
            print(f"Error reading the Excel file: {e}")
            return None

    def create_device(self, device_name):
        """
        Create a device in ThingsBoard.

        :param device_name: str, name of the device to create
        :return: Device ID if successful, None otherwise.
        """
        url = f"{self.thingsboard_url}/api/device"
        headers = {
            "Content-Type": "application/json",
            "X-Authorization": f"Bearer {self.auth_token}"
        }
        payload = {"name": device_name, "type": "default"}  # Adjust the type as needed.

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            device_id = response.json().get("id", {}).get("id")
            print(f"Device '{device_name}' created successfully with ID: {device_id}")
            return device_id
        except requests.RequestException as e:
            print(f"Error creating device '{device_name}': {e}")
            return None

    def set_device_attributes(self, device_id, attributes):
        """
        Set server attributes for a specific device in ThingsBoard.

        :param device_id: str, ID of the device.
        :param attributes: dict, server attributes to set for the device.
        """
        url = f"{self.thingsboard_url}/api/plugins/telemetry/DEVICE/{device_id}/attributes/SERVER_SCOPE"
        headers = {
            "Content-Type": "application/json",
            "X-Authorization": f"Bearer {self.auth_token}"
        }

        try:
            response = requests.post(url, headers=headers, json=attributes)
            response.raise_for_status()
            print(f"Attributes set successfully for device ID: {device_id}")
        except requests.RequestException as e:
            print(f"Error setting attributes for device ID {device_id}: {e}")

    def create_devices_from_excel(self):
        """
        Create devices and set their server attributes based on the Excel file.
        """
        if not self.auth_token:
            print("Authentication token is missing. Fetching the token...")
            if not self.get_auth_token():
                print("Failed to get authentication token. Exiting.")
                return

        data = self.load_excel_data()
        if data is None:
            return

        for row in data:
            device_name = row.get("name")  # Assuming the device name is in the "name" field.
            if not device_name:
                print("Missing 'name' in row, skipping.")
                continue

            # Remove the 'name' field from the attributes and ignore the values, keeping the attribute names only
            attributes = {k: "none" for k, v in row.items() if k != "Unnamed: 0" and k != "name"}

            # Create the device
            device_id = self.create_device(device_name)
            if device_id:
                # Set server attributes (only attribute names, values are ignored)
                self.set_device_attributes(device_id, attributes)



