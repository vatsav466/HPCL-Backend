import numpy as np
import pandas as pd
import h3.api.basic_str as h3
from datetime import datetime, timedelta
from shapely.geometry import Point, Polygon
from shapely.vectorized import contains
from sqlalchemy import create_engine, text, Integer, Double, Boolean, DateTime, VARCHAR, Float

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("styler.render.max_elements", 800000)

import warnings
warnings.filterwarnings('ignore')

# ===============================
# LOAD EVENTS DATA
# ===============================

DB_CONFIG = {
    'host': '10.90.38.213',
    'port': 5432,
    'database': 'hpcl_ceg',
    'user': 'ceg_user',
    'password': 'TTNqetkiJLPM50jC'
}
engine = create_engine(
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
    f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)
print("Database connection established successfully!")

EVENTS_RENAME_MAP = {
    "event_date": "EVENT_DATETIME",
    "sap_id": "SAP_ID",
    "destination": "DESTINATION",
    "location_type": "LOCATION_TYPE",
    "tt_type": "TT_TYPE",
    "tt_number": "TT_NUMBER",
    "transporter_id": "TRANSPORTER_ID",
    "transporter_name": "TRANSPORTER_NAME",
    "invoice_no": "INVOICE_NO",
    "load_no": "LOAD_NO",
    "route_no": "ROUTE_NO",
    "trip_status": "TRIP_STATUS",
    "driver_name": "DRIVER_NAME",
    "scheduled_datetime": "SCHEDULED_DATETIME",
    "start_datetime": "START_DATETIME",
    "start_location": "START_LOCATION",
    "start_speed": "START_SPEED",
    "start_latitude": "LAT",
    "start_longitude": "LON",
    "end_datetime": "END_DATETIME",
    "end_location": "END_LOCATION",
    "end_speed": "END_SPEED",
    "end_latitude": "END_LATITUDE",
    "end_longitude": "END_LONGITUDE",
    "distance_km": "DISTANCE_KM",
    "duration": "DURATION",
    "bu": "BU",                       # extra in DB
    "location_name": "LOCATION_NAME", # extra in DB
    "zone": "ZONE",
    "region": "REGION",               # extra in DB
    "stoppage_datetime": "STOPPAGE_DATETIME",
    "stoppage_location": "STOPPAGE_LOCATION",
    "stoppage_latitude": "LAT",
    "stoppage_longitude": "LON",
}

RD_FILE = pd.read_sql_query("SELECT * FROM public.vts_route_deviation WHERE event_date >= CURRENT_DATE - INTERVAL '90 days';", engine)
print(f"Loaded {len(RD_FILE)} route deviation records")
ST_FILE = pd.read_sql_query("SELECT * FROM public.vts_stoppage_violation  WHERE event_date >= CURRENT_DATE - INTERVAL '90 days';", engine)
print(f"Loaded {len(ST_FILE)} stoppage violation records")
DR_FILE = pd.read_sql_query("SELECT * FROM public.vts_device_removed WHERE event_date >= CURRENT_DATE - INTERVAL '90 days';", engine)
print(f"Loaded {len(DR_FILE)} device removed records")
PD_FILE = pd.read_sql_query("SELECT * FROM public.vts_power_disconnect WHERE event_date >= CURRENT_DATE - INTERVAL '90 days';", engine)
print(f"Loaded {len(PD_FILE)} power disconnect records")


RENAMES_alerts = {
    
    "EVENT_DATE": "EVENT_DATETIME",
    "START_LATITUDE": "LAT",
    "START_LONGITUDE": "LON",
    "STOPPAGE_LATITUDE":"LAT",
    "STOPPAGE_LONGITUDE": "LON"
}


def load_alerts_data():
    rd = RD_FILE
    stp = ST_FILE
    dr = DR_FILE
    pdw = PD_FILE
    # Apply renames + timestamp conversion
    for df in [rd, stp, dr, pdw]:
        df.rename(columns=EVENTS_RENAME_MAP, inplace=True)
        df.rename(columns=RENAMES_alerts, inplace=True)
        if "EVENT_DATETIME" in df.columns:
            df["EVENT_DATETIME"] = pd.to_datetime(df["EVENT_DATETIME"])

    # Add alert types
    rd["ALERT_TYPE"] = "ROUTE_DEVIATION"
    stp["ALERT_TYPE"] = "STOPPAGE_VIOLATION"
    dr["ALERT_TYPE"] = "DEVICE_REMOVED"
    pdw["ALERT_TYPE"] = "POWER_DISCONNECT"

    

    # Combine
    alerts = pd.concat([rd, stp, dr, pdw], ignore_index=True)
    alerts.sort_values("EVENT_DATETIME", inplace=True)


    if "LOCATION_TYPE" in alerts.columns and "TRIP_STATUS" in alerts.columns:
        alerts = alerts[(alerts["LOCATION_TYPE"] == "TAS") & (alerts["TRIP_STATUS"].isin(["LOADED", "UN LOADED"]))]

    return alerts


alerts = load_alerts_data()
print(f"Total loaded alerts: {len(alerts)}")



# ============================
# LOAD Completed_Trips File
# ============================

TRIP_RENAME_MAP = {
    "row_numb": "ROW_NUMB",
    "totalcount": "TOTALCOUNT",
    "tt_number": "VEHICLE_RTO_NO",
    "invoice_no": "CHALLAN_NO",
    "trip_name": "TRIP_NAME",
    "driver_name": "DRIVER_NAME",
    "depot_name": "DEPOT_NAME",
    "consumer_erp_name": "CONSUMER_ERP_NAME",
    "vendor_name": "VENDOR_NAME",
    "route_id": "ROUTE_ID",
    "sec_route_id": "SEC_ROUTE_ID",
    "scheduled_trip_start_datetime": "SCHEDULED_TRIP_START_DATETIME",
    "scheduled_trip_end_datetime": "SCHEDULED_TRIP_END_DATETIME",
    "schedule_rtt": "SCHEDULE_RTT",
    "schedule_rttd": "SCHEDULE_RTTD",
    "trip_id": "TRIP_ID",
    "depot_out_time": "DEPOT_OUT_TIME",
    "consumer_in": "CONSUMER_IN",
    "loaded_duration": "LOADED_DURATION",
    "loaded_distance": "LOADED_DISTANCE",
    "consumer_out": "CONSUMER_OUT",
    "unloading_duration": "UNLOADING_DURATION",
    "ret_depot_in": "RET_DEPOT_IN",
    "ret_depot_odo": "RET_DEPOT_ODO",
    "un_loaded_duration": "UN_LOADED_DURATION",
    "total_distance": "TOTAL_DISTANCE",
    "total_duration": "TOTAL_DURATION",
    "trip_status": "TRIP_STATUS",
    "trip_closed_by_client_id": "TRIP_CLOSED_BY_CLIENT_ID",
    "trip_performance_status": "TRIP_PERFORMANCE_STATUS",
    "depot_erp_code": "DEPOT_ERP_CODE",
    "consumer_erp_code": "CONSUMER_ERP_CODE",
    "transporter_code": "ERP_TRANSPORTER_CODE",
    "vehicle_id": "VEHICLE_ID",
    "trip_status_ril": "TRIP_STATUS_RIL",
    "vehicle_latitude": "VEHICLE_LATITUDE",
    "vehicle_longitude": "VEHICLE_LONGITUDE",
    "trip_distance": "TRIP_DISTANCE",
    "vehicle_location": "VEHICLE_LOCATION",
    "vehicle_speed": "VEHICLE_SPEED",
    "vehicle_gps_datetime": "VEHICLE_GPS_DATETIME",
    "tp_status": "TP_STATUS",
    "trip_performance_minutes": "TRIP_PERFORMANCE_MINUTES",
    "loadno": "LOADNO",
    "route_no": "ROUTE_NO",
    "zone_name": "ZONE_NAME",
    "area_name": "AREA_NAME",
    "teritory_name": "TERITORY_NAME",
    "ld_cnt_route_deviation": "LD_CNT_ROUTE_DEVIATION",
    "ld_cnt_stoppage_violation": "LD_CNT_STOPPAGE_VIOLATION",
    "ld_cnt_speed_violation": "LD_CNT_SPEED_VIOLATION",
    "ul_cnt_route_deviation": "UL_CNT_ROUTE_DEVIATION",
    "ul_cnt_stoppage_violation": "UL_CNT_STOPPAGE_VIOLATION",
    "ul_cnt_speed_violation": "UL_CNT_SPEED_VIOLATION",
    "insert_datetime": "INSERT_DATETIME",
}


trip_data=pd.read_sql_query('SELECT * FROM public.vts_completed_trip', engine)
trip_data.rename(columns=TRIP_RENAME_MAP, inplace=True)
print(f"Loaded {len(trip_data)} completed trip records")


trip_data["SCHEDULED_TRIP_END_DATETIME"] = pd.to_datetime(trip_data["SCHEDULED_TRIP_END_DATETIME"], errors="coerce")
trip_data["SCHEDULED_TRIP_START_DATETIME"] = pd.to_datetime(trip_data["SCHEDULED_TRIP_START_DATETIME"], errors="coerce")

trip_df = trip_data.drop_duplicates(subset=['CHALLAN_NO'], keep='first')# Remove duplicates based on specific column(s)

completed_Trips_df=trip_df[['ROW_NUMB', 'TOTALCOUNT', 'VEHICLE_RTO_NO', 'CHALLAN_NO', 'TRIP_NAME', 'DRIVER_NAME', 'DEPOT_NAME', 'CONSUMER_ERP_NAME', 'VENDOR_NAME', 'ROUTE_ID', 'SEC_ROUTE_ID',
       'SCHEDULED_TRIP_START_DATETIME', 'SCHEDULED_TRIP_END_DATETIME', 'SCHEDULE_RTT', 'SCHEDULE_RTTD', 'TRIP_ID', 'DEPOT_OUT_TIME', 'CONSUMER_IN', 'LOADED_DURATION', 'LOADED_DISTANCE',
       'CONSUMER_OUT', 'UNLOADING_DURATION', 'RET_DEPOT_IN', 'RET_DEPOT_ODO', 'UN_LOADED_DURATION', 'TOTAL_DISTANCE', 'TOTAL_DURATION', 'TRIP_STATUS', 'TRIP_CLOSED_BY_CLIENT_ID',
       'TRIP_PERFORMANCE_STATUS', 'CONSUMER_ERP_CODE', 'ERP_TRANSPORTER_CODE', 'VEHICLE_ID', 'TRIP_STATUS_RIL', 'VEHICLE_LATITUDE', 'VEHICLE_LONGITUDE', 'TRIP_DISTANCE',
       'VEHICLE_LOCATION', 'VEHICLE_SPEED', 'VEHICLE_GPS_DATETIME', 'TP_STATUS', 'TRIP_PERFORMANCE_MINUTES', 'LOADNO', 'ROUTE_NO', 'ZONE_NAME', 'AREA_NAME', 'TERITORY_NAME']]

completed_Trips_df.rename(columns={'CHALLAN_NO': 'INVOICE_NO', "ERP_TRANSPORTER_CODE":"TRANSPORTER_CODE","VEHICLE_RTO_NO":"TT_NUMBER", "ZONE_NAME":"ZONE",'AREA_NAME':"LOCATION"}, inplace=True)





# ===============================
# LOAD MASTER MAPPING
# ===============================

VEHICLE_MASTER_RENAME_MAP = {
    "tt_number": "TT No",
    "tank_compartment": "Tank Compartment",
    "vol_capacity": "VOL Capacity",
    "transporter_name": "Transporter Name",
    "transporter_code": "Transporter Code",
    "location_name": "Location Name",
    "sap_id": "Location Code",   # extra in DB → kept as uppercase
    
}

master_df = pd.read_sql_query('SELECT * FROM public.vehicle_master', engine)
print(f"Loaded {len(master_df)} vehicle master records")
master_df.rename(columns=VEHICLE_MASTER_RENAME_MAP, inplace=True)
master_df.rename(columns={"Transporter Code":"TRANSPORTER_CODE","Transporter Name":"TRANSPORTER_NAME", 
                          "TT No":"TT_NUMBER", "Location Code":"LOCATION_CODE", "Location Name":"LOCATION_NAME"}, inplace=True)

# Keep only the columns we need for mapping
required_cols = ["TT_NUMBER", "TRANSPORTER_CODE", "TRANSPORTER_NAME", "LOCATION_NAME", "LOCATION_CODE"]
available_cols = [col for col in required_cols if col in master_df.columns]
master_df = master_df[available_cols].copy()


# ===============================
# LOAD GEOFENCE DATA
# ===============================
GEOFENCE_RENAME_MAP = {
    "geofence_name": "GEOFENCE_NAME",
    "latitude": "LATITUDE",
    "longitude": "LONGITUDE",
    "radius": "RADIUS",
    "latlon": "latlon",              # already same in both
    "geofence_type": "GEOFENCE_TYPE",
}

geofence_data = pd.read_excel("GeofenceMaster.xlsx")
geofence_data.rename(columns=GEOFENCE_RENAME_MAP, inplace=True)
print(f"Loaded {len(geofence_data)} geofence records")
geofence_data.rename(columns={c: c.lower() for c in geofence_data.columns}, inplace=True)
geofence_data.rename(columns={'geofence_type': 'GEOFENCE_TYPE', 'latitude': 'LATITUDE', 
                               'longitude': 'LONGITUDE', 'radius': 'RADIUS'}, inplace=True)

# =====================================================
# DATE RANGE & TRAIN DATA AND TEST/REALTIME DATA SPLIT
# =====================================================
min_dt_alerts = alerts["EVENT_DATETIME"].min()
max_dt_alerts = alerts["EVENT_DATETIME"].max()


min_dt_ct = completed_Trips_df["SCHEDULED_TRIP_START_DATETIME"].min()
max_dt_ct = completed_Trips_df["SCHEDULED_TRIP_END_DATETIME"].max()


print(f"alerts date range:{min_dt_alerts} to {max_dt_alerts}")
print(f"completed trips date range: {min_dt_ct} to {max_dt_ct}")

# Split alerts data
realtime_data = alerts
realtime_data.rename(columns={'TRANSPORTER_ID': 'TRANSPORTER_CODE'}, inplace=True)

train_data = alerts
train_data.rename(columns={'TRANSPORTER_ID': 'TRANSPORTER_CODE'}, inplace=True)

# Split trip data
trip_train_df = completed_Trips_df
trip_Realtime_df = completed_Trips_df

# ======================================
# COMBO DETECTION & COMBO RISK MAPPING
# ======================================

COMBO_RULES = {
    "route_deviation_then_device_removed_then_power_disconnect": {
        "sequence": ("ROUTE_DEVIATION", "DEVICE_REMOVED", "POWER_DISCONNECT"),
        "within_minutes": 30,
        "combo_delta": 50,
    },
    "route_dev_plus_stoppage": {
        "sequence": ("ROUTE_DEVIATION", "STOPPAGE_VIOLATION"),
        "within_minutes": 30,
        "combo_delta": 40,
    },
    "multiple_route_devs": {
        "sequence": ("ROUTE_DEVIATION",),
        "count_required": 3,
        "within_minutes": 30,
        "combo_delta": 25,
    },
}

# ===============================
# COMBO DETECTION
# ===============================
def detect_combo_rules(df):
    combos = []
    df_sorted = df.sort_values("EVENT_DATETIME")
    for inv, group in df_sorted.groupby("INVOICE_NO"):
        group = group.sort_values("EVENT_DATETIME").to_dict("records")
        triggered = None
        for i, current in enumerate(group):
            for rule_name, rule in COMBO_RULES.items():
                seq = rule["sequence"]
                within = rule["within_minutes"]
                if len(seq) > 1:
                    for past in group[:i]:
                        if (
                            past["ALERT_TYPE"] == seq[0]
                            and current["ALERT_TYPE"] == seq[1]
                            and abs((current["EVENT_DATETIME"] - past["EVENT_DATETIME"]).total_seconds() / 60)
                            <= within
                        ):
                            triggered = rule_name
                else:
                    if current["ALERT_TYPE"] == seq[0]:
                        past_events = [
                            p for p in group[:i]
                            if (current["EVENT_DATETIME"] - p["EVENT_DATETIME"]).total_seconds() / 60 <= within
                            and p["ALERT_TYPE"] == seq[0]
                        ]
                        if len(past_events) >= rule.get("count_required", 2):
                            triggered = rule_name
            if triggered:
                combos.append({
                    "INVOICE_NO": inv,
                    "Last_Combo_Rule": triggered,
                    "Triggered_At": current["EVENT_DATETIME"],
                })
    return pd.DataFrame(combos)

combo_df = detect_combo_rules(realtime_data)
print(f"Detected {len(combo_df)} combo triggers")


# ==================================================
# TRANSPORTER RISK CALCULATION
# ==================================================

# STEP 1: TRIP COUNTS PER TRANSPORTER
trip_counts = (
    trip_train_df.groupby("TRANSPORTER_CODE", as_index=False)
    .agg(total_trips=("INVOICE_NO", "count"))
)

# STEP 2: ALERT COUNTS PER TRANSPORTER
alert_summary = (
    train_data.groupby(["TRANSPORTER_CODE", "ALERT_TYPE"])
    .agg(total_alerts=("ALERT_TYPE", "count"))
    .reset_index()
)

# Pivot ALERT_TYPE horizontally
alert_summary_pivot = (
    alert_summary.pivot_table(
        index="TRANSPORTER_CODE",
        columns="ALERT_TYPE",
        values="total_alerts",
        fill_value=0
    )
    .reset_index()
)
alert_summary_pivot.columns.name = None

# STEP 3: MERGE TRIP & ALERT DATA
final_alert_summary = trip_counts.merge(alert_summary_pivot, on="TRANSPORTER_CODE", how="left")
final_alert_summary.fillna(0, inplace=True)

# STEP 4: CONFIGURATION
ALERT_WEIGHTS = {
    "DEVICE_REMOVED": 1.5,
    "POWER_DISCONNECT": 1.2,
    "ROUTE_DEVIATION": 1.0,
    "STOPPAGE_VIOLATION": 0.8,
}

# STEP 5: ENTITY RISK CALCULATION
final_alert_summary["entity_risk"] = 0.0

for alert_type, weight in ALERT_WEIGHTS.items():
    if alert_type in final_alert_summary.columns:
        final_alert_summary[f"{alert_type}_per_trip"] = np.where(
            final_alert_summary["total_trips"] > 0,
            (final_alert_summary[alert_type] / final_alert_summary["total_trips"]).round(3),
            0
        )
        final_alert_summary["entity_risk"] += (
            final_alert_summary[f"{alert_type}_per_trip"] * weight
        )

final_alert_summary["entity_risk"] = final_alert_summary["entity_risk"].round(3)

# STEP 6: FINAL OUTPUT
entity_risk_summary = final_alert_summary[["TRANSPORTER_CODE", "total_trips", "entity_risk"]].copy()

# Create transporter name mapping
transporter_name_map = (
    master_df.drop_duplicates(subset=["TRANSPORTER_CODE"])
    .set_index("TRANSPORTER_CODE")["TRANSPORTER_NAME"]
    .to_dict()
)

# ✅ Normalize 0–100
min_val = entity_risk_summary["entity_risk"].min()
max_val = entity_risk_summary["entity_risk"].max()

entity_risk_summary["RISK_SCORE"] = ((entity_risk_summary["entity_risk"] - min_val) / (max_val - min_val)) * 100

# This ensures fair comparison across all TTs
entity_risk_summary["RISK_SCORE"] = (
    entity_risk_summary["RISK_SCORE"]
).round(2)

entity_risk_summary["TRANSPORTER_NAME"] = entity_risk_summary["TRANSPORTER_CODE"].map(transporter_name_map)
Transporter_risk_summary = entity_risk_summary[['TRANSPORTER_CODE', 'TRANSPORTER_NAME', "total_trips", 'RISK_SCORE']].copy()


# ===============================
# TT RISK CALCULATION
# ===============================

# CALCULATE TOTAL TRIPS
# ===============================
# IMPROVED TT RISK CALCULATION
# ===============================

# STEP 1: CALCULATE TOTAL TRIPS PER TT_NUMBER
trip_counts_tt = (
    trip_train_df.groupby("TT_NUMBER")["TRIP_ID"]
    .nunique()
    .reset_index()
    .rename(columns={"TRIP_ID": "total_trips"})
)

# STEP 2: CALCULATE ALERTS PER TT_NUMBER AND ALERT_TYPE
alert_summary_tt = (
    train_data.groupby(["TT_NUMBER", "ALERT_TYPE"])
    .agg(total_alerts=("ALERT_TYPE", "count"))
    .reset_index()
)

# STEP 3: PIVOT ALERT_TYPE HORIZONTALLY (one column per alert type)
alert_summary_pivot_tt = (
    alert_summary_tt.pivot_table(
        index="TT_NUMBER",
        columns="ALERT_TYPE",
        values="total_alerts",
        fill_value=0
    )
    .reset_index()
)
alert_summary_pivot_tt.columns.name = None

# STEP 4: MERGE TRIP COUNTS WITH ALERTS
final_alert_summary_tt = trip_counts_tt.merge(
    alert_summary_pivot_tt, 
    on="TT_NUMBER", 
    how="inner"  # Use outer join to keep TTs with only trips OR only alerts
)

# Fill NaN values
final_alert_summary_tt["total_trips"] = final_alert_summary_tt["total_trips"].fillna(0)
for alert_type in ALERT_WEIGHTS.keys():
    if alert_type in final_alert_summary_tt.columns:
        final_alert_summary_tt[alert_type] = final_alert_summary_tt[alert_type].fillna(0)

# STEP 5: CALCULATE ALERTS PER TRIP FOR EACH ALERT TYPE
for alert_type in ALERT_WEIGHTS.keys():
    if alert_type in final_alert_summary_tt.columns:
        final_alert_summary_tt[f"{alert_type}_per_trip"] = np.where(
            final_alert_summary_tt["total_trips"] > 0,
            (final_alert_summary_tt[alert_type] / final_alert_summary_tt["total_trips"]).round(3),
            final_alert_summary_tt[alert_type] * 0.5  # Penalty multiplier for TTs with alerts but no recorded trips
        )
    else:
        final_alert_summary_tt[f"{alert_type}_per_trip"] = 0

# STEP 6: CALCULATE WEIGHTED ENTITY RISK
final_alert_summary_tt["entity_risk"] = 0.0

for alert_type, weight in ALERT_WEIGHTS.items():
    if f"{alert_type}_per_trip" in final_alert_summary_tt.columns:
        final_alert_summary_tt["entity_risk"] += (
            final_alert_summary_tt[f"{alert_type}_per_trip"] * weight
        )

final_alert_summary_tt["entity_risk"] = final_alert_summary_tt["entity_risk"].round(3)

# STEP 7: NORMALIZE TO 0-100 RISK SCORE (PERCENTILE-BASED)

# ✅ Normalize 0–100
min_val = final_alert_summary_tt["entity_risk"].min()
max_val = final_alert_summary_tt["entity_risk"].max()

final_alert_summary_tt["RISK_SCORE"] = ((final_alert_summary_tt["entity_risk"] - min_val) / (max_val - min_val)) * 100

# This ensures fair comparison across all TTs
final_alert_summary_tt["RISK_SCORE"] = (
    final_alert_summary_tt["RISK_SCORE"]
).round(2)

# STEP 8: ADD TRANSPORTER INFORMATION
transporter_code_map = (
    master_df.drop_duplicates(subset=["TT_NUMBER"])
    .set_index("TT_NUMBER")["TRANSPORTER_CODE"]
    .to_dict()
)

transporter_name_map = (
    master_df.drop_duplicates(subset=["TT_NUMBER"])
    .set_index("TT_NUMBER")["TRANSPORTER_NAME"]
    .to_dict()
)

final_alert_summary_tt["TRANSPORTER_CODE"] = final_alert_summary_tt["TT_NUMBER"].map(transporter_code_map)
final_alert_summary_tt["TRANSPORTER_NAME"] = final_alert_summary_tt["TT_NUMBER"].map(transporter_name_map)

# STEP 9: CREATE FINAL OUTPUT DATAFRAMES

# Summary output (for display and API)
TT_risk_summary = final_alert_summary_tt[[
    "TT_NUMBER", 
    "TRANSPORTER_CODE", 
    "TRANSPORTER_NAME", 
    "total_trips",
    "RISK_SCORE"
]].copy()

# Detailed output (for analysis - includes raw entity_risk)
TT_entity_risk_summary = final_alert_summary_tt[[
    "TT_NUMBER", 
    "TRANSPORTER_CODE", 
    "TRANSPORTER_NAME",
    "total_trips",
    "entity_risk",
    "RISK_SCORE"
]].copy()

# Sort by risk score (highest risk first)
TT_risk_summary = TT_risk_summary.sort_values("RISK_SCORE", ascending=False).reset_index(drop=True)
TT_entity_risk_summary = TT_entity_risk_summary.sort_values("RISK_SCORE", ascending=False).reset_index(drop=True)

# STEP 10: PRINT SUMMARY STATISTICS
print(f"Total TTs analyzed: {len(TT_risk_summary)}")



# ==================================================
# CREATING CLUSTERS
# ==================================================

# CONFIGURATION / THRESHOLDS
CLUSTER_RADIUS_M = 300
H3_RESOLUTION = 8
LOOKBACK_DAYS = 25
MERGE_DISTANCE_M = 200
RETIRE_DAYS = 20
INFLUENCE_RADIUS = 800

# Alert-specific thresholds
ALERT_THRESHOLDS = {
    "STOPPAGE_VIOLATION": {"min_events": 15, "min_unique_vehicles": 3, "min_unique_days": 3},
    "ROUTE_DEVIATION": {"min_events": 15, "min_unique_vehicles": 3, "min_unique_days": 3},
    "POWER_DISCONNECT": {"min_events": 10, "min_unique_vehicles": 3, "min_unique_days": 3},
    "DEVICE_REMOVED": {"min_events": 5, "min_unique_vehicles": 3, "min_unique_days": 3}
}

WEIGHTS = {"frequency": 0.5, "recency": 0.3, "diversity": 0.2}
OVERLAP_THRESHOLD = 0.5

# SCORING FUNCTIONS
def freq_score(n):
    if n <= 1: return 10
    elif n <= 3: return 30
    elif n <= 5: return 60
    elif n <= 9: return 80
    else: return 100

def recency_score(days_ago):
    if days_ago <= 3: return 100
    elif days_ago <= 7: return 80
    elif days_ago <= 14: return 60
    elif days_ago <= 30: return 30
    else: return 10

def diversity_score(n):
    if n == 1: return 20
    elif n <= 3: return 50
    elif n <= 6: return 80
    else: return 100

def classify_risk(score):
    if score <= 40: return "Low"
    elif score <= 70: return "Medium"
    elif score <= 85: return "High"
    else: return "Critical"

# H3 ASSIGNMENT
def assign_h3(df, resolution=H3_RESOLUTION):
    if df.empty:
        return df.copy()
    df = df.dropna(subset=["LAT", "LON"]).copy()
    df["h3_index"] = df.apply(lambda r: h3.latlng_to_cell(float(r["LAT"]), float(r["LON"]), resolution), axis=1)
    return df

# BUILD CANDIDATE CLUSTERS
def build_candidate_clusters(train_df, lookback_days=LOOKBACK_DAYS, resolution=H3_RESOLUTION):
    if train_df.empty:
        return {}, None
    latest_time = train_df["EVENT_DATETIME"].max()
    cutoff = latest_time - timedelta(days=lookback_days)
    df = train_df[train_df["EVENT_DATETIME"] >= cutoff].copy()
    df = assign_h3(df, resolution)

    clusters = {}
    seq = 0

    grouped = df.groupby(["ALERT_TYPE", "h3_index"])
    for (atype, cell), g in grouped:
        thresholds = ALERT_THRESHOLDS[atype]

        if len(g) < thresholds["min_events"]:
            continue
        if g["TT_NUMBER"].nunique() < thresholds["min_unique_vehicles"]:
            continue
        if g["EVENT_DATETIME"].dt.date.nunique() < thresholds["min_unique_days"]:
            continue

        seq += 1
        cid = f"{atype[:2]}-{seq}"
        clusters[cid] = {
            "cluster_id": cid,
            "alert_type": atype,
            "h3_index": cell,
            "centroid_lat": g["LAT"].mean(),
            "centroid_lon": g["LON"].mean(),
            "first_seen": g["EVENT_DATETIME"].min(),
            "last_seen": g["EVENT_DATETIME"].max(),
            "events_25d": len(g),
            "events_10d": len(g[g["EVENT_DATETIME"] >= (latest_time - timedelta(days=10))]),
            "events_5d": len(g[g["EVENT_DATETIME"] >= (latest_time - timedelta(days=5))]),
            "unique_trucks_30d": g["TT_NUMBER"].nunique(),
            "unique_days_30d": g["EVENT_DATETIME"].dt.date.nunique()
        }
    return clusters, latest_time

# MERGE CLUSTERS
def haversine_vectorized(lon1, lat1, lon2, lat2):
    R = 6371000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return 2*R*np.arctan2(np.sqrt(a), np.sqrt(1-a))

def merge_clusters(clusters, merge_distance_m=MERGE_DISTANCE_M):
    ids = list(clusters.keys())
    merged, used = {}, set()
    for i, cid in enumerate(ids):
        if cid in used: continue
        base = clusters[cid].copy()
        to_merge = [cid]
        for j in range(i + 1, len(ids)):
            cid2 = ids[j]
            if cid2 in used: continue
            c2 = clusters[cid2]
            if c2["alert_type"] != base["alert_type"]: continue
            if not (base["first_seen"] <= c2["last_seen"] and c2["first_seen"] <= base["last_seen"]): continue
            dist = haversine_vectorized(base["centroid_lon"], base["centroid_lat"], c2["centroid_lon"], c2["centroid_lat"])
            if dist <= merge_distance_m:
                to_merge.append(cid2)
                used.add(cid2)
        parent = max(to_merge, key=lambda x: clusters[x]["events_25d"])
        agg = clusters[parent].copy()
        if len(to_merge) > 1:
            agg["centroid_lat"] = np.mean([clusters[t]["centroid_lat"] for t in to_merge])
            agg["centroid_lon"] = np.mean([clusters[t]["centroid_lon"] for t in to_merge])
            agg["first_seen"] = min(clusters[t]["first_seen"] for t in to_merge)
            agg["last_seen"] = max(clusters[t]["last_seen"] for t in to_merge)
            agg["events_25d"] = sum(clusters[t]["events_25d"] for t in to_merge)
            agg["events_10d"] = sum(clusters[t]["events_10d"] for t in to_merge)
            agg["events_5d"] = sum(clusters[t]["events_5d"] for t in to_merge)
            agg["unique_trucks_30d"] = max(clusters[t]["unique_trucks_30d"] for t in to_merge)
            agg["unique_days_30d"] = max(clusters[t]["unique_days_30d"] for t in to_merge)
        merged[parent] = agg
    return merged

# VALIDATE & SCORE CLUSTERS
def validate_and_score(merged_clusters, latest_time):
    master = {}
    for cid, c in merged_clusters.items():
        atype = c.get("alert_type", "")
        thresholds = ALERT_THRESHOLDS[atype]

        E = c.get("events_25d", 0)
        Uveh = c.get("unique_trucks_30d", 0)
        Uday = c.get("unique_days_30d", 0)
        recent_ok = c.get("events_10d", 0) >= 1

        if (E >= thresholds["min_events"]) and (Uveh >= thresholds["min_unique_vehicles"]) and (Uday >= thresholds["min_unique_days"]) and recent_ok:
            status = "VALID"
        elif c.get("events_5d", 0) >= 3 and Uveh >= 2:
            status = "EMERGING"
        elif E >= 3:
            status = "PROVISIONAL"
        else:
            status = "NOISE"

        days_since_last = (latest_time - c["last_seen"]).days if c.get("last_seen") else None
        f_sub = freq_score(c.get("events_10d", 0))
        r_sub = recency_score(days_since_last if days_since_last is not None else 999)
        d_sub = diversity_score(Uveh)
        risk = f_sub * WEIGHTS["frequency"] + r_sub * WEIGHTS["recency"] + d_sub * WEIGHTS["diversity"]
        master[cid] = {
            **c,
            "status": status,
            "days_since_last": days_since_last,
            "freq_subscore": f_sub,
            "recency_subscore": r_sub,
            "diversity_subscore": d_sub,
            "risk_score": round(risk, 1),
            "risk_band": classify_risk(risk)
        }
    return master

# VECTORIZE GEOFENCE FILTERING
def filter_clusters_geofence(CLUSTER_MASTER, geofence_data):
    geofences = geofence_data[geofence_data["GEOFENCE_TYPE"].str.lower().str.strip() == "authorised"]
    n_clusters = len(CLUSTER_MASTER)
    overlap_flags = np.zeros(n_clusters, dtype=bool)
    
    cluster_lats = CLUSTER_MASTER["centroid_lat"].values
    cluster_lons = CLUSTER_MASTER["centroid_lon"].values
    cluster_buffer_deg = CLUSTER_RADIUS_M / 111000
    
    for _, gf in geofences.iterrows():
        gf_point = Point(gf["LONGITUDE"], gf["LATITUDE"])
        gf_radius_deg = gf["RADIUS"] / 111000
        gf_buffer = gf_point.buffer(gf_radius_deg)
        for i in range(n_clusters):
            if overlap_flags[i]:
                continue
            cluster_point = Point(cluster_lons[i], cluster_lats[i])
            cluster_buffer = cluster_point.buffer(cluster_buffer_deg)
            fraction_overlap = cluster_buffer.intersection(gf_buffer).area / cluster_buffer.area
            if fraction_overlap >= OVERLAP_THRESHOLD:
                overlap_flags[i] = True
                
    filtered_master = CLUSTER_MASTER[~overlap_flags].copy()
    return filtered_master

# BUILD CLUSTER WEIGHTS
def build_cluster_weights(CLUSTER_MASTER):
    cluster_weights_per_alert = {}
    for alert_type, group in CLUSTER_MASTER.groupby("alert_type"):
        cluster_weights_per_alert[alert_type] = group[["centroid_lat", "centroid_lon", "risk_score"]].to_dict(orient="records")
    return cluster_weights_per_alert

# FULL PIPELINE
def run_cluster_scoring_from_train(train_data, geofence_data=None):
    clusters, latest_time = build_candidate_clusters(train_data)
    merged_clusters = merge_clusters(clusters)
    CLUSTER_MASTER = validate_and_score(merged_clusters, latest_time)
    CLUSTER_MASTER_DF = pd.DataFrame(CLUSTER_MASTER.values())
    CLUSTER_MASTER_VALID = CLUSTER_MASTER_DF[CLUSTER_MASTER_DF["status"] == "VALID"].copy()

    if geofence_data is not None:
        FINAL_CLUSTER_MASTER = filter_clusters_geofence(CLUSTER_MASTER_VALID, geofence_data)
    else:
        FINAL_CLUSTER_MASTER = CLUSTER_MASTER_VALID.copy()

    return CLUSTER_MASTER_DF, FINAL_CLUSTER_MASTER

# RUN PIPELINE
CLUSTER_MASTER, FINAL_CLUSTER_MASTER = run_cluster_scoring_from_train(train_data, geofence_data)

cluster_weights_per_alert = build_cluster_weights(FINAL_CLUSTER_MASTER)

FINAL_CLUSTER_MASTER_df = FINAL_CLUSTER_MASTER[[
    'cluster_id', 'alert_type', 'risk_score', 'risk_band','centroid_lat', 'centroid_lon', 'first_seen', 'last_seen', 
    'events_25d', 'events_10d', 'events_5d', 'unique_trucks_30d', 'status', 
    'days_since_last' 
]].copy()


# ==================================================
# LOCATION SENSITIVITY CALCULATION
# ==================================================

from sklearn.neighbors import BallTree

INFLUENCE_RADIUS = 800

def compute_total_location_sensitivity_fast(
    realtime_data,
    cluster_weights_per_alert,
    alert_type_weights,
    radius_m,
):
    R = 6371000.0  # Earth radius (m)
    total_scores = np.zeros(len(realtime_data), dtype=np.float32)

    # Convert realtime coordinates to radians once
    realtime_coords = np.radians(realtime_data[["LAT", "LON"]].values.astype(np.float32))

    for alert_type, type_weight in alert_type_weights.items():
        clusters = cluster_weights_per_alert.get(alert_type, [])
        if not clusters:
            continue

        # Extract cluster info
        cluster_coords = np.radians(
            np.array([[c["centroid_lat"], c["centroid_lon"]] for c in clusters], dtype=np.float32)
        )
        cluster_risks = np.array([c["risk_score"] for c in clusters], dtype=np.float32)

        # Build BallTree for cluster centroids (Haversine metric)
        tree = BallTree(cluster_coords, metric="haversine")

        # Convert search radius to radians
        radius_radians = radius_m / R

        # Find clusters within influence radius for each realtime point
        indices_array = tree.query_radius(realtime_coords, r=radius_radians, return_distance=True)

        for i, (cluster_idx, dist_radians) in enumerate(zip(*indices_array)):
            if len(cluster_idx) == 0:
                continue

            # Convert to meters
            dist_m = dist_radians * R

            # Compute influence (linear decay)
            influence = np.clip(1 - dist_m / radius_m, 0, None)

            # Weighted sum for this point
            total_scores[i] += np.sum(cluster_risks[cluster_idx] * influence) * type_weight

    realtime_data["location_sensitivity"] = total_scores
    return realtime_data


# Define alert type weights
alert_type_weights = {
    "ROUTE_DEVIATION": 0.4,
    "STOPPAGE_VIOLATION": 0.3,
    "POWER_DISCONNECT": 0.2,
    "DEVICE_REMOVED": 0.1
}

# Compute location sensitivity
realtime_data = compute_total_location_sensitivity_fast(
    realtime_data,
    cluster_weights_per_alert,
    alert_type_weights,
    radius_m=INFLUENCE_RADIUS
)

Location_Sensitivity = realtime_data.groupby('INVOICE_NO')['location_sensitivity'].mean()

print("✅ Location sensitivity computed successfully.")


# ===============================
# COMBO RISK MAPPING
# ===============================

if not combo_df.empty:
    combo_df_agg = (
        combo_df.groupby("INVOICE_NO")["Last_Combo_Rule"]
        .apply(lambda x: x.dropna().iloc[-1] if len(x.dropna()) else None)
        .reset_index()
    )
    combo_df_agg["combo_risk"] = combo_df_agg["Last_Combo_Rule"].apply(
        lambda x: COMBO_RULES[x]["combo_delta"] / 100 if x in COMBO_RULES else 0
    )
    realtime_data = realtime_data.merge(
        combo_df_agg[["INVOICE_NO", "combo_risk"]], on="INVOICE_NO", how="left"
    )
    realtime_data["combo_risk"].fillna(0, inplace=True)
else:
    realtime_data["combo_risk"] = 0

combo_Risk_df = (
    realtime_data.groupby('INVOICE_NO', as_index=False)['combo_risk'].mean()
)


# COMBO TYPE COUNTS PER TRIP
if not combo_df.empty:
    combo_type_counts = (
        combo_df.groupby(['INVOICE_NO', 'Last_Combo_Rule'])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    # ✅ Add total combo count
    combo_type_counts["Total_Combo_Count"] = combo_type_counts.drop(columns=["INVOICE_NO"]).sum(axis=1)

    # ✅ Merge combo counts into realtime_data
    combo_Risk = combo_Risk_df.merge(combo_type_counts, on="INVOICE_NO", how="left")
    combo_Risk.fillna(0, inplace=True)

print("combo_Risk :", combo_Risk.columns)
print("✅ Combo Risk computed successfully.")



# ==============================================
# ATOMIC RISK CALCULATION AND MAPPING
# ==============================================

risk_map = {
    "ROUTE_DEVIATION": 0.2,
    "STOPPAGE_VIOLATION": 0.1,
    "DEVICE_REMOVED": 0.4,
    "POWER_DISCONNECT": 0.3,
}

realtime_data["atomic_risk"] = realtime_data["ALERT_TYPE"].map(risk_map)
Atomic_Risk = realtime_data.groupby('INVOICE_NO')['atomic_risk'].mean()

print("✅ Atomic Risk computed successfully.")


# ==============================================
# PREPARE COMPLETED TRIPS DATA
# ==============================================



Entity_Risk = TT_entity_risk_summary[["TT_NUMBER", "entity_risk"]].copy()

print("✅ Atomic Risk computed successfully.")
# ==============================================
# MERGE ALL RISK COMPONENTS
# ==============================================
completed_Trips = trip_Realtime_df[[
    'TRIP_NAME', 'TRIP_ID', 'SCHEDULED_TRIP_START_DATETIME', 'SCHEDULED_TRIP_END_DATETIME',
    'INVOICE_NO', 'TT_NUMBER', 'TRANSPORTER_CODE', 'ROUTE_NO', 'ZONE', 'LOCATION'
]].copy()

# Merge completed_Trips and Atomic_Risk
merged_df_1_2 = pd.merge(completed_Trips, Atomic_Risk, on='INVOICE_NO', how='left')

# Merge with combo_Risk
merged_df_1_2_3 = pd.merge(merged_df_1_2, combo_Risk, on='INVOICE_NO', how='left')

# Merge with Location_Sensitivity
merged_df_1_2_3_4 = pd.merge(merged_df_1_2_3, Location_Sensitivity, on='INVOICE_NO', how='left')

# Merge with Entity_Risk
final_merged_df = pd.merge(merged_df_1_2_3_4, Entity_Risk, on='TT_NUMBER', how='left')

# Fill NaN values with 0
final_merged_df['atomic_risk'].fillna(0, inplace=True)
final_merged_df['combo_risk'].fillna(0, inplace=True)
final_merged_df['location_sensitivity'].fillna(0, inplace=True)
final_merged_df['entity_risk'].fillna(0, inplace=True)


# ==========================================
# OVERALL RISK & CUMULATIVE RISK CALCULATION 
# ==========================================

# Normalize function
def normalize(series):
    if series.max() == series.min():
        return series * 0
    return (series - series.min()) / (series.max() - series.min())

# Normalize all risk components
final_merged_df["atomic_risk_norm"] = final_merged_df["atomic_risk"]
final_merged_df["combo_risk_norm"] = normalize(final_merged_df["combo_risk"])
final_merged_df["location_sensitivity_norm"] = normalize(final_merged_df["location_sensitivity"])
final_merged_df["entity_risk_norm"] = normalize(final_merged_df["entity_risk"])

# Define weights
w_atomic, w_combo, w_location, w_entity = 0.1, 0.4, 0.3, 0.2

# Calculate cumulative risk
final_merged_df["cumulative_risk"] = (
    w_atomic * final_merged_df["atomic_risk_norm"]
    + w_combo * final_merged_df["combo_risk_norm"]
    + w_location * final_merged_df["location_sensitivity_norm"]
    + w_entity * final_merged_df["entity_risk_norm"]
)

# PERCENTILE-BASED CUMULATIVE SCORE (0–100)
final_merged_df["Risk_Score"] = (
    final_merged_df["cumulative_risk"] * 100
).round(2)

Location_name_map = (
    master_df.drop_duplicates(subset=["TRANSPORTER_CODE"])
    .set_index("TRANSPORTER_CODE")["LOCATION_NAME"]
    .to_dict()
)

final_merged_df["LOCATION_NAME"] = final_merged_df["TRANSPORTER_CODE"].map(Location_name_map)


# Final output
final_merged = final_merged_df[[
    'TRIP_NAME', 'TRIP_ID', 'SCHEDULED_TRIP_START_DATETIME', 'SCHEDULED_TRIP_END_DATETIME', 
    'INVOICE_NO', 'TT_NUMBER', 'TRANSPORTER_CODE', 'ROUTE_NO', 'ZONE', 'LOCATION_NAME', 'Risk_Score'
]].copy()

print(final_merged_df.columns)
# ----------------------------------------------------------------------
# 1. Save Cluster master 
# ----------------------------------------------------------------------


# FINAL_CLUSTER_MASTER_df.to_csv("/Users/algofusion/hpcl_api/risk_sync/cluster_master.csv", index=False)
# print("len(FINAL_CLUSTER_MASTER_df) :", len(FINAL_CLUSTER_MASTER_df))
# print(f"✅ Cluster master data saved to cluster_master.csv")


# # ----------------------------------------------------------------------
# # 2. Save Combo Alerts 
# # ----------------------------------------------------------------------

# combo_df.to_csv("/Users/algofusion/hpcl_api/risk_sync/combo_alerts.csv", index=False)
# print("len(combo_df) :", len(combo_df))
# print(f"✅ Combo alerts data saved to combo_alerts.csv")


# # ----------------------------------------------------------------------
# # 3. Save Transporter Risk Score 
# # ----------------------------------------------------------------------
# Transporter_risk_summary.to_csv("/Users/algofusion/hpcl_api/risk_sync/transporter_risk_score.csv", index=False)
# print("len(Transporter_risk_summary) :", len(Transporter_risk_summary))
# print(f"✅ Transporter risk data saved to transporter_risk_score.csv")


# # ----------------------------------------------------------------------
# # 4. Save TT Risk Score 
# # ----------------------------------------------------------------------

# TT_risk_summary.to_csv("/Users/algofusion/hpcl_api/risk_sync/tt_risk_score.csv", index=False)
# print("len(TT_risk_summary) :", len(TT_risk_summary))
# print(f"✅ TT risk data saved to tt_risk_score.csv")


# # ----------------------------------------------------------------------
# # 5. Save Completed Trips Risk Score 
# # ----------------------------------------------------------------------
# final_merged.to_csv("/Users/algofusion/hpcl_api/risk_sync/completed_trips_risk_score.csv", index=False)
# print("len(final_merged) :", len(final_merged))
# print(f"✅ Completed trips risk score data saved to completed_trips_risk_score.csv")


def pandas_to_pg_dtypes(df: pd.DataFrame) -> dict:
    """Return a dict {column: sqlalchemy type} that matches the pandas df."""
    pg_types = {}
    for col, dtype in df.dtypes.items():
        str_dtype = str(dtype)
        if str_dtype.startswith('int'):
            pg_types[col] = Integer
        elif str_dtype.startswith('float'):
            pg_types[col] = Double
        elif str_dtype == 'bool':
            pg_types[col] = Boolean
        elif str_dtype == 'datetime64[ns]':
            pg_types[col] = DateTime
        else:
            # strings, categories, etc.
            max_len = df[col].astype(str).str.len().max()
            length = max(50, int(max_len) + 10) if pd.notna(max_len) else 255
            pg_types[col] = VARCHAR(length)
    return pg_types


def upsert_df(engine, df: pd.DataFrame, table_name: str, pk_columns: list):
    """
    Delete rows that already exist (identified by pk_columns) and insert the new ones.
    """
    if df.empty:
        return

    # Build WHERE clause for the DELETE
    pk_placeholders = " AND ".join([f'"{c}" = :{c.replace(" ", "_")}' for c in pk_columns])
    delete_sql = f'DELETE FROM public."{table_name}" WHERE {pk_placeholders};'

    with engine.begin() as conn:
        # 1. Delete existing rows
        for _, row in df[pk_columns].iterrows():
            params = {c.replace(" ", "_"): row[c] for c in pk_columns}
            conn.execute(text(delete_sql), params)

        # 2. Insert fresh rows
        df.to_sql(
            name=table_name,
            con=conn,
            schema='public',
            if_exists='append',
            index=False,
            method='multi'
        )

# ----------------------------------------------------------------------
# 1. Save Cluster master to database
# ----------------------------------------------------------------------
CLUSTER_TABLE = "cluster_master"
cluster_df = FINAL_CLUSTER_MASTER_df.copy()
cluster_df.columns = cluster_df.columns.str.lower()  # Convert to lowercase
cluster_pk = [col.lower() for col in ["cluster_id"]]  # Lowercase PK columns

cluster_dtypes = pandas_to_pg_dtypes(cluster_df)
cluster_df.to_sql(
    name=CLUSTER_TABLE,
    con=engine,
    schema='public',
    if_exists='replace',
    index=False,
    dtype=cluster_dtypes
)

upsert_df(engine, cluster_df, CLUSTER_TABLE, cluster_pk)
print(f"\n✅ Cluster master data saved to public.{CLUSTER_TABLE} ({len(cluster_df)} rows)")



# ----------------------------------------------------------------------
# 2. Save Combo Alerts to database
# ----------------------------------------------------------------------
COMBO_TABLE = "combo_alerts"
if not combo_df.empty:
    combo_df = combo_df.copy()
    combo_df.columns = combo_df.columns.str.lower()  # Convert to lowercase
    combo_dtypes = pandas_to_pg_dtypes(combo_df)
    combo_df.to_sql(
        name=COMBO_TABLE, con=engine, schema='public',
        if_exists='replace', index=False, dtype=combo_dtypes
    )
    print(f"✅ Combo alerts data saved to public.{COMBO_TABLE} ({len(combo_df)} rows)")

else:
    print(f"⚠️  No combo alerts detected, skipping {COMBO_TABLE} table creation")


# ----------------------------------------------------------------------
# 3. Save Transporter Risk Score to database
# ----------------------------------------------------------------------
TRANSPORTER_TABLE = "transporter_risk_score"
Transporter_risk_summary = Transporter_risk_summary.copy()
Transporter_risk_summary.columns = Transporter_risk_summary.columns.str.lower()  # Convert to lowercase
transporter_dtypes = pandas_to_pg_dtypes(Transporter_risk_summary)
Transporter_risk_summary.to_sql(
    name=TRANSPORTER_TABLE, con=engine, schema='public',
    if_exists='replace', index=False, dtype=transporter_dtypes
)
print(f"✅ Transporter risk data saved to public.{TRANSPORTER_TABLE} ({len(Transporter_risk_summary)} rows)")



# ----------------------------------------------------------------------
# 4. Save TT Risk Score to database
# ----------------------------------------------------------------------
TT_TABLE = "tt_risk_score"
TT_risk_summary = TT_risk_summary.copy()
TT_risk_summary.columns = TT_risk_summary.columns.str.lower()  # Convert to lowercase
tt_dtypes = pandas_to_pg_dtypes(TT_risk_summary)
TT_risk_summary.to_sql(
    name=TT_TABLE, con=engine, schema='public',
    if_exists='replace', index=False, dtype=tt_dtypes
)
print(f"✅ TT risk data saved to public.{TT_TABLE} ({len(TT_risk_summary)} rows)")



# ----------------------------------------------------------------------
# 5. Save Completed Trips Risk Score to database
# ----------------------------------------------------------------------
TABLE_NAME = "completed_trips_risk_score"
final_merged = final_merged.copy()
final_merged.columns = final_merged.columns.str.lower()  # Convert to lowercase
df_dtypes = pandas_to_pg_dtypes(final_merged)
final_merged.to_sql(
    name=TABLE_NAME, con=engine, schema='public',
    if_exists='replace', index=False, dtype=df_dtypes
)

print(f"✅ Completed trips risk score data saved to public.{TABLE_NAME} ({len(final_merged)} rows)")


engine.dispose()
print("\n" + "="*60)
print("DATABASE CONNECTION CLOSED")
print("="*60)
