import urdhva_base
import asyncio
import traceback
import datetime
import charts_actions
import dashboard_studio_model
import utilities.connection_mapping as connection_mapping
import orchestrator.sync_services.vts.vts_ongoing_trips as vts_ongoing_trips
import hpcl_ceg_enum
import orchestrator.dbconnector.widget_actions.vts_analytics as vts_analytics
import polars as pl
import orchestrator.dbconnector.credential_loader as credential_loader
import psycopg2
import psycopg2.extras


logger = urdhva_base.Logger.getInstance("vts_live_trips_check")

class VTSTripSyncService:
    CHUNK_SIZE = 1000
    BULK_UPDATE_BATCH_SIZE = 1000
    
    @staticmethod
    async def get_completed_invoices_from_vts(invoice_list):
        """Get completed invoices from VTS COMPLETED_TRIP table"""
        completed_set = set()
        
        try:
            conn = vts_ongoing_trips.get_db_connection()
            cursor = conn.cursor()
            
            for i in range(0, len(invoice_list), VTSTripSyncService.CHUNK_SIZE):
                chunk = invoice_list[i:i + VTSTripSyncService.CHUNK_SIZE]
                invoices_str = "', '".join(chunk)
                
                cursor.execute(f"""
                    SELECT DISTINCT CHALLAN_NO
                    FROM COMPLETED_TRIP
                    WHERE CHALLAN_NO IN ('{invoices_str}')
                """)
                
                completed_set.update(
                    str(row[0]).strip().replace(" ", "") 
                    for row in cursor.fetchall() 
                    if row[0]
                )
                        
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"VTS query error: {str(e)}")
            
        return completed_set
    
    @staticmethod
    async def get_completed_invoices_from_ims(base_invoice_list, ims_function):
        """Get completed invoices from IMS AUTO_DC_REQUESTS table"""
        completed_set = set()
        
        try:
            for i in range(0, len(base_invoice_list), VTSTripSyncService.CHUNK_SIZE):
                chunk = base_invoice_list[i:i + VTSTripSyncService.CHUNK_SIZE]
                invoices_str = "', '".join(chunk)
                
                ims_rows = await ims_function(query=f"""
                    SELECT DISTINCT INVOICE_NO
                    FROM "IMS_SAP"."AUTO_DC_REQUESTS"
                    WHERE "INVOICE_NO" IN ('{invoices_str}')
                """)
                
                if ims_rows:
                    completed_set.update(
                        str(row["INVOICE_NO"]).strip().replace(" ", "")
                        for row in ims_rows
                        if row.get("INVOICE_NO")
                    )
                    
        except Exception as e:
            logger.error(f"IMS query error: {str(e)}")
            
        return completed_set
    
    @staticmethod
    async def bulk_update_trips(trips_data):
        """
        Bulk update trips using direct database connection for faster updates
        """
        update_count = 0
        failed_count = 0
        conn = None
        cursor = None
        
        try:
            # Get database credentials
            creds = credential_loader.get_credentials('APP_DB')
            params = {
                "host": creds["host"],
                "database": creds["database"],
                "user": creds["user"],
                "password": creds["password"],
                "port": creds["port"]
            }
            
            # Establish connection
            conn = psycopg2.connect(**params)
            cursor = conn.cursor()
            
            # Prepare update query
            update_query = """
                UPDATE vts_ongoing_trips
                SET trip_status = %s,
                    vts_status = %s,
                    ims_status = %s,
                    trip_completed_time = %s
                WHERE id = %s
            """
            
            # Process in batches
            for i in range(0, len(trips_data), VTSTripSyncService.BULK_UPDATE_BATCH_SIZE):
                batch = trips_data[i:i + VTSTripSyncService.BULK_UPDATE_BATCH_SIZE]
                
                # Prepare batch data
                batch_values = [
                    (
                        record['trip_status'],
                        record['vts_status'],
                        record['ims_status'],
                        record['trip_completed_time'],
                        record['id']
                    )
                    for record in batch
                ]
                
                try:
                    # Execute batch update using psycopg2.extras.execute_batch for performance
                    psycopg2.extras.execute_batch(cursor, update_query, batch_values)
                    conn.commit()
                    
                    batch_success = len(batch)
                    update_count += batch_success
                    logger.info(f"Batch {i//VTSTripSyncService.BULK_UPDATE_BATCH_SIZE + 1}: {batch_success}/{len(batch)} successful")
                    
                except Exception as e:
                    conn.rollback()
                    failed_count += len(batch)
                    logger.error(f"Batch update failed: {str(e)}")
                    logger.error(traceback.format_exc())
            
            return update_count, failed_count
            
        except Exception as e:
            logger.error(f"Bulk update error: {str(e)}")
            logger.error(traceback.format_exc())
            return update_count, failed_count
            
        finally:
            # Clean up resources
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    async def sync_trip_completion_status():
        """Main sync function"""
        try:
            logger.info(f"[{datetime.datetime.now()}] Starting sync...")
            
            vts_live_query = """
                SELECT id, invoice_no, trip_status, vts_status, ims_status
                FROM vts_ongoing_trips
                WHERE trip_status IS NULL OR trip_status = 'Live'
            """
            
            # Get ongoing trips
            df = await vts_analytics.VTSAnalyticsActions.execute_query(vts_live_query, engine='polars')
            
            if df.is_empty():
                return {"status": True, "message": "No trips to sync", "updated": 0}
            
            logger.info(f"Checking {df.height} trips")
            
            # Normalize and extract base invoice numbers
            df = df.with_columns([
                pl.col("invoice_no").str.strip_chars().str.replace_all(r"\s+", "").alias("invoice_clean"),
                pl.col("invoice_no").str.strip_chars().str.replace_all(r"\s+", "").str.split("-").list.first().alias("base_invoice")
            ])
            
            invoice_list = df.select("invoice_clean").drop_nulls().unique().to_series().to_list()
            base_invoice_list = df.select("base_invoice").drop_nulls().unique().to_series().to_list()
            
            if not invoice_list:
                return {"status": True, "message": "No valid invoices", "updated": 0}
            
            # Get IMS function
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.connection_id = connection_mapping.connection_mapping.get("ims", "1")
            dashboard_studio_model.Charts_Connection_Vault_RoutingParams.action = 'execute_query'
            ims_function = await charts_actions.charts_connection_vault_routing(dashboard_studio_model.Charts_Connection_Vault_RoutingParams)
            
            # Fetch from both tables in parallel
            vts_set, ims_set = await asyncio.gather(
                VTSTripSyncService.get_completed_invoices_from_vts(invoice_list),
                VTSTripSyncService.get_completed_invoices_from_ims(base_invoice_list, ims_function)
            )
            
            logger.info(f"VTS completed: {len(vts_set)}, IMS completed: {len(ims_set)}")
            
            # Mark which trips are completed
            df = df.with_columns([
                pl.col("invoice_clean").is_in(list(vts_set)).alias("in_vts"),
                pl.col("base_invoice").is_in(list(ims_set)).alias("in_ims")
            ])
            
            # Prepare bulk update data - now updating ALL trips
            current_time = datetime.datetime.now()
            trips_data = []
            
            for row in df.iter_rows(named=True):
                in_vts = row['in_vts']
                in_ims = row['in_ims']
                
                # If invoice is in at least one table, mark as completed
                # If not in both tables, mark as ongoing
                if in_vts or in_ims:
                    trip_status = hpcl_ceg_enum.VtsLive.TripCompleted.value
                    trip_completed_time = current_time
                else:
                    trip_status = hpcl_ceg_enum.VtsLive.TripOngoing.value
                    trip_completed_time = None
                
                trips_data.append({
                    'id': row['id'],
                    'trip_status': trip_status,
                    'vts_status': (hpcl_ceg_enum.VtsLive.TripCompleted if in_vts else hpcl_ceg_enum.VtsLive.TripOngoing).value,
                    'ims_status': (hpcl_ceg_enum.VtsLive.TripCompleted if in_ims else hpcl_ceg_enum.VtsLive.TripOngoing).value,
                    'trip_completed_time': trip_completed_time
                })
            
            if not trips_data:
                logger.info("No trips to update")
                return {"status": True, "message": "No updates needed", "updated": 0}
            
            logger.info(f"Preparing to update {len(trips_data)} trips")
            
            # Perform bulk update
            update_count, failed_count = await VTSTripSyncService.bulk_update_trips(trips_data)
            
            logger.info(f"[{datetime.datetime.now()}] Sync completed: {update_count} updated, {failed_count} failed")
            
            return {
                "status": True,
                "message": "Sync completed",
                "updated": update_count,
                "failed": failed_count,
                "total_checked": df.height
            }
            
        except Exception as e:
            logger.error(f"Sync error: {str(e)}")
            logger.error(traceback.format_exc())
            return {"status": False, "message": str(e), "updated": 0}


async def main():
    result = await VTSTripSyncService.sync_trip_completion_status()
    logger.info(f"Final Result: {result}")
    return result


if __name__ == "__main__":
    asyncio.run(main())