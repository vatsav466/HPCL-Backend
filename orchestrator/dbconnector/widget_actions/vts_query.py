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
    "location_level_voilation_breakup": """
                      WITH interlock_pre AS (
                            SELECT
                                {group_by_column} AS group_key,
                                CASE
                                    WHEN interlock_name ILIKE '%RouteDeviation%' THEN 'Route Deviation'
                                    WHEN interlock_name ILIKE '%Stoppage%' THEN 'Speed Violation'
                                    WHEN interlock_name ILIKE '%Device Tampering%' THEN 'Device Tampering'
                                    ELSE 'Other'
                                END AS violation_type
                            FROM alerts
                            WHERE alert_section = 'VTS'
                            AND interlock_name ILIKE ANY (
                                ARRAY['%RouteDeviation%', '%Stoppage%', '%Device Tampering%']
                            )
                            {additional_where}
                            AND {group_by_column} IS NOT NULL
                            AND {group_by_column} != ''
                        )
                        SELECT
                            group_key,
                            violation_type,
                            COUNT(*) AS count
                        FROM interlock_pre
                        GROUP BY group_key, violation_type
                        ORDER BY group_key, violation_type;
    """

}
 
