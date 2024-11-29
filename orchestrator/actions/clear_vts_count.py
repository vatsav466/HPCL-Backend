import urdhva_base
import traceback
import hpcl_ceg_model

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")


class ClearVtsCount:
    async def clear_vts_count(cls, device_name, vehicle_number):
        """
        Clear the old count for a given VTS device name and vehicle number.
        
        Parameters:
        device_name (str): The VTS device name for which count is to be cleared.
        vehicle_number (str): The vehicle number for which count is to be cleared.
        
        Returns:
        tuple: (bool, str) A tuple indicating the success or failure of the operation and the reason.
        """
        try:
            if device_name in ["stoppage_violations_count", "route_deviation_count", "speed_violation_count", "main_supply_removal_count",
                            "night_driving_count", "no_halt_zone_count", "device_offline_count", "device_tamper_count"]:
                query = (f"vehicle_number='{vehicle_number}' and bu='{'TAS'}"
                        f"and status='Open' and device_name='{device_name}'"
                        f"and sop_id ='{"SOP001"}'")
                qstatus, resp = await hpcl_ceg_model.VTS.get_all(urdhva_base.queryparams.QueryParams(q=query), resp_type='plain')
                if resp['data']:
                    vts_record = resp['data'][0]
                    vts_record[device_name] = 0
                    await hpcl_ceg_model.VTS(**vts_record).modify()
                return True, "Old count cleared Successfully"
        
        except Exception as e:
            print(traceback.format_exc())
            logger.error(e)
            return False, "Failed to clear count"