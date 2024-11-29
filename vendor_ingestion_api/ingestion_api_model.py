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


class Vts_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    data: typing.List[vtsDataCreate]


class vaDataCreate(pydantic.BaseModel):
    alert_type: str
    alert_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: str
    video_url: typing.Optional[str] = pydantic.Field("", **{})


class Va_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    data: typing.Optional[typing.List[vaDataCreate]] | None = None


class productsDetailsCreate(pydantic.BaseModel):
    prod_code: typing.Optional[str] = pydantic.Field("", **{})
    uom: typing.Optional[str] = pydantic.Field("", **{})
    qty: typing.Optional[str] = pydantic.Field("", **{})


class crisDataCreate(pydantic.BaseModel):
    interlock_type: str
    interlock_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: str
    device_value: typing.Optional[str] = pydantic.Field("", **{})
    alert_id: str
    alert_status: ingestion_api_enum.AlertStatus
    tank_id: typing.Optional[str] = pydantic.Field("", **{})
    nozzle_id: typing.Optional[str] = pydantic.Field("", **{})
    pump_id: typing.Optional[str] = pydantic.Field("", **{})
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


class Emlock_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    data: typing.Optional[typing.List[emlockDataCreate]] | None = None


class Taslistener_Get_DataParams(pydantic.BaseModel):
    input_data: dict
    
    