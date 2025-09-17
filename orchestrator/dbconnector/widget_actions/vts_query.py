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
	                                                          GROUP BY device_id""",
    "blocked_in_ims" : """SELECT count (*) from alerts where alert_status = 'Open' and alert_section = 'VTS'""",

    "total_violations": """
                SELECT COUNT(*) 
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

    "product_safety": """
       SELECT 
            {group_by_column},
            SUM(CASE WHEN violation_type = 'route_deviation_count' THEN 1 ELSE 0 END) AS "Route Deviation",
            SUM(CASE WHEN violation_type = 'stoppage_violations_count' THEN 1 ELSE 0 END) AS "Stoppage Violation",
            SUM(CASE WHEN violation_type = 'device_tamper_count' THEN 1 ELSE 0 END) AS "Device Tampering",
            SUM(CASE WHEN violation_type = 'main_supply_removal_count' THEN 1 ELSE 0 END) AS "Power Disconnection"
        FROM alerts
        WHERE 
            alert_section = 'VTS'
            AND violation_type IN ('route_deviation_count', 'stoppage_violations_count', 'device_tamper_count', 'main_supply_removal_count')
        GROUP BY {group_by_column};
                      
    """,
    "trip_safety": """
       SELECT 
            {group_by_column},
            SUM(CASE WHEN violation_type = 'night_driving_count' THEN 1 ELSE 0 END) AS "Night Driving",
            SUM(CASE WHEN violation_type = 'speed_violation_count' THEN 1 ELSE 0 END) AS "Speed Violation",
            SUM(CASE WHEN violation_type = 'continuous_driving_count' THEN 1 ELSE 0 END) AS "Continuous Driving"
        FROM alerts
        WHERE 
            alert_section = 'VTS'
            AND violation_type IN ('night_driving_count', 'speed_violation_count', 'continuous_driving_count')
        GROUP BY {group_by_column};                    
    """,

}
 


