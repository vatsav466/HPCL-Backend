import urdhva_base

connection_mapping = urdhva_base.settings.db_connection_config
# connection_mapping = {
#     "ims": "3",
#     "hpcl_ceg": "1",
#     "cris": "2"
# }

schema_mapping = {
    "cris": "HPCL_HOS",
    "ims": "IMS_SAP",
    "hpcl_ceg": "HPCL_HOS"
}

table_mapping = {
    "dry_out": "sch_inventory_forecast_dashboard",
    "indent_req": "INDENT_REQUEST",
    "indent_prod": "INDENT_PRODUCTS",
    "indent_pattern": "INDENT_PATTERN",
    "truck_swipe": "TRUCK_SWIPE_ENTRY_SAP",
}

camunda_listener_mapping = urdhva_base.settings.camunda_url_config

# camunda_listener_mapping = {
#     "camunda_dryout_01": {"host": "10.90.38.167", "port": 9080},
#     "camunda_dryout_02": {"host": "10.90.38.167", "port": 9081},
#     "camunda_dryout_03": {"host": "10.90.38.167", "port": 9082},
#     "camunda_dryout_04": {"host": "10.90.38.167", "port": 9083},
#     "camunda_dryout_05": {"host": "10.90.38.167", "port": 9084},
#     "camunda_dryout_06": {"host": "10.90.38.167", "port": 9085},
#     "camunda_dryout_07": {"host": "10.90.38.167", "port": 9086},
#     "camunda_dryout_08": {"host": "10.90.38.167", "port": 9087},
#     "camunda_dryout_09": {"host": "10.90.38.167", "port": 9088},
#     "camunda_dryout_10": {"host": "10.90.38.167", "port": 9089}
# }

dry_out_top_x_axis = [{"name": "Indent Not Raised", "group": "not_raised"},
                  {"name": "Indent On Hold", "group": "pending"}, {"name": "Pending Indents", "group": "pending"},
                  {"name": "Truck Allocated", "group": "wip"},
                  {"name": "Sent to SAP", "group": "wip"}, {"name": "Sales Order Placed", "group": "wip"},
                  {"name": "R2 Swiped", "group": "wip"}, {"name": "Invoice Created", "group": "wip"},
                  {"name": "R3 Swiped", "group": "wip"}, {"name": "VTS", "group": "wip"},
                  {"name": "Indent Delivered", "group": "delivered"}]

truck_details = ["Dealer TT", "TT Available", "Empty Dealer TT Return", "Empty Transporter Return"]

dryout_aging = ["DryOut < 2 Days", "DryOut < 7 Days", "DryOut < 15 Days", "DryOut < 30 Days"]

dry_out_bottom_x_axis = [
        "Dealer", "SO\nRM", "SO\nCO", "SO", "SO\nRM", "SO\nRM", "PO\nRM", "PO\nRM", "PO\nRM", "PO\nRM", "SO\nRM"
    ]

creds_type = urdhva_base.settings.db_connection_mapping

# creds_type = {
#     "2": {"cred_model": "Databases", 'cred_type': "PostgreSQL"},
#     "3": {"cred_model": "Databases", 'cred_type': "Oracle"},
#     "1": {"cred_model": "Databases", 'cred_type': "PostgreSQL"}
# }

product_code_mapping = {
    "MS": "2811000",
    "HSD": "2812000",
    "TURBO": "3912000",
    "E20": "2822000",
    "POWER 95": "3672000",
    "POWER 99": "2816000",
    "POWER 100": "3373000"
}

item_name_mapping = {
    "2811000": "MS",
    "2812000": "HSD",
    "3912000": "TURBO",
    "2822000": "E20",
    "3672000": "POWER 95",
    "2816000": "POWER 99",
    "3373000": "POWER 100"
}

alert_action_category = {
    "VA": {
        "Safety": "Safety",
        "Security": "Security",
        "Operations": "Operations",
        "FalseAlert": "FalseAlert",
        "InvalidAlert": "InvalidAlert",
        "Other": "Other"
    },
    "VTS": {
        "Safety": "Safety",
        "Pilferage": "Pilferage",
        "Operations": "Operations"
    }
}

alert_action_rca_reason = {
    "VTS": [
        "Health Issue",
        "Person Issue",
        "Equipment issue",
        "Location/Outlet Near by",
        "Other"
    ],
    "VA": [
        "Person issue",
        "Equipment issue",
        "Lack of Awareness",
        "InvalidAlert",
        "FalseAlert",
        "Other"
    ]
}

rca_reason = {
    "FIRE/SMOKE": [
        "Short circuit or electrical fault.",
        "Equipment overheating.",
        "Unauthorized fire-related activities.",
        "Negligence during operations.",
        "Others"
    ],
    "ABSENCE OF EARTHING": [
        "Equipment not properly grounded.",
        "Earthing mechanism damaged or removed.",
        "Neglect in routine earthing checks.",
        "Others"
    ],
    "ABSENCE OF WHEELCHOCK": [
        "Misplaced after previous use.",
        "Insufficient wheel chocks allocated.",
        "Lack of awareness or training.",
        "Others"
    ],
    "ALIGHT FROM TWO WHEELER": [
        "Unsafe behavior or oversight by personnel.",
        "Lack of adherence to safety guidelines.",
        "Lack of proper monitoring.",
        "Others"
    ],
    "UNAUTHORIZED FILLING OF CONTAINER": [
        "Negligence or lack of training.",
        "Absence of supervision in sensitive areas.",
        "Deliberate violation of procedures.",
        "Others"
    ],
    "ABSENCE OF FIRE EXTINGUISHER DECANTATION": [
        "Fire extinguisher removed for emergency use.",
        "Neglect in replacing after usage.",
        "Lack of periodic safety checks.",
        "Others"
    ],
    "Person not wearing Safety Helmet": [
        "Person not wearing helmets due to oversight.",
        "Helmets damaged or unavailable.",
        "Lack of training on PPE compliance.",
        "Others"
    ],
    "LINE OF FIRE": [
        "Personnel entering restricted or unsafe zones.",
        "Lack of awareness about safety protocols.",
        "Poor supervision or monitoring.",
        "Others"
    ],
    "ABSENCE OF SAFETY HARNESS": [
        "Safety harness not available at the site.",
        "Personnel neglecting safety protocols.",
        "Damaged or unusable harness not replaced.",
        "Others"
    ],
    "Fire-Extinguisher": [
        "Routine maintenance or refill pending.",
        "Misplacement during an emergency.",
        "Delay in procurement of replacements.",
        "Others"
    ],
    "Wheel-Chock": [
        "Chock not placed due to negligence.",
        "Damaged chock not replaced.",
        "Lack of proper storage or tracking.",
        "Others"
    ],
    "Intrusion-PersonAtPerimeter": [
        "Unauthorized entry due to lack of monitoring.",
        "Security personnel not alert.",
        "Malfunctioning perimeter systems.",
        "Others"
    ],
    "LPGLeak-FillingGun": [
        "Damaged or malfunctioning filling gun.",
        "Improper handling during operations.",
        "Lack of routine equipment checks.",
        "Others"
    ],
    "LPGLeak-Detection": [
        "Faulty or uncalibrated detection systems.",
        "Lack of routine maintenance.",
        "Leakage caused by improper operations.",
        "Others"
    ],
    "PPE-Compliance": [
        "Personnel unaware of PPE guidelines.",
        "Unavailability or damage to PPE equipment.",
        "Neglect in wearing mandatory PPE.",
        "Others"
    ],
    "MAINTENANCE": [
        "Insufficient spare parts inventory.",
        "Others"
    ],
    "HIGH-LEVEL ALARM": [
        "Exceeded operational limits",
        "Faulty level sensors.",
        "Incorrect calibration of setpoints.",
        "Blocked or restricted process flow.",
        "Others"
    ],
    "HCD ALARM": [
        "Misconfigured alarm thresholds.",
        "Process fluctuations beyond normal range.",
        "Sensor drift or errors.",
        "Others"
    ],
    "HCD FAULT": [
        "Loose wiring or connection fault.",
        "Power supply interruption.",
        "System software or firmware issues.",
        "Others"
    ]
}

dry_out_query = f"""SELECT
                        "title",
                        "value" AS "Site_Count",
                        "prodvalue",
                        "tankvalue",
                        SUM("value") OVER (PARTITION BY 1) AS "totalvalue"
                    FROM (
                        SELECT
                            CASE
                                WHEN status = 1 THEN 'DRY OUT'
                                WHEN status = 2 THEN 'INTRADAY DRY OUT'
                                WHEN status = 3 THEN '1-3 Days'
                                WHEN status = 4 THEN '4-6 Days'
                            END AS "title",
                            status AS seqno,
                            COUNT(DISTINCT site_id || fcc_code) AS "value",
                            COUNT(DISTINCT site_id || fcc_code || item_name) AS "prodvalue",
                            SUM(tank_cnt) AS "tankvalue"
                        FROM (
                            SELECT
                                site_id,
                                fcc_code,
                                product_grp AS item_name,
                                COUNT(DISTINCT tank_no) AS tank_cnt,
                                CASE
                                    WHEN SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) <= 0 THEN 1
                                    WHEN SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) < (SUM(sch.avgsales_7days) / 7) THEN 2
                                    WHEN SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) >= (SUM(sch.avgsales_7days) / 7)
                                         AND SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) <= (SUM(sch.avgsales_7days) / 7) * 3 THEN 3
                                    WHEN SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) > (SUM(sch.avgsales_7days) / 7) * 3
                                         AND SUM(CASE WHEN pumpable_Stock >= 0 THEN pumpable_Stock ELSE 0 END) <= (SUM(sch.avgsales_7days) / 7) * 6 THEN 4
                                    ELSE 6
                                END AS status
                            FROM "HPCL_HOS".sch_inventory_forecast_dashboard as sch
                            WHERE sch.volume > 0
                            GROUP BY site_id, fcc_code, product_grp
                            ORDER BY site_id, fcc_code, product_grp
                        ) AS result1
                        WHERE status < 6
                        GROUP BY status
                        ORDER BY seqno
                    ) AS result2"""
