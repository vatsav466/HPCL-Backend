vts_query = {
    "total_trips": """select count(distinct invoice_number) from vts_alert_history""",

    "unblocked_by_L1": """select count (*) from alerts where alert_section = 'VTS' 
                                                       and alert_status = 'Close' 
                                                       and device_id = 'Instance - 1'""",

    "unblocked_by_L2": """select count (*) from alerts where alert_section = 'VTS' 
                                                       and alert_status = 'Close' 
                                                       and device_id = 'Instance - 2'""",

    "unblocked_by_L3": """select count (*) from alerts where  alert_section = 'VTS' 
                                                       and alert_status = 'Close' 
                                                       and device_id = 'Instance - 3'""",

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

    "blocked_in_ims" : """SELECT count (*) from alerts where alert_status = 'Open' and alert_section = 'VTS'""",

    "total_alerts" : """SELECT count (*) from alerts where alert_section = 'VTS'""",

    "blocked_alerts" : """SELECT count (*) from alerts where alert_status = 'Open' and alert_section = 'VTS'""",

    "auto_unblock" : """SELECT count (*) from alerts where alert_status = 'Close' and alert_section = 'VTS'
                        and mark_as_false = false """,

    "manual_unblock" : """SELECT count (*) from alerts where alert_status = 'Close' and alert_section = 'VTS'
                          and mark_as_false = true """,

   


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

    "route_violation_percentage": """
                SELECT ROUND(
                100.0 * SUM(route_deviation_count) /
                NULLIF(
                    SUM(stoppage_violations_count + route_deviation_count + night_driving_count + device_tamper_count + speed_violation_count),
                    0
                    ), 2
                ) AS "Route violation"
                FROM vts_alert_history
               """,
    
    "speed_violation_percentage": """ 
                SELECT ROUND(
                100.0 * SUM(speed_violation_count) /
                NULLIF(
                    SUM(stoppage_violations_count + route_deviation_count + night_driving_count + device_tamper_count + speed_violation_count),
                    0 
                    ), 2
                ) AS "Over speed"
                FROM vts_alert_history
               """,

    "night_driving_percentage": """
                SELECT ROUND(
                100.0 * SUM(night_driving_count) /
                NULLIF(
                    SUM(stoppage_violations_count + route_deviation_count + night_driving_count + device_tamper_count + speed_violation_count),
                    0
                    ), 2
                ) AS "Night driving"
                FROM vts_alert_history
               """,

    "unauthorized_stoppage_percentage": """
                SELECT ROUND(
                100.0 * SUM(stoppage_violations_count) /
                NULLIF(
                    SUM(stoppage_violations_count + route_deviation_count + night_driving_count + device_tamper_count + speed_violation_count),
                    0
                    ), 2
                ) AS "Unauthorized stoppage"
                FROM vts_alert_history
               """,

    "device_tampering_percentage": """
                SELECT ROUND(
                100.0 * SUM(device_tamper_count) /
                NULLIF(
                    SUM(stoppage_violations_count + route_deviation_count + night_driving_count + device_tamper_count + speed_violation_count),
                    0
                    ), 2
                ) AS "Device tampering"
                FROM vts_alert_history
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
                AND violation_type IN ('route_deviation_count', 'stoppage_violations_count', 'device_tamper_count', 'main_supply_removal_count', 'night_driving_count', 'speed_violation_count', 'continuous_driving_count')
            GROUP BY {group_by_column}
           """,
        

        "violation_analytics" : """
              SELECT DISTINCT vehicle_number, zone, location_name
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
                         vehicle_number
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
                    SUM(CASE WHEN alert_status = 'Close' AND mark_as_false = false THEN 1 ELSE 0 END) AS "Auto Unblock",
                    SUM(CASE WHEN alert_status = 'Close' AND mark_as_false = true THEN 1 ELSE 0 END) AS "Manual Unblock",
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
            SUM(CASE WHEN alert_status = 'Open' 
                    AND violation_type = '{violation_type}' 
                THEN 1 ELSE 0 END) AS "Blocked",

            SUM(CASE WHEN alert_status = 'Close' 
                    AND mark_as_false = false 
                    AND violation_type = '{violation_type}' 
                THEN 1 ELSE 0 END) AS "Auto Unblock",

            SUM(CASE WHEN alert_status = 'Close' 
                    AND mark_as_false = true 
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
                  """
    
    }
 


