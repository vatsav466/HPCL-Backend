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
import hpcl_ceg_enum

from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import *
from sqlalchemy.orm import *
from urdhva_base.postgresmodel import UrdhvaPostgresBase


class LocationMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'location_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    bu_id: Mapped[typing.Optional[str]] = mapped_column("bu_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    name: Mapped[str] = mapped_column("name", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
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
    district: Mapped[typing.Optional[str]] = mapped_column("district", String, index=True, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=True, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=True, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=True, nullable=True, default="", primary_key=False, unique=False)
    address: Mapped[typing.Optional[str]] = mapped_column("address", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    pincode: Mapped[typing.Optional[str]] = mapped_column("pincode", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    local_automation_vendor: Mapped[typing.Optional[str]] = mapped_column("local_automation_vendor", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    latitude: Mapped[typing.Optional[str]] = mapped_column("latitude", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    longitude: Mapped[typing.Optional[str]] = mapped_column("longitude", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class LocationMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'location_master'
    
    bu: hpcl_ceg_enum.BusinessUnit
    sap_id: str
    bu_id: typing.Optional[str] = pydantic.Field("", **{})
    name: str
    is_active: typing.Optional[bool] = pydantic.Field(False, )
    activation_date: typing.Optional[datetime.datetime] | None = None
    activation_notes: typing.Optional[str] = pydantic.Field("", **{})
    activated_by: typing.Optional[str] = pydantic.Field("", **{})
    deactivated_by: typing.Optional[str] = pydantic.Field("", **{})
    deactivation_notes: typing.Optional[str] = pydantic.Field("", **{})
    health_status: typing.Optional[hpcl_ceg_enum.LocationHealth] | None = None
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
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    bu_id: typing.Optional[str] = pydantic.Field("", **{})
    name: typing.Optional[str] | None = None
    is_active: typing.Optional[bool] = pydantic.Field(False, )
    activation_date: typing.Optional[datetime.datetime] | None = None
    activation_notes: typing.Optional[str] = pydantic.Field("", **{})
    activated_by: typing.Optional[str] = pydantic.Field("", **{})
    deactivated_by: typing.Optional[str] = pydantic.Field("", **{})
    deactivation_notes: typing.Optional[str] = pydantic.Field("", **{})
    health_status: typing.Optional[hpcl_ceg_enum.LocationHealth] | None = None
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


class Locationmaster_Download_Location_MasterParams(pydantic.BaseModel):
    pass


class Locationmaster_Fetch_Global_StatsParams(pydantic.BaseModel):
    bu: typing.Optional[typing.List[hpcl_ceg_enum.BusinessUnit]] | None = None


class Locationmaster_Download_TemplateParams(pydantic.BaseModel):
    pass


class RoleMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'role_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    user_name: Mapped[typing.Optional[str]] = mapped_column("user_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    role: Mapped[str] = mapped_column("role", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    email: Mapped[str] = mapped_column("email", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    phone_no: Mapped[str] = mapped_column("phone_no", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    city: Mapped[str] = mapped_column("city", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    district: Mapped[typing.Optional[str]] = mapped_column("district", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[str] = mapped_column("state", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[str] = mapped_column("zone", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    escalation_level: Mapped[typing.Optional[typing.Any]] = mapped_column("escalation_level", String, index=False, nullable=True, default=None, primary_key=False, unique=False)


class RoleMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'role_master'
    
    bu: hpcl_ceg_enum.BusinessUnit
    sap_id: str
    location_name: str
    user_name: typing.Optional[str] = pydantic.Field("", **{})
    role: str
    email: str
    phone_no: str
    city: str
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: str
    zone: str
    escalation_level: typing.Optional[hpcl_ceg_enum.NotificationLevel] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = RoleMasterSchema
        upsert_keys = []


class RoleMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'role_master'
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    location_name: typing.Optional[str] | None = None
    user_name: typing.Optional[str] = pydantic.Field("", **{})
    role: typing.Optional[str] | None = None
    email: typing.Optional[str] | None = None
    phone_no: typing.Optional[str] | None = None
    city: typing.Optional[str] | None = None
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] | None = None
    zone: typing.Optional[str] | None = None
    escalation_level: typing.Optional[hpcl_ceg_enum.NotificationLevel] | None = None

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


class Rolemaster_Download_Role_MasterParams(pydantic.BaseModel):
    pass


class Rolemaster_Download_TemplateParams(pydantic.BaseModel):
    pass


class ROAssetMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'ro_asset_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
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
    
    bu: hpcl_ceg_enum.BusinessUnit
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
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
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


class Roassetmaster_Download_Ro_Asset_MasterParams(pydantic.BaseModel):
    pass


class Roassetmaster_Download_TemplateParams(pydantic.BaseModel):
    pass


class TASAssetMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'tas_asset_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
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
    
    bu: hpcl_ceg_enum.BusinessUnit
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
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
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


class Tasassetmaster_Download_Tas_Asset_MasterParams(pydantic.BaseModel):
    pass


class Tasassetmaster_Download_TemplateParams(pydantic.BaseModel):
    pass


class LPGAssetMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_asset_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
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
    
    bu: hpcl_ceg_enum.BusinessUnit
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
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
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


class Lpgassetmaster_Download_Lpg_Asset_MasterParams(pydantic.BaseModel):
    pass


class Lpgassetmaster_Download_TemplateParams(pydantic.BaseModel):
    pass


class assetDataCreate(pydantic.BaseModel):
    ro_id: str
    local_tank_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_nozzle_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_mpd_id: typing.Optional[int] = pydantic.Field(0, **{})
    local_bay_id: typing.Optional[int] = pydantic.Field(0, **{})
    alert_status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None


class assetDetailsCreate(pydantic.BaseModel):
    asset_id: str
    data: typing.Optional[assetDataCreate] | None = None


class Alert_HistoryCreate(pydantic.BaseModel):
    device_data: typing.Optional[str] = pydantic.Field("", **{})
    allocated_time: typing.Optional[str] = pydantic.Field("", **{})
    processed_time: typing.Optional[str] = pydantic.Field("", **{})
    mail_sent_to: typing.Optional[str] = pydantic.Field("", **{})
    action_type: hpcl_ceg_enum.AlertActionType
    alert_status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None
    action_msg: str
    atr_uploaded: typing.Optional[bool] = pydantic.Field(False, )
    maintenance_exception: typing.Optional[bool] = pydantic.Field(False, )
    revocation: typing.Optional[bool] = pydantic.Field(False, )
    no_exception: typing.Optional[bool] = pydantic.Field(False, )
    is_approved: typing.Optional[bool] = pydantic.Field(False, )
    is_exc_approval_time_exp: typing.Optional[bool] = pydantic.Field(False, )
    is_raised: typing.Optional[bool] = pydantic.Field(False, )


class tagsCreate(pydantic.BaseModel):
    is_atr_uploaded: typing.Optional[bool] = pydantic.Field(False, )
    is_maintenance_exception: typing.Optional[bool] = pydantic.Field(False, )
    is_revocation: typing.Optional[bool] = pydantic.Field(False, )
    no_exception: typing.Optional[bool] = pydantic.Field(False, )
    is_approved: typing.Optional[bool] = pydantic.Field(False, )
    is_exc_approval_time_exp: typing.Optional[bool] = pydantic.Field(False, )
    is_raised: typing.Optional[bool] = pydantic.Field(False, )


class InterlockSchema(UrdhvaPostgresBase):
    __tablename__ = 'interlock'
    
    bu: Mapped[str] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sop_id: Mapped[str] = mapped_column("sop_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    interlock_name: Mapped[typing.Optional[str]] = mapped_column("interlock_name", String, index=True, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_name: Mapped[typing.Optional[str]] = mapped_column("device_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_type: Mapped[typing.Optional[str]] = mapped_column("device_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_id: Mapped[typing.Optional[str]] = mapped_column("device_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=True, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=True, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=True, nullable=True, default="", primary_key=False, unique=False)
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
    interlock_status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None

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
    interlock_status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = InterlockSchema
        upsert_keys = []


class InterlockGetResp(pydantic.BaseModel):
    data: typing.List[Interlock]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class EMLockSchema(UrdhvaPostgresBase):
    __tablename__ = 'em_lock'
    
    bu: Mapped[str] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    vehicle_number: Mapped[str] = mapped_column("vehicle_number", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    violation_type: Mapped[str] = mapped_column("violation_type", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    violation_count: Mapped[int] = mapped_column("violation_count", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    violation_start_date: Mapped[datetime.datetime] = mapped_column("violation_start_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    violation_history: Mapped[typing.Optional[typing.List[str]]] = mapped_column("violation_history", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    status: Mapped[typing.Any] = mapped_column("status", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class EMLockCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'em_lock'
    
    bu: str
    sap_id: str
    location_name: str
    vehicle_number: str
    violation_type: str
    violation_count: int
    violation_start_date: datetime.datetime
    violation_history: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    status: hpcl_ceg_enum.AlertStatus

    class Config:
        collection_name = 'data_flow'
        schema_class = EMLockSchema
        upsert_keys = []


class EMLock(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'em_lock'
    
    bu: typing.Optional[str] | None = None
    sap_id: typing.Optional[str] | None = None
    location_name: typing.Optional[str] | None = None
    vehicle_number: typing.Optional[str] | None = None
    violation_type: typing.Optional[str] | None = None
    violation_count: typing.Optional[int] | None = None
    violation_start_date: typing.Optional[datetime.datetime] | None = None
    violation_history: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = EMLockSchema
        upsert_keys = []


class EMLockGetResp(pydantic.BaseModel):
    data: typing.List[EMLock]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class VTSSchema(UrdhvaPostgresBase):
    __tablename__ = 'vts'
    
    bu: Mapped[str] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    vehicle_number: Mapped[str] = mapped_column("vehicle_number", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    violation_type: Mapped[str] = mapped_column("violation_type", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    violation_count: Mapped[int] = mapped_column("violation_count", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    violation_start_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("violation_start_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    violation_history: Mapped[typing.Optional[typing.List[str]]] = mapped_column("violation_history", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    block_duration: Mapped[typing.Optional[str]] = mapped_column("block_duration", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    block_msg: Mapped[typing.Optional[str]] = mapped_column("block_msg", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    status: Mapped[typing.Optional[typing.Any]] = mapped_column("status", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    report_duration: Mapped[typing.Optional[str]] = mapped_column("report_duration", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    total_trips: Mapped[typing.Optional[int]] = mapped_column("total_trips", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)


class VTSCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'vts'
    
    bu: str
    sap_id: str
    location_name: str
    vehicle_number: str
    violation_type: str
    violation_count: int
    violation_start_date: typing.Optional[datetime.datetime] | None = None
    violation_history: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    block_duration: typing.Optional[str] = pydantic.Field("", **{})
    block_msg: typing.Optional[str] = pydantic.Field("", **{})
    status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None
    report_duration: typing.Optional[str] = pydantic.Field("", **{})
    total_trips: typing.Optional[int] = pydantic.Field(0, **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = VTSSchema
        upsert_keys = []


class VTS(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'vts'
    
    bu: typing.Optional[str] | None = None
    sap_id: typing.Optional[str] | None = None
    location_name: typing.Optional[str] | None = None
    vehicle_number: typing.Optional[str] | None = None
    violation_type: typing.Optional[str] | None = None
    violation_count: typing.Optional[int] | None = None
    violation_start_date: typing.Optional[datetime.datetime] | None = None
    violation_history: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    block_duration: typing.Optional[str] = pydantic.Field("", **{})
    block_msg: typing.Optional[str] = pydantic.Field("", **{})
    status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None
    report_duration: typing.Optional[str] = pydantic.Field("", **{})
    total_trips: typing.Optional[int] = pydantic.Field(0, **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = VTSSchema
        upsert_keys = []


class VTSGetResp(pydantic.BaseModel):
    data: typing.List[VTS]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class AlertsSchema(UrdhvaPostgresBase):
    __tablename__ = 'alerts'
    
    bu: Mapped[typing.Optional[typing.Any]] = mapped_column("bu", String, index=True, nullable=True, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sop_id: Mapped[typing.Optional[str]] = mapped_column("sop_id", String, index=True, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    severity: Mapped[typing.Any] = mapped_column("severity", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    alert_status: Mapped[typing.Any] = mapped_column("alert_status", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    alert_state: Mapped[typing.Any] = mapped_column("alert_state", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    unique_id: Mapped[str] = mapped_column("unique_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    alert_section: Mapped[str] = mapped_column("alert_section", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    external_id: Mapped[typing.Optional[str]] = mapped_column("external_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_name: Mapped[typing.Optional[str]] = mapped_column("interlock_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_id: Mapped[typing.Optional[str]] = mapped_column("interlock_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_id: Mapped[typing.Optional[str]] = mapped_column("device_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_type: Mapped[typing.Optional[str]] = mapped_column("device_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_name: Mapped[typing.Optional[str]] = mapped_column("device_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_msg: Mapped[typing.Optional[str]] = mapped_column("device_msg", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    vehicle_number: Mapped[typing.Optional[str]] = mapped_column("vehicle_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    violation_type: Mapped[typing.Optional[str]] = mapped_column("violation_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_history: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("alert_history", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    last_sms_to: Mapped[typing.Optional[typing.List[str]]] = mapped_column("last_sms_to", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    last_mailed_to: Mapped[typing.Optional[typing.List[str]]] = mapped_column("last_mailed_to", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    last_escalated_to: Mapped[typing.Optional[typing.List[str]]] = mapped_column("last_escalated_to", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    last_notified_to: Mapped[typing.Optional[typing.List[str]]] = mapped_column("last_notified_to", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    assigned_to: Mapped[typing.Optional[str]] = mapped_column("assigned_to", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    assigned_to_role: Mapped[typing.Optional[str]] = mapped_column("assigned_to_role", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    district: Mapped[typing.Optional[str]] = mapped_column("district", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    raw_data: Mapped[typing.Optional[dict]] = mapped_column("raw_data", JSONB, index=False, nullable=True, default=pydantic.Field(default_factory=dict), primary_key=False, unique=False)
    r1_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("r1_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    r2_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("r2_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    r3_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("r3_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    indent_status: Mapped[typing.Optional[typing.Any]] = mapped_column("indent_status", String, index=False, nullable=True, default=None, primary_key=False, unique=False)


class AlertsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'alerts'
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    sap_id: str
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    severity: hpcl_ceg_enum.Severity
    alert_status: hpcl_ceg_enum.AlertStatus
    alert_state: hpcl_ceg_enum.AlertState
    unique_id: str
    alert_section: str
    external_id: typing.Optional[str] = pydantic.Field("", **{})
    interlock_name: typing.Optional[str] = pydantic.Field("", **{})
    interlock_id: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    device_msg: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_number: typing.Optional[str] = pydantic.Field("", **{})
    violation_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_history: typing.Optional[typing.List[Alert_HistoryCreate]] | None = None
    last_sms_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_mailed_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_escalated_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_notified_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    assigned_to: typing.Optional[str] = pydantic.Field("", **{})
    assigned_to_role: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    raw_data: typing.Optional[dict] = pydantic.Field(pydantic.Field(default_factory=dict), )
    r1_time: typing.Optional[datetime.datetime] | None = None
    r2_time: typing.Optional[datetime.datetime] | None = None
    r3_time: typing.Optional[datetime.datetime] | None = None
    indent_status: typing.Optional[hpcl_ceg_enum.IndentStatus] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = AlertsSchema
        upsert_keys = []


class Alerts(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'alerts'
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    severity: typing.Optional[hpcl_ceg_enum.Severity] | None = None
    alert_status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None
    alert_state: typing.Optional[hpcl_ceg_enum.AlertState] | None = None
    unique_id: typing.Optional[str] | None = None
    alert_section: typing.Optional[str] | None = None
    external_id: typing.Optional[str] = pydantic.Field("", **{})
    interlock_name: typing.Optional[str] = pydantic.Field("", **{})
    interlock_id: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    device_msg: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_number: typing.Optional[str] = pydantic.Field("", **{})
    violation_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_history: typing.Optional[typing.List[Alert_HistoryCreate]] | None = None
    last_sms_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_mailed_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_escalated_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_notified_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    assigned_to: typing.Optional[str] = pydantic.Field("", **{})
    assigned_to_role: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    raw_data: typing.Optional[dict] = pydantic.Field(pydantic.Field(default_factory=dict), )
    r1_time: typing.Optional[datetime.datetime] | None = None
    r2_time: typing.Optional[datetime.datetime] | None = None
    r3_time: typing.Optional[datetime.datetime] | None = None
    indent_status: typing.Optional[hpcl_ceg_enum.IndentStatus] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = AlertsSchema
        upsert_keys = []


class AlertsGetResp(pydantic.BaseModel):
    data: typing.List[Alerts]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Alerts_Alert_ActionParams(pydantic.BaseModel):
    action_type: hpcl_ceg_enum.AlertActionType
    alert_id: str
    action_msg: typing.Optional[str] = pydantic.Field("", **{})
    days: typing.Optional[int] = pydantic.Field(0, **{})
    justification_type: typing.Optional[str] = pydantic.Field("", **{})
    event_tags: typing.Optional[tagsCreate] | None = None


class CEMSLocationMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'cems_location_master'
    
    bu_id: Mapped[str] = mapped_column("bu_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bu: Mapped[typing.Optional[typing.Any]] = mapped_column("bu", String, index=True, nullable=True, default=None, primary_key=False, unique=False)
    device_name: Mapped[str] = mapped_column("device_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    location_id: Mapped[str] = mapped_column("location_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    source_id: Mapped[str] = mapped_column("source_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zonal_id: Mapped[str] = mapped_column("zonal_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    district: Mapped[typing.Optional[str]] = mapped_column("district", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class CEMSLocationMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'cems_location_master'
    
    bu_id: str
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    device_name: str
    location_name: str
    location_id: str
    source_id: str
    zonal_id: str
    district: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = CEMSLocationMasterSchema
        upsert_keys = []


class CEMSLocationMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'cems_location_master'
    
    bu_id: typing.Optional[str] | None = None
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    device_name: typing.Optional[str] | None = None
    location_name: typing.Optional[str] | None = None
    location_id: typing.Optional[str] | None = None
    source_id: typing.Optional[str] | None = None
    zonal_id: typing.Optional[str] | None = None
    district: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        schema_class = CEMSLocationMasterSchema
        upsert_keys = []


class CEMSLocationMasterGetResp(pydantic.BaseModel):
    data: typing.List[CEMSLocationMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Cemslocationmaster_Upload_Cems_Location_MasterParams(pydantic.BaseModel):
    pass


class Cemslocationmaster_Download_Cems_Location_MasterParams(pydantic.BaseModel):
    pass


class Cemslocationmaster_Download_TemplateParams(pydantic.BaseModel):
    pass


class CEMSQuantityMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'cems_quantity_master'
    
    quantity_name: Mapped[str] = mapped_column("quantity_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    quantity_id: Mapped[str] = mapped_column("quantity_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    unit: Mapped[str] = mapped_column("unit", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class CEMSQuantityMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'cems_quantity_master'
    
    quantity_name: str
    quantity_id: str
    unit: str

    class Config:
        collection_name = 'data_flow'
        schema_class = CEMSQuantityMasterSchema
        upsert_keys = []


class CEMSQuantityMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'cems_quantity_master'
    
    quantity_name: typing.Optional[str] | None = None
    quantity_id: typing.Optional[str] | None = None
    unit: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = CEMSQuantityMasterSchema
        upsert_keys = []


class CEMSQuantityMasterGetResp(pydantic.BaseModel):
    data: typing.List[CEMSQuantityMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class TagsCreate(pydantic.BaseModel):
    name: str
    value: str


class CredentialDataCreate(pydantic.BaseModel):
    host: typing.Optional[str] = pydantic.Field("", **{})
    port: typing.Optional[str] = pydantic.Field("", **{})
    access_key: typing.Optional[str] = pydantic.Field("", **{})
    secret_key: typing.Optional[urdhva_base.types.Secret] | None = None
    user_name: typing.Optional[str] = pydantic.Field("", **{})
    password: typing.Optional[urdhva_base.types.Secret] | None = None
    fingerprint: typing.Optional[str] = pydantic.Field("", **{})
    tenancy: typing.Optional[str] = pydantic.Field("", **{})
    key_file: typing.Optional[str] = pydantic.Field("", **{})
    key_content: typing.Optional[str] = pydantic.Field("", **{})
    client_id: typing.Optional[str] = pydantic.Field("", **{})
    client_secret: typing.Optional[urdhva_base.types.Secret] | None = None
    tenant_id: typing.Optional[str] = pydantic.Field("", **{})
    private_pass: typing.Optional[urdhva_base.types.Secret] | None = None
    private_key_pass: typing.Optional[urdhva_base.types.Secret] | None = None
    source_path: typing.Optional[str] = pydantic.Field("", **{})
    dest_path: typing.Optional[str] = pydantic.Field("", **{})
    api_key: typing.Optional[urdhva_base.types.Secret] | None = None
    database_name: typing.Optional[str] = pydantic.Field("", **{})
    other_details: typing.Optional[str] = pydantic.Field("", **{})


class CredsModelSchema(UrdhvaPostgresBase):
    __tablename__ = 'creds_model'
    
    name: Mapped[str] = mapped_column("name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    cred_model: Mapped[str] = mapped_column("cred_model", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    cred_type: Mapped[str] = mapped_column("cred_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    credentials: Mapped[typing.Any] = mapped_column("credentials", JSONB, index=False, nullable=False, default=None, primary_key=False, unique=False)


class CredsModelCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'creds_model'
    
    name: str
    cred_model: str
    cred_type: str
    credentials: CredentialDataCreate

    class Config:
        collection_name = 'data_flow'
        schema_class = CredsModelSchema
        upsert_keys = []


class CredsModel(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'creds_model'
    
    name: typing.Optional[str] | None = None
    cred_model: typing.Optional[str] | None = None
    cred_type: typing.Optional[str] | None = None
    credentials: typing.Optional[CredentialDataCreate] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = CredsModelSchema
        upsert_keys = []


class CredsModelGetResp(pydantic.BaseModel):
    data: typing.List[CredsModel]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Credsmodel_Create_CredentialParams(pydantic.BaseModel):
    record_id: typing.Optional[int] = pydantic.Field(0, **{})
    name: str
    cred_model: str
    cred_type: str
    tags: typing.Optional[typing.List[TagsCreate]] | None = None
    credentials: CredentialDataCreate


class Credsmodel_Load_CredsParams(pydantic.BaseModel):
    pass


class DashboardOrderCreate(pydantic.BaseModel):
    dashboard_id: int
    display_name: str


class GroupsDataCreate(pydantic.BaseModel):
    group_id: int
    name: str
    description: typing.Optional[str] = pydantic.Field("", **{})
    created_by: typing.Optional[str] = pydantic.Field("", **{})
    created_user: typing.Optional[str] = pydantic.Field("", **{})
    dashboard_order: typing.Optional[typing.List[DashboardOrderCreate]] | None = None
    group_order: typing.Optional[int] = pydantic.Field(0, **{})
    organization_id: int


class productsDetailsCreate(pydantic.BaseModel):
    prod_code: typing.Optional[str] = pydantic.Field("", **{})
    uom: typing.Optional[str] = pydantic.Field("", **{})
    qty: typing.Optional[str] = pydantic.Field("", **{})


class IndentDryOutSchema(UrdhvaPostgresBase):
    __tablename__ = 'indent_dry_out'
    
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    location_id: Mapped[str] = mapped_column("location_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_code: Mapped[str] = mapped_column("ro_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bu: Mapped[typing.Optional[typing.Any]] = mapped_column("bu", String, index=True, nullable=True, default=None, primary_key=False, unique=False)
    interlock_type: Mapped[str] = mapped_column("interlock_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    interlock_description: Mapped[typing.Optional[str]] = mapped_column("interlock_description", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_id: Mapped[str] = mapped_column("device_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    device_value: Mapped[typing.Optional[str]] = mapped_column("device_value", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_id: Mapped[str] = mapped_column("alert_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    alert_status: Mapped[typing.Any] = mapped_column("alert_status", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    tank_id: Mapped[typing.Optional[str]] = mapped_column("tank_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    nozzle_id: Mapped[typing.Optional[str]] = mapped_column("nozzle_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    pump_id: Mapped[typing.Optional[str]] = mapped_column("pump_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    indent_no: Mapped[typing.Optional[str]] = mapped_column("indent_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    products: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("products", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)


class IndentDryOutCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'indent_dry_out'
    
    sap_id: str
    location_id: str
    ro_code: str
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    interlock_type: str
    interlock_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: str
    device_value: typing.Optional[str] = pydantic.Field("", **{})
    alert_id: str
    alert_status: hpcl_ceg_enum.AlertStatus
    tank_id: typing.Optional[str] = pydantic.Field("", **{})
    nozzle_id: typing.Optional[str] = pydantic.Field("", **{})
    pump_id: typing.Optional[str] = pydantic.Field("", **{})
    indent_no: typing.Optional[str] = pydantic.Field("", **{})
    products: typing.Optional[typing.List[productsDetailsCreate]] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = IndentDryOutSchema
        upsert_keys = []


class IndentDryOut(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'indent_dry_out'
    
    sap_id: typing.Optional[str] | None = None
    location_id: typing.Optional[str] | None = None
    ro_code: typing.Optional[str] | None = None
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    interlock_type: typing.Optional[str] | None = None
    interlock_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] | None = None
    device_value: typing.Optional[str] = pydantic.Field("", **{})
    alert_id: typing.Optional[str] | None = None
    alert_status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None
    tank_id: typing.Optional[str] = pydantic.Field("", **{})
    nozzle_id: typing.Optional[str] = pydantic.Field("", **{})
    pump_id: typing.Optional[str] = pydantic.Field("", **{})
    indent_no: typing.Optional[str] = pydantic.Field("", **{})
    products: typing.Optional[typing.List[productsDetailsCreate]] | None = None

    class Config:
        collection_name = 'data_flow'
        schema_class = IndentDryOutSchema
        upsert_keys = []


class IndentDryOutGetResp(pydantic.BaseModel):
    data: typing.List[IndentDryOut]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class ScreensSchema(UrdhvaPostgresBase):
    __tablename__ = 'screens'
    
    screen_title: Mapped[str] = mapped_column("screen_title", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    dashboards: Mapped[typing.List[int]] = mapped_column("dashboards", ARRAY(Integer), index=False, nullable=False, default=None, primary_key=False, unique=False)
    created_by: Mapped[typing.Optional[str]] = mapped_column("created_by", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    updated_by: Mapped[typing.Optional[str]] = mapped_column("updated_by", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    x: Mapped[typing.Optional[int]] = mapped_column("x", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    y: Mapped[typing.Optional[int]] = mapped_column("y", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    w: Mapped[typing.Optional[int]] = mapped_column("w", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    h: Mapped[typing.Optional[int]] = mapped_column("h", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    static: Mapped[typing.Optional[bool]] = mapped_column("static", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    moved: Mapped[typing.Optional[bool]] = mapped_column("moved", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)


class ScreensCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'screens'
    
    screen_title: str
    dashboards: typing.List[int]
    created_by: typing.Optional[str] = pydantic.Field("", **{})
    updated_by: typing.Optional[str] = pydantic.Field("", **{})
    x: typing.Optional[int] = pydantic.Field(0, **{})
    y: typing.Optional[int] = pydantic.Field(0, **{})
    w: typing.Optional[int] = pydantic.Field(0, **{})
    h: typing.Optional[int] = pydantic.Field(0, **{})
    static: typing.Optional[bool] = pydantic.Field(False, )
    moved: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        schema_class = ScreensSchema
        upsert_keys = []


class Screens(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'screens'
    
    screen_title: typing.Optional[str] | None = None
    dashboards: typing.Optional[typing.List[int]] | None = None
    created_by: typing.Optional[str] = pydantic.Field("", **{})
    updated_by: typing.Optional[str] = pydantic.Field("", **{})
    x: typing.Optional[int] = pydantic.Field(0, **{})
    y: typing.Optional[int] = pydantic.Field(0, **{})
    w: typing.Optional[int] = pydantic.Field(0, **{})
    h: typing.Optional[int] = pydantic.Field(0, **{})
    static: typing.Optional[bool] = pydantic.Field(False, )
    moved: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        schema_class = ScreensSchema
        upsert_keys = []


class ScreensGetResp(pydantic.BaseModel):
    data: typing.List[Screens]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)
