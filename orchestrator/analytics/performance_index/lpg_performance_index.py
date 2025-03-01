import urdhva_base.queryparams
import json
import pandas as pd
import hpcl_ceg_model
from utilities.helpers import map_device_category
import orchestrator.analytics.performance_index.performance_index_factory as performance_index_factory


class LPGPerformanceIndex(performance_index_factory.PerformanceIndex):
    def __init__(self):
        super().__init__()
        self.bu = "LPG"
        self.rules_df = None  # Initialize as None

    async def initialize(self):
        """Async method to load performance index rules for LPG."""
        self.rules_df = await self.load_performance_index()

    async def get_all_alerts(self, location_id):
        """Fetch all LPG alerts in an open state."""
        req_fields = ['interlock_name', 'created_at', 'sop_id']
        open_alerts = []
        params = urdhva_base.queryparams.QueryParams(q=f"bu='{self.bu}' and sap_id='{location_id}' "
                                                       f"and alert_status='Open'",
                                                     limit=10000, fields=json.dumps(req_fields))
        skip = 0
        while True:
            params.skip = skip
            print("params --> ", params)
            resp = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
            if resp['data']:
                open_alerts.extend(resp['data'])
            if resp['count'] < 10000:
                break
            skip += 1
        return open_alerts

    async def generate_performance_index_lpg(self, location_id):
        """
        Generate the performance index for LPG based on alert data and dynamic rules from self.rules_df.
        """
        # Step 1: Fetch all open alerts
        open_alerts = await self.get_all_alerts(location_id)

        if not open_alerts:
            return {"oi_score": 0, "details": "No open alerts found"}

        alerts_df = pd.DataFrame(open_alerts)

        if 'interlock_name' not in alerts_df.columns:
            return {"oi_score": 0, "details": "Invalid alert data format"}

        # Step 2: Fetch rules for LPG from self.rules_df
        lpg_rules = self.rules_df[self.rules_df['BU'] == 'LPG']

        if lpg_rules.empty:
            return {"oi_score": 0, "details": "No LPG rules found"}

        alerts_df['DeviceCategory'] = alerts_df['interlock_name'].map(map_device_category)
        total_devices = alerts_df['interlock_name'].nunique()
        print("total_devices --> ", total_devices)
        if total_devices == 0:
            return {"oi_score": 0, "details": "No valid devices found"}

        alert_counts = alerts_df.groupby('DeviceCategory')['interlock_name'].nunique()
        print("alert_counts --> ", alert_counts)

        # Step 5: Compute OI Score
        oi_scores = {}
        total_oi_score = 0

        for _, rule in lpg_rules.iterrows():
            print("rule --> ", rule)
            category = rule['DeviceCategory']
            print("rule category --> ", category)
            weightage = rule['Weightage']
            print("rule weightage --> ", weightage)

            if category not in alert_counts:
                continue  # Skip if no alerts exist for this category

            open_alert_devices = alert_counts[category]
            print("rule open_alert_devices --> ", open_alert_devices)
            rejection_percentage = (open_alert_devices / total_devices) * 100
            print("rule rejection_percentage --> ", rejection_percentage)

            # Fetch rejection thresholds dynamically
            thresholds = self.extract_thresholds(rule['Rejections'])
            print("rule thresholds --> ", thresholds)

            # Determine score based on rejection percentage
            score = self.calculate_score(rejection_percentage, thresholds)
            print("rule score --> ", score)

            # Apply weightage
            weighted_score = (score / 100) * weightage
            print("rule weighted_score --> ", weighted_score)
            oi_scores[category] = {"oi_score": float(weighted_score), "weightage": int(weightage)}
            total_oi_score += weighted_score

        return {"lpg_oi_score": round(total_oi_score, 2), "lpg_category_scores": oi_scores}

    # Helper function to extract threshold ranges from the rules
    def extract_thresholds(self, rejection_rules):
        """
        Parses rejection thresholds dynamically from the rules DataFrame.
        """
        thresholds = []
        rules_list = rejection_rules.split('\n')  # Assuming rules are stored in multiple lines

        for rule in rules_list:
            parts = rule.split('%')
            if len(parts) > 1:
                range_values = re.findall(r'\d+', rule)
                if len(range_values) == 1:
                    thresholds.append((float(range_values[0]), 100 if '≤' in rule else 0))
                elif len(range_values) == 2:
                    thresholds.append((float(range_values[0]), float(range_values[1]), 0, 100))  # range condition
        return thresholds

    # Helper function to calculate score based on rejection percentage
    def calculate_score(self, rejection_percentage, thresholds):
        """
        Determines the score based on dynamic thresholds.
        """
        for threshold in thresholds:
            if len(threshold) == 2 and rejection_percentage <= threshold[0]:
                return threshold[1]
            elif len(threshold) == 4 and threshold[0] < rejection_percentage <= threshold[1]:
                return threshold[3]
        return 0  # Default score if no conditions match
