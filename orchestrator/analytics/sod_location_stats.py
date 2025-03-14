import urdhva_base
import hpcl_ceg_model
import utilities.helpers as helpers


async def generate_sod_engineering_location_stats(sap_id):
    """
    Function to get TAS location data for Engineering dashboard, This will give status of master/slave and
    Counts of Device/Equipment types with Faulty and Maintenance Count
    :param sap_id:
    :return:
    """
    status, location_data = await helpers.get_location_details('TAS', sap_id)
    if not status:
        return {"status": False, "data": "Invalid Location / Location not found"}
    # Hardcoded data for UI development purpose
    json_data = [{"id": "lrca", "name": "LRCA", "status": "standby"},
                 {"id": "lrcb", "name": "LRCB", "status": "online"},
                 {"id": "gantry_bcu", "name": "Gantry BCU ", "total": 34, "faulty": 1, "maintanance": 1},
                 {"id": "mfm", "name": "MFM", "total": 10, "faulty": 1, "maintanance": 0},
                 {"id": "primary_radar", "name": "Primary Radar", "total": 11, "faulty": 0, "maintanance": 0},
                 {"id": "mov", "name": "MOV", "total": 30, "faulty": 0, "maintanance": 0},
                 {"id": "pumps", "name": "Pumps", "total": 14, "faulty": 0, "maintanance": 1},
                 {"id": "barrier_gate", "name": "Barrier Gate", "total": 6, "faulty": 0, "maintanance": 0},
                 {"id": "rosov", "name": "Rosov", "total": 30, "faulty": 1, "maintanance": 1},
                 {"id": "vft", "name": "VFT", "total": 5, "faulty": 0, "maintanance": 0},
                 {"id": "secondary_radar", "name": "Secondary Radar", "total": 5, "faulty": 0, "maintanance": 0},
                 {"id": "pt_hydrant", "name": "PT Hydrant", "total": 1, "faulty": 0, "maintanance": 0},
                 {"id": "hooter", "name": "Hooter", "total": 20, "faulty": 0, "maintanance": 4},
                 {"id": "esd", "name": "ESD", "total": 10, "faulty": 0, "maintanance": 0},
                 {"id": "fire_engine", "name": "Fire Engine", "total": 4, "faulty": 0, "maintanance": 0},
                 {"id": "hcd", "name": "HCD", "total": 11, "faulty": 0, "maintanance": 0},
                 {"id": "dyke", "name": "Dyke", "total": 4, "faulty": 0, "maintanance": 0},
                 {"id": "jockey_pump", "name": "Jockey Pump", "total": 4, "faulty": 1, "maintanance": 1},
                 {"id": "air_compressor", "name": "Air Compressor", "total": 6, "faulty": 0, "maintanance": 1}]
    return {"status": True, "data":  json_data}
