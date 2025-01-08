#!/bin/bash

cd /opt/ceg/algo/api_manager
source /opt/ceg/venv/bin/activate
unbffer python /opt/ceg/algo/orchestrator/alerting/listener/sync_ims_indent_products.py > /var/log/ceg_sys_logs/sync_ims_indent_products.log
unbffer python /opt/ceg/algo/orchestrator/alerting/listener/sync_ims_indent_request.py > /var/log/ceg_sys_logs/sync_ims_indent_request.log
unbffer python /opt/ceg/algo/orchestrator/alerting/listener/sync_ims_truck_swipe.py > /var/log/ceg_sys_logs/sync_ims_truck_swipe.log