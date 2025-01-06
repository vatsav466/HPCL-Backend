connection_mapping = {
    "ims": "3",
    "hpcl_ceg": "1",
    "cris": "2"
}

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

camunda_listener_mapping = {
    "camunda_dryout_01": {"host": "10.90.38.167", "port": 9080},
    "camunda_dryout_02": {"host": "10.90.38.167", "port": 9081},
    "camunda_dryout_03": {"host": "10.90.38.167", "port": 9082},
    "camunda_dryout_04": {"host": "10.90.38.167", "port": 9083},
    "camunda_dryout_05": {"host": "10.90.38.167", "port": 9084},
    "camunda_dryout_06": {"host": "10.90.38.167", "port": 9085},
    "camunda_dryout_07": {"host": "10.90.38.167", "port": 9086},
    "camunda_dryout_08": {"host": "10.90.38.167", "port": 9087},
    "camunda_dryout_09": {"host": "10.90.38.167", "port": 9088},
    "camunda_dryout_10": {"host": "10.90.38.167", "port": 9089}
}

dry_out_top_x_axis = [{"name": "Indent Not Raised", "group": "not_raised"},
                  {"name": "Indent On Hold", "group": "pending"}, {"name": "Pending Indents", "group": "pending"},
                  {"name": "Truck Allocated", "group": "wip"},
                  {"name": "Sent to SAP", "group": "wip"}, {"name": "Sales Order Placed", "group": "wip"},
                  {"name": "R2 Swiped", "group": "wip"}, {"name": "Invoice Created", "group": "wip"},
                  {"name": "R3 Swiped", "group": "wip"}, {"name": "VTS", "group": "wip"}]
                  # {"name": "Indent Delivered", "group": "delivered"}]

truck_details = ["Dealer TT", "TT Available", "Empty Dealer TT Return", "Empty Transporter Return"]

dryout_aging = ["DryOut < 2 Days", "DryOut < 7 Days", "DryOut < 15 Days", "DryOut < 30 Days"]

dry_out_bottom_x_axis = [
        "Dealer", "SO\nRM", "SO\nCO", "SO", "SO\nRM", "SO\nRM", "PO\nRM", "PO\nRM", "PO\nRM", "PO\nRM", "SO\nRM"
    ]

creds_type = {
    "2": {"cred_model": "Databases", 'cred_type': "PostgreSQL"},
    "3": {"cred_model": "Databases", 'cred_type': "Oracle"},
    "1": {"cred_model": "Databases", 'cred_type': "PostgreSQL"}
}

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
