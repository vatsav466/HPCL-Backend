import urdhva_base
import uuid
import hpcl_ceg_model
import orchestrator.analytics.ro_analysis as ro_analysis
import utilities.cris_alert_mapping as cris_alert_mapping

class SendRoCommand:
    def __init__(self):
        self.params = dict()

    async def get_required_variables(self):
        return ["alert_id", "va_level", "vehicle"]

    async def interlock_disable_command(self, params: dict):
        if not self.params:
            self.params = params

        alert_data = await hpcl_ceg_model.Alerts.get(self.params['alert_id'])
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        interlock_data = cris_alert_mapping.Cris_Alert_Mapping[alert_data['bu']][alert_data['violation_type']]
        interlock_data = interlock_data['escalations'][self.params['va_level']]
        interlock_disable = {
            "rocode": alert_data['sap_id'],
            "reqno": str(uuid.uuid4()),
            "interlocktype": alert_data['violation_type'],
            "device": alert_data['device_name'],
            "deviceid": alert_data['device_id'],
            "disablehrs": interlock_data['disabling_hrs']
        }
        resp = await ro_analysis.interlock_disable(interlock_disable)
        print(f"Ro interlock disable resp: {resp}")
        return True, {"msg": "Ok"}