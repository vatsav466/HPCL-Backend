from enum import Enum


class TASInterlockMapping(str, Enum):
    sap123 = "HealthinessofFireWaterLevelsinTanks"
    sap124 = "TAS_Additive_Overdose_21"
