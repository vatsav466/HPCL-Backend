from enum import Enum


class TASInterlockMapping(str, Enum):
    sap123 = "HealthinessofFireWaterLevelsinTanks"
    # sap124 = "TAS_Additive_Overdose_21"
    sap124 = "TAS_Tank_overfill_production_inlet_mov_activate_hls_7"
