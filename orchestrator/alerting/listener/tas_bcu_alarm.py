import urdhva_base
import os
import json
import asyncio
import traceback
from datetime import datetime
import tas_duplicate_alert_check as duplicates_check
from orchestrator.alerting.alert_manager import create_alert, close_alert
from orchestrator.alerting.listener.tas_listener import fix_additional_info


async def tas_bcu_listener(rmsg):
    try:
        if rmsg.get("details") and rmsg["details"].get("additionalInfo"):
            rmsg["details"]["additionalInfo"] = fix_additional_info(rmsg["details"]["additionalInfo"])
        if rmsg['status'] == 'ACTIVE_UNACK':
            alertdata = rmsg['details']['additionalInfo']
            # First, check if it's a duplicate
            is_duplicate = await duplicates_check.duplicate_check(alertdata)
            if is_duplicate:
                print(f"Alert already exists (duplicate) for: {alertdata}")
                return  
            # Valid new alert, proceed to create it
            alertdata['severity'] = rmsg['severity']
            alertdata['alert_type'] = rmsg['details']['additionalInfo']['bu']
            alertdata['alert_id'] = rmsg['id']['id']
            custom_data = rmsg['details']['additionalInfo'].get("customData", {})
            
            alertdata['message'] = ", ".join([f"{key}={value}" for key, value in custom_data.items()])
            print("Create Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
                                                        rmsg['type']))
            await create_alert(alertdata)
        elif rmsg['status'] == 'CLEARED_UNACK':
            alertdata = rmsg['details']['additionalInfo']
            alertdata['alert_type'] = rmsg['details']['additionalInfo']['bu']
            alertdata['alert_id'] = rmsg['id']['id']
            print("Close Alert bu:%s SAPID:%s for:%s " % (alertdata.get('bu', ''), alertdata.get('sap_id', ''),
                                                        rmsg['type']))
            await close_alert(alertdata)
        else:
            print("Invalid message received:%s" % rmsg)
        return True
    except Exception as e:
        print(traceback.format_exc())
        print("Exception in processing RQ message:%s" % e)
            
    
    
if __name__=="__main__":
    rmsgs = [
            {
                    "tenantId": {
                        "entityType": "TENANT",
                        "id": "7bc8da50-f33d-11ef-9b4e-d19fe2e912bb"
                    },
                    "type": "BCU Premissive",
                    "originator": {
                        "entityType": "DEVICE",
                        "id": "fe89bee0-1e81-11f0-92d4-2baa80353207"
                    },
                    "severity": "CRITICAL",
                    "status": "ACTIVE_UNACK",
                    "startTs": 1745302066028,
                    "endTs": 1745302066028,
                    "ackTs": 0,
                    "clearTs": 1745302805073,
                    "details": {
                        "additionalInfo": {
                            "location_id": "1919",
                            "location_name": "Secunderabad",
                            "plantlocationid": "1919",
                            "plantlocation": "Secunderabad",
                            "bu_id": "eee588c0-1e81-11f0-92d4-2baa80353207",
                            "SAPID": "1919",
                            "BU": "TAS",
                            "LP 36_BC-8B-LP1_SKO@Secunderabad": 1,
                            "LP Earthing STATUS": "0",
                            "NO FLOW STATUS OF MAIN": "0",
                            "LOW FLOW STATUS OF MAIN": "0",
                            "HIGH FLOW STATUS OF MAIN": "0",
                            "UNAUTHORISE FLOW STATUS OF MAIN": "0",
                            "METER OVERRUN STATUS OF MAIN": "0",
                            "BLEND OVERDOSE STATUS OF MAIN": "0",
                            "BLEND UNDERDOSE STATUS OF MAIN": "0",
                            "ADD OVERDOSE STATUS OF MAIN": "0",
                            "ADD UNDERDOSE STATUS OF MAIN": "0",
                            "BCU LOADING STATUS": "0",
                            "BCU VS MFM TOTALIZER MISMATCH": "0",
                            "DAY START TOTALIZER MISMATCH": "0",
                            "K-FACTOR CHANGE STATUS": "0",
                            "deviceType": "Loading Point",
                            "deviceName": "LP 36_BC-8B-LP1_SKO@Secunderabad",
                            "sap_id": "1919",
                            "interlockName": "BCU Permissive Off",
                            "unitName": "LP 36_BC-8B-LP1_SKO@Secunderabad",
                            "Sensor_Type": "BCU",
                            "Sensor_Name": "BCU",
                            "sopid": "SOP028A",
                            "alert_category": "Process",
                            "severity": "Medium",
                            "BCU Number": "N/A"
                        }
                    },
                    "propagate": False,
                    "propagateRelationTypes": [],
                    "id": {
                        "entityType": "ALARM",
                        "id": "1c388700-1f40-11f0-92d4-2baa80353207"
                    },
                    "createdTime": 1745302066032,
                    "name": "BCU Premissive"
            },
            {
                    "tenantId": {
                        "entityType": "TENANT",
                        "id": "7bc8da50-f33d-11ef-9b4e-d19fe2e912bb"
                    },
                    "type": "BCU Premissive",
                    "originator": {
                        "entityType": "DEVICE",
                        "id": "fe89bee0-1e81-11f0-92d4-2baa80353207"
                    },
                    "severity": "CRITICAL",
                    "status": "CLEARED_UNACK",
                    "startTs": 1745302066028,
                    "endTs": 1745302066028,
                    "ackTs": 0,
                    "clearTs": 1745302805073,
                    "details": {
                        "additionalInfo": {
                            "location_id": "1919",
                            "location_name": "Secunderabad",
                            "plantlocationid": "1919",
                            "plantlocation": "Secunderabad",
                            "bu_id": "eee588c0-1e81-11f0-92d4-2baa80353207",
                            "SAPID": "1919",
                            "BU": "TAS",
                            "LP 36_BC-8B-LP1_SKO@Secunderabad": 1,
                            "LP Earthing STATUS": "0",
                            "NO FLOW STATUS OF MAIN": "0",
                            "LOW FLOW STATUS OF MAIN": "0",
                            "HIGH FLOW STATUS OF MAIN": "0",
                            "UNAUTHORISE FLOW STATUS OF MAIN": "0",
                            "METER OVERRUN STATUS OF MAIN": "0",
                            "BLEND OVERDOSE STATUS OF MAIN": "0",
                            "BLEND UNDERDOSE STATUS OF MAIN": "0",
                            "ADD OVERDOSE STATUS OF MAIN": "0",
                            "ADD UNDERDOSE STATUS OF MAIN": "0",
                            "BCU LOADING STATUS": "0",
                            "BCU VS MFM TOTALIZER MISMATCH": "0",
                            "DAY START TOTALIZER MISMATCH": "0",
                            "K-FACTOR CHANGE STATUS": "0",
                            "deviceType": "Loading Point",
                            "deviceName": "LP 36_BC-8B-LP1_SKO@Secunderabad",
                            "sap_id": "1919",
                            "interlockName": "BCU Permissive Off",
                            "unitName": "LP 36_BC-8B-LP1_SKO@Secunderabad",
                            "Sensor_Type": "BCU",
                            "Sensor_Name": "BCU",
                            "sopid": "SOP028A",
                            "alert_category": "Process",
                            "severity": "Medium",
                            "BCU Number": "N/A"
                        }
                    },
                    "propagate": False,
                    "propagateRelationTypes": [],
                    "id": {
                        "entityType": "ALARM",
                        "id": "1c388700-1f40-11f0-92d4-2baa80353207"
                    },
                    "createdTime": 1745302066032,
                    "name": "BCU Premissive"
                }
    ]
    
    print(rmsgs)
    for rmsg in rmsgs:
        asyncio.run(tas_bcu_listener(rmsg))