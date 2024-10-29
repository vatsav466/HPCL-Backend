import typing
import datetime
import ipaddress
import fastapi
import pydantic
import shutil
import os
import urdhva_base
import urdhva_base.postgresmodel
import urdhva_base.queryparams
import urdhva_base.types
import dnc_schema_enum

from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import *
from sqlalchemy.orm import *
from urdhva_base.postgresmodel import UrdhvaPostgresBase


class LocationMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'location_master'
    
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bu: Mapped[str] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    district: Mapped[typing.Optional[str]] = mapped_column("district", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    pin_code: Mapped[typing.Optional[str]] = mapped_column("pin_code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    local_automation_vendor: Mapped[typing.Optional[str]] = mapped_column("local_automation_vendor", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    latitude: Mapped[typing.Optional[str]] = mapped_column("latitude", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    longitude: Mapped[typing.Optional[str]] = mapped_column("longitude", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class LocationMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'location_master'
    
    sap_id: str
    bu: str
    location_name: str
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    pin_code: typing.Optional[str] = pydantic.Field("", **{})
    local_automation_vendor: typing.Optional[str] = pydantic.Field("", **{})
    latitude: typing.Optional[str] = pydantic.Field("", **{})
    longitude: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = LocationMasterSchema
        upsert_keys = []


class LocationMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'location_master'
    
    sap_id: typing.Optional[str] | None = None
    bu: typing.Optional[str] | None = None
    location_name: typing.Optional[str] | None = None
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    pin_code: typing.Optional[str] = pydantic.Field("", **{})
    local_automation_vendor: typing.Optional[str] = pydantic.Field("", **{})
    latitude: typing.Optional[str] = pydantic.Field("", **{})
    longitude: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = LocationMasterSchema
        upsert_keys = []


class LocationMasterGetResp(pydantic.BaseModel):
    data: typing.List[LocationMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Locationmaster_Upload_MasterfileParams(pydantic.BaseModel):
    pass


class RoleMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'role_master'
    
    bu: Mapped[str] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bu_id: Mapped[str] = mapped_column("bu_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    site_name: Mapped[str] = mapped_column("site_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    incharge_name: Mapped[typing.Optional[str]] = mapped_column("incharge_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    incharge_email: Mapped[typing.Optional[str]] = mapped_column("incharge_email", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    incharge_phone: Mapped[typing.Optional[str]] = mapped_column("incharge_phone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    incharge_role: Mapped[typing.Optional[str]] = mapped_column("incharge_role", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    notification_level: Mapped[typing.Optional[str]] = mapped_column("notification_level", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class RoleMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'role_master'
    
    bu: str
    bu_id: str
    site_name: str
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    incharge_name: typing.Optional[str] = pydantic.Field("", **{})
    incharge_email: typing.Optional[str] = pydantic.Field("", **{})
    incharge_phone: typing.Optional[str] = pydantic.Field("", **{})
    incharge_role: typing.Optional[str] = pydantic.Field("", **{})
    notification_level: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = RoleMasterSchema
        upsert_keys = []


class RoleMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'role_master'
    
    bu: typing.Optional[str] | None = None
    bu_id: typing.Optional[str] | None = None
    site_name: typing.Optional[str] | None = None
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    incharge_name: typing.Optional[str] = pydantic.Field("", **{})
    incharge_email: typing.Optional[str] = pydantic.Field("", **{})
    incharge_phone: typing.Optional[str] = pydantic.Field("", **{})
    incharge_role: typing.Optional[str] = pydantic.Field("", **{})
    notification_level: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = RoleMasterSchema
        upsert_keys = []


class RoleMasterGetResp(pydantic.BaseModel):
    data: typing.List[RoleMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Rolemaster_Upload_MasterfileParams(pydantic.BaseModel):
    pass


class AssetMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'asset_master'
    
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    local_bay_id: Mapped[typing.Optional[int]] = mapped_column("local_bay_id", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    local_mpdid: Mapped[typing.Optional[int]] = mapped_column("local_mpdid", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    local_tank_id: Mapped[typing.Optional[int]] = mapped_column("local_tank_id", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    local_nozzle_id: Mapped[typing.Optional[int]] = mapped_column("local_nozzle_id", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    global_nozzle_id: Mapped[typing.Optional[int]] = mapped_column("global_nozzle_id", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    location_device_id: Mapped[typing.Optional[int]] = mapped_column("location_device_id", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    site_name: Mapped[typing.Optional[str]] = mapped_column("site_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class AssetMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'asset_master'
    
    sap_id: str
    local_bay_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_mpdid: typing.Optional[int] = pydantic.Field(0, **{})
    local_tank_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_nozzle_id: typing.Optional[int] = pydantic.Field(0, **{})
    global_nozzle_id: typing.Optional[int] = pydantic.Field(0, **{})
    location_device_id: typing.Optional[int] = pydantic.Field(0, **{})
    site_name: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = AssetMasterSchema
        upsert_keys = []


class AssetMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'asset_master'
    
    sap_id: typing.Optional[str] | None = None
    local_bay_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_mpdid: typing.Optional[int] = pydantic.Field(0, **{})
    local_tank_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_nozzle_id: typing.Optional[int] = pydantic.Field(0, **{})
    global_nozzle_id: typing.Optional[int] = pydantic.Field(0, **{})
    location_device_id: typing.Optional[int] = pydantic.Field(0, **{})
    site_name: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = AssetMasterSchema
        upsert_keys = []


class AssetMasterGetResp(pydantic.BaseModel):
    data: typing.List[AssetMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Assetmaster_Upload_MasterfileParams(pydantic.BaseModel):
    pass
    