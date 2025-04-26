import urdhva_base
import asyncio
import json
import datetime
import traceback
import hpcl_ceg_model
import orchestrator.alerting.alert_factory as alert_create
import orchestrator.alerting.listener.tas_maintenance_alert_check as alert_close

logger = urdhva_base.logger.Logger.getInstance("workflow_process-log")


class TasEsdActivation:
    async def get_required_variables(self):
        return [
            "BU", "sap_id", "sop_id", "device_id",
            "device_type", "device_name", "cause_effect",
            "effect_sop_id", "cause_sop_id", "alert_id", "interlock_name",
            "rosov_interlock_name", "dbbv_interlock_name", "esd_rosov_fail_status",
            "rosov_pl_mode", "esd_rosov_close_status", "esd_mov_fail_status",
            "mov_pl_mode", "esd_mov_close_status"
        ]

    async def tas_esd_activation_check(self, params):
        try:
            bu = params.get("BU", "")
            sap_id = params.get("sap_id", "")
            sop_id = params.get("sop_id", "")
            device_id = params.get("device_id", "")
            device_name = params.get("device_name", "")
            alert_id = params.get("alert_id", "")
            
            # Get the incoming interlock name
            interlock_name = params.get("interlock_name", "")
            
            # Define the known interlock names
            ROSOV_INTERLOCK = "All ROSOVs Closed(Except PL Receipt)_Fail"
            DBBV_INTERLOCK = "All DBBVs Closed(Except PL Receipt)_Fail"
            ESD_ROSOV_FAIL = "ESD ROSOV_Close Status_Fail"
            ROSOV_PL_MODE = "ROSOV in PL Receipt Mode"
            ESD_ROSOV_CLOSE = "ESD ROSOV_Close Status"
            ESD_MOV_FAIL = "ESD MOV_Close Status_Fail"
            MOV_PL_MODE = "MOV in PL Receipt Mode"
            ESD_MOV_CLOSE = "ESD MOV_Close Status"
            
            time_window = 2

            # Polling configuration for alert checking
            max_attempts = 6  # Total 30 seconds (6 attempts × 5 seconds)
            poll_interval = 5  # Check every 5 seconds
            
            # Initial counts
            maintenance_alert_count = fault_alert_count = rosov_pl_close_count = esd_close_status_count = 0
            mov_pl_close_count = esd_mov_close_status_count = 0
            esd_device_names = []
            location_name = ""
            
            # Determine which alert type we're dealing with based on interlock name
            is_rosov_alert = (interlock_name == ROSOV_INTERLOCK)
            is_dbbv_alert = (interlock_name == DBBV_INTERLOCK)
            
            # Step 1: Determine which interlock we're processing and poll for required alerts
            alerts_found = False
            attempt_count = 0
            
            fail_status_interlock = ESD_ROSOV_FAIL if is_rosov_alert else ESD_MOV_FAIL
            
            while not alerts_found and attempt_count < max_attempts:
                if is_rosov_alert or is_dbbv_alert:
                    # Processing a main interlock (ROSOV or DBBV)
                    # Query for related failure status
                    esd_close_data = await self._query_esd_alerts(
                        sap_id, 
                        fail_status_interlock, 
                        time_window
                    )
                    
                    if esd_close_data:
                        alerts_found = True
                        logger.info(f"Found relevant alerts for {fail_status_interlock} on attempt {attempt_count+1}")
                        # Process the found alerts
                        for alert in esd_close_data:
                            esd_device_name = alert.get('tas_device_name', '')
                            if esd_device_name:
                                esd_device_names.append(esd_device_name)
                                # # Update alert history for this device
                                # await self._update_alert_history(
                                #     bu=bu, 
                                #     sap_id=sap_id, 
                                #     device_name=esd_device_name,
                                #     interlock_name=interlock_name,
                                #     fail_status_interlock=fail_status_interlock
                                # )
                        if esd_close_data:
                            location_name = esd_close_data[0].get("location_name", "")
                
                if not alerts_found:
                    attempt_count += 1
                    logger.info(f"Attempt {attempt_count}/{max_attempts}: Waiting for alerts to arrive...")
                    await asyncio.sleep(poll_interval)
            
            # Check maintenance alerts if no ESD device names found
            if not esd_device_names:
                maint_alerts = await self._query_maintenance_alerts(sap_id)
                device_names = {a.get("tas_device_name") for a in maint_alerts.get("data", []) if a.get("tas_device_name")}
                maintenance_alert_count = len(device_names)
            else:
                for device in esd_device_names:
                    fault_alerts = await self._query_fault_alerts(sap_id)
                    unique_devices = {a.get("tas_device_name") for a in fault_alerts.get("data", []) if a.get("tas_device_name")}
                    fault_alert_count += len(unique_devices)

            # Query for relevant alerts based on the interlock type
            if is_rosov_alert:
                # Query for ROSOV-related alerts
                esd_status_data = await self._query_esd_status_alerts(sap_id, ESD_ROSOV_CLOSE, time_window)
                esd_close_status_count = len(esd_status_data.get("data", []))
                
                rosov_pl_data = await self._query_pl_mode_alerts(sap_id, ROSOV_PL_MODE, time_window)
                rosov_pl_close_count = len(rosov_pl_data.get("data", []))
            
            if is_dbbv_alert:
                # Query for DBBV/MOV-related alerts
                esd_mov_status_data = await self._query_esd_status_alerts(sap_id, ESD_MOV_CLOSE, time_window)
                esd_mov_close_status_count = len(esd_mov_status_data.get("data", []))
                
                mov_pl_data = await self._query_pl_mode_alerts(sap_id, MOV_PL_MODE, time_window)
                mov_pl_close_count = len(mov_pl_data.get("data", []))
                    
            # Architecture total tank count
            total_tank_count = await self._get_total_tank_count(sap_id)

            # Calculate totals based on which interlock we're dealing with
            if is_rosov_alert and (maintenance_alert_count > 0 or fault_alert_count > 0):
                # Decision branch for ROSOV alerts
                if maintenance_alert_count > 0:
                    total_count = maintenance_alert_count + rosov_pl_close_count + esd_close_status_count
                    path = "maintenance"
                else:
                    total_count = fault_alert_count + rosov_pl_close_count + esd_close_status_count
                    path = "fault"

                logger.info(f"ROSOV Path: {path}, Total count: {total_count}, Tank count: {total_tank_count}")

                if total_count == total_tank_count:
                    return await self._create_rosov_alert(bu, sap_id, location_name, total_count)
            
            if is_dbbv_alert and (maintenance_alert_count > 0 or fault_alert_count > 0):
                # Decision branch for DBBV/MOV alerts
                if maintenance_alert_count > 0:
                    total_count = maintenance_alert_count + mov_pl_close_count + esd_mov_close_status_count
                    path = "maintenance"
                else:
                    total_count = fault_alert_count + mov_pl_close_count + esd_mov_close_status_count
                    path = "fault"

                logger.info(f"DBBV Path: {path}, Total count: {total_count}, Tank count: {total_tank_count}")

                if total_count == total_tank_count:
                    return await self._create_dbbv_alert(bu, sap_id, location_name, total_count)
            
            # 🔁 NEW: If no fault or maintenance, update alert history for collected ESD devices
            if maintenance_alert_count == 0 and fault_alert_count == 0:
                if is_rosov_alert and esd_device_names:
                    for dev_name in esd_device_names:
                        await self._update_alert_history(
                            bu=bu,
                            sap_id=sap_id,
                            device_name=dev_name,
                            interlock_name=ROSOV_INTERLOCK,
                            fail_status_interlock=ESD_ROSOV_FAIL
                        )
                elif is_dbbv_alert and esd_device_names:
                    for dev_name in esd_device_names:
                        await self._update_alert_history(
                            bu=bu,
                            sap_id=sap_id,
                            device_name=dev_name,
                            interlock_name=DBBV_INTERLOCK,
                            fail_status_interlock=ESD_MOV_FAIL
                        )
                        
            return True, {"status": "counts don't match", "rosov_total": (maintenance_alert_count + rosov_pl_close_count + esd_close_status_count), "dbbv_total": (maintenance_alert_count + mov_pl_close_count + esd_mov_close_status_count), "tank_count": total_tank_count}
        
        except Exception as e:
            logger.info(traceback.format_exc())
            logger.error(traceback.format_exc())
            return False, {"status": str(e)}
    
    async def _query_esd_alerts(self, sap_id, interlock_name, time_window):
        """Query for ESD alerts based on interlock name"""
        esd_query = (
            f"bu = 'TAS' AND sap_id = '{sap_id}' AND alert_section = 'TAS' "
            f"AND interlock_name = '{interlock_name}' "
            f"AND alert_status != 'Close' "
            f"AND created_at >= NOW() - INTERVAL '{time_window} minutes'"
        )
        esd_params = urdhva_base.queryparams.QueryParams()
        esd_params.q = esd_query
        logger.info(f"Query for {interlock_name}: {esd_params.q}")
        esd_params.fields = ["tas_device_name", "location_name"]

        esd_close_alerts = await hpcl_ceg_model.Alerts.get_all(esd_params, resp_type='plain')
        return esd_close_alerts.get("data", [])
    
    async def _query_maintenance_alerts(self, sap_id):
        """Query for maintenance alerts"""
        maint_query = (
            f"bu = 'TAS' AND sap_id = '{sap_id}' AND alert_section = 'TAS' "
            f"AND interlock_name LIKE '%Maintenance%' AND alert_status != 'Close'"
        )
        maint_params = urdhva_base.queryparams.QueryParams()
        maint_params.q = maint_query
        maint_params.fields = ["tas_device_name"]
        logger.info(f"Maintenance query: {maint_params.q}")
        
        maint_alerts = await hpcl_ceg_model.Alerts.get_all(maint_params, resp_type='plain')
        logger.info(f"Maintenance alerts: {maint_alerts}")
        return maint_alerts
    
    async def _query_fault_alerts(self, sap_id):
        """Query for fault alerts"""
        fault_query = (
            f"bu = 'TAS' AND sap_id = '{sap_id}' AND alert_section = 'TAS' "
            f"AND sop_id = 'SOP018' AND alert_status != 'Close'"
        )
        fault_params = urdhva_base.queryparams.QueryParams()
        fault_params.q = fault_query
        logger.info(f"Fault query: {fault_params.q}")
        fault_params.fields = ["tas_device_name"]

        fault_alerts = await hpcl_ceg_model.Alerts.get_all(fault_params, resp_type='plain')
        logger.info(f"Fault alerts: {fault_alerts}")
        return fault_alerts
    
    async def _query_esd_status_alerts(self, sap_id, interlock_name, time_window):
        """Query for ESD status alerts"""
        esd_status_query = (
            f"bu = 'TAS' AND sap_id = '{sap_id}' AND alert_section = 'TAS' AND "
            f"interlock_name = '{interlock_name}' AND alert_status != 'Open' AND created_at >= NOW() - INTERVAL '{time_window} minutes'"
        )
        esd_status_params = urdhva_base.queryparams.QueryParams()
        esd_status_params.q = esd_status_query
        logger.info(f"ESD status query: {esd_status_params.q}")
        
        esd_status_data = await hpcl_ceg_model.Alerts.get_all(esd_status_params, resp_type='plain')
        logger.info(f"ESD status data: {esd_status_data}")
        return esd_status_data
    
    async def _query_pl_mode_alerts(self, sap_id, interlock_name, time_window):
        """Query for PL mode alerts"""
        pl_query = (
            f"bu = 'TAS' AND sap_id = '{sap_id}' AND alert_section = 'TAS' AND "
            f"interlock_name = '{interlock_name}' AND alert_status != 'Open' AND created_at >= NOW() - INTERVAL '{time_window} minutes'"
        )
        pl_params = urdhva_base.queryparams.QueryParams()
        pl_params.q = pl_query
        logger.info(f"PL mode query: {pl_params.q}")
        
        pl_data = await hpcl_ceg_model.Alerts.get_all(pl_params, resp_type='plain')
        logger.info(f"PL mode data: {pl_data}")
        return pl_data
    
    async def _get_total_tank_count(self, sap_id):
        """Get total tank count from architecture data"""
        arch_query = f"sap_id = '{sap_id}'"
        arch_params = urdhva_base.queryparams.QueryParams()
        arch_params.q = arch_query
        logger.info(f"Architecture query: {arch_params.q}")
        arch_params.fields = ["total_tank_count"]

        arch_data = await hpcl_ceg_model.ArchitectureData.get_all(arch_params, resp_type='plain')
        logger.info(f"Architecture data: {arch_data}")
        tank_counts = {item.get("total_tank_count", 0) for item in arch_data.get("data", [])}
        total_tank_count = max(tank_counts) if tank_counts else 0
        logger.info(f"Total tank count: {total_tank_count}")
        return total_tank_count
    
    async def _create_rosov_alert(self, bu, sap_id, location_name, total_count):
        """Create ROSOV alert"""
        alert_message = "All ROSOVs closed(Except PL Receipt)"
        alert_data = {
            "bu": bu,
            "sap_id": sap_id,
            "location_name": location_name,
            "sop_id": "SOP02A",
            "interlock_name": alert_message,
            "alert_status": "Open",
            "alert_state": "InProgress",
            "severity": "CRITICAL",
            "alert_section": "TAS",
            "device_name": "",
            "return_data": True
        }
        status, created_alert = await alert_create.AlertFactory().create_alert(alert_data=alert_data)
        logger.info("created_alert ROSOV ---> ", created_alert)
        if created_alert and isinstance(created_alert, dict):
            alert_data["unique_id"] = created_alert.get("unique_id")
            alert_data["id"] = created_alert.get("id")
            await alert_close.close_tas_workflow(alert_data=alert_data, message_type="interLockOk")
            return True, {
                "status": "success",
                "message": alert_message,
                "count": total_count,
                "alert_id": alert_data["id"],
                "unique_id": alert_data["unique_id"],
                "alert_type": "ROSOV"
            }
        return True, {"status": "ROSOV alert creation failed"}
    
    async def _create_dbbv_alert(self, bu, sap_id, location_name, total_count):
        """Create DBBV alert"""
        alert_message = "All DBBVs Closed(Except PL Receipt)"
        alert_data = {
            "bu": bu,
            "sap_id": sap_id,
            "location_name": location_name,
            "sop_id": "SOP02A",
            "interlock_name": alert_message,
            "alert_status": "Open",
            "alert_state": "InProgress",
            "severity": "CRITICAL",
            "alert_section": "TAS",
            "device_name": "",
            "return_data": True
        }
        status, created_alert = await alert_create.AlertFactory().create_alert(alert_data=alert_data)
        logger.info("created_alert DBBV ---> ", created_alert)
        if created_alert and isinstance(created_alert, dict):
            alert_data["unique_id"] = created_alert.get("unique_id")
            alert_data["id"] = created_alert.get("id")
            await alert_close.close_tas_workflow(alert_data=alert_data)
            return True, {
                "status": "success",
                "message": alert_message,
                "count": total_count,
                "alert_id": alert_data["id"],
                "unique_id": alert_data["unique_id"],
                "alert_type": "DBBV"
            }
        return True, {"status": "DBBV alert creation failed"}

    async def _update_alert_history(self, bu, sap_id, device_name, interlock_name, fail_status_interlock):
        """Update alert history for a device when no maintenance or fault alerts are found"""
        try:
            # Query for the specific alert to update
            query = (
                f"bu = 'TAS' AND sap_id = '{sap_id}' AND alert_section = 'TAS' AND "
                f"interlock_name = '{interlock_name}' "
                f"AND alert_status != 'Close'"
            )
            params = urdhva_base.queryparams.QueryParams()
            params.q = query
            params.fields = ["id", "alert_history"]
            logger.info(f"[UpdateHistory] Query: {params.q}")
            
            alerts = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
            processed_time = datetime.datetime.utcnow()

            for alert in alerts.get("data", []):
                alert_id = alert.get("id")
                existing_history = alert.get("alert_history", []) or []
                last_processed_time = processed_time.isoformat()

                # Try to get last InterlockCreated time if exists
                for entry in existing_history:
                    if entry.get("action_type") == "InterlockCreated" and entry.get("processed_time"):
                        last_processed_time = entry["processed_time"]
                        break

                # Avoid adding duplicate ESDFailure entries
                already_exists = any(
                    h.get("action_type") == "ESDFailure" and device_name in h.get("action_msg", "")
                    for h in existing_history
                )

                if not already_exists:
                    device_type = "ROSOV" if "ROSOV" in fail_status_interlock else "MOV"
                    new_entry = {
                        "processed_time": processed_time.isoformat(),
                        "allocated_time": last_processed_time,
                        "action_msg": f"ESD {device_type} failure alert for device {device_name}",
                        "action_type": "ESDFailure"
                    }
                    updated_history = existing_history + [new_entry]
                    print(f"[UpdateHistory] Updating alert ID {alert_id} with history: {new_entry}")
                    
                    alert_obj = hpcl_ceg_model.Alerts(id=alert_id, alert_history=updated_history)
                    await alert_obj.modify()

            return True
        except Exception as e:
            logger.info(traceback.format_exc())
            logger.error(f"Error in _update_alert_history: {str(e)}")
            return False

        except Exception as e:
            logger.info(traceback.format_exc())
            logger.error(f"Error updating fault history: {str(e)}")
            return False