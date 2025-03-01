import urdhva_base.queryparams
import os
import json
import pandas as pd
import hpcl_ceg_model
from utilities.helpers import map_device_category
import orchestrator.analytics.performance_index.performance_index_factory as performance_index_factory


class TASPerformanceIndex(performance_index_factory.PerformanceIndex):
    def __init__(self):
        super().__init__()
        self.bu = "TAS"
        self.rules_df = None  # Initialize as None

    async def initialize(self):
        """Async method to load performance index rules."""
        self.rules_df = await self.load_performance_index()

    async def get_all_alerts(self, location_id):
        # Load all alerts in open state
        req_fields = ['interlock_name', 'created_at', 'sop_id']
        open_alerts = []
        params = urdhva_base.queryparams.QueryParams(q=f"bu='{self.bu}' and sap_id='{location_id}' "
                                                       f"and alert_status='Open'",
                                                     limit=10000, fields=json.dumps(req_fields))
        skip = 0
        while True:
            params.skip = skip
            resp = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
            if resp['data']:
                open_alerts.extend(resp['data'])
            if resp['count'] < 10000:
                break
            skip += 1
        return open_alerts

    async def generate_performance_index(self, location_id):
        ...

    async def generate_performance_index_va(self, location_id):
        ...

    async def generate_performance_index_vts(self, location_id):
        ...

    async def generate_performance_index_tas(self, location_id):
        # Get all open alerts by Device category (Safety, Process, FE&Jockey, WaterLevl, FoamQty, PT) and distinct
        # devices Compute OI Score
        # weightage can be fetched from self.rules
        # oi_score = round(((total_devices - open_alert_devices) / total_devices) * weightage, 2) if total_devices >
        # 0 else 0
        # Example self.rules_df[self.rules_df['DeviceCategory'] == 'Process']['Weightage'][0]
        # Todo:- need to check Enabled key in future
        # Step 1: Fetch all open alerts
        open_alerts = await self.get_all_alerts(location_id)

        if not open_alerts:
            return {"oi_score": 0, "details": "No open alerts found"}

        alerts_df = pd.DataFrame(open_alerts)

        if 'interlock_name' not in alerts_df.columns:
            return {"oi_score": 0, "details": "Invalid alert data format"}

        # Map interlock_name to DeviceCategory using interlock_category_mapping
        alerts_df['DeviceCategory'] = alerts_df['interlock_name'].map(map_device_category)

        # Count total unique devices per category
        total_devices = alerts_df['interlock_name'].nunique()
        print("total_devices --> ", total_devices)

        alert_counts = alerts_df.groupby('DeviceCategory')['interlock_name'].nunique()

        # Compute OI Score
        oi_scores = {}
        total_oi_score = 0

        for category, open_alert_devices in alert_counts.items():
            print("category --> ", category)
            weightage = self.rules_df.loc[self.rules_df['DeviceCategory'] == category, 'Weightage'].values
            print("weightage --> ", weightage)
            weightage = weightage[0] if len(weightage) > 0 else 0  
            print("weightage len --> ", weightage)
            print("open_alert_devices --> ", open_alert_devices)

            oi_score = round(((total_devices - open_alert_devices) / total_devices) * weightage, 2) if total_devices > 0 else 0
            print("oi score --> ", oi_score)
            oi_scores[category] = oi_score
            print("oi_scores --> ", oi_scores)
            total_oi_score += oi_score
            print("total_oi_score --> ", total_oi_score)

        return {"oi_score": round(total_oi_score, 2), "category_scores": oi_scores}

    async def generate_performance_index_emlock(self, location_id):
        ...
