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
import dnc_schema_enum

from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import *
from sqlalchemy.orm import *
from urdhva_base.postgresmodel import UrdhvaPostgresBase


class LocationMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'location_master'
    
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sop_id: Mapped[typing.Optional[str]] = mapped_column("sop_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bu: Mapped[typing.Optional[typing.Any]] = mapped_column("bu", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
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
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    bu: typing.Optional[dnc_schema_enum.LocationType] | None = None
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
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    bu: typing.Optional[dnc_schema_enum.LocationType] | None = None
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
    
    bu: Mapped[typing.Optional[typing.Any]] = mapped_column("bu", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    bu_id: Mapped[str] = mapped_column("bu_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    site_name: Mapped[str] = mapped_column("site_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    incharge_name: Mapped[typing.Optional[str]] = mapped_column("incharge_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    incharge_email: Mapped[typing.Optional[str]] = mapped_column("incharge_email", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    incharge_phone: Mapped[typing.Optional[str]] = mapped_column("incharge_phone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    incharge_role: Mapped[typing.Optional[str]] = mapped_column("incharge_role", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    notification_level: Mapped[typing.Optional[typing.Any]] = mapped_column("notification_level", String, index=False, nullable=True, default=None, primary_key=False, unique=False)


class RoleMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'role_master'
    
    bu: typing.Optional[dnc_schema_enum.LocationType] | None = None
    bu_id: str
    site_name: str
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    incharge_name: typing.Optional[str] = pydantic.Field("", **{})
    incharge_email: typing.Optional[str] = pydantic.Field("", **{})
    incharge_phone: typing.Optional[str] = pydantic.Field("", **{})
    incharge_role: typing.Optional[str] = pydantic.Field("", **{})
    notification_level: typing.Optional[dnc_schema_enum.NotificationLevel] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = RoleMasterSchema
        upsert_keys = []


class RoleMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'role_master'
    
    bu: typing.Optional[dnc_schema_enum.LocationType] | None = None
    bu_id: typing.Optional[str] | None = None
    site_name: typing.Optional[str] | None = None
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    incharge_name: typing.Optional[str] = pydantic.Field("", **{})
    incharge_email: typing.Optional[str] = pydantic.Field("", **{})
    incharge_phone: typing.Optional[str] = pydantic.Field("", **{})
    incharge_role: typing.Optional[str] = pydantic.Field("", **{})
    notification_level: typing.Optional[dnc_schema_enum.NotificationLevel] | None = None

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
    local_mpd_id: Mapped[typing.Optional[int]] = mapped_column("local_mpd_id", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
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
    local_mpd_id: typing.Optional[int] = pydantic.Field(0, **{})
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
    local_mpd_id: typing.Optional[int] = pydantic.Field(0, **{})
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
    alert_status: typing.Optional[dnc_schema_enum.AlertStatus] | None = None

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
    alert_status: typing.Optional[dnc_schema_enum.AlertStatus] | None = None

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


class overrideCreate(pydantic.BaseModel):
    days: typing.Optional[int] = pydantic.Field(0, **{})
    msg: typing.Optional[str] = pydantic.Field("", **{})


class AlertsSchema(UrdhvaPostgresBase):
    __tablename__ = 'alerts'
    
    _id: Mapped[str] = mapped_column("_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sop_id: Mapped[str] = mapped_column("sop_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    asset_id: Mapped[typing.Optional[typing.Any]] = mapped_column("asset_id", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    alert_type: Mapped[typing.Optional[str]] = mapped_column("alert_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_status: Mapped[typing.Optional[typing.Any]] = mapped_column("alert_status", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    alert_message: Mapped[typing.Optional[str]] = mapped_column("alert_message", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_name: Mapped[typing.Optional[str]] = mapped_column("interlock_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_name: Mapped[typing.Optional[str]] = mapped_column("device_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_type: Mapped[typing.Optional[str]] = mapped_column("device_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_device_id: Mapped[typing.Optional[str]] = mapped_column("location_device_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    priority: Mapped[typing.Optional[str]] = mapped_column("priority", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    district: Mapped[typing.Optional[str]] = mapped_column("district", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_history: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("alert_history", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    closed: Mapped[typing.Optional[bool]] = mapped_column("closed", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    closed_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("closed_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    incharge_role: Mapped[typing.Optional[str]] = mapped_column("incharge_role", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sales_area: Mapped[typing.Optional[str]] = mapped_column("sales_area", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    mail_sent_to: Mapped[typing.Optional[str]] = mapped_column("mail_sent_to", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sms_sent_to: Mapped[typing.Optional[str]] = mapped_column("sms_sent_to", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class AlertsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'alerts'
    
    _id: str
    sap_id: str
    sop_id: str
    asset_id: typing.Optional[assetDetailsCreate] | None = None
    alert_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_status: typing.Optional[dnc_schema_enum.AlertStatus] | None = None
    alert_message: typing.Optional[str] = pydantic.Field("", **{})
    interlock_name: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    location_device_id: typing.Optional[str] = pydantic.Field("", **{})
    priority: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    alert_history: typing.Optional[typing.List[Alert_HistoryCreate]] | None = None
    closed: typing.Optional[bool] = pydantic.Field(False, )
    closed_time: typing.Optional[datetime.datetime] | None = None
    incharge_role: typing.Optional[str] = pydantic.Field("", **{})
    sales_area: typing.Optional[str] = pydantic.Field("", **{})
    mail_sent_to: typing.Optional[str] = pydantic.Field("", **{})
    sms_sent_to: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = AlertsSchema
        upsert_keys = []


class Alerts(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'alerts'
    
    _id: typing.Optional[str] | None = None
    sap_id: typing.Optional[str] | None = None
    sop_id: typing.Optional[str] | None = None
    asset_id: typing.Optional[assetDetailsCreate] | None = None
    alert_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_status: typing.Optional[dnc_schema_enum.AlertStatus] | None = None
    alert_message: typing.Optional[str] = pydantic.Field("", **{})
    interlock_name: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    location_device_id: typing.Optional[str] = pydantic.Field("", **{})
    priority: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    alert_history: typing.Optional[typing.List[Alert_HistoryCreate]] | None = None
    closed: typing.Optional[bool] = pydantic.Field(False, )
    closed_time: typing.Optional[datetime.datetime] | None = None
    incharge_role: typing.Optional[str] = pydantic.Field("", **{})
    sales_area: typing.Optional[str] = pydantic.Field("", **{})
    mail_sent_to: typing.Optional[str] = pydantic.Field("", **{})
    sms_sent_to: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = AlertsSchema
        upsert_keys = []


class AlertsGetResp(pydantic.BaseModel):
    data: typing.List[Alerts]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Alerts_JustificationParams(pydantic.BaseModel):
    alert_id: str
    alert_msg: typing.Optional[str] = pydantic.Field("", **{})
    days: typing.Optional[int] = pydantic.Field(0, **{})
    justification_type: typing.Optional[str] = pydantic.Field("", **{})
    event_tags: typing.Optional[tagsCreate] | None = None


class Alerts_RejectParams(pydantic.BaseModel):
    alertid: typing.Optional[str] = pydantic.Field("", **{})
    alertmsg: typing.Optional[str] = pydantic.Field("", **{})
    days: typing.Optional[int] = pydantic.Field(0, **{})


class Alerts_ApproveParams(pydantic.BaseModel):
    alertid: typing.Optional[str] = pydantic.Field("", **{})
    alertmsg: typing.Optional[str] = pydantic.Field("", **{})
    days: typing.Optional[int] = pydantic.Field(0, **{})


class Alerts_OverrideParams(pydantic.BaseModel):
    alertid: str
    overridemsg: typing.Optional[overrideCreate] | None = None


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
    location_type: str
    data: typing.Optional[vtsDataCreate] | None = None


class vaDataCreate(pydantic.BaseModel):
    alert_type: str
    alert_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: str
    video_url: typing.Optional[str] = pydantic.Field("", **{})


class Va_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    location_type: str
    data: typing.Optional[typing.List[vaDataCreate]] | None = None


class crisDataCreate(pydantic.BaseModel):
    interlock_type: str
    interlock_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: str
    device_value: typing.Optional[str] = pydantic.Field("", **{})


class Cris_Ingest_DataParams(pydantic.BaseModel):
    vendor_id: str
    location_id: str
    data: typing.Optional[typing.List[crisDataCreate]] | None = None
    
    