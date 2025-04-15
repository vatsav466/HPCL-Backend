import urdhva_base
import time
import datetime
import traceback
import hpcl_ceg_model
import utilities.helpers as helpers

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")

class CauseEffect:
    async def get_required_variables(self):
        return ["BU", "sap_id", "sop_id", "device_id", 
                "device_type", "device_name", "cause_effect", 
                "effect_sop_id", "cause_sop_id", "alert_id", "interlock_name"]

    # async def handle_cause_alert(self, params):
    #     effect_sop_id = params.get("effect_sop_id")
    #     if isinstance(effect_sop_id, list):
    #         effect_sop_id = ','.join([f"'{item.strip('[]')}'" for item in effect_sop_id])
        
    #     # Get current cause alert details
    #     interlock_name = params.get("interlock_name", "Unknown")
        
    #     query = (
    #         f"""bu = '{params.get("BU")}' and """
    #         f"""sap_id = '{params.get("sap_id")}' and """
    #         f"""sop_id in ({effect_sop_id}) and """
    #         f"""device_id = '{params.get("device_id")}' and """ 
    #         # f"""device_type = '{params.get("device_type")}' and """ 
    #         # f"""device_name like '%{params.get("device_name")}%' and """ 
    #         f"""cause_effect = 'Effect'"""
    #     )

    #     query_params = urdhva_base.queryparams.QueryParams()
    #     query_params.q = query
    #     query_params.sort = {"created_at": "desc"}

    #     effect_alerts = await hpcl_ceg_model.Alerts.get_all(query_params, resp_type='plain')
    #     processed_time = datetime.datetime.now(datetime.timezone.utc)
        
    #     if effect_alerts['data']:
    #         # Found effect alerts - update their history
    #         for effect_alert in effect_alerts['data']:
    #             effect_alert_id = effect_alert['id']
    #             existing_effect_history = effect_alert.get('alert_history', [])
    #             last_processed_time = processed_time

    #             for entry in reversed(existing_effect_history):
    #                 if entry.get("action_type") == "InterlockCreated" and entry.get("processed_time"):
    #                     last_processed_time = entry.get("processed_time")
    #                     break
                
    #             new_entry = {
    #                 "processed_time": processed_time.isoformat(),
    #                 "allocated_time": last_processed_time,
    #                 "action_msg": f"Related Cause alert {interlock_name} created",
    #                 "action_type": "Cause"
    #             }

    #             updated_effect_history = existing_effect_history + [new_entry]
    #             print("updated_effect_history  ---> ", updated_effect_history)
    #             effect_data_obj = hpcl_ceg_model.Alerts(id=effect_alert_id, alert_history=updated_effect_history)
    #             await effect_data_obj.modify()
        
    #     # Even if we didn't find effect alerts, we don't add any special marker
    #     # When effect alerts come in later, they'll have to find the related cause alerts

    #     return True, {"Message": "Alert History updated"}

    # async def handle_effect_alert(self, params):
    #     if params.get('interlock_name', '').lower().endswith('_fail'):
    #         return True, {"Message": "Skipped _fail interlock"}
        
    #     # Get current effect alert details
    #     interlock_name = params.get("interlock_name", "Unknown")
    #     cause_sop_id = params.get("cause_sop_id")

    #     query = (
    #         f"""bu = '{params.get("BU")}' and """
    #         f"""sap_id = '{params.get("sap_id")}' and """
    #         f"""sop_id = '{cause_sop_id}' and """
    #         f"""device_id = '{params.get("device_id")}' and """ 
    #         # f"""device_type = '{params.get("device_type")}' and """ 
    #         # f"""device_name like '%{params.get("device_name")}%' and """ 
    #         f"""cause_effect = 'Cause'"""
    #     )

    #     query_params = urdhva_base.queryparams.QueryParams()
    #     query_params.q = query
    #     query_params.sort = {"created_at": "desc"}
    #     print("query_params --> ", query_params)
    #     cause_alerts = await hpcl_ceg_model.Alerts.get_all(query_params, resp_type='plain')
    #     print("cause_alerts --> ", cause_alerts)
    #     processed_time = datetime.datetime.now(datetime.timezone.utc)
        
    #     if cause_alerts['data']:
    #         print("into if cause_alerts['data']", cause_alerts['data'])
    #         # Found cause alerts - update their history
    #         for cause_alert in cause_alerts['data']:
    #             print("cause_alert --> ", cause_alert)
    #             cause_alert_id = cause_alert['id']
    #             existing_cause_history = cause_alert.get('alert_history', [])
    #             last_processed_time = processed_time

    #             print("existing_cause_history  ---> ", existing_cause_history)

    #             for entry in reversed(existing_cause_history):
    #                 print("entry --> ", entry)
    #                 if entry.get("action_type") == "InterlockCreated" and entry.get("processed_time"):
    #                     last_processed_time = entry.get("processed_time")
    #                     break
                
    #             new_entry = {
    #                 "processed_time": processed_time.isoformat(),
    #                 "allocated_time": last_processed_time,
    #                 "action_msg": f"Related Effect alert {interlock_name} created",
    #                 "action_type": "Effect"
    #             }

    #             print("new_entry  ---> ", new_entry)

    #             updated_cause_history = existing_cause_history + [new_entry]
    #             print("updated_cause_history  ---> ", updated_cause_history)

    #             cause_data_obj = hpcl_ceg_model.Alerts(id=cause_alert_id, alert_history=updated_cause_history)
    #             await cause_data_obj.modify()
        
    #     # Even if we didn't find cause alerts, we don't add any special marker
    #     # When cause alerts come in later, they'll have to find the related effect alerts
        
    #     return True, {"Message": "Alert History updated"}

    async def handle_cause_alert(self, params):
        effect_sop_id = params.get("effect_sop_id")
        if isinstance(effect_sop_id, list):
            effect_sop_id = ','.join([f"'{item.strip('[]')}'" for item in effect_sop_id])
        
        # Get current cause alert details
        cause_alert_id = params.get("alert_id")  # Get the current cause alert ID
        interlock_name = params.get("interlock_name", "Unknown")
        
        query = (
            f"""bu = '{params.get("BU")}' and """
            f"""sap_id = '{params.get("sap_id")}' and """
            f"""sop_id in ({effect_sop_id}) and """
            f"""device_id = '{params.get("device_id")}' and """ 
            # f"""device_type = '{params.get("device_type")}' and """ 
            # f"""device_name like '%{params.get("device_name")}%' and """ 
            f"""cause_effect = 'Effect'"""
        )

        query_params = urdhva_base.queryparams.QueryParams()
        query_params.q = query
        query_params.sort = {"created_at": "desc"}

        effect_alerts = await hpcl_ceg_model.Alerts.get_all(query_params, resp_type='plain')
        processed_time = datetime.datetime.now(datetime.timezone.utc)
        
        # Variables to store the related effect alert info for updating cause history
        related_effect_interlock_names = []
        
        if effect_alerts['data']:
            # Found effect alerts - update their history
            for effect_alert in effect_alerts['data']:
                effect_alert_id = effect_alert['id']
                effect_interlock_name = effect_alert.get('interlock_name', "Unknown Effect")
                related_effect_interlock_names.append(effect_interlock_name)
                
                existing_effect_history = effect_alert.get('alert_history', [])
                last_processed_time = processed_time

                for entry in reversed(existing_effect_history):
                    if entry.get("action_type") == "InterlockCreated" and entry.get("processed_time"):
                        last_processed_time = entry.get("processed_time")
                        break
                
                new_entry = {
                    "processed_time": processed_time.isoformat(),
                    "allocated_time": last_processed_time,
                    "action_msg": f"Related Cause alert {interlock_name}",
                    "action_type": "Cause"
                }

                updated_effect_history = existing_effect_history + [new_entry]
                print("updated_effect_history  ---> ", updated_effect_history)
                effect_data_obj = hpcl_ceg_model.Alerts(id=effect_alert_id, alert_history=updated_effect_history)
                await effect_data_obj.modify()
        
        # Now update the current cause alert history with the effect alert info
        if cause_alert_id:
            cause_alert = await hpcl_ceg_model.Alerts.get(cause_alert_id)
            if cause_alert:
                existing_cause_history = getattr(cause_alert, 'alert_history', []) or []
                last_processed_time = processed_time

                for entry in reversed(existing_cause_history):
                    if entry.get("action_type") == "InterlockCreated" and entry.get("processed_time"):
                        last_processed_time = entry.get("processed_time")
                        break
                
                # Create a new entry for the cause alert history
                if related_effect_interlock_names:
                    # If we found effect alerts, list them
                    effect_names = ", ".join(related_effect_interlock_names)
                    new_cause_entry = {
                        "processed_time": last_processed_time,
                        "allocated_time": last_processed_time,
                        "action_msg": f"Related to Effect alert {effect_names}",
                        "action_type": "Effect"
                    }
                
                    updated_cause_history = existing_cause_history + [new_cause_entry]
                
                    cause_data_obj = hpcl_ceg_model.Alerts(id=cause_alert_id, alert_history=updated_cause_history)
                    await cause_data_obj.modify()

        return True, {"Message": "Alert History updated"}

    async def handle_effect_alert(self, params):
        if params.get('interlock_name', '').lower().endswith('_fail'):
            return True, {"Message": "Skipped _fail interlock"}
        
        # Get current effect alert details
        effect_alert_id = params.get("alert_id")  # Get the current effect alert ID
        interlock_name = params.get("interlock_name", "Unknown")
        cause_sop_id = params.get("cause_sop_id")

        query = (
            f"""bu = '{params.get("BU")}' and """
            f"""sap_id = '{params.get("sap_id")}' and """
            f"""sop_id = '{cause_sop_id}' and """
            f"""device_id = '{params.get("device_id")}' and """ 
            # f"""device_type = '{params.get("device_type")}' and """ 
            # f"""device_name like '%{params.get("device_name")}%' and """ 
            f"""cause_effect = 'Cause'"""
        )

        query_params = urdhva_base.queryparams.QueryParams()
        query_params.q = query
        query_params.sort = {"created_at": "desc"}
        print("query_params --> ", query_params)
        cause_alerts = await hpcl_ceg_model.Alerts.get_all(query_params, resp_type='plain')
        print("cause_alerts --> ", cause_alerts)
        processed_time = datetime.datetime.now(datetime.timezone.utc)
        
        # Variables to store the related cause alert info for updating effect history
        related_cause_interlock_name = None
        
        if cause_alerts['data']:
            print("into if cause_alerts['data']", cause_alerts['data'])
            # Found cause alerts - update their history
            for cause_alert in cause_alerts['data']:
                print("cause_alert --> ", cause_alert)
                cause_alert_id = cause_alert['id']
                related_cause_interlock_name = cause_alert.get('interlock_name', "Unknown Cause")
                existing_cause_history = cause_alert.get('alert_history', [])
                last_processed_time = processed_time

                print("existing_cause_history  ---> ", existing_cause_history)

                for entry in reversed(existing_cause_history):
                    print("entry --> ", entry)
                    if entry.get("action_type") == "InterlockCreated" and entry.get("processed_time"):
                        last_processed_time = entry.get("processed_time")
                        break
                
                new_entry = {
                    "processed_time": last_processed_time,
                    "allocated_time": last_processed_time,
                    "action_msg": f"Related Effect alert {interlock_name}",
                    "action_type": "Effect"
                }

                print("new_entry  ---> ", new_entry)

                updated_cause_history = existing_cause_history + [new_entry]
                print("updated_cause_history  ---> ", updated_cause_history)

                cause_data_obj = hpcl_ceg_model.Alerts(id=cause_alert_id, alert_history=updated_cause_history)
                await cause_data_obj.modify()
        
        # Now update the current effect alert history with the cause alert info
        if effect_alert_id:
            effect_alert = await hpcl_ceg_model.Alerts.get(effect_alert_id)
            if effect_alert:
                # Correct way to access fields from a Pydantic or SQLAlchemy model
                existing_effect_history = getattr(effect_alert, 'alert_history', []) or []
                last_processed_time = processed_time

                for entry in reversed(existing_effect_history):
                    if entry.get("action_type") == "InterlockCreated" and entry.get("processed_time"):
                        last_processed_time = entry.get("processed_time")
                        break
                
                # Create a new entry for the effect alert history
                cause_info = related_cause_interlock_name or "Unknown Cause"
                new_effect_entry = {
                    "processed_time": last_processed_time,
                    "allocated_time": last_processed_time,
                    "action_msg": f"Related to Cause alert {cause_info}",
                    "action_type": "Cause"
                }
                
                updated_effect_history = existing_effect_history + [new_effect_entry]
                
                effect_data_obj = hpcl_ceg_model.Alerts(id=effect_alert_id, alert_history=updated_effect_history)
                await effect_data_obj.modify()
        
        return True, {"Message": "Alert History updated"}


    async def cause_effect_alert(self, params):
        print("params --> ", params)
        try:
            if params.get('cause_effect') == 'Cause':
                return await self.handle_cause_alert(params)
            elif params.get('cause_effect') == 'Effect':
                return await self.handle_effect_alert(params)
            else:
                logger.warning(f"Unknown Cause_Effect value: {params.get('Cause_Effect')}")
                return None
        except Exception as e:
            logger.error(f"Error processing alert: {traceback.format_exc()}")
            return None
