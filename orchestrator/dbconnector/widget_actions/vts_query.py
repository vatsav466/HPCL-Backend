vts_query = {
    "total_trips": """select count(distinct invoice_number) from vts_alert_history""",

    "tt_having_device_issue" : """SELECT count(*)
                                            FROM vts_alert_history 
                                            WHERE main_supply_removal_count >= 6 
                                """,

    "unblocked_by_L1": """select count (*) from alerts where alert_section = 'VTS' 
                                                       and alert_status = 'Close' 
                                                       and 'Location In-Charge SOD' = ANY(assigned_user_roles)""",

    "unblocked_by_L2": """select count (*) from alerts where alert_section = 'VTS' 
                                                       and alert_status = 'Close' 
                                                       and  'Zonal Transport Officer SOD' = ANY(assigned_user_roles)""",

    "unblocked_by_L3": """select count (*) from alerts where  alert_section = 'VTS' 
                                                       and alert_status = 'Close' 
                                                       and  'Zonal Head SOD' = ANY(assigned_user_roles)""",

    "unblocked_within_day": """select count (*) from alerts where alert_section = 'VTS' 
                                                            and alert_status = 'Close' 
                                                            and (vehicle_blocked_end_date - vehicle_blocked_start_date) <= interval '1 day'""",
                                                            
    "unblocked_2_to_3_days": """select count (*) from alerts where  alert_section = 'VTS' 
                                                             and alert_status = 'Close' 
                                                             and (vehicle_blocked_end_date - vehicle_blocked_start_date) > interval '1 day' 
                                                             and (vehicle_blocked_end_date - vehicle_blocked_start_date) <= interval '3 days'""",

    "unblocked_greater_3_days": """select count (*) from alerts where alert_section = 'VTS' 
                                                                and alert_status = 'Close' 
                                                                and (vehicle_blocked_end_date - vehicle_blocked_start_date) > interval '3 days'""",
    
    "itdg_actionable" : """SELECT device_id AS instance_level, COUNT(*) AS count FROM alerts
                                                              WHERE  alert_section = 'VTS'
                                                              AND
                                                              device_id IN ('Instance - 1', 'Instance - 2', 'Instance - 3')
	                                                          GROUP BY device_id""",

    "blocked_in_ims" : """SELECT count (*) from alerts where alert_section = 'VTS' and vehicle_unblocked_date is null""",

    "total_alerts" : """SELECT device_id AS instance_level, COUNT(*) AS count FROM alerts
                                                              WHERE  alert_section = 'VTS'
                                                              AND
                                                              device_id IN ('Instance - 1', 'Instance - 2', 'Instance - 3')
	                                                          GROUP BY device_id""",

    "blocked_alerts" : """SELECT device_id AS instance_level, COUNT(*) AS count FROM alerts
                                                              WHERE  alert_section = 'VTS'
                                                              AND vehicle_unblocked_date is null and
                                                              device_id IN ('Instance - 1', 'Instance - 2', 'Instance - 3')
	                                                          GROUP BY device_id""",

    "auto_unblock" : """SELECT device_id AS instance_level, COUNT(*) AS count FROM alerts
                                                              WHERE  alert_section = 'VTS'
                                                              AND alert_status = 'Close' and mark_as_false = false and
                                                              vehicle_unblocked_date is not null 
                                                              and
                                                              device_id IN ('Instance - 1', 'Instance - 2', 'Instance - 3')
	                                                          GROUP BY device_id """,

    "manual_unblock" : """ SELECT device_id AS instance_level, COUNT(*) AS count FROM alerts
                                                              WHERE  alert_section = 'VTS'
                                                              AND alert_status = 'Close' and mark_as_false = true and
                                                              vehicle_unblocked_date is not null and
                                                              device_id IN ('Instance - 1', 'Instance - 2', 'Instance - 3')
	                                                          GROUP BY device_id """,
    
    "safety_compliance" : """
                            SELECT 
                                event_date, 
                                sap_id, 
                                location_type,
                                tt_number, 
                                transporter_name, 
                                invoice_no, 
                                location_name, 
                                zone from 
                            {drill_state}
                          """,


    "vts_panic" : """SELECT count(event_date) as driver_panic from vts_panic""",

    "vts_harsh_braking" : """SELECT count(event_date) as harsh_braking from vts_harsh_braking""",

    "vts_harsh_acceleration" : """SELECT count(event_date) as harsh_acceleration from vts_harsh_acceleration""",

    "vts_device_removed" : """SELECT count(event_date) as device_removed from vts_device_removed""",
   
    "total_violations_product": """
                SELECT 
                (
                COUNT(DISTINCT CASE WHEN stoppage_violations_count != 0 THEN invoice_number END) +
                COUNT(DISTINCT CASE WHEN route_deviation_count != 0 THEN invoice_number END) +
                COUNT(DISTINCT CASE WHEN device_tamper_count != 0 THEN invoice_number END) +
                COUNT(DISTINCT CASE WHEN main_supply_removal_count != 0 THEN invoice_number END)
                ) AS count
                FROM vts_alert_history
           """,

    "total_violations_trip" : """
                SELECT 
                (
                 COUNT(DISTINCT CASE WHEN night_driving_count != 0 THEN invoice_number END) +
                 COUNT(DISTINCT CASE WHEN speed_violation_count != 0 THEN invoice_number END) +
                 COUNT(DISTINCT CASE WHEN continuous_driving_count != 0 THEN invoice_number END) 
                ) AS count
               FROM vts_alert_history
           """,


    "vts_ongoing_trips": """
                         SELECT * from vts_ongoing_trips where violation_type = '{ongoing_trips_type}'
                         """,

    "percentage_of_violations" : """
                                  SELECT
                                        distinct invoice_number, 
                                        route_deviation_count,
                                        stoppage_violations_count,
                                        device_tamper_count,
                                        speed_violation_count,
                                        night_driving_count,
                                        main_supply_removal_count
                                    FROM 
                                        vts_alert_history 
                                    WHERE invoice_number IS NOT NULL        
                                 """,

    "product_safety": """
            SELECT
            location_id,
            COUNT(DISTINCT CASE WHEN stoppage_violations_count != 0 THEN invoice_number END) AS "Stoppage Violation",
            COUNT(DISTINCT CASE WHEN route_deviation_count != 0 THEN invoice_number END) AS "Route Deviation",
            COUNT(DISTINCT CASE WHEN device_tamper_count != 0 THEN invoice_number END) AS "Device Tampering",
            COUNT(DISTINCT CASE WHEN main_supply_removal_count != 0 THEN invoice_number END) AS "Power Disconnection"
            FROM vts_alert_history
            GROUP BY location_id                   
    """,
    "trip_safety": """
            SELECT
            location_id,
            COUNT(DISTINCT CASE WHEN night_driving_count != 0 THEN invoice_number END) AS "Night Driving",
            COUNT(DISTINCT CASE WHEN speed_violation_count != 0 THEN invoice_number END) AS "Speed Violation",
            COUNT(DISTINCT CASE WHEN continuous_driving_count != 0 THEN invoice_number END) AS "Continuous Driving"
            FROM vts_alert_history
            GROUP BY location_id               
    """,

    "total_violations_alerts" : """
        SELECT 
            {group_by_column},
            SUM(CASE WHEN violation_type = 'route_deviation_count' THEN 1 ELSE 0 END) AS "Route Deviation",
            SUM(CASE WHEN violation_type = 'stoppage_violations_count' THEN 1 ELSE 0 END) AS "Stoppage Violation",
            SUM(CASE WHEN violation_type = 'device_tamper_count' THEN 1 ELSE 0 END) AS "Device Tampering",
            SUM(CASE WHEN violation_type = 'main_supply_removal_count' THEN 1 ELSE 0 END) AS "Power Disconnection",
			SUM(CASE WHEN violation_type = 'night_driving_count' THEN 1 ELSE 0 END) AS "Night Driving",
            SUM(CASE WHEN violation_type = 'speed_violation_count' THEN 1 ELSE 0 END) AS "Speed Violation",
            SUM(CASE WHEN violation_type = 'continuous_driving_count' THEN 1 ELSE 0 END) AS "Continuous Driving"
			
        FROM alerts
        WHERE 
            alert_section = 'VTS'
            AND violation_type IN ('route_deviation_count', 'stoppage_violations_count', 'device_tamper_count', 'main_supply_removal_count', 'night_driving_count', 'speed_violation_count', 'continuous_driving_count')
        GROUP BY {group_by_column}
         """,
    "violations_blocked" : """
           SELECT 
            {group_by_column},
            SUM(CASE WHEN violation_type = 'route_deviation_count' THEN 1 ELSE 0 END) AS "Route Deviation",
            SUM(CASE WHEN violation_type = 'stoppage_violations_count' THEN 1 ELSE 0 END) AS "Stoppage Violation",
            SUM(CASE WHEN violation_type = 'device_tamper_count' THEN 1 ELSE 0 END) AS "Device Tampering",
            SUM(CASE WHEN violation_type = 'main_supply_removal_count' THEN 1 ELSE 0 END) AS "Power Disconnection",
			SUM(CASE WHEN violation_type = 'night_driving_count' THEN 1 ELSE 0 END) AS "Night Driving",
            SUM(CASE WHEN violation_type = 'speed_violation_count' THEN 1 ELSE 0 END) AS "Speed Violation",
            SUM(CASE WHEN violation_type = 'continuous_driving_count' THEN 1 ELSE 0 END) AS "Continuous Driving"
			
        FROM alerts
        WHERE 
            alert_section = 'VTS' and  alert_status = 'Open'
            AND violation_type IN ('route_deviation_count', 'stoppage_violations_count', 'device_tamper_count', 'main_supply_removal_count', 'night_driving_count', 'speed_violation_count', 'continuous_driving_count')
        GROUP BY {group_by_column}
          """,

    "violations_auto_unblocked" : """
            SELECT 
            {group_by_column},
            SUM(CASE WHEN violation_type = 'route_deviation_count' THEN 1 ELSE 0 END) AS "Route Deviation",
            SUM(CASE WHEN violation_type = 'stoppage_violations_count' THEN 1 ELSE 0 END) AS "Stoppage Violation",
            SUM(CASE WHEN violation_type = 'device_tamper_count' THEN 1 ELSE 0 END) AS "Device Tampering",
            SUM(CASE WHEN violation_type = 'main_supply_removal_count' THEN 1 ELSE 0 END) AS "Power Disconnection",
			SUM(CASE WHEN violation_type = 'night_driving_count' THEN 1 ELSE 0 END) AS "Night Driving",
            SUM(CASE WHEN violation_type = 'speed_violation_count' THEN 1 ELSE 0 END) AS "Speed Violation",
            SUM(CASE WHEN violation_type = 'continuous_driving_count' THEN 1 ELSE 0 END) AS "Continuous Driving"
			
        FROM alerts
        WHERE 
            alert_section = 'VTS' and alert_status = 'Close' and mark_as_false = false 
            and
            vehicle_unblocked_date is not null
            and 
            AND violation_type IN ('route_deviation_count', 'stoppage_violations_count', 'device_tamper_count', 'main_supply_removal_count', 'night_driving_count', 'speed_violation_count', 'continuous_driving_count')
        GROUP BY {group_by_column}
       """,

       "violations_manual_unblocked" : """
                SELECT
                {group_by_column},
                SUM(CASE WHEN violation_type = 'route_deviation_count' THEN 1 ELSE 0 END) AS "Route Deviation",
                SUM(CASE WHEN violation_type = 'stoppage_violations_count' THEN 1 ELSE 0 END) AS "Stoppage Violation",
                SUM(CASE WHEN violation_type = 'device_tamper_count' THEN 1 ELSE 0 END) AS "Device Tampering",
                SUM(CASE WHEN violation_type = 'main_supply_removal_count' THEN 1 ELSE 0 END) AS "Power Disconnection",
                SUM(CASE WHEN violation_type = 'night_driving_count' THEN 1 ELSE 0 END) AS "Night Driving",
                SUM(CASE WHEN violation_type = 'speed_violation_count' THEN 1 ELSE 0 END) AS "Speed Violation",
                SUM(CASE WHEN violation_type = 'continuous_driving_count' THEN 1 ELSE 0 END) AS "Continuous Driving"
            
            FROM alerts
            WHERE 
                alert_section = 'VTS' and alert_status = 'Close' and mark_as_false = true
                and vehicle_unblocked_date is not null
                AND violation_type IN ('route_deviation_count', 'stoppage_violations_count', 'device_tamper_count', 'main_supply_removal_count', 'night_driving_count', 'speed_violation_count', 'continuous_driving_count')
            GROUP BY {group_by_column}
           """,
        

        "violation_analytics" : """
              SELECT DISTINCT vehicle_number, zone, location_name, violation_type
                FROM alerts
                WHERE alert_section = 'VTS'
                AND violation_type IN (
                        'route_deviation_count', 
                        'stoppage_violations_count', 
                        'device_tamper_count', 
                        'main_supply_removal_count',
                        'night_driving_count',
                        'speed_violation_count',
                        'continuous_driving_count'
                )
          """,

        "vts_history_query" : """   
                    SELECT DISTINCT invoice_number, 
                                    tl_number, 
                                    route_deviation_count, 
                                    stoppage_violations_count, 
                                    device_tamper_count, 
                                    main_supply_removal_count, 
                                    night_driving_count, 
                                    speed_violation_count, 
                                    continuous_driving_count 
                    FROM vts_alert_history
           """,
        
        "violation_trend_alerts" : """
                    SELECT DISTINCT
                        {period_expr} AS period,
                         vehicle_number,
                         violation_type
                    FROM alerts
                    WHERE alert_section = 'VTS'
                    AND violation_type IN (
                        'route_deviation_count', 
                        'stoppage_violations_count', 
                        'device_tamper_count', 
                        'main_supply_removal_count',
                        'night_driving_count',
                        'speed_violation_count',
                        'continuous_driving_count')
                    AND zone != ''
                    ORDER BY period, vehicle_number
             """,
            
    "violation_details" : """
                SELECT
                    {period_expr} AS period,
                    COUNT(*) AS total_alerts,
                    SUM(CASE WHEN alert_status = 'Open' THEN 1 ELSE 0 END) AS "Blocked",
                    SUM(CASE WHEN alert_status = 'Close' AND mark_as_false = false and vehicle_unblocked_date is not null THEN 1 ELSE 0 END) AS "Auto Unblock",
                    SUM(CASE WHEN alert_status = 'Close' AND mark_as_false = true and vehicle_unblocked_date is not null THEN 1 ELSE 0 END) AS "Manual Unblock",
                    SUM(CASE WHEN device_id = 'Instance - 1' THEN 1 ELSE 0 END) AS instance_1,
                    SUM(CASE WHEN device_id = 'Instance - 2' THEN 1 ELSE 0 END) AS instance_2,
                    SUM(CASE WHEN device_id = 'Instance - 3' THEN 1 ELSE 0 END) AS instance_3
                FROM alerts
                WHERE alert_section = 'VTS'
                AND violation_type = '{violation_type}'
                AND device_id IN ('Instance - 1', 'Instance - 2', 'Instance - 3')
            GROUP BY period
            ORDER BY period
          """,

    "alert_summary" : """
            SELECT
            {group_by_column},
            device_id as instance_level,
            SUM(CASE WHEN vehicle_unblocked_date is null
                    AND violation_type = '{violation_type}' 
                THEN 1 ELSE 0 END) AS "Blocked",

            SUM(CASE WHEN alert_status = 'Close' 
                    AND mark_as_false = false 
                    AND vehicle_unblocked_date is not null
                    AND violation_type = '{violation_type}' 
                THEN 1 ELSE 0 END) AS "Auto Unblock",

            SUM(CASE WHEN alert_status = 'Close' 
                    AND mark_as_false = true 
                    and vehicle_unblocked_date is not null
                    AND violation_type = '{violation_type}' 
                THEN 1 ELSE 0 END) AS "Manual Unblock",

            SUM(CASE WHEN violation_type = '{violation_type}' THEN 1 ELSE 0 END) AS "Total"

        FROM alerts
        WHERE 
            alert_section = 'VTS'
            AND violation_type = '{violation_type}'
            AND device_id IN ('Instance - 1', 'Instance - 2', 'Instance - 3')
        GROUP BY {group_by_column}, device_id
        ORDER BY {group_by_column}, device_id;
             """ ,
    
    "shortage_tibco" : """
                          SELECT PLANT_CD, ZONE_CD, INVOICE_NO, VEHICLE_ID,QTY_SHORTAGE
                          FROM SALES_BASED_TRIPS_TILL_DATE
                        """,
    
    "violation_drill_down" : """
                            SELECT 
                                tl_number,
                                invoice_number,
                                DATE(vts_end_datetime) as created_at,
                                route_deviation_count,
                                stoppage_violations_count,
                                device_tamper_count,
                                main_supply_removal_count,
                                night_driving_count,
                                speed_violation_count,
                                continuous_driving_count
                            FROM vts_alert_history
                            """ ,
    "shoratage_vts_history" : """
                              SELECT 
                                    invoice_number,
                                    route_deviation_count,
                                    stoppage_violations_count,
                                    device_tamper_count,
                                    main_supply_removal_count,
                                    night_driving_count,
                                    speed_violation_count,
                                    continuous_driving_count
                              FROM vts_alert_history  
                              """,
    
    "vts_insite" : """        
                SELECT
                    sap_id,
                    location_name,
                    vehicle_number,
                    transporter_code,
                    zone,
                    SUM(CASE WHEN violation_type = 'route_deviation_count' THEN 1 ELSE 0 END) AS route_deviation_count,
                    SUM(CASE WHEN violation_type = 'stoppage_violations_count' THEN 1 ELSE 0 END) AS stoppage_violations_count,
                    SUM(CASE WHEN violation_type = 'device_tamper_count' THEN 1 ELSE 0 END) AS device_tamper_count,
                    SUM(CASE WHEN violation_type = 'main_supply_removal_count' THEN 1 ELSE 0 END) AS main_supply_removal_count,
                    SUM(CASE WHEN violation_type = 'night_driving_count' THEN 1 ELSE 0 END) AS night_driving_count,
                    SUM(CASE WHEN violation_type = 'speed_violation_count' THEN 1 ELSE 0 END) AS speed_violation_count,
                    SUM(CASE WHEN violation_type = 'continuous_driving_count' THEN 1 ELSE 0 END) AS continuous_driving_count
                FROM alerts 
                WHERE transporter_code != '' and location_name != '' and alert_section = 'VTS'
                GROUP BY sap_id, location_name, vehicle_number, transporter_code,zone
                  """,

    "vts_insite_violation_type" : """
                                     SELECT 
                                        sap_id,
                                        location_name,
                                        vehicle_number,
                                        invoice_number,
                                        transporter_code,
                                        zone,
                                        {select_clause}
                                    FROM alerts 
                                    WHERE transporter_code != '' 
                                    AND location_name != '' 
                                    AND alert_section = 'VTS'
                                    GROUP BY sap_id, location_name, vehicle_number, transporter_code, zone, invoice_number
                                    HAVING {having_clause}
                                  """,
    
    "vts_insite_history": """
                            SELECT
                                tl_number,
                                invoice_number,
                                DATE(vts_end_datetime) AS created_at,
                                COUNT(DISTINCT CASE WHEN stoppage_violations_count != 0 THEN invoice_number END) AS stoppage_violations_count,
                                COUNT(DISTINCT CASE WHEN route_deviation_count != 0 THEN invoice_number END) AS route_deviation_count,
                                COUNT(DISTINCT CASE WHEN device_tamper_count != 0 THEN invoice_number END) AS device_tamper_count,
                                COUNT(DISTINCT CASE WHEN main_supply_removal_count != 0 THEN invoice_number END) AS main_supply_removal_count,
                                COUNT(DISTINCT CASE WHEN night_driving_count != 0 THEN invoice_number END) AS night_driving_count,
                                COUNT(DISTINCT CASE WHEN speed_violation_count != 0 THEN invoice_number END) AS speed_violation_count,
                                COUNT(DISTINCT CASE WHEN continuous_driving_count != 0 THEN invoice_number END) AS continuous_driving_count
                            FROM (
                                SELECT DISTINCT tl_number, invoice_number, vts_end_datetime,
                                    stoppage_violations_count, route_deviation_count, device_tamper_count,
                                    main_supply_removal_count, night_driving_count, speed_violation_count, continuous_driving_count
                                FROM vts_alert_history
                                WHERE invoice_number IS NOT NULL
                            ) AS history_data
                            GROUP BY tl_number, invoice_number, DATE(vts_end_datetime)
                          """,
    "vts_insite_history_type": """
                               SELECT 
                                tl_number,
                                invoice_number,
                                {select_clause}
                            FROM (
                                SELECT DISTINCT tl_number, invoice_number,
                                       stoppage_violations_count, route_deviation_count, device_tamper_count,
                                       main_supply_removal_count, night_driving_count, speed_violation_count, continuous_driving_count
                                FROM vts_alert_history
                                WHERE invoice_number IS NOT NULL
                            ) AS history_data
                            GROUP BY tl_number, invoice_number
                            HAVING {having_clause}
                               """,
    "closed_alerts": """ SELECT 
                            sap_id, location_name, zone, vehicle_number as tt_number, transporter_code, 
                            violation_type, zone, vehicle_blocked_start_date, 
                            vehicle_blocked_end_date, vehicle_unblocked_date
                        FROM 
                            alerts 
                        WHERE 
                            alert_status='Close' AND alert_section='VTS' AND bu='TAS' """,
    
    "unblocked_tt_shortage": """
                            SELECT 
                                SUM(CAST(qty_shortage AS FLOAT)) AS shortage, vehicle_id as vehicle_number
                            FROM 
                                sales_trips_till_date
                            WHERE 
                                qty_shortage != 'NaN' AND qty_shortage != '0.0'
                            """,
    
    "get_emlock_open_data": """
                            SELECT
                                sap_id, location_name, zone, region, trucknumber,
                                invoicenumber as invoice_number, swipeoutl1, swipeoutl2
                            FROM
                                vts_tripauditmaster
                            WHERE
                                invoicenumber != 'null' and invoicenumber != ''
                            """,
    "emlock_open": """ 
                    SELECT 
                        (COUNT(*) FILTER (WHERE swipeoutl1 != 'true') +
                        COUNT(*) FILTER (WHERE swipeoutl2 != 'true')) as emlock_open
                    FROM vts_tripauditmaster;
                    """,                    
    "all_violations" : [   
                            "route_deviation_count",
                            "stoppage_violations_count",
                            "device_tamper_count",
                            "main_supply_removal_count",
                            "night_driving_count",
                            "speed_violation_count",
                            "continuous_driving_count"
                      ],

     "power_disconnection": """
                            SELECT * 
                            FROM vts_alert_history 
                            WHERE main_supply_removal_count >= 6  
                           """,

    "email_master_details": """
                            SELECT sap_id, zone, transporter_name, transporter_code, location_name
                            FROM email_master
                            """
                              
    }


