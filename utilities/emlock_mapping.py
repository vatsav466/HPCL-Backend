emlock_vehicle_mapping = {
    "VTSOFFLINE": {
        "interlock_name": "EM Locks : VTS Offline - Lorry",
        "sop_id": "SOP001", 
        "severity": "HIGH"
    },    
    "DELAY": {
        "interlock_name": "EM Locks : Transit Time Delay - Lorry",
        "sop_id": "SOP003", 
        "severity": "HIGH"
    },

    "PRE_DECANTATION_ISSUE": {
        "ineterlock_name": "Pre-Decantation OTP", 
        "sop_id": "SOP005", 
        "severity": "HIGH"
    }
}


emlock_dealer_mapping = {
    "VTSOFFLINE": {
        "interlock_name": "EM Locks : VTS Offline - Customer",
        "sop_id": "SOP002", 
        "severity": "HIGH"
    },
    "DELAY": {
        "interlock_name": "EM Locks : Transit Time Delay - Customer",
        "sop_id": "SOP004", 
        "severity": "HIGH"
    },
    "POST_DECANTATION_ISSUE": {
        "interlock_name": "Post-Decantation OTP", 
        "sop_id": "SOP006", 
        "severity": "HIGH"
    }
}