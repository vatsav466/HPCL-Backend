import urdhva_base.queryparams
import json
import hpcl_ceg_model
import orchestrator.analytics.performance_index.performance_index_factory as performance_index_factory


class TASPerformanceIndex(performance_index_factory.PerformanceIndex):
    def __init__(self):
        super().__init__()
        self.bu = "TAS"

    async def get_all_alerts(self, location_id):
        # Load all alerts in open state
        req_fields = ['interlock_name', 'created_at', 'sop_id']
        open_alerts = []
        params = urdhva_base.queryparams.QueryParams(q=f"bu='{self.bu} and sap_id='{location_id} "
                                                       f"and alert_status='Open'",
                                                     limit=10000, fields=json.dumps(req_fields))
        skip = 0
        while True:
            params.skip = params
            resp = await hpcl_ceg_model.Alerts.get_all(params)
            if resp['data']:
                open_alerts.extend(resp['data'])
            if resp['count'] < 10000:
                break
            skip += 1

    async def load_performance_index(self):
        ...

    async def generate_performance_index(self, location_id):
        ...

    async def generate_performance_index_va(self, location_id):
        ...

    async def generate_performance_index_vts(self, location_id):
        ...

    async def generate_performance_index_tas(self, location_id):
        ...

    async def generate_performance_index_emlock(self, location_id):
        ...
