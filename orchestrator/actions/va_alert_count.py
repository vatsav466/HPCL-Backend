import urdhva_base
import traceback
import datetime
import hpcl_ceg_model
import utilities.helpers as helpers
import orchestrator.alerting.alert_manager as alert_manager

logger = urdhva_base.logger.Logger.getInstance("actions-processing-log")

class VAAlertMapping:
    async def vaalertmapping(self, params):
        """
        Updates the status of the alert with the given alert_id to "Under Maintenance",
        clears the role and rolelist, and sets final approval to True in the database.

        Args:
            params (dict): A dictionary containing 'alert_id'.

        Returns:
            str: "2", "1", or "0" based on conditions.
        """
        try:
            alert_data = await hpcl_ceg_model.Alerts.get(params.get('alert_id'))
            
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__
            
            interlock_name = alert_data.get("interlock_name", "")
            bu = alert_data.get("bu", "")
            count = 0
            
            if alert_data.get("va_rolemap", ""):
                return alert_data["va_rolemap"]
            
            maintenance_time = helpers.get_time_stamp_by_delta(
                days=7, with_month_start_day=False, ascending=False, date_time_format=None
            ).strftime("%Y-%m-%d")
            maintenance_time = datetime.datetime.strptime(maintenance_time, "%Y-%m-%d")
            
            query = (
                f"sap_id='{alert_data.get('sap_id', '')}' and bu='{bu}' "
                f"and device_id='{alert_data.get('device_id', '')}' "
                f"and created_at::DATE>='{maintenance_time}' "
                f"and interlock_name='{interlock_name}'"
            )
            
            count_result = await hpcl_ceg_model.Alerts.get_all(
                urdhva_base.queryparams.QueryParams(q=query), resp_type='plain'
            )
            count = count_result['count']

            # Condition checking for threshold "2"
            if (
                (bu == "TAS" and (
                    (interlock_name in [
                        "Non compliance of Fire Extinguisher (TT Unloading)", "Perimeter Intrusion",
                        "TT Dome Covers/ valve Box in open status", "Safety Harness non compliance (TT Unloading)",
                        "Wheel choke non compliance (TT Unloading)"
                    ] and count > 25)
                    or
                    (interlock_name in [
                        "Intrusion in nonworking hours (Storage Area/Wagon Gantry)", "Obstruction on approach road (Emergency gate)",
                        "PPE non compliance", "Product filling in unauthorized container (TT Gantry)",
                        "TT Crew non availability (TT unloading)", "TT Crew entering below TT",
                        "Unauthorized activity in parking area"
                    ] and count > 50)
                    or
                    (interlock_name in [
                        "Non availability of Crash Guard in TT", "Emergency gate Key Removal",
                        "Parking Discipline deviation", "Unauthorized Activity (Emergency Gate opening )"
                    ] and count > 60)
                    or
                    (interlock_name in [
                        "Clustering of people", "TT Branding non compliance", "Unauthorized activity (Stacking of unwanted material in shed)"
                    ] and count > 100)
                ))
                or
                (bu == "LPG" and (
                    (interlock_name in [
                        "Non compliance of Fire Extinguisher (TT Unloading)", "Wheel choke non compliance (TT Unloading)"
                    ] and count > 15)
                    or
                    (interlock_name == "Perimeter Intrusion" and count > 25)
                    or
                    (interlock_name in [
                        "Intrusion in nonworking hours (Storage Area/Wagon Gantry)", "Obstruction on approach road (Emergency gate)",
                        "PPE non compliance", "TT Crew non availability (TT unloading)", "TT Crew entering below TT",
                        "Unauthorized activity in parking area"
                    ] and count > 50)
                ))
                or (interlock_name == "Fire/Leak/Leakage" and count > 2)
            ):
                alert_data["va_rolemap"]="2"
                await hpcl_ceg_model.Alerts(**alert_data).modify()
                return "2"
            
            # Condition checking for threshold "1"
            elif (
                (bu == "TAS" and (
                    (interlock_name in [
                        "Non compliance of Fire Extinguisher (TT Unloading)", "Perimeter Intrusion",
                        "TT Dome Covers/ valve Box in open status", "Safety Harness non compliance (TT Unloading)",
                        "Wheel choke non compliance (TT Unloading)"
                    ] and count > 10)
                    or
                    (interlock_name in [
                        "Intrusion in nonworking hours (Storage Area/Wagon Gantry)", "Obstruction on approach road (Emergency gate)",
                        "PPE non compliance", "Product filling in unauthorized container (TT Gantry)",
                        "TT Crew non availability (TT unloading)", "TT Crew entering below TT",
                        "Unauthorized activity in parking area"
                    ] and count > 25)
                    or
                    (interlock_name in [
                        "Non availability of Crash Guard in TT", "Emergency gate Key Removal",
                        "Parking Discipline deviation", "Unauthorized Activity (Emergency Gate opening )"
                    ] and count > 35)
                    or
                    (interlock_name in [
                        "Clustering of people", "TT Branding non compliance", "Unauthorized activity (Stacking of unwanted material in shed)"
                    ] and count > 50)
                ))
                or
                (bu == "LPG" and (
                    (interlock_name in [
                        "Non compliance of Fire Extinguisher (TT Unloading)", "Perimeter Intrusion",
                        "Wheel choke non compliance (TT Unloading)"
                    ] and count > 10)
                    or
                    (interlock_name in [
                        "Unauthorized Activity (Emergency Gate opening )", "Non availability of TT Crew inside the vehicle",
                        "Position of Truck on weigh bridge", "Parking Discipline deviation"
                    ] and count > 35)
                    or
                    (interlock_name in [
                        "Intrusion in nonworking hours (Storage Area/Wagon Gantry)", "Obstruction on approach road (Emergency gate)",
                        "PPE non compliance", "TT Crew non availability (TT unloading)", "TT Crew entering below TT",
                        "Unauthorized activity in parking area"
                    ] and count > 25)
                    or
                    (interlock_name in [
                        "Detection of rolling of cylinders", "Clustering of people"
                    ] and count > 50)
                    or
                    (interlock_name == "Detection of LPG Leakages thru Filling Gun" and count > 5)
                ))
                or (interlock_name == "Fire/Leak/Leakage" and count > 1)
            ):
                alert_data["va_rolemap"]="1"
                await hpcl_ceg_model.Alerts(**alert_data).modify()
                return "1"
            
            else:
                alert_data["va_rolemap"]="0"
                await hpcl_ceg_model.Alerts(**alert_data).modify()
                return "0"
        except Exception as e:
            logger.error(e)
            print(traceback.format_exc())
            return False, e
