import urdhva_base
import datetime
import traceback
import utilities.interlock_mapping
import utilities.helpers as helpers
import orchestrator.alerting.alert_helper as alert_helper
import orchestrator.alerting.alert_factory as alert_factory

logger = urdhva_base.logger.Logger.getInstance("nrd_alert_processing")


class NRDAlertManager(alert_factory.AlertFactory):
    @classmethod
    async def create_bu_alert(cls, alert_data, camunda_url=urdhva_base.settings.camunda_url):
        try:
            logger.info(f"alert_data received to create alert {alert_data}")

            # Retrieve necessary fields from the alert_data
            status, loc_dt = await alert_helper.get_location_details(bu=alert_data['bu'],
                                                                     sap_id=alert_data['sap_id'])
            if not status:
                logger.info(f"Error in finding location {alert_data['sap_id']} "
                            f"for bu {alert_data['bu']} - {loc_dt}")
                loc_dt = {'name': ""}

            exception_msg = (
                f"Vehicle Number: {alert_data['vehicle_number']} \n"
                f"Violation Type: No VTS No Load \n"
                f"Reported at: {alert_data['reported_at']}"
            )

            allocated_time = datetime.datetime.now(datetime.timezone.utc)
            processed_time = datetime.datetime.now(datetime.timezone.utc)
            alert_history = [{
                "action_msg": exception_msg,
                "action_type": "Created",
                "alert_status": "Open",
                "allocated_time": allocated_time.isoformat(),
                "processed_time": processed_time.isoformat()
                }]

            interlock_details = utilities.interlock_mapping.get_interlock_name(
                alert_data['bu'],"No VTS No Load")
            logger.info(f"NRD interlock data: {interlock_details}")
            
            # preparing alert_data for NRD
            interlock_details.update({"bu": alert_data['bu'],
                                      "location_name": loc_dt.get('name',''),
                                      "sap_id": alert_data['sap_id'],
                                      "alert_section": "VTS",
                                      "alert_history":alert_history,
                                      "violation_type": "No VTS No Load"
                                    })
            
            interlock_details['equipment_name'] = "No VTS No Load"
            interlock_details['vehicle_blocked_start_date'] = (urdhva_base.utilities.get_present_time()).isoformat()
            interlock_details['vehicle_blocked_end_date'] = urdhva_base.utilities.get_present_time() + datetime.timedelta(days=1826)
            interlock_details['mark_as_false'] = False
            
            camunda_url = await helpers.get_camunda_url(bu=alert_data['bu'], sap_id=alert_data['sap_id'], alert_section="VTS")
            await cls.create_alert(interlock_details, camunda_url)

        except Exception as e:
            print('traceback',traceback.format_exc())
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.error(e)
            return {"status": False, "message": str(e), "alert_data": None}

    @classmethod
    async def close_bu_alert(cls, alert_data):
        try:
            logger.info(f"Alert data received to close alert: {alert_data}")
            print('Traceback',traceback.format_exc())
            logger.error(f"Traceback: {traceback.format_exc()}")
            return await cls.close_alert(alert_data)

        except Exception as e:
            raise Exception(status_code=500, detail="Error closing alert.") from e
