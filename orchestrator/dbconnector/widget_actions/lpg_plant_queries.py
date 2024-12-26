import utilities.helpers as helpers

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

    "alert_ageing": f'''SELECT DISTINCT
                        CASE 
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) <= 1 THEN 'Last 1 Day'
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 1 AND 2 THEN '1 to 2 Days'
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 2 AND 5 THEN '2 to 5 Days'
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 5 AND 7 THEN '5 to 7 Days'
                            WHEN DATE_PART('day', CURRENT_DATE - created_at) BETWEEN 7 AND 10 THEN '7 to 10 Days'
                            ELSE 'Older than 10 Days'
                        END AS alert_ageing,
                        COUNT(*) OVER (
                            PARTITION BY 
                            CASE 
                                WHEN DATE_PART('day', CURRENT_DATE - created_at) <= 1 THEN 'Last 1 Day'
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
                    ORDER BY 
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
                            severity,
                            COUNT(*) AS total_alerts
                        FROM alerts
                        GROUP BY DATE(created_at), severity
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
                                DATE_TRUNC('hour', created_at) AS alert_hour,
                                COUNT(*) AS alert_count
                            FROM 
                                alerts
                            WHERE 
                                created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                            GROUP BY 
                                DATE_TRUNC('hour', created_at)
                            ORDER BY 
                                alert_hour;''',
}