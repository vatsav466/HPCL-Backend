import typing
import datetime
import ipaddress
import fastapi
import pydantic
import shutil
import os
import urdhva_base.postgresmodel
import urdhva_base.queryparams
import urdhva_base.types
import ingestion_api_enum

from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import *
from sqlalchemy.orm import *
from urdhva_base.postgresmodel import UrdhvaPostgresBase


class vtsDataCreate(pydantic.BaseModel):
    tl_number: str
    report_duration: str
    total_trips: typing.Optional[int] = pydantic.Field(0, **{})
    stoppage_violations_count: typing.Optional[int] = pydantic.Field(0, **{})
    route_deviation_count: typing.Optional[int] = pydantic.Field(0, **{})
    speed_violation_count: typing.Optional[int] = pydantic.Field(0, **{})
    main_supply_removal_count: typing.Optional[int] = pydantic.Field(0, **{})
    night_driving_count: typing.Optional[int] = pydantic.Field(0, **{})
    no_halt_zone_count: typing.Optional[int] = pydantic.Field(0, **{})
    device_offline_count: typing.Optional[int] = pydantic.Field(0, **{})
    device_tamper_count: typing.Optional[int] = pydantic.Field(0, **{})
    approved_by: typing.Optional[str] = pydantic.Field("", **{})
    invoice_number: typing.Optional[str] = pydantic.Field("", **{})


class vtsDataUpdatedCreate(pydantic.BaseModel):
    alert_id: str
    zone: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    terminal_code: typing.Optional[str] = pydantic.Field("", **{})
    trip_status: typing.Optional[str] = pydantic.Field("", **{})
    truck_regno: str
    violation_type: str
    threshold_limit: typing.Optional[str] = pydantic.Field("", **{})
    unit: typing.Optional[str] = pydantic.Field("", **{})
    min_violation_count: typing.Optional[str] = pydantic.Field("", **{})
    max_violation_count: typing.Optional[str] = pydantic.Field("", **{})
    trip_alert_count: typing.Optional[str] = pydantic.Field("", **{})
    violation_count: typing.Optional[str] = pydantic.Field("", **{})
    shortage_in_trip: typing.Optional[str] = pydantic.Field("", **{})
    cumulative_duration: typing.Optional[str] = pydantic.Field("", **{})
    trip_type: typing.Optional[str] = pydantic.Field("", **{})
    active: typing.Optional[str] = pydantic.Field("", **{})
    approval_status: typing.Optional[str] = pydantic.Field("", **{})
    start_location: typing.Optional[str] = pydantic.Field("", **{})
    end_location: typing.Optional[str] = pydantic.Field("", **{})
    distance: typing.Optional[str] = pydantic.Field("", **{})
    duration: typing.Optional[str] = pydantic.Field("", **{})
    from_date: typing.Optional[str] = pydantic.Field("", **{})
    to_date: typing.Optional[str] = pydantic.Field("", **{})
    latitude: typing.Optional[str] = pydantic.Field("", **{})
    longitude: typing.Optional[str] = pydantic.Field("", **{})
    endlatitude: typing.Optional[str] = pydantic.Field("", **{})
    endlongitude: typing.Optional[str] = pydantic.Field("", **{})


class vtsBlockedTruckOldCreate(pydantic.BaseModel):
    alert_id: str
    alert_type: str
    action_type: typing.Optional[str] = pydantic.Field("", **{})
    category: typing.Optional[str] = pydantic.Field("", **{})
    rca_reason: typing.Optional[str] = pydantic.Field("", **{})
    remarks: typing.Optional[str] = pydantic.Field("", **{})
    truck_regno: typing.Optional[str] = pydantic.Field("", **{})
    without_shortage_count: typing.Optional[str] = pydantic.Field("", **{})
    with_shortage_count: typing.Optional[str] = pydantic.Field("", **{})
    first_blocked_days: typing.Optional[str] = pydantic.Field("", **{})
    second_blocked_days: typing.Optional[str] = pydantic.Field("", **{})
    third_blocked_days: typing.Optional[str] = pydantic.Field("", **{})
    active: typing.Optional[bool] = pydantic.Field(False, )
    approval_status: typing.Optional[str] = pydantic.Field("", **{})
    blocked_datetime: typing.Optional[str] = pydantic.Field("", **{})
    unblocked_datetime: typing.Optional[str] = pydantic.Field("", **{})


class vtsBlockedTruckCreate(pydantic.BaseModel):
    tt_no: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    transporter_name: typing.Optional[str] = pydantic.Field("", **{})
    transporter_code: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_blocked_desc: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_blocked_start_date: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_blocked_end_date: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_blocked_instance_no: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_blocked_instance_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_type: typing.Optional[str] = pydantic.Field("", **{})


class Vts_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    data: typing.List[vtsDataCreate]


class Vts_Ingest_Data_Blocked_TrucksParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    data: typing.List[vtsBlockedTruckCreate]


class Vts_Ingest_Data_Un_Blocked_TrucksParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    data: typing.List[vtsBlockedTruckCreate]


class vaDataCreate(pydantic.BaseModel):
    alert_id: typing.Optional[str] = pydantic.Field("", **{})
    alert_timestamp: typing.Optional[str] = pydantic.Field("", **{})
    alert_type: str
    alert_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: str
    video_url: typing.Optional[str] = pydantic.Field("", **{})


class vaScoreCreate(pydantic.BaseModel):
    overall_score: typing.Optional[str] = pydantic.Field("", **{})


class Va_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    data: typing.Optional[typing.List[vaDataCreate]] | None = None


class Va_Ingest_Data_ScoreParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    data: typing.List[vaScoreCreate]


class productsDetailsCreate(pydantic.BaseModel):
    prod_code: typing.Optional[str] = pydantic.Field("", **{})
    uom: typing.Optional[str] = pydantic.Field("", **{})
    qty: typing.Optional[str] = pydantic.Field("", **{})


class crisDataCreate(pydantic.BaseModel):
    interlock_type: str
    interlock_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: str
    device_value: typing.Optional[str] = pydantic.Field("", **{})
    alarm_id: str
    tank_id: typing.Optional[str] = pydantic.Field("", **{})
    nozzle_id: typing.Optional[str] = pydantic.Field("", **{})
    pump_no: typing.Optional[str] = pydantic.Field("", **{})
    occurrence_date: typing.Optional[str] = pydantic.Field("", **{})
    closure_date: typing.Optional[str] = pydantic.Field("", **{})
    indent_no: typing.Optional[str] = pydantic.Field("", **{})
    products: typing.Optional[typing.List[productsDetailsCreate]] | None = None


class Cris_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    ro_code: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    data: typing.Optional[typing.List[crisDataCreate]] | None = None


class Ims_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None


class emlockDataCreate(pydantic.BaseModel):
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    vehicle_number: str
    violation_type: str
    initiated_date: str
    approved_date: typing.Optional[str] = pydantic.Field("", **{})
    approved_by: typing.Optional[str] = pydantic.Field("", **{})


class emlockVendorDataCreate(pydantic.BaseModel):
    location_type: str
    emlock_exception_id: str
    terminal_code: str
    truck_number: str
    exception_type: str
    ro_code: typing.Optional[str] = pydantic.Field("", **{})
    created_datetime: str


class Emlock_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    data: typing.Optional[typing.List[emlockVendorDataCreate]] | None = None


class Taslistener_Get_DataParams(pydantic.BaseModel):
    input_data: dict


