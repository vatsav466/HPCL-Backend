import urdhva_base
import asyncio
import datetime
import threading
import time
import traceback
from typing import Dict, List, Optional, Set, Any
import hpcl_ceg_enum
import hpcl_ceg_model
import orchestrator.alerting.alert_helper as alert_helper
import utilities.helpers as helpers
#import pyodbc
import orchestrator.dbconnector.credential_loader as credential_loader
import pandas as pd

logger = urdhva_base.logger.Logger.getInstance('vts_device_status_monitor_log')


class VTSDeviceStatusMonitor:
    """
    VTS Device Status Monitor.
    
    A monitoring service that checks VTS device working status every 15 minutes
    and manages alerts based on device status. Creates alerts when devices are
    not working and closes alerts when devices are working again.
    
    Attributes:
        monitoring_active (bool): Flag indicating if monitoring is currently active.
        monitoring_thread (Optional[threading.Thread]): Background monitoring thread.
        last_checked_devices (Set[str]): Set of device IDs checked in last run.
        last_check_timestamp (Optional[datetime.datetime]): Timestamp of last check.
    """
    
    def __init__(self) -> None:
        """
        Initialize the VTS Device Status Monitor.
        
        Sets up the monitoring state variables and prepares the monitor
        for operation.
        """
        self.monitoring_active: bool = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.last_checked_devices: Set[str] = set()
        self.last_check_timestamp: Optional[datetime.datetime] = None

    # async def vtstrackdb_connection(self):
    #     try:
    #         creds = credential_loader.get_credentials('VTS_TRACK_DB')
    #         conn = pyodbc.connect(
    #         'DRIVER={ODBC Driver 18 for SQL Server};'
    #         f'Server={creds['host']},{creds['port']};'
    #         f'Database={creds['database']};'
    #         f'UID={creds['user']};'
    #         f'PWD={creds['password']};'
    #         'TrustServerCertificate=yes;MARS_Connection=yes;',
    #         )
    #         return conn
    #     except Exception as e:
    #         print(f"DB connection failed: {e}")
    #         return None

    # def execute_vtstruckdb_query(self, conn, query):
    #     try:
    #         cursor = conn.cursor()
    #         cursor.execute(query)
    #         rows = cursor.fetchall()
    #         columns = [col[0].lower() for col in cursor.description]
            
    #         # Debug logging
    #         logger.info(f"Query returned {len(rows)} rows")
    #         logger.info(f"Column names: {columns}")
    #         if rows:
    #             logger.info(f"First row length: {len(rows[0])}")
    #             logger.info(f"First row sample: {rows[0]}")
            
    #         df = pd.DataFrame.from_records(rows, columns=columns)
    #         cursor.close()
    #         return df
    #     except pyodbc.Error as e:
    #         logger.error(f"Query execution failed: {e}")
    #         return None
    #     except Exception as e:
    #         logger.error(f"DataFrame creation failed: {e}")
    #         logger.error(f"Columns: {columns}, Row count: {len(rows) if rows else 0}")
    #         return None
    
    async def get_device_status_from_mssql(self) -> List[Dict[str, Any]]:
        """
        Retrieve device status data from MS SQL vts_device_status table.
        
        Returns:
            List[Dict[str, Any]]: List of device status records with proper data types
        """
        try:
            # connection = await self.vtstrackdb_connection()
            # if not connection:
            #     logger.error("Failed to connect to MS SQL database")
            #     return []
            # query = """SELECT UKID, TRUCK_REGNO, DEVICEWORKING, LAST_UPDT_DATE FROM VTS_DEVICE_STATUS_HIST ORDER BY LAST_UPDT_DATE DESC"""

            query = """SELECT ukid, truck_regno, deviceworking, last_updt_date FROM vts_device_status ORDER BY last_updt_date DESC"""
            result = await urdhva_base.BasePostgresModel.get_aggr_data(query)
            df = pd.DataFrame(result.get("data", []))
            

            # df = self.execute_vtstruckdb_query(connection, query)
            if df is None or df.empty:
                logger.warning("No data retrieved from MS SQL vts_device_status")
                #connection.close()
                return []
            
            
            df['truck_regno'] = df['truck_regno'].apply(lambda x: str(x).strip() if pd.notna(x) else None)
            df['deviceworking'] = df['deviceworking'].apply(lambda x: str(x).strip() if pd.notna(x) else None)
            df = df.where(pd.notna(df), None)
            
            #connection.close()
            
            # result = df.to_dict('records')
            # logger.info(f"Retrieved {len(result)} records from MS SQL vts_device_status")
            return df
            
        except Exception as e:
            logger.error(f"Error getting device status from MS SQL: {e}")
            logger.error(traceback.format_exc())
            return []
    
    async def get_truck_details_from_postgres(self) -> List[Dict[str, Any]]:
        """
        Retrieve truck details data from PostgreSQL vts_truck_details table.
        
        Returns:
        """
        try:
            query = """
                SELECT 
                    truck_regno,
                    sap_id,
                    bu
                FROM vts_truck_details
            """
            result = await urdhva_base.BasePostgresModel.get_aggr_data(query)
            truck_details = result.get("data", [])
            
            logger.info(f"Retrieved {len(truck_details)} records from PostgreSQL vts_truck_details")
            return truck_details
            
        except Exception as e:
            print(f"Error getting truck details from PostgreSQL: {e}")
            print(traceback.format_exc())
            return []
    
    async def get_device_status_data(self) -> List[Dict[str, Any]]:
        """
        Retrieve device status data from the VTS device status table.
        Joins MS SQL VTS device status with PostgreSQL truck details
        using 'truck_regno' as the common key.
        """
        try:
            # Fetch device status from MS SQL
            device_df = await self.get_device_status_from_mssql()
            if device_df.empty:
                logger.warning("No device status data retrieved from MS SQL")
                return []

            # Fetch truck details from PostgreSQL
            truck_details_data = await self.get_truck_details_from_postgres()
            if not truck_details_data:
                logger.warning("No truck details data retrieved from PostgreSQL")
                return []
                
            truck_df = pd.DataFrame(truck_details_data)
            
            # Normalize device truck_regno BEFORE filtering
            device_df['truck_regno'] = (
                device_df['truck_regno']
                .astype(str)
                .str.strip()
                .str.upper()
            )
            
            # Normalize truck truck_regno BEFORE filtering
            truck_df['truck_regno'] = (
                truck_df['truck_regno']
                .astype(str)
                .str.strip()
                .str.upper()
            )
            
            # Filter out null/empty values AFTER normalization
            device_df = device_df[device_df['truck_regno'].notna()]
            device_df = device_df[device_df['truck_regno'] != '']
            truck_df = truck_df[truck_df['truck_regno'].notna()]
            truck_df = truck_df[truck_df['truck_regno'] != '']
            
            logger.info(f"After normalization - Device records: {len(device_df)}, Truck records: {len(truck_df)}")
            
            # Debug: Show sample data
            if not device_df.empty:
                logger.info(f"Sample device truck_regno values: {device_df['truck_regno'].head(3).tolist()}")
            if not truck_df.empty:
                logger.info(f"Sample truck truck_regno values: {truck_df['truck_regno'].head(3).tolist()}")
            
            # Perform LEFT JOIN on truck_regno
            merged_df = device_df.merge(
                truck_df[['truck_regno', 'sap_id', 'bu']], 
                on='truck_regno',
                how='left'
            )
            
            # Select final columns in order
            result_df = merged_df[['ukid', 'truck_regno', 'deviceworking', 'last_updt_date', 'sap_id', 'bu']]

            print("result_df--->", result_df.head(5))
            
            # Replace NaN/None values
            result_df = result_df.where(pd.notna(result_df), None)
            
            # Logging and statistics
            matched_count = len(result_df[result_df['sap_id'].notna()])
            unmatched_count = len(result_df) - matched_count
            
            logger.info(
                f"Device status merge complete: {len(result_df)} total records, "
                f"{matched_count} matched with truck details, {unmatched_count} unmatched"
            )
            
            # Debug: Show which truck_regno values didn't match
            if unmatched_count > 0:
                unmatched_regonos = result_df[result_df['sap_id'].isna()]['truck_regno'].unique()[:5]
                logger.warning(f"Sample unmatched truck_regno values: {unmatched_regonos.tolist()}")
            
            return result_df.to_dict('records')

        except Exception as e:
            logger.error(f"Error getting device status data: {e}")
            logger.error(traceback.format_exc())
            return []

    
    async def check_existing_alert(self, truck_regno: str) -> Dict[str, Any]:
        """
        Check for existing open alerts for a specific truck.
        
        Queries the alerts table to find any open VTS alerts for the given
        truck registration number. Returns the most recent open alert if found.
        
        Args:
            truck_regno (str): Vehicle registration number to check alerts for.
            
        Returns:
            Dict[str, Any]: Alert data containing:
                - id: Alert identifier
                - alert_status: Current alert status
                - alert_state: Current alert state
                - unique_id: Unique alert identifier
            Returns empty dict if no open alert found.
            
        Raises:
            Exception: Logs error and returns empty dict if database query fails.
        """
        try:
            query = """
                SELECT id, alert_status, alert_state, unique_id
                FROM alerts 
                WHERE vehicle_number = %s 
                AND alert_status = 'Open'
                AND alert_section = 'VTS'
                ORDER BY created_at DESC
                LIMIT 1
            """
            result = await hpcl_ceg_model.BasePostgresModel.get_aggr_data(
                query, params=[truck_regno]
            )
            return result.get("data", [{}])[0] if result.get("data") else {}
        except Exception as e:
            logger.error(
                f"Error checking existing alert for truck {truck_regno}: {e}"
            )
            return {}
    
    async def create_device_status_alert(self, device_data: Dict[str, Any]) -> bool:
        """
        Create a device status alert when device is not working.
        
        Creates a new alert in the system when a VTS device is detected as
        not working. The alert includes device details, location information,
        and proper categorization for tracking and resolution.
        
        Args:
            device_data (Dict[str, Any]): Device information containing:
                - ukid: Unique device identifier
                - truck_regno: Vehicle registration number
                - bu: Business unit code
                - sap_id: SAP system identifier
                
        Returns:
            bool: True if alert created successfully, False otherwise.
            
        Raises:
            Exception: Logs error and returns False if alert creation fails.
        """
        try:
            bu = device_data.get('bu', '')
            sap_id = device_data.get('sap_id', '')
            sop_id = "SOP00N"
            
            # Get location details
            status, location_details = await helpers.get_location_details(bu, sap_id)
            if not status:
                location_details = {'name': f"VTS Location {sap_id}"}
            
            # Prepare base data
            base_data = {
                key: location_details.get(key, '') for key in [
                    'state', 'city', 'zone', 'region', 'district',
                    'terminal_plant_id', 'terminal_plant_name', 'sales_area',
                    'category'
                ]
            }
            base_data.update({
                'device_id': str(device_data.get('ukid', '')),
                'device_type': 'VTS_DEVICE',
                'device_name': f"VTS Device {device_data.get('truck_regno', '')}",
                'sop_id': sop_id,
                'sap_id': sap_id,
                'bu': bu,
                'location_name': location_details.get('name', '')
            })
            
            print("data--->", sap_id, sop_id)
            # Get unique alert ID
            unique_id = await alert_helper.get_alert_unique_id('VTS', sap_id, sop_id)

            print("base data --->", base_data)
            print("unique_id --->", unique_id)
            
            # # Create alert
            # alert_resp = await hpcl_ceg_model.AlertsCreate(**{
            #     **base_data,
            #     'severity': 'Medium',
            #     'bu': bu,
            #     'alert_category': None,
            #     'alert_status': hpcl_ceg_enum.AlertStatus.Open,
            #     'alert_state': hpcl_ceg_enum.AlertState.InProgress,
            #     'unique_id': unique_id,
            #     'alert_section': 'VTS',
            #     'external_id': None,
            #     'interlock_name': None,
            #     'interlock_id': '',
            #     'vehicle_number': device_data.get('truck_regno', ''),
            #     'violation_type': 'NRD',
            #     'clear_count': False,
            #     'alert_history': [{
            #         "action_msg": (
            #             f"VTS Device of truck: '{device_data.get('truck_regno', '')}' is not reporting"
            #         ),
            #         "action_type": "Created",
            #         "alert_status": "Open",
            #         "allocated_time": urdhva_base.utilities.get_present_time().replace(
            #             tzinfo=None
            #         ).isoformat(),
            #         "processed_time": urdhva_base.utilities.get_present_time().replace(
            #             tzinfo=None
            #         ).isoformat()
            #     }],
            #     'device_msg': (
            #         f"VTS Device not working for truck '{device_data.get('truck_regno', '')}' "
            #     ),
            #     'equipment_type': 'VTS_DEVICE',
            #     'equipment_name': f"VTS Device {device_data.get('truck_regno', '')}",
            #     'sensor_id': str(device_data.get('ukid', '')),
            #     'tas_device_name': f"VTS Device {device_data.get('truck_regno', '')}",
            #     'alert_message': (
            #         f"Action required on the VTS device of truck '{device_data.get('truck_regno', '')}'."
            #     ),
            #     'last_sms_to': [],
            #     'last_mailed_to': [],
            #     'last_escalated_to': [],
            #     'last_notified_to': [],
            #     'assigned_to': '',
            #     'assigned_to_role': '',
            #     'assigned_users': [],
            #     'assigned_user_roles': [],
            #     'indent_status': hpcl_ceg_enum.IndentStatus.Pending,
            #     'dealer_id': '',
            #     'product_code': '',
            #     'indent_no': '',
            #     'workflow_datetime': urdhva_base.utilities.get_present_time().replace(
            #         tzinfo=None
            #     ).isoformat(),
            #     'indent_raised_date': None,
            #     'vendor_alert_id': f"VTS_DEVICE_{device_data.get('ukid', '')}",
            #     'raw_data': {}
            # }).create()
            
            # if alert_resp:
            #     logger.info(
            #         f"Successfully created alert for truck "
            #         f"{device_data.get('truck_regno')} - VTS device not working"
            #     )
            #     return True
            # else:
            #     logger.error(
            #         f"Failed to create alert for truck "
            #         f"{device_data.get('truck_regno')} - VTS device not working"
            #     )
            #     return False
                
        except Exception as e:
            logger.error(f"Failed to create device status alert: {e}")
            return False
    
    async def close_device_status_alert(self, alert_id: int) -> bool:
        """
        Close a device status alert when device is working again.
        
        Updates an existing alert to closed status when the associated VTS
        device is detected as working properly. Adds closure information
        to the alert history for audit purposes.
        
        Args:
            alert_id (int): ID of the alert to close.
            
        Returns:
            bool: True if alert closed successfully, False otherwise.
            
        Raises:
            Exception: Logs error and returns False if alert closure fails.
        """
        try:
            # Get the alert data
            alert_data = await hpcl_ceg_model.Alerts.get(alert_id)
            if not alert_data:
                logger.warning(f"Alert with ID {alert_id} not found")
                return False
            
            # Convert to dict if needed
            if not isinstance(alert_data, dict):
                alert_data = alert_data.__dict__
            
            # Remove SQLAlchemy instance state if present
            if "_sa_instance_state" in alert_data.keys():
                del alert_data["_sa_instance_state"]
            
            # Update alert status to closed
            alert_data['alert_status'] = hpcl_ceg_enum.AlertStatus.Close.value
            alert_data['alert_state'] = hpcl_ceg_enum.AlertState.Resolved.value
            alert_data['closed_at'] = datetime.datetime.now()
            
            # Add closure to alert history
            if not alert_data.get('alert_history'):
                alert_data['alert_history'] = []
            
            alert_data['alert_history'].append({
                "action_msg": "Device is working again - alert closed",
                "action_type": "Closed",
                "alert_status": "Close",
                "allocated_time": urdhva_base.utilities.get_present_time().replace(
                    tzinfo=None
                ).isoformat(),
                "processed_time": urdhva_base.utilities.get_present_time().replace(
                    tzinfo=None
                ).isoformat()
            })
            
            # Update the alert
            data_obj = hpcl_ceg_model.Alerts(**alert_data)
            await data_obj.modify()
            
            logger.info(
                f"Successfully closed alert ID {alert_id} - VTS device is working again"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to close alert {alert_id}: {e}")
            return False
    
    async def check_device_status(self) -> int:
        """
        Check device status and manage alerts based on device working status.
        
        Performs the main monitoring logic by:
        1. Retrieving all device status data from the database
        2. Checking each device's working status
        3. Creating alerts for non-working devices without existing alerts
        4. Closing alerts for devices that are working again
        5. Logging comprehensive summary statistics
        
        Returns:
            int: Number of devices currently not working.
            
        Raises:
            Exception: Logs error and returns 0 if monitoring fails.
        """
        try:
            current_time = datetime.datetime.now()
            logger.info(
                f"Starting device status check at "
                f"{current_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Get all device status data
            device_data = await self.get_device_status_data()
            
            if not device_data:
                logger.warning("No device data found")
                return 0
            
            # Process each device
            alerts_created = 0
            alerts_closed = 0
            
            for device in device_data:
                truck_regno = device.get('truck_regno')
                deviceworking = device.get('deviceworking')
                ukid = device.get('ukid')
                
                if not truck_regno or not ukid:
                    continue
                
                # Check if there's an existing open alert for this truck
                existing_alert = await self.check_existing_alert(truck_regno)
                
                if deviceworking == 'N' and not existing_alert:
                    # Device is not working and no open alert exists - create new alert
                    logger.warning(
                        f"VTS device is not working for truck {truck_regno} "
                        f"(Device ID: {ukid})"
                    )
                    if await self.create_device_status_alert(device):
                        alerts_created += 1
                        
                elif deviceworking == 'Y' and existing_alert:
                    # Device is working but alert is still open - close the alert
                    logger.info(
                        f"VTS device is now working for truck {truck_regno} "
                        f"(Device ID: {ukid})"
                    )
                    print("existing_alert --->", existing_alert)
                    # if await self.close_device_status_alert(
                    #     existing_alert.get('id')
                    # ):
                    #     alerts_closed += 1
            
            # Log summary
            total_devices = len(device_data)
            not_working_count = len([
                d for d in device_data if d.get('deviceworking') == 'N'
            ])
            working_count = len([
                d for d in device_data if d.get('deviceworking') == 'Y'
            ])
            
            logger.info("Device Status Summary:")
            logger.info(f"Total devices monitored: {total_devices}")
            logger.info(f"Devices working properly: {working_count}")
            logger.info(f"Devices not working: {not_working_count}")
            logger.info(f"New alerts created: {alerts_created}")
            logger.info(f"Existing alerts closed: {alerts_closed}")
            
            if not_working_count == 0:
                logger.info("All VTS devices are functioning normally")
            elif alerts_created > 0 or alerts_closed > 0:
                logger.info(
                    f"Alert processing completed: {alerts_created} new alerts "
                    f"created, {alerts_closed} alerts resolved"
                )

            return not_working_count
            
        except Exception as e:
            logger.error(f"Device status check failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return 0
    
    async def run_monitoring_check(self) -> int:
        """
        Run a single monitoring check.
        
        Performs one complete check of VTS device status and manages alerts.
        This method is designed to be called by cron jobs or other scheduled
        execution mechanisms.
        
        Returns:
            int: Number of devices currently not working.
            
        Raises:
            Exception: Logs error and returns 0 if monitoring fails.
        """
        logger.info("Starting VTS device status monitoring check")
        
        try:
            result = await self.check_device_status()
            logger.info("VTS device status monitoring check completed")
            return result
        except Exception as e:
            logger.error(f"VTS device status monitoring check failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return 0

async def main() -> None:
    """
    Main function to run a single VTS device status check.
    
    Performs one complete check of VTS device status and manages alerts.
    This function is designed to be called by cron jobs or other scheduled
    execution mechanisms.
    
    The function runs once and exits, making it suitable for cron job execution.
    """
    print("Starting VTS Device Status Monitor Check")
    print("Checking device working status and managing alerts")
    print("Logs will be saved to vts_device_status_monitor.log")
    print("=" * 60)
    
    # Create monitor instance
    monitor = VTSDeviceStatusMonitor()
    
    try:
        # Run single monitoring check
        not_working_count = await monitor.run_monitoring_check()
        
        print(f"Monitoring check completed. Devices not working: {not_working_count}")
        
    except Exception as e:
        logger.error(f"Fatal error in VTS device status monitor: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"Error occurred during monitoring check: {e}")


if __name__ == "__main__":
    asyncio.run(main())
