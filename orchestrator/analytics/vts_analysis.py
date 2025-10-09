import urdhva_base
import pandas as pd
import typing
import json
import httpx
import aiohttp
import asyncio
import requests
import datetime
import hpcl_ceg_model
import hpcl_ceg_enum
from collections import Counter
from geopy.distance import geodesic
import utilities.helpers as helpers
import utilities.vts_mapping as vts_mapping
import utilities.interlock_mapping as interlock_mapping
import orchestrator.alerting.alert_helper as alert_helper
import utilities.vts_instance_mapping as vts_instance_mapping
from orchestrator.workflow.workflow_process import Camunda
import orchestrator.analytics.va_analysis as va_analysis
import orchestrator.alerting.alert_manager as alert_manager
import orchestrator.alerting.alert_factory as alert_factory
import orchestrator.dbconnector.credential_loader as credential_loader
import utilities.role_configuration as vts_role_mapping
import cache_gateway.cache_api_actions as cache_api_actions

logger = urdhva_base.logger.Logger.getInstance('vts_alert_log')

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

async def post_blocked_tt_ims(input_data: typing.List[typing.Dict[str, typing.Any]]) -> typing.List[typing.Any]:
    """
    Args:
        input_data: List of dicts, e.g.:
        [
            {
               "transactNo" : "1234567899",
               "truckRegNo" : "KA01AJ4588",
               "blockingFlag" : "Y",
               "blockingFrom" : "20231225",
               "blockingTo" : "20240112"
            }
        ]

    Returns:
        The response JSON parsed as a list. If the response is a single dict,
        it is wrapped in a list.
    """
    url = urdhva_base.settings.post_to_ims_url
    session = requests.Session()
    try:
        response = session.post(url, json=input_data, headers=default_headers)
        if response.status_code // 100 == 2:
            logger.info(f"Data successfully posted to IMS {response.json()}")
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

async def insert_truck_details(data):
    data = pd.DataFrame(data)
    data.rename(columns={"LOCATION_CODE": "sap_id"}, inplace=True)
    data.columns = data.columns.str.lower()
    data['instance_1'] = data['instance_1'].fillna(0)
    data['instance_2'] = data['instance_2'].fillna(0)
    data['instance_3'] = data['instance_3'].fillna(0)
    if not 'bu' in data.columns:
        data['bu'] = ""
    data = data.fillna("")
    await hpcl_ceg_model.VtsTruckDetails.bulk_update(data.to_dict(orient="records"), upsert=True)


async def get_instance(tt_number: str, sap_id: str, bu: str, get_raw_data=False):
    query = f"select * from vts_truck_details where truck_regno = '{tt_number}'"
    vts_truck_data = await hpcl_ceg_model.VtsTruckDetails.get_aggr_data(query, limit=0)
    if get_raw_data:
        return vts_truck_data.get("data", [])
    if not vts_truck_data.get("data", []):
        vts_truck_record = {
            "truck_regno": tt_number,
            "sap_id": sap_id,
            "bu": bu,
            "truck_status": "UNBLOCKED", 
            "violation_type": "",
            "block_start_datetime": None,
            "block_end_datetime": None, 
            "instance_1": 0, 
            "instance_2": 0,
            "instance_3": 0,
            "alert_id": "",
            "blacklist": False,
            "truck_history": []
        }
        #print("vts_truck_record",vts_truck_record)
        await hpcl_ceg_model.VtsTruckDetailsCreate(**vts_truck_record).create()
        return "0"
    vts_truck_data = vts_truck_data.get("data", [])[0]
    print(vts_truck_data)
    if not vts_truck_data['instance_1']:
        return "0"
    if not vts_truck_data['instance_2']:
        return "1"
    return "2"

async def is_vehicle_blacklisted(tl_number: str):
    black_list_query = f"select * from vts_truck_details where truck_regno = '{tl_number}' and blacklist='true'"
    vts_blacklist_data = await hpcl_ceg_model.VtsTruckDetails.get_aggr_data(black_list_query, limit=0)
    if vts_blacklist_data.get("data", []):
        return True
    return False

async def is_alert_exists(tl_number: str):
    query = f"select id from alerts where vehicle_number = '{tl_number}' and alert_status != 'Close' and alert_section = 'VTS'"
    print("query: ", query)
    vts_alert_data = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=0)
    print("vts_alert_data: ", vts_alert_data)
    if vts_alert_data.get("data", []):
        return True
    return False

async def last_closed_at(tt_number: str):
    query = f"vehicle_number = '{tt_number}' and alert_status = 'Close' and alert_section = 'VTS'"
    print("query: ", query)
    vts_alert_data = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query,limit=5),resp_type='plain')
    #print("vts_alert_data: ", vts_alert_data)
    if len(vts_alert_data['data']):
        return vts_alert_data['data'][0]['closed_at']
    return None

async def is_vehicle_blacklisted_in_alerts(tl_number, sap_id, bu):
    query = (f"vehicle_number = '{tl_number}' and bu = '{bu}' and alert_section = 'VTS' and "
            f"violation_type in ('device_tamper_count','main_supply_removal_count')")
    vts_alert_data = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query,limit=5),resp_type='plain')
    if len(vts_alert_data['data']):
        query = (f"update vts_truck_details set blacklist='true' "
                 f"where truck_regno = '{tl_number}'")
        await hpcl_ceg_model.VtsTruckDetails.update_by_query(query)
        return True
    return False

async def last_opened_at(tt_number: str):
    query = f"vehicle_number = '{tt_number}' and alert_status != 'Close' and alert_section = 'VTS'"
    print("query: ", query)
    vts_alert_data = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query,limit=5),resp_type='plain')
    #print("vts_alert_data: ", vts_alert_data)
    if len(vts_alert_data['data']):
        alert_history = list(reversed(vts_alert_data['data'][0]['alert_history']))
        created_at = vts_alert_data['data'][0]['created_at']
        for record in alert_history:
            action_msg = record.get("action_msg", "")
            if action_msg.startswith("Instance Updated for this Vehicle Number:"):
                created_at = datetime.datetime.fromisoformat(record.get("processed_time"))
                #print("First processed_time:", created_at)
                break
        return created_at, vts_alert_data['data'][0]['id']
    return None, None

async def get_updated_vts_instance(tt_number: str, sap_id: str, bu: str):
    vts_map = vts_mapping.vts_interlock_mapping
    instance_mapping = vts_instance_mapping.instance_mapping
    start_date, end_date = await va_analysis.get_period_datetime(period='fortnight')
    start_date = start_date.strftime("%Y-%m-%d")
    end_date = end_date.strftime("%Y-%m-%d")
    vts_opened_alert_data, alert_id = await last_opened_at(tt_number)
    vts_alert_data = []
    if vts_opened_alert_data:
        last_updated_at_ist = vts_opened_alert_data + datetime.timedelta(hours=5, minutes=30)
        start_date_ = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_ = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        if start_date_ <= last_updated_at_ist.date() <= end_date_:
            query = (f"select DISTINCT ON (tl_number, invoice_number) violation_type, id from vts_alert_history where tl_number = '{tt_number}' "
                    f"and vts_end_datetime::date between '{start_date}' and '{end_date}' and created_at > '{vts_opened_alert_data}'")
            vts_alert_data = await hpcl_ceg_model.VtsAlertHistory.get_aggr_data(query, limit=0)
        else:
            query = (f"select DISTINCT ON (tl_number, invoice_number) violation_type, id from vts_alert_history where tl_number = '{tt_number}' "
                    f"and vts_end_datetime::date between '{start_date}' and '{end_date}'")
            vts_alert_data = await hpcl_ceg_model.VtsAlertHistory.get_aggr_data(query, limit=0)
    else:
        query = (f"select DISTINCT ON (tl_number, invoice_number) violation_type, id from vts_alert_history where tl_number = '{tt_number}' "
                f"and vts_end_datetime::date between '{start_date}' and '{end_date}'")
        vts_alert_data = await hpcl_ceg_model.VtsAlertHistory.get_aggr_data(query, limit=0)
    if not vts_alert_data:
        return False
    vts_alert_data = vts_alert_data.get("data", [])
    print("vts_alert_data: ", vts_alert_data)
    all_violations = [violation for d in vts_alert_data for violation in d["violation_type"]]
    violations_ids = [str(d["id"]) for d in vts_alert_data]
    violation_counts = dict(Counter(all_violations))
    instance = {}
    violation_name = ""
    current_instance = await get_instance(tt_number,sap_id,bu)
    instance_data = instance_mapping[bu].get(current_instance,{})
    for key, violation_data in instance_data.items():
        if key in violation_counts.keys() and violation_counts[key] > violation_data['violation_count']:
            if key in ['device_tamper_count', 'main_supply_removal_count']:
                await is_vehicle_blacklisted_in_alerts(tt_number,sap_id,bu)
            instance = vts_map[key]['alerting_rules'][current_instance]
            instance['severity'] = vts_map[key]["severity"]
            violation_name = key
    return instance, violation_name, violations_ids, alert_id

async def get_vts_instance(tt_number: str, sap_id: str, bu: str):
    vts_map = vts_mapping.vts_interlock_mapping
    instance_mapping = vts_instance_mapping.instance_mapping
    start_date, end_date = await va_analysis.get_period_datetime(period='fortnight')
    start_date = start_date.strftime("%Y-%m-%d")
    end_date = end_date.strftime("%Y-%m-%d")
    vts_closed_alert_data = await last_closed_at(tt_number)
    vts_alert_data = []
    if vts_closed_alert_data:
        last_updated_at_ist = vts_closed_alert_data + datetime.timedelta(hours=5, minutes=30)
        start_date_ = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_ = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        if start_date_ <= last_updated_at_ist.date() <= end_date_:
            query = (f"select DISTINCT ON (tl_number, invoice_number) violation_type, id from vts_alert_history where tl_number = '{tt_number}' "
                    f"and vts_end_datetime::date between '{start_date}' and '{end_date}' and created_at > '{vts_closed_alert_data}'")
            vts_alert_data = await hpcl_ceg_model.VtsAlertHistory.get_aggr_data(query, limit=0)
        else:
            query = (f"select DISTINCT ON (tl_number, invoice_number) violation_type, id from vts_alert_history where tl_number = '{tt_number}' "
                    f"and vts_end_datetime::date between '{start_date}' and '{end_date}'")
            vts_alert_data = await hpcl_ceg_model.VtsAlertHistory.get_aggr_data(query, limit=0)
    else:
        query = (f"select DISTINCT ON (tl_number, invoice_number) violation_type, id from vts_alert_history where tl_number = '{tt_number}' "
                f"and vts_end_datetime::date between '{start_date}' and '{end_date}'")
        vts_alert_data = await hpcl_ceg_model.VtsAlertHistory.get_aggr_data(query, limit=0)
    if not vts_alert_data:
        return False
    vts_alert_data = vts_alert_data.get("data", [])
    print("vts_alert_data: ", vts_alert_data)
    all_violations = [violation for d in vts_alert_data for violation in d["violation_type"]]
    violations_ids = [str(d["id"]) for d in vts_alert_data]
    violation_counts = dict(Counter(all_violations))
    instance = {}
    violation_name = ""
    current_instance = await get_instance(tt_number,sap_id,bu)
    instance_data = instance_mapping[bu].get(current_instance,{})
    for key, violation_data in instance_data.items():
        if key in violation_counts.keys() and violation_counts[key] > violation_data['violation_count']:
            if key in ['device_tamper_count', 'main_supply_removal_count']:
                await is_vehicle_blacklisted_in_alerts(tt_number,sap_id,bu)
            instance = vts_map[key]['alerting_rules'][current_instance]
            instance['severity'] = vts_map[key]["severity"]
            violation_name = key
    # if "device_tamper_count" in violation_counts.keys() and violation_counts['device_tamper_count'] > 1:
    #     instance = vts_map["device_tamper_count"]['alerting_rules'][await get_instance(tt_number,sap_id,bu)]
    #     instance['severity'] = vts_map["device_tamper_count"]["severity"]
    #     violation_name = "device_tamper_count"

    # elif "main_supply_removal_count" in violation_counts.keys() and violation_counts['main_supply_removal_count'] > 1:
    #     instance = vts_map["main_supply_removal_count"]['alerting_rules'][await get_instance(tt_number,sap_id,bu)]
    #     instance['severity'] = vts_map["main_supply_removal_count"]["severity"]
    #     violation_name = "main_supply_removal_count"

    # elif "route_deviation_count" in violation_counts.keys() and violation_counts['route_deviation_count'] > 5:
    #     instance = vts_map["route_deviation_count"]['alerting_rules'][await get_instance(tt_number,sap_id,bu)]
    #     instance['severity'] = vts_map["route_deviation_count"]["severity"]
    #     violation_name = "route_deviation_count"

    # elif "stoppage_violations_count" in violation_counts.keys() and violation_counts['stoppage_violations_count'] > 5:
    #     instance = vts_map["stoppage_violations_count"]['alerting_rules'][await get_instance(tt_number,sap_id,bu)]
    #     instance['severity'] = vts_map["stoppage_violations_count"]["severity"]
    #     violation_name = "stoppage_violations_count"

    # elif "speed_violation_count" in violation_counts.keys() and violation_counts['speed_violation_count'] > 3:
    #     instance = vts_map["speed_violation_count"]['alerting_rules'][await get_instance(tt_number,sap_id,bu)]
    #     instance['severity'] = vts_map["speed_violation_count"]["severity"]
    #     violation_name = "speed_violation_count"

    # elif "night_driving_count" in violation_counts.keys() and violation_counts['night_driving_count'] > 3:
    #     instance = vts_map["night_driving_count"]['alerting_rules'][await get_instance(tt_number,sap_id,bu)]
    #     instance['severity'] = vts_map["night_driving_count"]["severity"]
    #     violation_name = "night_driving_count"

    # elif "continuous_driving_count" in violation_counts.keys() and violation_counts['continuous_driving_count'] > 3:
    #     instance = vts_map["continuous_driving_count"]['alerting_rules'][await get_instance(tt_number,sap_id,bu)]
    #     instance['severity'] = vts_map["continuous_driving_count"]["severity"]
    #     violation_name = "continuous_driving_count"

    return instance, violation_name, violations_ids

async def update_vts_instance(alert_data):
    vts_end_datetime = alert_data.get('vts_end_datetime',None)
    instance_data, violation_name, vts_alert_history_ids, alert_id = await get_updated_vts_instance(alert_data['tl_number'],alert_data['location_id'],alert_data['location_type'])
    if not instance_data:
        logger.info(f"No Max Violation for TT {alert_data['tl_number']}")
        return
    alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
    if not isinstance(alert_data, dict):
        alert_data = alert_data.__dict__
    if "_sa_instance_state" in alert_data.keys():
        del alert_data["_sa_instance_state"]

    alert_message = (
        f"Instance Updated for this Vehicle Number: {alert_data['vehicle_number']} from {alert_data['device_id']} to {instance_data['instance']} with violation {violation_name}"
        )    
    alert_data["action_msg"] = alert_message
    alert_data["action_type"] = "Blocked"
    await alert_manager.AlertAction().update_alert_history(input_data=alert_data, alert_data=alert_data)

    vehicle_blocked_end_date = (
        alert_data['vehicle_blocked_start_date'] +
        datetime.timedelta(days=instance_data['block_duration'])
        )
    
    await hpcl_ceg_model.Alerts(**{"id": alert_data['id'], 
                                        "vehicle_blocked_end_date": vehicle_blocked_end_date,
                                        "device_id": instance_data['instance'],
                                        "external_timestamp": vts_end_datetime,
                                        "device_name": instance_data['instance']}).modify()
    
    if instance_data['instance'] == 'Instance - 1':
        query = (f"update vts_truck_details set instance_1 = 1, truck_status = 'BLOCKED', block_start_datetime = '{alert_data['vehicle_blocked_start_date']}', block_end_datetime = '{vehicle_blocked_end_date}' "
                 f"where truck_regno = '{alert_data['vehicle_number']}'")
    if instance_data['instance'] == 'Instance - 2':
        query = (f"update vts_truck_details set instance_2 = 1, truck_status = 'BLOCKED', block_start_datetime = '{alert_data['vehicle_blocked_start_date']}', block_end_datetime = '{vehicle_blocked_end_date}' "
                 f"where truck_regno = '{alert_data['vehicle_number']}'")
    if instance_data['instance'] == 'Instance - 3':
        query = (f"update vts_truck_details set instance_3 = 1, truck_status = 'BLOCKED', block_start_datetime = '{alert_data['vehicle_blocked_start_date']}', block_end_datetime = '{vehicle_blocked_end_date}' "
                 f"where truck_regno = '{alert_data['vehicle_number']}'")
    if query:
        await hpcl_ceg_model.VtsTruckDetails.update_by_query(query)

    await update_alert_id_to_vts_history(alert_id=str(alert_data['id']), vts_alert_id=vts_alert_history_ids)

    return True

async def is_violation_exists(tl_number,invoice_number,violation):
    query = (f"select * from vts_violation_history where tl_number = '{tl_number}' and invoice_number= '{invoice_number}' and violation_name='{violation}'")
    print("query------>",query)
    vts_alert_data = await hpcl_ceg_model.VtsViolationHistory.get_aggr_data(query, limit=0)
    print("vts_alert_data--------->", vts_alert_data)
    if vts_alert_data.get("data", []):
        return True
    return False

async def trigger_vts_alarm_alert(entry):
    violation_fields = vts_instance_mapping.instance_mapping[entry['location_type']]["0"]
    camunda_url = await helpers.get_camunda_url(bu=entry['location_type'], sap_id=entry['location_id'],
                                                alert_section="VTS")
    location_data = entry.get("location_data", {})
    if not location_data:
        retries = 3
        for attempt in range(retries):
            if urdhva_base.ctx.exists(): 
                _, location_data = await alert_helper.get_location_details(entry['location_type'], entry['location_id'])
                break
            else:
                _, location_data = await cache_api_actions.get_location_data(bu=entry['location_type'], location_id=entry['location_id'])
            
            if location_data:
                break
            
            print(f"Retrying to fetch location data for {entry['location_type']} {entry['location_id']}... Attempt {attempt + 1}/{retries}")
            await asyncio.sleep(3)
    # print("location_data --> ", location_data)
    # if not status:
    #     return False, location_data
    base_data = {
        key: location_data.get(key, '') for key in [
            'state', 'city', 'zone', 'region', 'district', 'sales_area'
        ]
    }
    base_data.update({"location_name": location_data.get('name', '')})

    for v_field in violation_fields.keys():
        violation_data_mapping = vts_instance_mapping.violation_mapping["VTS"][v_field]
        violation_name = violation_data_mapping['violation_name']
        sop_id = violation_data_mapping['sop_id']
        severity = violation_data_mapping['severity']
        if not await is_violation_exists(entry['tl_number'],entry['invoice_number'],violation_name) and entry[v_field]>0:
            #unique_id = await alert_helper.get_alert_unique_id("TAS", entry['location_id'], sop_id)
            async with httpx.AsyncClient(verify=False) as client:
                base_url = f"http://{urdhva_base.settings.cache_gateway_host}:{urdhva_base.settings.cache_gateway_port}"
                resp = await client.get(f"{base_url}/api_cache/v1/get_unique_alert_id", params={"bu": "VTS",
                                                                                                "sap_id": entry['location_id'],
                                                                                                "sop_id": sop_id})
                if resp.status_code // 100 == 2:
                    unique_id = resp.text.strip('"')
            alert_message = (
                f"Vehicle Number: {entry['tl_number']} \n"
                f"Violation Type: {violation_name} \n"
                f"Reported at: {entry['vts_end_datetime']}"
            )
            allocated_time = datetime.datetime.now(datetime.timezone.utc)
            processed_time = datetime.datetime.now(datetime.timezone.utc)
            alert_history = [
                {
                    "action_msg": alert_message,
                    "action_type": "Created",
                    "alert_status": "Open",
                    "allocated_time": allocated_time.isoformat(),
                    "processed_time": processed_time.isoformat()
                }
            ]
            violation_data = {
                "vendor_id": entry['vendor_id'],
                "location_id": str(entry['location_id']),
                "location_type": entry['location_type'],
                "tl_number": entry['tl_number'],
                "unique_id": unique_id,
                "sop_id": sop_id,
                "alert_section": "VTS",
                "severity": severity.capitalize() if severity else "Medium",
                "report_duration": entry['report_duration'],
                "scheduled_trip_start_datetime": entry['scheduled_trip_start_datetime'],
                "scheduled_trip_end_datetime":entry['scheduled_trip_end_datetime'],
                "vts_start_datetime": entry['vts_start_datetime'],
                "vts_end_datetime": entry['vts_end_datetime'],
                "total_trips": entry['total_trips'],
                "violation_name": violation_name,
                "violation_type": v_field,
                "violation_count": entry[v_field],
                "alert_status": hpcl_ceg_enum.AlertStatus.Open,
                "approved_status": False,
                "invoice_number": entry['invoice_number'],
                "tt_type": entry['tt_type'],
                "workflow_datetime": urdhva_base.utilities.get_present_time().replace(tzinfo=None).isoformat(),
                "workflow_url": camunda_url,
                "workflow_port": camunda_url.split(":")[2],
                "alert_history": alert_history,
                "last_sms_to": [], 
                "last_mailed_to": [],
                "last_escalated_to": [],
                "last_notified_to": [], 
                "assigned_to": '',
                "assigned_to_role": '',
                "assigned_users": [],
                "assigned_user_roles": []
            }
            violation_data.update(base_data)
            vts_history_resp = await hpcl_ceg_model.VtsViolationHistoryCreate(**violation_data).create()
            alert_level = "level - 1"
            payload = {"businessKey": unique_id,
                        "variables": {"alert_id": {"value": vts_history_resp['id'], "type": "String"},
                                      "interlock_name": {"value": violation_name, "type": "String"},
                                      "location_type": {"value": entry['location_type'], "type": "String"},
                                      "sap_id": {"value": entry['location_id'], "type": "String"},
                                      "sop_id": {"value": sop_id, "type": "String"},
                                      "tt_type": {"value": entry['tt_type'], "type": "String"},
                                      "vts_level": {"value": alert_level, "type": "String"},
                                      "alert_section": {"value": "VTS", "type": "String"},
                                      "violation_type": {"value": v_field, "type": "String"},
                                      "invoice_number": {"value": entry['invoice_number'], "type": "String"},
                                      "vehicle_number": {"value": entry['tl_number'], "type": "String"},
                                      "transporter_code": {"value": entry['vendor_id'], "type": "String"},
                                      "workflow_datetime": {"value": datetime.datetime.now(datetime.UTC)
                                                            .strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z", "type": "String"}
                                    }}
            interlock_name = interlock_mapping.get_interlock_name(bu=entry['location_type'], interlock_name=violation_name,sop_id=sop_id)
            workflowid = interlock_name.get("workflow_name") or interlock_name.get("interlock_name") or None
            workflow_id = interlock_mapping.fmt_il_name(workflowid)
            await Camunda().start_workflow_vts(payload=payload, workflowId=workflow_id, camunda_url=camunda_url)

async def create_vts_violation_alerts(enriched_data):
    try:
        for entry in enriched_data:
            entry['auto_unblock'] = True
            entry['violation_type'] = await get_vts_violation(entry)
            entry['vts_start_datetime'], entry['vts_end_datetime'] = map(
                lambda x: datetime.datetime.strptime(x, "%Y-%m-%d %H:%M:%S"), entry['report_duration'].split(" to "))
            await trigger_vts_alarm_alert(entry)
    except Exception as e:
        logger.error(f"Error creating VTS Alert : {str(e)}")
    
async def create_vts_alerts(enriched_data):
    try:
        for entry in enriched_data:            
            entry['auto_unblock'] = True
            entry['violation_type'] = await get_vts_violation(entry)
            entry['vts_start_datetime'], entry['vts_end_datetime'] = map(
                lambda x: datetime.datetime.strptime(x, "%Y-%m-%d %H:%M:%S"), entry['report_duration'].split(" to "))
            await hpcl_ceg_model.VtsAlertHistoryCreate(**entry).create()
            # Skipping if the truck is already blacklisted
            if await is_vehicle_blacklisted(entry['tl_number']):
                black_list_query = f"select * from vts_truck_details where truck_regno = '{entry['tl_number']}'"
                vts_blacklist_data = await hpcl_ceg_model.VtsTruckDetails.get_aggr_data(black_list_query, limit=0)
                vts_truck_data = vts_blacklist_data['data'][0]
                truck_history = vts_truck_data.get("truck_history") or []
                truck_history.append({
                    "violated_date": entry["vts_end_datetime"].isoformat() if isinstance(entry["vts_end_datetime"], datetime.datetime) else entry["vts_end_datetime"],
                    "transporter_code": entry["vendor_id"],
                    "invoice_number": entry["invoice_number"],
                    "stoppage_violations_count": entry["stoppage_violations_count"],
                    "route_deviation_count": entry["route_deviation_count"],
                    "speed_violation_count": entry["speed_violation_count"],
                    "main_supply_removal_count": entry["main_supply_removal_count"],
                    "night_driving_count": entry["night_driving_count"],
                    "no_halt_zone_count": entry["no_halt_zone_count"],
                    "device_offline_count": entry["device_offline_count"],
                    "device_tamper_count": entry["device_tamper_count"],
                    "continuous_driving_count": entry["continuous_driving_count"],
                    "last_violated_date": truck_history[-1]['violated_date'] if len(truck_history) else ""})
                await hpcl_ceg_model.VtsTruckDetails(**{"id": vts_truck_data['id'], "truck_history": truck_history}).modify()
                continue
            if not await is_alert_exists(entry['tl_number']):                
                await alert_manager.create_alert({**entry, "alert_type": "VTS"})
            else:
                await update_vts_instance(entry)
    except Exception as e:
        logger.error(f"Error creating VTS Alert : {str(e)}")

async def close_camunda_workflow(alert_id):
    MAX_RETRIES = 5
    RETRY_DELAY = 5
    headers = {"Content-Type": "application/json"}
    alert_data = await hpcl_ceg_model.Alerts.get(alert_id)

    if not isinstance(alert_data, dict):
        alert_data = alert_data.__dict__

    instance_id = alert_data.get("workflow_instance_id")
    camunda_url = alert_data.get("workflow_url")
    url = f"{camunda_url}/engine-rest/process-instance/{instance_id}"
    async with aiohttp.ClientSession() as session:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.delete(url, headers=headers) as response:
                    if response.status == 204:  # Success in Camunda
                        print(f"{instance_id} Deleted successfully.")
                        break
                    else:
                        error_text = await response.text()
                        print(
                            f"Error Deleting {alert_id} {instance_id} {camunda_url} (attempt {attempt + 1}): {response.status} - {error_text}")

            except aiohttp.ClientError as e:
                print(f"Request error for {camunda_url} {instance_id} {alert_id} (attempt {attempt + 1}): {e}")

        # Retry logic with exponential backoff
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
        else:
            print(f"Failed to Deleting {camunda_url} {instance_id} after {MAX_RETRIES} retries.")
            return False
    return True

async def close_vts_alerts(alert_id):
    alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
    if not isinstance(alert_data, dict):
        alert_data = alert_data.__dict__
    alert_history = alert_data.get('alert_history', []) if isinstance(alert_data, dict) else getattr(alert_data,
                                                                                                     'alert_history',
                                                                                                     [])
    allocated_time = alert_data.get('updated_at', datetime.datetime.now(datetime.timezone.utc))
    if alert_history and alert_history[-1].get("processed_time"):
        allocated_time = alert_history[-1]["processed_time"]
    processed_time = datetime.datetime.now(datetime.timezone.utc)
    alert_message = (
        f"Vehicle Number: {alert_data['vehicle_number']} \n"
        f"Violation Type: {alert_data['violation_type']} \n"
        f"Vehicle Blocked Time: {alert_data['vehicle_blocked_start_date']} to {alert_data['vehicle_blocked_end_date']} \n"
    )
    alert_history.append(
        {
            'processed_time': processed_time.isoformat(),
            'allocated_time': allocated_time,  # For first entry, allocated_time equals processed_time
            'action_type': "Resolved",
            'action_msg': alert_message,
            "action_by": "VTS_VENDOR"
        }
    )
    alert_data['alert_status'] = 'Close'
    alert_data['alert_state'] = 'Resolved'
    await hpcl_ceg_model.Alerts(**{"id": alert_id, "alert_history": alert_history, "alert_status": "Close", "alert_state": "Resolved"}).modify()

async def fetch_access_token():
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": urdhva_base.settings.lpg_vts_client_id,
        "client_secret": urdhva_base.settings.lpg_vts_client_secret_key,
        "client_authentication": "send_as_basic_auth_header"
    }
    try:
        response = requests.post(urdhva_base.settings.lpg_vts_auth_url, headers=headers, data=data, timeout=10, verify=False)
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch token: {e}")
        return None

async def post_lpg_tt(payload):
    access_token = await fetch_access_token()
    if not access_token:
        print(f"[ERROR] Failed to fetch token")
        return None
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    try:
        response = requests.post(urdhva_base.settings.lpg_publish_url, headers=headers, data=json.dumps(payload),
                                 timeout=15, verify=False)
        response.raise_for_status()
        print("response->",response.json())
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Publish API call failed: {e}")
        return None

async def get_vts_alerts_count(bu: str, vehicle_number: str, sap_id: str, alert_section:str):
    vts_mapping = vts_role_mapping.vts_unblocking_matrix[alert_section]
    if sap_id in ['1652','1672','1693','1462','1649']:
        vts_mapping = vts_role_mapping.vts_sod_top_unblocking_matrix[alert_section]
    if bu in vts_mapping.keys():
        query = (f"""select count(*) as "count" from alerts """
                 f"where bu = '{bu}' and "
                 f"alert_section = 'VTS' and "
                 f"vehicle_number = '{vehicle_number}' and "
                 f"sap_id = '{sap_id}'")
        # dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = 1
        # dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
        # function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
        # resp = await function(query=query)
        resp = await hpcl_ceg_model.Alerts.get_aggr_data(query, limit=0)
        resp = resp.get("data", [])
        if resp:
            resp = resp[0]
            return resp.get("count", 0)
    return 0

async def get_vts_levels(bu: str, vehicle_number: str, sap_id: str, alert_section:str):
    vts_mapping = vts_role_mapping.vts_unblocking_matrix[alert_section]
    if sap_id in ['1652','1672','1693','1462','1649']:
        vts_mapping = vts_role_mapping.vts_sod_top_unblocking_matrix[alert_section]
    if bu in vts_mapping.keys():
        vts_level_data = vts_mapping[bu]
        vts_alert_count = await get_vts_alerts_count(bu=bu, vehicle_number=vehicle_number, sap_id=sap_id, alert_section=alert_section)
        previous_count = 0
        for key, value in vts_level_data.items():
            if value['condition'] == "<":
                if int(vts_alert_count) <= int(value['value']):
                    return "level - 1"
            if value['condition'] == "<>":
                if int(previous_count) < vts_alert_count <= int(value['value']):
                    return "level - 2"
            if value['condition'] == ">":
                if vts_alert_count > int(value['value']):
                    return "level - 3"
            previous_count = value['value']
    return ""

# device_tamper_count
# main_supply_removal_count
# route_deviation_count
# stoppage_violations_count
# speed_violation_count
# night_driving_count
# continuous_driving_count
