import urdhva_base
import asyncio
import asyncpg
import sys
import os
from typing import Dict, Any, Optional
sys.path.append("/opt/ceg/algo")
import orchestrator.dbconnector.credential_loader as credential_loader

logger = urdhva_base.Logger.getInstance("device_installation_into_pg_admin")

creds_app = credential_loader.get_credentials('APP_DB')




async def sync_device_to_tank_truck_master():
    """
    Sync device_installation data to tank_truck_master table.
    """
    conn: Optional[asyncpg.Connection] = None
    

    try:
        conn = await asyncpg.connect(
            user=creds_app['user'],
            password=creds_app['password'],
            host=creds_app['host'],
            port=creds_app['port'],
            database=creds_app['database']
        )
        print("Database connected")
        
        
        # Sync query with data validation and transformation
        sync_query = r"""
            INSERT INTO tank_truck_master (
                truck_number,
                business,
                transporter_code,
                deviceno,
                vtseffectivedate,
                vtsendingdate,
                vtseffectivedatej,
                vtsendingdatej,
                locationcode,
                zonecode,
                statuscode,
                transactionoriginator,
                userid,
                dateupdated,
                timeupdated,
                dateupdatedj,
                timeupdatedj,
                jdeupdateflag,
                jdeupdatedate,
                jdeupdatetime,
                jdeuserid,
                remarks
            )
            SELECT 
                VE.sap_tt_no,
                'RET' AS business,
                CASE 
                    WHEN TRIM(VE.transporter) ~ '^[0-9]+$'
                    THEN VE.transporter::DOUBLE PRECISION
                END,
                CASE
                    WHEN TRIM(VE.device) ~ '^[0-9]+$'
                    THEN VE.device::BIGINT
                END,
                VE.vehicle_installation_date,
                NULL,
                CASE
                    WHEN VE.vehicle_installation_date ~ '^\d{4}-\d{2}-\d{2}$'
                    THEN TO_CHAR(VE.vehicle_installation_date::DATE, 'YYYYDDD')::BIGINT
                END,
                NULL,
                CASE
                    WHEN TRIM(VE.sap_id) ~ '^[0-9]+$'
                    THEN VE.sap_id::BIGINT
                END,
                NULL,
                'A',
                'ALGF',
                NULL,
                TO_CHAR(NOW(), 'YYYY-MM-DD'),
                TO_CHAR(NOW(), 'HH24:MI:SS'),
                TO_CHAR(NOW(), 'YYYYDDD')::BIGINT,
                NULL,
                'N',
                NULL,
                NULL,
                NULL,
                NULL
            FROM device_installation VE
            WHERE VE.aot_status = 'PENDING'
        """
        
#         AND NOT EXISTS (
#     SELECT 1
#     FROM tank_truck_master TM
#     WHERE TM.truck_number = VE.sap_tt_no
# )

        result = await conn.execute(sync_query)
        print(f"Synced {result} records to tank_truck_master")
        
        # Additional update query for expired vehicles
        update_query = r"""
            UPDATE tank_truck_master 
            SET 
                jdeupdateflag = 'U',
                statuscode = 'I'
            WHERE truck_number IN (
                SELECT DISTINCT truck_number 
                FROM tank_truck_master 
                WHERE truck_number IN (
                    SELECT DISTINCT truck_regnno 
                    FROM vehicle_masterv 
                    WHERE truck_expiry = 'Y'
                )
            )
        """
        
        update_result = await conn.execute(update_query)
        print(f"Updated {update_result} records with JDE flags")
        
        return True

    except Exception as e:
        print(f" Sync error: {e}")
        return False

    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    print("Device Installation Sync Started")
    asyncio.run(sync_device_to_tank_truck_master())
   