import urdhva_base
import pytz
import datetime
import hpcl_ceg_model
import orchestrator.analytics.vts_analysis as vts_analysis
import orchestrator.alerting.alert_manager as alert_manager

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class SendVtsCommand:

    async def get_required_variables(self):
        return ["alert_id", "interrupt", "WaivedOff", "auto_unblock", "BU"]
    
    async def sendvtscommand(self, params):
        print("params --->", params)
        if 'WaivedOff' in params.keys():
            params['WaivedOff'] = True if params['WaivedOff'] == 'true' else False
        if 'auto_unblock' in params.keys():
            params['auto_unblock'] = True if params['auto_unblock'] == 'true' else False

        alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))
        if not isinstance(alert_data, dict):
            alert_data = alert_data.__dict__

        if urdhva_base.context.context.exists():
            rpt = urdhva_base.context.context.get('rpt', {})
        else:
            rpt = {}

        if params.get("interrupt").lower() == 'block':
            input_data = {
                "TT_No": alert_data['vehicle_number'],
                "BlockStartDate": alert_data['vehicle_blocked_start_date'].isoformat(),
                "BlockEndDate": alert_data['vehicle_blocked_end_date'].isoformat(),
                "BlockedRemarks": alert_data['device_name']
            }
            # await vts_analysis.post_blocked_tt(input_data)
            alert_message = (
                f"Alert details Alert ID: {alert_data.get('unique_id', '')}, status: Block, Vehicle: {alert_data.get('vehicle_number', '')} trip details are sent successfully to VTS to block the Vehicle "
            )
            alert_data["action_msg"] = alert_message
            alert_data["action_type"] = "VTS"
            await alert_manager.AlertAction().update_alert_history(input_data=alert_data, alert_data=alert_data)
            return True, {"sapcommandsent": True}

        if params.get("interrupt").lower() == 'unblock':
            un_block_datetime = str(alert_data['vehicle_blocked_end_date'].isoformat()) if params.get(
                "auto_unblock", False) else str(urdhva_base.utilities.get_present_time().isoformat())
            approved_datetime = await alert_manager.get_approved_remarks(alert_data, is_approved=False, get_approved_time=True)
            doc_link = await alert_manager.get_doc_link_from_alert_history(alert_data)
            params1 = {
                "TT_No": alert_data['vehicle_number'],
                "UnBlockedBy": rpt.get("email", "NOVEX_USER"),
                "UnBlockedDateTime": un_block_datetime,
                "UnBlockedRemarks": await alert_manager.get_approved_remarks(alert_data, is_approved=False),
                "ApprovedBy": rpt.get("email", "NOVEX_USER"),
                "ApprovedDateTime": approved_datetime,
                "ApprovedRemarks": await alert_manager.get_approved_remarks(alert_data, is_approved=True),
                "BlockStartDate": str(alert_data['vehicle_blocked_end_date'].isoformat()),
                "BlockEndDate": str(alert_data['vehicle_blocked_start_date'].isoformat()),
                "WaivedOff": params.get("WaivedOff", False),
                "AlertID": alert_data['id'],
                "DocLink": {
                    "DocPaths": doc_link if doc_link else []
                }
            }
            # await vts_analysis.post_unblocked_tt(params1)
            if not params['auto_unblock']:
                query = (f"location_id='{alert_data['sap_id']}' and tl_number='{alert_data['vehicle_number']}' "
                         f"and {alert_data['violation_type']}>=1 and created_at<'{alert_data['created_at']}' and location_type='{alert_data['bu']}' "
                         f"and auto_unblock!='false'")
                data = await hpcl_ceg_model.VtsAlertHistory.get_all(urdhva_base.queryparams.QueryParams(q=query),
                                                                    resp_type='plain')
                data = data['data'][0]
                data['auto_unblock'] = False
                await hpcl_ceg_model.VtsAlertHistory(**data).modify()
                alert_data['mark_as_false'] = True
                await hpcl_ceg_model.Alerts(**alert_data).modify()
            
            alert_message = (
                f"Alert details Alert ID: {alert_data.get('unique_id', '')}, status: Unblock, Vehicle: {alert_data.get('vehicle_number', '')} trip details are sent successfully to VTS to Unblock the Vehicle "
            )
            alert_data["action_msg"] = alert_message
            alert_data["action_type"] = "VTS"
            await alert_manager.AlertAction().update_alert_history(input_data=alert_data, alert_data=alert_data)
            return True, {"sapcommandsent": True}

        return False, {"sapcommandsent": False}