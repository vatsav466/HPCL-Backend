import utilities.helpers as helpers
from datetime import datetime

today = datetime.now()
current_month = datetime.now().strftime("%B") # format : January, February
if today.month < 4:
    start_year = today.year - 1
else:
    start_year = today.year
end_year = start_year + 1
financial_year = f"{start_year}-{end_year}" # Format : 2024-2025


timezone_format = 'YYYY-MM-DD HH24:MI:SS.US'
lpg_plant_query = {
    "production_query": f'''SELECT SUM("productivity.normal.production")/1000 AS total_production,
        AVG("productivity.normal.production") AS average_production
FROM public.lpg_consolidated_data
WHERE process_date BETWEEN TO_TIMESTAMP('{helpers.get_time_stamp_by_delta(months=1)} 00:00:00.000000', '{timezone_format}')
  AND TO_TIMESTAMP('{helpers.get_time_stamp_by_delta(months=0)} 00:00:00.000000', '{timezone_format}')
LIMIT 50000;''',

    "rejection_query": f'''SELECT AVG(sortoutpercentage)/100 AS cs_rejections
FROM
  (WITH aggregated_data AS
     (SELECT el.system_id,
             el.process_id,
             el.process_status,
             COUNT(el.event_log_id) AS count,
             REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1') AS plant_name,
             el.process_date::DATE AS process_date
      FROM lpg_event_log_data el
      WHERE el.system_id IN (1,
                             2)
        AND el.process_id IN (4,
                              24)
      GROUP BY el.system_id,
               el.process_id,
               el.process_status,
               REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1'),
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
LIMIT 50000;''',

    "total_gd_rejection": f'''SELECT AVG(sortoutpercentage)/100 AS "Percentage"
FROM
  (WITH aggregated_data AS
     (SELECT el.system_id,
             el.process_id,
             el.process_status,
             COUNT(el.event_log_id) AS count,
             REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1') AS plant_name,
             el.process_date::DATE AS process_date
      FROM lpg_event_log_data el
      WHERE el.system_id IN (1,
                             2)
        AND el.process_id IN (3,
                              23)
      GROUP BY el.system_id,
               el.process_id,
               el.process_status,
               REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1'),
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
LIMIT 50000;''',

    "total_pt_rejection": f'''SELECT AVG(sortoutpercentage)/100 AS "AVG(sortoutpercentage)/100"
FROM
  (WITH aggregated_data AS
     (SELECT el.system_id,
             el.process_id,
             el.process_status,
             COUNT(el.event_log_id) AS count,
             REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1') AS plant_name,
             el.process_date::DATE AS process_date
      FROM lpg_event_log_data el
      WHERE el.system_id IN (1,
                             2)
        AND el.process_id IN (4,
                              24)
      GROUP BY el.system_id,
               el.process_id,
               el.process_status,
               REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1'),
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
LIMIT 50000;''',
    
    "productivity_cyl_per_hour": f'''SELECT zone AS zone,
               AVG("productivity.normal.productivity") AS "Total Productivity"
FROM public.lpg_consolidated_data
GROUP BY zone
ORDER BY COUNT(*) DESC
LIMIT 10000;''',

    "rejections_by_zones" : f'''SELECT zone AS zone,
               rejection_type AS rejection_type,
               AVG(sort_out_percentage) AS "AVG(sort_out_percentage)",
               COUNT(*) AS count
FROM public."Rejections"
GROUP BY zone,
         rejection_type
ORDER BY count DESC
LIMIT 10000;''',

    "daily_productivity_cyl_per_hour": f'''SELECT DATE_TRUNC('day', process_date) AS process_date,
       sum("productivity.normal.productivity") AS "Productivity"
FROM public.lpg_consolidated_data
GROUP BY DATE_TRUNC('day', process_date)
ORDER BY "Productivity" DESC
LIMIT 10000;''',
    
    "cyl_rejection_in_check_scale": f'''SELECT zone AS zone,
               AVG("sort_out_percentage") AS "AVG(""sort_out_percentage"")"
FROM
  (WITH aggregated_data AS
     (SELECT system_id,
             topic_name,
             DATE(process_date) AS process_date,
             COUNT(production_log_id) AS total_count,
             SUM(CASE
                     WHEN process_status IN (1040, 2064, 1296, 17424, 1048, 4120, 5392, 1041, 1042, 2192, 4112, 4113, 5136, 6160) THEN 1
                     ELSE 0
                 END) AS sort_outs,
             SUM(CASE
                     WHEN process_status < 0
                          OR process_status = 4096 THEN 1
                     ELSE 0
                 END) AS comm_errors
      FROM lpg_dncceg_data
      WHERE system_id IN (1,
                          2)
        AND process_id IN (2,
                           22)
      GROUP BY system_id,
               topic_name,
               DATE(process_date)),
        final_data AS
     (SELECT system_id,
             topic_name,
             process_date,
             total_count,
             total_count - sort_outs AS cyl_filled,
             sort_outs,
             comm_errors,
             CASE
                 WHEN total_count > 0 THEN sort_outs::FLOAT / total_count
                 ELSE 0
             END AS sort_out_percentage,
             REGEXP_REPLACE(topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1') AS plant_name
      FROM aggregated_data) SELECT fd.*,
                                   p.zone
   FROM final_data fd
   JOIN plants p ON p.short_name = fd.plant_name) AS virtual_table
GROUP BY zone
ORDER BY "AVG(""sort_out_percentage"")" DESC
LIMIT 1000;''',





    "cyl_rejection_in_gd": f'''SELECT zone AS zone,
               sum(sortoutpercentage) AS "Rejection Percentage"
FROM
  (WITH aggregated_data AS
     (SELECT el.system_id,
             el.process_id,
             el.process_status,
             COUNT(el.event_log_id) AS count,
             SUBSTRING(el.topic_name FROM '^.*_dncceg_([^-\s]+).*') AS plant_name,
             el.process_date::DATE AS process_date
      FROM lpg_event_log_data el
      WHERE el.system_id IN (1,
                             2)
        AND el.process_id IN (3,
                              23)
      GROUP BY el.system_id,
               el.process_id,
               el.process_status,
               SUBSTRING(el.topic_name FROM '^.*_dncceg_([^-\s]+).*'),
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
GROUP BY zone
ORDER BY "Rejection Percentage" DESC
LIMIT 1000;''',

    "cyl_rejection_in_pt": f'''SELECT zone AS zone,
               AVG("sortoutpercentage") AS "Percentage Rejection"
FROM
  (WITH aggregated_data AS
     (SELECT el.system_id,
             el.process_id,
             el.process_status,
             COUNT(el.event_log_id) AS count,
             REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1') AS plant_name,
             el.process_date::DATE AS process_date
      FROM lpg_event_log_data el
      WHERE el.system_id IN (1,
                             2)
        AND el.process_id IN (4,
                              24)
      GROUP BY el.system_id,
               el.process_id,
               el.process_status,
               REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1'),
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
GROUP BY zone
ORDER BY "Percentage Rejection" DESC
LIMIT 1000;''',

    "cyl_count_by_carousel": f'''SELECT carousel AS carousel,
       sum("bottling.14_2kg") AS "14.2 KG",
       sum("bottling.19kg") AS "19 KG"
FROM public.lpg_consolidated_data
GROUP BY carousel
ORDER BY "14.2 KG" DESC
LIMIT 1000;''',

    "cyl_count_by_zone": f'''SELECT zone AS zone,
               sum("bottling.14_2kg") AS "SUM(bottling.14_2kg)",
               sum("bottling.19kg") AS "SUM(bottling.19kg)",
               COUNT(*) AS count
FROM public.lpg_consolidated_data
WHERE process_date >= TO_TIMESTAMP('{helpers.get_time_stamp_by_delta(months=1)} 00:00:00.000000', '{timezone_format}')
  AND process_date < TO_TIMESTAMP('{helpers.get_time_stamp_by_delta(months=0)} 00:00:00.000000', '{timezone_format}')
GROUP BY zone
ORDER BY count DESC
LIMIT 10000;''',

    "bottom_cs_plants": f'''SELECT plant_name AS plant_name,
       system_id AS system_id,
       AVG("sort_out_percentage") AS "AVG(""sort_out_percentage"")"
FROM
  (WITH aggregated_data AS
     (SELECT system_id,
             topic_name,
             DATE(process_date) AS process_date,
             COUNT(production_log_id) AS total_count,
             SUM(CASE
                     WHEN process_status IN (1040, 2064, 1296, 17424, 1048, 4120, 5392, 1041, 1042, 2192, 4112, 4113, 5136, 6160) THEN 1
                     ELSE 0
                 END) AS sort_outs,
             SUM(CASE
                     WHEN process_status < 0
                          OR process_status = 4096 THEN 1
                     ELSE 0
                 END) AS comm_errors
      FROM lpg_dncceg_data
      WHERE system_id IN (1,
                          2)
        AND process_id IN (2,
                           22)
      GROUP BY system_id,
               topic_name,
               DATE(process_date)),
        final_data AS
     (SELECT system_id,
             topic_name,
             process_date,
             total_count,
             total_count - sort_outs AS cyl_filled,
             sort_outs,
             comm_errors,
             CASE
                 WHEN total_count > 0 THEN sort_outs::FLOAT / total_count
                 ELSE 0
             END AS sort_out_percentage,
             REGEXP_REPLACE(topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1') AS plant_name
      FROM aggregated_data) SELECT fd.*,
                                   p.zone
   FROM final_data fd
   JOIN plants p ON p.short_name = fd.plant_name) AS virtual_table
GROUP BY plant_name,
         system_id
ORDER BY COUNT(*) DESC
LIMIT 10000;''',

    "bottom_gd_plants": f'''SELECT plant_name AS plant_name,
       system_id AS system_id,
       sum(sortoutpercentage) AS "Percentage Rejection"
FROM
  (WITH aggregated_data AS
     (SELECT el.system_id,
             el.process_id,
             el.process_status,
             COUNT(el.event_log_id) AS count,
             REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1') AS plant_name,
             el.process_date::DATE AS process_date
      FROM lpg_event_log_data el
      WHERE el.system_id IN (1,
                             2)
        AND el.process_id IN (3,
                              23)
      GROUP BY el.system_id,
               el.process_id,
               el.process_status,
               REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1'),
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
GROUP BY plant_name,
         system_id
ORDER BY "Percentage Rejection" DESC
LIMIT 10000;''',

    "bottom_pt_plants": f'''SELECT plant_name AS plant_name,
       system_id AS system_id,
       sum(sortoutpercentage) AS "Percentage Rejection"
FROM
  (WITH aggregated_data AS
     (SELECT el.system_id,
             el.process_id,
             el.process_status,
             COUNT(el.event_log_id) AS count,
             REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1') AS plant_name,
             el.process_date::DATE AS process_date
      FROM lpg_event_log_data el
      WHERE el.system_id IN (1,
                             2)
        AND el.process_id IN (4,
                              24)
      GROUP BY el.system_id,
               el.process_id,
               el.process_status,
               REGEXP_REPLACE(el.topic_name, '^.*_dncceg_([^-\s]+).*$', '\\1'),
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
GROUP BY plant_name,
         system_id
ORDER BY "Percentage Rejection" DESC
LIMIT 10000;''',

    "bottom_productivity_plants": f'''SELECT short_name AS short_name,
       AVG("productivity.normal.productivity") AS "Total Productivity"
FROM public.lpg_consolidated_data
WHERE (short_name NOT IN ('sitarganj',
                          'madurai'))
GROUP BY short_name
ORDER BY COUNT(*) DESC
LIMIT 10000;''',

    "productivity_by_zone": f'''SELECT DATE_TRUNC('day', process_date) AS process_date,
       zone AS zone,
               sum("productivity.normal.productivity") AS "SUM(productivity.normal.productivity)"
FROM public.lpg_consolidated_data
GROUP BY DATE_TRUNC('day', process_date),
         zone
ORDER BY "SUM(productivity.normal.productivity)" DESC
LIMIT 50000;''',

    "productivity_by_location": f'''SELECT DATE_TRUNC('day', process_date) AS process_date,
       short_name AS short_name,
       sum("productivity.normal.productivity") AS "SUM(productivity.normal.productivity)"
FROM public.lpg_consolidated_data
GROUP BY DATE_TRUNC('day', process_date),
         short_name
ORDER BY "SUM(productivity.normal.productivity)" DESC
LIMIT 10000;''',

    "consolidated_table": f'''SELECT DATE_TRUNC('day', process_date) AS process_date,
       short_name AS short_name,
       carousel AS carousel,
       sum("bottling.14_2kg") AS "Bottling Summary(14.2KG)",
       sum("bottling.19kg") AS "Bottling Summary(19KG)",
       sum("bottling.total") AS "Bottling Summary(Total)",
       sum("productivity.normal.production") AS "Productivity Normal Hours(Production)",
       sum("productivity.normal.stoppages") AS "Productivity Normal Hours(Stoppage)",
       sum("productivity.normal.productivity") AS "Productivity Normal Hours(Productivity)",
       sum("productivity.break.production") AS "Productivity Break Hours(Production)",
       sum("productivity.break.net_hours") AS "Productivity Break Hours(Net Hours)",
       sum("productivity.break.productivity") AS "Productivity Break Hours(Productivity)",
       sum("productivity.overtime.production") AS "Productivity Overtime(Production)",
       sum("productivity.overtime.productivity") AS "Productivity Overtime(Net Hours)"
FROM public.lpg_consolidated_data
GROUP BY DATE_TRUNC('day', process_date),
         short_name,
         carousel
ORDER BY "Bottling Summary(14.2KG)" DESC
LIMIT 10000;''',

     "top_productivity_plants": f'''SELECT short_name AS short_name,
       AVG("productivity.normal.productivity") AS "Productivity"
FROM public.lpg_consolidated_data
WHERE short_name IN ('sitarganj',
                     'madurai',
                     'barhi',
                     'mysore',
                     'gummidipoondi')
GROUP BY short_name
ORDER BY COUNT(*) DESC
LIMIT 10000;''',

    "high_alert_locations": f'''SELECT location_name, COUNT(*) AS alert_count
                                FROM public.alerts 
                                WHERE severity = 'High'
                                GROUP BY location_name 
                                ORDER BY alert_count DESC''',

    "critical_alert_locations": f'''SELECT location_name, COUNT(*) AS alert_count
                                FROM public.alerts 
                                WHERE severity = 'Critical'
                                GROUP BY location_name 
                                ORDER BY alert_count DESC''',

    "sod_terminal": f'''SELECT severity, COUNT(*) AS alert_count 
                        FROM public.alerts 
                        GROUP BY severity 
                        ORDER BY alert_count DESC''',

    "alert_categories": f'''SELECT severity, alert_status, COUNT(*) AS alert_count 
                            FROM public.alerts 
                            WHERE alert_status IN ('Open', 'Close')
                            GROUP BY severity, alert_status 
                            ORDER BY alert_count DESC''',

    "tas_alerts": f'''SELECT bu, alert_section, COUNT(*) AS alert_count 
                      FROM public.alerts 
                      WHERE alert_section NOT IN ('VA', 'VTS')
                      GROUP BY bu, alert_section 
                      ORDER BY alert_count DESC''',

    "non_tas_alerts": f'''SELECT alert_section, COUNT(*) AS alert_count 
                          FROM public.alerts 
                          WHERE alert_section NOT IN ('TAS')
                          GROUP BY alert_section 
                          ORDER BY alert_count DESC''',

    "no_of_terminals": f'''SELECT bu, COUNT(*) AS no_of_terminals 
                           FROM public.alerts 
                           GROUP BY bu 
                           ORDER BY no_of_terminals DESC''',

    "alert_ageing": f'''SELECT DISTINCT bu, alert_section,
                        CASE 
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) <= 1 THEN '1 Day'
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 1 AND 2 THEN '1 to 2 Days'
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 2 AND 5 THEN '2 to 5 Days'
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 5 AND 7 THEN '5 to 7 Days'
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 7 AND 10 THEN '7 to 10 Days'
                            ELSE 'Older than 10 Days'
                        END AS alert_ageing,
                        COUNT(*) OVER (
                            PARTITION BY 
                            bu, alert_section,
                            CASE 
                                WHEN DATE_PART('day', CURRENT_DATE - created_at) <= 1 THEN '1 Day'
                                WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 1 AND 2 THEN '1 to 2 Days'
                                WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 2 AND 5 THEN '2 to 5 Days'
                                WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 5 AND 7 THEN '5 to 7 Days'
                                WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 7 AND 10 THEN '7 to 10 Days'
                                ELSE 'Older than 10 Days'
                            END
                        ) AS alert_count,
                        CASE 
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) <= 1 THEN 1
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 1 AND 2 THEN 2
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 2 AND 5 THEN 3
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 5 AND 7 THEN 4
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 7 AND 10 THEN 5
                            ELSE 6
                        END AS alert_ageing_order
                    FROM 
                        alerts
                    ORDER BY bu, alert_section,
                        alert_ageing_order''',

    "alert_distributions": f'''SELECT severity, COUNT(*) AS alert_count 
                               FROM public.alerts 
                               GROUP BY severity 
                               ORDER BY alert_count DESC ;''',
        
    "analytics": f'''SELECT 
                        a.sap_id, a.interlock_name,
                        COUNT(a.severity) as severity_count, 
                        a.alert_status, 
                        a.severity,
                        b.name
                    FROM alerts a 
                    left join location_master b ON a.sap_id = b.sap_id
                    GROUP BY a.sap_id, a.interlock_name, a.severity, a.alert_status, b.name
                    ORDER BY severity_count DESC;
                    ''',

    "no_of_locations": f'''SELECT COUNT(sap_id) FROM location_master''',

    "day_wise_alerts": f'''SELECT 
                            DATE(created_at) AS alert_date,
                            interlock_name,
                            severity,
                            COUNT(*) AS total_alerts
                        FROM alerts
                        GROUP BY DATE(created_at), interlock_name, severity
                        ORDER BY alert_date, severity;
                        ''',
    
    "location_severity_count": f'''SELECT 
                                        b.name AS location_name,
                                        a.severity,
                                        COUNT(a.severity) AS alert_count
                                    FROM 
                                        alerts a
                                    LEFT JOIN 
                                        location_master b 
                                    ON 
                                        a.sap_id = b.sap_id
                                    GROUP BY 
                                        b.name, a.severity
                                    ORDER BY 
                                        b.name, a.severity;''',
    
    "severity_count": f'''SELECT 
                            lm.sap_id,
                            lm.bu,
                            lm.state,
                            lm.region,
                            lm.zone,
                            lm.name,
                            lm.latitude,
                            lm.longitude,
                            jsonb_build_object(
                                'Critical', SUM(CASE WHEN a.severity = 'Critical' THEN 1 ELSE 0 END),
                                'High', SUM(CASE WHEN a.severity = 'High' THEN 1 ELSE 0 END),
                                'Medium', SUM(CASE WHEN a.severity = 'Medium' THEN 1 ELSE 0 END),
                                'Low', SUM(CASE WHEN a.severity = 'Low' THEN 1 ELSE 0 END)
                            ) AS alerts
                        FROM 
                            location_master lm
                        LEFT JOIN 
                            alerts a
                        ON 
                            lm.sap_id = a.sap_id AND lm.bu = a.bu
                        GROUP BY 
                            lm.sap_id, lm.bu, lm.state, lm.region, lm.zone, lm.name, lm.latitude, lm.longitude;''',
    
    "hourly_alerts": f'''SELECT 
                                DATE_TRUNC('hour', created_at) AS alert_hour, interlock_name,
                                COUNT(*) AS alert_count
                            FROM 
                                alerts
                            WHERE 
                                created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                            GROUP BY 
                                DATE_TRUNC('hour', created_at), interlock_name
                            ORDER BY 
                                alert_hour;''',
    
    "sales_performance": f'''SELECT "SBU", "SBU_Name", "ZONE", "Zone_Name", "REGION", "Region_Name", "SA", 
                                    "SalesArea_Name", "PRODUCT", "ProductName", "UOM", "INVOICE_DT", 
                                    "TARGET_QTY_TMT", "FISCAL_YEAR", "NETWEIGHT_TMT", "FinalSum", 
                                    "FinalActualSum", "Rate_Per_Day_Required_MMT", "Rate_per_day_current_MMT", 
                                    "month_year", "month_name", "Prediction_Value", "Zone_Region_Achievement",  
                                    "Product_Achievement"
                            FROM public."M60_LEVEL_METADATA"''',

    "sales_growth": f'''SELECT * FROM public."MOM_LEVEL_FINAL_DATA" where "MOM_LEVEL_FINAL_DATA"."fiscal_year" in ('2023-2024','2024-2025') ''',
        
    "carry_forward_analysis": f'''select 
                                        SUM(total_indents) as "total_indents", 
                                        SUM(indents_executed) as "indents_executed", 
                                        SUM(cf_indents) as "cf_indents", SUM(dry_out_locations) as "dry_out_locations",
                                        SUM(dry_out_cat_a) as "dry_out_cat_a", DATE(execution_date)
                                  from 
                                        "carry_forward_indents"''',

    "carry_fwd_indent": f'''SELECT 
                                    reported_date::DATE AS execution_date,
                                    COUNT(*) AS cf_indents,
                                    COUNT(dry_out_in_days) AS dry_out_locations,
                                    COUNT(category) AS dry_out_cat_a
                                FROM 
                                    public.carry_fwd_indent''',
    
    "location_wise_distribution": f'''SELECT 
                                            bu,
                                            alert_section,
                                            interlock_name,
                                            location_name,
                                            severity,
                                            COUNT(*) AS alert_count
                                        FROM 
                                            alerts
                                        GROUP BY 
                                            bu, alert_section, interlock_name, location_name, severity
                                        ORDER BY 
                                        bu, alert_section, interlock_name, location_name, severity;''',
    
    "lpg_cdcms_booking_vs_sales_vs_pending": f'''select sum("bookings_volume") as "Bookings",
                            sum("sales_volume") as "Sales",
                            sum("pendings_volume") as "Pending",
                            "ZOName",
                            "ROName",
                            "SAName",
                            "DistributorName",
                            "ConsumerType",
                            "CylType"
                    from
                        "lpg_todays_cdcms_sales_summary"''',
    
    "lpg_cdcms_sakhi_registrations": f''' SELECT 
                                            "Month",
                                            "Month_Number",
                                            SUM("SakhiRegisteredCount") AS "SakhiRegistered",
                                            "ZOName", "ROName", "SAName", "DistributorName"
                                        FROM
                                            "lpg_cdcms_sakhi_registrations"
                                    ''',
    
    "lpg_cdcms_monthly_sales": f'''select
                                sum("sales_volume") as "Total Sales",
                                "Month",
                                "Month_Number",
                                "ZOName",
                                "ROName",
                                "SAName",
                                "ConsumerType", 
                                "CylType",
                                "DistributorName"
                            from
                                "lpg_monthly_cdcms_sales_summary"''',
    
    "lpg_cdcms_bookings_order_source_wise": f'''select
                                    "OrderSourceName",
                                    "DistributorName",
	                                "ZOName",
	                                "ROName",
	                                "SAName",
                                    "ConsumerType", 
                                    "CylType",
	                                sum("bookings_volume") as "Total_Bookings"
                                from
	                                "lpg_todays_cdcms_sales_summary"''',
                                 
    "lpg_cdcms_pending_cosumer_type_wise": f'''
                                select 
                                    "ZOName",
                                    "ROName",
                                    "SAName",
                                    "ConsumerType",
                                    "DistributorName",
                                    "CylType",
                                    sum("pendings_volume") as "Total_pending" 
                                from
                                    "lpg_todays_cdcms_sales_summary" ''',
    "lpg_cdcms_ageing" : f'''
                        select 
                            "ZOName",
                            "ROName",
                            "SAName",
                            "DistributorName",
                            "ConsumerType",
                            "CylType",
                            sum("pending_1_3_days") as "pending_1_3_days",
                            sum("pending_4_7_days") as "pending_4_7_days",
                            sum("pending_8_15_days") as "pending_8_15_days",
                            sum("Pending_Beyond15D") as "pending_beyond_15_days"
                        from
                            "lpg_todays_cdcms_sales_summary" ''',
    
    "lpg_cdcms_current_financial_year_sales": f'''select
                                            "DistributorName",
                                            "ConsumerType",
                                            "ZOName",
                                            "ROName",
                                            "SAName",
                                            sum("sales_volume") as "Sales"
                                        from
                                            "lpg_monthly_cdcms_sales_summary"''',
    
    "lpg_cdcms_overall_ctc_statistics": f'''select
                                        "Category",
                                        "JDEDistributorCode",
                                        "ZOName",
                                        "ROName",
                                        "SAName",
                                        sum("ACTCCount") as "ACTC",
                                        sum("BCTCCount") as "BCTC",
                                        sum("NCTCCount") as "NCTC"
                                    from
                                        "LPG_CONSUMERS_SUMMARY"''',

    "lpg_cdcms_safety_check_pending": f'''select
                                            "SubCategory",
                                            "JDEDistributorCode",
                                            "ZOName",
                                            "ROName",
                                            "SAName",
                                            sum("SafetyCheckPending") as "SafetyCheckPending"
                                        from
                                            "LPG_CONSUMERS_SUMMARY"''',

    'lpg_cdcms_actual_vs_historic_sales': f''' select 
                                            "Month",
                                            "Month_Number",
                                            "Financial_Year",
                                            "Quarter",
                                            sum("sales_volume") as "sales_volume",
                                            "ZOName", "ROName", "SAName", "ConsumerType", "CylType", "DistributorName"
                                        from
                                            "lpg_monthly_cdcms_sales_summary" ''',
    
    "lpg_cdcms_total_consumers": f''' select
                                "ZOName",
                                "ROName",
                                "SAName",
                                "JDEDistributorCode",
                                "Category" as "Category",
                                "SubCategory" as "SubCategory",
                                sum("ConsumerCount") as "Total_Consumers"
                            from
                                "LPG_CONSUMERS_SUMMARY" ''',
                                
    "lpg_cdcms_backlogs": f''' SELECT 
                                    "DistributorName",
                                    "ZOName", "ROName", "SAName",
                                    SUM("TotalSalesYesterday"),
                                    SUM("Total_Pending"),
                                FROM
                                    "lpg_cdcms_sales_summary" ''',
    
    "lpg_cdcms_backlogs_today": f''' SELECT
                                        "DistributorName",
                                        "ZOName", "ROName", "SAName",
                                        SUM("TotalSalesYesterday"),
                                        SUM("Total_Pending"),
                                    FROM
                                        "lpg_todays_cdcms_sales_summary" ''',
    
    "sales_growth_ytd": f'''select * from "MOM_DAY_LEVEL_DATA" where "MOM_DAY_LEVEL_DATA"."fiscal_year" in ('2023-2024','2024-2025')''',
    
    "lpg_cdcms_total_suvidha": f'''select 
                            "ZOName",
                            "ROName",
                            "SAName",
                            "JDEDistributorCode",
                            "SubCategory" as "SubCategory",
                            "Category" As "Category",
                            sum("SuvidhaClub") as "SuvidhaClub" 
                        from
                            "LPG_CONSUMERS_SUMMARY" ''',
    "lpg_cdcms_ekyc_statistics": f'''
                        SELECT
                            "ROName",
                            "SAName",
                            "JDEDistributorCode",
                            "ZOName",
                            sum("eKYCCompleted") as "Completed",
                            sum("eKYCPending") as "Pending"     
                        FROM
                            "LPG_CONSUMERS_SUMMARY"
                        ''',
    
    "lpg_operations_productivity_zone": f'''   
                        select 
                            "zone" as "zone",
                            "name" as "name",
                            "carousel" as "carousel",
                            avg("productivity.normal.productivity") as "productivity"
                        from 
                            "LPG_OPERATIONS_SUMMARY_DATA"
                        ''',
    
    "lpg_operations_production_zone": f''' 
                        select 
                            "zone" as "zone",
                            "name" as "name",
                            "carousel" as "carousel",
                            sum("productivity.normal.production")/1000 as "Productions" 
                        from 
                            "LPG_OPERATIONS_SUMMARY_DATA" ''',
    
    "lpg_operations_filled_cylinder": f''' 
                        select 
                            sum("total") as "Handled",
                            sum("cylfilled") as "Cylinder_Filled",
                            "zone" as "zone",
                            "plant" as "plant"
                        from
                            "lpg_cs_rejections" ''',
    
    "cp_total_locations": 'select count(distinct("sap_id")) as "total_plants" from "cp_tank_delivery_updated" ', 

    "cp_total_dus": '''SELECT SUM("du") AS "total_du"
FROM (
    SELECT COUNT(DISTINCT "dispensing_unit") AS "du"
    FROM "cp_transaction_updated"
    GROUP BY "sap_id"
) AS subquery ''',

    "cp_total_tanks": '''SELECT SUM("tanks") AS "total_tanks"
FROM (
    SELECT COUNT(DISTINCT "tank_no") AS "tanks"
    FROM "cp_tank_delivery_updated"
    GROUP BY "sap_id"
) AS subquery ''',

    "cp_avg_monthly_consumption": '''SELECT 
    AVG("sale_volume")/1000 AS "avg_sale_volume",
    TO_CHAR(CAST("start_date" AS TIMESTAMP), 'Mon YYYY') AS "start_month_year",
    "product" AS "product"
FROM
    "cp_tank_delivery_updated"
GROUP BY
    TO_CHAR(CAST("start_date" AS TIMESTAMP), 'Mon YYYY'),
    "product",
    TO_CHAR(CAST("start_date" AS TIMESTAMP), 'MM-YYYY')
ORDER BY
    TO_CHAR(CAST("start_date" AS TIMESTAMP), 'MM-YYYY') ASC''',

    "cp_avg_monthly_consumption_by_location": '''SELECT 
    AVG("sale_volume")/1000 AS "avg_sale_volume",
	"depot" AS "plant",
    TO_CHAR(CAST("start_date" AS TIMESTAMP), 'Mon YYYY') AS "start_month_year",
    "product" AS "product"
FROM
    "cp_tank_delivery_updated"
GROUP BY
    TO_CHAR(CAST("start_date" AS TIMESTAMP), 'Mon YYYY'),
    "product",
	"depot",
    TO_CHAR(CAST("start_date" AS TIMESTAMP), 'MM-YYYY')
ORDER BY
    "depot",TO_CHAR(CAST("start_date" AS TIMESTAMP), 'MM-YYYY') ASC''',

    "cp_total_volume_consumption": '''select sum("sale_volume")/1000 as "total_consumption" 
    from "cp_tank_delivery_updated" ''',

    "cp_total_volume_sales": '''select sum("sale_volume")/1000 as "total_sales" 
    from "cp_transaction_updated"''',

    "lpg_cdcms_exception_stats": f''' select 
                                        "ZOName" ,
                                        "ROName",
                                        "SAName" ,
                                        "JDEDistributorCode",
                                        "ExceptionName" as "ExceptionName" ,
                                        SUM("Consumers") AS "Consumers",
                                        SUM("Refills") AS "Refills"
                                    from
                                        "subsidy_exception_statistics_EC_data" 
                                     ''',

    "lpg_cdcms_subsidy_failure_stats": f'''
                        SELECT 
                            "ZOName" ,
                            "ROName",
                            "SAName",
                            "JDEDistributorCode",
                            "PaymentErrorName" as "PaymentErrorName",
                            sum("Consumers") as "Consumers",
                            sum("Refills") as "Refills"
                        FROM
                            "subsidy_failure_statistics_PEC_data"''',
    
    "cs_query" : f'''
                    select 
                        "zone" as "zone",
                        "plant" as "plant",
                        'CS' AS "rejection_type",
                        avg("sortoutpercentage") * 100 as "Rejections",
                        CAST("process_date" AS DATE) as "process_date"
                    from
                        "lpg_cs_rejections"
                ''',

    "pt_query": f'''
                    select 
                        "zone" as "zone",
                        "plant" as "plant",
                        'PT' AS "rejection_type",
                        avg("sortoutpercentage") * 100 as "Rejections",
                        CAST("process_date" AS DATE) as "process_date"
                    from
                        "lpg_pt_rejections"
                ''',

    "gd_query" : f'''
                    select 
                        "zone" as "zone",
                        "plant" as "plant",
                        'GD' AS "rejection_type",
                        avg("sortoutpercentage") * 100 as "Rejections",
                        CAST("process_date" AS DATE) as "process_date"
                    from
                        "lpg_gd_rejections"
                ''',
                    
    'cdcms_current_year_sales':f''' SELECT 
                                        ROUND(CAST(SUM("sales_volume") / 1000000 AS NUMERIC), 2) AS "total_sales"
                                    FROM 
                                        "lpg_monthly_cdcms_sales_summary"
                                    WHERE 
                                        "Financial_Year"='{financial_year}' AND "ZOName" IS NOT NULL ''',
    
    'cdcms_current_month_sales':f'''select
                                        ROUND(CAST(SUM("sales_volume") / 1000000 AS NUMERIC), 2) AS "total_sales"
                                    from
                                        "lpg_monthly_cdcms_sales_summary"
                                    where
                                        "Financial_Year"='{financial_year}' AND "Month"='{current_month}' AND "ZOName" IS NOT NULL ''',
    
    'cdcms_current_week_sales': f''' SELECT 
                                        ROUND(CAST(SUM("sales_volume") / 1000000 AS NUMERIC), 2) AS "total_sales"
                                    FROM
                                        "lpg_cdcms_sales_summary"
                                    WHERE 
                                        "Execution_Date" >= CURRENT_DATE - EXTRACT(DOW FROM CURRENT_DATE)::INT + 1
                                        AND "Execution_Date" <= CURRENT_DATE AND "ZOName" IS NOT NULL ''',
    
    'cdcms_current_date_sales':f'''select
                                        ROUND(CAST(SUM("sales_volume") / 1000000 AS NUMERIC), 2) AS "total_sales"
                                    from
                                        "lpg_todays_cdcms_sales_summary"
                                    where
                                        "ZOName" IS NOT NULL ''',                                

    'cdcms_current_date_bookings':f'''select
                                        ROUND(CAST(SUM("bookings_volume") / 1000000 AS NUMERIC), 2) AS "Bookings"
                                    from
                                        "lpg_todays_cdcms_sales_summary"
                                    where
                                        "ZOName" IS NOT NULL ''',

    'cdcms_current_date_pending':f'''select
                                        ROUND(CAST(SUM("pendings_volume") / 1000000 AS NUMERIC), 2) AS "Pending"
                                    from
                                        "lpg_todays_cdcms_sales_summary"
                                    where
                                        "ZOName" IS NOT NULL ''',

    'lpg_operations_current_month_productivity': f''' SELECT 
                                                        ROUND(AVG("productivity.normal.productivity")) 
                                                    FROM 
                                                        "LPG_OPERATIONS_SUMMARY_DATA"
                                                    WHERE 
                                                        DATE_TRUNC('month', "process_date") = DATE_TRUNC('month', CURRENT_DATE); ''',

    'lpg_operations_current_month_productions': '''SELECT
                                                        ROUND(AVG("productivity.normal.production"))
                                                    FROM
                                                        "LPG_OPERATIONS_SUMMARY_DATA"
                                                    WHERE
                                                        DATE_TRUNC('month', "process_date") = DATE_TRUNC('month', CURRENT_DATE);''',

    'lpg_operations_current_month_cylinder_filled': ''' SELECT
                                                            ROUND(SUM("cylfilled"::numeric)/100000, 2) AS "Cylinders_Filled"
                                                        FROM
                                                            "lpg_cs_rejections"
                                                        WHERE
                                                            DATE_TRUNC('month', "process_date") = DATE_TRUNC('month', CURRENT_DATE); ''',

    'lpg_operations_current_month_cs_rejection': ''' SELECT
                                                        ROUND(AVG("sortoutpercentage"::numeric), 2) * 100 AS "Cylinders_Filled"
                                                    FROM
                                                        "lpg_cs_rejections"
                                                    WHERE
                                                        DATE_TRUNC('month', "process_date") = DATE_TRUNC('month', CURRENT_DATE); ''',

    'lpg_operations_current_month_gd_rejection': ''' SELECT
                                                        ROUND(AVG("sortoutpercentage"::numeric), 2) * 100 AS "Cylinders_Filled"
                                                    FROM
                                                        "lpg_gd_rejections"
                                                    WHERE
                                                        DATE_TRUNC('month', "process_date") = DATE_TRUNC('month', CURRENT_DATE); ''',

    'lpg_operations_current_month_pt_rejection': ''' SELECT
                                                        ROUND(AVG("sortoutpercentage"::numeric), 2) * 100 AS "Cylinders_Filled"
                                                    FROM
                                                        "lpg_pt_rejections"
                                                    WHERE
                                                        DATE_TRUNC('month', "process_date") = DATE_TRUNC('month', CURRENT_DATE); ''',

    "lpg_cdcms_domestic_sales_table": f''' select 
                                        "ZOName" as "ZOName",
                                        "CylType" as "CylType",
                                        "ConsumerType" as "ConsumerType",
                                        sum("bookings_volume") as "Total_Booking",
                                        sum("sales_volume") as "Total_Sales",
                                        sum("pendings_volume") as "Total_Pending"
                                    from
                                        "lpg_todays_cdcms_sales_summary" 
                                     ''',

    "lpg_cdcms_consumer_statistics_table": f''' select 
                                    "ZoneNames" as "ZoneNames",
                                    "SubCategory" as "SubCategory",
                                    sum("ConsumerCount") as "Total_Consumers",
                                    sum("eKYCCompleted") as "eKYCCompleted",
                                    sum("eKYCPending") as "eKYCPending",
                                    sum("SafetyCheckPending") as "SafetyCheckPending",
                                    sum("SuvidhaClub") as "SuvidhaClub",
                                    "CylinderType" as "CylinderType" 
                                from
                                    "LPG_CONSUMERS_SUMMARY" '''
}
