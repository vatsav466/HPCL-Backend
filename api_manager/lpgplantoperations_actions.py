from hpcl_ceg_enum import *
from hpcl_ceg_model import *
import fastapi
import csv
import time
import asyncio

router = fastapi.APIRouter(prefix='/lpgplantoperations')

CSV_PATH = "/opt/ceg/algo/orchestrator/sync_services/lpg/LPG_PLANTS_CREDENTIALS.csv"


async def check_telnet(host_ip: str, port: int):
    start_time = time.time()
    try:
        # asyncio open_connection is fully async
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host_ip, port),
            timeout=5
            )
        writer.close()
        await writer.wait_closed()
        latency = round((time.time() - start_time) * 1000)  # ms
        return {"status": "live", "latency": f"{latency}"}
    except Exception:
        return {"status": "down", "latency": "-"}

# Action check_connection_status
@router.post('/check_connection_status', tags=['LpgPlantOperations'])
async def lpgplantoperations_check_connection_status(data: Lpgplantoperations_Check_Connection_StatusParams):
    sap_id = data.sap_id

    # Read CSV and filter plants for this SAP ID
    plants = []
    try:
        with open(CSV_PATH, mode='r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("erp_id") == sap_id:
                    port_str = row.get("port")
                    if not port_str:
                        continue
                    plants.append({
                        "plant_name": row.get("plant_name"),
                        "host_ip": row.get("host_ip"),
                        "port": int(port_str)
                    })
    except Exception as e:
        return {"status": False, "message": f"Failed to read CSV: {str(e)}", "data": {sap_id: []}}

    if not plants:
        return {"status": True, "message": "success", "data": {sap_id: []}}

    # Run checks concurrently using asyncio
    tasks = [check_telnet(p['host_ip'], p['port']) for p in plants]
    statuses = await asyncio.gather(*tasks)

    # Combine results
    results = []
    for plant, status in zip(plants, statuses):
        results.append({
            "plant_name": plant["plant_name"],
            "status": status["status"],
            "latency": status["latency"]
        })

    return {
        "status": True,
        "message": "success",
        "data": {
            "sap_id": sap_id,
            "connection_status": results
        }
    }
