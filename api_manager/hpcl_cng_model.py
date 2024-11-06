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
import hpcl_cng_enum

from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import *
from sqlalchemy.orm import *
from urdhva_base.postgresmodel import UrdhvaPostgresBase


class LocationMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'location_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bu_id: Mapped[typing.Optional[str]] = mapped_column("bu_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    name: Mapped[str] = mapped_column("name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    is_active: Mapped[typing.Optional[bool]] = mapped_column("is_active", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    activation_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("activation_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    activation_notes: Mapped[typing.Optional[str]] = mapped_column("activation_notes", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    activated_by: Mapped[typing.Optional[str]] = mapped_column("activated_by", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    deactivated_by: Mapped[typing.Optional[str]] = mapped_column("deactivated_by", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    deactivation_notes: Mapped[typing.Optional[str]] = mapped_column("deactivation_notes", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    health_status: Mapped[typing.Optional[typing.Any]] = mapped_column("health_status", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    health_notes: Mapped[typing.Optional[str]] = mapped_column("health_notes", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    scada_vendor: Mapped[typing.Optional[str]] = mapped_column("scada_vendor", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    scada_version: Mapped[typing.Optional[str]] = mapped_column("scada_version", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    scada_conn_status: Mapped[typing.Optional[bool]] = mapped_column("scada_conn_status", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    scada_conn_notes: Mapped[typing.Optional[str]] = mapped_column("scada_conn_notes", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    district: Mapped[typing.Optional[str]] = mapped_column("district", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    address: Mapped[typing.Optional[str]] = mapped_column("address", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    pincode: Mapped[typing.Optional[str]] = mapped_column("pincode", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    local_automation_vendor: Mapped[typing.Optional[str]] = mapped_column("local_automation_vendor", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    latitude: Mapped[typing.Optional[str]] = mapped_column("latitude", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    longitude: Mapped[typing.Optional[str]] = mapped_column("longitude", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class LocationMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'location_master'
    
    bu: hpcl_cng_enum.BusinessUnit
    sap_id: str
    bu_id: typing.Optional[str] = pydantic.Field("", **{})
    name: str
    is_active: typing.Optional[bool] = pydantic.Field(False, )
    activation_date: typing.Optional[datetime.datetime] | None = None
    activation_notes: typing.Optional[str] = pydantic.Field("", **{})
    activated_by: typing.Optional[str] = pydantic.Field("", **{})
    deactivated_by: typing.Optional[str] = pydantic.Field("", **{})
    deactivation_notes: typing.Optional[str] = pydantic.Field("", **{})
    health_status: typing.Optional[hpcl_cng_enum.LocationHealth] | None = None
    health_notes: typing.Optional[str] = pydantic.Field("", **{})
    scada_vendor: typing.Optional[str] = pydantic.Field("", **{})
    scada_version: typing.Optional[str] = pydantic.Field("", **{})
    scada_conn_status: typing.Optional[bool] = pydantic.Field(False, )
    scada_conn_notes: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    address: typing.Optional[str] = pydantic.Field("", **{})
    pincode: typing.Optional[str] = pydantic.Field("", **{})
    local_automation_vendor: typing.Optional[str] = pydantic.Field("", **{})
    latitude: typing.Optional[str] = pydantic.Field("", **{})
    longitude: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = LocationMasterSchema
        upsert_keys = []


class LocationMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'location_master'
    
    bu: typing.Optional[hpcl_cng_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    bu_id: typing.Optional[str] = pydantic.Field("", **{})
    name: typing.Optional[str] | None = None
    is_active: typing.Optional[bool] = pydantic.Field(False, )
    activation_date: typing.Optional[datetime.datetime] | None = None
    activation_notes: typing.Optional[str] = pydantic.Field("", **{})
    activated_by: typing.Optional[str] = pydantic.Field("", **{})
    deactivated_by: typing.Optional[str] = pydantic.Field("", **{})
    deactivation_notes: typing.Optional[str] = pydantic.Field("", **{})
    health_status: typing.Optional[hpcl_cng_enum.LocationHealth] | None = None
    health_notes: typing.Optional[str] = pydantic.Field("", **{})
    scada_vendor: typing.Optional[str] = pydantic.Field("", **{})
    scada_version: typing.Optional[str] = pydantic.Field("", **{})
    scada_conn_status: typing.Optional[bool] = pydantic.Field(False, )
    scada_conn_notes: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    address: typing.Optional[str] = pydantic.Field("", **{})
    pincode: typing.Optional[str] = pydantic.Field("", **{})
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


class Locationmaster_Upload_Location_MasterParams(pydantic.BaseModel):
    pass


class RoleMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'role_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    role: Mapped[str] = mapped_column("role", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    email: Mapped[str] = mapped_column("email", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    phone_no: Mapped[str] = mapped_column("phone_no", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    district: Mapped[typing.Optional[str]] = mapped_column("district", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    escalation_level: Mapped[typing.Optional[typing.Any]] = mapped_column("escalation_level", String, index=False, nullable=True, default=None, primary_key=False, unique=False)


class RoleMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'role_master'
    
    bu: hpcl_cng_enum.BusinessUnit
    sap_id: str
    location_name: str
    role: str
    email: str
    phone_no: str
    city: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    escalation_level: typing.Optional[hpcl_cng_enum.NotificationLevel] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = RoleMasterSchema
        upsert_keys = []


class RoleMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'role_master'
    
    bu: typing.Optional[hpcl_cng_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    location_name: typing.Optional[str] | None = None
    role: typing.Optional[str] | None = None
    email: typing.Optional[str] | None = None
    phone_no: typing.Optional[str] | None = None
    city: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    escalation_level: typing.Optional[hpcl_cng_enum.NotificationLevel] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = RoleMasterSchema
        upsert_keys = []


class RoleMasterGetResp(pydantic.BaseModel):
    data: typing.List[RoleMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Rolemaster_Upload_Role_MasterParams(pydantic.BaseModel):
    pass


class ROAssetMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'ro_asset_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bay_id: Mapped[int] = mapped_column("bay_id", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    mpd_id: Mapped[int] = mapped_column("mpd_id", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    tank_id: Mapped[int] = mapped_column("tank_id", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    nozzle_id: Mapped[int] = mapped_column("nozzle_id", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    global_nozzle_id: Mapped[int] = mapped_column("global_nozzle_id", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class ROAssetMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'ro_asset_master'
    
    bu: hpcl_cng_enum.BusinessUnit
    sap_id: str
    location_name: str
    bay_id: int
    mpd_id: int
    tank_id: int
    nozzle_id: int
    global_nozzle_id: int
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = ROAssetMasterSchema
        upsert_keys = []


class ROAssetMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'ro_asset_master'
    
    bu: typing.Optional[hpcl_cng_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    location_name: typing.Optional[str] | None = None
    bay_id: typing.Optional[int] | None = None
    mpd_id: typing.Optional[int] | None = None
    tank_id: typing.Optional[int] | None = None
    nozzle_id: typing.Optional[int] | None = None
    global_nozzle_id: typing.Optional[int] | None = None
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = ROAssetMasterSchema
        upsert_keys = []


class ROAssetMasterGetResp(pydantic.BaseModel):
    data: typing.List[ROAssetMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Roassetmaster_Upload_Ro_Asset_MasterParams(pydantic.BaseModel):
    pass


class TASAssetMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'tas_asset_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_type: Mapped[str] = mapped_column("device_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_desc: Mapped[str] = mapped_column("device_desc", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_tag: Mapped[str] = mapped_column("device_tag", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_id: Mapped[str] = mapped_column("device_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_key: Mapped[str] = mapped_column("device_key", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class TASAssetMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'tas_asset_master'
    
    bu: hpcl_cng_enum.BusinessUnit
    sap_id: str
    location_name: str
    device_type: str
    device_desc: str
    device_tag: str
    device_id: str
    device_key: str
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = TASAssetMasterSchema
        upsert_keys = []


class TASAssetMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'tas_asset_master'
    
    bu: typing.Optional[hpcl_cng_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    location_name: typing.Optional[str] | None = None
    device_type: typing.Optional[str] | None = None
    device_desc: typing.Optional[str] | None = None
    device_tag: typing.Optional[str] | None = None
    device_id: typing.Optional[str] | None = None
    device_key: typing.Optional[str] | None = None
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = TASAssetMasterSchema
        upsert_keys = []


class TASAssetMasterGetResp(pydantic.BaseModel):
    data: typing.List[TASAssetMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Tasassetmaster_Upload_Tas_Asset_MasterParams(pydantic.BaseModel):
    pass


class LPGAssetMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_asset_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_type: Mapped[str] = mapped_column("device_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_desc: Mapped[str] = mapped_column("device_desc", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_tag: Mapped[str] = mapped_column("device_tag", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_id: Mapped[str] = mapped_column("device_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_key: Mapped[str] = mapped_column("device_key", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class LPGAssetMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_asset_master'
    
    bu: hpcl_cng_enum.BusinessUnit
    sap_id: str
    location_name: str
    device_type: str
    device_desc: str
    device_tag: str
    device_id: str
    device_key: str
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = LPGAssetMasterSchema
        upsert_keys = []


class LPGAssetMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_asset_master'
    
    bu: typing.Optional[hpcl_cng_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    location_name: typing.Optional[str] | None = None
    device_type: typing.Optional[str] | None = None
    device_desc: typing.Optional[str] | None = None
    device_tag: typing.Optional[str] | None = None
    device_id: typing.Optional[str] | None = None
    device_key: typing.Optional[str] | None = None
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = LPGAssetMasterSchema
        upsert_keys = []


class LPGAssetMasterGetResp(pydantic.BaseModel):
    data: typing.List[LPGAssetMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Lpgassetmaster_Upload_Lpg_Asset_MasterParams(pydantic.BaseModel):
    pass


class assetDataSchema(UrdhvaPostgresBase):
    __tablename__ = 'asset_data'
    
    ro_id: Mapped[str] = mapped_column("ro_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    local_tank_id: Mapped[typing.Optional[int]] = mapped_column("local_tank_id", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    local_nozzle_id: Mapped[typing.Optional[int]] = mapped_column("local_nozzle_id", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    local_mpd_id: Mapped[typing.Optional[int]] = mapped_column("local_mpd_id", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    local_bay_id: Mapped[typing.Optional[int]] = mapped_column("local_bay_id", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    alert_status: Mapped[typing.Optional[typing.Any]] = mapped_column("alert_status", String, index=False, nullable=True, default=None, primary_key=False, unique=False)


class assetDataCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'asset_data'
    
    ro_id: str
    local_tank_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_nozzle_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_mpd_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_bay_id: typing.Optional[int] = pydantic.Field(0, **{})
    alert_status: typing.Optional[hpcl_cng_enum.AlertStatus] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = assetDataSchema
        upsert_keys = []


class assetData(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'asset_data'
    
    ro_id: typing.Optional[str] | None = None
    local_tank_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_nozzle_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_mpd_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_bay_id: typing.Optional[int] = pydantic.Field(0, **{})
    alert_status: typing.Optional[hpcl_cng_enum.AlertStatus] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = assetDataSchema
        upsert_keys = []


class assetDataGetResp(pydantic.BaseModel):
    data: typing.List[assetData]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class assetDetailsCreate(pydantic.BaseModel):
    asset_id: str
    data: typing.Optional[assetData] | None = None


class Alert_HistoryCreate(pydantic.BaseModel):
    alert_created_time: typing.Optional[datetime.datetime] | None = None
    local_tank_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_mpd_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_bay_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_nozzle_id: typing.Optional[int] = pydantic.Field(0, **{})
    entered_queue_at: typing.Optional[datetime.datetime] | None = None
    processed_at: typing.Optional[datetime.datetime] | None = None
    active: typing.Optional[str] = pydantic.Field("", **{})
    mail_sent_to: typing.Optional[str] = pydantic.Field("", **{})
    date: typing.Optional[datetime.datetime] | None = None


class tagsCreate(pydantic.BaseModel):
    is_atr_uploaded: typing.Optional[bool] = pydantic.Field(False, )
    is_maintenance_exception: typing.Optional[bool] = pydantic.Field(False, )
    is_revocation: typing.Optional[bool] = pydantic.Field(False, )
    no_exception: typing.Optional[bool] = pydantic.Field(False, )


class InterlockSchema(UrdhvaPostgresBase):
    __tablename__ = 'interlock'
    
    bu: Mapped[str] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sop_id: Mapped[str] = mapped_column("sop_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    interlock_name: Mapped[typing.Optional[str]] = mapped_column("interlock_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_name: Mapped[typing.Optional[str]] = mapped_column("device_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_type: Mapped[typing.Optional[str]] = mapped_column("device_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_id: Mapped[typing.Optional[str]] = mapped_column("device_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_status: Mapped[typing.Optional[typing.Any]] = mapped_column("interlock_status", String, index=False, nullable=True, default=None, primary_key=False, unique=False)


class InterlockCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'interlock'
    
    bu: str
    sap_id: str
    sop_id: str
    interlock_name: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    interlock_status: typing.Optional[hpcl_cng_enum.AlertStatus] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = InterlockSchema
        upsert_keys = []


class Interlock(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'interlock'
    
    bu: typing.Optional[str] | None = None
    sap_id: typing.Optional[str] | None = None
    sop_id: typing.Optional[str] | None = None
    interlock_name: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    interlock_status: typing.Optional[hpcl_cng_enum.AlertStatus] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = InterlockSchema
        upsert_keys = []


class InterlockGetResp(pydantic.BaseModel):
    data: typing.List[Interlock]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class AlertsSchema(UrdhvaPostgresBase):
    __tablename__ = 'alerts'
    
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sop_id: Mapped[typing.Optional[str]] = mapped_column("sop_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    asset_id: Mapped[typing.Optional[typing.Any]] = mapped_column("asset_id", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    alert_type: Mapped[typing.Optional[str]] = mapped_column("alert_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_id: Mapped[typing.Optional[str]] = mapped_column("alert_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_status: Mapped[typing.Optional[typing.Any]] = mapped_column("alert_status", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    alert_message: Mapped[typing.Optional[str]] = mapped_column("alert_message", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_name: Mapped[typing.Optional[str]] = mapped_column("interlock_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_id: Mapped[typing.Optional[str]] = mapped_column("interlock_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_name: Mapped[typing.Optional[str]] = mapped_column("device_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_type: Mapped[typing.Optional[str]] = mapped_column("device_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_device_id: Mapped[typing.Optional[str]] = mapped_column("location_device_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    priority: Mapped[typing.Optional[typing.Any]] = mapped_column("priority", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    district: Mapped[typing.Optional[str]] = mapped_column("district", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_history: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("alert_history", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    closed: Mapped[typing.Optional[bool]] = mapped_column("closed", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    closed_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("closed_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    mail_sent_to: Mapped[typing.Optional[str]] = mapped_column("mail_sent_to", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sms_sent_to: Mapped[typing.Optional[str]] = mapped_column("sms_sent_to", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    acted_by: Mapped[typing.Optional[str]] = mapped_column("acted_by", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    assigned_to: Mapped[typing.Optional[typing.List[str]]] = mapped_column("assigned_to", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)


class AlertsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'alerts'
    
    sap_id: str
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    asset_id: typing.Optional[assetDetailsCreate] | None = None
    alert_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_id: typing.Optional[str] = pydantic.Field("", **{})
    alert_status: typing.Optional[hpcl_cng_enum.AlertStatus] | None = None
    alert_message: typing.Optional[str] = pydantic.Field("", **{})
    interlock_name: typing.Optional[str] = pydantic.Field("", **{})
    interlock_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    location_device_id: typing.Optional[str] = pydantic.Field("", **{})
    priority: typing.Optional[hpcl_cng_enum.Priority] | None = None
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    alert_history: typing.Optional[typing.List[Alert_HistoryCreate]] | None = None
    closed: typing.Optional[bool] = pydantic.Field(False, )
    closed_time: typing.Optional[datetime.datetime] | None = None
    mail_sent_to: typing.Optional[str] = pydantic.Field("", **{})
    sms_sent_to: typing.Optional[str] = pydantic.Field("", **{})
    acted_by: typing.Optional[str] = pydantic.Field("", **{})
    assigned_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = AlertsSchema
        upsert_keys = []


class Alerts(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'alerts'
    
    sap_id: typing.Optional[str] | None = None
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    asset_id: typing.Optional[assetDetailsCreate] | None = None
    alert_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_id: typing.Optional[str] = pydantic.Field("", **{})
    alert_status: typing.Optional[hpcl_cng_enum.AlertStatus] | None = None
    alert_message: typing.Optional[str] = pydantic.Field("", **{})
    interlock_name: typing.Optional[str] = pydantic.Field("", **{})
    interlock_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    location_device_id: typing.Optional[str] = pydantic.Field("", **{})
    priority: typing.Optional[hpcl_cng_enum.Priority] | None = None
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    alert_history: typing.Optional[typing.List[Alert_HistoryCreate]] | None = None
    closed: typing.Optional[bool] = pydantic.Field(False, )
    closed_time: typing.Optional[datetime.datetime] | None = None
    mail_sent_to: typing.Optional[str] = pydantic.Field("", **{})
    sms_sent_to: typing.Optional[str] = pydantic.Field("", **{})
    acted_by: typing.Optional[str] = pydantic.Field("", **{})
    assigned_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = AlertsSchema
        upsert_keys = []


class AlertsGetResp(pydantic.BaseModel):
    data: typing.List[Alerts]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Alerts_Alert_ActionParams(pydantic.BaseModel):
    action_type: hpcl_cng_enum.AlertActionType
    alert_id: int
    action_msg: typing.Optional[str] = pydantic.Field("", **{})
    days: typing.Optional[int] = pydantic.Field(0, **{})
    justification_type: typing.Optional[str] = pydantic.Field("", **{})
    event_tags: typing.Optional[tagsCreate] | None = None


class ui_interface_dataCreate(pydantic.BaseModel):
    ui_component: typing.Optional[str] = pydantic.Field("", **{})
    is_component_display: typing.Optional[bool] = pydantic.Field(False, )


class api_task_dataCreate(pydantic.BaseModel):
    api_display_name: typing.Optional[str] = pydantic.Field("", **{})
    api_name: typing.Optional[str] = pydantic.Field("", **{})


class DNCRoleMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'dnc_role_master'
    
    role_id: Mapped[str] = mapped_column("role_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    role_name: Mapped[str] = mapped_column("role_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    source_system: Mapped[typing.List[str]] = mapped_column("source_system", ARRAY(String), index=False, nullable=False, default=None, primary_key=False, unique=False)
    parent_ui_interface: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("parent_ui_interface", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    child_ui_interface: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("child_ui_interface", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    tasks: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("tasks", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    conditions: Mapped[typing.Optional[dict]] = mapped_column("conditions", JSONB, index=False, nullable=True, default={}, primary_key=False, unique=False)


class DNCRoleMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'dnc_role_master'
    
    role_id: str
    role_name: str
    source_system: typing.List[str]
    parent_ui_interface: typing.Optional[typing.List[ui_interface_dataCreate]] | None = None
    child_ui_interface: typing.Optional[typing.List[ui_interface_dataCreate]] | None = None
    tasks: typing.Optional[typing.List[api_task_dataCreate]] | None = None
    conditions: typing.Optional[dict] = pydantic.Field({}, )

    class Config:
        collection_name = 'data_flow'
        schema_class = DNCRoleMasterSchema
        upsert_keys = []


class DNCRoleMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'dnc_role_master'
    
    role_id: typing.Optional[str] | None = None
    role_name: typing.Optional[str] | None = None
    source_system: typing.Optional[typing.List[str]] | None = None
    parent_ui_interface: typing.Optional[typing.List[ui_interface_dataCreate]] | None = None
    child_ui_interface: typing.Optional[typing.List[ui_interface_dataCreate]] | None = None
    tasks: typing.Optional[typing.List[api_task_dataCreate]] | None = None
    conditions: typing.Optional[dict] = pydantic.Field({}, )

    class Config:
        collection_name = 'data_flow'
        schema_class = DNCRoleMasterSchema
        upsert_keys = []


class DNCRoleMasterGetResp(pydantic.BaseModel):
    data: typing.List[DNCRoleMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Dncrolemaster_Get_Dnc_Role_MasterParams(pydantic.BaseModel):
    role_id: str
    source_system: str


class Dncrolemaster_Download_Dnc_Role_MasterParams(pydantic.BaseModel):
    condition: dict


class Dncrolemaster_Upload_Dnc_Role_MasterParams(pydantic.BaseModel):
    pass


class CEGRoleMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'ceg_role_master'
    
    role_id: Mapped[str] = mapped_column("role_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    role_name: Mapped[str] = mapped_column("role_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    source_system: Mapped[typing.List[str]] = mapped_column("source_system", ARRAY(String), index=False, nullable=False, default=None, primary_key=False, unique=False)
    parent_ui_interface: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("parent_ui_interface", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    child_ui_interface: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("child_ui_interface", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    tasks: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("tasks", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    conditions: Mapped[typing.Optional[dict]] = mapped_column("conditions", JSONB, index=False, nullable=True, default={}, primary_key=False, unique=False)


class CEGRoleMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'ceg_role_master'
    
    role_id: str
    role_name: str
    source_system: typing.List[str]
    parent_ui_interface: typing.Optional[typing.List[ui_interface_dataCreate]] | None = None
    child_ui_interface: typing.Optional[typing.List[ui_interface_dataCreate]] | None = None
    tasks: typing.Optional[typing.List[api_task_dataCreate]] | None = None
    conditions: typing.Optional[dict] = pydantic.Field({}, )

    class Config:
        collection_name = 'data_flow'
        schema_class = CEGRoleMasterSchema
        upsert_keys = []


class CEGRoleMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'ceg_role_master'
    
    role_id: typing.Optional[str] | None = None
    role_name: typing.Optional[str] | None = None
    source_system: typing.Optional[typing.List[str]] | None = None
    parent_ui_interface: typing.Optional[typing.List[ui_interface_dataCreate]] | None = None
    child_ui_interface: typing.Optional[typing.List[ui_interface_dataCreate]] | None = None
    tasks: typing.Optional[typing.List[api_task_dataCreate]] | None = None
    conditions: typing.Optional[dict] = pydantic.Field({}, )

    class Config:
        collection_name = 'data_flow'
        schema_class = CEGRoleMasterSchema
        upsert_keys = []


class CEGRoleMasterGetResp(pydantic.BaseModel):
    data: typing.List[CEGRoleMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Cegrolemaster_Get_Ceg_Role_MasterParams(pydantic.BaseModel):
    role_id: str
    source_system: str


class Cegrolemaster_Download_Ceg_Role_MasterParams(pydantic.BaseModel):
    condition: dict


class Cegrolemaster_Upload_Dnc_Role_MasterParams(pydantic.BaseModel):
    pass
    