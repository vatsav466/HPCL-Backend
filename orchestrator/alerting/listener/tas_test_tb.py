import requests
import json

# ThingsBoard API endpoint
base_url = "http://140.245.238.142:8081"

# List of devices with their access tokens and telemetry data
devices = [
    {
        "access_token": "I4QVDgQsfTdTTJYog36A",  # Device 1 access token
        "data": {
            "LEVEL SWITCH MAINTENANCE": "0",
            "RIM SEAL MAINTENANCE STATUS": "0",
            "TANK MAINTENANCE": "0",
            "MOV MAINTENANCE IL1": "0",
            "ROSOV MAINTENANCE IL1": "0",
            "RADAR MAINTENANCE": "0",
            # "ROSOV FAIL TO CLOSE STATUS IL2": "0",
            # "ROSOV FAIL TO CLOSE STATUS RCL": "0",
            # "ROSOV OPEN STATUS IL2": "0",
            # "ROSOV OPEN STATUS RCL": "0"

        }
    },
    {
        "access_token": "9hMtwlhNEKO1paQt1EEM",  # Device 1 access token
        "data": {
            "LEVEL SWITCH MAINTENANCE": "0",
            "RIM SEAL MAINTENANCE STATUS": "0",
            "TANK MAINTENANCE": "0",
            "MOV MAINTENANCE IL1": "0",
            "ROSOV MAINTENANCE IL1": "0",
            "RADAR MAINTENANCE": "0"
            # "ROSOV FAIL TO CLOSE STATUS IL2": "0",
            # "ROSOV FAIL TO CLOSE STATUS RCL": "0",
            # "ROSOV OPEN STATUS IL2": "0",
            # "ROSOV OPEN STATUS RCL": "0"
        }
    },
    # {
    #     "access_token": "reu7nCMXH9ionmZwveEs",  # Device 2 access token
    #     "data": {
    #         "ESD MAINTENANCE STATUS": "1",
            
    #     }
    # },
    # {
    #     "access_token": "AnotherDeviceToken123",  # Device 3 access token
    #     "data": {
    #         "SENSOR1 STATUS": "ON",
    #         "SENSOR2 STATUS": "OFF",
    #         "TEMPERATURE": 25.6,
    #         "HUMIDITY": 65
    #     }
    # }
]

# Prepare headers
headers = {
    "Content-Type": "application/json"
}

# Iterate over the devices and send telemetry data
for device in devices:
    access_token = device["access_token"]
    data = device["data"]

    # Send telemetry request
    response = requests.post(f"{base_url}/api/v1/{access_token}/telemetry", json=data, headers=headers, verify=False)

    if response.status_code == 200:
        print(f"Telemetry data sent successfully for device with access token: {access_token}")
    else:
        print(f"Failed to send telemetry data for device with access token: {access_token}. "
              f"Status code: {response.status_code}, Response: {response.text}")