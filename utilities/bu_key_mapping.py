Location = {
    "LocationID": "sap_id",
    "LocationName": "name",
    "LocationType": "bu",
    "LocationState": "state",
    "Address": "address",
    "LocationDistrict": "district",
    "LocationRegion": "region",
    "LocationCity": "city",
    "LocationZone": "zone",
    "LocationPinCode": "pinCode",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "LocalAutomationVendor": "localAutomationVendor"
}

LPG = {
    "LocationID": "sap_id",
    "LocationName": "location_name",
    "LocationType": "bu",
    "LocationState": "state",
    "LocationCity": "city",
    "LocationRegion": "region",
    "DeviceType": "device_type",
    "DeviceDesc": "device_desc",
    "DeviceTag": "device_tag",
    "DeviceID": "device_id",
    "DeviceKey": "device_key"
}


RO = {
    "LocationID": "sap_id",
    "LocationName": "location_name",
    "LocationType": "bu",
    "LocationState": "state",
    "LocationCity": "city",
    "LocationRegion": "region",
    "BayID": "bay_id",
    "MPDID": "mpd_id",
    "TankID": "tank_id",
    "NozzleID": "nozzle_id"
}

Role = {
    "LocationID": "sap_id",
    "LocationName": "name",
    "LocationType": "bu",
    "LocationState": "state",
    "LocationCity": "city",
    "LocationRegion": "region",
    "InchargeName": "inchargeName",
    "InchargeEmail": "inchargeEmail",
    "InchargePhone": "inchargePhone",
    "InchargeRole": "inchargeRole",
    "NotificationLevel": "notificationLevel"
}

TAS = {
    "LocationID": "sap_id",
    "LocationName": "location_name",
    "LocationType": "bu",
    "LocationState": "state",
    "LocationCity": "city",
    "LocationRegion": "region",
    "DeviceType": "device_type",
    "DeviceDesc": "device_desc",
    "DeviceTag": "device_tag",
    "DeviceID": "device_id",
    "DeviceKey": "device_key"
}

processcodemap = {
    'RO': '1', 
    'TAS': '2', 
    'VTS': '3', 
    'TAS_vehicle': '3', 
    'LPG_vehicle': '4'
    }


tasSopcommands = {
    "SOP012": "/ASSETS/OPC/TLF_PULSE_STP_LPID.OP",
    "SOP013": "/ASSETS/OPC/TLF_KFACT_STP_LPID.OP",
    "SOP014": "/ASSETS/OPC/TLF_NFLOW_STP_LPID.OP",
    "SOP015": "/ASSETS/OPC/TLF_LFLOW_STP_LPID.OP",
    "SOP016": "/ASSETS/OPC/TLF_HFLOW_STP_LPID.OP",
    "SOP017": "/ASSETS/OPC/TLF_UFLOW_STP_LPID.OP",
    "SOP018": "/ASSETS/OPC/TLF_ORUN_STP_LPID.OP",
    "SOP019": "/ASSETS/OPC/TLF_BOVER_STP_LPID.OP",
    "SOP020": "/ASSETS/OPC/TLF_BUNDER_STP_LPID.OP",
    "SOP021": "/ASSETS/OPC/TLF_AOVER_STP_LPID.OP",
    "SOP022": "/ASSETS/OPC/TLF_AUNDER_STP_LPID.OP",
}