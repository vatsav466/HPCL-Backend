import urdhva_base
# import ThingsBoardApi
from api_manager import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class InterlockStatus:
    async def get_required_variables(self):
        return ["alert_id"]
    
    async def checkInterlockStatus(self, params):
        tbAltStatus = False
        print("params --> ", params)
        alert_id = params.get('alert_id')
        alert_data = await hpcl_ceg_model.Alerts.get(alert_id)

        if alert_data:
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__
            else:
                alert_data = alert_data
            
            tbAlertId = alert_data['external_id']
            bu = alert_data.get('bu', "")
            sap_id = alert_data.get('sap_id', '0')

            # tb = ThingsBoardApi.TB(bu, sap_id)
            try:
                # tbAltStatus = await tb.getTbAlertStatus(tbAlertId)
                tbAltStatus = True
            except Exception as e:
                print("Exception in getting current Alert status in thingsboard %s" % (e))
        return True, {"interlockcleared": tbAltStatus}
