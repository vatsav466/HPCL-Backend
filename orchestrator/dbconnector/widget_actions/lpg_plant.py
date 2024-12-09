import urdhva_base
import utilities.helpers as helpers


class LPGPlantActions:
    @staticmethod
    def get_production_details(filters):
        timezone_format = 'YYYY-MM-DD HH24:MI:SS.US'
        production_query = f'''SELECT SUM("productivity.normal.production")/1000 AS total_production,
        AVG("productivity.normal.production") AS average_production
FROM public.lpg_consolidated_data
WHERE process_date >= TO_TIMESTAMP('{helpers.get_time_stamp_by_delta(months=1)} 00:00:00.000000', '{timezone_format}')
  AND process_date < TO_TIMESTAMP('{helpers.get_time_stamp_by_delta(months=0)}  00:00:00.000000', '{timezone_format}')
LIMIT 50000;'''

        rejection_query = f'''SELECT AVG(sortoutpercentage)/100 AS cs_rejections
FROM
  (WITH aggregated_data AS
     (SELECT el.system_id,
             el.process_id,
             el.process_status,
             COUNT(el.event_log_id) AS count,
             REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\1') AS plant_name,
             el.process_date::DATE AS process_date
      FROM lpg_event_log_data el
      WHERE el.system_id IN (1,
                             2)
        AND el.process_id IN (4,
                              24)
      GROUP BY el.system_id,
               el.process_id,
               el.process_status,
               REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\1'),
               el.process_date::DATE),
        mapped_data AS
     (SELECT ad.system_id,
             ad.process_id,
             ad.process_status,
             ad.count,
             ad.plant_name,
             ad.process_date,
             p.zone
      FROM aggregated_data ad
      LEFT JOIN plants p ON ad.plant_name = p.short_name) SELECT system_id,
                                                                 SUM(count) AS handled,
                                                                 SUM(count) FILTER (
                                                                                    WHERE process_status != 0) AS sortout,
                                                                 CASE
                                                                     WHEN SUM(count) > 0 THEN (SUM(count) FILTER (
                                                                                                                  WHERE process_status != 0) * 1.0) / SUM(count)
                                                                     ELSE 0
                                                                 END AS sortOutPercentage,
                                                                 plant_name,
                                                                 zone,
                                                                 process_date
   FROM mapped_data
   GROUP BY system_id,
            plant_name,
            zone,
            process_date) AS virtual_table
WHERE process_date >= TO_DATE('{helpers.get_time_stamp_by_delta(months=1)}', 'YYYY-MM-DD')
  AND process_date < TO_DATE('{helpers.get_time_stamp_by_delta(months=0)}', 'YYYY-MM-DD')
LIMIT 50000;'''


