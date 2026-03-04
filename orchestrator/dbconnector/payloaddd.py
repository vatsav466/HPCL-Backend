import pandas as pd
from cryptography.fernet import Fernet
import base64
# Fernet key must be 32-byte base64-encoded
encryption_key = b'mcMAmuM2wLgNey7hgaCXDsaH__h13R2esSQ7fKvX3ak='

def encrypt_data(data: str, key: bytes) -> str:
    """Encrypts and double-base64-encodes the result (as in your original logic)"""
    cipher = Fernet(key)
    encrypted = cipher.encrypt(data.encode('utf-8'))  # Fernet already returns base64
    return base64.b64encode(encrypted).decode('utf-8')  # Second layer of base64

def decrypt_data(data: str, key: bytes) -> str:
    """Decrypts a double-base64-encoded Fernet token"""
    # Fix padding for outer base64
    missing_padding = len(data) % 4
    if missing_padding:
        data += '=' * (4 - missing_padding)

    encrypted_token = base64.b64decode(data)  # decode outer base64
    cipher = Fernet(key)
    decrypted = cipher.decrypt(encrypted_token)  # decrypt inner (Fernet base64)
    return decrypted.decode('utf-8')


if  __name__== "__main__":
    encrypted_input = "Z0FBQUFBQnBwdVNQdk5sOUhOSVdxbGk2WG5WNHdSMHZ5TmRNUE1mVnZQYW0tOXF5Rm9Vck1WY0MzRVpHVURKNGlpcmY0SUJfVFFHOEpHcHNmdDRMcVVxQTF2UG8wbmhUektxMXF4aTR1clFQbWNxOExRRGItZ1QyYkIxT0RwUlE4OFBuYUJNa3E4d0w"
    decrypted_output = decrypt_data(encrypted_input, encryption_key)
    print("Decrypted message:", decrypted_output)


    
    
    
    
    # { "action": "risk_score", "filters": [],
    #  "cross_filters": [ { "key": "scheduled_trip_start_datetime", "cond": "equals", "value": "2025-10-04,2025-10-06" } ],
    #  "drill_state": "completed_trips_risk_score", "payload": { "table_name": "completed_trips_risk_score" } }