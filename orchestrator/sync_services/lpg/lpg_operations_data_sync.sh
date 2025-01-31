#!/bin/bash
cd /opt/ceg/algo/orchestrator/sync_services/lpg
source /opt/ceg/venv/bin/activate
unbuffer python /opt/ceg/algo/orchestrator/sync_services/lpg/lpg_get_rejections.py > /var/log/ceg_sys_logs/lpg_rejection_data_sync.log 2>&1
unbuffer python /opt/ceg/algo/orchestrator/sync_services/lpg/fetch_lpg_operations_data.py > /var/log/ceg_sys_logs/lpg_consolidated_data_sync.log 2>&1