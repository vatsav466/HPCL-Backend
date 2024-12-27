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

dry_out_top_x_axis = [{"name": "Indent Not Raised", "group": "not_raised"}, {"name": "Pending Indents", "group": "pending"},
                  {"name": "Indent On Hold", "group": "pending"}, {"name": "Truck Allocated", "group": "wip"},
                  {"name": "Sent to SAP", "group": "wip"}, {"name": "Sales Order Placed", "group": "wip"},
                  {"name": "R2 Swiped", "group": "wip"}, {"name": "Invoice Created", "group": "wip"},
                  {"name": "R3 Swiped", "group": "wip"}, {"name": "VTS", "group": "wip"},
                  {"name": "Indent Delivered", "group": "delivered"}]

dry_out_bottom_x_axis = [
        "Dealer", "SO\nRM", "SO\nCO", "SO", "SO\nRM", "SO\nRM", "PO\nRM", "PO\nRM", "PO\nRM", "PO\nRM", "SO\nRM"
    ]

creds_type = {
    "2": {"cred_model": "Databases", 'cred_type': "PostgreSQL"},
    "3": {"cred_model": "Databases", 'cred_type': "Oracle"},
    "1": {"cred_model": "Databases", 'cred_type': "PostgreSQL"}
}