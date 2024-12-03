import urdhva_base
import pytz
import json
import requests
from requests.auth import HTTPBasicAuth
import asyncio
import datetime
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class SendSapCommand:

    async def get_required_variables(self):
        return ["alert_id", "interrupt", "vehicle"]
    
    async def sendsapcommand(self, params):
        IST = pytz.timezone('Asia/Kolkata')
        currtime = datetime.datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')
        interuptName = params.get('interrupt')
        isvehicle = params.get('vehicle')
        processcodemap = {'RO': '1', 'TAS': '2', 'VTS': '3', 'TAS_vehicle': '3', 'LPG_vehicle': '4'}

        alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))

        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__
        
        flag = 'B'
        if interuptName.lower() == 'unblock':
            flag = 'U'
        
        bu = alert_data.get('bu','')
        processkey = bu
        vendor = ''
        code = alert_data.get('sap_id', '')
        vehicle_number = alert_data.get('vehicle_number', '')
        sopi_id = alert_data.get('sop_id', '')
        device_type = alert_data.get('device_type', '')

        if device_type == "Aryaomnitalk":
            code = alert_data.get('vehicle_number', '')
            vendor = alert_data.get('vendor', '')
        if isvehicle and isvehicle.lower() == 'true':
            processkey += '_vehicle'
            code = alert_data.get('vehicle_number', '')
            vendor = alert_data.get('vendor', '')
        
        if flag == 'U':
            vehicle_number = alert_data.get('vehicle_number', '')
        
        unblocks = []

        if flag == 'U':
            await asyncio.sleep(4)
            query = (f"vehicle_number='{vehicle_number}' and device_type='{'Aryaomnitalk'}'"
                     f"and alert_status >='{'Open'}'")
            status, ndata = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query), resp_type='plain')
            if status and ndata['data']:
                udata1 = ndata['data']
                for fdata in udata1:
                    unblocks.append(fdata['id'])
            if len(unblocks) > 1:
                alert_data["alert_history"].append(
                    'Another voilations are existing for this lorry:%s :%s-%s' % (vehicle_number, unblocks, currtime))
                await hpcl_ceg_model.Alerts(**alert_data).modify()
                return True, {"sapcommandsent": True}
        
        process_code = processcodemap.get(processkey, '')

        ts = datetime.datetime.now()
        request_date = ts.strftime('%Y-%m-%d')
        request_time = ts.strftime('%H:%M:%S')

        user_name = urdhva_base.settings.sap_user_name
        password = urdhva_base.settings.sap_password
        url = urdhva_base.settings.sap_url
        reason = alert_data.get('msg', 'IRIS')
        blocks = []

        query = (f"vehicle_number='{vehicle_number}' and device_type='{'Aryaomnitalk'}'"
                     f"and alert_status >='{'Open'}'")
        status, aldata2 = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query), resp_type='plain')

        if status and aldata2['data']:
            for fdata in aldata2['data']:
                blocks.append(fdata['id'])
        
        data = {}

        if aldata2['total'] == 1 and flag == 'B':
            data = {"Input": {"Source": "CCC",
                              "Request_Date": request_date,  # "2021-01-21",
                              "Request_Time": request_time,  # "17:20:00",
                              "Process_Code": process_code,
                              "Request": [{"Code": code,
                                           "Vendor": vendor,
                                           "Flag": flag,
                                           "Reason": reason,
                                           "UserID": ""
                                           }]
                            }
                }
        elif aldata2['total'] == 0 and flag =='B':
            data = {"Input": {"Source": "CCC",
                              "Request_Date": request_date,  # "2021-01-21",
                              "Request_Time": request_time,  # "17:20:00",
                              "Process_Code": process_code,
                              "Request": [{"Code": code,
                                           "Vendor": vendor,
                                           "Flag": flag,
                                           "Reason": reason,
                                           "UserID": ""
                                           }]
                            }
                }
        
        elif len(unblocks) == 1 and flag == 'U':
            data = {"Input": {"Source": "CCC",
                              "Request_Date": request_date,  # "2021-01-21",
                              "Request_Time": request_time,  # "17:20:00",
                              "Process_Code": process_code,
                              "Request": [{"Code": code,
                                           "Vendor": vendor,
                                           "Flag": flag,
                                           "Reason": reason,
                                           "UserID": ""
                                        }]
                        }
                }
        
        elif sopi_id == "SOP023":
            data = {"Input": {"Source": "CCC",
                              "Request_Date": request_date,  # "2021-01-21",
                              "Request_Time": request_time,  # "17:20:00",
                              "Process_Code": process_code,
                              "Request": [{"Code": code,
                                           "Vendor": vendor,
                                           "Flag": flag,
                                           "Reason": reason,
                                           "UserID": ""
                                           }]
                            }
                }
        
        elif flag == 'B' and interuptName == 'block' and len(
                blocks) > 1:
            alert_data['alert_history'].append(
                'Another voilations are existing for this lorry:%s :%s-%s' % (vehicle_number, blocks, currtime))
            await hpcl_ceg_model.Alerts(**alert_data).modify()
            return True, {"sapcommandsent": True}
        
        exceptionOcr, exceptionStr = False, ''
        if data:
            try:
                resp = requests.post(url=url, auth=HTTPBasicAuth(user_name,password), data=json.dumps(data), verify=False)
                sap_status_code = resp.status_code
                print("SAP Command Data:%s Response:%s Text:%s" % (data, sap_status_code, resp.text))
            
            except Exception as e:
                print("Exception Occured While sending  Sap Command :" + str(e))
                sap_status_code = 407
                exceptionOcr = True
                exceptionStr = str(e)
        else:
            sap_status_code = 407
            exceptionOcr = False
        
        IST = pytz.timezone('Asia/Kolkata')
        currtime = datetime.datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')

        if int(sap_status_code/100) == 2:
            sap_resp = resp.json()['Output']['Responce']
            msg = 'Success, Status:%s Remarks:%s' % (sap_resp['Status'], sap_resp['Remarks'])
        else:
            if exceptionOcr:
                msg = 'Failed, %s' % exceptionStr
            else:
                msg = 'Failed'
        
        alert_data['alert_history'].append('%s - SAP Response:%s' % (currtime, msg))
        alert_data['block'] = True 
        await hpcl_ceg_model.Alerts(**alert_data).modify()

        if exceptionOcr:
            return True, {"sapcommandsent": False}
        return True, {"sapcommandsent": True}

        








        
            




            
        



        