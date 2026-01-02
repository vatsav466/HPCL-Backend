vts_query = {
    "total_trips": """select count(distinct invoice_number) from vts_alert_history""",

    "tt_having_device_issue" : """SELECT count(*)
                                            FROM vts_alert_history 
                                            WHERE main_supply_removal_count >= 6 
                                """,

    "unblocked_by_L1": """SELECT COUNT(*) AS location_incharge_sod_count
                            FROM alerts a
                            WHERE a.alert_section = 'VTS'
                            AND a.vehicle_unblocked_date IS NOT NULL
                            AND a.mark_as_false = 'TRUE'
                            AND a.sap_id NOT IN ('1652','1672','1693','1462','1649','1689','1676','1700','1691')
                            AND (
                                    /* CONDITION A: Approved but NOT "Approved unblock request by..." */
                                    EXISTS (
                                        SELECT 1
                                        FROM jsonb_array_elements(a.alert_history) AS elem(obj)
                                        WHERE obj->>'action_type' = 'Approved'
                                        AND obj->>'action_msg' NOT LIKE 'Approved unblock request by%'
                                    )

                                    AND

                                    /* CONDITION B: Active with specific recipients */
                                    EXISTS (
                                        SELECT 1
                                        FROM jsonb_array_elements(a.alert_history) AS elem(obj)
                                        WHERE obj->>'action_type' = 'Active'
                                        AND (
                                                obj->>'action_msg' ILIKE '%Safety Officer SOD%'
                                            OR obj->>'action_msg' ILIKE '%Maintenance Officer SOD%'
                                            OR obj->>'action_msg' ILIKE '%Planning Officer SOD%'
                                            )
                                    )
                                )""",

    "unblocked_by_L2": """SELECT COUNT(*) AS zonal_transport_officer_sod_count
                            FROM alerts a
                            WHERE a.alert_section = 'VTS'
                            AND a.vehicle_unblocked_date IS NOT NULL
                            AND a.mark_as_false = 'TRUE'
                            AND (
                                    /* CONDITION A: Approved but NOT "Approved unblock request by..." */
                                    EXISTS (
                                        SELECT 1
                                        FROM jsonb_array_elements(a.alert_history) AS elem(obj)
                                        WHERE obj->>'action_type' = 'Approved'
                                        AND obj->>'action_msg' NOT LIKE 'Approved unblock request by%'
                                    )

                                    AND

                                    /* CONDITION B1: Active + Safety/Maintenance/Planning (SAP IDs in list) */
                                    (
                                        a.sap_id IN ('1652','1672','1693','1462','1649','1689','1676','1700','1691')
                                        AND EXISTS (
                                            SELECT 1
                                            FROM jsonb_array_elements(a.alert_history) AS elem(obj)
                                            WHERE obj->>'action_type' = 'Active'
                                            AND (
                                                    obj->>'action_msg' ILIKE '%Safety Officer SOD%'
                                                OR obj->>'action_msg' ILIKE '%Maintenance Officer SOD%'
                                                OR obj->>'action_msg' ILIKE '%Planning Officer SOD%'
                                            )
                                        )
                                    )

                                    OR

                                    /* CONDITION B2: Active + Location Incharge (other SAP IDs) */
                                    (
                                        a.sap_id NOT IN ('1652','1672','1693','1462','1649','1689','1676','1700','1691')
                                        AND EXISTS (
                                            SELECT 1
                                            FROM jsonb_array_elements(a.alert_history) AS elem(obj)
                                            WHERE obj->>'action_type' = 'Active'
                                            AND obj->>'action_msg' ILIKE '%Location Incharge SOD%'
                                        )
                                    )
                                )""",

    "unblocked_by_L3": """SELECT COUNT(*) AS zonal_head_sod_count
                            FROM alerts a
                            WHERE a.alert_section = 'VTS'
                            AND a.vehicle_unblocked_date IS NOT NULL
                            AND a.mark_as_false = 'TRUE'
                            AND (
                                    /* CONDITION A: Approved but NOT "Approved unblock request by..." */
                                    EXISTS (
                                        SELECT 1
                                        FROM jsonb_array_elements(a.alert_history) AS elem(obj)
                                        WHERE obj->>'action_type' = 'Approved'
                                        AND obj->>'action_msg' NOT LIKE 'Approved unblock request by%'
                                    )

                                    AND

                                    /* CONDITION B: Active mail sent to Zonal Transport Officer SOD */
                                    EXISTS (
                                        SELECT 1
                                        FROM jsonb_array_elements(a.alert_history) AS elem(obj)
                                        WHERE obj->>'action_type' = 'Active'
                                        AND obj->>'action_msg' ILIKE '%Zonal Transport Officer SOD%'
                                    )
                                )""",
    "unblocked_by_L4":"""SELECT COUNT(*) AS alert_manager_count
                            FROM alerts
                            WHERE alert_section = 'VTS'
                            AND vehicle_unblocked_date IS NOT NULL
                            AND mark_as_false = TRUE
                            AND assigned_user_roles IS NOT NULL
                            AND array_length(assigned_user_roles, 1) > 0""",

    "unblocked_within_day": """select count (*) from alerts where alert_section = 'VTS' 
                                                            and alert_status = 'Close' 
                                                            and (vehicle_unblocked_date - created_at) <= interval '1 day'""",
                                                            
    "unblocked_2_to_3_days": """select count (*) from alerts where  alert_section = 'VTS' 
                                                             and alert_status = 'Close' 
                                                             and (vehicle_unblocked_date - created_at) > interval '1 day' 
                                                             and (vehicle_unblocked_date - created_at) <= interval '3 days'""",

    "unblocked_greater_3_days": """select count (*) from alerts where alert_section = 'VTS' 
                                                                and alert_status = 'Close' 
                                                                and (vehicle_unblocked_date - created_at) > interval '3 days'""",
    
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
    
    "vts_panic" : """SELECT count(distinct invoice_no) as driver_panic from vts_panic""",

    "vts_harsh_braking" : """SELECT count(distinct invoice_no) as harsh_braking from vts_harsh_braking""",

    "vts_harsh_acceleration" : """SELECT count(distinct invoice_no) as harsh_acceleration from vts_harsh_acceleration""",

    "vts_device_removed" : """SELECT count(distinct invoice_no) as device_removed from vts_device_removed""",
    
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
                                        main_supply_removal_count,
                                        continuous_driving_count
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
              SELECT  vehicle_number, zone, location_name, violation_type, device_id
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
                AND device_id IN ('Instance - 1', 'Instance - 2', 'Instance - 3')
                AND zone != ''
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
                    SELECT 
                        {period_expr} AS period,
                         vehicle_number,
                         violation_type,
                         device_id
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
                    AND device_id IN ('Instance - 1', 'Instance - 2', 'Instance - 3')
                    ORDER BY period, vehicle_number
             """,
            
    "violation_details" : """
                SELECT
                    {period_expr} AS period,
                    COUNT(*) AS total_alerts,
                    SUM(CASE WHEN vehicle_unblocked_date is null THEN 1 ELSE 0 END) AS "Blocked",
                    SUM(CASE WHEN alert_status = 'Close' AND mark_as_false = false and vehicle_unblocked_date is not null THEN 1 ELSE 0 END) AS "Auto Unblock",
                    SUM(CASE WHEN alert_status = 'Close' AND mark_as_false = true and vehicle_unblocked_date is not null THEN 1 ELSE 0 END) AS "Manual Unblock",
                    SUM(CASE WHEN device_id = 'Instance - 1' THEN 1 ELSE 0 END) AS instance_1,
                    SUM(CASE WHEN device_id = 'Instance - 2' THEN 1 ELSE 0 END) AS instance_2,
                    SUM(CASE WHEN device_id = 'Instance - 3' THEN 1 ELSE 0 END) AS instance_3
                FROM alerts
                WHERE alert_section = 'VTS'
                AND violation_type = '{violation_type}'
                AND device_id IN ('Instance - 1', 'Instance - 2', 'Instance - 3')
                AND zone != ''
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
            AND zone != ''
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
                                location_name,
                                zone,
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
                    zone,
                    SUM(CASE WHEN violation_type = 'route_deviation_count' THEN 1 ELSE 0 END) AS route_deviation_count,
                    SUM(CASE WHEN violation_type = 'stoppage_violations_count' THEN 1 ELSE 0 END) AS stoppage_violations_count,
                    SUM(CASE WHEN violation_type = 'device_tamper_count' THEN 1 ELSE 0 END) AS device_tamper_count,
                    SUM(CASE WHEN violation_type = 'main_supply_removal_count' THEN 1 ELSE 0 END) AS main_supply_removal_count,
                    SUM(CASE WHEN violation_type = 'night_driving_count' THEN 1 ELSE 0 END) AS night_driving_count,
                    SUM(CASE WHEN violation_type = 'speed_violation_count' THEN 1 ELSE 0 END) AS speed_violation_count,
                    SUM(CASE WHEN violation_type = 'continuous_driving_count' THEN 1 ELSE 0 END) AS continuous_driving_count
                FROM alerts  
                WHERE alert_section = 'VTS'
                GROUP BY sap_id, location_name, vehicle_number, zone
                  """,

    "vts_insite_violation_type" : """
                                     SELECT 
                                        sap_id,
                                        location_name,
                                        vehicle_number,
                                        zone,
                                        {select_clause}
                                    FROM alerts 
                                    WHERE alert_section = 'VTS'
                                    GROUP BY sap_id, location_name, vehicle_number, zone
                                    HAVING {having_clause}
                                  """,
    
    "vts_insite_history": """
                           SELECT
                               tl_number,
                               invoice_number,
                               location_name,
                               zone,
                               destination_code,
                               TO_CHAR(date_trunc('day', scheduled_trip_start_datetime), 'YYYYMMDD') AS created_at,
                               MAX(stoppage_violations_count) AS stoppage_violations_count,
                               MAX(route_deviation_count) AS route_deviation_count,
                               MAX(device_tamper_count) AS device_tamper_count,
                               MAX(main_supply_removal_count) AS main_supply_removal_count,
                               MAX(night_driving_count) AS night_driving_count,
                               MAX(speed_violation_count) AS speed_violation_count,
                               MAX(continuous_driving_count) AS continuous_driving_count
                           FROM
                               vts_alert_history
                           WHERE
                               invoice_number IS NOT NULL
                           GROUP BY
                               tl_number,
                               invoice_number,
                               location_name,
                               destination_code,
                               zone,
                               date_trunc('day', scheduled_trip_start_datetime);
                          """,

    "vts_insite_history_type": """
                                    SELECT 
                                    tl_number,
                                    location_name,
                                    zone,
                                    invoice_number,
                                    DATE(scheduled_trip_start_datetime) AS created_at,
                                    {select_clause}
                                FROM (
                                    SELECT DISTINCT invoice_number, tl_number, scheduled_trip_start_datetime, location_name, zone,stoppage_violations_count, 
                                    route_deviation_count, device_tamper_count, main_supply_removal_count, night_driving_count, 
                                    speed_violation_count, continuous_driving_count
                                    FROM vts_alert_history
                                    WHERE invoice_number IS NOT NULL
                                ) AS history_data
                                GROUP BY invoice_number, tl_number,DATE(scheduled_trip_start_datetime), zone, location_name
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
                                SUM(CAST(qty_shortage AS FLOAT)) AS shortage, vehicle_id as tt_number
                            FROM 
                                sales_trips_till_date
                            WHERE 
                                load_status = '6'
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
                    FROM vts_tripauditmaster
                    WHERE 1=1
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
                            """,
    "alert_details":"""
                    SELECT bu,zone,location_name,sap_id,alert_status,transporter_code,vehicle_number,unique_id,vehicle_blocked_start_date,vehicle_blocked_end_date 
                    FROM alerts 
                    """,
    
    "accept_and_block":"""
                SELECT
                    a.id AS alert_id, a.vehicle_number,
                    n.alert_id, n.notices
                FROM alerts a, notices_vts n
                WHERE a.alert_section = 'VTS' AND a.alert_status = 'Close'
                AND a.vehicle_unblocked_date IS NULL AND CAST(n.alert_id AS BIGINT) = a.id
                {final_condition}  """    

                              
    }
    

