#!/bin/bash

echo "Code Sync Started"

CodeDir='/opt/ceg/algo'
for folder in UrdhvaBase api_manager ceg_role_master_api orchestrator utilities vendor_ingestion_api workflow
do
  if [ ! -d $CodeDir/$folder ]; then
    mkdir -p $CodeDir/$folder
  fi
done

rsync -azSP UrdhvaBase/ $CodeDir/UrdhvaBase/ --exclude .alg_env
rsync -azSP api_manager/  $CodeDir/api_manager/  --exclude .alg_env
rsync -azSP ceg_role_master_api/  $CodeDir/ceg_role_master_api/  --exclude .alg_env
rsync -azSP orchestrator/  $CodeDir/orchestrator/  --exclude .alg_env
rsync -azSP utilities/  $CodeDir/utilities/  --exclude .alg_env
rsync -azSP vendor_ingestion_api/  $CodeDir/vendor_ingestion_api/  --exclude .alg_env
rsync -azSP workflow/  $CodeDir/workflow/  --exclude .alg_env

# shellcheck disable=SC2006
proxy_settings=`env | grep http_proxy`
if [ -z "$proxy_settings" ]; then
  pip_proxy=" --proxy $proxy_settings"
else
  pip_proxy=""
fi

cd $CodeDir/UrdhvaBase
/opt/ceg/venv/bin/python -m pip install "$pip_proxy" -e .
/opt/ceg/venv/bin/python -m pip install "$pip_proxy" -r requirements.txt

mkdir -p /var/log/ceg_sys_logs/ | true
mkdir -p /var/log/ceg_logs/ | true


echo "Restarting All Base API Services"

for ((port=9001; port <= 9005; port++))
do
  echo "Restarting ceg_api@\"$port\" Service"
  systemctl restart ceg_api@"$port".service
  systemctl enable ceg_api@"$port".service
  sleep 5
done

echo "Restarting DNC API Services"

for ((port=9009; port <= 9009; port++))
do
  echo "Restarting ceg_dnc_role_api@\"$port\" Service"
  systemctl restart ceg_dnc_role_api@"$port".service
  systemctl enable ceg_dnc_role_api@"$port".service
  sleep 5
done

echo "Restarting Vendor Ingestion API Services"

for ((port=9010; port <= 9014; port++))
do
  echo "Restarting ceg_ingest_api@\"$port\" Service"
  systemctl restart ceg_ingest_api@"$port".service
  systemctl enable ceg_ingest_api@"$port".service
  sleep 5
done

systemctl start nginx

echo "Code Sync Completed"