import pandas as pd
import urdhva_base
import typing
import requests
import hpcl_ceg_model
from geopy.distance import geodesic
import orchestrator.analytics.va_analysis as va_analysis
import orchestrator.alerting.alert_factory as alert_factory
import orchestrator.dbconnector.credential_loader as credential_loader

default_headers = {"Content-Type": "application/json"}

async def get_creds(db_name: str):
    creds = credential_loader.get_credentials(db_name)
    return creds

async def is_vts_enabled(truck_no: str) -> bool:
    """

    Args:
        truck_no: "TN01SS1234"

    Returns:

    """
    creds = await get_creds("VTS")
    url = f"http://{creds['host']}:{creds['port']}/api/TTDetails/VTSEnabled"
    session = requests.Session()
    session.auth = (creds['user'], creds['password'])
    try:
        response = session.post(url, params={"TT_No": truck_no}, headers=default_headers)
        if response.status_code // 100 == 2:
            return response.json()
        return response.json()
    finally:
        session.close()

async def get_tt_current_location(truck_no: str) -> typing.Dict[typing.Any, typing.Any]:
    """

    Args:
        truck_no: "TN01SS1234"

    Returns:

    """
    creds = credential_loader.get_credentials("VTS")
    url = f"http://{creds['host']}:{creds['port']}/api/TTDetails/VTSCurrentLocation"
    session = requests.Session()
    session.auth = (creds['user'], creds['password'])
    try:
        response = session.post(url, params={"TT_No": truck_no}, headers=default_headers)
        if response.status_code // 100 == 2:
            return response.json()
        return response.json()
    finally:
        session.close()

async def get_trucks_available_in_terminal(terminal_plant_id: str) -> typing.List[typing.Any]:
    """

    Args:
        terminal_plant_id: "1234"

    Returns:

    """
    creds = credential_loader.get_credentials("VTS")
    url = f"http://{creds['host']}:{creds['port']}/api/TTDetails/TT_Inside_Depot"
    session = requests.Session()
    session.auth = (creds['user'], creds['password'])
    try:
        response = session.post(url, params={"DEPOT_ERP_CODE": terminal_plant_id}, headers=default_headers)
        if response.status_code // 100 == 2:
            return response.json()
        return response.json()
    finally:
        session.close()

async def get_trucks_returning_to_terminal() -> typing.List[typing.Any]:
    """

    Returns:

    """
    creds = credential_loader.get_credentials("VTS")
    url = f"http://{creds['host']}:{creds['port']}/api/TTDetails/TT_Approching_Depot"
    session = requests.Session()
    session.auth = (creds['user'], creds['password'])
    try:
        response = session.post(url, params={}, headers=default_headers)
        if response.status_code // 100 == 2:
            return response.json()
        return response.json()
    finally:
        session.close()

async def get_all_blocked_tt() -> typing.List[typing.Any]:
    """

    Returns:

    """
    creds = credential_loader.get_credentials("VTS")
    url = f"http://{creds['host']}:{creds['port']}/api/TTDetails/TT_Blocked_List"
    session = requests.Session()
    session.auth = (creds['user'], creds['password'])
    try:
        response = session.get(url, params={}, headers=default_headers)
        if response.status_code // 100 == 2:
            return response.json()
        return response.json()
    finally:
        session.close()

async def get_today_blocked_tt() -> typing.List[typing.Any]:
    """

    Returns:

    """
    creds = credential_loader.get_credentials("VTS")
    url = f"http://{creds['host']}:{creds['port']}/api/TTDetails/TT_Blocked_Today"
    session = requests.Session()
    session.auth = (creds['user'], creds['password'])
    try:
        response = session.get(url, params={}, headers=default_headers)
        if response.status_code // 100 == 2:
            return response.json()
        return response.json()
    finally:
        session.close()

async def get_today_unblocked_tt() -> typing.List[typing.Any]:
    """

    Returns:

    """
    creds = credential_loader.get_credentials("VTS")
    url = f"http://{creds['host']}:{creds['port']}/api/TTDetails/TT_UnBlocked_Today"
    session = requests.Session()
    session.auth = (creds['user'], creds['password'])
    try:
        response = session.get(url, params={}, headers=default_headers)
        if response.status_code // 100 == 2:
            return response.json()
        return response.json()
    finally:
        session.close()

async def post_unblocked_tt(input_data: dict) -> typing.List[typing.Any]:
    """

    Args:
        input_data: {
            "TT_No": "",
            "UnBlockedBy": "",
            "UnBlockedDateTime": "",
            "UnBlockedRemarks": "",
            "ApprovedBy": "",
            "ApprovedDateTime": "",
            "ApprovedRemarks": "",
            "BlockStartDate": "",
            "BlockEndDate": "",
            "WaivedOff": 0/1, # 0 to false (when tt accept violation), 1 - true to go one level instance back if tt provides violation is wrong
            "AlertID": "",
            "DocLink": {
                "DocPaths": ["https://example.com/doc1.pdf"]
            }
        }

    Returns:

    """
    creds = credential_loader.get_credentials("VTS")
    url = f"http://{creds['host']}:{creds['port']}/api/TTDetails/TT_UnBlocked"
    session = requests.Session()
    session.auth = (creds['user'], creds['password'])
    try:
        response = session.post(url, json=input_data, headers=default_headers)
        if response.status_code // 100 == 2:
            return response.json()
        return response.json()
    finally:
        session.close()

async def post_blocked_tt(input_data: dict) -> typing.List[typing.Any]:
    """

    Args:
        input_data: {
            "TT_No": <String>,
            "BlockStartDate": <String>,
            "BlockEndDate": <String>,
            "BlockedRemarks": <String>
        }

    Returns:

    """
    creds = credential_loader.get_credentials("VTS")
    url = f"http://{creds['host']}:{creds['port']}/api/TTDetails/TT_Blocked"
    session = requests.Session()
    session.auth = (creds['user'], creds['password'])
    try:
        response = session.post(url, json=input_data, headers=default_headers)
        if response.status_code // 100 == 2:
            return response.json()
        return response.json()
    finally:
        session.close()

async def get_distance_of_truck(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    # Note: this is straight line route for actual need to use OSRM, google maps
    start_coords = (start_lat, start_lon)
    end_coords = (end_lat, end_lon)
    distance_km = geodesic(start_coords, end_coords).kilometers
    return round(distance_km, 2)

async def create_vts_alert(alert_data: dict):
    # entry['vendor_alert_id'] = entry.pop("alert_id")
    alert_data['device_name'] = alert_data.get('vehicle_blocked_instance_no', '').strip()
    alert_data['device_id'] = alert_data.get('vehicle_blocked_instance_no', '').strip()
    alert_data['alert_type'] = "VTS"
    alert_data['vehicle_number'] = alert_data.pop('tt_no')
    alert_data['violation_type'] = alert_data.pop('vehicle_blocked_instance_type')
    alert_data['sap_id'] = alert_data.pop('location_id')
    alert_data['bu'] = str(alert_data.pop('location_type'))

    cls = alert_factory.AlertFactory()
    return await cls.create_alert(alert_data, urdhva_base.settings.camunda_url)

async def update_alert_id_to_vts_history(alert_id: str, vts_alert_id: list[str]):
    if vts_alert_id:
        if not isinstance(vts_alert_id, list):
            vts_alert_id = [vts_alert_id]

        vts_alert_id = "', '".join(vts_alert_id)
        query = (f"""update vts_alert_history set alert_id='{alert_id}' """
                 f"""where id in ('{vts_alert_id}')""")
        await hpcl_ceg_model.VtsAlertHistory.update_by_query(query)

async def insert_violation_count(file_name):
    df = pd.read_excel(file_name, header=4)
    df1 = pd.read_excel(file_name, sheet_name="Trip Deatils", header=4)

    df = df[[
        "TT Number", "Device Removed Loaded Trip", "Route Deviation Loaded Trip",
        "Speed Violation Loaded Trip", "Stoppage Violation Loaded Trip",
        "Power Disconnected Loaded Trip", "Night Driving Loaded Trip",
        "Route Deviation  & Stoppage Loaded Trip"
    ]]

    df1 = df1[["TT Number", "Actual Trip Start Location"]]
    df1 = df1.drop_duplicates()
    df = pd.merge(
        df, df1, on=["TT Number"], how='left'
    )

    print(df[df['_merge'] != 'both'])

    df = df.to_dict(orient="records")
    for record in df:
        ...

async def get_vts_violation(entry):
    vts_violation = []
    violation_list = [
        "stoppage_violations_count", "route_deviation_count", "speed_violation_count", "main_supply_removal_count",
        "night_driving_count", "no_halt_zone_count", "device_offline_count", "device_tamper_count", "continuous_driving_count"
    ]
    for violation in violation_list:
        if entry.get(violation, 0) > 0:
            vts_violation.append(violation)
    return vts_violation

async def get_vts_instance(tt_number: str):
    start_date, end_date = va_analysis.get_period_datetime(period='fortnight')
    start_date = start_date.strftime("%Y-%m-%d")
    end_date = end_date.strftime("%Y-%m-%d")
    query = (f"select * from vts_alert_history where tl_number = '{tt_number}'"
             f"and vts_end_datetime::date between '{start_date}' and '{end_date}'")
    vts_alert_data = await hpcl_ceg_model.VtsTruckDetails.get_aggr_data(query, limit=0)
    if not vts_alert_data:
        return False
    vts_alert_data = vts_alert_data.get("data", [])[0]


# Priority

# device_tamper_count
# main_supply_removal_count
# route_deviation_count
# stoppage_violations_count
# speed_violation_count
# night_driving_count
