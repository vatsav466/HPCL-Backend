from orchestrator.sync_services.vts import vts_ongoing_trips
import urdhva_base
import asyncio
import traceback
import datetime
import charts_actions
import dashboard_studio_model
import utilities.connection_mapping as connection_mapping
import hpcl_ceg_enum
import hpcl_ceg_model
import orchestrator.dbconnector.widget_actions.vts_analytics as vts_analytics
import polars as pl


logger = urdhva_base.Logger.getInstance("vts_live_trips_check")

class VTSTripSyncService:
    CHUNK_SIZE = 1000
    
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
            
            logger.info(f"VTS: {len(vts_set)}, IMS: {len(ims_set)}")
            
            # Mark which trips are completed
            df = df.with_columns([
                pl.col("invoice_clean").is_in(list(vts_set)).alias("in_vts"),
                pl.col("base_invoice").is_in(list(ims_set)).alias("in_ims")
            ])
            
            # Filter only trips that need update
            trips_to_update = df.filter(
                pl.col("in_vts") | pl.col("in_ims")
            )
            
            if trips_to_update.is_empty():
                logger.info("No completed trips found")
                return {"status": True, "message": "No updates needed", "updated": 0}
            
            logger.info(f"Updating {trips_to_update.height} trips")
            
            # Prepare bulk update list
            update_count = 0
            failed_count = 0
            updates_list = []
            
            for row in trips_to_update.iter_rows(named=True):
                try:
                    # Determine status based on presence in tables
                    in_vts = row['in_vts']
                    in_ims = row['in_ims']
                    
                    update_record = {
                        "id": row['id'],
                        "invoice_no": row['invoice_no'],
                        "trip_status": hpcl_ceg_enum.VtsLive.TripCompleted,
                        "vts_status": hpcl_ceg_enum.VtsLive.TripCompleted if in_vts else hpcl_ceg_enum.VtsLive.TripOngoing,
                        "ims_status": hpcl_ceg_enum.VtsLive.TripCompleted if in_ims else hpcl_ceg_enum.VtsLive.TripOngoing,
                        "trip_completed_time": datetime.datetime.now()
                    }
                    
                    updates_list.append(update_record)
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Preparation failed for trip {row['id']}: {str(e)}")
            
            # Bulk update all existing records at once
            if updates_list:
                try:
                    await hpcl_ceg_model.VtsOngoingTripsCreate.bulk_update(records=updates_list,upsert=True)
                    update_count = len(updates_list)
                    logger.info(f"Bulk updated {update_count} trips")
                except Exception as e:
                    logger.error(f"Bulk update failed: {str(e)}")
                    failed_count += len(updates_list)
            
            logger.info(f"[{datetime.datetime.now()}] Updated {update_count} trips, {failed_count} failed")
            
            return {
                "status": True,
                "message": "Sync completed",
                "updated": update_count,
                "failed": failed_count
            }
            
        except Exception as e:
            logger.error(f"Sync error: {str(e)}")
            logger.error(traceback.format_exc())
            return {"status": False, "message": str(e), "updated": 0}


async def main():
    result = await VTSTripSyncService.sync_trip_completion_status()
    logger.info(f"Result: {result}")
    return result


if __name__ == "__main__":
    asyncio.run(main())