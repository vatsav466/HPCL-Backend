"""
TAS Analytics Query Configurations - WITH unique_id matching
Contains all query templates and interlock definitions for equipment analysis
"""

# ============================================================================
# ESD EQUIPMENT QUERIES AND CONFIGURATIONS
# ============================================================================

ESD_QUERIES = {
    "pushbutton_activated": """
        alert_section = 'TAS'
        AND equipment_name = 'ESD'
        AND bu = 'TAS'
        AND interlock_name = 'ESD Pushbutton Activated'
    """,
    "all_interlocks_template": """
        alert_section = 'TAS'
        AND equipment_name = 'ESD'
        AND bu = 'TAS'
        AND sap_id IN ('{sap_ids}')
        AND interlock_name != 'ESD Pushbutton Activated'
    """
}

ESD_FIELDS = {
    "main_alert": ["unique_id", "location_name", "sap_id", "interlock_name", "created_at"],
    "pushbutton_activated": ["unique_id", "location_name", "sap_id", "created_at", "device_name"],
    "interlocks": ["id", "unique_id", "sap_id", "location_name", "created_at", "interlock_name"]
}

ESD_CATEGORIES = {
    "Barrier Gate opened": r"(?i)Barrier Gate opened",
    "Power ESD Activation": r"(?i)Power ESD Activation",
    "Gantry Permissive Power Off": r"(?i)Gantry Permissive Power Off",
    "All Tanks in Dormant Mode": r"(?i)All Tanks in Dormant Mode",
    "All DBBVs Closed": r"(?i)All DBBVs Closed",
    "TLF Product Pumps Stopped": r"(?i)TLF Product Pumps Stopped",
    "ESD Command To Process PLC": r"(?i)ESD Command To Process PLC",
    "Hooter cum strobe for ESD": r"(?i)Hooter cum strobe for ESD",
    "Siren Activated": r"(?i)Siren Activated",
    "All ROSOVs Closed": r"(?i)All ROSOVs Closed"
}

# ============================================================================
# VFT EQUIPMENT QUERIES AND CONFIGURATIONS
# ============================================================================

VFT_QUERIES = {
    "hhh_alarm": """
        bu = 'TAS'
        AND interlock_name = 'HHH alarm from VFT'
    """,
    "other_interlocks": """
        bu = 'TAS'
        AND interlock_name != 'HHH alarm from VFT'
        AND (interlock_name LIKE '%ROSOV_Close Status%' OR interlock_name LIKE '%MOV_Close Status%')
    """,
    "all_interlocks_template": """
        bu = 'TAS'
        AND sap_id IN ('{sap_ids}')
        AND interlock_name != 'HHH alarm from VFT'
        AND (interlock_name LIKE '%ROSOV_Close Status%' OR interlock_name LIKE '%MOV_Close Status%')
    """
}

VFT_FIELDS = {
    "hhh_alarm": ["unique_id", "location_name", "sap_id", "created_at", "device_name"],
    "other_interlocks": ["id", "unique_id", "location_name", "sap_id", "interlock_name", "created_at"],
    "interlocks": ["id", "unique_id", "sap_id", "location_name", "created_at", "interlock_name"]
}

VFT_CATEGORIES = {
    "ROSOV Close Status": r"(?i)ROSOV_Close Status",
    "MOV Close Status": r"(?i)MOV_Close Status"
}

# ============================================================================
# RADAR EQUIPMENT QUERIES AND CONFIGURATIONS
# ============================================================================

RADAR_QUERIES = {
    "radar_activated": """
        equipment_name = 'RADAR'
        AND bu = 'TAS'
        AND interlock_name = 'HHH alarm from Secondary Radar guage'
    """,
    "other_interlocks": """
        bu = 'TAS'
        AND interlock_name != 'HHH alarm from Secondary Radar guage'
        AND (interlock_name LIKE '%ROSOV_Close Status%' OR interlock_name LIKE '%MOV_Close Status%')
    """,
    "all_interlocks_template": """
        bu = 'TAS'
        AND sap_id IN ('{sap_ids}')
        AND interlock_name != 'HHH alarm from Secondary Radar guage'
        AND (interlock_name LIKE '%ROSOV_Close Status%' OR interlock_name LIKE '%MOV_Close Status%')
    """
}

RADAR_FIELDS = {
    "radar_activated": ["unique_id", "location_name", "sap_id", "created_at", "device_name"],
    "other_interlocks": ["id", "unique_id", "location_name", "sap_id", "interlock_name", "created_at"],
    "interlocks": ["id", "unique_id", "sap_id", "location_name", "created_at", "interlock_name"]
}

RADAR_CATEGORIES = {
    "ROSOV Close Status": r"(?i)ROSOV_Close Status",
    "MOV Close Status": r"(?i)MOV_Close Status"
}

# ============================================================================
# BCU EQUIPMENT QUERIES AND CONFIGURATIONS
# ============================================================================

BCU_QUERIES = {
    "bcu_alarm": """
        bu = 'TAS'
        AND alert_category = 'Gantry'
        AND interlock_name NOT LIKE '%BCU Permissive Off%'
    """,
    "all_interlocks_template": """
        bu = 'TAS'
        AND sap_id IN ('{sap_ids}')
        AND interlock_name IN ('{interlocks}')
    """,
    "permissive_off_template": """
        bu = 'TAS'
        AND sap_id IN ('{sap_ids}')
        AND interlock_name LIKE '%BCU Permissive Off%'
    """
}

BCU_FIELDS = {
    "bcu_alarm": ["unique_id", "location_name", "sap_id", "created_at", "device_name"],
    "interlocks": ["id", "unique_id", "sap_id", "created_at", "interlock_name"],
    "permissive_off": ["id", "unique_id", "sap_id", "created_at", "interlock_name"]
}

BCU_INTERLOCKS = [
    "Earthing Failure Alarm",
    "Blend Underdose Alarm_BCU",
    "No Flow alarm_BCU",
    "Additive Overdose Alarm_BCU",
    "Meter overrun Alarm_BCU",
    "Additive Underdose Alarm_BCU",
    "Unauthorized Flow Alarm_BCU",
    "High Flow Alarm_BCU",
    "Blend overdose Alarm_BCU",
    "Low Flow alarm_BCU",
    "No Flow alarm Blend_BCU",
    "Unauthorized Flow Alarm Blend_BCU",
    "High Flow Alarm Blend_BCU",
    "Low Flow alarm Blend_BCU",
    "Meter overrun Alarm Blend_BCU",
    "K Factor Change_BCU",
    "Day End totaliser Mismatch",
    "Day End totaliser Mismatch Blend"
]

BCU_ALARM_DETAILS_LIMIT = 100

# ============================================================================
# FIRE EFFECT EQUIPMENT QUERIES AND CONFIGURATIONS
# ============================================================================

FIRE_EFFECT_QUERIES = {
    "fire_effect_alarm": """
        bu = 'TAS'
        AND device_type = 'Fire Effect'
    """,
    "all_interlocks_template": """
        bu = 'TAS'
        AND device_type = 'Fire Effect'
        AND sap_id IN ('{sap_ids}')
        AND (
            interlock_name LIKE '%Hooter Activated at control room%'
            OR interlock_name LIKE '%All TLF Product Pumps Stopped%'
            OR interlock_name LIKE '%Gantry Permissive Off%'
        )
    """
}

FIRE_EFFECT_FIELDS = {
    "fire_effect_alarm": ["unique_id", "location_name", "sap_id", "created_at", "device_name"],
    "interlocks": ["id", "unique_id", "sap_id", "location_name", "created_at", "interlock_name"]
}

FIRE_EFFECT_INTERLOCKS = [
    "Hooter Activated at control room",
    "All TLF Product Pumps Stopped",
    "Gantry Permissive Off"
]

# ============================================================================
# EQUIPMENT TYPE MAPPING
# ============================================================================

EQUIPMENT_TYPE_MAPPING = {
    'ESD': 'ESD',   
    'VFT': 'VFT',
    'RADAR': 'RADAR',
    'BCU': 'BCU',
    'FIRE EFFECT': 'Fire Effect'
}

DEFAULT_EQUIPMENT_TYPES = ['ESD', 'VFT', 'RADAR', 'BCU', 'FIRE EFFECT']

# ============================================================================
# COMMON PATTERNS
# ============================================================================

FAIL_PATTERNS = ['Fail', '_Fail', 'fail']

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def build_date_filter(start_date, end_date):
    """Build date filter for queries"""
    if (start_date and end_date and 
        start_date.strip() and end_date.strip() and
        start_date.lower() != "string" and end_date.lower() != "string"):
        return f" AND created_at::date BETWEEN '{start_date}' AND '{end_date}'"
    return ""

def build_location_filter(location_name):
    """Build location filter for queries"""
    if location_name and location_name.strip():
        return f" AND location_name = '{location_name}'"
    return ""

def build_complete_query(base_query, start_date=None, end_date=None, location_name=None):
    """Build complete query with filters"""
    query = base_query
    
    if location_name:
        query += build_location_filter(location_name)
    
    if start_date and end_date:
        query += build_date_filter(start_date, end_date)
    
    return query

def format_sap_ids_for_query(sap_ids):
    """Format SAP IDs for IN clause"""
    return "','".join(sap_ids)

def format_interlocks_for_query(interlocks):
    """Format interlocks for IN clause"""
    return "','".join(interlocks)