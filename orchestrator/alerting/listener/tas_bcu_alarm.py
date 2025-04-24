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
            alert_history = await duplicates_check.alert_history_check(alertdata, month_check=False)
            if alert_history:
                # Closing the alert as for same device, already the alert has been created for the current date
                alertdata["sop_id"] = f"{alertdata['sop_id']}_C"
                await create_alert(alertdata)
                print(f"Device already initiated for the day, Closing the alert : {alertdata}")
                return
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
    rmsg = open("/Users/apple/Documents/SUBLIME_TEXTS/bcu_permisive_alarm.json", "r")
    rmsg = json.load(rmsg)
    
    print(rmsg)
    asyncio.run(tas_bcu_listener(rmsg))