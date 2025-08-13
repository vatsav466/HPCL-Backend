import urdhva_base
import asyncio
import traceback
from datetime import datetime
from dateutil.relativedelta import relativedelta
from orchestrator.dbconnector.widget_actions import lpg_config


class LPGOperationsActions:

    async def get_breaks(plant_id, carousal_id):
        query = f"""SELECT start_time, stop_time FROM public.breaks WHERE plant_id = {plant_id} AND carousal_id = {carousal_id}"""
        result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if result['data']:
            result = result['data']
        else:
            return False
        breaks = []
        for row in result:
            breaks.append({
                "from" : row['start_time'],
                "to" : row['stop_time']
            })
        return breaks

    async def get_plant_short_name(sap_id):
        query = f""" SELECT short_name FROM public.plants WHERE erp_id = {sap_id} """
        result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=1)
        if result["data"]:
            return result["data"][0]["short_name"]
        return None

    async def get_plant_id_by_short_name(plantShortName):
        query = f""" SELECT MAX(id) as id from public.plants where short_name = '{plantShortName}' """
        result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if result['data']:
            plant_id = result['data']
            return plant_id[0]['id']
        else:
            return 0
    
    async def get_carousals_config(plant_short_name):
        plant_id = await LPGOperationsActions.get_plant_id_by_short_name(plant_short_name)

        query = f""" SELECT carousal_id, heads, rated_productivity, start_time, stop_time FROM public.carousals WHERE plant_id = {plant_id} """
        result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if result['data']:
            result = result['data']
        else:
            return False
        config = {}
        for row in result:
            config[row['carousal_id']] = {
                'heads' : row['heads'],
                'stdOutput' : row['rated_productivity'],
                'times' : {
                    'start' : row['start_time'],
                    'end' : row['stop_time'],
                    'breaks' : await LPGOperationsActions.get_breaks(plant_id, row['carousal_id'])
                }
            }
        return config

    async def get_carousals(type: str, sap_id: str):
        plant_short_name = await LPGOperationsActions.get_plant_short_name(sap_id=sap_id)
        carousal_config = await LPGOperationsActions.get_carousals_config(plant_short_name)
        keys = list(carousal_config.keys())
        if type == 'string':
            return ", ".join(map(str, keys))
        if type == 'array':
            return  keys
        if type == 'full':
            return carousal_config
        else:
            return  ", ".join(map(str, list(carousal_config.keys())))

    @staticmethod
    async def get_gd_rejection(data : dict):
        from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
        to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")

        if not data.get("carousal", None):
            carousal = await LPGOperationsActions.get_carousals('string', data.get("sap_id"))
            processId = '3,23'

        query = f"""SELECT
                        process_id,
                        process_status,
                        COUNT(event_log_id)
                    FROM event_log
                    WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                        AND system_id IN ({carousal})
                        AND process_id IN ({processId})
                        AND sap_id = {data['sap_id']}
                    GROUP BY  process_status, process_id """
        
        results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if results['data']:
            results = results['data']

        if results:
            data = {
                'handled' : 0,
                'sortout' : 0
            }

            for row in results:
                data['handled'] += row['count'] 
                if row['process_status'] != 0:
                    data['sortout'] += row['count'] 

            data['rejection_rate'] = round((data['sortout'] / data['handled']) * 100, 2)
            return data
        return False
    
    @staticmethod
    async def get_pt_rejection(data : dict):
        from_date = datetime.strptime(
            f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S"
            )
        to_date = datetime.strptime(
            f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S"
            )

        if not data.get("carousal", None):
            carousal = await LPGOperationsActions.get_carousals('string', data.get("sap_id"))
        processId = '4,24'
        
        query = f"""SELECT
                        process_id,
                        process_status,
                        COUNT(event_log_id)
                    FROM event_log
                    WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                        AND system_id IN ({carousal})
                        AND process_id IN ({processId})
                        AND sap_id = {data['sap_id']}
                    GROUP BY  process_status, process_id"""

        results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if results['data']:
            results = results['data']

        if results:
            data = {
                'handled' : 0,
                'sortout' : 0
            }

            for row in results:
                data['handled'] += row['count'] 
                if row['process_status'] != 0:
                    data['sortout'] += row['count'] 

            data['rejection_rate'] = round((data['sortout'] / data['handled']) * 100, 2)
            return data
        return False
    

    async def get_cs_rejection(data : dict):
        from_date = datetime.strptime(
            f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S"
            )
        to_date = datetime.strptime(
            f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S"
            )
        
        carousals = await LPGOperationsActions.get_carousals('string', data.get("sap_id"))
        carousal_array = await LPGOperationsActions.get_carousals('array', data.get("sap_id"))
        
        query =f"""SELECT
                        system_id,
                        process_status,
                        COUNT(production_log_id)
                    FROM production_log
                    WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                        AND system_id IN ({carousals})
                        AND process_id IN (2,22)
                    GROUP BY  process_status, system_id"""

        results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if results['data']:
            results = results['data']
        data = {}
        total = {}
        totalSortout = {}
        otherErrors = {}
        commErrorSortout = {}

        for c in carousal_array:
            total[c] = 0
            totalSortout[c] = 0
            otherErrors[c] = 0
            commErrorSortout[c] = 0
        sortoutStatuses = [1040, 2064, 1296, 17424, 1048, 4120, 5392]
        otherErrorStatuses = [1041, 1042, 2192, 4112, 4113, 5136, 6160]
        for row in results:
            carID = row['system_id']
            processID = row['process_status']
            if carID not in data:
                data[carID] = {}
            data[carID][processID] = row['count']
            total[carID] += row['count']
            if row['process_status'] in otherErrorStatuses:
                otherErrors[carID] += row['count']
            if row['process_status'] in sortoutStatuses + otherErrorStatuses:
                totalSortout[carID] += row['count']
            if row['process_status'] < 0 or row['process_status'] == 4096:
                commErrorSortout[carID] += row['count']
        
        refData = {}
        for id in carousal_array:
            refData[id] = {
            'total' : int(total[id]),
            'cylinder_filled':int(total[id] - totalSortout[id]),
            'underfilled': int(data.get(id, {}).get(1040, 0)),
            'overfilled' : int(data.get(id, {}).get(2064, 0)),
            'negative_tare'	: int(data.get(id, {}).get(1296, 0)+(data.get(id, {}).get(5392,0))),
            'positive_tare' : int(data.get(id, {}).get(17424, 0)),
            'timeout':int(data.get(id, {}).get(1048, 0) + data.get(id,{}).get(4120, 0)),
            'other_errors'	: int(otherErrors[id]),
            'sortout':int(totalSortout[id]),
            'commErrorSortout':int(commErrorSortout[id]),
            'rejection_rate' : round((int(totalSortout[id]) / int(total[id])) * 100, 2)
            }

        return refData