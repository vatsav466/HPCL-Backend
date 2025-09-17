import urdhva_base
import pytz
import datetime
import hpcl_ceg_model
import orchestrator.analytics.vts_analysis as vts_analysis
import orchestrator.alerting.alert_manager as alert_manager


class MakerCheckerAcknowledgment:
    async def get_required_variables(self):
        return ["alert_id", "vts_alert_justified"]
    
    async def maker_checker_justification(self,params):

        alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))

        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__
        
        if "_sa_instance_state" in alert_data.keys():
            del alert_data["_sa_instance_state"]
        
        # rpt = urdhva_base.context.context.get("rpt", {})

        # if rpt:
        #     role = ", ".join(map(str, rpt.get('novex_role')))
        #     roles = f"{rpt.get('username')} ({role})"

        roles = ", ".join(f"'{roles_name}'" for roles_name in alert_data["assigned_user_roles"])

        if params.get('vts_alert_justified','') == 'checker':
            alert_message = (
                f"Vehicle UnBlocking Rejected by the checker {roles}"
                )
        
        if params.get('vts_alert_justified') == 'maker':
            alert_message = (
                f"Vehicle Blocking Accepted by the maker {roles}"
                )
            
        alert_data["action_msg"] = alert_message
        alert_data["action_type"] = "Blocked"
        await alert_manager.AlertAction().update_alert_history(input_data=alert_data, alert_data=alert_data)

        await hpcl_ceg_model.Alerts(**{"id": alert_data['id'], 
                                        "closed_at": datetime.datetime.now(),
                                        "alert_status": 'Close',
                                        "alert_state": 'Resolved'}).modify()
        
        return True, {"sapcommandsent": True}