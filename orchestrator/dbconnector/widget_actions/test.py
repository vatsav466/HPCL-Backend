import urdhva_base
# import calendar
import json
from decimal import Decimal
import psycopg2
import asyncio
from datetime import datetime, timedelta, time 
# import traceback
import polars as pl
pl.Config(set_fmt_float="full")
import numpy as np
import pandas as pd
# from orchestrator.dbconnector.widget_actions import config
import math
import lpg_config
# import hpcl_ceg_model
# import dashboard_studio_model
# from dateutil.relativedelta import relativedelta
# import utilities.connection_mapping as connection_mapping
# from orchestrator.dbconnector.widget_actions import widget_actions
# from api_manager.charts_actions import charts_connection_vault_routing
# from dashboard_studio_model import Charts_Connection_Vault_RoutingParams
# import orchestrator.dbconnector.widget_actions.lpg_plant_queries as lpg_plant_queries
class SecureConfig:
    interruptionToExclude = 100

class LPGOperationsActions:   
    async def get_productivity(data : dict):
        #if carosaul or cyl_types are not provided use default
        if not data.get("carousal", None):
            carousal = await LPGOperationsActions.get_carousals('string')
        if not data.get("cyl_types", None):
            cyl_types = ",".join(map(str, lpg_config.cyl_types))

        from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
        to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")

        #excluding statuses
        excludedStatuses = ", ".join(map(str, lpg_config.process_statuses['negativeTare'] + lpg_config.process_statuses['positiveTare']))
        # query
        query_string = f"""SELECT
        system_id,
        MAX(sap_id) AS sap_id,
        SUM(CASE
          WHEN (cyl_type = 1)
          THEN 1
          WHEN (cyl_type = 2)
          THEN 1.25
          ELSE 0
          END) AS total,
        (SELECT process_date
          FROM production_log
            WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
            AND process_id IN (2,22)
            AND system_id = p.system_id
            AND cyl_type IN ({cyl_types})
            AND process_status NOT IN ({excludedStatuses})
            ORDER BY process_date DESC
            LIMIT 1
        ) AS last_cyl_time,
        (SELECT process_date
          FROM production_log
            WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
            AND process_id IN (2,22)
            AND system_id = p.system_id
            AND cyl_type IN ({cyl_types})
            AND process_status NOT IN ({excludedStatuses})
            ORDER BY process_date ASC
            LIMIT 1
        ) AS first_cyl_time
         FROM production_log p
        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
          AND process_id IN (2,22)
          AND system_id IN ({carousal})
          AND cyl_type IN ({cyl_types})
          AND process_status NOT IN ({excludedStatuses})
          AND sap_id = {data['sap_id']}
        GROUP BY system_id
        ;"""

        rawData = await urdhva_base.BasePostgresModel.get_aggr_data(query_string, limit=0)
        if rawData["data"]:
            rawData = rawData["data"]
        
        if rawData is None:
            return False

        secure = SecureConfig()
        interruption_to_exclude = secure.interruptionToExclude * 60 

        system_ids = []
        for row in rawData:
            system_ids.append(row['system_id'])

        return_data = {}
        for id in system_ids:
            query_text = f"""SELECT * FROM production_log 
                        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                          AND system_id = {id}
                          AND process_id IN (2,22)
                          AND cyl_type IN ({cyl_types})
                          AND sap_id = {data['sap_id']}
                        ORDER BY production_log_id ASC
                       ;"""
            
            query_data = await urdhva_base.BasePostgresModel.get_aggr_data(query_text, limit=0)
            if query_data['data'] :
                query_data = query_data['data']

            # calculating time gap for each row 
            for i, row in enumerate(query_data):
                row['timeGap'] = (row['process_date'] - query_data[max(i - 1, 0)]['process_date']).total_seconds()

            filtered_rows = [row for row in query_data if row['timeGap'] > interruption_to_exclude]

            total_interruption = 0
            interruption_array = []

            for row in filtered_rows:
                total_interruption += row['timeGap']
                start_time = row['process_date'] - timedelta(seconds=row['timeGap'])
                interruption_array.append(
                    {
                        'duration' : row['timeGap'],
                        'startTimeEpoch' : int(start_time.timestamp()),
                        'startTime' : start_time.strftime('%Y-%m-%d %H:%M:%S.%f')
                    }
                )
            return_data[id] = {
                'totalInterruption' : total_interruption,
                'interruptionCount' : len(interruption_array)
            }
      
        cyl_data = {}
        totalProductionToday = 0
        totalInterval = 0

        for row in rawData:
            interruption = timedelta(seconds=return_data[row['system_id']]['totalInterruption'])
            row['interval'] = (row['last_cyl_time'] - row['first_cyl_time'] - interruption) / (60 * 60)
            productivityAdjustmentFactor = lpg_config.productivityAdjustmentFactor
            row['productivity'] = row['total'] / Decimal(row['interval'].total_seconds() / 3600) * Decimal(productivityAdjustmentFactor)

            cyl_data[row['system_id']] = row
            totalProductionToday = row['total']
            totalInterval = Decimal(row['interval'].total_seconds())
  
        productivityToday = {
          'overall' : 0
        }

        if totalProductionToday == 0 :
            "deal with 0 production today"
        
        else:
          productivityToday['overall'] = totalProductionToday / totalInterval * Decimal(lpg_config.productivityAdjustmentFactor)
          productivityToday.update(cyl_data)
        

        return productivityToday

    async def get_check_scale_rejection_report(data : dict):
        from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
        to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")
        carousals = await LPGOperationsActions.get_carousals('string')
        carousal_array = await LPGOperationsActions.get_carousals('array')
        query =f"""SELECT
        system_id,
        process_status,
        COUNT(production_log_id)
        FROM production_log
        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
          AND system_id IN ({carousals})
          AND process_id IN (2,22)
        GROUP BY  process_status, system_id;"""

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
        # return results, data, total, totalSortout, otherErrors, commErrorSortout
        refData = {}
        for id in carousal_array:
            refData[id] = {
            'total' : int(total[id]),
            'cylFilled':int(total[id] - totalSortout[id]),
            'underfilled': int(data.get(id, {}).get(1040, 0)),
            'overfilled' : int(data.get(id, {}).get(2064, 0)),
            'ntare'	: int(data.get(id, {}).get(1296, 0)+(data.get(id, {}).get(5392,0))),
            'ptare' : int(data.get(id, {}).get(17424, 0)),
            'timeout':int(data.get(id, {}).get(1048, 0) + data.get(id,{}).get(4120, 0)),
            'other'	: int(otherErrors[id]),
            'totalSortout':int(totalSortout[id]),
            'commErrorSortout':int(commErrorSortout[id]),
            'sortOutPercentage' : int(totalSortout[id]) / int(total[id])
            }

        return refData


    async def get_check_scale_rejection_data(data : dict):

        from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
        to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")
        if not data.get("carousal", None):
            carousal = await LPGOperationsActions.get_carousals('string')
        if not data.get("cyl_types", None):
            cyl_types = ",".join(map(str, lpg_config.cyl_types))

        query = f"""SELECT
        system_id,
        process_status,
        COUNT(production_log_id)
        FROM production_log
        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
          AND system_id IN ({carousal})
          AND process_id IN (2,22)
        GROUP BY  process_status, system_id;"""

        results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if results['data']:
            results = results['data']
        data = {}
        total = {1:0,2:0}
        sortoutStatuses = [1040, 2064, 1296, 17424, 1048, 4120, 5392]
        totalSortout = {1:0, 2:0 }
        otherErrorStatuses = [1041, 1042, 2192, 4112, 4113, 5136, 6160]
        otherErrors = {1:0,2:0}
        commErrorSortout = {1:0,2:0}

        for row in results:
            carID = row['system_id']
            processID = row['process_status']
            total[carID] += row['count']
            if row['process_status'] in  otherErrorStatuses:
                otherErrors[carID] += row['count']
            if row['process_status'] in sortoutStatuses + otherErrorStatuses:
                totalSortout[carID] += row['count']
            if row['process_status'] < 0 or row['process_status'] == 4096:
                commErrorSortout[carID] += row['count']
        
        refData = {}
        for id in [1,2]:
            row = data.get(id, {})
            refData[id] = {
            'total' : total[id],
            'cylFilled' : total[id] - totalSortout[id],
            'underfilled' : row.get(1040, 0),
            'overfilled': data.get(id, {}).get(2064, 0),
            'ntare' : row.get(1296, 0) + row.get(5392, 0),
            'ptare' :row.get(17424, 0),
            'timeout' : row.get(1048,0) + row.get(4120,0),
            'other' : otherErrors[id],
            'totalSortout' : totalSortout[id],
            'commErrorSortout' : commErrorSortout[id]
            }
        return refData
    

    async def get_check_scale_rejection_summary(data : dict):
        if not data.get("carousal", None):
            carousal = await LPGOperationsActions.get_carousals('string')
            carousal_count = 2
        if not data.get("cyl_types", None):
            cyl_types = ",".join(map(str, lpg_config.cyl_types))
    
        from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
        to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")

        query = f"""SELECT
        system_id,
        process_status,
        COUNT(production_log_id)
        FROM production_log
        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
          AND system_id IN ({carousal})
          AND process_id = 2
        GROUP BY  process_status, system_id;"""

        results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if results['data']:
            results = results['data']
        data = {}
    
        total = {1:0,2:0}
        sortoutStatuses = [1040, 2064, 1296, 17424, 1048, 4120, 5392]
        totalSortout = {1:0, 2:0}

        otherErrorStatuses = [1041, 1042, 2192, 4112, 4113, 5136, 6160];
        otherErrors = {1:0, 2:0}
        commErrorSortout ={1:0,2:0}
        for row in results:
            carID = row['system_id']
            processID = row['process_status']
            data[carID] = {}
            data[carID][processID] = row['count']
            total[carID] += row['count']
            if row['process_status'] in sortoutStatuses + otherErrorStatuses:
                totalSortout[carID] += row['count']
            if row['process_status'] < 0 or row['process_status'] == 4096:
                commErrorSortout[carID] += row['count']
        refData = {
            'total' : 0,
            'cylFilled' : 0,
            'totalSortout' : 0,
            'commErrorSortout' : 0
        }
        for id in  [1, 2]:
            refData['total'] += total[id]
            refData['cylFilled'] += total[id] - totalSortout[id]
            refData['totalSortout'] += totalSortout[id]
            refData['commErrorSortout'] += commErrorSortout[id]

        refData['sortOutPercentage'] = refData['totalSortout'] / refData['total']

        return refData 
    
    async def get_cs_rejection_stat(data : dict):
        if not data.get("carousal", None):
            carousal = await LPGOperationsActions.get_carousals('string')
        if not data.get("cyl_types", None):
            cyl_types = ",".join(map(str, lpg_config.cyl_types))
    
        from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
        to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")

        query = f"""
          SELECT
        system_id,
        process_status,
        COUNT(production_log_id)
        FROM production_log
        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
          AND system_id IN ({carousal})
          AND process_id IN (2, 22)
          AND sap_id = {data['sap_id']}
        GROUP BY  process_status, system_id
        """
        results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if results['data']:
            results = results['data']
        data = {}
        total = {
            1:0,
            2:0
        }
        sortoutStatuses = [1040, 2064, 1296, 17424, 1048, 4120, 5392]
        totalSortout = {
        1 : 0,
        2 : 0
        }
        otherErrorStatuses = [1041, 1042, 2192, 4112, 4113, 5136, 6160]
        otherErrors = {
          1 : 0,
          2 : 0
        }
        commErrorSortout = {
        1 : 0,
        2 : 0
        }
        for row in results:
           carID = row['system_id']
           processID = row['process_status']
           data[carID] = {}
           data[carID][processID] = row['count']
           total[carID] += row['count']
           total[carID] += row['count']

           if row['process_status'] in sortoutStatuses + otherErrorStatuses:
               totalSortout[carID] += row['count']
           if(row['process_status'] < 0 or row['process_status'] == 4096):
                commErrorSortout[carID] += row['count']
        
        refData = {
            'total' : 0,
            "cylFilled" : 0,
            "totalSortout" : 0,
            "commErrorSortout" : 0
        }
        for id in [1,2]:
          refData['total'] += total[id]
          refData['cylFilled'] += total[id] - totalSortout[id]
          refData['totalSortout'] += totalSortout[id]
          refData['commErrorSortout'] += commErrorSortout[id]

        if refData['total'] :
            refData['sortOutPercentage'] = (refData['totalSortout'] / refData['total']) * 100
        else:
            refData['sortOutPercentage'] = 0
        
        return refData
    
    async def get_gd_rejection(data : dict):
          if not data.get("carousal", None):
            carousal = await LPGOperationsActions.get_carousals('string')
          processId = '3,23'
          if not data.get("cyl_types", None):
            cyl_types = ",".join(map(str, lpg_config.cyl_types))
          
          from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
          to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")

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

              data['sortOutPercentage'] = (data['sortout'] / data['handled']) * 100
              return data
          return False

    async def get_pt_rejection(data : dict):
          if not data.get("carousal", None):
            carousal = await LPGOperationsActions.get_carousals('string')
          processId = '4,24'
          if not data.get("cyl_types", None):
            cyl_types = ",".join(map(str, lpg_config.cyl_types))
          
          from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
          to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")

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

              data['sortOutPercentage'] = (data['sortout'] / data['handled']) * 100
              return data
          return False
    
    async def get_filling_accuracy_data(data :dict):
      cyl_types = ",".join(map(str, lpg_config.cyl_types))
      carousal = await LPGOperationsActions.get_carousals('string')
      from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
      to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")
      query = f"""
        SELECT
        system_id,
        MAX(sap_id) AS sap_id,
        SUM(CASE WHEN
                    ((cyl_type = 1) AND (check_net - 14200) = 0)
                    OR
                    ((cyl_type = 2) AND (check_net - 19000) = 0)
                  THEN 1
                  ELSE 0
            END) AS nil_var,
        SUM(CASE WHEN
                    ((cyl_type = 1) AND (check_net - 14200) > 0 AND (check_net - 14200) <= 50)
                    OR
                    ((cyl_type = 1) AND (check_net - 14200) < 0 AND (check_net - 14200) >= -50)
                    OR
                    ((cyl_type = 2) AND (check_net - 19000) > 0 AND (check_net - 19000) <= 50)
                    OR
                    ((cyl_type = 2) AND (check_net - 19000) < 0 AND (check_net - 19000) >= -50)
                  THEN 1
                  ELSE 0
            END) AS zero_fifty,
        SUM(CASE WHEN
                    ((cyl_type = 1) AND (check_net - 14200) > 50 AND (check_net - 14200) <= 100)
                    OR
                    ((cyl_type = 1) AND (check_net - 14200) < -50 AND (check_net - 14200) >= -100)
                    OR
                    ((cyl_type = 2) AND (check_net - 19000) > 50 AND (check_net - 19000) <= 100)
                    OR
                    ((cyl_type = 2) AND (check_net - 19000) < -50 AND (check_net - 19000) >= -100)
                  THEN 1
                  ELSE 0
            END) AS fifty_hundred,
        SUM(CASE WHEN
                    ((cyl_type = 1) AND (check_net - 14200) > 100 AND (check_net - 14200) <= 200)
                    OR
                    ((cyl_type = 1) AND (check_net - 14200) < -100 AND (check_net - 14200) >= -200)
                    OR
                    ((cyl_type = 2) AND (check_net - 19000) > 100 AND (check_net - 14200) <= 200)
                    OR
                    ((cyl_type = 2) AND (check_net - 19000) < -100 AND (check_net - 14200) >= -200)
                  THEN 1
                  ELSE 0
            END) AS hundred_plus,
        SUM(CASE WHEN ((check_net - 14200) >= -200 AND (check_net - 14200) <= 200) THEN (check_net - 14200)
         WHEN ((check_net - 14200) < -200) THEN -200
         WHEN ((check_net - 14200) > 200) THEN 200
         ELSE 0 END)/(COUNT(production_log_id)::float) AS average,
         COUNT(production_log_id) AS count,
        STDDEV_POP(CASE WHEN ((check_net - 14200) >= -200 AND (check_net - 14200) <= 200) THEN (check_net - 14200)
         WHEN ((check_net - 14200) < -200) THEN -200
         WHEN ((check_net - 14200) > 200) THEN 200
         ELSE 0 END) AS stddev
        FROM production_log
        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
          AND system_id IN ({carousal})
          AND process_id IN (2, 22)
          AND cyl_type IN ({cyl_types})
          AND process_status IN (0, 1040, 2064)
          AND sap_id = {data['sap_id']}
        GROUP BY system_id
        ORDER BY system_id ASC;
        """
      print(query)
      stats = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
      if stats['data']:
          stats = stats['data']

      if stats:
          return stats
      return False
    
    async def get_plant_id_by_shortName(plantShortName):
        query = f"""SELECT MAX(id) as id from public.plants where short_name = '{plantShortName}';"""
        result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if result['data']:
            plant_id = result['data']
            return plant_id[0]['id']
        else:
            return 0    
        
    async def get_Breaks(plant_id, carousal_id):
        query = f"""SELECT start_time, stop_time FROM public.breaks WHERE plant_id = {plant_id} AND carousal_id = {carousal_id};"""
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
    
    async def get_carousals_config(plantShortName):
        plant_id = await LPGOperationsActions.get_plant_id_by_shortName(plantShortName)

        query = f"""SELECT carousal_id, heads, rated_productivity, start_time, stop_time FROM public.carousals WHERE plant_id = {plant_id};"""
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
                    'breaks' : await LPGOperationsActions.get_Breaks( plant_id, row['carousal_id'])
                }
            }
        return config
    
    async def get_carousals(type : str):
        carousal_config = await LPGOperationsActions.get_carousals_config(lpg_config.plant_shortName)
        keys = list(carousal_config.keys())
        if type == 'string':
            return ", ".join(map(str, keys))
        if type == 'array':
            return  keys
        if type == 'full':
            return carousal_config
        else:
            return  ", ".join(map(str, list(carousal_config.keys())))
      
            

    async def get_bottling_summary(data : dict):
      excludedStatuses = ", ".join(map(str, lpg_config.process_statuses['negativeTare'] + lpg_config.process_statuses['positiveTare']))
      from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
      to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")
      carousal = await LPGOperationsActions.get_carousals('string')
      queryString = f"""SELECT
      system_id as carousal,
      SUM(CASE
        WHEN (cyl_type = 1)
        THEN 1
        ELSE 0
        END) AS production_14_2,
      SUM(CASE
        WHEN (cyl_type = 2)
        THEN 1
        ELSE 0
        END) AS production_19
      FROM production_log
      WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
        AND process_id IN (2,22)
        AND system_id IN ({carousal})
        AND cyl_type IN (1,2)
        AND process_status NOT IN ({excludedStatuses})
      GROUP BY system_id 
      ORDER BY system_id;"""
      

      data = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
      if data['data']:
          data = data['data']
      carousals = await LPGOperationsActions.get_carousals('array')
      result = {}

      if(data and (data[0]["production_14_2"] > 0 or data[0]["production_19"] > 0)):
        for d in data:
          for c in carousals:
            if c == d["carousal"]:
              result[c] = d 
        return result
      return None
    
    async def plant_info(data : dict):
        query = """
            SELECT plants.erp_id, plants.id, plants.plant_name, carousals.carousal_id,
            carousals.heads, carousals.rated_productivity,
            carousals.start_time, carousals.stop_time,
            breaks.start_time as break_start_time,
            breaks.stop_time as break_stop_time
            from plants
            JOIN carousals 
            ON plants.id = carousals.plant_id
            JOIN breaks
            ON carousals.plant_id = breaks.plant_id
            AND carousals.carousal_id = breaks.carousal_id 
            """
        
        if not data.get('sap_id' , None):
            query = query + "ORDER BY plants.id"
        else:
            query = query + f"WHERE plants.erp_id = {data['sap_id']}" + "ORDER BY plants.id"
                
        plant_data = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        if plant_data['data']:
            plant_data = plant_data['data']
        
        data = {}
        for plant in plant_data:
            if plant['id'] not in data:
                data[plant['id']] = {
                    'name' : plant['plant_name'],
                    'sap_id' : plant['erp_id'],
                    'carousal' : {}
                }
            if plant['carousal_id'] not in data[plant['id']]['carousal']:
                data[plant['id']]['carousal'][plant['carousal_id']] = {
                    'heads' : plant['heads'],
                     'stdOutput' : plant['rated_productivity'],
                    'times' : {
                        'start' : plant['start_time'],
                        'end' : plant['stop_time'],
                        'breaks' : [{
                            'start_time' : plant['break_start_time'],
                            'stop_time' : plant['break_stop_time']

                        }]
                }
                }
            elif plant['carousal_id'] in data[plant['id']]['carousal']:
                data[plant['id']]['carousal'][plant['carousal_id']]['times']['breaks'].append(
                    {
                        'start_time' : plant['break_start_time'],
                        'stop_time' : plant['break_stop_time']
                    }
                )
        return data
    
    async def config_to_phases(config):
        phases = {}
        for key, value in config.items():
            start = value['times']['start']
            end = value['times']['end']
            breaks = value['times']['breaks']

            working_periods = []
            break_periods = []
            overtime_periods = []

            current_start = start

            for b in breaks:
                break_start = b['from']
                break_end = b['to']
                if current_start < break_start:
                    working_periods.append({
                        'from': current_start,
                        'to': break_start
                    })
                break_periods.append(b)
                current_start = break_end

            if current_start < end:
                working_periods.append({
                    'from': current_start,
                    'to': end
                })

            overtime_periods.append({
                'from': '00:00:00',
                'to': start
            })
            overtime_periods.append({
                'from': end,
                'to': '23:59:59'
            })

            phases[key] = {
                'working': working_periods,
                'breaks': break_periods,
                'overtime': overtime_periods
            }

        return phases

    async def get_phases():
        plant = lpg_config.plant_shortName
        carousal_config = await LPGOperationsActions.get_carousals_config(plant)
        if carousal_config is None:
            raise Exception("Error Processing Request")
        phases = await LPGOperationsActions.config_to_phases(carousal_config)
        return phases

    # getDailyOperatingHours
    async def get_daily_operating_hours():
        phases = await LPGOperationsActions.get_phases()
        operating_time = {}

        for key,value in phases.items():
            totalWorkingSeconds = 0
            totalBreakSeconds = 0

            for working_period in value['working']:
                from_date = datetime.strptime(f'{working_period['from']}', "%H:%M:%S" )
                to_date = datetime.strptime(f'{working_period['to']}', "%H:%M:%S")
                interval =  to_date - from_date
                interval = interval.total_seconds()
                totalWorkingSeconds += interval
            
            for break_period in value['breaks']:
                from_date = datetime.strptime(f'{break_period['from']}', "%H:%M:%S" )
                to_date = datetime.strptime(f'{break_period['to']}', "%H:%M:%S")
                interval =  to_date - from_date
                interval = interval.total_seconds()
                totalBreakSeconds += interval

            totalWorkingHours = totalWorkingSeconds / 3600
            totalBreakHours = totalBreakSeconds / 3600
            operating_time[key] = {
            'normal' : totalWorkingHours,
            'break' : totalBreakHours,
              }
        return  operating_time
    
    async def build_production_gap_query(carousal, phases, from_date, to_date):
        minInterruption = lpg_config.min_interruption

        normalGapStringArray = []
        normalGapString = ""
        for working_phase in phases['working']:
            normalGapStringArray.append(f"""getGapBetweenTimes(process_time, prev_process_time, '{working_phase['from']}'::text, '{working_phase['to']}'::text)""")
        normalGapString = " + ".join(normalGapStringArray)

        breakGapStringArray = []
        breakGapString = ""
        for break_phase in phases['breaks']:
            breakGapStringArray.append(f"""getGapBetweenTimes(process_time, prev_process_time, '{break_phase['from']}'::text, '{break_phase['to']}'::text)""")
        breakGapString = " + ".join(breakGapStringArray)

        overtimeGapStringArray = []
        overtimeGapString = ""
        for over_time_phase in phases['overtime']:
            overtimeGapStringArray.append(f"""(process_time::time between '{over_time_phase['from']}'::time and '{over_time_phase['to']}'::time and prev_process_time:: time between '{over_time_phase['from']}'::time and '{over_time_phase['to']}'::time )""")
        overtimeGapString = " or ".join(overtimeGapStringArray)

        normalEndGapStringArray = []
        normalEndGapString = ""
        for normal_end_phase in phases['working']:
            normalEndGapStringArray.append(f"""getEndGapForPhase(last_cyl_time, '{normal_end_phase['from']}', '{normal_end_phase['to']}')""")
        normalEndGapString = " + ".join(normalEndGapStringArray)

        breakEndGapStringArray = []
        breakEndGapString = ""
        for break_end_phase in phases['breaks']:
            breakEndGapStringArray.append(f"""getEndGapForPhase(last_cyl_time, '{break_end_phase['from']}', '{break_end_phase['to']}')""")
        breakEndGapString = " + ".join(breakEndGapStringArray)

        queryString  = f"""WITH day_wise_data as (
                select
                process_date::date as process_day,
                to_char(process_date, 'HH24:MI:SS.MS') as process_time,
                process_date,
                system_id,
                process_status,
                cyl_type,
                production_log_id
                FROM
                production_log
                    where process_date between '{from_date} 00:00:00' and '{to_date} 23:59:59.999'
                    AND process_id IN (2,22)
                    AND cyl_type IN (1,2)
                    and system_id = {carousal}
                    order by production_log_id asc
            ),
            time_gaps as ( 
                select
                process_day,
                    production_log_id,
                    system_id,
                    process_date,
                    process_time,
                    LAG(process_time) OVER (PARTITION BY system_id, process_day ORDER BY process_time) AS prev_process_time
                FROM day_wise_data
            ),
            grouped_gaps as (
                select 
                    process_day,
                    system_id,
                    process_time,
                    prev_process_time,
                    case 
                        when prev_process_time is not null and ({overtimeGapString})
                        then process_time:: time - prev_process_time:: time
                    else '0 seconds'::interval
                    end as overtime_gap,
                    {breakGapString} as break_gap,
                    {normalGapString} as normal_gap
                from
                time_gaps
            ),
            last_cyl_data as (
                select
                process_day,
                MAX(process_time::time) as last_cyl_time
                from
                day_wise_data
                group by process_day		
            ),
            end_gap_data as ( 
                select 
                process_day,
                last_cyl_time,
                {normalEndGapString} as normal_end_gap,
                {breakEndGapString} as break_end_gap
                from
                last_cyl_data
            ),
            process_days as (
                select 
                    distinct process_day 
                from day_wise_data
            ),
            intervening_gaps_data as (
                SELECT 
                    pd.process_day,
                    COALESCE(SUM(gg.break_gap), interval '0') AS total_break_gap,
                    COALESCE(SUM(gg.normal_gap), interval '0') AS total_normal_gap,
                    COALESCE(SUM(gg.overtime_gap), interval '0') AS total_overtime_gap
                FROM
                    process_days pd
                LEFT JOIN grouped_gaps gg
                    ON pd.process_day = gg.process_day
                    AND (gg.break_gap + gg.normal_gap + gg.overtime_gap) > '{minInterruption} seconds'::interval
                GROUP BY pd.process_day
            )
            select  
                EXTRACT(EPOCH from sum(igd.total_normal_gap + egd.normal_end_gap)) / 3600 as total_normal_gap,
                EXTRACT(EPOCH from sum(igd.total_break_gap + egd.break_end_gap)) / 3600 as total_break_gap,
                EXTRACT(EPOCH FROM sum(igd.total_overtime_gap)) / 3600 as total_overtime_gap
            from intervening_gaps_data igd 
            left join end_gap_data egd on igd.process_day = egd.process_day;"""

        return queryString
    
    async def get_gap_between_times_function_create_string():
      queryString  = f"""CREATE OR REPLACE FUNCTION getGapBetweenTimes(process_time TEXT, prev_process_time text, start_time text, end_time TEXT)
      RETURNS INTERVAL AS $$
      begin
        return case 
          when prev_process_time is null 
            then case 
              when process_time::time <= start_time::time
                then '0 seconds'::interval
              when process_time::time >= end_time::time
                then end_time::time - start_time::time
              else process_time::time - start_time::time
            end
          WHEN process_time::time > end_time::time AND prev_process_time::time > end_time::time 
              THEN  '0 seconds'::interval
              WHEN process_time::time < start_time::time AND prev_process_time::time < start_time::time 
              THEN  '0 seconds'::interval
              WHEN prev_process_time::time >= start_time::time AND process_time::time <= end_time::time 
              THEN  process_time::time - prev_process_time::time
              WHEN prev_process_time::time < start_time::time AND process_time::time > end_time::time 
              THEN  end_time::time - start_time::time
              WHEN prev_process_time::time < start_time::time AND process_time::time between start_time::time and end_time::time 
              THEN  process_time::time - start_time::time
              WHEN process_time::time > end_time::time AND prev_process_time::time between start_time::time and end_time::time 
              THEN  end_time::time - prev_process_time::time
            ELSE '2 days'::interval
          END;
      END;
      $$ LANGUAGE plpgsql;"""

      return queryString
    
    async def get_end_gap_function_create_string():
        queryString  = f"""CREATE OR REPLACE FUNCTION getEndGapForPhase(last_cyl_time TIME, phase_start text, phase_end text)
            RETURNS INTERVAL AS $$
            begin
                return case 
                WHEN last_cyl_time < phase_start::time 
                    THEN  phase_end::time - phase_start::time 
                    WHEN last_cyl_time > phase_end::time
                    THEN  '0 seconds'::interval
                    WHEN last_cyl_time between phase_start::time and phase_end::time
                    THEN  phase_end::time - last_cyl_time
                    ELSE '0 seconds'::interval
                END;
            END;
            $$ LANGUAGE plpgsql;"""
        return queryString
    
    async def get_production_gaps(carousal, from_date, to_date):
      phases = await LPGOperationsActions.get_phases()
      queryString = await LPGOperationsActions.build_production_gap_query(carousal, phases[carousal], from_date, to_date)
    #   gapBetweenTimesFunctionCreateString = await LPGOperationsActions.get_gap_between_times_function_create_string()
    #   endGapFunctionCreateString = await LPGOperationsActions.get_end_gap_function_create_string()
    #   query1 = await urdhva_base.BasePostgresModel.get_aggr_data(gapBetweenTimesFunctionCreateString, limit=0)
    #   query2 = await urdhva_base.BasePostgresModel.get_aggr_data(endGapFunctionCreateString, limit=0)
      query3 = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
      if query3['data']:
          query3 = query3['data']
      return query3[0]

    async def get_non_operating_days(carousal, from_date, to_date):
        queryString = F"""WITH all_dates AS (
                      SELECT generate_series('{from_date}'::date, '{to_date}'::date, '1 day'::interval) AS process_day),
                        row_counts AS (
                            SELECT
                                process_date::date AS process_day,
                                COUNT(*) AS row_count
                            FROM
                                production_log
                            WHERE
                                process_date BETWEEN '{from_date} 00:00:00' AND '{to_date} 23:59:59'
                                AND system_id = {carousal}
                                AND process_id IN (1,2,22)
                                AND process_status NOT IN (16)
                            GROUP BY
                                process_date::date
                        ),
                        empty_days as (
                          SELECT
                              ad.process_day as days,
                              COALESCE(rc.row_count, 0) AS row_count
                          FROM
                              all_dates ad
                          LEFT JOIN
                              row_counts rc ON ad.process_day = rc.process_day
                          WHERE
                              COALESCE(rc.row_count, 0) < 1
                        )
                        select count(days) from empty_days;"""
        data = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
        if data['data']:
            data = data['data']

        if(data and len(data) > 0):
            return data[0]['count']
        return 0

    
    # getProductionGapsForAllCarousals
    async def get_production_gaps_for_all_carousals(data: dict):
        from_date = datetime.strptime(f"{data['from_date']}", "%Y-%m-%d").date()
        to_date = datetime.strptime(f"{data['to_date']}","%Y-%m-%d").date()
        if from_date > to_date:
            return False
        interval_days = (to_date - from_date).days
        total_intervening_days = interval_days + 1
        carousalsArray = await LPGOperationsActions.get_carousals("array")
        dailyOperatingHours = await LPGOperationsActions.get_daily_operating_hours()

        data = {}
        for carousal in carousalsArray: 
            data[carousal] = await LPGOperationsActions.get_production_gaps(carousal, from_date, to_date)
            data[carousal]['carousal'] = carousal
            data[carousal]['intervening_days'] = total_intervening_days
            data[carousal]['non_op_days'] = await LPGOperationsActions.get_non_operating_days(carousal, from_date, to_date)
            data[carousal]['net_op_days'] = total_intervening_days - data[carousal]['non_op_days']
            data[carousal]['daily_op_hours'] = dailyOperatingHours[carousal]
            data[carousal]['max_op_hours']= {}
            data[carousal]['max_op_hours']['normal'] = dailyOperatingHours[carousal]['normal'] * data[carousal]['net_op_days']
            data[carousal]['max_op_hours']['break'] = dailyOperatingHours[carousal]['break'] * data[carousal]['net_op_days']
            data[carousal]['net_op_hours'] = {}
            data[carousal]['net_op_hours']['normal'] = Decimal(data[carousal]['max_op_hours']['normal']) - data[carousal]['total_normal_gap']
            data[carousal]['net_op_hours']['break'] = Decimal(data[carousal]['max_op_hours']['break']) - data[carousal]['total_break_gap']
        return data
    
    async def get_phased_production_data_query_string(carousal, from_date, to_date):
        excludedStatuses = ", ".join(map(str, lpg_config.process_statuses['negativeTare'] + lpg_config.process_statuses['positiveTare']))
        phases = await LPGOperationsActions.get_phases()
        normalPhaseStringArray = []
        normalPhaseString = ""
        for working_phase in phases[carousal]['working']:
            normalPhaseStringArray.append(f"""process_date::time between '{working_phase['from']}'::time and '{working_phase['to']}'::time""")
        normalPhaseString = " or ".join(normalPhaseStringArray)
      
        breakPhaseStringArray = []
        breakPhaseString = ""
        for break_phase in phases[carousal]['breaks']:
            breakPhaseStringArray.append(f""" process_date::time between '{break_phase['from']}'::time and '{break_phase['to']}'::time """)
        breakPhaseString = " or ".join(breakPhaseStringArray)
    
        queryString = f"""WITH phased_data as (
                    select 
                    *,
                    case 
                        when {normalPhaseString}
                        then 'normal'
                        when {breakPhaseString} 
                        then 'break'
                        else 'overtime'
                    end as phase
                    from
                    production_log
                    where 
                    process_date between '{from_date} 00:00:00' and '{to_date} 23:59:59.999'
                    and process_id in (2, 22)
                    AND process_status NOT IN ({excludedStatuses})
                    and system_id = {carousal}
                )
                select 
                    phase,
                    sum(
                    case 
                        when cyl_type = 1 then 1 else 0
                    end 
                    ) as prod_14_2,
                    sum(
                    case 
                        when cyl_type = 2 then 1 else 0
                    end 
                    ) as prod_19
                from 
                    phased_data
                group by phase;"""

        return queryString

    async def get_phase_wise_production(carousal, from_date, to_date):
        phases = await LPGOperationsActions.get_phases()
        queryString = await LPGOperationsActions.get_phased_production_data_query_string(carousal, from_date, to_date)
        data = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
        if data['data']:
            data = data['data']
        blankProdData = {
        'prod_14_2':0,
        'prod_19':0}

        returnData = {
        'normal':blankProdData,
        'break':blankProdData,
        'overtime':blankProdData}

        for phase_data in data:
            returnData[phase_data['phase']] = phase_data
     
        return returnData
    
    async def get_start_end_times(carousal):
        plant = lpg_config.plant_shortName
        carousal_config = await LPGOperationsActions.get_carousals_config(plant)
        if carousal_config is None:
            raise Exception("Error Processing Request", 1)
        return {
        'start' : carousal_config[carousal]['times']['start'],
        'end' : carousal_config[carousal]['times']['end']
        }

    async def build_ot_production_period_query(carousal, from_date, to_date):
        startEndTimes = await LPGOperationsActions.get_start_end_times(carousal)
        startTime = startEndTimes['start']
        endTime = startEndTimes['end']
        queryString  = f"""WITH day_wise_data as (
                select
                process_date::date as process_day,
                to_char(process_date, 'HH24:MI:SS.MS') as process_time,
                process_date
                FROM
                production_log
                    where process_date between '{from_date} 00:00:00' and '{to_date} 23:59:59.999'
                    AND process_id IN (2, 22)
                    AND cyl_type IN (1, 2)
                    and system_id = {carousal}
                    order by production_log_id asc
            ),
            pre_shift_ot_periods as (
                select 
                process_day,
                max(process_time::time) - min(process_time::time) as production_time
                from 
                day_wise_data
                where 
                process_time::time between '00:00:00'::time and '{startTime}'::time
                group by process_day
            ),
            post_shift_ot_periods as (
                select 
                process_day,
                max(process_time::time) - min(process_time::time) as production_time
                from 
                day_wise_data
                where 
                process_time::time between '{endTime}'::time and '23:59:59.999'::time
                group by process_day
            )
            select 
                EXTRACT(EPOCH from (select sum(production_time) from pre_shift_ot_periods)) / 3600 as total_pre_shift_time,
                EXTRACT(EPOCH from (select sum(production_time) from post_shift_ot_periods)) / 3600 as total_post_shift_time;"""

        return queryString
    
    async def get_phase_wise_production_for_all_carousals(data : dict):
        from_date = datetime.strptime(f"{data['from_date']}", "%Y-%m-%d").date()
        to_date = datetime.strptime(f"{data['to_date']}","%Y-%m-%d").date()
        carousalsArray = await LPGOperationsActions.get_carousals("array")
        data = {}
        for carousal in carousalsArray:
            prodData = await LPGOperationsActions.get_phase_wise_production(carousal, from_date, to_date)
            data[carousal] = prodData
        return data
    
    async def get_ot_production_period(carousal, from_date, to_date):
        queryString = await LPGOperationsActions.build_ot_production_period_query(carousal, from_date, to_date)
        data = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
        if data['data']:
            data = data['data']
        return data[0]
        
    async def get_ot_production_period_for_all_carousals(data:dict):
        from_date = datetime.strptime(f"{data['from_date']}", "%Y-%m-%d").date()
        to_date = datetime.strptime(f"{data['to_date']}","%Y-%m-%d").date()
        carousalsArray = await LPGOperationsActions.get_carousals("array")
        data = {}
        for carousal in carousalsArray: 
            data[carousal] = await LPGOperationsActions.get_ot_production_period(carousal, from_date, to_date)
        return data
    
    async def calculate_productivity_v2(bottlingData, productionHoursData, otProductionTime):
    #   $productionHoursData2 = $productionLogModel->getProductionGapsForAllCarousals($fromDate, $toDate);
    #   $otProductionTime = $productionLogModel->getOtProductionPeriodForAllCarousals($fromDate, $toDate);
    #   $bottlingData2 = $productionLogModel->getPhaseWiseProductionForAllCarousals($fromDate, $toDate);
        phases = ['normal', 'break', 'overtime']
        productivityData = {}
        for key , value in bottlingData.items():
            for phase in phases:
                totalProduction = bottlingData[key][phase]['prod_14_2'] + 1.25 * bottlingData[key][phase]['prod_19']
                gapHours = productionHoursData[key]["total_" + phase + "_gap"]
                if key not in productivityData:
                     productivityData[key] = {}
                productivityData[key][phase]={}
                if phase != 'overtime':                                        
                    maxHours = productionHoursData[key]['max_op_hours'][phase]
                    productivityData[key][phase]['net_hours'] =  Decimal(maxHours) - gapHours
                else:
                    if otProductionTime[key]['total_post_shift_time'] is None:
                        total_post_shift_time = 0
                    else:
                        total_post_shift_time = otProductionTime[key]['total_post_shift_time']                    
                    productivityData[key][phase]['net_hours'] =  otProductionTime[key]['total_pre_shift_time'] + total_post_shift_time - gapHours
                productivityData[key][phase]['total_production'] =  totalProduction
                if not (productivityData[key][phase]['net_hours']):
                    productivityData[key][phase]['productivity'] =  0
                else:
                    productivityData[key][phase]['productivity'] =  Decimal(totalProduction) / productivityData[key][phase]['net_hours']
        return productivityData
    
    async def hourly_production_data(from_day, to_day):
        # from_day = datetime.strptime(f"{data['day']} 00:00:00", "%Y-%m-%d %H:%M:%S")
        # to_day = datetime.strptime(f"{data['day']} 23:59:59", "%Y-%m-%d %H:%M:%S")


        cyl_type = ", ".join(map(str, lpg_config.cyl_types))
        carousal = await LPGOperationsActions.get_carousals('string')
        excludedStatuses = ", ".join(map(str, lpg_config.process_statuses['negativeTare'] + lpg_config.process_statuses['positiveTare']))
        queryString = f"""SELECT
                DATE_TRUNC('hour', process_date) as hour,
                SUM(CASE WHEN (system_id = 1 AND cyl_type = 1) THEN 1 ELSE 0 END) AS c1_t1,
                SUM(CASE WHEN (system_id = 1 AND cyl_type = 2) THEN 1 ELSE 0 END) AS c1_t2,
                SUM(CASE WHEN (system_id = 2 AND cyl_type = 1) THEN 1 ELSE 0 END) AS c2_t1,
                SUM(CASE WHEN (system_id = 2 AND cyl_type = 2) THEN 1 ELSE 0 END) AS c2_t2
                FROM production_log
                WHERE process_date BETWEEN '{from_day}' AND '{to_day}'
                AND process_id IN (2,22)
                AND system_id IN ({carousal})
                AND cyl_type IN ({cyl_type})
                AND process_status NOT IN ({excludedStatuses})
                GROUP BY DATE_TRUNC('hour', process_date)
                ORDER BY hour ASC;"""
        stats = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
        if stats['data']:
            return stats['data']
        return False

    async def get_hourly_production_data(data : dict):
        from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
        to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")

        rawData = await LPGOperationsActions.hourly_production_data(from_date, to_date)
        data = {
            1 : [],
            2 : [],
            'labels' : [],
            'total1' : 0,
            'total2' : 0
        }
        if len(rawData) == 0:
            return data
        labels = []
        car1Data = []
        car2Data = []
        total1 = 0
        total2 = 0

        for row in rawData:
            timeLow = row['hour']
            timeHigh = row['hour'] + timedelta(hours=1)
            label = timeLow.strftime('%H') + '00 - ' + timeHigh.strftime('%H') + '00'
            labels.append(label)
            count1 = math.floor(row['c1_t1'] + 0.5)
            count2 = math.floor(row['c2_t2'] + 0.5)
            total1 += count1
            total2 += count2
            car1Data.append(count1)
            car2Data.append(count2)

        data['labels'] = labels
        data['total1'] = total1
        data['total2'] = total2
        data[1] = car1Data
        data[2] = car2Data

        return data
    
    async def get_periodic_production(from_date, to_date, carousal, cyl_type, period):
        carousal = ", ".join(map(str, carousal)) 
        cyl_types = ", ".join(map(str, cyl_type))
        queryString = f"""SELECT
        date_trunc('hour', process_date) + (((date_part('minute', process_date)::integer / {period}::integer) * {period}::integer) || ' minutes')::interval AS period_start,
        SUM(CASE WHEN (system_id = 1 AND cyl_type = 1) THEN 1 ELSE 0 END) AS c1_t1,
        SUM(CASE WHEN (system_id = 1 AND cyl_type = 2) THEN 1 ELSE 0 END) AS c1_t2,
        SUM(CASE WHEN (system_id = 2 AND cyl_type = 1) THEN 1 ELSE 0 END) AS c2_t1,
        SUM(CASE WHEN (system_id = 2 AND cyl_type = 2) THEN 1 ELSE 0 END) AS c2_t2
         FROM production_log
        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
          AND process_id IN (2, 22)
          AND system_id IN ({carousal})
          AND cyl_type IN ({cyl_types})
          AND process_status NOT IN (5454545454545)
        GROUP BY period_start
        ORDER BY period_start ASC;"""
        stats = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit = 0)
        if stats['data']:
          return stats['data']
        
        return False
    
    async def get_hourly_production_table_data(data : dict):
        from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
        to_date = datetime.strptime(f"{data['to_date']} 23:59:59", "%Y-%m-%d %H:%M:%S")
        interval = data.get("interval", 60)
        carousal = await LPGOperationsActions.get_carousals('string')
        cyl_types = ", ".join(map(str,lpg_config.cyl_types))
        qData = await LPGOperationsActions.get_periodic_production(from_date, to_date, [1,2], [1,2], interval)
        
        if len(qData) == 0:
            data = {
            'status' : 'success',
            'message' : 'No data found!',
            'tabledata' : []
            }
            return data

        showDate = False
        
        if from_date != to_date:
            showDate = True
        
        if qData:
            prodData = {}
            for key, row in enumerate(qData):
                prodData[key] = {}
                prodData[key]['from'] = row['period_start'].strftime("%Y-%m-%d %H:%M") if showDate else row['period_start'].strftime("%H:%M")
                period_end = row['period_start'] + timedelta(minutes=interval)
                prodData[key]['to'] = (period_end.strftime("%Y-%m-%d %H:%M") if showDate else period_end.strftime("%H:%M"))       
                prodData[key]['c1_t1'] = row['c1_t1']
                prodData[key]['c1_t2'] = row['c1_t2']
                prodData[key]['c1_total'] = row['c1_t2'] + row['c1_t1']
                prodData[key]['c2_t1'] = row['c2_t1']
                prodData[key]['c2_t2'] = row['c2_t2']
                prodData[key]['c2_total'] = row['c2_t1'] + row['c2_t2']
        data = {
            'status' : 'success',
            'message' : 'data fetched successfully',
            'tabledata' : prodData
        }

        return prodData
    async def get_scales_filling_count(from_date, to_date):
    #   public function getScalesFillingCount($from = NULL, $to = NULL, $carousal = NULL)
      
    #   day = day??date('Y-m-d', time());
    #   $cyl_types = implode(", ", [1, 2]);
    #   $carousal = implode(", ", $carousal??[1, 2]);

    #   $from = date('Y-m-d H:i:s', $from??strtotime("-4 hours"));
    #   $to = date('Y-m-d H:i:s', $to??time());
        carousalArray = [1, 2]
        carousal = await LPGOperationsActions.get_carousals('string')
        cyl_types = ", ".join(map(str, lpg_config.cyl_types))
        excludedStatuses = ", ".join(map(str, lpg_config.process_statuses['negativeTare'] + lpg_config.process_statuses['positiveTare']))
        queryString = f"""SELECT
        system_id,
        machine_id,
        device_id,
        COUNT(production_log)
         FROM production_log
        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
          AND process_id IN (2, 22)
          AND system_id IN ({carousal})
          AND cyl_type IN ({cyl_types})
          AND process_status NOT IN ({excludedStatuses})
        GROUP BY machine_id, system_id, device_id
        ORDER BY system_id ASC, machine_id ASC;"""

        rawData = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit = 0)
        rawData = rawData['data']

        queryString2 = f"""SELECT (SELECT process_date
            FROM production_log
              WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
              AND process_id IN (2,22)
              AND system_id IN ({carousal})
              AND cyl_type IN ({cyl_types})
              AND process_status NOT IN ({excludedStatuses})
              ORDER BY process_date DESC
              LIMIT 1
            ) AS last_cyl_time,
            (SELECT process_date
            FROM production_log
              WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
              AND process_id IN (2, 22)
              AND system_id IN ({carousal})
              AND cyl_type IN ({cyl_types})
              AND process_status NOT IN ({excludedStatuses})
              ORDER BY process_date ASC
              LIMIT 1
              ) AS first_cyl_time,
               system_id
              FROM production_log
                WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                AND process_id IN (2, 22)
                AND system_id IN ({carousal})
                AND cyl_type IN ({cyl_types})
                AND process_status NOT IN ({excludedStatuses})
                GROUP BY system_id
                LIMIT 2;"""
        metaData2 = await urdhva_base.BasePostgresModel.get_aggr_data(queryString2, limit = 0)
        metaData2 = metaData2['data']

        queryString3 = f"""SELECT 
            MIN(process_date) as first_cyl_time,
            MAX(process_date) as last_cyl_time,
            system_id
            FROM production_log
              WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
              AND process_id IN (2, 22)
              AND system_id IN ({carousal})
              AND cyl_type IN ({cyl_types})
              AND process_status NOT IN ({excludedStatuses})
              GROUP BY system_id
              LIMIT 2;"""
        metaData = await urdhva_base.BasePostgresModel.get_aggr_data(queryString3, limit = 0)
        metaData = metaData['data']
        if len(rawData) == 0 and len(metaData) == 0 and len(metaData2) == 0:
            return {
                'rawData' : [],
                'meta' : [],
                'metaData' : []
            }   
        metaDataArray = {}
        if len(rawData)>0:
          if len(metaData ) > 0:
            for row in metaData:
                for c in carousalArray:
                    if row['system_id'] == c:
                        metaDataArray[c] = {
                        "first_cyl_time"  : row['first_cyl_time'],
                        "last_cyl_time"   : row['last_cyl_time']
                        }
            return {
                'rawData' : rawData,
                'meta' : metaData2[0],
                'metaData' : metaDataArray
            }
        return False

    async def get_scales_efficiencies(from_date, to_date, carousal=[1,2]):
        # getScalesEfficiencies
        # from_date = datetime.strptime(f"{from_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
        # to_date = datetime.strptime(f"{to_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
        raw_data = await LPGOperationsActions.get_scales_filling_count(from_date, to_date)
                
        if not raw_data :
            data = {
                'row' : [],
                'meta' : {
                    'car1Eff' : 0,
                    'car2Eff' : 0
                }
            }
            return data
        meta_data = raw_data['metaData']
        raw_data = raw_data['rawData']
        intervals = {}

        for c in carousal:
            if c in meta_data and meta_data[c] is not None:
                intervals[c] = min(to_date - from_date, meta_data[c]['last_cyl_time'] - meta_data[c]['first_cyl_time'])
                intervals[c] = intervals[c].total_seconds()
        # carousal_config = config.carousalConfig
        carousal_config = await LPGOperationsActions.get_carousals('full')
        carousal_config[lpg_config.plant_shortName] = carousal_config
        carSpeed = lpg_config.carousalSpeed
        plant = lpg_config.plant_shortName
        # return intervals
        if plant in carousal_config and carousal_config[lpg_config.plant_shortName] is not None:
            stdOutput = {}
            for c in carousal:
                if c in meta_data and meta_data[c] is not None:
                    if c in carousal_config[plant] and carousal_config[plant][c] is not None:
                        stdOutput[c] = carousal_config[plant][c]["stdOutput"]*(intervals[c] / 60 / 60) / carousal_config[plant][c]["heads"]
                    else:
                        stdOutput[c] = 0
                else:
                    stdOutput = {
                        1 : 1 / carSpeed[1] * intervals[1],
                        2 : 1 / carSpeed[2] * intervals.get(2, 0)
                    }

        overallCount = {
        1 : 0,
        2 : 0
        }
        if len(raw_data) > 0:
            for row in raw_data:
                plantsWithDeviceId = lpg_config.plantsWithDeviceId
                if plant in plantsWithDeviceId:
                    row['scale'] = row['device_id']
                else:
                    row['scale'] = row['machine_id']
                row['carousal'] = row['system_id']
                row['efficiency'] = row['count']/stdOutput[row['system_id']]
                row['stdOutput'] = stdOutput[row['system_id']]
                row['interval'] = intervals[row['system_id']]
                overallCount[row['system_id']] += row['count']
        
            if plant in carousal_config and  carousal_config[plant] is not None:
                overallEfficiency = {
                'car1Eff' : 0,
                'car2Eff' : 0
                }
                for c in carousal:
                    if c in meta_data and meta_data[c] is not None:
                        if c in carousal_config[plant] and carousal_config[plant][c] is not None:
                            overallEfficiency[f'car{c}Eff'] = (overallCount[c] / stdOutput[c]) * carousal_config[plant][c]["heads"]
                        else:
                            overallEfficiency[f'car{c}Eff'] = 0

            else: 
                overallEfficiency = {
            'car1Eff' : (overallCount[1] / (stdOutput[1]) * 24),
            'car2Eff' : (overallCount[2] / (stdOutput[2]) * 24) 
            }
            data = {
          'rows' : raw_data,
          'meta' : overallEfficiency,
            }

            return data
        return False
    
    async def get_under_performing_scales(data : dict):
        row_count = data.get('row_count', 10)
        if data['from_date'] and data['to_date']:
            from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
            to_date = datetime.strptime(f"{data['to_date']} 23:59:59", "%Y-%m-%d %H:%M:%S")
            # if data['period'] == 0:
            #     from_time =  datetime.combine(datetime.today().date(), datetime.min.time())
            # else:
            data = await LPGOperationsActions.get_scales_efficiencies(from_date, to_date)
        if data is None:
            data['rows'] = []
            data['meta'] = {
                'car1Eff' : 0,
                'car2Eff' : 0
            }
        data['rows'].sort(key=lambda x: x["efficiency"])
        data['rows'] = data['rows'][:row_count]

        return data
      

 
data = {
    "from_date" : "2025-08-01",
    "to_date" : "2025-08-20",
    "sap_id" : 2330,
    "day" : "2025-08-05",
    "row_count" : 10
}


async def main(data):
    # print("gd_rejection")
    # gd_rejection = await LPGOperationsActions.get_gd_rejection(data= data )
    # print(gd_rejection)
    # print()
    # print("pt_rejection")
    # pt_rejection = await LPGOperationsActions.get_pt_rejection(data= data )
    # print(pt_rejection)
    # print()
    # print("filling_accuracy_data")
    # filling_accuracy_data = await LPGOperationsActions.get_filling_accuracy_data(data =data)
    # print(filling_accuracy_data)
    # print()
    # print("bottling summary")
    # bottling_summary = await LPGOperationsActions.get_bottling_summary(data =data)
    # print(bottling_summary)
    # print()    
    # plant_data = await LPGOperationsActions.plant_info(data)
    # print(plant_data)
    # print()
    # print("cs rejection data")
    # cs_data = await LPGOperationsActions.get_check_scale_rejection_report(data)
    # print(cs_data)
    # print()

    # cs_data2 = await LPGOperationsActions.get_check_scale_rejection_summary(data)
    # print(cs_data2)
    # print()
    # # $productionHoursData2 = $productionLogModel->getProductionGapsForAllCarousals($fromDate, $toDate);
    # # $otProductionTime = $productionLogModel->getOtProductionPeriodForAllCarousals($fromDate, $toDate);
    # # $bottlingData2 = $productionLogModel->getPhaseWiseProductionForAllCarousals($fromDate, $toDate);
    
    # #productivity
    # print("production gaps for all carousals")
    # productionHoursData2 = await LPGOperationsActions.get_production_gaps_for_all_carousals(data)
    # print(productionHoursData2)
    # print()
    # print("get phase wise production for all carousals")
    # bottlingData2 = await LPGOperationsActions.get_phase_wise_production_for_all_carousals(data)
    # print(bottlingData2)
    # print()
    # print("get ot production period for all carousals")    
    # otProductionTime = await LPGOperationsActions.get_ot_production_period_for_all_carousals(data)
    # print(otProductionTime)
    # print()
    # print('productivity')
    # productivity = await LPGOperationsActions.calculate_productivity_v2(bottlingData2, productionHoursData2, otProductionTime)
    # print(productivity)

    # print('hourly production')
    hrly_prod = await LPGOperationsActions.get_hourly_production_data(data)
    print(hrly_prod)
    # print()
    print('hourly production table data')
    prod_table_data = await LPGOperationsActions.get_hourly_production_table_data(data)
    print(prod_table_data)
    # print('scales efficiency')
    # scale_efficiency = await LPGOperationsActions.get_under_performing_scales(data)
    # print(scale_efficiency)
    
asyncio.run(main(data))