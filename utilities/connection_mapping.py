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
    "camunda_dryout_01": {"host": "10.90.38.166", "port": 9090},
    "camunda_dryout_02": {"host": "10.90.38.166", "port": 9091},
    "camunda_dryout_03": {"host": "10.90.38.166", "port": 9092},
    "camunda_dryout_04": {"host": "10.90.38.166", "port": 9093},
    "camunda_dryout_05": {"host": "10.90.38.166", "port": 9094},
    "camunda_dryout_06": {"host": "10.90.38.166", "port": 9095},
    "camunda_dryout_07": {"host": "10.90.38.166", "port": 9096},
    "camunda_dryout_08": {"host": "10.90.38.166", "port": 9097},
    "camunda_dryout_09": {"host": "10.90.38.166", "port": 9098},
    "camunda_dryout_10": {"host": "10.90.38.166", "port": 9099}
}
