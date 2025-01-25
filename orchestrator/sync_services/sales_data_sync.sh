#!/bin/bash

cd /opt/ceg/algo/LPG
source /opt/ceg/venv/bin/activate
unbuffer python /opt/ceg/algo/Sales/sales_check.py > /var/log/ceg_sys_logs/sales_data_sync.log 2>&1

