import datetime
import urdhva_base
import api_manager
import urdhva_base.queryparams
import dateutil.parser as dt_parser
import orchestrator.alerting.alert_helper as alert_helper
import orchestrator.alerting.alert_factory as alert_factory

logger = urdhva_base.logger.Logger.getInstance("emlock_alertmanager")


class EMLockAlertManager(alert_factory.AlertFactory):
    @classmethod
    async def create_bu_alert(cls, alert_data):
        """
        Converting/Transforming EMLock raw alert data into unique alert data format
        :param alert_data:
        :return:
        """
        recv_time = datetime.datetime.now(tz=datetime.timezone.utc)
        for record in alert_data['data']:
            status, location_details = alert_helper.get_location_details(record['location_type'], record['location_id'])
            if not status:
                logger.info(f"Error in finding location {record['location_id']} "
                            f"for bu {record['location_type']} - {location_details}")
                continue
            exception_msg = (f"Vehicle Number - {record['vehicle_number']}, Violation Type - {record['violation_type']}"
                             f", Approved By - {record['approved_by']}, "
                             f"Exception Date - {recv_time}")
            query = (f"where sap_id={record['location_id']} and vehicle_number='{record['vehicle_number']}' "
                     f"and status='Open' and violation_type='{record['violation_type']}'")

            data = await api_manager.hpcl_ceg_model.EMLock.get_all(urdhva_base.queryparams.QueryParams(q=query, limit=1))
            if len(data['data']):
                # Updating existing EM Lock record
                em_lock_record = data['data'][0]
                em_lock_record['violation_history'].append(exception_msg)
                if (recv_time - dt_parser.parse(em_lock_record['violation_start_date'])).days > 15:
                    em_lock_record['violation_count'] = 0
                else:
                    em_lock_record['violation_count'] += 1
                if em_lock_record['violation_count'] > 10:
                    # Create Alert record and class create_alert
                    em_lock_record['violation_count'] = 0
            else:
                # Creating EM Lock record
                em_lock_record = {"bu": record['location_type'], "sap_id": record['location_id'],
                                  "location_name": location_details['name'], "vehicle_number": record['vehicle_number'],
                                  "violation_type": record['violation_type'],
                                  "violation_count": 1, "status": 'Open', "violation_history": [exception_msg],
                                  "violation_start_date": recv_time}

    @classmethod
    def close_bu_alert(cls, alert_data):
        ...
