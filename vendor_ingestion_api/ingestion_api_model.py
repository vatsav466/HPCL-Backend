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
    data: typing.Optional[vtsDataCreate] | None = None


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


class crisDataCreate(pydantic.BaseModel):
    interlock_type: str
    interlock_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: str
    device_value: typing.Optional[str] = pydantic.Field("", **{})


class Cris_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    data: typing.Optional[typing.List[crisDataCreate]] | None = None


class imsDataCreate(pydantic.BaseModel):
    vehicle_number: str
    violation_type: str
    initiated_date: str
    approved_date: typing.Optional[str] = pydantic.Field("", **{})
    approved_by: typing.Optional[str] = pydantic.Field("", **{})


class Ims_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: typing.Optional[ingestion_api_enum.BusinessUnit] | None = None
    data: typing.Optional[typing.List[imsDataCreate]] | None = None
    
    