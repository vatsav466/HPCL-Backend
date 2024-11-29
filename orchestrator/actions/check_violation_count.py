import urdhva_base
import datetime
import traceback
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class CheckViolationCount:
    async def check_violation_count(self, sap_id, vehicle_number, bu, violation_type):
        """
        This method is used to get the violation count for a given vehicle from the DB
        based on the given violation type and sap id.
        
        Parameters:
        sap_id (str): The sap id of the vehicle.
        vehicle_number (str): The vehicle number for which violation count is to be fetched.
        violation_type (str): The type of violation for which count is to be fetched.
        
        Returns:
        int: The violation count of the vehicle.
        """
        try:
            current_date = datetime.datetime.now()
            current_quarter = int((current_date.month - 1) / 3 + 1)
            dt_firstday = datetime.datetime(current_date.year, 3 * current_quarter - 2, 1)
            start_date = str(dt_firstday).replace(" ", "T")
            start_date_time = start_date + '.000Z'
            query = (f"sap_id='{sap_id}' and vehicle_number='{vehicle_number}' and bu='{bu}'"
                    f"and alert_status='Open' and violation_type='{violation_type}' and sop_id='{'SOP001'}'"
                    f"and created_at >='{start_date_time}'")
            status, count = await hpcl_ceg_model.Alerts.count(urdhva_base.queryparams.QueryParams(q=query), resp_type='plain')
            return count

        except Exception as e:
            print(traceback.format_exc())
            logger.error(e)
            return None

    async def check_violation_all_count(self, sap_id, vehicle_number, bu, violation_type):
        data = ['Speed Violation', 'Unauthorized Stoppage', 'Night Driving', 'Route Deviation', 'Power Disconnect','No Halt_Zone','VTS device_tampering','VTS offline']
        finalresp = {}
        for devicename in data:
            query = (f"sap_id='{sap_id}' and vehicle_number='{vehicle_number}' and bu='{bu}'"
                     f"and alert_status='Open' and violation_type='{violation_type}' and sop_id='{'SOP001'}'")
            status, count = await hpcl_ceg_model.Alerts.count(urdhva_base.queryparams.QueryParams(q=query), resp_type='plain')
            finalresp[devicename] = count
        return finalresp
    