import os
import psycopg2
import traceback
import subprocess
import pandas as pd
import polars as pl
import numpy as np
from sqlalchemy import create_engine
from datetime import datetime, timedelta


class LPG_CONSOLIDATED():
    def __init__(self, host, database, user, password, port, plantShortName):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.plantShortName = plantShortName

    def get_connection(self):
        connection = psycopg2.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password,
            port=self.port
        )
        cursor = connection.cursor()
        return cursor

    def get_data(self, query, records=False, runOnly=False, params=None):
        if params:
            connection = psycopg2.connect(
                        host=params["host"],
                        database=params["database"],
                        user=params["user"],
                        password=params["password"],
                        port=params["port"]
                    )
            cursor = connection.cursor()
        else:
            cursor = self.get_connection()

        cursor.execute(query)
        if not runOnly:
            data = cursor.fetchall()
            if records:
                columns = [desc[0] for desc in cursor.description]
                data = [dict(zip(columns, row)) for row in data]
            return data
        else:
            resp = cursor.fetchone()[0]
            return resp

    def getAllPlantsConfig(self):
        params = {
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            }

        queryString = """
        SELECT
            plants.short_name AS value,
            plants.plant_name AS text,
            plants.zone AS zone,
            COUNT(carousals.carousal_id) AS carousals_count
        FROM
            plants
        LEFT JOIN carousals ON plants.id = carousals.plant_id
        GROUP BY
            plants.short_name,
            plants.plant_name,
            plants.zone
        ORDER BY
            plants.short_name;
        """

        data = self.get_data(queryString, records=True, params=params)
        return data

    def getPlantsConfigByShortName(self, shortName):
        queryString = f"""
                        SELECT
                            plants.short_name AS short_name,
                            plants.plant_name AS name,
                            plants.zone AS zone,
                            COUNT(carousals.carousal_id) AS carousals_count
                        FROM
                            plants
                        LEFT JOIN carousals ON plants.id = carousals.plant_id
                        WHERE plants.short_name = '{shortName}'
                        GROUP BY plants.short_name, plants.plant_name, plants.zone
                        ORDER BY plants.short_name;
                        """
        params = {
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            }

        result = self.get_data(queryString, records=True, params=params)
        if result and len(result) == 1:
            return result[0]
        return None

    def getPlantIdByShortName(self, plantShortName):
        query = f""" select * from plants where "short_name"='{plantShortName}' limit 1;"""
        params = {
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            }
        data = self.get_data(query, records=True, params=params)
        if data:
            return data[0]['id']
        return False


    def getBreaks(self, plantId, carousalId):
        query = f""" select * from breaks where "plant_id"='{plantId}' and "carousal_id"='{carousalId}' """
        params = {
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            }
        result = self.get_data(query, records=True, params=params)
        if not result:
            return False

        breaks = {}
        for key, row in enumerate(result):
            breaks[key] = {
                'from': row['start_time'],
                'to': row['stop_time']
            }
        return breaks


    def getCarousalConfig(self, plantShortName):
        plantId = self.getPlantIdByShortName(plantShortName)
        if not plantId:
            return False
        query = f""" select * from carousals where "plant_id"='{plantId}' """
        params = {
            "host": "10.90.38.162",
            "database": "hpcl_ceg",
            "user": "ceg_user",
            "password": "TTNqetkiJLPM50jC",
            "port": 5432
            }
        result = self.get_data(query, records=True, params=params)
        if not result:
            return False
        config = {}
        for row in result:
            config[row['carousal_id']] = {
                'heads': row['heads'],
                'stdOutput': row['rated_productivity'],
                'times': {
                    'start': row['start_time'],
                    'end': row['stop_time'],
                    'breaks': self.getBreaks(plantId, row['carousal_id'])
                }
            }
        return config


    def getCarousals(self, type):
        carousal_config = self.getCarousalConfig(self.plantShortName)
        if carousal_config:
            if type == 'string':
                carousals = ", ".join(f"'{key}'" for key in carousal_config.keys())
            elif type == 'array':
                carousals = list(carousal_config.keys())
            elif type == 'full':
                carousals = carousal_config
            else:
                carousals = ", ".join(map(str, carousal_config.keys()))
            return carousals


    def getBottlingSummary(self, from_datetime, to_datetime):
        carousals = self.getCarousals("string")
        queryString = f""" SELECT
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
                        FROM lpg_operations_data
                        WHERE process_date BETWEEN '{from_datetime}' AND '{to_datetime}'
                            AND process_id IN (2, 22)
                            AND system_id IN ({carousals})
                            AND cyl_type IN (1, 2)
                            AND process_status NOT IN (1296, 5392, 17424)
                            AND "Plant Name"='{self.plantShortName.capitalize()}'
                        GROUP BY system_id
                        ORDER BY system_id """
        data = self.get_data(queryString, records=True)
        carousals = self.getCarousals("array")
        result = {}
        if data and (data[0].get("production_14_2", 0) > 0 or data[0].get("production_19", 0) > 0):
            for d in data:
                for c in carousals:
                    if str(c) == str(d.get("carousal")):
                        result[c] = d
            return result
        return data


    def getStartEndTimes(self, carousal):
        carousalConfig = self.getCarousalConfig(self.plantShortName)
        if not carousalConfig:
            raise Exception("Error Processing Request: Carousal configuration not found")
        return {
            'start': carousalConfig[int(carousal)]['times']['start'],
            'end': carousalConfig[int(carousal)]['times']['end'],
        }


    def buildOtProductionPeriodQuery(self, carousal, fromDate, toDate):
        startEndTimes = self.getStartEndTimes(carousal)
        startTime = startEndTimes['start']
        endTime = startEndTimes['end']
        queryString = f"""
                        WITH day_wise_data AS (
                            SELECT
                                process_date::date AS process_day,
                                to_char(process_date, 'HH24:MI:SS.MS') AS process_time,
                                process_date
                            FROM
                                lpg_operations_data
                            WHERE
                                process_date BETWEEN '{fromDate} 00:00:00' AND '{toDate} 23:59:59.999'
                                AND process_id IN (2, 22)
                                AND cyl_type IN (1, 2)
                                AND system_id = {carousal}
                                AND "Plant Name"='{self.plantShortName.capitalize()}'
                            ORDER BY
                                production_log_id ASC
                        ),
                        pre_shift_ot_periods AS (
                            SELECT
                                process_day,
                                MAX(process_time::time) - MIN(process_time::time) AS production_time
                            FROM
                                day_wise_data
                            WHERE
                                process_time::time BETWEEN '00:00:00'::time AND '{startTime}'::time
                            GROUP BY
                                process_day
                        ),
                        post_shift_ot_periods AS (
                            SELECT
                                process_day,
                                MAX(process_time::time) - MIN(process_time::time) AS production_time
                            FROM
                                day_wise_data
                            WHERE
                                process_time::time BETWEEN '{endTime}'::time AND '23:59:59.999'::time
                            GROUP BY
                                process_day
                        )
                        SELECT
                            EXTRACT(EPOCH FROM (SELECT SUM(production_time) FROM pre_shift_ot_periods)) / 3600 AS total_pre_shift_time,
                            EXTRACT(EPOCH FROM (SELECT SUM(production_time) FROM post_shift_ot_periods)) / 3600 AS total_post_shift_time;
                        """
        return queryString


    def getOtProductionPeriod(self, carousal, fromDate, toDate):
        queryString = self.buildOtProductionPeriodQuery(carousal, fromDate, toDate)
        data = self.get_data(queryString, records=True)
        if data:
            data = data[0]
        return data


    def getOtProductionPeriodForAllCarousals(self, fromDate, toDate):
        carousalsArray = self.getCarousals("array")
        data = {}
        if not carousalsArray:
            return data
        for carousal in carousalsArray:
            data[carousal] = self.getOtProductionPeriod(carousal, fromDate, toDate)
        return data


    def calculateProductivityV2(self, bottlingData, production_hours_data, ot_production_time):
        phases = ['normal', 'break', 'overtime']
        productivity_data = {}
        for car, b_data in bottlingData.items():
            car = str(car)
            for phase in phases:
                print("--")
                print("b_data :", b_data)
                print("phase :", phase)
                print("--")
                total_production = b_data[phase]['prod_14_2'] + 1.25 * b_data[phase]['prod_19']
                gap_hours = production_hours_data[car][f"total_{phase}_gap"]
                if gap_hours == None:
                    gap_hours = 0
                gap_hours = round(float(gap_hours), 2)
                if phase != 'overtime':
                    max_hours = production_hours_data[car]['max_op_hours'][phase]
                    productivity_data.setdefault(car, {}).setdefault(phase, {})['net_hours'] = round(float(max_hours), 2) - round(float(gap_hours), 2)
                else:
                    total_post_shift_time = ot_production_time[int(car)]['total_post_shift_time']
                    total_pre_shift_time = ot_production_time[int(car)]['total_pre_shift_time']
                    if total_post_shift_time:
                        total_post_shift_time = float(total_post_shift_time)
                    else:
                        total_post_shift_time = 0
                    if total_pre_shift_time:
                        total_pre_shift_time = float(total_pre_shift_time)
                    else:
                        total_pre_shift_time = 0

                    productivity_data.setdefault(car, {}).setdefault(phase, {})['net_hours'] = (
                        total_pre_shift_time + total_post_shift_time - gap_hours
                    )
                productivity_data[car][phase]['total_production'] = total_production
                if productivity_data[car][phase]['net_hours'] == 0:
                    productivity_data[car][phase]['productivity'] = 0
                else:
                    productivity_data[car][phase]['productivity'] = float(total_production) / float(productivity_data[car][phase]['net_hours'])
        return productivity_data

    def configToPhases(self, config):
        phases = {}
        for key, value in config.items():
            start = value['times']['start']
            end = value['times']['end']
            breaks = value['times']['breaks']

            working_periods = []
            break_periods = []
            overtime_periods = []

            current_start = start

            for break_period in breaks.values():
                break_start = break_period['from']
                break_end = break_period['to']

                if current_start < break_start:
                    working_periods.append({
                        'from': current_start,
                        'to': break_start
                    })

                break_periods.append(break_period)

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
                'to': '23:59:59.999'
            })

            phases[key] = {
                'working': working_periods,
                'breaks': break_periods,
                'overtime': overtime_periods
            }

        return phases


    def getPhases(self):
        carousalConfig = self.getCarousalConfig(self.plantShortName)
        if not carousalConfig:
            #raise Exception("Error Processing Request")
            return {}
        phases = self.configToPhases(carousalConfig)
        return phases


    def getPhasedProductionDataQueryString(self, carousal, from_date, to_date):
        phases = self.getPhases()

        normal_phase_string_array = []
        for working_phase in phases[carousal]['working']:
            normal_phase_string_array.append(f"process_date::time between '{working_phase['from']}'::time and '{working_phase['to']}'::time")
        normal_phase_string = " or ".join(normal_phase_string_array)

        break_phase_string_array = []
        for break_phase in phases[carousal]['breaks']:
            break_phase_string_array.append(f"process_date::time between '{break_phase['from']}'::time and '{break_phase['to']}'::time")
        break_phase_string = " or ".join(break_phase_string_array)

        query_string = f"""
        WITH phased_data as (
            SELECT
                *,
                CASE
                    WHEN {normal_phase_string} THEN 'normal'
                    WHEN {break_phase_string} THEN 'break'
                    ELSE 'overtime'
                END as phase
            FROM
                lpg_operations_data
            WHERE
                process_date BETWEEN '{from_date} 00:00:00' AND '{to_date} 23:59:59.999'
                AND process_id IN (2, 22)
                AND process_status NOT IN (1296, 5392, 17424)
                AND system_id = '{carousal}'
                AND "Plant Name"='{self.plantShortName.capitalize()}'
        )
        SELECT
            phase,
            SUM(CASE WHEN cyl_type = 1 THEN 1 ELSE 0 END) AS prod_14_2,
            SUM(CASE WHEN cyl_type = 2 THEN 1 ELSE 0 END) AS prod_19
        FROM
            phased_data
        GROUP BY phase;
        """
        return query_string



    def getPhaseWiseProduction(self, carousal, fromDate, toDate):
        phases = self.getPhases()
        query_string = self.getPhasedProductionDataQueryString(carousal, fromDate, toDate)

        data = self.get_data(query_string, records=True)

        blank_prod_data = {
            'prod_14_2': 0,
            'prod_19': 0,
        }

        return_data = {
            'normal': blank_prod_data,
            'break': blank_prod_data,
            'overtime': blank_prod_data,
        }

        for phase_data in data:
            phase = phase_data['phase']
            if phase in return_data:
                return_data[phase] = phase_data
        return return_data


    def getPhaseWiseProductionForAllCarousals(self, fromDate, toDate):
        carousalsArray = self.getCarousals("array")
        data = {}
        if not carousalsArray:
            return data
        for carousal in carousalsArray:
            prod_data = self.getPhaseWiseProduction(carousal, fromDate, toDate)
            data[carousal] = prod_data
        return data

    def getDailyOperatingHours(self):
        operating_time = {}
        phases = self.getPhases()
        for carousal, phase_data in phases.items():
            total_working_seconds = 0
            total_break_seconds = 0
            # Calculate total working time
            for working_period in phase_data['working']:
                start_time = datetime.strptime(working_period['from'], "%H:%M:%S")
                end_time = datetime.strptime(working_period['to'], "%H:%M:%S")
                total_working_seconds += (end_time - start_time).total_seconds()

            for break_period in phase_data['breaks']:
                start_time = datetime.strptime(break_period['from'], "%H:%M:%S")
                end_time = datetime.strptime(break_period['to'], "%H:%M:%S")
                total_break_seconds += (end_time - start_time).total_seconds()

            total_working_hours = total_working_seconds / 3600
            total_break_hours = total_break_seconds / 3600

            operating_time[carousal] = {
                'normal': total_working_hours,
                'break': total_break_hours,
            }
        return operating_time


    def buildProductionGapQuery(self, carousal, phases, start_time, end_time):
        min_interruption = 30
        normal_gap_string_array = [
            f"getGapBetweenTimes(process_time, prev_process_time, '{phase['from']}'::text, '{phase['to']}'::text)"
            for phase in phases.get('working', [])
        ]
        normal_gap_string = " + ".join(normal_gap_string_array)

        break_gap_string_array = [
            f"getGapBetweenTimes(process_time, prev_process_time, '{phase['from']}'::text, '{phase['to']}'::text)"
            for phase in phases.get('breaks', [])
        ]
        break_gap_string = " + ".join(break_gap_string_array)
        overtime_gap_string_array = [
            f"(process_time::time BETWEEN '{phase['from']}'::time AND '{phase['to']}'::time "
            f"AND prev_process_time::time BETWEEN '{phase['from']}'::time AND '{phase['to']}'::time)"
            for phase in phases.get('overtime', [])
        ]
        overtime_gap_string = " OR ".join(overtime_gap_string_array)

        normal_end_gap_string_array = [
            f"getEndGapForPhase(last_cyl_time, '{phase['from']}', '{phase['to']}')"
            for phase in phases.get('working', [])
        ]
        normal_end_gap_string = " + ".join(normal_end_gap_string_array)

        break_end_gap_string_array = [
            f"getEndGapForPhase(last_cyl_time, '{phase['from']}', '{phase['to']}')"
            for phase in phases.get('breaks', [])
        ]
        break_end_gap_string = " + ".join(break_end_gap_string_array)

        query_string = f"""
        WITH day_wise_data AS (
            SELECT
                process_date::date AS process_day,
                TO_CHAR(process_date, 'HH24:MI:SS.MS') AS process_time,
                process_date,
                system_id,
                process_status,
                cyl_type,
                production_log_id
            FROM lpg_operations_data
            WHERE process_date BETWEEN '{start_time} 00:00:00' AND '{end_time} 23:59:59.999'
            AND process_id IN (2, 22)
            AND cyl_type IN (1, 2)
            AND system_id = {carousal}
            AND "Plant Name"='{self.plantShortName.capitalize()}'
            ORDER BY production_log_id ASC
        ),
        time_gaps AS (
            SELECT
                process_day,
                production_log_id,
                system_id,
                process_date,
                process_time,
                LAG(process_time) OVER (PARTITION BY system_id, process_day ORDER BY process_time) AS prev_process_time
            FROM day_wise_data
        ),
        grouped_gaps AS (
            SELECT
                process_day,
                system_id,
                process_time,
                prev_process_time,
                CASE
                    WHEN prev_process_time IS NOT NULL AND ({overtime_gap_string})
                        THEN process_time::time - prev_process_time::time
                    ELSE '0 seconds'::interval
                END AS overtime_gap,
                {break_gap_string} AS break_gap,
                {normal_gap_string} AS normal_gap
            FROM time_gaps
        ),
        last_cyl_data AS (
            SELECT
                process_day,
                MAX(process_time::time) AS last_cyl_time
            FROM day_wise_data
            GROUP BY process_day
        ),
        end_gap_data AS (
            SELECT
                process_day,
                last_cyl_time,
                {normal_end_gap_string} AS normal_end_gap,
                {break_end_gap_string} AS break_end_gap
            FROM last_cyl_data
        ),
        process_days AS (
            SELECT DISTINCT process_day FROM day_wise_data
        ),
        intervening_gaps_data AS (
            SELECT
                pd.process_day,
                COALESCE(SUM(gg.break_gap), INTERVAL '0') AS total_break_gap,
                COALESCE(SUM(gg.normal_gap), INTERVAL '0') AS total_normal_gap,
                COALESCE(SUM(gg.overtime_gap), INTERVAL '0') AS total_overtime_gap
            FROM process_days pd
            LEFT JOIN grouped_gaps gg
                ON pd.process_day = gg.process_day
                AND (gg.break_gap + gg.normal_gap + gg.overtime_gap) > '{min_interruption} seconds'::interval
            GROUP BY pd.process_day
        )
        SELECT
            EXTRACT(EPOCH FROM SUM(igd.total_normal_gap + egd.normal_end_gap)) / 3600 AS total_normal_gap,
            EXTRACT(EPOCH FROM SUM(igd.total_break_gap + egd.break_end_gap)) / 3600 AS total_break_gap,
            EXTRACT(EPOCH FROM SUM(igd.total_overtime_gap)) / 3600 AS total_overtime_gap
        FROM intervening_gaps_data igd
        LEFT JOIN end_gap_data egd ON igd.process_day = egd.process_day;
        """
        return query_string


    def getGapBetweenTimesFunctionCreateString(self):
        queryString = """
                    CREATE OR REPLACE FUNCTION getGapBetweenTimes(process_time TEXT, prev_process_time TEXT, start_time TEXT, end_time TEXT)
                    RETURNS INTERVAL AS $function$
                    BEGIN
                        RETURN CASE
                            WHEN prev_process_time IS NULL THEN
                                CASE
                                    WHEN process_time::time <= start_time::time THEN '0 seconds'::interval
                                    WHEN process_time::time >= end_time::time THEN end_time::time - start_time::time
                                    ELSE process_time::time - start_time::time
                                END
                            WHEN process_time::time > end_time::time AND prev_process_time::time > end_time::time THEN '0 seconds'::interval
                            WHEN process_time::time < start_time::time AND prev_process_time::time < start_time::time THEN '0 seconds'::interval
                            WHEN prev_process_time::time >= start_time::time AND process_time::time <= end_time::time THEN process_time::time - prev_process_time::time
                            WHEN prev_process_time::time < start_time::time AND process_time::time > end_time::time THEN end_time::time - start_time::time
                            WHEN prev_process_time::time < start_time::time AND process_time::time BETWEEN start_time::time AND end_time::time THEN process_time::time - start_time::time
                            WHEN process_time::time > end_time::time AND prev_process_time::time BETWEEN start_time::time AND end_time::time THEN end_time::time - prev_process_time::time
                            ELSE '2 days'::interval
                        END;
                    END;
                    $function$ LANGUAGE plpgsql;
                    """
        return queryString


    def getEndGapFunctionCreateString(self):
        queryString = """
                    CREATE OR REPLACE FUNCTION getEndGapForPhase(last_cyl_time TIME, phase_start TEXT, phase_end TEXT)
                    RETURNS INTERVAL AS $function$
                    BEGIN
                        RETURN CASE
                            WHEN last_cyl_time < phase_start::time THEN phase_end::time - phase_start::time
                            WHEN last_cyl_time > phase_end::time THEN '0 seconds'::interval
                            WHEN last_cyl_time BETWEEN phase_start::time AND phase_end::time THEN phase_end::time - last_cyl_time
                            ELSE '0 seconds'::interval
                        END;
                    END;
                    $function$ LANGUAGE plpgsql;
                    """
        return queryString


    def getProductionGaps(self, carousal, fromDate, toDate):
        phases = self.getPhases()
        queryString = self.buildProductionGapQuery(carousal, phases[carousal], fromDate, toDate)

        gapBetweenTimesFunctionCreateString = self.getGapBetweenTimesFunctionCreateString()
        endGapFunctionCreateString = self.getEndGapFunctionCreateString()

        # self.get_data(gapBetweenTimesFunctionCreateString, runOnly=True)
        # self.get_data(endGapFunctionCreateString, runOnly=True)
        print("queryString :", queryString)
        data = self.get_data(queryString, records=True)
        if data:
            data = data[0]
        return data

    def getNonOperatingDays(self, carousal, from_date, to_date):
        query_string = f""" WITH all_dates AS (
                      SELECT generate_series('{from_date}'::date, '{to_date}'::date, '1 day'::interval) AS process_day
                        ),
                        row_counts AS (
                            SELECT
                                process_date::date AS process_day,
                                COUNT(*) AS row_count
                            FROM
                                lpg_operations_data
                            WHERE
                                process_date BETWEEN '{from_date} 00:00:00' AND '{to_date} 23:59:59'
                                AND system_id = '{carousal}'
                                AND process_id IN (1, 2, 22)
                                AND process_status NOT IN (16)
                                AND "Plant Name"='{self.plantShortName.capitalize()}'
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
                        select count(days) from empty_days; """

        data = self.get_data(query_string, records=True)
        if data:
            data = data[0]['count']
        return data


    def getProductionGapsForAllCarousals(self, from_date, to_date):
        datetime1 = datetime.strptime(from_date, "%Y-%m-%d")
        datetime2 = datetime.strptime(to_date, "%Y-%m-%d")
        if datetime1 > datetime2:
            return None
        total_intervening_days = (datetime2 - datetime1).days + 1
        carousals_array = self.getCarousals("array")
        daily_operating_hours = self.getDailyOperatingHours()
        data = {}
        if not carousals_array:
            return data
        print("carousals_array :", carousals_array)
        for carousal in carousals_array:
            production_gaps = self.getProductionGaps(carousal, from_date, to_date)
            carousal = str(carousal)
            print("carousal :", carousal)
            data[carousal] = production_gaps
            print(data)
            data[carousal]['carousal'] = carousal
            data[carousal]['intervening_days'] = total_intervening_days

            non_op_days = self.getNonOperatingDays(carousal, from_date, to_date)
            data[carousal]['non_op_days'] = non_op_days

            net_op_days = total_intervening_days - non_op_days
            data[carousal]['net_op_days'] = net_op_days

            daily_op_hours = daily_operating_hours[int(carousal)]
            data[carousal]['daily_op_hours'] = daily_op_hours

            max_normal_op_hours = daily_op_hours['normal'] * net_op_days
            max_break_op_hours = daily_op_hours['break'] * net_op_days
            data[carousal]['max_op_hours'] = {
                'normal': max_normal_op_hours,
                'break': max_break_op_hours
            }

            total_normal_gap = production_gaps['total_normal_gap']
            total_break_gap = production_gaps['total_break_gap']
            print("max_normal_op_hours :", max_normal_op_hours)
            print("total_normal_gap :", total_normal_gap)
            print("max_break_op_hours :", max_break_op_hours)
            print("total_break_gap :", total_break_gap)
            #if not total_normal_gap['total_break_gap']:
            #    total_normal_gap = 0
            if total_break_gap == None:
                total_break_gap = 0
            if total_normal_gap == None:
                total_normal_gap = 0
            data[carousal]['net_op_hours'] = {
                'normal': round(float(max_normal_op_hours)) - round(float(total_normal_gap)),
                'break': round(float(max_break_op_hours)) - round(float(total_break_gap))
            }
        return data


    def flatten_dict(self, d, parent_key='', sep='_'):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


    def getPerformanceReportV2Data(self, plant, fromDate, toDate):
        from_datetime = datetime.strptime(fromDate + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
        to_datetime = datetime.strptime(toDate + ' 23:59:59.999', '%Y-%m-%d %H:%M:%S.%f')

        #productionLogModel->setPlant($plant);
        # bottlingData = self.getBottlingSummary(from_datetime, to_datetime)

        otProductionTime = self.getOtProductionPeriodForAllCarousals(fromDate, toDate)
        print("otProductionTime :", otProductionTime)
        bottlingData = self.getPhaseWiseProductionForAllCarousals(fromDate, toDate)
        print("bottlingData :", bottlingData)
        productionHoursData = self.getProductionGapsForAllCarousals(fromDate, toDate)
        print("productionHoursData :", productionHoursData)

        data = {
            "carousals" : self.getCarousals("full"),
            "bottlingData": bottlingData,
            "productionHoursData": productionHoursData,
            "productivityData": self.calculateProductivityV2(bottlingData, productionHoursData, otProductionTime)
            }

        # carousals_df = pd.DataFrame.from_dict({k: self.flatten_dict(v) for k, v in data['carousals'].items()}, orient='index')
        # bottling_data_df = pd.DataFrame.from_dict({k: self.flatten_dict(v) for k, v in data['bottlingData'].items()}, orient='index')
        # production_hours_df = pd.DataFrame.from_dict({k: self.flatten_dict(v) for k, v in data['productionHoursData'].items()}, orient='index')
        # productivity_data_df = pd.DataFrame.from_dict({k: self.flatten_dict(v) for k, v in data['productivityData'].items()}, orient='index')

        # print(carousals_df)
        # print(bottling_data_df)
        # print(production_hours_df)
        # print(productivity_data_df)

        # output_file = "/tmp/ConsolidatedLPG.xlsx"
        # writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
        # carousals_df.to_excel(writer, sheet_name='Carousals', index=True)
        # bottling_data_df.to_excel(writer, sheet_name='bottling_data', index=True)
        # production_hours_df.to_excel(writer, sheet_name='production_hours', index=True)
        # productivity_data_df.to_excel(writer, sheet_name='productivity_data', index=True)
        # writer._save()

        if not data:
            data = {
                'status': 'success',
                'message': 'No data found!',
                'data': []
            }
            return data
        if data:
            data = {
                'status': 'success',
                'message': 'Data Fetched Successfully!',
                'data': data
            }
            return data


    def getPerformanceData(self, fromDate, toDate, plantShortName):
        query = f""" SELECT * FROM lpg_operations_data WHERE "Plant Name"='{self.plantShortName.capitalize()}' LIMIT 10"""
        datacheck = self.get_data(query)
        if not datacheck:
            return pd.DataFrame()
        query = f"""SELECT MAX(process_date) AS max_datetime FROM "lpg_operations_data" WHERE CAST(process_date AS DATE) = '{fromDate}' AND "Plant Name"='{self.plantShortName.capitalize()}';"""
        print("query -->", query)
        process_date =  self.get_data(query, runOnly=True)
        print("process_date :", process_date)
        if not process_date:
            return pd.DataFrame()
        allPlants = self.getAllPlantsConfig()
        carousalCounts = {}
        zoneMaps = {}
        for plant in allPlants:
            carousalCounts[plant['value']] = plant['carousals_count']
            zoneMaps[plant['value']] = plant['zone']
        plant = self.getPlantsConfigByShortName(self.plantShortName)
        response = self.getPerformanceReportV2Data(self.plantShortName, fromDate, toDate)
        data = {}
        if response['status'] == 'success':
            data['plant'] = plant
            data.update(response['data'])
        else:
            data['plant'] = plant

        transformData = self.transformData([data], carousalCounts, zoneMaps)
        df = pd.json_normalize(transformData)
        # df['process_date'] = datetime.strptime(process_date, "%Y-%m-%d %H:%M:%S.%f")
        df['process_date'] = process_date
        return df


    def transformData(self, data, carousal_counts, zone_maps):
        """
        Transforms raw data into a structured list of dictionaries for further processing.

        Args:
            data (list): The raw input data to be transformed.
            carousal_counts (dict): A mapping of short names to carousal counts.
            zone_maps (dict): A mapping of plant short names to zones.

        Returns:
            list: A list of transformed rows with detailed metrics.
        """
        rows = []
        # Loop through each data row (representing a plant).
        print("data :", data)
        for d_row in data:
            # Loop through each carousal in the current plant data.
            print("---")
            print("d_row :", d_row)
            if not d_row['carousals']:
                return rows
            for car_id, car in d_row['carousals'].items():
                row = {}
                # Check if the carousal is an additional one (id greater than 1).
                row['is_additional_carousel'] = car_id > 1
                # Add plant details such as short name, full name, and zone.
                row['short_name'] = d_row['plant']['short_name']
                row['name'] = d_row['plant']['name']
                row['zone'] = zone_maps[row['short_name']]
                # Add carousal-specific details.
                row['carousel'] = car_id
                row['filling_heads'] = car['heads']
                row['carousel_count'] = carousal_counts[row['short_name']]
                # Calculate bottling data for different products.
                row['bottling'] = {
                    '14_2kg': (
                        d_row['bottlingData'][car_id]['normal']['prod_14_2']
                        + d_row['bottlingData'][car_id]['break']['prod_14_2']
                        + d_row['bottlingData'][car_id]['overtime']['prod_14_2']
                    ),
                    '19kg': (
                        d_row['bottlingData'][car_id]['normal']['prod_19']
                        + d_row['bottlingData'][car_id]['break']['prod_19']
                        + d_row['bottlingData'][car_id]['overtime']['prod_19']
                    ),
                }
                row['bottling']['total'] = row['bottling']['14_2kg'] + row['bottling']['19kg']

                # Process productivity metrics for normal, break, and overtime periods.
                stoppages = d_row['productionHoursData'][str(car_id)]['total_normal_gap']

                if stoppages == None:
                    stoppages = 0
                row['productivity'] = {
                    'normal': {
                        'production': d_row['productivityData'][str(car_id)]['normal']['total_production'],
                        'stoppages': round(float(stoppages), 2),
                        'productivity': round(float(d_row['productivityData'][str(car_id)]['normal']['productivity']), 0),
                    },
                    'break': {
                        'production': d_row['productivityData'][str(car_id)]['break']['total_production'],
                        'net_hours': round(float(d_row['productivityData'][str(car_id)]['break']['net_hours']), 2),
                        'productivity': round(float(d_row['productivityData'][str(car_id)]['break']['productivity']), 0),
                    },
                    'overtime': {
                        'production': d_row['productivityData'][str(car_id)]['overtime']['total_production'],
                        'net_hours': round(float(d_row['productivityData'][str(car_id)]['overtime']['net_hours']), 2),
                        'productivity': round(float(d_row['productivityData'][str(car_id)]['overtime']['productivity']), 0),
                    },
                }

                # Calculate rejection percentages for different categories.
                gd_summary = d_row.get('gdRejectionSummary', {}).get(car_id, {})
                row['rejections'] = {
                    'eld': {
                        'percent': (
                            round((gd_summary['rejected'] / gd_summary['total']) * 100, 2)
                            if gd_summary.get('total', 0) != 0
                            else 0
                        )
                    }
                }

                pt_summary = d_row.get('ptRejectionSummary', {}).get(car_id, {})
                row['rejections']['ort'] = {
                    'percent': (
                        round((pt_summary['rejected'] / pt_summary['total']) * 100, 2)
                        if pt_summary.get('total', 0) != 0
                        else 0
                    )
                }

                cs_summary = d_row.get('checkScaleRejectionSummary', {}).get(car_id, {})
                row['rejections']['cs'] = {
                    'percent': (
                        round((cs_summary['totalSortout'] / cs_summary['total']) * 100, 2)
                        if cs_summary.get('total', 0) != 0
                        else 0
                    )
                }

                rows.append(row)
        return rows


def insertToDB(data, table_name):
    data = pl.from_pandas(data)
    pg_conn = psycopg2.connect(
                host="10.90.38.162",
                database="hpcl_ceg",
                user="ceg_user",
                password="TTNqetkiJLPM50jC",
                port=5432
            )
    table_create_sql = ''
    cur = pg_conn.cursor()
    dtype_dict = {'String':str('text'),'Int64': str('text'), 'Int32': str('text'), 'Boolean': str('text'), 'Float64': str('double precision'),'Float32': str('double precision'),
                  'Object': str('text'), 'Datetime': str('timestamp'), 'Utf8': str('text'), "Datetime(time_unit='us', time_zone=None)": str('timestamp')}
    print('Data Types :',data.dtypes)
    col_dtype = {col: data[col].dtype for col in data.columns}
    for col, dty in col_dtype.items():
        dty = dtype_dict.get(str(dty))
        table_create_sql += f'"{col}" {dty},'
    table_create_sql = table_create_sql[:-1]

    create_table_index = f'CREATE INDEX IF NOT EXISTS "{table_name}_index" ON "{table_name}" ("carousel", "short_name")'
    table_create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({table_create_sql})'
    print("table_create_sql :", table_create_sql)
    cur.execute(table_create_sql)
    pg_conn.commit()
    cur.execute(create_table_index)

    sql = f"""SELECT * FROM "{table_name}" LIMIT 1"""
    cur.execute(sql)
    column_names = [desc[0] for desc in cur.description]
    columns=[]
    for i in column_names:
        columns.append(i)
    data = data.select(columns)
    try:
        query = f'''
        COPY "{table_name}"
        FROM STDIN
        CSV HEADER DELIMITER '~';
        '''
        for g, split_df in data.group_by(len(data)// 10000000):
            csv_file = f'/tmp/{table_name}.csv'
            split_df.write_csv(csv_file, separator='~')
            with open(csv_file, 'r') as f:
                cur.copy_expert(query, f)
                pg_conn.commit()
        cur.close()
        if os.path.exists(f'/tmp/{table_name}.csv'):
            os.remove(f'/tmp/{table_name}.csv')
    except Exception as e:
        print("Error :", str(e))
        raise Exception(e)
    
def generate_summary():
    host =  "10.90.38.162"
    database = "hpcl_ceg"
    user = "ceg_user"
    password = "TTNqetkiJLPM50jC"
    port = 5432
    # Create database connection for fetching max date
    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        port=port
    )
    cursor = conn.cursor()
    df = pl.read_csv("/opt/ceg/algo/LPG/LPG_PLANTS_CREDENTIALS.csv")
    try:
        for plant in df.iter_rows(named=True):
            location = plant["short_name"]
            ###### START DATE ######
            query = f""" SELECT MIN("process_date") FROM lpg_operations_data WHERE "Plant Name" = '{location.capitalize()}' """
            print("min query :", query)
            cursor.execute(query)
            start_date = cursor.fetchone()[0]
            if start_date:
                start_date = start_date.strftime("%Y-%m-%d")
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
            ###### END DATE ######
            query = f""" SELECT MAX("process_date") FROM lpg_operations_data WHERE "Plant Name" = '{location.capitalize()}' """
            print("max query :", query)
            cursor.execute(query)
            end_date = cursor.fetchone()[0]
            if end_date:
                end_date = end_date.strftime("%Y-%m-%d")
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
            current_date = start_date
            if not start_date:
                print("*"*50)
                print(f"No Data Found for {location}")
                print("*"*50)
                continue
            print(f"Processing --> {location} from {start_date.date()} to {end_date.date()}")
            # Process each date for this location
            while current_date <= end_date:
                print("-"*50)
                print("DATE --->", current_date)
                print("-"*50)
                fromDate = current_date.strftime("%Y-%m-%d")
                toDate = current_date.strftime("%Y-%m-%d")            
                print("location -->", location)
                ins = LPG_CONSOLIDATED(host, database, user, password, port, location)
                data = ins.getPerformanceData(fromDate, toDate, location)
                print("*-"*25)
                print(f"Summary of {location}  :")
                print(data)
                print("*-"*25)
                if not data.empty:
                    for col in data.columns:
                        try:
                            data[col] = data[col].fillna(0).astype(np.float64)
                        except Exception as e:
                            print(f"- Could Not Convert {col} to Float -")
                    insertToDB(data, "LPG_OPERATIONS_SUMMARY_DATA")
                    
                    for col in data.columns:
                        data.rename(columns={col: col.replace(".","_")}, inplace=True)
                    data.rename(columns={"short_name": "location"}, inplace=True)
                    data["sap_id"] = plant["erp_id"]
                    data["SiteRegion"] = plant["SiteRegion"]
                    data['SiteArea'] = plant["SiteArea"]
                    data["bu"] = "LPG"
                    if "filling_heads" in data.columns:
                        data["filling_heads"] = data["filling_heads"].astype(str) + "H"
                    insertToDB(data, "lpg_operations_summary")
                current_date += timedelta(days=1)
    except Exception as e:
        print("-- Exception While Running Lpg Operations Data Sync --")
        print("traceback :", traceback.format_exc())
        query = f""" TRUNCATE lpg_operations_data; """
        cursor.execute(query)
        conn.commit()
        cursor.close()
        conn.close()
    
    query = f""" TRUNCATE lpg_operations_data; """
    cursor.execute(query)
    conn.commit()
    cursor.close()
    conn.close()
    print("*"*50)
    print("*"*10, " Completed ", "*"*10)
    print("*"*50)

if __name__=="__main__":
    generate_summary()