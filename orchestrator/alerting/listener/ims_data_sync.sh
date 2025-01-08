#!/bin/bash

cd /opt/ceg/algo/api_manager
source /opt/ceg/venv/bin/activate
unbuffer python /opt/ceg/algo/orchestrator/alerting/listener/sync_ims_indent_products.py > /var/log/ceg_sys_logs/sync_ims_indent_products.log
unbuffer python /opt/ceg/algo/orchestrator/alerting/listener/sync_ims_indent_request.py > /var/log/ceg_sys_logs/sync_ims_indent_request.log
unbuffer python /opt/ceg/algo/orchestrator/alerting/listener/sync_ims_truck_swipe.py > /var/log/ceg_sys_logs/sync_ims_truck_swipe.log