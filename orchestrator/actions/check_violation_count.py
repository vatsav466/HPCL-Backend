import urdhva_base
import datetime
import traceback
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class CheckViolationCount:
    async def check_violation_count(self, sap_id, bu, vehicle_number, violation_type, created_at=None):
        """
        This method is used to get the violation count for a given vehicle from the DB
        based on the given violation type and sap id.
        
        Parameters:
        sap_id (str): The SAP ID of the vehicle.
        bu (str): The Business Unit of the vehicle.
        vehicle_number (str): The vehicle number for which violation count is to be fetched.
        violation_type (str): The type of violation for which count is to be fetched.
        
        Returns:
        int: The violation count of the vehicle.
        """
        try:
            # Get the current date and calculate the first day of the current quarter
            if created_at:
                  current_date = created_at
            else:
                current_date = datetime.datetime.now()
            current_quarter = int((current_date.month - 1) / 3 + 1)
            dt_firstday = datetime.datetime(current_date.year, 3 * current_quarter - 2, 1)
            
            # Format the start date in the same format as the database ('YYYY-MM-DD HH:MM:SS.SSSSSS')
            start_date_time = dt_firstday.strftime("%Y-%m-%d")

            # Construct the query
            query = (f"sap_id='{sap_id}' and bu='{bu}' and vehicle_number='{vehicle_number}' "
                     f"and violation_type='{violation_type}' and sop_id='SOP001' "
                     f"and created_at::DATE >= '{start_date_time}'")
            # Fetch the count of violations matching the query
            count = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query),resp_type='plain')
            return count

        except Exception as e:
            # Log the error and return None
            print(traceback.format_exc())
            logger.error(e)
            return None

    async def check_violation_all_count(self,sap_id, bu, vehicle_number, violation_type):
        """
        This method is used to get the violation count for a given vehicle from the DB
        based on the given violation type, SAP ID, business unit, and vehicle number.

        Parameters:
        sap_id (str): The SAP ID of the vehicle.
        bu (str): The Business Unit of the vehicle.
        vehicle_number (str): The vehicle number for which violation count is to be fetched.
        violation_type (str): The type of violation for which count is to be fetched.

        Returns:
        dict: A dictionary with the violation type as the key and the violation count as the value.
            If an error occurs, the value will be None.
        """
        finalresp = {}
        try:
            query = f"bu='{bu}' and sap_id='{sap_id}' and vehicle_number='{vehicle_number}' and violation_type='{violation_type}' and sop_id='SOP001'"
            count = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query), resp_type='plain')
            finalresp[violation_type] = count
        
        except Exception as e:
            # Log the error and return None
            print(traceback.format_exc())
            logger.error(e)
            finalresp[violation_type] = None
        return finalresp
    async def check_interlock(self,sap_id, bu, vehicle_number, interlockname,violation_type):
        """
        This method is used to get the violation count for a given vehicle from the DB
        based on the given violation type, SAP ID, business unit, and vehicle number.

        Parameters:
        sap_id (str): The SAP ID of the vehicle.
        bu (str): The Business Unit of the vehicle.
        vehicle_number (str): The vehicle number for which violation count is to be fetched.
        violation_type (str): The type of violation for which count is to be fetched.

        Returns:
        dict: A dictionary with the violation type as the key and the violation count as the value.
            If an error occurs, the value will be None.
        """
        try:
            query = f"bu='{bu}' and sap_id='{sap_id}' and interlock_name='{interlockname}' and alert_status='Open' and vehicle_number='{vehicle_number}' and violation_type='{violation_type}' and sop_id='SOP001'"
            data = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query), resp_type='plain')
            if len(data['data']):
                return data['data'][0]            
        except Exception as e:
            # Log the error and return None
            print(traceback.format_exc())
            logger.error(e)
    
    async def checktripcount(self,sap_id, bu, vehicle_number, violation_type):
        """
        This method is used to get the violation count for a given vehicle from the DB
        based on the given violation type, SAP ID, business unit, and vehicle number.

        Parameters:
        sap_id (str): The SAP ID of the vehicle.
        bu (str): The Business Unit of the vehicle.
        vehicle_number (str): The vehicle number for which violation count is to be fetched.
        violation_type (str): The type of violation for which count is to be fetched.

        Returns:
        dict: A dictionary with the violation type as the key and the violation count as the value.
            If an error occurs, the value will be None.
        """
        try:
            query = f"bu='{bu}' and sap_id='{sap_id}' and alert_status='Open' and vehicle_number='{vehicle_number}' and violation_type='{violation_type}' and sop_id='SOP001'"
            data = await hpcl_ceg_model.Alerts.get_all(urdhva_base.queryparams.QueryParams(q=query, limit=1), resp_type='plain')
            if len(data['data']):
                return data['data'][0]            
        except Exception as e:
            # Log the error and return None
            print(traceback.format_exc())
            logger.error(e)
    
        
