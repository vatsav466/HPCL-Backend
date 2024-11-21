import json
import requests

# ThingsBoard API URL (replace placeholder with your actual server URL)
THINGSBOARD_URL = "http://140.245.238.142:8080"

def load_site_data(site_id):
    """
    Loads site data from a JSON file.
    """
    try:
        file_name = f"{site_id}.json"  # JSON file name derived from site_id
        with open(file_name, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"File {site_id}.json not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {site_id}.json")
        return None


def post_telemetry(device_key, sensor_type, tag_value):
    """
    Sends telemetry data to ThingsBoard for a specific device.
    """
    telemetry_data = {
        sensor_type:tag_value
    }
    url = f"{THINGSBOARD_URL}/api/v1/{device_key}/telemetry"  # Using deviceKey as the token
    
    try:
        response = requests.post(url, json=telemetry_data)
        if response.status_code == 200:
            print(f"Telemetry sent successfully for DeviceKey: {device_key}, SensorType: {sensor_type}")
        else:
            print(f"Failed to send telemetry for DeviceKey: {device_key}, SensorType: {sensor_type}")
            print(f"Response: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        print(f"Error sending telemetry: {e}")


def send_telemetry_for_all(site_id, tag_value):
    """
    Sends telemetry for all components and sensors in a site.
    """
    site_data = load_site_data(site_id)
    if not site_data:
        print(f"No data found for site ID: {site_id}")
        return

    for component in site_data.get("components", []):
        device_key = component.get("deviceKey")
        if not device_key:
            print(f"Device key missing in component: {component}")
            continue

        print(f"Processing device key: {device_key}")
        for sensor in component.get("entitySensors", []):
            tag_path = sensor.get("TagPath")
            if not tag_path:
                print(f"TagPath missing in sensor: {sensor}")
                continue
            
            print(f"Processing TagPath: {tag_path}")
            post_telemetry(device_key, sensor.get("sensorType"), tag_value)


# Example Usage
site_id = "1234"
tag_value = "false"  # Replace with the actual value you want to send
send_telemetry_for_all(site_id, tag_value)
