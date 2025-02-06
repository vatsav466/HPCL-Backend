import urdhva_base
import typing
import requests
from geopy.distance import geodesic
import orchestrator.dbconnector.credential_loader as credential_loader

default_headers = {"Content-Type": "application/json"}

async def get_creds(db_name: str):
    creds = credential_loader.get_credentials(db_name)
    return creds

async def is_vts_enabled(truck_no: str) -> bool:
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

async def get_unblocked_tt() -> typing.List[typing.Any]:
    creds = credential_loader.get_credentials("VTS")
    url = f"http://{creds['host']}:{creds['port']}/api/TTDetails/TT_UnBlocked"
    session = requests.Session()
    session.auth = (creds['user'], creds['password'])
    try:
        response = session.post(url, params={}, headers=default_headers)
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