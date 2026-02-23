import urdhva_base
import math
import sys
import asyncio
import numpy as np
import traceback
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from orchestrator.dbconnector.widget_actions import lpg_config
from utilities.helpers import calculate_productivity
import math
import glob
import re
import numpy as np
import traceback
import polars as pl
import os



class LPGOperationsActions:
    async def plants_dropdown(data: dict):
        query = """ select * from lpg_plant_operations_masters """
        try:
            result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)

            plants = []
            zones = set()
            regions = set()

            if result and "data" in result and result["data"]:
                for row in result["data"]:
                    plants.append({
                        "sap_id": str(row["sap_id"]),
                        "plant": row["plant_name"]
                    })
                    if not row["zone"] is None:
                        zones.add(row["zone"])
                    if not row["region"] is None:
                        regions.add(row["region"])

            return {
                "status": True,
                "message": "Success",
                "data": {
                    "plant": plants,
                    "zone": list(zones),
                    "region": list(regions),
                    "carousel_type": ["12H", "24H", "48H", "72H"]
                }
            }

        except Exception:
            print("Exception in plants_dropdown")
            print("traceback :", traceback.format_exc())

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
        try:
            from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
            to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")

            if not data.get("carousal", None):
                carousal = await LPGOperationsActions.get_carousals('string', data.get("sap_id"))
                processId = '3,23'

            query = f"""SELECT
                            system_id,
                            process_status,
                            COUNT(event_log_id)
                        FROM event_log
                        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                            AND system_id IN ({carousal})
                            AND process_id IN ({processId})
                            AND sap_id = {data['sap_id']}
                        GROUP BY  process_status, system_id """
            
            results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
            if results['data']:
                results = results['data']
            else:
                return {}

            if results:
                carousal_wise_data = {}

                for row in results:
                    sys_id = row['system_id']
                    if sys_id not in carousal_wise_data:
                        carousal_wise_data[sys_id] = {
                            'handled': 0,
                            'sortout': 0
                        }

                    carousal_wise_data[sys_id]['handled'] += row['count']
                    if row['process_status'] != 0:
                        carousal_wise_data[sys_id]['sortout'] += row['count']

                # compute rejection_rate per system_id
                for sys_id, stats in carousal_wise_data.items():
                    if stats['handled'] > 0:
                        stats['rejection_rate'] = round((stats['sortout'] / stats['handled']) * 100, 2)
                    else:
                        stats['rejection_rate'] = 0.0

                return carousal_wise_data
            return False, "No data found"
        except Exception as e:
            print("Exception in gd_rejection :", str(e))
            print("Traceback :", traceback.format_exc())
            return False, "No data found"
    
    @staticmethod
    async def get_pt_rejection(data : dict):
        try:
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
                            system_id,
                            process_status,
                            COUNT(event_log_id)
                        FROM event_log
                        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                            AND system_id IN ({carousal})
                            AND process_id IN ({processId})
                            AND sap_id = {data['sap_id']}
                        GROUP BY  process_status, system_id"""

            results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
            if results['data']:
                results = results['data']
            else:
                return {}

            if results:
                carousal_wise_data = {}

                for row in results:
                    sys_id = row['system_id']
                    if sys_id not in carousal_wise_data:
                        carousal_wise_data[sys_id] = {
                            'handled': 0,
                            'sortout': 0
                        }

                    carousal_wise_data[sys_id]['handled'] += row['count']
                    if row['process_status'] != 0:
                        carousal_wise_data[sys_id]['sortout'] += row['count']

                # compute rejection_rate per system_id
                for sys_id, stats in carousal_wise_data.items():
                    if stats['handled'] > 0:
                        stats['rejection_rate'] = round((stats['sortout'] / stats['handled']) * 100, 2)
                    else:
                        stats['rejection_rate'] = 0.0

                return carousal_wise_data
            return False, "No data found"
        except Exception as e:
            print("Exception in pt_rejection :", str(e))
            print("Traceback :", traceback.format_exc())
            return False, "No data found"
    

    async def get_cs_rejection(data : dict):
        try:
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
                            AND sap_id = {data['sap_id']}
                            AND system_id IN ({carousals})
                            AND process_id IN (2,22)
                        GROUP BY  process_status, system_id"""

            results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
            if results['data']:
                results = results['data']
            else:
                return {}
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
                'handled' : int(total[id]),
                'cylinder_filled':int(total[id] - totalSortout[id]),
                'underfilled': int(data.get(id, {}).get(1040, 0)),
                'overfilled' : int(data.get(id, {}).get(2064, 0)),
                'negative_tare'	: int(data.get(id, {}).get(1296, 0)+(data.get(id, {}).get(5392,0))),
                'positive_tare' : int(data.get(id, {}).get(17424, 0)),
                'timeout':int(data.get(id, {}).get(1048, 0) + data.get(id,{}).get(4120, 0)),
                'other_errors'	: int(otherErrors[id]),
                'sortout':int(totalSortout[id]),
                'commErrorSortout':int(commErrorSortout[id]),
                'rejection_rate' : round((int(totalSortout[id]) / int(total[id])) * 100, 2) if int(total[id]) > 0 else 0.0
                }

            return refData
        except Exception as e:
            print("Exception in cs_rejection :", str(e))
            print("Traceback :", traceback.format_exc())
            return False, "No data found"
    
    async def get_cs_rejection_card(data : dict):
        try:
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
                            AND sap_id = {data['sap_id']}
                            AND system_id IN ({carousals})
                            AND process_id IN (2,22)
                        GROUP BY  process_status, system_id"""

            results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
            if results['data']:
                results = results['data']
            else:
                return {}
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
            
            refData = {
                "handled": 0,
                "sortout": 0
            }
            for id in carousal_array:
                refData["handled"] += int(total[id])
                refData["sortout"] += int(totalSortout[id])
            refData["rejection_rate"] = round((int(refData["sortout"]) / int(refData["handled"])) * 100, 2)
            return refData
        except Exception as e:
            print("Exception in getting filling accuracy :", str(e))
            print("Traceback :", traceback.format_exc())
            return False, "No data found"

    #################### Productivity ####################
    async def get_start_end_times(carousal, data):
        plant_short_name = await LPGOperationsActions.get_plant_short_name(sap_id=data["sap_id"])
        carousal_config = await LPGOperationsActions.get_carousals_config(plant_short_name)
        if carousal_config is None:
            raise Exception("Error Processing Request", 1)
        return {
        'start' : carousal_config[carousal]['times']['start'],
        'end' : carousal_config[carousal]['times']['end']
        }

    async def build_ot_production_period_query(carousal, data):
        from_date = datetime.strptime(f"{data['from_date']}", "%Y-%m-%d").date()
        to_date = datetime.strptime(f"{data['to_date']}","%Y-%m-%d").date()

        startEndTimes = await LPGOperationsActions.get_start_end_times(carousal, data)
        startTime = startEndTimes['start']
        endTime = startEndTimes['end']
        queryString  = f"""WITH day_wise_data as (
                select
                    process_date::date as process_day,
                    to_char(process_date, 'HH24:MI:SS.MS') as process_time,
                    process_date
                FROM production_log
                    where process_date between '{from_date} 00:00:00' and '{to_date} 23:59:59.999'
                    AND sap_id = {data['sap_id']}
                    AND process_id IN (2, 22)
                    AND cyl_type IN (1, 2)
                    and system_id = {carousal}
                    order by production_log_id asc
            ),
            pre_shift_ot_periods as (
                select 
                    process_day,
                    max(process_time::time) - min(process_time::time) as production_time
                from day_wise_data
                where 
                    process_time::time between '00:00:00'::time and '{startTime}'::time
                    group by process_day
            ),
            post_shift_ot_periods as (
                select 
                    process_day,
                    max(process_time::time) - min(process_time::time) as production_time
                from day_wise_data
                where 
                    process_time::time between '{endTime}'::time and '23:59:59.999'::time
                    group by process_day
            )
            select 
                EXTRACT(EPOCH from (select sum(production_time) from pre_shift_ot_periods)) / 3600 as total_pre_shift_time,
                EXTRACT(EPOCH from (select sum(production_time) from post_shift_ot_periods)) / 3600 as total_post_shift_time;"""

        return queryString

    async def build_production_gap_query(carousal, phases, from_date, to_date, sap_id):
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
                FROM production_log
                where 
                    process_date between '{from_date} 00:00:00' and '{to_date} 23:59:59.999'
                    AND sap_id = {sap_id}
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

    async def get_non_operating_days(carousal, data):
        from_date = datetime.strptime(f"{data['from_date']}", "%Y-%m-%d").date()
        to_date = datetime.strptime(f"{data['to_date']}","%Y-%m-%d").date()
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
                                AND sap_id = {data['sap_id']}
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
    
    async def get_production_gaps(carousal, data):
        from_date = datetime.strptime(f"{data['from_date']}", "%Y-%m-%d").date()
        to_date = datetime.strptime(f"{data['to_date']}","%Y-%m-%d").date()
        phases = await LPGOperationsActions.get_phases(data)
        queryString = await LPGOperationsActions.build_production_gap_query(carousal, phases[carousal], from_date, to_date, data["sap_id"])
        query3 = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
        if query3['data']:
            query3 = query3['data']
        return query3[0]
    
    async def get_daily_operating_hours(data):
        phases = await LPGOperationsActions.get_phases(data)
        operating_time = {}

        for key, value in phases.items():
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
                interval = to_date - from_date
                interval = interval.total_seconds()
                totalBreakSeconds += interval

            totalWorkingHours = totalWorkingSeconds / 3600
            totalBreakHours = totalBreakSeconds / 3600
            operating_time[key] = {
            'normal' : totalWorkingHours,
            'break' : totalBreakHours,
              }
        return  operating_time

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

    async def get_phases(data):
        plant_short_name = await LPGOperationsActions.get_plant_short_name(sap_id=data["sap_id"])
        carousal_config = await LPGOperationsActions.get_carousals_config(plant_short_name)
        if carousal_config is None:
            raise Exception("Error Processing Request")
        phases = await LPGOperationsActions.config_to_phases(carousal_config)
        return phases

    async def get_phased_production_data_query_string(carousal, data):
        from_date = datetime.strptime(f"{data['from_date']}", "%Y-%m-%d").date()
        to_date = datetime.strptime(f"{data['to_date']}","%Y-%m-%d").date()

        excludedStatuses = ", ".join(map(str, lpg_config.process_statuses['negativeTare'] + lpg_config.process_statuses['positiveTare']))
        phases = await LPGOperationsActions.get_phases(data)
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
                    from production_log
                    where 
                        process_date between '{from_date} 00:00:00' and '{to_date} 23:59:59.999'
                        AND sap_id = {data['sap_id']}
                        AND process_id in (2, 22)
                        AND process_status NOT IN ({excludedStatuses})
                        AND system_id = {carousal}
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

    async def get_phase_wise_production(carousal, data):
        queryString = await LPGOperationsActions.get_phased_production_data_query_string(carousal, data)
        data = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
        
        blankProdData = {
            'prod_14_2': 0,
            'prod_19': 0
            }

        returnData = {
            'normal': blankProdData,
            'break': blankProdData,
            'overtime': blankProdData
            }
        if data['data']:
            for phase_data in data['data']:
                returnData[phase_data['phase']] = phase_data
     
        return returnData

    async def bottling_data(data : dict):        
        carousalsArray = await LPGOperationsActions.get_carousals("array", data["sap_id"])
        bottling = {}
        for carousal in carousalsArray:
            prodData = await LPGOperationsActions.get_phase_wise_production(carousal, data)
            bottling[carousal] = prodData
        return bottling

    async def production_hours_data(data: dict):   
        def none_to_zero(d):
            for k, v in d.items():
                if isinstance(v, dict):
                    none_to_zero(v)
                elif v is None:
                    d[k] = 0.0
            return d     
        from_date = datetime.strptime(f"{data['from_date']}", "%Y-%m-%d").date()
        to_date = datetime.strptime(f"{data['to_date']}","%Y-%m-%d").date()
        if from_date > to_date:
            return False
        interval_days = (to_date - from_date).days
        total_intervening_days = interval_days + 1
        carousalsArray = await LPGOperationsActions.get_carousals("array", data["sap_id"])
        dailyOperatingHours = await LPGOperationsActions.get_daily_operating_hours(data)

        production_hours = {}
        for carousal in carousalsArray: 
            production_hours[carousal] = await LPGOperationsActions.get_production_gaps(carousal, data)
            production_hours = {k: none_to_zero(v) for k, v in production_hours.items()}
            production_hours[carousal]['carousal'] = carousal
            production_hours[carousal]['intervening_days'] = total_intervening_days
            production_hours[carousal]['non_op_days'] = await LPGOperationsActions.get_non_operating_days(carousal, data)
            production_hours[carousal]['net_op_days'] = total_intervening_days - production_hours[carousal]['non_op_days']
            production_hours[carousal]['daily_op_hours'] = dailyOperatingHours[carousal]
            production_hours[carousal]['max_op_hours']= {}
            production_hours[carousal]['max_op_hours']['normal'] = dailyOperatingHours[carousal]['normal'] * production_hours[carousal]['net_op_days']
            production_hours[carousal]['max_op_hours']['break'] = dailyOperatingHours[carousal]['break'] * production_hours[carousal]['net_op_days']
            production_hours[carousal]['net_op_hours'] = {}
            production_hours[carousal]['net_op_hours']['normal'] = float((production_hours[carousal]['max_op_hours']['normal']) - float(production_hours[carousal]['total_normal_gap']))
            production_hours[carousal]['net_op_hours']['break'] = float((production_hours[carousal]['max_op_hours']['break']) - float(production_hours[carousal]['total_break_gap']))
        return production_hours
    
    async def get_ot_production_period(carousal, data):
        queryString = await LPGOperationsActions.build_ot_production_period_query(carousal, data)
        data = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
        if data['data']:
            data = data['data']
        return data[0]
    
    async def ot_production_time(data:dict):
        carousalsArray = await LPGOperationsActions.get_carousals("array", data["sap_id"])
        ot_production = {}
        for carousal in carousalsArray: 
            ot_production[carousal] = await LPGOperationsActions.get_ot_production_period(carousal, data)
        return ot_production
    
    async def get_productivity(data: dict):
        try:
            bottling_data = await LPGOperationsActions.bottling_data(data)
            production_hours_data = await LPGOperationsActions.production_hours_data(data)
            ot_production_time = await LPGOperationsActions.ot_production_time(data)
            phases = ['normal', 'break', 'overtime']
            productivityData = {}
            for key, value in bottling_data.items():
                for phase in phases:
                    totalProduction = bottling_data[key][phase]['prod_14_2'] + 1.25 * bottling_data[key][phase]['prod_19']
                    gapHours = production_hours_data[key]["total_" + phase + "_gap"]
                    if key not in productivityData:
                        productivityData[key] = {}
                    productivityData[key][phase]={}
                    if phase != 'overtime':                                        
                        maxHours = production_hours_data[key]['max_op_hours'][phase]
                        productivityData[key][phase]['net_hours'] =  abs(float(maxHours) - float(gapHours))
                    else:
                        total_pre_shift_time = ot_production_time[key]['total_pre_shift_time']
                        total_post_shift_time = ot_production_time[key]['total_post_shift_time']
                        if total_pre_shift_time is None:
                            total_pre_shift_time = 0
                        if total_post_shift_time is None:
                            total_post_shift_time = 0
                        productivityData[key][phase]['net_hours'] =  abs(total_pre_shift_time + total_post_shift_time - gapHours)
                    productivityData[key][phase]['total_production'] = totalProduction
                    if not (productivityData[key][phase]['net_hours']):
                        productivityData[key][phase]['productivity'] =  0
                    else:
                        productivityData[key][phase]['productivity'] = abs(round(float(totalProduction) / float(productivityData[key][phase]['net_hours']), 2))
            return productivityData    
        except Exception as e:
            print("Exception in getting filling accuracy :", str(e))
            print("Traceback :", traceback.format_exc())
            return False, "No data found"
    
    ##########################  Filling Accuracy  ################################
    async def get_filling_accuracy(data: dict):
        try:
            cyl_types = ",".join(map(str, lpg_config.cyl_types))
            carousal = await LPGOperationsActions.get_carousals('string', data["sap_id"])
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
                    ORDER BY system_id ASC
                    """
            stats = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
            if stats['data']:
                return stats['data']
            return False, "No data found"
        except Exception as e:
            print("Exception in getting filling accuracy :", str(e))
            print("Traceback :", traceback.format_exc())
            return False, "No data found"
    
    async def get_bottling_summary(data: dict):
        try:
            excludedStatuses = ", ".join(
                map(str, lpg_config.process_statuses['negativeTare'] + lpg_config.process_statuses['positiveTare'])
                )
            from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
            to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")
            
            carousal = await LPGOperationsActions.get_carousals('string', data["sap_id"])
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
                        AND sap_id = {data['sap_id']}
                        AND process_id IN (2,22)
                        AND system_id IN ({carousal})
                        AND cyl_type IN (1,2)
                        AND process_status NOT IN ({excludedStatuses})
                    GROUP BY system_id 
                    ORDER BY system_id;"""        

            bottling_data = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
            if bottling_data['data']:
                bottling_data = bottling_data['data']
            else:
                return {}
            carousals = await LPGOperationsActions.get_carousals('array', data["sap_id"])
            result = {}

            if(bottling_data and (bottling_data[0]["production_14_2"] > 0 or bottling_data[0]["production_19"] > 0)):
                for d in bottling_data:
                    for c in carousals:
                        if c == d["carousal"]:
                            result[c] = d
                return result
            return False, "No data found"
        except Exception as e:
            print("Exception in getting bottling summary :", str(e))
            print("Traceback :", traceback.format_exc())
            return False, "No data found"


############## Hourly Production Data ###################
    async def hourly_production_data(data: dict):
        # from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
        # to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")
        from_date = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"
        to_date = datetime.now().strftime("%Y-%m-%d") + " 23:59:59"
        
        cyl_type = ", ".join(map(str, lpg_config.cyl_types))
        carousal = await LPGOperationsActions.get_carousals('string', data['sap_id'])

        excludedStatuses = ", ".join(map(str, lpg_config.process_statuses['negativeTare'] + lpg_config.process_statuses['positiveTare']))
        queryString = f"""
        SELECT
            DATE_TRUNC('hour', process_date) as hour,
            SUM(CASE WHEN (system_id = 1 AND cyl_type = 1) THEN 1 ELSE 0 END) AS c1_t1,
            SUM(CASE WHEN (system_id = 1 AND cyl_type = 2) THEN 1 ELSE 0 END) AS c1_t2,
            SUM(CASE WHEN (system_id = 2 AND cyl_type = 1) THEN 1 ELSE 0 END) AS c2_t1,
            SUM(CASE WHEN (system_id = 2 AND cyl_type = 2) THEN 1 ELSE 0 END) AS c2_t2
        FROM production_log
        WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
            AND sap_id = {data['sap_id']}
            AND process_id IN (2,22)
            AND system_id IN ({carousal})
            AND cyl_type IN ({cyl_type})
            AND process_status NOT IN ({excludedStatuses})
        GROUP BY DATE_TRUNC('hour', process_date)
        ORDER BY hour ASC;
        """
        stats = await urdhva_base.BasePostgresModel.get_aggr_data(queryString, limit=0)
        if stats['data']:
            return stats['data']
        return False

    async def get_hourly_production(data : dict):
        try:
            rawData = await LPGOperationsActions.hourly_production_data(data=data)
            print("rawData :", rawData)
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
        except Exception as e:
            print("Exception in getting bottling summary :", str(e))
            print("Traceback :", traceback.format_exc())
            return False, "No data found"
    
    async def get_total_production_today_data(data: dict):
        production_data = await LPGOperationsActions.get_productivity(data)
        if not production_data:
            return False, "No data found"

        production_data = await calculate_productivity(production_data)
        total_production = round(production_data["total_production"].sum(), 2)

        today_date = datetime.strptime(data["from_date"], "%Y-%m-%d")
        yesterday_date = today_date - timedelta(days=1)

        yesterday_payload = {
            "sap_id": data["sap_id"],
            "from_date": yesterday_date.strftime("%Y-%m-%d"),
            "to_date": yesterday_date.strftime("%Y-%m-%d")
        }

        yesterday_data = await LPGOperationsActions.get_productivity(yesterday_payload)

        if yesterday_data:
            yesterday_data = await calculate_productivity(yesterday_data)
            yesterday_total = round(yesterday_data["total_production"].sum(), 2)
        else:
            yesterday_total = 0

        change_percent = round(((total_production / yesterday_total) - 1) * 100, 2) if yesterday_total > 0 else 0

        print("Production:", total_production)

        return {
            "Total Production": total_production,
            "Yesterday Production": yesterday_total,
            "Change (%)": change_percent
        }


    async def get_total_productivity_today_data(data: dict):
        production_data = await LPGOperationsActions.get_productivity(data)
        if not production_data:
            return False, "No data found"

        production_data = await calculate_productivity(production_data)

        total_production = production_data["total_production"].sum()
        total_hours = production_data["total_net_hours"].sum()
        total_productivity = round(total_production / total_hours, 2) if total_hours > 0 else 0

        today_date = datetime.strptime(data["from_date"], "%Y-%m-%d")
        yesterday_date = today_date - timedelta(days=1)

        yesterday_payload = {
            "sap_id": data["sap_id"],
            "from_date": yesterday_date.strftime("%Y-%m-%d"),
            "to_date": yesterday_date.strftime("%Y-%m-%d")
        }

        yesterday_data = await LPGOperationsActions.get_productivity(yesterday_payload)

        if yesterday_data:
            yesterday_data = await calculate_productivity(yesterday_data)
            y_total_prod = yesterday_data["total_production"].sum()
            y_total_hours = yesterday_data["total_net_hours"].sum()
            yesterday_productivity = round(y_total_prod / y_total_hours, 2) if y_total_hours > 0 else 0
        else:
            yesterday_productivity = 0

        change_percent = round(((total_productivity / yesterday_productivity) - 1) * 100, 2) if yesterday_productivity > 0 else 0

        print("Productivity:", total_productivity)

        return {
            "Productivity": total_productivity,
            "Yesterday Productivity": yesterday_productivity,
            "Change (%)": change_percent
        }
    
    async def get_productivity_raw_data(data: dict):
        try:
            today = datetime.now().date()
            from_date = datetime.combine(today, datetime.min.time())
            to_date = datetime.combine(today, datetime.max.time())
            sap_id = data["sap_id"]

            # Get carousals dynamically
            carousal = await LPGOperationsActions.get_carousals(
                'string', sap_id
            )

            if not carousal:
                return []

            # Get interval & avg duration from LPG operations (or set defaults internally)
            interval = 15
            avg_duration = 30

            interval = interval if interval else 15
            avg_duration = avg_duration if avg_duration else 30

            excluded_statuses = "1296,5392,17424"

            # 🔹 Dynamic SUM columns per carousal
            dynamic_columns = []
            for cid in carousal.split(","):
                dynamic_columns.append(f"""
                    SUM(CASE WHEN (system_id = {cid.strip()} AND cyl_type = 1) THEN 1
                            WHEN (system_id = {cid.strip()} AND cyl_type = 2) THEN 1.25
                            ELSE 0 END) AS c{cid.strip()}
                """)

            dynamic_columns_sql = ", ".join(dynamic_columns)

            query = f"""
                SELECT
                    date_part('epoch', 
                        date_trunc('hour', process_date) +  
                        (((date_part('minute', process_date)::integer / {interval}) * {interval}) || ' minutes')::interval
                    ) AS period_end,
                    {dynamic_columns_sql}
                FROM production_log
                WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                AND process_id IN (2, 22)
                AND system_id IN ({carousal})
                AND cyl_type IN (1, 2)
                AND process_status NOT IN ({excluded_statuses})
                AND sap_id = {sap_id}
                GROUP BY period_end
                ORDER BY period_end ASC;
            """

            print("query:",query)
            results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)

            if results.get("data"):
                return results["data"], avg_duration, carousal

            return [], avg_duration, carousal

        except Exception as e:
            print("Exception in get_productivity_raw_data:", str(e))
            print(traceback.format_exc())
            return [], 30, ""


    async def get_productivity_moving_average(data: dict):
        try:
            raw_data, avg_duration, carousal_string = await LPGOperationsActions.get_productivity_raw_data(data)

            if not raw_data:
                return False, "No data found"

            df = pd.DataFrame(raw_data)
            df["period_end"] = df["period_end"].astype(np.int64)


            for col in df.columns:
                if col != "period_end":
                    df[col] = df[col].astype(float)

            avg_duration_secs = avg_duration * 60
            hourly_factor = 3600 / avg_duration_secs
            adjustment_factor = 8.5 / 7.75

            carousals = [c.strip() for c in carousal_string.split(",")]
            
            output = {
                "labels": [],
                "overall": {}
            }

            for cid in carousals:
                output[f"c{cid}_rate"] = []
                output["overall"][f"c{cid}"] = 0

            for _, row in df.iterrows():
                current_ts = row["period_end"]

                window_df = df[
                    (df["period_end"] >= current_ts - avg_duration_secs) &
                    (df["period_end"] < current_ts)
                ]

                output["labels"].append(
                    datetime.fromtimestamp(current_ts).strftime("%H:%M")
                )

                for cid in carousals:
                    col = f"c{cid}"
                    window_sum = window_df[col].sum() if col in window_df else 0
                    rate = round(window_sum * hourly_factor, 2)
                    output[f"c{cid}_rate"].append(rate)

            # 🔹 Overall Adjusted Productivity
            for cid in carousals:
                rates = [r for r in output[f"c{cid}_rate"] if r > 0]
                if rates:
                    output["overall"][f"c{cid}"] = round(
                        (sum(rates) / len(rates)) * adjustment_factor,
                        2
                    )

            print("*" * 40)
            print("Moving Average Productivity")
            print("Overall:", output["overall"])
            print("*" * 40)

            return output

        except Exception as e:
            print("Exception in get_productivity_moving_average:", str(e))
            print(traceback.format_exc())
            return False, "Error occurred"

        
    async def get_eld_old_rejections(data : dict):
        eld_data = await LPGOperationsActions.get_gd_rejection(data)
        old_data = await LPGOperationsActions.get_pt_rejection(data)

        eld_data = eld_data if eld_data else {}
        old_data = old_data if old_data else {}

        output = {}
        output['ELD'] = eld_data
        output['OLD'] = old_data

        return output

    async def get_eld_drill_down(data: dict):
        try:
            from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
            to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")
            if not data.get("carousal", None):
                        carousal = await LPGOperationsActions.get_carousals('string', data.get("sap_id"))
                        processId = '3,23'

            query = f"""SELECT
                        system_id,
                        process_status,
                        COUNT(event_log_id),
                        device_id
                    FROM event_log
                    WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                        AND system_id IN ({carousal})
                        AND process_id IN ({processId})
                        AND sap_id = {data['sap_id']}
                    GROUP BY  process_status, system_id,device_id """
            print(query)
            results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
            print(results)
            if results['data']:
                    results = results['data']
            else:
                return {}

            if results:
                carousal_wise_data = {}

                for row in results:
                    sys_id = row['system_id']
                    device_id = row['device_id']

                    # initialize system_id dict
                    if sys_id not in carousal_wise_data:
                        carousal_wise_data[sys_id] = {}

                    # initialize device_id dict
                    if device_id not in carousal_wise_data[sys_id]:
                        carousal_wise_data[sys_id][device_id] = {
                            'handled': 0,
                            'sortout': 0
                        }

                    # update handled
                    carousal_wise_data[sys_id][device_id]['handled'] += row['count']

                    # update sortout
                    if row['process_status'] != 0:
                        carousal_wise_data[sys_id][device_id]['sortout'] += row['count']

                return carousal_wise_data
            return False, "No data found"
        
        except Exception as e:
            print("Exception in gd_rejection :", str(e))
            print("Traceback :", traceback.format_exc())
            return False, "No data found"
        
    async def get_old_drill_down(data: dict):
        try:
            from_date = datetime.strptime(f"{data['from_date']} 00:00:00", "%Y-%m-%d %H:%M:%S")
            to_date = datetime.strptime(f"{data['to_date']} 23:59:59","%Y-%m-%d %H:%M:%S")
            if not data.get("carousal", None):
                carousal = await LPGOperationsActions.get_carousals('string', data.get("sap_id"))
                processId =  '4,24'
            else:
                carousal = '1,2'
            query = f"""SELECT
                        system_id,
                        process_status,
                        COUNT(event_log_id),
                        device_id
                    FROM event_log
                    WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                        AND system_id IN ({carousal})
                        AND process_id IN ({processId})
                        AND sap_id = {data['sap_id']}
                    GROUP BY  process_status, system_id,device_id """
            print(query)
            results = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
            print(results)
            if results['data']:
                    results = results['data']
            else:
                return {}

            if results:
                carousal_wise_data = {}

                for row in results:
                    sys_id = row['system_id']
                    device_id = row['device_id']

                    # initialize system_id dict
                    if sys_id not in carousal_wise_data:
                        carousal_wise_data[sys_id] = {}

                    # initialize device_id dict
                    if device_id not in carousal_wise_data[sys_id]:
                        carousal_wise_data[sys_id][device_id] = {
                            'handled': 0,
                            'sortout': 0
                        }

                    # update handled
                    carousal_wise_data[sys_id][device_id]['handled'] += row['count']

                    # update sortout
                    if row['process_status'] != 0:
                        carousal_wise_data[sys_id][device_id]['sortout'] += row['count']

                return carousal_wise_data
            return False, "No data found"
        
        except Exception as e:
            print("Exception in gd_rejection :", str(e))
            print("Traceback :", traceback.format_exc())
            return False, "No data found"
        
    
    async def get_scale_id(row: dict) -> int:
        return row.get("device_id") or row.get("machine_id")

    async def get_scales_efficiency_data(sap_id, carousal_list, from_date, to_date):
        query = f"""
            WITH ScaleAggregates AS (
                SELECT 
                    system_id, 
                    machine_id, 
                    device_id, 
                    COUNT(*) AS scale_count,
                    MIN(process_date) as scale_first,
                    MAX(process_date) as scale_last
                FROM production_log
                WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
                AND process_id IN (2, 22)
                AND system_id IN ({carousal_list})
                AND cyl_type IN (1, 2)
                AND process_status NOT IN (1296, 5392, 17424)
                AND sap_id = {sap_id}
                GROUP BY system_id, machine_id, device_id
            )
            SELECT 
                *,
                MIN(scale_first) OVER (PARTITION BY system_id) AS first_cyl_time_overall,
                MAX(scale_last) OVER (PARTITION BY system_id) AS last_cyl_time_overall
            FROM ScaleAggregates
            ORDER BY system_id ASC, machine_id ASC
        """
        
        raw_data = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        
        meta_data = {}
        if raw_data and raw_data.get('data'):
            for row in raw_data['data']:
                s_id = row["system_id"]
                if s_id not in meta_data:
                    meta_data[s_id] = {
                        "first_cyl_time": row["first_cyl_time_overall"],
                        "last_cyl_time":  row["last_cyl_time_overall"],
                    }
            return {"rows": raw_data['data'], "metaData": meta_data}
        return False

    async def under_performance_scales(data: dict):

        if not data.get('time'):
            today = datetime.now().date()
            from_date = datetime.combine(today, datetime.min.time())
            to_date = datetime.combine(today, datetime.max.time())
        else:
            now = datetime.now()
            tg = data['time'].lower()

            if tg.endswith('m'):  # minutes
                delta = timedelta(minutes=int(tg[:-1]))
            elif tg.endswith('h'):  # hours
                delta = timedelta(hours=int(tg[:-1]))
            elif tg.endswith('d'):  # days
                delta = timedelta(days=int(tg[:-1]))
            else:
                raise ValueError("Invalid time_grain format")

            from_date = now - delta
            to_date = now
        print(from_date,to_date)
        sap_id = data.get("sap_id")
        
        carousals_data = await LPGOperationsActions.get_carousals('full', sap_id)
        c_ids = list(carousals_data.keys())
        carousal_list = ", ".join(map(str, c_ids))

        scales_count = await LPGOperationsActions.get_scales_efficiency_data(sap_id, carousal_list, from_date, to_date)
        
        if not scales_count:
            return {"rows": [], "meta": {f"car{c}Eff": "0%" for c in c_ids}}

        meta_data = scales_count["metaData"]
        raw_rows = scales_count["rows"]
        
        intervals = {}
        std_output_per_head = {}
        car_speeds = {1: 50, 2: 48, 3: 48}
        
        for c_id in c_ids:
            if c_id in meta_data:
                first_time = meta_data[c_id]["first_cyl_time"]
                last_time = meta_data[c_id]["last_cyl_time"]

                # Convert if string
                if isinstance(first_time, str):
                    first_time = datetime.fromisoformat(first_time)

                if isinstance(last_time, str):
                    last_time = datetime.fromisoformat(last_time)

                diff = (last_time - first_time).total_seconds()
                intervals[c_id] = diff if diff > 0 else 0.0
            else:
                intervals[c_id] = 0.0
                
            interval = intervals[c_id]
            if c_id in carousals_data and interval > 0:
                std_output_per_head[c_id] = (carousals_data[c_id]["stdOutput"] * (interval / 3600)) / carousals_data[c_id]["heads"]
            elif c_id in car_speeds and interval > 0:
                std_output_per_head[c_id] = (1 / car_speeds[c_id]) * interval
            else:
                std_output_per_head[c_id] = 0.0

        overall_count = {c_id: 0 for c_id in c_ids}
        processed_rows = []
        for row in raw_rows:
            s_id = row["system_id"]
            denom = std_output_per_head.get(s_id, 0)
            eff = row["scale_count"] / denom if denom > 0 else 0.0
            
            tag = "above-average"
            if eff <= 0.75: tag = "below-average"
            elif eff <= 1.0: tag = "average"

            processed_rows.append({
                "scale": await LPGOperationsActions.get_scale_id(row),
                "carousal": s_id,
                "efficiency": eff,
                "efficiency_display": f"{round(eff * 100)}%",
                "tag": tag,
                "count": row["scale_count"]
            })
            overall_count[s_id] += row["scale_count"]

        meta = {}
        for c_id in c_ids:
            key = f"car{c_id}Eff"
            heads = carousals_data.get(c_id, {}).get("heads", 24)
            total_std_output = std_output_per_head.get(c_id, 0) * heads
            overall_eff = overall_count[c_id] / total_std_output if total_std_output > 0 else 0.0
            meta[key] = f"{round(overall_eff * 100)}%"

        processed_rows.sort(key=lambda x: x["efficiency"])
        return {"rows": processed_rows[:10], "meta": meta}

    async def underfill_overfill_scales(data: dict):

        if not data.get('time'):
            today = datetime.now().date()
            from_date = datetime.combine(today, datetime.min.time())
            to_date = datetime.combine(today, datetime.max.time())
        else:
            now = datetime.now()
            tg = data['time'].lower()

            if tg.endswith('m'):  # minutes
                delta = timedelta(minutes=int(tg[:-1]))
            elif tg.endswith('h'):  # hours
                delta = timedelta(hours=int(tg[:-1]))
            elif tg.endswith('d'):  # days
                delta = timedelta(days=int(tg[:-1]))
            else:
                raise ValueError("Invalid time_grain format")

            from_date = now - delta
            to_date = now
        print(from_date,to_date)
        sap_id = data.get("sap_id")
        carousals_data = await LPGOperationsActions.get_carousals('full', sap_id)
        c_ids = list(carousals_data.keys())
        c_list = ", ".join(map(str, c_ids))

        query = f"""
            SELECT system_id, machine_id, device_id, 
                COUNT(*) as total,
                SUM(CASE WHEN 
                        ((cyl_type = 1) AND (ABS(check_net - 14200) > 100 AND ABS(check_net - 14200) <= 200))
                        OR
                        ((cyl_type = 2) AND (ABS(check_net - 19000) > 100 AND ABS(check_net - 19000) <= 200))
                    THEN 1 ELSE 0 END) AS hundred_plus
            FROM production_log
            WHERE process_date BETWEEN '{from_date}' AND '{to_date}'
            AND process_id IN (2, 22)
            AND system_id IN ({c_list})
            AND sap_id = {sap_id}
            GROUP BY system_id, machine_id, device_id
        """
        print("query:",query)
        res = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)
        rows = res.get('data', [])
        print(len(rows))
        overall = {c_id: {"total": 0, "h_plus": 0} for c_id in c_ids}
        processed_rows = []

        for row in rows:
            s_id = row["system_id"]
            total = row["total"] or 1
            acc = 1 - (row["hundred_plus"] / total)
            
            tag = "above-average"
            if acc <= 0.97: tag = "below-average"
            elif acc <= 1.0: tag = "average"

            processed_rows.append({
                "scale": await LPGOperationsActions.get_scale_id(row),
                "carousal": s_id,
                "accuracy": acc,
                "accuracy_display": f"{round(acc * 100)}%",
                "tag": tag,
                "total": row["total"]
            })
            
            if s_id in overall:
                overall[s_id]["total"] += row["total"]
                overall[s_id]["h_plus"] += row["hundred_plus"]

        meta = {}
        for c_id in c_ids:
            denom = overall[c_id]["total"] or 1
            overall_acc = 1 - (overall[c_id]["h_plus"] / denom)
            meta[f"car{c_id}Acc"] = f"{(overall_acc * 100):.2f}%"

        processed_rows.sort(key=lambda x: x["accuracy"])
        return {"rows": processed_rows[:10], "meta": meta}
    
    
    @staticmethod
    async def plant_month_analysis(data):

        CURRENT_FILE = os.path.abspath(__file__)
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_FILE)))
        MASTER_PATH = os.path.join(BASE_DIR, "masters", "lpg_production_cost")


        MONTH_ORDER = [
            "April", "May", "June", "July",
            "August", "September", "October",
            "November", "December",
            "January", "February", "March"
        ]

        MONTH_FILE_PREFIX = {
            "January": "Jan",
            "February": "Feb",
            "March": "Mar",
            "April": "April",
            "May": "May",
            "June": "June",
            "July": "July",
            "August": "Aug",
            "September": "Sep",
            "October": "Oct",
            "November": "Nov",
            "December": "Dec"
        }

        #  Define once (fixes COLUMNS error)
        COLUMNS = [
            "Production (MT) - CY",
            "Production (MT) - LY",
            "Manpower Expenses (CY)",
            "Manpower Expenses (LY)",
            "Other OPEX Expenses (CY)",
            "Other OPEX Expenses (LY)",
            "M&R CVR Expenses (CY)",
            "M&R CVR Expenses (LY)",
            "Depreciation Expenses (CY)",
            "Depreciation Expenses (LY)"
        ]

        requested_sap_id = str(data.get("sap_id")).strip() if data.get("sap_id") else None
        requested_zone = str(data.get("zone")).strip() if data.get("zone") else None

        months_to_process = (
            [data.get("month").capitalize()]
            if data.get("month")
            else MONTH_ORDER
        )

        # ===============================
        # Fetch DB SAP IDs
        # ===============================
        query = """ SELECT DISTINCT sap_id FROM lpg_plant_operations_masters """
        result = await urdhva_base.BasePostgresModel.get_aggr_data(query, limit=0)

        db_sap_ids = [
            str(row["sap_id"]).strip()
            for row in result.get("data", [])
            if row.get("sap_id")
        ]

        db_df = pl.DataFrame({"sap_id": db_sap_ids})

        final_results = []
        prev_month_cost_df = None
        april_base_cost_df = None
        august_base_cost_df = None
        # =====================================
        # PRELOAD APRIL BASE (Always Load)
        # =====================================
        april_prefix = MONTH_FILE_PREFIX["April"]
        april_files = glob.glob(os.path.join(MASTER_PATH, f"{april_prefix}-*.xlsx"))

        if april_files:
            april_df = pl.read_excel(april_files[0], sheet_name="Sheet1")

            if "Plant" in april_df.columns:
                april_df = april_df.with_columns(
                    pl.col("Plant")
                    .cast(pl.Utf8)
                    .str.split(" - ")
                    .list.get(0)
                    .alias("sap_id")
                ).join(db_df, on="sap_id", how="inner")

            april_df = april_df.with_columns([
                (
                    (pl.col("Manpower Expenses (CY)") / pl.col("Production (MT) - CY")).fill_null(0) +
                    (pl.col("Other OPEX Expenses (CY)") / pl.col("Production (MT) - CY")).fill_null(0) +
                    (pl.col("M&R CVR Expenses (CY)") / pl.col("Production (MT) - CY")).fill_null(0) +
                    (pl.col("Depreciation Expenses (CY)") / pl.col("Production (MT) - CY")).fill_null(0)
                ).alias("Base Total Cost (CY)"),

                (
                    (pl.col("Manpower Expenses (LY)") / pl.col("Production (MT) - LY")).fill_null(0) +
                    (pl.col("Other OPEX Expenses (LY)") / pl.col("Production (MT) - LY")).fill_null(0) +
                    (pl.col("M&R CVR Expenses (LY)") / pl.col("Production (MT) - LY")).fill_null(0) +
                    (pl.col("Depreciation Expenses (LY)") / pl.col("Production (MT) - LY")).fill_null(0)
                ).alias("Base Total Cost (LY)")
            ])
            april_df = april_df.with_columns([

                (
                    pl.col("Base Total Cost (CY)") *
                    pl.col("Production (MT) - CY")
                ).alias("Base Total Prod Cost (CY)"),

                (
                    pl.col("Base Total Cost (LY)") *
                    pl.col("Production (MT) - LY")
                ).alias("Base Total Prod Cost (LY)")
            ])
            april_base_cost_df = april_df.select([
                "sap_id",
                "Base Total Cost (CY)",
                "Base Total Cost (LY)",
                "Base Total Prod Cost (CY)",
                "Base Total Prod Cost (LY)"
            ])


        # =====================================
        # PRELOAD AUGUST BASE (Always Load)
        # =====================================
        aug_prefix = MONTH_FILE_PREFIX["August"]
        aug_files = glob.glob(os.path.join(MASTER_PATH, f"{aug_prefix}-*.xlsx"))

        if aug_files:
            aug_df = pl.read_excel(aug_files[0], sheet_name="Sheet1")

            if "Plant" in aug_df.columns:
                aug_df = aug_df.with_columns(
                    pl.col("Plant")
                    .cast(pl.Utf8)
                    .str.split(" - ")
                    .list.get(0)
                    .alias("sap_id")
                ).join(db_df, on="sap_id", how="inner")

            aug_df = aug_df.with_columns([
                (
                    (pl.col("Manpower Expenses (CY)") / pl.col("Production (MT) - CY")).fill_null(0) +
                    (pl.col("Other OPEX Expenses (CY)") / pl.col("Production (MT) - CY")).fill_null(0) +
                    (pl.col("M&R CVR Expenses (CY)") / pl.col("Production (MT) - CY")).fill_null(0) +
                    (pl.col("Depreciation Expenses (CY)") / pl.col("Production (MT) - CY")).fill_null(0)
                ).alias("Base Total Cost (CY)"),

                (
                    (pl.col("Manpower Expenses (LY)") / pl.col("Production (MT) - LY")).fill_null(0) +
                    (pl.col("Other OPEX Expenses (LY)") / pl.col("Production (MT) - LY")).fill_null(0) +
                    (pl.col("M&R CVR Expenses (LY)") / pl.col("Production (MT) - LY")).fill_null(0) +
                    (pl.col("Depreciation Expenses (LY)") / pl.col("Production (MT) - LY")).fill_null(0)
                ).alias("Base Total Cost (LY)")
            ])
            aug_df = aug_df.with_columns([

                (
                    pl.col("Base Total Cost (CY)") *
                    pl.col("Production (MT) - CY")
                ).alias("Base Total Prod Cost (CY)"),

                (
                    pl.col("Base Total Cost (LY)") *
                    pl.col("Production (MT) - LY")
                ).alias("Base Total Prod Cost (LY)")
            ])
            august_base_cost_df = aug_df.select([
                "sap_id",
                "Base Total Cost (CY)",
                "Base Total Cost (LY)",
                "Base Total Prod Cost (CY)",
                "Base Total Prod Cost (LY)"
            ])

        # ==========================================================
        # LOOP THROUGH MONTHS
        # ==========================================================
        for month in months_to_process:
            # =========================================
            #  PRELOAD AUGUST BASE COST
            # =========================================

            
            file_prefix = MONTH_FILE_PREFIX[month]
            files = glob.glob(os.path.join(MASTER_PATH, f"{file_prefix}-*.xlsx"))
            print("===================================")
            print("Month:", month)
            print("File Prefix:", file_prefix)
            print("Search Path:", os.path.join(MASTER_PATH, f"{file_prefix}-*.xlsx"))
            print("Files Found:", files)
            print("===================================")

            if not files:
                continue

            current_file = files[0]
            year_match = re.search(r"-(\d+)\.xlsx$", current_file)
            if not year_match:
                continue

            current_year = int(year_match.group(1))
            print("DEBUG → Processing Month:", month)
            print("DEBUG → Current Year:", current_year)
            current_df = pl.read_excel(current_file, sheet_name="Sheet1")

            # Extract sap_id
            if "Plant" in current_df.columns:
                current_df = current_df.with_columns(
                    pl.col("Plant")
                    .cast(pl.Utf8)
                    .str.split(" - ")
                    .list.get(0)
                    .alias("sap_id")
                ).join(db_df, on="sap_id", how="inner")

            # ===============================
            # SUBTRACTION LOGIC (UNCHANGED)
            # ===============================
            if month == "April":
                merged = current_df
                merged = merged.with_columns([
                    pl.lit(0).alias("Manpower Expenses (LY)"),
                    pl.lit(0).alias("Manpower Expenses (CY)")
                ])

            else:
                month_index = MONTH_ORDER.index(month)
                prev_month = MONTH_ORDER[month_index - 1]
                prev_year = current_year - 1 if month == "January" else current_year

                prev_prefix = MONTH_FILE_PREFIX[prev_month]
                prev_pattern = os.path.join(MASTER_PATH, f"{prev_prefix}-{prev_year}.xlsx")

                if os.path.exists(prev_pattern):

                    prev_df = pl.read_excel(prev_pattern, sheet_name="Sheet1")

                    if "Plant" in prev_df.columns:
                        prev_df = prev_df.with_columns(
                            pl.col("Plant")
                            .cast(pl.Utf8)
                            .str.split(" - ")
                            .list.get(0)
                            .alias("sap_id")
                        ).join(db_df, on="sap_id", how="inner")

                    merged = current_df.join(
                        prev_df,
                        on=["SBU", "Zone", "Regional Office", "Plant", "sap_id"],
                        how="left",
                        suffix="_prev"
                    )
                    merged = merged.with_columns([
                    pl.lit(0).alias("Manpower Expenses (LY)"),
                    pl.lit(0).alias("Manpower Expenses (CY)")
                ])

                    for col in COLUMNS:
                        prev_col = f"{col}_prev"
                        if col in merged.columns and prev_col in merged.columns:
                            merged = merged.with_columns(
                                (pl.col(col) - pl.col(prev_col).fill_null(0)).alias(col)
                            )
                else:
                    merged = current_df
                    merged = merged.with_columns([
                    pl.lit(0).alias("Manpower Expenses (LY)"),
                    pl.lit(0).alias("Manpower Expenses (CY)")
                ])

            # ===============================
            # Inject missing columns (SAFE)
            # ===============================
            for col in COLUMNS:
                if col not in merged.columns:
                    merged = merged.with_columns(pl.lit(0).alias(col))

            # ===============================
            # COST CALCULATION
            # ===============================
            merged = merged.with_columns([

                (pl.col("Manpower Expenses (CY)") / pl.col("Production (MT) - CY"))
                    .fill_nan(0).fill_null(0).alias("Manpower Cost (CY)"),

                (pl.col("Other OPEX Expenses (CY)") / pl.col("Production (MT) - CY"))
                    .fill_nan(0).fill_null(0).alias("Other OPEX Cost (CY)"),

                (pl.col("M&R CVR Expenses (CY)") / pl.col("Production (MT) - CY"))
                    .fill_nan(0).fill_null(0).alias("M&R CVR Cost (CY)"),

                (pl.col("Depreciation Expenses (CY)") / pl.col("Production (MT) - CY"))
                    .fill_nan(0).fill_null(0).alias("Depreciation Cost (CY)"),

                (pl.col("Manpower Expenses (LY)") / pl.col("Production (MT) - LY"))
                    .fill_nan(0).fill_null(0).alias("Manpower Cost (LY)"),

                (pl.col("Other OPEX Expenses (LY)") / pl.col("Production (MT) - LY"))
                    .fill_nan(0).fill_null(0).alias("Other OPEX Cost (LY)"),

                (pl.col("M&R CVR Expenses (LY)") / pl.col("Production (MT) - LY"))
                    .fill_nan(0).fill_null(0).alias("M&R CVR Cost (LY)"),

                (pl.col("Depreciation Expenses (LY)") / pl.col("Production (MT) - LY"))
                    .fill_nan(0).fill_null(0).alias("Depreciation Cost (LY)")
            ])
            # ===============================
            # FORCE OTHER OPEX COST = 0
            # # ===============================

            merged = merged.with_columns([

                (
                    pl.col("Manpower Cost (CY)") +
                    pl.col("Other OPEX Cost (CY)") +
                    pl.col("M&R CVR Cost (CY)") +
                    pl.col("Depreciation Cost (CY)")
                ).alias("Total Cost (CY)"),

                (
                    pl.col("Manpower Cost (LY)") +
                    pl.col("Other OPEX Cost (LY)") +
                    pl.col("M&R CVR Cost (LY)") +
                    pl.col("Depreciation Cost (LY)")
                ).alias("Total Cost (LY)")
            ])
            
            # ===============================
            # SAVINGS (Dynamic Base Logic)
            # ===============================

            if month in ["April", "May", "June", "July"] and april_base_cost_df is not None:

                merged = merged.join(
                    april_base_cost_df,
                    on="sap_id",
                    how="left"
                )

            elif month in ["August", "September", "October", "November", "December", "January", "February", "March"] and august_base_cost_df is not None:

                merged = merged.join(
                    august_base_cost_df,
                    on="sap_id",
                    how="left"
                )
                merged = merged.with_columns([
                    pl.lit(0).alias("Manpower Expenses (LY)"),
                    pl.lit(0).alias("Manpower Expenses (CY)")
                ])

            # Force April & August savings = 0
            if month in ["April", "August"]:

                merged = merged.with_columns([
                    pl.lit(0).alias("Savings (CY)"),
                    pl.lit(0).alias("Savings (LY)")
                ])

            else:

                merged = merged.with_columns([

                    (
                        pl.col("Production (MT) - CY") *
                        (pl.col("Base Total Cost (CY)") - pl.col("Total Cost (CY)"))
                    ).fill_null(0).alias("Savings (CY)"),

                    (
                        pl.col("Production (MT) - LY") *
                        (pl.col("Base Total Cost (LY)") - pl.col("Total Cost (LY)"))
                    ).fill_null(0).alias("Savings (LY)")
                ])
            # ===============================
            # TOTAL PROD COST
            # ===============================
            merged = merged.with_columns([

                (pl.col("Total Cost (CY)") *
                pl.col("Production (MT) - CY"))
                .alias("Total Prod Cost (CY)"),

                (pl.col("Total Cost (LY)") *
                pl.col("Production (MT) - LY"))
                .alias("Total Prod Cost (LY)")
            ])
            # ===============================
            # NEW SAVINGS BASED ON TOTAL PROD COST
            # ===============================

            if month in ["April", "August"]:

                merged = merged.with_columns([
                    pl.lit(0).alias("savings_cy"),
                    pl.lit(0).alias("savings_ly")
                ])

            else:

                merged = merged.with_columns([

                    (
                        pl.col("Base Total Prod Cost (CY)") -
                        pl.col("Total Prod Cost (CY)")
                    ).fill_null(0).alias("savings_cy"),

                    (
                        pl.col("Base Total Prod Cost (LY)") -
                        pl.col("Total Prod Cost (LY)")
                    ).fill_null(0).alias("savings_ly")
                ])
            # Store for next month
            prev_month_cost_df = merged.select([
                "sap_id",
                "Total Cost (CY)",
                "Total Cost (LY)"
            ])

            
            merged = merged.with_columns(pl.lit(month).alias("Month"))
            float_cols = [
                col for col, dtype in zip(merged.columns, merged.dtypes)
                if dtype in (pl.Float32, pl.Float64)
            ]

            merged = merged.with_columns([
                pl.col(col).round(0).cast(pl.Int64) for col in float_cols
            ])
            # Apply filters
            if requested_sap_id:
                merged = merged.filter(pl.col("sap_id") == requested_sap_id)

            if requested_zone:
                merged = merged.filter(pl.col("Zone") == requested_zone)

            final_results.extend(
                merged.select([
                    "Month",
                    "SBU",
                    "Zone",
                    "Regional Office",
                    "Plant",
                    "sap_id",
                    pl.col("Production (MT) - LY").alias("production_mt_ly"),
                    pl.col("Production (MT) - CY").alias("production_mt_cy"),

                    pl.col("Manpower Cost (CY)").alias("manpower_cost_mt_cy"),
                    pl.col("Other OPEX Cost (CY)").alias("other_opex_cost_mt_cy"),
                    pl.col("M&R CVR Cost (CY)").alias("mr_cvr_cost_mt_cy"),
                    pl.col("Depreciation Cost (CY)").alias("depreciation_cost_mt_cy"),

                    pl.col("Manpower Cost (LY)").alias("manpower_cost_mt_ly"),
                    pl.col("Other OPEX Cost (LY)").alias("other_opex_cost_mt_ly"),
                    pl.col("M&R CVR Cost (LY)").alias("mr_cvr_cost_mt_ly"),
                    pl.col("Depreciation Cost (LY)").alias("depreciation_cost_mt_ly"),

                    pl.col("Total Cost (CY)").alias("total_cost_mt_cy"),
                    pl.col("Total Cost (LY)").alias("total_cost_mt_ly"),

                    pl.col("Total Prod Cost (CY)").alias("total_prod_cost_cy"),
                    pl.col("Total Prod Cost (LY)").alias("total_prod_cost_ly"),

                    pl.col("Savings (CY)").alias("savings_mt_cy"),
                    pl.col("Savings (LY)").alias("savings_mt_ly"),
                    pl.col("savings_cy"),
                    pl.col("savings_ly")
                ]).to_dicts()
            )
            
        overall_row = {}
        monthly_aggregated = []

        # return {"data": final_results}
        if final_results:

            final_df = pl.DataFrame(final_results)

            sum_columns = [
                "production_mt_ly",
                "production_mt_cy",

                "total_prod_cost_cy",
                "total_prod_cost_ly",

                "savings_cy",
                "savings_ly"
            ]
            
            avg_columns = [
                "manpower_cost_mt_cy",
                "other_opex_cost_mt_cy",
                "mr_cvr_cost_mt_cy",
                "depreciation_cost_mt_cy",

                "manpower_cost_mt_ly",
                "other_opex_cost_mt_ly",
                "mr_cvr_cost_mt_ly",
                "depreciation_cost_mt_ly",

                "total_cost_mt_cy",
                "total_cost_mt_ly",
                
                "savings_mt_cy",
                "savings_mt_ly",
            ]
            

            overall_row = final_df.select([
                pl.sum(col).round(0).alias(col) for col in sum_columns
            ] + [pl.mean(col).round(0).alias(col) for col in avg_columns
                ])

            overall_row = overall_row.with_columns([
                (pl.col("total_prod_cost_cy") / pl.col("production_mt_cy"))
                    .fill_nan(0).fill_null(0).alias("total_cost_mt_cy"),
                (pl.col("total_prod_cost_ly") / pl.col("production_mt_ly"))
                .fill_nan(0).fill_null(0).alias("total_cost_mt_ly")
            ]).to_dicts()[0]
            
            monthly_aggregated = final_df.group_by("Month").agg(
                [pl.sum(col).round(0).alias(col) for col in sum_columns] +
                [pl.mean(col).round(0).alias(col) for col in avg_columns]
            )

            monthly_aggregated = monthly_aggregated.with_columns([
                (pl.col("total_prod_cost_cy") / pl.col("production_mt_cy"))
                .fill_nan(0).fill_null(0).alias("total_cost_mt_cy"),
                (pl.col("total_prod_cost_ly") / pl.col("production_mt_cy"))
                .fill_nan(0).fill_null(0).alias("total_cost_mt_ly")
            ]).to_dicts()


            # If sap_id filter applied
            if requested_sap_id:
                overall_row.update({
                    
                    "SBU": final_results[0]["SBU"],
                    "Zone": final_results[0]["Zone"],
                    "Regional Office": final_results[0]["Regional Office"],
                    "Plant": final_results[0]["Plant"],
                    "sap_id": final_results[0]["sap_id"]
                })
                for rec in monthly_aggregated:
                    rec.update({
                    "SBU": final_results[0]["SBU"],
                    "Zone": final_results[0]["Zone"],
                    "Regional Office": final_results[0]["Regional Office"],
                    "Plant": final_results[0]["Plant"],
                    "sap_id": final_results[0]["sap_id"]
                })
            else:
                # No sap_id filter → sum of all plants
                overall_row.update({
                    "SBU": "All",
                    "Zone": "All",
                    "Regional Office": "All",
                    "Plant": "All Plants",
                    "sap_id": "All"
                })
                for rec in monthly_aggregated:
                    rec.update({
                    "SBU": "All",
                    "Zone": "All",
                    "Regional Office": "All",
                    "Plant": "All Plants",
                    "sap_id": "All"
                })

            

        return {
            "data": final_results,
            "overall": overall_row,
            "monthly_aggregated": monthly_aggregated
        }
