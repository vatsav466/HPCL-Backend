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


class RoleMapperCreate(pydantic.BaseModel):
    menu_name: str
    allowed_sub_menus: typing.Optional[typing.List[str]] = pydantic.Field("", **{})


class RolesSchema(UrdhvaPostgresBase):
    __tablename__ = 'roles'
    
    name: Mapped[str] = mapped_column("name", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    status: Mapped[bool] = mapped_column("status", Boolean, index=False, nullable=False, default=None, primary_key=False, unique=False)
    allowed_pages: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("allowed_pages", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(name, name="roles_name"),)


class RolesCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'roles'
    
    name: str
    status: bool
    allowed_pages: typing.Optional[typing.List[RoleMapperCreate]] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = RolesSchema
        upsert_keys = ['name']


class Roles(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'roles'
    
    name: typing.Optional[str] | None = None
    status: typing.Optional[bool] | None = None
    allowed_pages: typing.Optional[typing.List[RoleMapperCreate]] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = RolesSchema
        upsert_keys = ['name']


class RolesGetResp(pydantic.BaseModel):
    data: typing.List[Roles]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Roles_Create_RoleParams(pydantic.BaseModel):
    name: str
    allowed_pages: typing.Optional[typing.List[RoleMapperCreate]] | None = None

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Roles_Update_Role_StatusParams(pydantic.BaseModel):
    enable: bool
    role_name: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Roles_Get_All_PagesParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class UsersSchema(UrdhvaPostgresBase):
    __tablename__ = 'users'
    
    username: Mapped[str] = mapped_column("username", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    email: Mapped[str] = mapped_column("email", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    first_name: Mapped[str] = mapped_column("first_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    last_name: Mapped[str] = mapped_column("last_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    password: Mapped[typing.Optional[urdhva_base.types.Secret]] = mapped_column("password", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    employee_id: Mapped[str] = mapped_column("employee_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    employee_number: Mapped[typing.Optional[str]] = mapped_column("employee_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bu: Mapped[typing.List[typing.Any]] = mapped_column("bu", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[typing.List[str]] = mapped_column("sap_id", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    system_role: Mapped[typing.List[str]] = mapped_column("system_role", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    novex_role: Mapped[typing.List[str]] = mapped_column("novex_role", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[typing.Optional[typing.List[str]]] = mapped_column("region", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.List[str]] = mapped_column("state", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[typing.List[str]] = mapped_column("zone", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    sales_area: Mapped[typing.List[str]] = mapped_column("sales_area", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    escalation_level: Mapped[typing.Optional[typing.Any]] = mapped_column("escalation_level", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    is_ad_user: Mapped[bool] = mapped_column("is_ad_user", Boolean, index=False, nullable=False, default=None, primary_key=False, unique=False)
    status: Mapped[bool] = mapped_column("status", Boolean, index=False, nullable=False, default=None, primary_key=False, unique=False)
    manual_user: Mapped[bool] = mapped_column("manual_user", Boolean, index=False, nullable=False, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(username, employee_id, name="users_username_employee_id"),)


class UsersCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'users'
    
    username: str
    email: str
    first_name: str
    last_name: str
    password: typing.Optional[urdhva_base.types.Secret] | None = None
    employee_id: str
    employee_number: typing.Optional[str] = pydantic.Field("", **{})
    bu: typing.List[hpcl_ceg_enum.BusinessUnit]
    sap_id: typing.List[str]
    system_role: typing.List[str]
    novex_role: typing.List[str]
    region: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    state: typing.List[str]
    zone: typing.List[str]
    sales_area: typing.List[str]
    escalation_level: typing.Optional[hpcl_ceg_enum.NotificationLevel] | None = None
    is_ad_user: bool
    status: bool
    manual_user: bool

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = UsersSchema
        upsert_keys = ['username', 'employee_id']


class Users(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'users'
    
    username: typing.Optional[str] | None = None
    email: typing.Optional[str] | None = None
    first_name: typing.Optional[str] | None = None
    last_name: typing.Optional[str] | None = None
    password: typing.Optional[urdhva_base.types.Secret] | None = None
    employee_id: typing.Optional[str] | None = None
    employee_number: typing.Optional[str] = pydantic.Field("", **{})
    bu: typing.Optional[typing.List[hpcl_ceg_enum.BusinessUnit]] | None = None
    sap_id: typing.Optional[typing.List[str]] | None = None
    system_role: typing.Optional[typing.List[str]] | None = None
    novex_role: typing.Optional[typing.List[str]] | None = None
    region: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    state: typing.Optional[typing.List[str]] | None = None
    zone: typing.Optional[typing.List[str]] | None = None
    sales_area: typing.Optional[typing.List[str]] | None = None
    escalation_level: typing.Optional[hpcl_ceg_enum.NotificationLevel] | None = None
    is_ad_user: typing.Optional[bool] | None = None
    status: typing.Optional[bool] | None = None
    manual_user: typing.Optional[bool] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = UsersSchema
        upsert_keys = ['username', 'employee_id']


class UsersGetResp(pydantic.BaseModel):
    data: typing.List[Users]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Users_Fetch_UsersParams(pydantic.BaseModel):
    search_string: str
    limit: typing.Optional[int] = pydantic.Field(100, **{})
    skip: typing.Optional[int] = pydantic.Field(0, **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Users_Create_UserParams(pydantic.BaseModel):
    username: str
    password: str
    first_name: str
    last_name: str
    employee_id: str
    role: typing.List[str]

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Users_Update_User_StatusParams(pydantic.BaseModel):
    enable: bool
    username: str
    first_name: str
    last_name: str
    region: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    state: typing.List[str]
    zone: typing.List[str]
    sap_id: typing.List[str]
    bu: typing.List[hpcl_ceg_enum.BusinessUnit]
    sales_area: typing.List[str]
    novex_role: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Users_LoginParams(pydantic.BaseModel):
    username: str = pydantic.Field(**{'pattern': '^[a-zA-Z0-9_.-]+$'})
    password: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Users_LogoutParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class DataFiltersCreate(pydantic.BaseModel):
    key: str
    cond: str
    value: str


class LocationMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'location_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    bu_id: Mapped[typing.Optional[str]] = mapped_column("bu_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    ro_id: Mapped[typing.Optional[str]] = mapped_column("ro_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
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
    dealer_name: Mapped[typing.Optional[str]] = mapped_column("dealer_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    dealer_phone: Mapped[typing.Optional[str]] = mapped_column("dealer_phone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    dealer_email: Mapped[typing.Optional[str]] = mapped_column("dealer_email", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    local_automation_vendor: Mapped[typing.Optional[str]] = mapped_column("local_automation_vendor", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    latitude: Mapped[typing.Optional[str]] = mapped_column("latitude", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    longitude: Mapped[typing.Optional[str]] = mapped_column("longitude", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sales_area: Mapped[typing.Optional[str]] = mapped_column("sales_area", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    terminal_plant_id: Mapped[typing.Optional[str]] = mapped_column("terminal_plant_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    terminal_plant_name: Mapped[typing.Optional[str]] = mapped_column("terminal_plant_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    category: Mapped[typing.Optional[str]] = mapped_column("category", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    distributor_code: Mapped[typing.Optional[str]] = mapped_column("distributor_code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    distributor_name: Mapped[typing.Optional[str]] = mapped_column("distributor_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    round_trip_distance: Mapped[typing.Optional[int]] = mapped_column("round_trip_distance", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    location_onboard: Mapped[typing.Optional[bool]] = mapped_column("location_onboard", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)


class LocationMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'location_master'
    
    bu: hpcl_ceg_enum.BusinessUnit
    sap_id: str
    bu_id: typing.Optional[str] = pydantic.Field("", **{})
    ro_id: typing.Optional[str] = pydantic.Field("", **{})
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
    dealer_name: typing.Optional[str] = pydantic.Field("", **{})
    dealer_phone: typing.Optional[str] = pydantic.Field("", **{})
    dealer_email: typing.Optional[str] = pydantic.Field("", **{})
    local_automation_vendor: typing.Optional[str] = pydantic.Field("", **{})
    latitude: typing.Optional[str] = pydantic.Field("", **{})
    longitude: typing.Optional[str] = pydantic.Field("", **{})
    sales_area: typing.Optional[str] = pydantic.Field("", **{})
    terminal_plant_id: typing.Optional[str] = pydantic.Field("", **{})
    terminal_plant_name: typing.Optional[str] = pydantic.Field("", **{})
    category: typing.Optional[str] = pydantic.Field("", **{})
    distributor_code: typing.Optional[str] = pydantic.Field("", **{})
    distributor_name: typing.Optional[str] = pydantic.Field("", **{})
    round_trip_distance: typing.Optional[int] = pydantic.Field(0, **{})
    location_onboard: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LocationMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'zone', 'region', 'sales_area', 'sap_id']


class LocationMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'location_master'
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    bu_id: typing.Optional[str] = pydantic.Field("", **{})
    ro_id: typing.Optional[str] = pydantic.Field("", **{})
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
    dealer_name: typing.Optional[str] = pydantic.Field("", **{})
    dealer_phone: typing.Optional[str] = pydantic.Field("", **{})
    dealer_email: typing.Optional[str] = pydantic.Field("", **{})
    local_automation_vendor: typing.Optional[str] = pydantic.Field("", **{})
    latitude: typing.Optional[str] = pydantic.Field("", **{})
    longitude: typing.Optional[str] = pydantic.Field("", **{})
    sales_area: typing.Optional[str] = pydantic.Field("", **{})
    terminal_plant_id: typing.Optional[str] = pydantic.Field("", **{})
    terminal_plant_name: typing.Optional[str] = pydantic.Field("", **{})
    category: typing.Optional[str] = pydantic.Field("", **{})
    distributor_code: typing.Optional[str] = pydantic.Field("", **{})
    distributor_name: typing.Optional[str] = pydantic.Field("", **{})
    round_trip_distance: typing.Optional[int] = pydantic.Field(0, **{})
    location_onboard: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LocationMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'zone', 'region', 'sales_area', 'sap_id']


class LocationMasterGetResp(pydantic.BaseModel):
    data: typing.List[LocationMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Locationmaster_Upload_Location_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Locationmaster_Download_Location_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Locationmaster_Fetch_Global_StatsParams(pydantic.BaseModel):
    bu: typing.Optional[typing.List[hpcl_ceg_enum.BusinessUnit]] | None = None

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Locationmaster_Download_TemplateParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Locationmaster_Upload_Tags_DataParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Locationmaster_Update_Location_MasterParams(pydantic.BaseModel):
    sap_id: str
    name: str
    city: typing.Optional[str] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    address: typing.Optional[str] = pydantic.Field("", **{})
    pincode: typing.Optional[str] = pydantic.Field("", **{})
    sales_area: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Locationmaster_Get_Sod_Engineering_StatsParams(pydantic.BaseModel):
    sap_id: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Locationmaster_Location_Command_ControlParams(pydantic.BaseModel):
    sap_id: str
    action: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class RoleMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'role_master'
    
    bu: Mapped[typing.List[typing.Any]] = mapped_column("bu", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[typing.List[str]] = mapped_column("sap_id", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    user_name: Mapped[typing.Optional[str]] = mapped_column("user_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    employee_id: Mapped[str] = mapped_column("employee_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    system_role: Mapped[str] = mapped_column("system_role", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    novex_role: Mapped[str] = mapped_column("novex_role", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    email: Mapped[str] = mapped_column("email", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    phone_no: Mapped[str] = mapped_column("phone_no", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[typing.Optional[typing.List[str]]] = mapped_column("region", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.List[str]] = mapped_column("state", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[typing.List[str]] = mapped_column("zone", ARRAY(String), index=True, nullable=False, default=None, primary_key=False, unique=False)
    escalation_level: Mapped[typing.Optional[typing.Any]] = mapped_column("escalation_level", String, index=False, nullable=True, default=None, primary_key=False, unique=False)


class RoleMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'role_master'
    
    bu: typing.List[hpcl_ceg_enum.BusinessUnit]
    sap_id: typing.List[str]
    location_name: str
    user_name: typing.Optional[str] = pydantic.Field("", **{})
    employee_id: str
    system_role: str
    novex_role: str
    email: str
    phone_no: str
    region: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    state: typing.List[str]
    zone: typing.List[str]
    escalation_level: typing.Optional[hpcl_ceg_enum.NotificationLevel] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = RoleMasterSchema
        upsert_keys = []


class RoleMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'role_master'
    
    bu: typing.Optional[typing.List[hpcl_ceg_enum.BusinessUnit]] | None = None
    sap_id: typing.Optional[typing.List[str]] | None = None
    location_name: typing.Optional[str] | None = None
    user_name: typing.Optional[str] = pydantic.Field("", **{})
    employee_id: typing.Optional[str] | None = None
    system_role: typing.Optional[str] | None = None
    novex_role: typing.Optional[str] | None = None
    email: typing.Optional[str] | None = None
    phone_no: typing.Optional[str] | None = None
    region: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    state: typing.Optional[typing.List[str]] | None = None
    zone: typing.Optional[typing.List[str]] | None = None
    escalation_level: typing.Optional[hpcl_ceg_enum.NotificationLevel] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = RoleMasterSchema
        upsert_keys = []


class RoleMasterGetResp(pydantic.BaseModel):
    data: typing.List[RoleMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Rolemaster_Upload_Role_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Rolemaster_Download_Role_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Rolemaster_Download_TemplateParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ROAssetMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id', 'region']


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ROAssetMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id', 'region']


class ROAssetMasterGetResp(pydantic.BaseModel):
    data: typing.List[ROAssetMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Roassetmaster_Upload_Ro_Asset_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Roassetmaster_Download_Ro_Asset_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Roassetmaster_Download_TemplateParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = TASAssetMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id', 'region']


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = TASAssetMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id', 'region']


class TASAssetMasterGetResp(pydantic.BaseModel):
    data: typing.List[TASAssetMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Tasassetmaster_Upload_Tas_Asset_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Tasassetmaster_Download_Tas_Asset_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Tasassetmaster_Download_TemplateParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LPGAssetMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id', 'region']


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LPGAssetMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id', 'region']


class LPGAssetMasterGetResp(pydantic.BaseModel):
    data: typing.List[LPGAssetMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Lpgassetmaster_Upload_Lpg_Asset_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Lpgassetmaster_Download_Lpg_Asset_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Lpgassetmaster_Download_TemplateParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


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
    ims_datetime: typing.Optional[str] = pydantic.Field("", **{})
    prod_reqd_dt: typing.Optional[str] = pydantic.Field("", **{})
    mail_sent_to: typing.Optional[str] = pydantic.Field("", **{})
    action_by: typing.Optional[str] = pydantic.Field("", **{})
    action_type: hpcl_ceg_enum.AlertActionType
    alert_status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None
    action_msg: str
    remarks: typing.Optional[str] = pydantic.Field("", **{})
    doc_link: typing.Optional[str] = pydantic.Field("", **{})
    atr_uploaded: typing.Optional[bool] = pydantic.Field(False, )
    maintenance_exception: typing.Optional[bool] = pydantic.Field(False, )
    revocation: typing.Optional[bool] = pydantic.Field(False, )
    no_exception: typing.Optional[bool] = pydantic.Field(False, )
    is_approved: typing.Optional[bool] = pydantic.Field(False, )
    is_exc_approval_time_exp: typing.Optional[bool] = pydantic.Field(False, )
    is_raised: typing.Optional[bool] = pydantic.Field(False, )
    is_cancelled: typing.Optional[bool] = pydantic.Field(False, )
    is_allocated: typing.Optional[bool] = pydantic.Field(False, )
    is_sent_to_sap: typing.Optional[bool] = pydantic.Field(False, )
    is_order_placed: typing.Optional[bool] = pydantic.Field(False, )
    is_created: typing.Optional[bool] = pydantic.Field(False, )
    is_r1_swipe: typing.Optional[bool] = pydantic.Field(False, )
    is_r2_swipe: typing.Optional[bool] = pydantic.Field(False, )
    is_r3_swipe: typing.Optional[bool] = pydantic.Field(False, )
    is_delivered: typing.Optional[bool] = pydantic.Field(False, )
    is_tripped: typing.Optional[bool] = pydantic.Field(False, )
    is_justify: typing.Optional[bool] = pydantic.Field(False, )
    is_vts: typing.Optional[bool] = pydantic.Field(False, )
    is_blocked: typing.Optional[bool] = pydantic.Field(False, )
    is_unblocked: typing.Optional[bool] = pydantic.Field(False, )
    is_interrupt: typing.Optional[bool] = pydantic.Field(False, )
    is_extra_days: typing.Optional[bool] = pydantic.Field(False, )
    is_rejected: typing.Optional[bool] = pydantic.Field(False, )


class tagsCreate(pydantic.BaseModel):
    is_atr_uploaded: typing.Optional[bool] = pydantic.Field(False, )
    is_maintenance_exception: typing.Optional[bool] = pydantic.Field(False, )
    is_revocation: typing.Optional[bool] = pydantic.Field(False, )
    no_exception: typing.Optional[bool] = pydantic.Field(False, )
    is_approved: typing.Optional[bool] = pydantic.Field(False, )
    is_exc_approval_time_exp: typing.Optional[bool] = pydantic.Field(False, )
    is_raised: typing.Optional[bool] = pydantic.Field(False, )
    is_cancelled: typing.Optional[bool] = pydantic.Field(False, )
    is_allocated: typing.Optional[bool] = pydantic.Field(False, )
    is_sent_to_sap: typing.Optional[bool] = pydantic.Field(False, )
    is_order_placed: typing.Optional[bool] = pydantic.Field(False, )
    is_created: typing.Optional[bool] = pydantic.Field(False, )
    is_r1_swipe: typing.Optional[bool] = pydantic.Field(False, )
    is_r2_swipe: typing.Optional[bool] = pydantic.Field(False, )
    is_r3_swipe: typing.Optional[bool] = pydantic.Field(False, )
    is_vts: typing.Optional[bool] = pydantic.Field(False, )
    is_delivered: typing.Optional[bool] = pydantic.Field(False, )
    is_tripped: typing.Optional[bool] = pydantic.Field(False, )
    is_justify: typing.Optional[bool] = pydantic.Field(False, )
    is_blocked: typing.Optional[bool] = pydantic.Field(False, )
    is_un_blocked: typing.Optional[bool] = pydantic.Field(False, )
    is_interrupt: typing.Optional[bool] = pydantic.Field(False, )
    is_extra_days: typing.Optional[bool] = pydantic.Field(False, )


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = InterlockSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id', 'zone']


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = InterlockSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id', 'zone']


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = EMLockSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = EMLockSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = VTSSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = VTSSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


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
    alert_category: Mapped[typing.Optional[str]] = mapped_column("alert_category", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_status: Mapped[typing.Any] = mapped_column("alert_status", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    alert_state: Mapped[typing.Any] = mapped_column("alert_state", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    unique_id: Mapped[str] = mapped_column("unique_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    alert_section: Mapped[str] = mapped_column("alert_section", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    external_id: Mapped[typing.Optional[str]] = mapped_column("external_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_name: Mapped[typing.Optional[str]] = mapped_column("interlock_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_id: Mapped[typing.Optional[str]] = mapped_column("interlock_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_id: Mapped[typing.Optional[str]] = mapped_column("device_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    equipment_id: Mapped[typing.Optional[str]] = mapped_column("equipment_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sensor_id: Mapped[typing.Optional[str]] = mapped_column("sensor_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_type: Mapped[typing.Optional[str]] = mapped_column("device_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    equipment_type: Mapped[typing.Optional[str]] = mapped_column("equipment_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_name: Mapped[typing.Optional[str]] = mapped_column("device_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    equipment_name: Mapped[typing.Optional[str]] = mapped_column("equipment_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_msg: Mapped[typing.Optional[str]] = mapped_column("device_msg", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    vehicle_number: Mapped[typing.Optional[str]] = mapped_column("vehicle_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    violation_type: Mapped[typing.Optional[str]] = mapped_column("violation_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    clear_count: Mapped[typing.Optional[bool]] = mapped_column("clear_count", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    maintenance_time: Mapped[typing.Optional[str]] = mapped_column("maintenance_time", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    tt_load_number: Mapped[typing.Optional[str]] = mapped_column("tt_load_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    is_flagged_false: Mapped[typing.Optional[bool]] = mapped_column("is_flagged_false", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    rca: Mapped[typing.Optional[str]] = mapped_column("rca", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    rca_type: Mapped[typing.Optional[str]] = mapped_column("rca_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_history: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("alert_history", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    last_sms_to: Mapped[typing.Optional[typing.List[str]]] = mapped_column("last_sms_to", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    last_mailed_to: Mapped[typing.Optional[typing.List[str]]] = mapped_column("last_mailed_to", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    last_escalated_to: Mapped[typing.Optional[typing.List[str]]] = mapped_column("last_escalated_to", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    last_notified_to: Mapped[typing.Optional[typing.List[str]]] = mapped_column("last_notified_to", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    assigned_to: Mapped[typing.Optional[str]] = mapped_column("assigned_to", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    assigned_to_role: Mapped[typing.Optional[str]] = mapped_column("assigned_to_role", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    assigned_users: Mapped[typing.Optional[typing.List[str]]] = mapped_column("assigned_users", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    assigned_user_roles: Mapped[typing.Optional[typing.List[str]]] = mapped_column("assigned_user_roles", ARRAY(String), index=True, nullable=True, default="", primary_key=False, unique=False)
    district: Mapped[typing.Optional[str]] = mapped_column("district", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    state: Mapped[typing.Optional[str]] = mapped_column("state", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    city: Mapped[typing.Optional[str]] = mapped_column("city", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sales_area: Mapped[typing.Optional[str]] = mapped_column("sales_area", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    raw_data: Mapped[typing.Optional[dict]] = mapped_column("raw_data", JSONB, index=False, nullable=True, default=pydantic.Field(default_factory=dict), primary_key=False, unique=False)
    r1_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("r1_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    r2_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("r2_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    r3_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("r3_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    indent_status: Mapped[typing.Optional[typing.Any]] = mapped_column("indent_status", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    product_code: Mapped[typing.Optional[str]] = mapped_column("product_code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    indent_no: Mapped[typing.Optional[str]] = mapped_column("indent_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    dealer_id: Mapped[typing.Optional[str]] = mapped_column("dealer_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    workflow_instance_id: Mapped[typing.Optional[str]] = mapped_column("workflow_instance_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    workflow_datetime: Mapped[typing.Optional[datetime.datetime]] = mapped_column("workflow_datetime", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    terminal_plant_id: Mapped[typing.Optional[str]] = mapped_column("terminal_plant_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    terminal_plant_name: Mapped[typing.Optional[str]] = mapped_column("terminal_plant_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    servicing_plant_id: Mapped[typing.Optional[str]] = mapped_column("servicing_plant_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    servicing_plant_name: Mapped[typing.Optional[str]] = mapped_column("servicing_plant_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    progress_rate: Mapped[typing.Optional[int]] = mapped_column("progress_rate", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    category: Mapped[typing.Optional[str]] = mapped_column("category", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    indent_raised_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("indent_raised_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    dry_out_in_days: Mapped[typing.Optional[str]] = mapped_column("dry_out_in_days", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    origin_altid: Mapped[typing.Optional[str]] = mapped_column("origin_altid", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_message: Mapped[typing.Optional[str]] = mapped_column("alert_message", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    external_timestamp: Mapped[typing.Optional[datetime.datetime]] = mapped_column("external_timestamp", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    atg_ack: Mapped[typing.Optional[bool]] = mapped_column("atg_ack", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    emlock_ack: Mapped[typing.Optional[bool]] = mapped_column("emlock_ack", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    vts_return: Mapped[typing.Optional[bool]] = mapped_column("vts_return", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    atg_ack_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("atg_ack_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    transporter_name: Mapped[typing.Optional[str]] = mapped_column("transporter_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    transporter_code: Mapped[typing.Optional[str]] = mapped_column("transporter_code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    vehicle_blocked_start_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("vehicle_blocked_start_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    vehicle_blocked_end_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("vehicle_blocked_end_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    mark_as_false: Mapped[typing.Optional[bool]] = mapped_column("mark_as_false", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)


class AlertsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'alerts'
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    sap_id: str
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    severity: hpcl_ceg_enum.Severity
    alert_category: typing.Optional[str] = pydantic.Field("", **{})
    alert_status: hpcl_ceg_enum.AlertStatus
    alert_state: hpcl_ceg_enum.AlertState
    unique_id: str
    alert_section: str
    external_id: typing.Optional[str] = pydantic.Field("", **{})
    interlock_name: typing.Optional[str] = pydantic.Field("", **{})
    interlock_id: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] = pydantic.Field("", **{})
    equipment_id: typing.Optional[str] = pydantic.Field("", **{})
    sensor_id: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    equipment_type: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    equipment_name: typing.Optional[str] = pydantic.Field("", **{})
    device_msg: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_number: typing.Optional[str] = pydantic.Field("", **{})
    violation_type: typing.Optional[str] = pydantic.Field("", **{})
    clear_count: typing.Optional[bool] = pydantic.Field(False, )
    maintenance_time: typing.Optional[str] = pydantic.Field("", **{})
    tt_load_number: typing.Optional[str] = pydantic.Field("", **{})
    is_flagged_false: typing.Optional[bool] = pydantic.Field(False, )
    rca: typing.Optional[str] = pydantic.Field("", **{})
    rca_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_history: typing.Optional[typing.List[Alert_HistoryCreate]] | None = None
    last_sms_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_mailed_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_escalated_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_notified_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    assigned_to: typing.Optional[str] = pydantic.Field("", **{})
    assigned_to_role: typing.Optional[str] = pydantic.Field("", **{})
    assigned_users: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    assigned_user_roles: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    sales_area: typing.Optional[str] = pydantic.Field("", **{})
    raw_data: typing.Optional[dict] = pydantic.Field(pydantic.Field(default_factory=dict), )
    r1_time: typing.Optional[datetime.datetime] | None = None
    r2_time: typing.Optional[datetime.datetime] | None = None
    r3_time: typing.Optional[datetime.datetime] | None = None
    indent_status: typing.Optional[hpcl_ceg_enum.IndentStatus] | None = None
    product_code: typing.Optional[str] = pydantic.Field("", **{})
    indent_no: typing.Optional[str] = pydantic.Field("", **{})
    dealer_id: typing.Optional[str] = pydantic.Field("", **{})
    workflow_instance_id: typing.Optional[str] = pydantic.Field("", **{})
    workflow_datetime: typing.Optional[datetime.datetime] | None = None
    terminal_plant_id: typing.Optional[str] = pydantic.Field("", **{})
    terminal_plant_name: typing.Optional[str] = pydantic.Field("", **{})
    servicing_plant_id: typing.Optional[str] = pydantic.Field("", **{})
    servicing_plant_name: typing.Optional[str] = pydantic.Field("", **{})
    progress_rate: typing.Optional[int] = pydantic.Field(0, **{})
    category: typing.Optional[str] = pydantic.Field("", **{})
    indent_raised_date: typing.Optional[datetime.datetime] | None = None
    dry_out_in_days: typing.Optional[str] = pydantic.Field("", **{})
    origin_altid: typing.Optional[str] = pydantic.Field("", **{})
    alert_message: typing.Optional[str] = pydantic.Field("", **{})
    external_timestamp: typing.Optional[datetime.datetime] | None = None
    atg_ack: typing.Optional[bool] = pydantic.Field(False, )
    emlock_ack: typing.Optional[bool] = pydantic.Field(False, )
    vts_return: typing.Optional[bool] = pydantic.Field(False, )
    atg_ack_time: typing.Optional[datetime.datetime] | None = None
    transporter_name: typing.Optional[str] = pydantic.Field("", **{})
    transporter_code: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_blocked_start_date: typing.Optional[datetime.datetime] | None = None
    vehicle_blocked_end_date: typing.Optional[datetime.datetime] | None = None
    mark_as_false: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = AlertsSchema
        upsert_keys = []
        search_fields = ['bu', 'sap_id', 'sop_id', 'location_name', 'alert_section', 'alert_status', 'interlock_name', 'vehicle_number', 'device_name', 'device_id', 'device_msg', 'violation_type', 'rca_type', 'assigned_to', 'region', 'zone', 'indent_status']
        access_key_mapping = ['bu', 'zone', 'region', 'sales_area', 'sap_id', 'terminal_plant_id:sap_id']


class Alerts(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'alerts'
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    severity: typing.Optional[hpcl_ceg_enum.Severity] | None = None
    alert_category: typing.Optional[str] = pydantic.Field("", **{})
    alert_status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None
    alert_state: typing.Optional[hpcl_ceg_enum.AlertState] | None = None
    unique_id: typing.Optional[str] | None = None
    alert_section: typing.Optional[str] | None = None
    external_id: typing.Optional[str] = pydantic.Field("", **{})
    interlock_name: typing.Optional[str] = pydantic.Field("", **{})
    interlock_id: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] = pydantic.Field("", **{})
    equipment_id: typing.Optional[str] = pydantic.Field("", **{})
    sensor_id: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    equipment_type: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    equipment_name: typing.Optional[str] = pydantic.Field("", **{})
    device_msg: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_number: typing.Optional[str] = pydantic.Field("", **{})
    violation_type: typing.Optional[str] = pydantic.Field("", **{})
    clear_count: typing.Optional[bool] = pydantic.Field(False, )
    maintenance_time: typing.Optional[str] = pydantic.Field("", **{})
    tt_load_number: typing.Optional[str] = pydantic.Field("", **{})
    is_flagged_false: typing.Optional[bool] = pydantic.Field(False, )
    rca: typing.Optional[str] = pydantic.Field("", **{})
    rca_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_history: typing.Optional[typing.List[Alert_HistoryCreate]] | None = None
    last_sms_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_mailed_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_escalated_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    last_notified_to: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    assigned_to: typing.Optional[str] = pydantic.Field("", **{})
    assigned_to_role: typing.Optional[str] = pydantic.Field("", **{})
    assigned_users: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    assigned_user_roles: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    district: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    state: typing.Optional[str] = pydantic.Field("", **{})
    city: typing.Optional[str] = pydantic.Field("", **{})
    sales_area: typing.Optional[str] = pydantic.Field("", **{})
    raw_data: typing.Optional[dict] = pydantic.Field(pydantic.Field(default_factory=dict), )
    r1_time: typing.Optional[datetime.datetime] | None = None
    r2_time: typing.Optional[datetime.datetime] | None = None
    r3_time: typing.Optional[datetime.datetime] | None = None
    indent_status: typing.Optional[hpcl_ceg_enum.IndentStatus] | None = None
    product_code: typing.Optional[str] = pydantic.Field("", **{})
    indent_no: typing.Optional[str] = pydantic.Field("", **{})
    dealer_id: typing.Optional[str] = pydantic.Field("", **{})
    workflow_instance_id: typing.Optional[str] = pydantic.Field("", **{})
    workflow_datetime: typing.Optional[datetime.datetime] | None = None
    terminal_plant_id: typing.Optional[str] = pydantic.Field("", **{})
    terminal_plant_name: typing.Optional[str] = pydantic.Field("", **{})
    servicing_plant_id: typing.Optional[str] = pydantic.Field("", **{})
    servicing_plant_name: typing.Optional[str] = pydantic.Field("", **{})
    progress_rate: typing.Optional[int] = pydantic.Field(0, **{})
    category: typing.Optional[str] = pydantic.Field("", **{})
    indent_raised_date: typing.Optional[datetime.datetime] | None = None
    dry_out_in_days: typing.Optional[str] = pydantic.Field("", **{})
    origin_altid: typing.Optional[str] = pydantic.Field("", **{})
    alert_message: typing.Optional[str] = pydantic.Field("", **{})
    external_timestamp: typing.Optional[datetime.datetime] | None = None
    atg_ack: typing.Optional[bool] = pydantic.Field(False, )
    emlock_ack: typing.Optional[bool] = pydantic.Field(False, )
    vts_return: typing.Optional[bool] = pydantic.Field(False, )
    atg_ack_time: typing.Optional[datetime.datetime] | None = None
    transporter_name: typing.Optional[str] = pydantic.Field("", **{})
    transporter_code: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_blocked_start_date: typing.Optional[datetime.datetime] | None = None
    vehicle_blocked_end_date: typing.Optional[datetime.datetime] | None = None
    mark_as_false: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = AlertsSchema
        upsert_keys = []
        search_fields = ['bu', 'sap_id', 'sop_id', 'location_name', 'alert_section', 'alert_status', 'interlock_name', 'vehicle_number', 'device_name', 'device_id', 'device_msg', 'violation_type', 'rca_type', 'assigned_to', 'region', 'zone', 'indent_status']
        access_key_mapping = ['bu', 'zone', 'region', 'sales_area', 'sap_id', 'terminal_plant_id:sap_id']


class AlertsGetResp(pydantic.BaseModel):
    data: typing.List[Alerts]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Alerts_Alert_ActionParams(pydantic.BaseModel):
    bu: typing.Optional[str] = pydantic.Field("", **{})
    alert_section: typing.Optional[str] = pydantic.Field("", **{})
    action_type: hpcl_ceg_enum.AlertActionType
    alert_id: str
    action_msg: typing.Optional[str] = pydantic.Field("", **{})
    days: typing.Optional[int] = pydantic.Field(0, **{})
    justification_type: typing.Optional[str] = pydantic.Field("", **{})
    category: typing.Optional[str] = pydantic.Field("", **{})
    rca_reason: typing.Optional[str] = pydantic.Field("", **{})
    action_description: typing.Optional[str] = pydantic.Field("", **{})
    doc_link: typing.Optional[str] = pydantic.Field("", **{})
    acknowledged_by: typing.Optional[str] = pydantic.Field("", **{})
    load_number: typing.Optional[str] = pydantic.Field("", **{})
    fan_number: typing.Optional[str] = pydantic.Field("", **{})
    invoice_number: typing.Optional[str] = pydantic.Field("", **{})
    trip_type: typing.Optional[str] = pydantic.Field("", **{})
    event_tags: typing.Optional[tagsCreate] | None = None

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Alerts_Intitiate_Vts_ExceptionParams(pydantic.BaseModel):
    alert_id: str
    excep_msg: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Alerts_Get_Performance_IndexParams(pydantic.BaseModel):
    bu: str
    skip: typing.Optional[int] = pydantic.Field(0, **{})
    limit: typing.Optional[int] = pydantic.Field(0, **{})
    filters: typing.Optional[typing.List[DataFiltersCreate]] | None = None

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Alerts_Upload_DocumentParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Alerts_Stored_DocumentParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Alerts_Get_Frequent_Dryout_RoParams(pydantic.BaseModel):
    start_date: typing.Optional[datetime.datetime] | None = None
    end_date: typing.Optional[datetime.datetime] | None = None

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Alerts_Get_Frequent_Dryout_TerminalsParams(pydantic.BaseModel):
    start_date: typing.Optional[datetime.datetime] | None = None
    end_date: typing.Optional[datetime.datetime] | None = None

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Alerts_Get_Closed_Alerts_DetailsParams(pydantic.BaseModel):
    bu: str
    alert_id: str
    alert_section: str
    interlock_name: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = CEMSLocationMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'zone', 'region', 'location_id:sap_id']


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = CEMSLocationMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'zone', 'region', 'location_id:sap_id']


class CEMSLocationMasterGetResp(pydantic.BaseModel):
    data: typing.List[CEMSLocationMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Cemslocationmaster_Upload_Cems_Location_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Cemslocationmaster_Download_Cems_Location_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Cemslocationmaster_Download_TemplateParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = CEMSQuantityMasterSchema
        upsert_keys = []


class CEMSQuantityMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'cems_quantity_master'
    
    quantity_name: typing.Optional[str] | None = None
    quantity_id: typing.Optional[str] | None = None
    unit: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
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

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Credsmodel_Load_CredsParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


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


class IndentDryOutDataFiltersCreate(pydantic.BaseModel):
    key: str = pydantic.Field(**{'pattern': '^[a-zA-Z0-9_.\\-=" ]+$'})
    cond: str = pydantic.Field(**{'pattern': '^([a-zA-Z0-9_.\\-=! ]+|)$'})
    value: typing.List[str]


class DryOutHistorySchema(UrdhvaPostgresBase):
    __tablename__ = 'dry_out_history'
    
    bu: Mapped[str] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=True, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    name: Mapped[str] = mapped_column("name", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    start_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("start_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    end_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("end_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    product_no: Mapped[str] = mapped_column("product_no", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    item_name: Mapped[str] = mapped_column("item_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    plant_id: Mapped[str] = mapped_column("plant_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    plant_name: Mapped[str] = mapped_column("plant_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    category: Mapped[typing.Optional[str]] = mapped_column("category", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    status: Mapped[typing.Any] = mapped_column("status", String, index=True, nullable=False, default=None, primary_key=False, unique=False)


class DryOutHistoryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'dry_out_history'
    
    bu: str
    sap_id: str
    name: str
    start_time: typing.Optional[datetime.datetime] | None = None
    end_time: typing.Optional[datetime.datetime] | None = None
    product_no: str
    item_name: str
    plant_id: str
    plant_name: str
    category: typing.Optional[str] = pydantic.Field("", **{})
    status: hpcl_ceg_enum.AlertStatus

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = DryOutHistorySchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


class DryOutHistory(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'dry_out_history'
    
    bu: typing.Optional[str] | None = None
    sap_id: typing.Optional[str] | None = None
    name: typing.Optional[str] | None = None
    start_time: typing.Optional[datetime.datetime] | None = None
    end_time: typing.Optional[datetime.datetime] | None = None
    product_no: typing.Optional[str] | None = None
    item_name: typing.Optional[str] | None = None
    plant_id: typing.Optional[str] | None = None
    plant_name: typing.Optional[str] | None = None
    category: typing.Optional[str] = pydantic.Field("", **{})
    status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = DryOutHistorySchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


class DryOutHistoryGetResp(pydantic.BaseModel):
    data: typing.List[DryOutHistory]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class CarryFwdIndentSchema(UrdhvaPostgresBase):
    __tablename__ = 'carry_fwd_indent'
    
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    terminal_plant_id: Mapped[typing.Optional[str]] = mapped_column("terminal_plant_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    indent_no: Mapped[str] = mapped_column("indent_no", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    prod_reqd_dt: Mapped[datetime.datetime] = mapped_column("prod_reqd_dt", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    reported_date: Mapped[datetime.datetime] = mapped_column("reported_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    dry_out_in_days: Mapped[typing.Optional[str]] = mapped_column("dry_out_in_days", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    dried_out: Mapped[typing.Optional[bool]] = mapped_column("dried_out", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    category: Mapped[typing.Optional[str]] = mapped_column("category", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class CarryFwdIndentCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'carry_fwd_indent'
    
    sap_id: str
    terminal_plant_id: typing.Optional[str] = pydantic.Field("", **{})
    indent_no: str
    prod_reqd_dt: datetime.datetime
    reported_date: datetime.datetime
    dry_out_in_days: typing.Optional[str] = pydantic.Field("", **{})
    dried_out: typing.Optional[bool] = pydantic.Field(False, )
    category: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = CarryFwdIndentSchema
        upsert_keys = []


class CarryFwdIndent(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'carry_fwd_indent'
    
    sap_id: typing.Optional[str] | None = None
    terminal_plant_id: typing.Optional[str] = pydantic.Field("", **{})
    indent_no: typing.Optional[str] | None = None
    prod_reqd_dt: typing.Optional[datetime.datetime] | None = None
    reported_date: typing.Optional[datetime.datetime] | None = None
    dry_out_in_days: typing.Optional[str] = pydantic.Field("", **{})
    dried_out: typing.Optional[bool] = pydantic.Field(False, )
    category: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = CarryFwdIndentSchema
        upsert_keys = []


class CarryFwdIndentGetResp(pydantic.BaseModel):
    data: typing.List[CarryFwdIndent]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class IndentDryOutSchema(UrdhvaPostgresBase):
    __tablename__ = 'indent_dry_out'
    
    bu: Mapped[str] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=True, unique=False)
    site_id: Mapped[str] = mapped_column("site_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    fcc_code: Mapped[str] = mapped_column("fcc_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    tank_no: Mapped[str] = mapped_column("tank_no", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    product_no: Mapped[str] = mapped_column("product_no", String, index=True, nullable=False, default=None, primary_key=True, unique=False)
    item_name: Mapped[str] = mapped_column("item_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    capacity: Mapped[int] = mapped_column("capacity", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    volume: Mapped[typing.Optional[float]] = mapped_column("volume", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    ullage: Mapped[typing.Optional[float]] = mapped_column("ullage", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    avgsales_7days: Mapped[typing.Optional[float]] = mapped_column("avgsales_7days", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    stock_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("stock_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    status: Mapped[typing.Optional[int]] = mapped_column("status", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    daysstatus: Mapped[typing.Optional[int]] = mapped_column("daysstatus", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    lastrocdate: Mapped[typing.Optional[datetime.datetime]] = mapped_column("lastrocdate", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    executed_on: Mapped[typing.Optional[datetime.datetime]] = mapped_column("executed_on", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    pumpable_stock: Mapped[typing.Optional[float]] = mapped_column("pumpable_stock", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    rosapcode: Mapped[typing.Optional[int]] = mapped_column("rosapcode", Integer, index=True, nullable=True, default=0, primary_key=True, unique=False)
    product_grp: Mapped[typing.Optional[str]] = mapped_column("product_grp", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_status: Mapped[typing.Optional[typing.Any]] = mapped_column("interlock_status", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    interlock_created_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("interlock_created_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    interlock_closed_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("interlock_closed_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(bu, product_no, rosapcode, name="indent_dry_out_bu_product_no_rosapcode"),)


class IndentDryOutCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'indent_dry_out'
    
    bu: str
    site_id: str
    fcc_code: str
    tank_no: str
    product_no: str
    item_name: str
    capacity: int
    volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    ullage: typing.Optional[float] = pydantic.Field(0.0, **{})
    avgsales_7days: typing.Optional[float] = pydantic.Field(0.0, **{})
    stock_date: typing.Optional[datetime.datetime] | None = None
    status: typing.Optional[int] = pydantic.Field(0, **{})
    daysstatus: typing.Optional[int] = pydantic.Field(0, **{})
    lastrocdate: typing.Optional[datetime.datetime] | None = None
    executed_on: typing.Optional[datetime.datetime] | None = None
    pumpable_stock: typing.Optional[float] = pydantic.Field(0.0, **{})
    rosapcode: typing.Optional[int] = pydantic.Field(0, **{})
    product_grp: typing.Optional[str] = pydantic.Field("", **{})
    interlock_status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None
    interlock_created_date: typing.Optional[datetime.datetime] | None = None
    interlock_closed_date: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = IndentDryOutSchema
        upsert_keys = ['bu', 'product_no', 'rosapcode']
        access_key_mapping = ['bu', 'zone', 'region', 'sales_area', 'site_id:sap_id']


class IndentDryOut(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'indent_dry_out'
    
    bu: typing.Optional[str] | None = None
    site_id: typing.Optional[str] | None = None
    fcc_code: typing.Optional[str] | None = None
    tank_no: typing.Optional[str] | None = None
    product_no: typing.Optional[str] | None = None
    item_name: typing.Optional[str] | None = None
    capacity: typing.Optional[int] | None = None
    volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    ullage: typing.Optional[float] = pydantic.Field(0.0, **{})
    avgsales_7days: typing.Optional[float] = pydantic.Field(0.0, **{})
    stock_date: typing.Optional[datetime.datetime] | None = None
    status: typing.Optional[int] = pydantic.Field(0, **{})
    daysstatus: typing.Optional[int] = pydantic.Field(0, **{})
    lastrocdate: typing.Optional[datetime.datetime] | None = None
    executed_on: typing.Optional[datetime.datetime] | None = None
    pumpable_stock: typing.Optional[float] = pydantic.Field(0.0, **{})
    rosapcode: typing.Optional[int] = pydantic.Field(0, **{})
    product_grp: typing.Optional[str] = pydantic.Field("", **{})
    interlock_status: typing.Optional[hpcl_ceg_enum.AlertStatus] | None = None
    interlock_created_date: typing.Optional[datetime.datetime] | None = None
    interlock_closed_date: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = IndentDryOutSchema
        upsert_keys = ['bu', 'product_no', 'rosapcode']
        access_key_mapping = ['bu', 'zone', 'region', 'sales_area', 'site_id:sap_id']


class IndentDryOutGetResp(pydantic.BaseModel):
    data: typing.List[IndentDryOut]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Indentdryout_Sync_Data_From_Cris_To_CegParams(pydantic.BaseModel):
    source_connection: str
    destination_connection: str
    source_table: str
    destination_table: str
    source_schema: typing.Optional[str] = pydantic.Field("", **{})
    destination_schema: str
    conflict_columns: typing.Optional[typing.List[str]] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Dried_Out_PlantsParams(pydantic.BaseModel):
    filters: typing.List[IndentDryOutDataFiltersCreate]

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Alert_HistoryParams(pydantic.BaseModel):
    alert_id: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Dry_Out_StatsParams(pydantic.BaseModel):
    filters: typing.List[DataFiltersCreate]

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Indent_AnalysisParams(pydantic.BaseModel):
    filters: typing.List[DataFiltersCreate]

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Distinct_PlantParams(pydantic.BaseModel):
    bu: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Distinct_Location_DetailsParams(pydantic.BaseModel):
    bu: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    region: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    sales_area: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    plant: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    cat_a_dealers: typing.Optional[bool] = pydantic.Field(False, )
    dry_out_dealers: typing.Optional[bool] = pydantic.Field(False, )
    location_onboard: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Create_Dry_Out_AlertParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Sync_Ro_Daily_SalesParams(pydantic.BaseModel):
    from_date: datetime.datetime
    to_date: datetime.datetime

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Dry_Out_CountParams(pydantic.BaseModel):
    filters: typing.Optional[typing.List[IndentDryOutDataFiltersCreate]] | None = None

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Filtered_Location_DataParams(pydantic.BaseModel):
    request_parameter: str
    bu: str
    filters: typing.Optional[typing.List[IndentDryOutDataFiltersCreate]] | None = None

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Indent_DataParams(pydantic.BaseModel):
    filters: typing.List[DataFiltersCreate]

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Dried_Out_RoParams(pydantic.BaseModel):
    filters: typing.List[IndentDryOutDataFiltersCreate]

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Dried_Out_Ro_DataParams(pydantic.BaseModel):
    filters: typing.List[IndentDryOutDataFiltersCreate]

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Distinct_Ro_NameParams(pydantic.BaseModel):
    filters: typing.List[IndentDryOutDataFiltersCreate]

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Carry_Fwd_IndentsParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Get_Dryout_ReportParams(pydantic.BaseModel):
    dry_out_in_days: typing.List[str]

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Indentdryout_Generate_Dryout_Group_DataParams(pydantic.BaseModel):
    action: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class LpgOperationsSummarySchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_operations_summary'
    
    is_additional_carousel: Mapped[float] = mapped_column("is_additional_carousel", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    short_name: Mapped[str] = mapped_column("short_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    name: Mapped[str] = mapped_column("name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[str] = mapped_column("zone", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    carousel: Mapped[float] = mapped_column("carousel", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    filling_heads: Mapped[str] = mapped_column("filling_heads", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    carousel_count: Mapped[float] = mapped_column("carousel_count", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bottling_14_2kg: Mapped[float] = mapped_column("bottling_14_2kg", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bottling_19kg: Mapped[float] = mapped_column("bottling_19kg", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bottling_total: Mapped[float] = mapped_column("bottling_total", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    productivity_normal_production: Mapped[float] = mapped_column("productivity_normal_production", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    productivity_normal_stoppages: Mapped[float] = mapped_column("productivity_normal_stoppages", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    productivity_normal_productivity: Mapped[float] = mapped_column("productivity_normal_productivity", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    productivity_break_production: Mapped[float] = mapped_column("productivity_break_production", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    productivity_break_net_hours: Mapped[float] = mapped_column("productivity_break_net_hours", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    productivity_break_productivity: Mapped[float] = mapped_column("productivity_break_productivity", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    productivity_overtime_production: Mapped[float] = mapped_column("productivity_overtime_production", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    productivity_overtime_net_hours: Mapped[float] = mapped_column("productivity_overtime_net_hours", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    productivity_overtime_productivity: Mapped[float] = mapped_column("productivity_overtime_productivity", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    rejection_eld_percent: Mapped[float] = mapped_column("rejection_eld_percent", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    rejection_ort_percent: Mapped[float] = mapped_column("rejection_ort_percent", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    rejection_cs_percent: Mapped[float] = mapped_column("rejection_cs_percent", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    process_date: Mapped[datetime.datetime] = mapped_column("process_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    bu: Mapped[str] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[str] = mapped_column("region", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    site_area: Mapped[str] = mapped_column("site_area", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class LpgOperationsSummaryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_operations_summary'
    
    is_additional_carousel: float
    short_name: str
    name: str
    zone: str
    carousel: float
    filling_heads: str
    carousel_count: float
    bottling_14_2kg: float
    bottling_19kg: float
    bottling_total: float
    productivity_normal_production: float
    productivity_normal_stoppages: float
    productivity_normal_productivity: float
    productivity_break_production: float
    productivity_break_net_hours: float
    productivity_break_productivity: float
    productivity_overtime_production: float
    productivity_overtime_net_hours: float
    productivity_overtime_productivity: float
    rejection_eld_percent: float
    rejection_ort_percent: float
    rejection_cs_percent: float
    process_date: datetime.datetime
    bu: str
    sap_id: str
    region: str
    site_area: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgOperationsSummarySchema
        upsert_keys = []
        access_key_mapping = ['sap_id:sap_id', 'short_name:plant', 'zone:zone', 'region:region']


class LpgOperationsSummary(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_operations_summary'
    
    is_additional_carousel: typing.Optional[float] | None = None
    short_name: typing.Optional[str] | None = None
    name: typing.Optional[str] | None = None
    zone: typing.Optional[str] | None = None
    carousel: typing.Optional[float] | None = None
    filling_heads: typing.Optional[str] | None = None
    carousel_count: typing.Optional[float] | None = None
    bottling_14_2kg: typing.Optional[float] | None = None
    bottling_19kg: typing.Optional[float] | None = None
    bottling_total: typing.Optional[float] | None = None
    productivity_normal_production: typing.Optional[float] | None = None
    productivity_normal_stoppages: typing.Optional[float] | None = None
    productivity_normal_productivity: typing.Optional[float] | None = None
    productivity_break_production: typing.Optional[float] | None = None
    productivity_break_net_hours: typing.Optional[float] | None = None
    productivity_break_productivity: typing.Optional[float] | None = None
    productivity_overtime_production: typing.Optional[float] | None = None
    productivity_overtime_net_hours: typing.Optional[float] | None = None
    productivity_overtime_productivity: typing.Optional[float] | None = None
    rejection_eld_percent: typing.Optional[float] | None = None
    rejection_ort_percent: typing.Optional[float] | None = None
    rejection_cs_percent: typing.Optional[float] | None = None
    process_date: typing.Optional[datetime.datetime] | None = None
    bu: typing.Optional[str] | None = None
    sap_id: typing.Optional[str] | None = None
    region: typing.Optional[str] | None = None
    site_area: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgOperationsSummarySchema
        upsert_keys = []
        access_key_mapping = ['sap_id:sap_id', 'short_name:plant', 'zone:zone', 'region:region']


class LpgOperationsSummaryGetResp(pydantic.BaseModel):
    data: typing.List[LpgOperationsSummary]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Lpgoperationssummary_Get_Productions_RateParams(pydantic.BaseModel):
    dimension: str
    daywise: bool
    days: int
    top: typing.Optional[int] = pydantic.Field(0, **{})
    bottom: typing.Optional[int] = pydantic.Field(0, **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Lpgoperationssummary_Get_Productivity_RateParams(pydantic.BaseModel):
    dimension: str
    daywise: bool
    days: int
    top: typing.Optional[int] = pydantic.Field(0, **{})
    bottom: typing.Optional[int] = pydantic.Field(0, **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class LpgCsRejectionsSchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_cs_rejections'
    
    process_date: Mapped[datetime.datetime] = mapped_column("process_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    system_id: Mapped[float] = mapped_column("system_id", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    cyl_type: Mapped[str] = mapped_column("cyl_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    total: Mapped[float] = mapped_column("total", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    cylfilled: Mapped[float] = mapped_column("cylfilled", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    totalsortout: Mapped[float] = mapped_column("totalsortout", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    commerrorsortout: Mapped[float] = mapped_column("commerrorsortout", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sortoutpercentage: Mapped[float] = mapped_column("sortoutpercentage", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    plant: Mapped[str] = mapped_column("plant", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[str] = mapped_column("zone", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    execution__date: Mapped[datetime.datetime] = mapped_column("execution__date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    max_date: Mapped[datetime.datetime] = mapped_column("max_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class LpgCsRejectionsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_cs_rejections'
    
    process_date: datetime.datetime
    system_id: float
    cyl_type: str
    total: float
    cylfilled: float
    totalsortout: float
    commerrorsortout: float
    sortoutpercentage: float
    plant: str
    zone: str
    execution__date: datetime.datetime
    max_date: datetime.datetime
    sap_id: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgCsRejectionsSchema
        upsert_keys = []
        access_key_mapping = ['sap_id:sap_id', 'plant:plant', 'zone:zone']


class LpgCsRejections(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_cs_rejections'
    
    process_date: typing.Optional[datetime.datetime] | None = None
    system_id: typing.Optional[float] | None = None
    cyl_type: typing.Optional[str] | None = None
    total: typing.Optional[float] | None = None
    cylfilled: typing.Optional[float] | None = None
    totalsortout: typing.Optional[float] | None = None
    commerrorsortout: typing.Optional[float] | None = None
    sortoutpercentage: typing.Optional[float] | None = None
    plant: typing.Optional[str] | None = None
    zone: typing.Optional[str] | None = None
    execution__date: typing.Optional[datetime.datetime] | None = None
    max_date: typing.Optional[datetime.datetime] | None = None
    sap_id: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgCsRejectionsSchema
        upsert_keys = []
        access_key_mapping = ['sap_id:sap_id', 'plant:plant', 'zone:zone']


class LpgCsRejectionsGetResp(pydantic.BaseModel):
    data: typing.List[LpgCsRejections]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class LpgGdRejectionsSchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_gd_rejections'
    
    process_date: Mapped[datetime.datetime] = mapped_column("process_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    system_id: Mapped[float] = mapped_column("system_id", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    cyl_type: Mapped[str] = mapped_column("cyl_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    total: Mapped[float] = mapped_column("total", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sortout: Mapped[float] = mapped_column("sortout", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sortoutpercentage: Mapped[float] = mapped_column("sortoutpercentage", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    plant: Mapped[str] = mapped_column("plant", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[str] = mapped_column("zone", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    execution__date: Mapped[datetime.datetime] = mapped_column("execution__date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    max_date: Mapped[datetime.datetime] = mapped_column("max_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class LpgGdRejectionsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_gd_rejections'
    
    process_date: datetime.datetime
    system_id: float
    cyl_type: str
    total: float
    sortout: float
    sortoutpercentage: float
    plant: str
    zone: str
    execution__date: datetime.datetime
    max_date: datetime.datetime
    sap_id: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgGdRejectionsSchema
        upsert_keys = []
        access_key_mapping = ['sap_id:sap_id', 'plant:plant', 'zone:zone']


class LpgGdRejections(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_gd_rejections'
    
    process_date: typing.Optional[datetime.datetime] | None = None
    system_id: typing.Optional[float] | None = None
    cyl_type: typing.Optional[str] | None = None
    total: typing.Optional[float] | None = None
    sortout: typing.Optional[float] | None = None
    sortoutpercentage: typing.Optional[float] | None = None
    plant: typing.Optional[str] | None = None
    zone: typing.Optional[str] | None = None
    execution__date: typing.Optional[datetime.datetime] | None = None
    max_date: typing.Optional[datetime.datetime] | None = None
    sap_id: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgGdRejectionsSchema
        upsert_keys = []
        access_key_mapping = ['sap_id:sap_id', 'plant:plant', 'zone:zone']


class LpgGdRejectionsGetResp(pydantic.BaseModel):
    data: typing.List[LpgGdRejections]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class LpgPtRejectionsSchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_pt_rejections'
    
    process_date: Mapped[datetime.datetime] = mapped_column("process_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    system_id: Mapped[float] = mapped_column("system_id", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    cyl_type: Mapped[str] = mapped_column("cyl_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    total: Mapped[float] = mapped_column("total", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sortout: Mapped[float] = mapped_column("sortout", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sortoutpercentage: Mapped[float] = mapped_column("sortoutpercentage", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    plant: Mapped[str] = mapped_column("plant", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[str] = mapped_column("zone", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    execution__date: Mapped[datetime.datetime] = mapped_column("execution__date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    max_date: Mapped[datetime.datetime] = mapped_column("max_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class LpgPtRejectionsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_pt_rejections'
    
    process_date: datetime.datetime
    system_id: float
    cyl_type: str
    total: float
    sortout: float
    sortoutpercentage: float
    plant: str
    zone: str
    execution__date: datetime.datetime
    max_date: datetime.datetime
    sap_id: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgPtRejectionsSchema
        upsert_keys = []
        access_key_mapping = ['sap_id:sap_id', 'plant:plant', 'zone:zone']


class LpgPtRejections(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_pt_rejections'
    
    process_date: typing.Optional[datetime.datetime] | None = None
    system_id: typing.Optional[float] | None = None
    cyl_type: typing.Optional[str] | None = None
    total: typing.Optional[float] | None = None
    sortout: typing.Optional[float] | None = None
    sortoutpercentage: typing.Optional[float] | None = None
    plant: typing.Optional[str] | None = None
    zone: typing.Optional[str] | None = None
    execution__date: typing.Optional[datetime.datetime] | None = None
    max_date: typing.Optional[datetime.datetime] | None = None
    sap_id: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgPtRejectionsSchema
        upsert_keys = []
        access_key_mapping = ['sap_id:sap_id', 'plant:plant', 'zone:zone']


class LpgPtRejectionsGetResp(pydantic.BaseModel):
    data: typing.List[LpgPtRejections]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class LpgRejectionsSchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_rejections'


class LpgRejectionsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_rejections'

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgRejectionsSchema
        upsert_keys = []


class LpgRejections(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_rejections'

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgRejectionsSchema
        upsert_keys = []


class LpgRejectionsGetResp(pydantic.BaseModel):
    data: typing.List[LpgRejections]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Lpgrejections_Get_RejectionsParams(pydantic.BaseModel):
    dimension: str
    daywise: bool
    days: int
    top: typing.Optional[int] = pydantic.Field(0, **{})
    bottom: typing.Optional[int] = pydantic.Field(0, **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Lpgrejections_Get_Cs_RejectionsParams(pydantic.BaseModel):
    dimension: str
    daywise: bool
    days: int
    top: typing.Optional[int] = pydantic.Field(0, **{})
    bottom: typing.Optional[int] = pydantic.Field(0, **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Lpgrejections_Get_Gd_RejectionsParams(pydantic.BaseModel):
    dimension: str
    daywise: bool
    days: int
    top: typing.Optional[int] = pydantic.Field(0, **{})
    bottom: typing.Optional[int] = pydantic.Field(0, **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Lpgrejections_Get_Pt_RejectionsParams(pydantic.BaseModel):
    dimension: str
    daywise: bool
    days: int
    top: typing.Optional[int] = pydantic.Field(0, **{})
    bottom: typing.Optional[int] = pydantic.Field(0, **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class LpgSalesSummaryDataSchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_sales_summary_data'
    
    jde_distributor_code: Mapped[int] = mapped_column("jde_distributor_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    consumer_type: Mapped[str] = mapped_column("consumer_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    is_prepaid: Mapped[str] = mapped_column("is_prepaid", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    cyl_type: Mapped[str] = mapped_column("cyl_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    order_source_code: Mapped[str] = mapped_column("order_source_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_0_d: Mapped[int] = mapped_column("pending_0_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_1_d: Mapped[int] = mapped_column("pending_1_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_2_d: Mapped[int] = mapped_column("pending_2_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_3_d: Mapped[int] = mapped_column("pending_3_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_4_d: Mapped[int] = mapped_column("pending_4_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_5_d: Mapped[int] = mapped_column("pending_5_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_6_d: Mapped[int] = mapped_column("pending_6_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_7_d: Mapped[int] = mapped_column("pending_7_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_8_d: Mapped[int] = mapped_column("pending_8_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_9_d: Mapped[int] = mapped_column("pending_9_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_10_d: Mapped[int] = mapped_column("pending_10_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_11_d: Mapped[int] = mapped_column("pending_11_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_12_d: Mapped[int] = mapped_column("pending_12_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_13_d: Mapped[int] = mapped_column("pending_13_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_14_d: Mapped[int] = mapped_column("pending_14_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_15_d: Mapped[int] = mapped_column("pending_15_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending__beyond15_d: Mapped[int] = mapped_column("pending__beyond15_d", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    booking_received_yesterday: Mapped[int] = mapped_column("booking_received_yesterday", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    total_sales_yesterday: Mapped[int] = mapped_column("total_sales_yesterday", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    booking_received_today: Mapped[int] = mapped_column("booking_received_today", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    total_sales_today: Mapped[int] = mapped_column("total_sales_today", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sa_code: Mapped[int] = mapped_column("sa_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    state_code: Mapped[str] = mapped_column("state_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    district_code: Mapped[int] = mapped_column("district_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    taluka_code: Mapped[str] = mapped_column("taluka_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    city_code: Mapped[str] = mapped_column("city_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_code: Mapped[int] = mapped_column("ro_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sa_name: Mapped[str] = mapped_column("sa_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zo_code: Mapped[str] = mapped_column("zo_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_name: Mapped[str] = mapped_column("ro_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zo_name: Mapped[str] = mapped_column("zo_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    order_source_name: Mapped[str] = mapped_column("order_source_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    total__pending: Mapped[int] = mapped_column("total__pending", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_1_3_days: Mapped[int] = mapped_column("pending_1_3_days", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_4_7_days: Mapped[int] = mapped_column("pending_4_7_days", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    pending_8_15_days: Mapped[int] = mapped_column("pending_8_15_days", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    execution__date: Mapped[datetime.datetime] = mapped_column("execution__date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    execution__month: Mapped[str] = mapped_column("execution__month", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    execution__year: Mapped[int] = mapped_column("execution__year", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    month__year: Mapped[str] = mapped_column("month__year", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class LpgSalesSummaryDataCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_sales_summary_data'
    
    jde_distributor_code: int
    consumer_type: str
    is_prepaid: str
    cyl_type: str
    order_source_code: str
    pending_0_d: int
    pending_1_d: int
    pending_2_d: int
    pending_3_d: int
    pending_4_d: int
    pending_5_d: int
    pending_6_d: int
    pending_7_d: int
    pending_8_d: int
    pending_9_d: int
    pending_10_d: int
    pending_11_d: int
    pending_12_d: int
    pending_13_d: int
    pending_14_d: int
    pending_15_d: int
    pending__beyond15_d: int
    booking_received_yesterday: int
    total_sales_yesterday: int
    booking_received_today: int
    total_sales_today: int
    sa_code: int
    state_code: str
    district_code: int
    taluka_code: str
    city_code: str
    ro_code: int
    sa_name: str
    zo_code: str
    ro_name: str
    zo_name: str
    order_source_name: str
    total__pending: int
    pending_1_3_days: int
    pending_4_7_days: int
    pending_8_15_days: int
    execution__date: datetime.datetime
    execution__month: str
    execution__year: int
    month__year: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgSalesSummaryDataSchema
        upsert_keys = []
        access_key_mapping = ['JDEDistributorCode:sap_id', 'SAName:sales_area', 'ZOName:zone']


class LpgSalesSummaryData(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_sales_summary_data'
    
    jde_distributor_code: typing.Optional[int] | None = None
    consumer_type: typing.Optional[str] | None = None
    is_prepaid: typing.Optional[str] | None = None
    cyl_type: typing.Optional[str] | None = None
    order_source_code: typing.Optional[str] | None = None
    pending_0_d: typing.Optional[int] | None = None
    pending_1_d: typing.Optional[int] | None = None
    pending_2_d: typing.Optional[int] | None = None
    pending_3_d: typing.Optional[int] | None = None
    pending_4_d: typing.Optional[int] | None = None
    pending_5_d: typing.Optional[int] | None = None
    pending_6_d: typing.Optional[int] | None = None
    pending_7_d: typing.Optional[int] | None = None
    pending_8_d: typing.Optional[int] | None = None
    pending_9_d: typing.Optional[int] | None = None
    pending_10_d: typing.Optional[int] | None = None
    pending_11_d: typing.Optional[int] | None = None
    pending_12_d: typing.Optional[int] | None = None
    pending_13_d: typing.Optional[int] | None = None
    pending_14_d: typing.Optional[int] | None = None
    pending_15_d: typing.Optional[int] | None = None
    pending__beyond15_d: typing.Optional[int] | None = None
    booking_received_yesterday: typing.Optional[int] | None = None
    total_sales_yesterday: typing.Optional[int] | None = None
    booking_received_today: typing.Optional[int] | None = None
    total_sales_today: typing.Optional[int] | None = None
    sa_code: typing.Optional[int] | None = None
    state_code: typing.Optional[str] | None = None
    district_code: typing.Optional[int] | None = None
    taluka_code: typing.Optional[str] | None = None
    city_code: typing.Optional[str] | None = None
    ro_code: typing.Optional[int] | None = None
    sa_name: typing.Optional[str] | None = None
    zo_code: typing.Optional[str] | None = None
    ro_name: typing.Optional[str] | None = None
    zo_name: typing.Optional[str] | None = None
    order_source_name: typing.Optional[str] | None = None
    total__pending: typing.Optional[int] | None = None
    pending_1_3_days: typing.Optional[int] | None = None
    pending_4_7_days: typing.Optional[int] | None = None
    pending_8_15_days: typing.Optional[int] | None = None
    execution__date: typing.Optional[datetime.datetime] | None = None
    execution__month: typing.Optional[str] | None = None
    execution__year: typing.Optional[int] | None = None
    month__year: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgSalesSummaryDataSchema
        upsert_keys = []
        access_key_mapping = ['JDEDistributorCode:sap_id', 'SAName:sales_area', 'ZOName:zone']


class LpgSalesSummaryDataGetResp(pydantic.BaseModel):
    data: typing.List[LpgSalesSummaryData]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class LpgConsumersSummarySchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_consumers_summary'
    
    distributor_code: Mapped[int] = mapped_column("distributor_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    relationship_status: Mapped[str] = mapped_column("relationship_status", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    relationship_sub_status: Mapped[str] = mapped_column("relationship_sub_status", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    consumer_category: Mapped[str] = mapped_column("consumer_category", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    typeof_consumer: Mapped[int] = mapped_column("typeof_consumer", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    main_scheme_category: Mapped[int] = mapped_column("main_scheme_category", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    scheme_code: Mapped[int] = mapped_column("scheme_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    connection_type: Mapped[str] = mapped_column("connection_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    cylinder_type: Mapped[str] = mapped_column("cylinder_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    consumer_count: Mapped[int] = mapped_column("consumer_count", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    e_kyc_completed: Mapped[int] = mapped_column("e_kyc_completed", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    suvidha_club: Mapped[int] = mapped_column("suvidha_club", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    hig_opt_out: Mapped[int] = mapped_column("hig_opt_out", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    subsidy_give_it_up: Mapped[int] = mapped_column("subsidy_give_it_up", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    actc_count: Mapped[int] = mapped_column("actc_count", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bctc_count: Mapped[int] = mapped_column("bctc_count", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    nctc_count: Mapped[int] = mapped_column("nctc_count", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    safety_check_pending: Mapped[int] = mapped_column("safety_check_pending", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    hp_pay_consumer_count: Mapped[int] = mapped_column("hp_pay_consumer_count", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    jde_distributor_code: Mapped[int] = mapped_column("jde_distributor_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sa_code: Mapped[int] = mapped_column("sa_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    state_code: Mapped[str] = mapped_column("state_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_code: Mapped[int] = mapped_column("ro_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sa_name: Mapped[str] = mapped_column("sa_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zo_code: Mapped[str] = mapped_column("zo_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_name: Mapped[str] = mapped_column("ro_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zo_name: Mapped[str] = mapped_column("zo_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    category: Mapped[str] = mapped_column("category", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sub_category: Mapped[str] = mapped_column("sub_category", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    category_status: Mapped[str] = mapped_column("category_status", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    e_kyc_pending: Mapped[int] = mapped_column("e_kyc_pending", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zone_names: Mapped[str] = mapped_column("zone_names", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class LpgConsumersSummaryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_consumers_summary'
    
    distributor_code: int
    relationship_status: str
    relationship_sub_status: str
    consumer_category: str
    typeof_consumer: int
    main_scheme_category: int
    scheme_code: int
    connection_type: str
    cylinder_type: str
    consumer_count: int
    e_kyc_completed: int
    suvidha_club: int
    hig_opt_out: int
    subsidy_give_it_up: int
    actc_count: int
    bctc_count: int
    nctc_count: int
    safety_check_pending: int
    hp_pay_consumer_count: int
    jde_distributor_code: int
    sa_code: int
    state_code: str
    ro_code: int
    sa_name: str
    zo_code: str
    ro_name: str
    zo_name: str
    category: str
    sub_category: str
    category_status: str
    e_kyc_pending: int
    zone_names: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgConsumersSummarySchema
        upsert_keys = []
        access_key_mapping = ['DistributorCode:sap_id', 'SAName:sales_area', 'ZOName:zone']


class LpgConsumersSummary(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_consumers_summary'
    
    distributor_code: typing.Optional[int] | None = None
    relationship_status: typing.Optional[str] | None = None
    relationship_sub_status: typing.Optional[str] | None = None
    consumer_category: typing.Optional[str] | None = None
    typeof_consumer: typing.Optional[int] | None = None
    main_scheme_category: typing.Optional[int] | None = None
    scheme_code: typing.Optional[int] | None = None
    connection_type: typing.Optional[str] | None = None
    cylinder_type: typing.Optional[str] | None = None
    consumer_count: typing.Optional[int] | None = None
    e_kyc_completed: typing.Optional[int] | None = None
    suvidha_club: typing.Optional[int] | None = None
    hig_opt_out: typing.Optional[int] | None = None
    subsidy_give_it_up: typing.Optional[int] | None = None
    actc_count: typing.Optional[int] | None = None
    bctc_count: typing.Optional[int] | None = None
    nctc_count: typing.Optional[int] | None = None
    safety_check_pending: typing.Optional[int] | None = None
    hp_pay_consumer_count: typing.Optional[int] | None = None
    jde_distributor_code: typing.Optional[int] | None = None
    sa_code: typing.Optional[int] | None = None
    state_code: typing.Optional[str] | None = None
    ro_code: typing.Optional[int] | None = None
    sa_name: typing.Optional[str] | None = None
    zo_code: typing.Optional[str] | None = None
    ro_name: typing.Optional[str] | None = None
    zo_name: typing.Optional[str] | None = None
    category: typing.Optional[str] | None = None
    sub_category: typing.Optional[str] | None = None
    category_status: typing.Optional[str] | None = None
    e_kyc_pending: typing.Optional[int] | None = None
    zone_names: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgConsumersSummarySchema
        upsert_keys = []
        access_key_mapping = ['DistributorCode:sap_id', 'SAName:sales_area', 'ZOName:zone']


class LpgConsumersSummaryGetResp(pydantic.BaseModel):
    data: typing.List[LpgConsumersSummary]
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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
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
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ScreensSchema
        upsert_keys = []


class ScreensGetResp(pydantic.BaseModel):
    data: typing.List[Screens]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class DeviceMasterSchema(UrdhvaPostgresBase):
    __tablename__ = 'device_master'
    
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_id: Mapped[typing.Optional[str]] = mapped_column("ro_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_type: Mapped[typing.Any] = mapped_column("device_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    tank_no: Mapped[typing.Optional[str]] = mapped_column("tank_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    tank_name: Mapped[typing.Optional[str]] = mapped_column("tank_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    tank_capacity: Mapped[typing.Optional[int]] = mapped_column("tank_capacity", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    pump_no: Mapped[typing.Optional[int]] = mapped_column("pump_no", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    du_no: Mapped[typing.Optional[int]] = mapped_column("du_no", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    nozzle_no: Mapped[typing.Optional[int]] = mapped_column("nozzle_no", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    global_nozzle_no: Mapped[typing.Optional[int]] = mapped_column("global_nozzle_no", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    product_type: Mapped[str] = mapped_column("product_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class DeviceMasterCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'device_master'
    
    bu: hpcl_ceg_enum.BusinessUnit
    sap_id: str
    ro_id: typing.Optional[str] = pydantic.Field("", **{})
    device_type: hpcl_ceg_enum.DeviceType
    tank_no: typing.Optional[str] = pydantic.Field("", **{})
    tank_name: typing.Optional[str] = pydantic.Field("", **{})
    tank_capacity: typing.Optional[int] = pydantic.Field(0, **{})
    pump_no: typing.Optional[int] = pydantic.Field(0, **{})
    du_no: typing.Optional[int] = pydantic.Field(0, **{})
    nozzle_no: typing.Optional[int] = pydantic.Field(0, **{})
    global_nozzle_no: typing.Optional[int] = pydantic.Field(0, **{})
    product_type: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = DeviceMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


class DeviceMaster(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'device_master'
    
    bu: typing.Optional[hpcl_ceg_enum.BusinessUnit] | None = None
    sap_id: typing.Optional[str] | None = None
    ro_id: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[hpcl_ceg_enum.DeviceType] | None = None
    tank_no: typing.Optional[str] = pydantic.Field("", **{})
    tank_name: typing.Optional[str] = pydantic.Field("", **{})
    tank_capacity: typing.Optional[int] = pydantic.Field(0, **{})
    pump_no: typing.Optional[int] = pydantic.Field(0, **{})
    du_no: typing.Optional[int] = pydantic.Field(0, **{})
    nozzle_no: typing.Optional[int] = pydantic.Field(0, **{})
    global_nozzle_no: typing.Optional[int] = pydantic.Field(0, **{})
    product_type: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = DeviceMasterSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


class DeviceMasterGetResp(pydantic.BaseModel):
    data: typing.List[DeviceMaster]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class VtsAlertHistorySchema(UrdhvaPostgresBase):
    __tablename__ = 'vts_alert_history'
    
    vendor_id: Mapped[typing.Optional[str]] = mapped_column("vendor_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_id: Mapped[typing.Optional[str]] = mapped_column("location_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_type: Mapped[typing.Optional[str]] = mapped_column("location_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    tl_number: Mapped[str] = mapped_column("tl_number", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    report_duration: Mapped[typing.Optional[str]] = mapped_column("report_duration", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    total_trips: Mapped[typing.Optional[int]] = mapped_column("total_trips", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    stoppage_violations_count: Mapped[typing.Optional[int]] = mapped_column("stoppage_violations_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    route_deviation_count: Mapped[typing.Optional[int]] = mapped_column("route_deviation_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    speed_violation_count: Mapped[typing.Optional[int]] = mapped_column("speed_violation_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    main_supply_removal_count: Mapped[typing.Optional[int]] = mapped_column("main_supply_removal_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    night_driving_count: Mapped[typing.Optional[int]] = mapped_column("night_driving_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    no_halt_zone_count: Mapped[typing.Optional[int]] = mapped_column("no_halt_zone_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    device_offline_count: Mapped[typing.Optional[int]] = mapped_column("device_offline_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    device_tamper_count: Mapped[typing.Optional[int]] = mapped_column("device_tamper_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    approved_by: Mapped[typing.Optional[str]] = mapped_column("approved_by", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    auto_unblock: Mapped[typing.Optional[bool]] = mapped_column("auto_unblock", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    alert_id: Mapped[typing.Optional[str]] = mapped_column("alert_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class VtsAlertHistoryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'vts_alert_history'
    
    vendor_id: typing.Optional[str] = pydantic.Field("", **{})
    location_id: typing.Optional[str] = pydantic.Field("", **{})
    location_type: typing.Optional[str] = pydantic.Field("", **{})
    tl_number: str
    report_duration: typing.Optional[str] = pydantic.Field("", **{})
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
    auto_unblock: typing.Optional[bool] = pydantic.Field(False, )
    alert_id: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = VtsAlertHistorySchema
        upsert_keys = []
        access_key_mapping = ['location_id:sap_id']


class VtsAlertHistory(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'vts_alert_history'
    
    vendor_id: typing.Optional[str] = pydantic.Field("", **{})
    location_id: typing.Optional[str] = pydantic.Field("", **{})
    location_type: typing.Optional[str] = pydantic.Field("", **{})
    tl_number: typing.Optional[str] | None = None
    report_duration: typing.Optional[str] = pydantic.Field("", **{})
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
    auto_unblock: typing.Optional[bool] = pydantic.Field(False, )
    alert_id: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = VtsAlertHistorySchema
        upsert_keys = []
        access_key_mapping = ['location_id:sap_id']


class VtsAlertHistoryGetResp(pydantic.BaseModel):
    data: typing.List[VtsAlertHistory]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class EmLockAlertHistorySchema(UrdhvaPostgresBase):
    __tablename__ = 'em_lock_alert_history'
    
    vendor_id: Mapped[typing.Optional[str]] = mapped_column("vendor_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_id: Mapped[typing.Optional[str]] = mapped_column("location_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_type: Mapped[typing.Optional[str]] = mapped_column("location_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    emlock_exception_id: Mapped[str] = mapped_column("emlock_exception_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    terminal_code: Mapped[str] = mapped_column("terminal_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    truck_number: Mapped[str] = mapped_column("truck_number", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    exception_type: Mapped[str] = mapped_column("exception_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_code: Mapped[typing.Optional[str]] = mapped_column("ro_code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    created_datetime: Mapped[str] = mapped_column("created_datetime", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class EmLockAlertHistoryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'em_lock_alert_history'
    
    vendor_id: typing.Optional[str] = pydantic.Field("", **{})
    location_id: typing.Optional[str] = pydantic.Field("", **{})
    location_type: typing.Optional[str] = pydantic.Field("", **{})
    emlock_exception_id: str
    terminal_code: str
    truck_number: str
    exception_type: str
    ro_code: typing.Optional[str] = pydantic.Field("", **{})
    created_datetime: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = EmLockAlertHistorySchema
        upsert_keys = []
        access_key_mapping = ['location_id:sap_id']


class EmLockAlertHistory(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'em_lock_alert_history'
    
    vendor_id: typing.Optional[str] = pydantic.Field("", **{})
    location_id: typing.Optional[str] = pydantic.Field("", **{})
    location_type: typing.Optional[str] = pydantic.Field("", **{})
    emlock_exception_id: typing.Optional[str] | None = None
    terminal_code: typing.Optional[str] | None = None
    truck_number: typing.Optional[str] | None = None
    exception_type: typing.Optional[str] | None = None
    ro_code: typing.Optional[str] = pydantic.Field("", **{})
    created_datetime: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = EmLockAlertHistorySchema
        upsert_keys = []
        access_key_mapping = ['location_id:sap_id']


class EmLockAlertHistoryGetResp(pydantic.BaseModel):
    data: typing.List[EmLockAlertHistory]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class VaAlertHistorySchema(UrdhvaPostgresBase):
    __tablename__ = 'va_alert_history'
    
    vendor_id: Mapped[typing.Optional[str]] = mapped_column("vendor_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_id: Mapped[typing.Optional[str]] = mapped_column("location_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_type: Mapped[typing.Optional[str]] = mapped_column("location_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_id: Mapped[typing.Optional[str]] = mapped_column("alert_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_type: Mapped[typing.Optional[str]] = mapped_column("alert_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_description: Mapped[typing.Optional[str]] = mapped_column("alert_description", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_id: Mapped[typing.Optional[str]] = mapped_column("device_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    video_url: Mapped[typing.Optional[str]] = mapped_column("video_url", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_timestamp: Mapped[typing.Optional[datetime.datetime]] = mapped_column("alert_timestamp", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)


class VaAlertHistoryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'va_alert_history'
    
    vendor_id: typing.Optional[str] = pydantic.Field("", **{})
    location_id: typing.Optional[str] = pydantic.Field("", **{})
    location_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_id: typing.Optional[str] = pydantic.Field("", **{})
    alert_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] = pydantic.Field("", **{})
    video_url: typing.Optional[str] = pydantic.Field("", **{})
    alert_timestamp: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = VaAlertHistorySchema
        upsert_keys = []
        access_key_mapping = ['location_id:sap_id']


class VaAlertHistory(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'va_alert_history'
    
    vendor_id: typing.Optional[str] = pydantic.Field("", **{})
    location_id: typing.Optional[str] = pydantic.Field("", **{})
    location_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_id: typing.Optional[str] = pydantic.Field("", **{})
    alert_type: typing.Optional[str] = pydantic.Field("", **{})
    alert_description: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] = pydantic.Field("", **{})
    video_url: typing.Optional[str] = pydantic.Field("", **{})
    alert_timestamp: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = VaAlertHistorySchema
        upsert_keys = []
        access_key_mapping = ['location_id:sap_id']


class VaAlertHistoryGetResp(pydantic.BaseModel):
    data: typing.List[VaAlertHistory]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class M60LevelMetaDataSchema(UrdhvaPostgresBase):
    __tablename__ = 'm60_level_meta_data'
    
    sbu: Mapped[typing.Optional[str]] = mapped_column("sbu", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sbu__name: Mapped[typing.Optional[str]] = mapped_column("sbu__name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone__name: Mapped[typing.Optional[str]] = mapped_column("zone__name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region__name: Mapped[typing.Optional[str]] = mapped_column("region__name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sa: Mapped[typing.Optional[str]] = mapped_column("sa", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sales_area__name: Mapped[typing.Optional[str]] = mapped_column("sales_area__name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product: Mapped[typing.Optional[str]] = mapped_column("product", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product_name: Mapped[typing.Optional[str]] = mapped_column("product_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    uom: Mapped[typing.Optional[str]] = mapped_column("uom", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    invoice_dt: Mapped[typing.Optional[str]] = mapped_column("invoice_dt", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    target_qty_kl: Mapped[typing.Optional[float]] = mapped_column("target_qty_kl", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    target_qty_tmt: Mapped[typing.Optional[float]] = mapped_column("target_qty_tmt", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    fiscal_year: Mapped[typing.Optional[str]] = mapped_column("fiscal_year", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    cur_fiscal_year: Mapped[typing.Optional[str]] = mapped_column("cur_fiscal_year", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgsbucd: Mapped[typing.Optional[str]] = mapped_column("orgsbucd", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgsbuname: Mapped[typing.Optional[str]] = mapped_column("orgsbuname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgzonecd: Mapped[typing.Optional[str]] = mapped_column("orgzonecd", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgzonename: Mapped[typing.Optional[str]] = mapped_column("orgzonename", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgrocd: Mapped[typing.Optional[str]] = mapped_column("orgrocd", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgroname: Mapped[typing.Optional[str]] = mapped_column("orgroname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgsacd: Mapped[typing.Optional[str]] = mapped_column("orgsacd", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgsaname: Mapped[typing.Optional[str]] = mapped_column("orgsaname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    productcode: Mapped[typing.Optional[str]] = mapped_column("productcode", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    materialgroupname: Mapped[typing.Optional[str]] = mapped_column("materialgroupname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    curfiscalyear: Mapped[typing.Optional[str]] = mapped_column("curfiscalyear", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    fiscalyear: Mapped[typing.Optional[str]] = mapped_column("fiscalyear", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    yearmonth: Mapped[typing.Optional[str]] = mapped_column("yearmonth", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    netweight_uom: Mapped[typing.Optional[float]] = mapped_column("netweight_uom", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    netweight_kg: Mapped[typing.Optional[float]] = mapped_column("netweight_kg", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    netweight_tmt: Mapped[typing.Optional[float]] = mapped_column("netweight_tmt", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    total__days__till__present_day: Mapped[typing.Optional[int]] = mapped_column("total__days__till__present_day", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    number__of__sundays__till__present_day: Mapped[typing.Optional[int]] = mapped_column("number__of__sundays__till__present_day", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    target_round: Mapped[typing.Optional[int]] = mapped_column("target_round", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    actual_round: Mapped[typing.Optional[int]] = mapped_column("actual_round", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    final_sum: Mapped[typing.Optional[float]] = mapped_column("final_sum", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    final_actual_sum: Mapped[typing.Optional[float]] = mapped_column("final_actual_sum", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    max_pending_days: Mapped[typing.Optional[int]] = mapped_column("max_pending_days", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    working__days__till__present_day__without_sundays: Mapped[typing.Optional[int]] = mapped_column("working__days__till__present_day__without_sundays", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    rate__per__day__required_mmt: Mapped[typing.Optional[float]] = mapped_column("rate__per__day__required_mmt", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    rate_per_day_current_mmt: Mapped[typing.Optional[float]] = mapped_column("rate_per_day_current_mmt", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    total__days_in_fy: Mapped[typing.Optional[int]] = mapped_column("total__days_in_fy", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    pending__days: Mapped[typing.Optional[int]] = mapped_column("pending__days", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    month_year: Mapped[typing.Optional[int]] = mapped_column("month_year", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    month_name: Mapped[typing.Optional[str]] = mapped_column("month_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    fy_month: Mapped[typing.Optional[int]] = mapped_column("fy_month", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    year_monthname: Mapped[typing.Optional[datetime.date]] = mapped_column("year_monthname", DATE, index=False, nullable=True, default=None, primary_key=False, unique=False)
    target__quantity_tmtt: Mapped[typing.Optional[float]] = mapped_column("target__quantity_tmtt", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    prediction__value: Mapped[typing.Optional[float]] = mapped_column("prediction__value", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    act__tgt__achievement: Mapped[typing.Optional[float]] = mapped_column("act__tgt__achievement", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    zone__region__achievement: Mapped[typing.Optional[float]] = mapped_column("zone__region__achievement", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    product__achievement: Mapped[typing.Optional[float]] = mapped_column("product__achievement", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    engine_id: Mapped[typing.Optional[str]] = mapped_column("engine_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class M60LevelMetaDataCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'm60_level_meta_data'
    
    sbu: typing.Optional[str] = pydantic.Field("", **{})
    sbu__name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    zone__name: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    region__name: typing.Optional[str] = pydantic.Field("", **{})
    sa: typing.Optional[str] = pydantic.Field("", **{})
    sales_area__name: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    product_name: typing.Optional[str] = pydantic.Field("", **{})
    uom: typing.Optional[str] = pydantic.Field("", **{})
    invoice_dt: typing.Optional[str] = pydantic.Field("", **{})
    target_qty_kl: typing.Optional[float] = pydantic.Field(0.0, **{})
    target_qty_tmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    fiscal_year: typing.Optional[str] = pydantic.Field("", **{})
    cur_fiscal_year: typing.Optional[str] = pydantic.Field("", **{})
    orgsbucd: typing.Optional[str] = pydantic.Field("", **{})
    orgsbuname: typing.Optional[str] = pydantic.Field("", **{})
    orgzonecd: typing.Optional[str] = pydantic.Field("", **{})
    orgzonename: typing.Optional[str] = pydantic.Field("", **{})
    orgrocd: typing.Optional[str] = pydantic.Field("", **{})
    orgroname: typing.Optional[str] = pydantic.Field("", **{})
    orgsacd: typing.Optional[str] = pydantic.Field("", **{})
    orgsaname: typing.Optional[str] = pydantic.Field("", **{})
    productcode: typing.Optional[str] = pydantic.Field("", **{})
    materialgroupname: typing.Optional[str] = pydantic.Field("", **{})
    curfiscalyear: typing.Optional[str] = pydantic.Field("", **{})
    fiscalyear: typing.Optional[str] = pydantic.Field("", **{})
    yearmonth: typing.Optional[str] = pydantic.Field("", **{})
    netweight_uom: typing.Optional[float] = pydantic.Field(0.0, **{})
    netweight_kg: typing.Optional[float] = pydantic.Field(0.0, **{})
    netweight_tmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    total__days__till__present_day: typing.Optional[int] = pydantic.Field(0, **{})
    number__of__sundays__till__present_day: typing.Optional[int] = pydantic.Field(0, **{})
    target_round: typing.Optional[int] = pydantic.Field(0, **{})
    actual_round: typing.Optional[int] = pydantic.Field(0, **{})
    final_sum: typing.Optional[float] = pydantic.Field(0.0, **{})
    final_actual_sum: typing.Optional[float] = pydantic.Field(0.0, **{})
    max_pending_days: typing.Optional[int] = pydantic.Field(0, **{})
    working__days__till__present_day__without_sundays: typing.Optional[int] = pydantic.Field(0, **{})
    rate__per__day__required_mmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    rate_per_day_current_mmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    total__days_in_fy: typing.Optional[int] = pydantic.Field(0, **{})
    pending__days: typing.Optional[int] = pydantic.Field(0, **{})
    month_year: typing.Optional[int] = pydantic.Field(0, **{})
    month_name: typing.Optional[str] = pydantic.Field("", **{})
    fy_month: typing.Optional[int] = pydantic.Field(0, **{})
    year_monthname: typing.Optional[datetime.date] | None = None
    target__quantity_tmtt: typing.Optional[float] = pydantic.Field(0.0, **{})
    prediction__value: typing.Optional[float] = pydantic.Field(0.0, **{})
    act__tgt__achievement: typing.Optional[float] = pydantic.Field(0.0, **{})
    zone__region__achievement: typing.Optional[float] = pydantic.Field(0.0, **{})
    product__achievement: typing.Optional[float] = pydantic.Field(0.0, **{})
    engine_id: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = M60LevelMetaDataSchema
        upsert_keys = []
        access_key_mapping = ['SBU_Name:bu', 'ZONE:zone', 'SalesArea_Name:sales_area', 'Region_Name:region']


class M60LevelMetaData(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'm60_level_meta_data'
    
    sbu: typing.Optional[str] = pydantic.Field("", **{})
    sbu__name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    zone__name: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    region__name: typing.Optional[str] = pydantic.Field("", **{})
    sa: typing.Optional[str] = pydantic.Field("", **{})
    sales_area__name: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    product_name: typing.Optional[str] = pydantic.Field("", **{})
    uom: typing.Optional[str] = pydantic.Field("", **{})
    invoice_dt: typing.Optional[str] = pydantic.Field("", **{})
    target_qty_kl: typing.Optional[float] = pydantic.Field(0.0, **{})
    target_qty_tmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    fiscal_year: typing.Optional[str] = pydantic.Field("", **{})
    cur_fiscal_year: typing.Optional[str] = pydantic.Field("", **{})
    orgsbucd: typing.Optional[str] = pydantic.Field("", **{})
    orgsbuname: typing.Optional[str] = pydantic.Field("", **{})
    orgzonecd: typing.Optional[str] = pydantic.Field("", **{})
    orgzonename: typing.Optional[str] = pydantic.Field("", **{})
    orgrocd: typing.Optional[str] = pydantic.Field("", **{})
    orgroname: typing.Optional[str] = pydantic.Field("", **{})
    orgsacd: typing.Optional[str] = pydantic.Field("", **{})
    orgsaname: typing.Optional[str] = pydantic.Field("", **{})
    productcode: typing.Optional[str] = pydantic.Field("", **{})
    materialgroupname: typing.Optional[str] = pydantic.Field("", **{})
    curfiscalyear: typing.Optional[str] = pydantic.Field("", **{})
    fiscalyear: typing.Optional[str] = pydantic.Field("", **{})
    yearmonth: typing.Optional[str] = pydantic.Field("", **{})
    netweight_uom: typing.Optional[float] = pydantic.Field(0.0, **{})
    netweight_kg: typing.Optional[float] = pydantic.Field(0.0, **{})
    netweight_tmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    total__days__till__present_day: typing.Optional[int] = pydantic.Field(0, **{})
    number__of__sundays__till__present_day: typing.Optional[int] = pydantic.Field(0, **{})
    target_round: typing.Optional[int] = pydantic.Field(0, **{})
    actual_round: typing.Optional[int] = pydantic.Field(0, **{})
    final_sum: typing.Optional[float] = pydantic.Field(0.0, **{})
    final_actual_sum: typing.Optional[float] = pydantic.Field(0.0, **{})
    max_pending_days: typing.Optional[int] = pydantic.Field(0, **{})
    working__days__till__present_day__without_sundays: typing.Optional[int] = pydantic.Field(0, **{})
    rate__per__day__required_mmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    rate_per_day_current_mmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    total__days_in_fy: typing.Optional[int] = pydantic.Field(0, **{})
    pending__days: typing.Optional[int] = pydantic.Field(0, **{})
    month_year: typing.Optional[int] = pydantic.Field(0, **{})
    month_name: typing.Optional[str] = pydantic.Field("", **{})
    fy_month: typing.Optional[int] = pydantic.Field(0, **{})
    year_monthname: typing.Optional[datetime.date] | None = None
    target__quantity_tmtt: typing.Optional[float] = pydantic.Field(0.0, **{})
    prediction__value: typing.Optional[float] = pydantic.Field(0.0, **{})
    act__tgt__achievement: typing.Optional[float] = pydantic.Field(0.0, **{})
    zone__region__achievement: typing.Optional[float] = pydantic.Field(0.0, **{})
    product__achievement: typing.Optional[float] = pydantic.Field(0.0, **{})
    engine_id: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = M60LevelMetaDataSchema
        upsert_keys = []
        access_key_mapping = ['SBU_Name:bu', 'ZONE:zone', 'SalesArea_Name:sales_area', 'Region_Name:region']


class M60LevelMetaDataGetResp(pydantic.BaseModel):
    data: typing.List[M60LevelMetaData]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class MomLevelFinalMetaDataSchema(UrdhvaPostgresBase):
    __tablename__ = 'mom_level_final_meta_data'
    
    orgsbucd: Mapped[typing.Optional[str]] = mapped_column("orgsbucd", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgsbuname: Mapped[typing.Optional[str]] = mapped_column("orgsbuname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgzonecd: Mapped[typing.Optional[str]] = mapped_column("orgzonecd", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgzonename: Mapped[typing.Optional[str]] = mapped_column("orgzonename", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgrocd: Mapped[typing.Optional[str]] = mapped_column("orgrocd", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgroname: Mapped[typing.Optional[str]] = mapped_column("orgroname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgsacd: Mapped[typing.Optional[str]] = mapped_column("orgsacd", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgsaname: Mapped[typing.Optional[str]] = mapped_column("orgsaname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    productcode: Mapped[typing.Optional[str]] = mapped_column("productcode", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    materialgroupname: Mapped[typing.Optional[str]] = mapped_column("materialgroupname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    curfiscalyear: Mapped[typing.Optional[str]] = mapped_column("curfiscalyear", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    fiscalyear: Mapped[typing.Optional[str]] = mapped_column("fiscalyear", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    yearmonth: Mapped[typing.Optional[str]] = mapped_column("yearmonth", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    netweight_uom: Mapped[typing.Optional[float]] = mapped_column("netweight_uom", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    netweight_kg: Mapped[typing.Optional[float]] = mapped_column("netweight_kg", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    netweight_tmt: Mapped[typing.Optional[float]] = mapped_column("netweight_tmt", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    fiscal_year: Mapped[typing.Optional[str]] = mapped_column("fiscal_year", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    engine_id: Mapped[typing.Optional[str]] = mapped_column("engine_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    month_name: Mapped[typing.Optional[str]] = mapped_column("month_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class MomLevelFinalMetaDataCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'mom_level_final_meta_data'
    
    orgsbucd: typing.Optional[str] = pydantic.Field("", **{})
    orgsbuname: typing.Optional[str] = pydantic.Field("", **{})
    orgzonecd: typing.Optional[str] = pydantic.Field("", **{})
    orgzonename: typing.Optional[str] = pydantic.Field("", **{})
    orgrocd: typing.Optional[str] = pydantic.Field("", **{})
    orgroname: typing.Optional[str] = pydantic.Field("", **{})
    orgsacd: typing.Optional[str] = pydantic.Field("", **{})
    orgsaname: typing.Optional[str] = pydantic.Field("", **{})
    productcode: typing.Optional[str] = pydantic.Field("", **{})
    materialgroupname: typing.Optional[str] = pydantic.Field("", **{})
    curfiscalyear: typing.Optional[str] = pydantic.Field("", **{})
    fiscalyear: typing.Optional[str] = pydantic.Field("", **{})
    yearmonth: typing.Optional[str] = pydantic.Field("", **{})
    netweight_uom: typing.Optional[float] = pydantic.Field(0.0, **{})
    netweight_kg: typing.Optional[float] = pydantic.Field(0.0, **{})
    netweight_tmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    fiscal_year: typing.Optional[str] = pydantic.Field("", **{})
    engine_id: typing.Optional[str] = pydantic.Field("", **{})
    month_name: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = MomLevelFinalMetaDataSchema
        upsert_keys = []
        access_key_mapping = ['ORGSBUNAME:bu', 'ORGZONENAME:zone', 'ORGSANAME:sales_area']


class MomLevelFinalMetaData(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'mom_level_final_meta_data'
    
    orgsbucd: typing.Optional[str] = pydantic.Field("", **{})
    orgsbuname: typing.Optional[str] = pydantic.Field("", **{})
    orgzonecd: typing.Optional[str] = pydantic.Field("", **{})
    orgzonename: typing.Optional[str] = pydantic.Field("", **{})
    orgrocd: typing.Optional[str] = pydantic.Field("", **{})
    orgroname: typing.Optional[str] = pydantic.Field("", **{})
    orgsacd: typing.Optional[str] = pydantic.Field("", **{})
    orgsaname: typing.Optional[str] = pydantic.Field("", **{})
    productcode: typing.Optional[str] = pydantic.Field("", **{})
    materialgroupname: typing.Optional[str] = pydantic.Field("", **{})
    curfiscalyear: typing.Optional[str] = pydantic.Field("", **{})
    fiscalyear: typing.Optional[str] = pydantic.Field("", **{})
    yearmonth: typing.Optional[str] = pydantic.Field("", **{})
    netweight_uom: typing.Optional[float] = pydantic.Field(0.0, **{})
    netweight_kg: typing.Optional[float] = pydantic.Field(0.0, **{})
    netweight_tmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    fiscal_year: typing.Optional[str] = pydantic.Field("", **{})
    engine_id: typing.Optional[str] = pydantic.Field("", **{})
    month_name: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = MomLevelFinalMetaDataSchema
        upsert_keys = []
        access_key_mapping = ['ORGSBUNAME:bu', 'ORGZONENAME:zone', 'ORGSANAME:sales_area']


class MomLevelFinalMetaDataGetResp(pydantic.BaseModel):
    data: typing.List[MomLevelFinalMetaData]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class IndustryPerformanceSchema(UrdhvaPostgresBase):
    __tablename__ = 'industry_performance'
    
    prod1_1: Mapped[typing.Optional[str]] = mapped_column("prod1_1", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    category: Mapped[typing.Optional[str]] = mapped_column("category", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sbu_name: Mapped[typing.Optional[str]] = mapped_column("sbu_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    statename: Mapped[typing.Optional[str]] = mapped_column("statename", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    company_name: Mapped[typing.Optional[str]] = mapped_column("company_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    productname: Mapped[typing.Optional[str]] = mapped_column("productname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    distname: Mapped[typing.Optional[str]] = mapped_column("distname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    prod2: Mapped[typing.Optional[str]] = mapped_column("prod2", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    comname: Mapped[typing.Optional[str]] = mapped_column("comname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    psu_pvt: Mapped[typing.Optional[str]] = mapped_column("psu_pvt", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    statecode: Mapped[typing.Optional[str]] = mapped_column("statecode", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    orgrocd: Mapped[typing.Optional[str]] = mapped_column("orgrocd", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    dist: Mapped[typing.Optional[str]] = mapped_column("dist", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    prod1: Mapped[typing.Optional[str]] = mapped_column("prod1", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    total: Mapped[typing.Optional[float]] = mapped_column("total", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    distcode: Mapped[typing.Optional[str]] = mapped_column("distcode", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    comcode: Mapped[typing.Optional[int]] = mapped_column("comcode", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    code: Mapped[typing.Optional[str]] = mapped_column("code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    productcode: Mapped[typing.Optional[int]] = mapped_column("productcode", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    zone_name: Mapped[typing.Optional[str]] = mapped_column("zone_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region_name: Mapped[typing.Optional[str]] = mapped_column("region_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    newcode: Mapped[typing.Optional[str]] = mapped_column("newcode", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    fiscal_year: Mapped[typing.Optional[str]] = mapped_column("fiscal_year", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    coname: Mapped[typing.Optional[str]] = mapped_column("coname", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    month_name: Mapped[typing.Optional[str]] = mapped_column("month_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    netweight_tmt: Mapped[typing.Optional[float]] = mapped_column("netweight_tmt", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    com_type: Mapped[typing.Optional[str]] = mapped_column("com_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class IndustryPerformanceCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'industry_performance'
    
    prod1_1: typing.Optional[str] = pydantic.Field("", **{})
    category: typing.Optional[str] = pydantic.Field("", **{})
    sbu_name: typing.Optional[str] = pydantic.Field("", **{})
    statename: typing.Optional[str] = pydantic.Field("", **{})
    company_name: typing.Optional[str] = pydantic.Field("", **{})
    productname: typing.Optional[str] = pydantic.Field("", **{})
    distname: typing.Optional[str] = pydantic.Field("", **{})
    prod2: typing.Optional[str] = pydantic.Field("", **{})
    comname: typing.Optional[str] = pydantic.Field("", **{})
    psu_pvt: typing.Optional[str] = pydantic.Field("", **{})
    statecode: typing.Optional[str] = pydantic.Field("", **{})
    orgrocd: typing.Optional[str] = pydantic.Field("", **{})
    dist: typing.Optional[str] = pydantic.Field("", **{})
    prod1: typing.Optional[str] = pydantic.Field("", **{})
    total: typing.Optional[float] = pydantic.Field(0.0, **{})
    distcode: typing.Optional[str] = pydantic.Field("", **{})
    comcode: typing.Optional[int] = pydantic.Field(0, **{})
    code: typing.Optional[str] = pydantic.Field("", **{})
    productcode: typing.Optional[int] = pydantic.Field(0, **{})
    zone_name: typing.Optional[str] = pydantic.Field("", **{})
    region_name: typing.Optional[str] = pydantic.Field("", **{})
    newcode: typing.Optional[str] = pydantic.Field("", **{})
    fiscal_year: typing.Optional[str] = pydantic.Field("", **{})
    coname: typing.Optional[str] = pydantic.Field("", **{})
    month_name: typing.Optional[str] = pydantic.Field("", **{})
    netweight_tmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    com_type: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = IndustryPerformanceSchema
        upsert_keys = []
        access_key_mapping = ['ORGSBUNAME:bu', 'ORGZONENAME:zone', 'ORGSANAME:sales_area']


class IndustryPerformance(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'industry_performance'
    
    prod1_1: typing.Optional[str] = pydantic.Field("", **{})
    category: typing.Optional[str] = pydantic.Field("", **{})
    sbu_name: typing.Optional[str] = pydantic.Field("", **{})
    statename: typing.Optional[str] = pydantic.Field("", **{})
    company_name: typing.Optional[str] = pydantic.Field("", **{})
    productname: typing.Optional[str] = pydantic.Field("", **{})
    distname: typing.Optional[str] = pydantic.Field("", **{})
    prod2: typing.Optional[str] = pydantic.Field("", **{})
    comname: typing.Optional[str] = pydantic.Field("", **{})
    psu_pvt: typing.Optional[str] = pydantic.Field("", **{})
    statecode: typing.Optional[str] = pydantic.Field("", **{})
    orgrocd: typing.Optional[str] = pydantic.Field("", **{})
    dist: typing.Optional[str] = pydantic.Field("", **{})
    prod1: typing.Optional[str] = pydantic.Field("", **{})
    total: typing.Optional[float] = pydantic.Field(0.0, **{})
    distcode: typing.Optional[str] = pydantic.Field("", **{})
    comcode: typing.Optional[int] = pydantic.Field(0, **{})
    code: typing.Optional[str] = pydantic.Field("", **{})
    productcode: typing.Optional[int] = pydantic.Field(0, **{})
    zone_name: typing.Optional[str] = pydantic.Field("", **{})
    region_name: typing.Optional[str] = pydantic.Field("", **{})
    newcode: typing.Optional[str] = pydantic.Field("", **{})
    fiscal_year: typing.Optional[str] = pydantic.Field("", **{})
    coname: typing.Optional[str] = pydantic.Field("", **{})
    month_name: typing.Optional[str] = pydantic.Field("", **{})
    netweight_tmt: typing.Optional[float] = pydantic.Field(0.0, **{})
    com_type: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = IndustryPerformanceSchema
        upsert_keys = []
        access_key_mapping = ['ORGSBUNAME:bu', 'ORGZONENAME:zone', 'ORGSANAME:sales_area']


class IndustryPerformanceGetResp(pydantic.BaseModel):
    data: typing.List[IndustryPerformance]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class ConsumerPumpTankDeliverySchema(UrdhvaPostgresBase):
    __tablename__ = 'consumer_pump_tank_delivery'
    
    bu: Mapped[typing.Optional[str]] = mapped_column("bu", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    depot: Mapped[typing.Optional[str]] = mapped_column("depot", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product: Mapped[typing.Optional[str]] = mapped_column("product", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    tank_group: Mapped[typing.Optional[str]] = mapped_column("tank_group", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    start_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("start_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    end_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("end_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    tank_no: Mapped[typing.Optional[int]] = mapped_column("tank_no", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    volume: Mapped[typing.Optional[float]] = mapped_column("volume", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    tc_volume: Mapped[typing.Optional[float]] = mapped_column("tc_volume", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    start_volume: Mapped[typing.Optional[float]] = mapped_column("start_volume", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    start_water: Mapped[typing.Optional[float]] = mapped_column("start_water", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    start_temp: Mapped[typing.Optional[float]] = mapped_column("start_temp", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    start_product_height: Mapped[typing.Optional[float]] = mapped_column("start_product_height", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    end_volume: Mapped[typing.Optional[float]] = mapped_column("end_volume", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    end_water: Mapped[typing.Optional[float]] = mapped_column("end_water", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    end_temp: Mapped[typing.Optional[float]] = mapped_column("end_temp", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    end_product_height: Mapped[typing.Optional[float]] = mapped_column("end_product_height", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    manual: Mapped[typing.Optional[bool]] = mapped_column("manual", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    delivery_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("delivery_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    truck_reg_no: Mapped[typing.Optional[str]] = mapped_column("truck_reg_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    po_number: Mapped[typing.Optional[str]] = mapped_column("po_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    verification_delivery_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("verification_delivery_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    verification_sales_order_no: Mapped[typing.Optional[str]] = mapped_column("verification_sales_order_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    actual_volume: Mapped[typing.Optional[float]] = mapped_column("actual_volume", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    actual_temp: Mapped[typing.Optional[float]] = mapped_column("actual_temp", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    density: Mapped[typing.Optional[float]] = mapped_column("density", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    pre_density: Mapped[typing.Optional[float]] = mapped_column("pre_density", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    post_density: Mapped[typing.Optional[float]] = mapped_column("post_density", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    source: Mapped[typing.Optional[str]] = mapped_column("source", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class ConsumerPumpTankDeliveryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'consumer_pump_tank_delivery'
    
    bu: typing.Optional[str] = pydantic.Field("", **{})
    depot: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    tank_group: typing.Optional[str] = pydantic.Field("", **{})
    start_time: typing.Optional[datetime.datetime] | None = None
    end_time: typing.Optional[datetime.datetime] | None = None
    tank_no: typing.Optional[int] = pydantic.Field(0, **{})
    volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    tc_volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    start_volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    start_water: typing.Optional[float] = pydantic.Field(0.0, **{})
    start_temp: typing.Optional[float] = pydantic.Field(0.0, **{})
    start_product_height: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_water: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_temp: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_product_height: typing.Optional[float] = pydantic.Field(0.0, **{})
    manual: typing.Optional[bool] = pydantic.Field(False, )
    delivery_date: typing.Optional[datetime.datetime] | None = None
    truck_reg_no: typing.Optional[str] = pydantic.Field("", **{})
    po_number: typing.Optional[str] = pydantic.Field("", **{})
    verification_delivery_time: typing.Optional[datetime.datetime] | None = None
    verification_sales_order_no: typing.Optional[str] = pydantic.Field("", **{})
    actual_volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    actual_temp: typing.Optional[float] = pydantic.Field(0.0, **{})
    density: typing.Optional[float] = pydantic.Field(0.0, **{})
    pre_density: typing.Optional[float] = pydantic.Field(0.0, **{})
    post_density: typing.Optional[float] = pydantic.Field(0.0, **{})
    source: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ConsumerPumpTankDeliverySchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


class ConsumerPumpTankDelivery(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'consumer_pump_tank_delivery'
    
    bu: typing.Optional[str] = pydantic.Field("", **{})
    depot: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    tank_group: typing.Optional[str] = pydantic.Field("", **{})
    start_time: typing.Optional[datetime.datetime] | None = None
    end_time: typing.Optional[datetime.datetime] | None = None
    tank_no: typing.Optional[int] = pydantic.Field(0, **{})
    volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    tc_volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    start_volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    start_water: typing.Optional[float] = pydantic.Field(0.0, **{})
    start_temp: typing.Optional[float] = pydantic.Field(0.0, **{})
    start_product_height: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_water: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_temp: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_product_height: typing.Optional[float] = pydantic.Field(0.0, **{})
    manual: typing.Optional[bool] = pydantic.Field(False, )
    delivery_date: typing.Optional[datetime.datetime] | None = None
    truck_reg_no: typing.Optional[str] = pydantic.Field("", **{})
    po_number: typing.Optional[str] = pydantic.Field("", **{})
    verification_delivery_time: typing.Optional[datetime.datetime] | None = None
    verification_sales_order_no: typing.Optional[str] = pydantic.Field("", **{})
    actual_volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    actual_temp: typing.Optional[float] = pydantic.Field(0.0, **{})
    density: typing.Optional[float] = pydantic.Field(0.0, **{})
    pre_density: typing.Optional[float] = pydantic.Field(0.0, **{})
    post_density: typing.Optional[float] = pydantic.Field(0.0, **{})
    source: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ConsumerPumpTankDeliverySchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


class ConsumerPumpTankDeliveryGetResp(pydantic.BaseModel):
    data: typing.List[ConsumerPumpTankDelivery]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class ConsumperPumpTransactionSchema(UrdhvaPostgresBase):
    __tablename__ = 'consumper_pump_transaction'
    
    bu: Mapped[typing.Optional[str]] = mapped_column("bu", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    depot: Mapped[typing.Optional[str]] = mapped_column("depot", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    make: Mapped[typing.Optional[str]] = mapped_column("make", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    model: Mapped[typing.Optional[str]] = mapped_column("model", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    make_model: Mapped[typing.Optional[str]] = mapped_column("make_model", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    capacity: Mapped[typing.Optional[int]] = mapped_column("capacity", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    token_type: Mapped[typing.Optional[str]] = mapped_column("token_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    transaction_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("transaction_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    transaction_type: Mapped[typing.Optional[str]] = mapped_column("transaction_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product: Mapped[typing.Optional[str]] = mapped_column("product", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    volume: Mapped[typing.Optional[float]] = mapped_column("volume", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    tank_no: Mapped[typing.Optional[int]] = mapped_column("tank_no", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    start_pump_totalizer: Mapped[typing.Optional[float]] = mapped_column("start_pump_totalizer", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    end_pump_totalizer: Mapped[typing.Optional[float]] = mapped_column("end_pump_totalizer", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    consumption_type: Mapped[typing.Optional[str]] = mapped_column("consumption_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    consumption_benchmark: Mapped[typing.Optional[int]] = mapped_column("consumption_benchmark", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    dispensing_unit: Mapped[typing.Optional[int]] = mapped_column("dispensing_unit", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    pump_no: Mapped[typing.Optional[int]] = mapped_column("pump_no", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    global_nozzle_no: Mapped[typing.Optional[int]] = mapped_column("global_nozzle_no", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    department: Mapped[typing.Optional[str]] = mapped_column("department", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    status: Mapped[typing.Optional[str]] = mapped_column("status", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class ConsumperPumpTransactionCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'consumper_pump_transaction'
    
    bu: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    depot: typing.Optional[str] = pydantic.Field("", **{})
    make: typing.Optional[str] = pydantic.Field("", **{})
    model: typing.Optional[str] = pydantic.Field("", **{})
    make_model: typing.Optional[str] = pydantic.Field("", **{})
    capacity: typing.Optional[int] = pydantic.Field(0, **{})
    token_type: typing.Optional[str] = pydantic.Field("", **{})
    transaction_time: typing.Optional[datetime.datetime] | None = None
    transaction_type: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    tank_no: typing.Optional[int] = pydantic.Field(0, **{})
    start_pump_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_pump_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    consumption_type: typing.Optional[str] = pydantic.Field("", **{})
    consumption_benchmark: typing.Optional[int] = pydantic.Field(0, **{})
    dispensing_unit: typing.Optional[int] = pydantic.Field(0, **{})
    pump_no: typing.Optional[int] = pydantic.Field(0, **{})
    global_nozzle_no: typing.Optional[int] = pydantic.Field(0, **{})
    department: typing.Optional[str] = pydantic.Field("", **{})
    status: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ConsumperPumpTransactionSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


class ConsumperPumpTransaction(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'consumper_pump_transaction'
    
    bu: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    depot: typing.Optional[str] = pydantic.Field("", **{})
    make: typing.Optional[str] = pydantic.Field("", **{})
    model: typing.Optional[str] = pydantic.Field("", **{})
    make_model: typing.Optional[str] = pydantic.Field("", **{})
    capacity: typing.Optional[int] = pydantic.Field(0, **{})
    token_type: typing.Optional[str] = pydantic.Field("", **{})
    transaction_time: typing.Optional[datetime.datetime] | None = None
    transaction_type: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    tank_no: typing.Optional[int] = pydantic.Field(0, **{})
    start_pump_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_pump_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    consumption_type: typing.Optional[str] = pydantic.Field("", **{})
    consumption_benchmark: typing.Optional[int] = pydantic.Field(0, **{})
    dispensing_unit: typing.Optional[int] = pydantic.Field(0, **{})
    pump_no: typing.Optional[int] = pydantic.Field(0, **{})
    global_nozzle_no: typing.Optional[int] = pydantic.Field(0, **{})
    department: typing.Optional[str] = pydantic.Field("", **{})
    status: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ConsumperPumpTransactionSchema
        upsert_keys = []
        access_key_mapping = ['bu', 'sap_id']


class ConsumperPumpTransactionGetResp(pydantic.BaseModel):
    data: typing.List[ConsumperPumpTransaction]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class BuLevelGeoCoordinatesSchema(UrdhvaPostgresBase):
    __tablename__ = 'bu_level_geo_coordinates'
    
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_id: Mapped[typing.Optional[str]] = mapped_column("ro_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bu: Mapped[str] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    latitude: Mapped[typing.Optional[str]] = mapped_column("latitude", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    longitude: Mapped[typing.Optional[str]] = mapped_column("longitude", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class BuLevelGeoCoordinatesCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'bu_level_geo_coordinates'
    
    sap_id: str
    ro_id: typing.Optional[str] = pydantic.Field("", **{})
    bu: str
    latitude: typing.Optional[str] = pydantic.Field("", **{})
    longitude: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = BuLevelGeoCoordinatesSchema
        upsert_keys = []
        access_key_mapping = ['bu']


class BuLevelGeoCoordinates(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'bu_level_geo_coordinates'
    
    sap_id: typing.Optional[str] | None = None
    ro_id: typing.Optional[str] = pydantic.Field("", **{})
    bu: typing.Optional[str] | None = None
    latitude: typing.Optional[str] = pydantic.Field("", **{})
    longitude: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = BuLevelGeoCoordinatesSchema
        upsert_keys = []
        access_key_mapping = ['bu']


class BuLevelGeoCoordinatesGetResp(pydantic.BaseModel):
    data: typing.List[BuLevelGeoCoordinates]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Bulevelgeocoordinates_Upload_Geo_MasterParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class LpgSubsidyExceptionDataSchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_subsidy_exception_data'
    
    exception__code: Mapped[str] = mapped_column("exception__code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    distributor__code: Mapped[int] = mapped_column("distributor__code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    refills: Mapped[int] = mapped_column("refills", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    consumers: Mapped[int] = mapped_column("consumers", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    
    exception_code: Mapped[str] = mapped_column("exception_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    exception_description: Mapped[str] = mapped_column("exception_description", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    exception_name: Mapped[str] = mapped_column("exception_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    jde_distributor_code: Mapped[int] = mapped_column("jde_distributor_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sa_code: Mapped[str] = mapped_column("sa_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    state_code: Mapped[str] = mapped_column("state_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_code: Mapped[str] = mapped_column("ro_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sa_name: Mapped[str] = mapped_column("sa_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zo_code: Mapped[str] = mapped_column("zo_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_name: Mapped[str] = mapped_column("ro_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zo_name: Mapped[str] = mapped_column("zo_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class LpgSubsidyExceptionDataCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_subsidy_exception_data'
    
    exception__code: str
    distributor__code: int
    refills: int
    consumers: int
    
    exception_code: str
    exception_description: str
    exception_name: str
    jde_distributor_code: int
    sa_code: str
    state_code: str
    ro_code: str
    sa_name: str
    zo_code: str
    ro_name: str
    zo_name: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgSubsidyExceptionDataSchema
        upsert_keys = []
        access_key_mapping = ['JDEDistributorCode:sap_id', 'SAName:sales_area', 'ZOName:zone']


class LpgSubsidyExceptionData(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_subsidy_exception_data'
    
    exception__code: typing.Optional[str] | None = None
    distributor__code: typing.Optional[int] | None = None
    refills: typing.Optional[int] | None = None
    consumers: typing.Optional[int] | None = None
    
    exception_code: typing.Optional[str] | None = None
    exception_description: typing.Optional[str] | None = None
    exception_name: typing.Optional[str] | None = None
    jde_distributor_code: typing.Optional[int] | None = None
    sa_code: typing.Optional[str] | None = None
    state_code: typing.Optional[str] | None = None
    ro_code: typing.Optional[str] | None = None
    sa_name: typing.Optional[str] | None = None
    zo_code: typing.Optional[str] | None = None
    ro_name: typing.Optional[str] | None = None
    zo_name: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgSubsidyExceptionDataSchema
        upsert_keys = []
        access_key_mapping = ['JDEDistributorCode:sap_id', 'SAName:sales_area', 'ZOName:zone']


class LpgSubsidyExceptionDataGetResp(pydantic.BaseModel):
    data: typing.List[LpgSubsidyExceptionData]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class LpgSubsidyFailureDataSchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_subsidy_failure_data'
    
    payment_error_code: Mapped[str] = mapped_column("payment_error_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    distributor__code: Mapped[int] = mapped_column("distributor__code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    refills: Mapped[int] = mapped_column("refills", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    consumers: Mapped[int] = mapped_column("consumers", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    code: Mapped[int] = mapped_column("code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    payment_error_decription: Mapped[str] = mapped_column("payment_error_decription", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    payment_error_name: Mapped[str] = mapped_column("payment_error_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    jde_distributor_code: Mapped[int] = mapped_column("jde_distributor_code", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sa_code: Mapped[str] = mapped_column("sa_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    state_code: Mapped[str] = mapped_column("state_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_code: Mapped[str] = mapped_column("ro_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sa_name: Mapped[str] = mapped_column("sa_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zo_code: Mapped[str] = mapped_column("zo_code", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ro_name: Mapped[str] = mapped_column("ro_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zo_name: Mapped[str] = mapped_column("zo_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class LpgSubsidyFailureDataCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_subsidy_failure_data'
    
    payment_error_code: str
    distributor__code: int
    refills: int
    consumers: int
    code: int
    payment_error_decription: str
    payment_error_name: str
    jde_distributor_code: int
    sa_code: str
    state_code: str
    ro_code: str
    sa_name: str
    zo_code: str
    ro_name: str
    zo_name: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgSubsidyFailureDataSchema
        upsert_keys = []
        access_key_mapping = ['JDEDistributorCode:sap_id', 'SAName:sales_area', 'ZOName:zone']


class LpgSubsidyFailureData(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_subsidy_failure_data'
    
    payment_error_code: typing.Optional[str] | None = None
    distributor__code: typing.Optional[int] | None = None
    refills: typing.Optional[int] | None = None
    consumers: typing.Optional[int] | None = None
    code: typing.Optional[int] | None = None
    payment_error_decription: typing.Optional[str] | None = None
    payment_error_name: typing.Optional[str] | None = None
    jde_distributor_code: typing.Optional[int] | None = None
    sa_code: typing.Optional[str] | None = None
    state_code: typing.Optional[str] | None = None
    ro_code: typing.Optional[str] | None = None
    sa_name: typing.Optional[str] | None = None
    zo_code: typing.Optional[str] | None = None
    ro_name: typing.Optional[str] | None = None
    zo_name: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgSubsidyFailureDataSchema
        upsert_keys = []
        access_key_mapping = ['JDEDistributorCode:sap_id', 'SAName:sales_area', 'ZOName:zone']


class LpgSubsidyFailureDataGetResp(pydantic.BaseModel):
    data: typing.List[LpgSubsidyFailureData]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class LpgOperationsRejectionsSchema(UrdhvaPostgresBase):
    __tablename__ = 'lpg_operations_rejections'
    
    zone: Mapped[str] = mapped_column("zone", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    plant: Mapped[str] = mapped_column("plant", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    cyl_type: Mapped[str] = mapped_column("cyl_type", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    max_date: Mapped[datetime.datetime] = mapped_column("max_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    execution__date: Mapped[datetime.datetime] = mapped_column("execution__date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    process_date: Mapped[datetime.datetime] = mapped_column("process_date", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    sortoutpercentage: Mapped[float] = mapped_column("sortoutpercentage", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    system_id: Mapped[int] = mapped_column("system_id", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    total: Mapped[int] = mapped_column("total", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)


class LpgOperationsRejectionsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'lpg_operations_rejections'
    
    zone: str
    plant: str
    cyl_type: str
    max_date: datetime.datetime
    execution__date: datetime.datetime
    process_date: datetime.datetime
    sortoutpercentage: float
    system_id: int
    total: int

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgOperationsRejectionsSchema
        upsert_keys = []
        access_key_mapping = ['zone']


class LpgOperationsRejections(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'lpg_operations_rejections'
    
    zone: typing.Optional[str] | None = None
    plant: typing.Optional[str] | None = None
    cyl_type: typing.Optional[str] | None = None
    max_date: typing.Optional[datetime.datetime] | None = None
    execution__date: typing.Optional[datetime.datetime] | None = None
    process_date: typing.Optional[datetime.datetime] | None = None
    sortoutpercentage: typing.Optional[float] | None = None
    system_id: typing.Optional[int] | None = None
    total: typing.Optional[int] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = LpgOperationsRejectionsSchema
        upsert_keys = []
        access_key_mapping = ['zone']


class LpgOperationsRejectionsGetResp(pydantic.BaseModel):
    data: typing.List[LpgOperationsRejections]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class ConsumerPumpTransactionsSchema(UrdhvaPostgresBase):
    __tablename__ = 'consumer_pump_transactions'
    
    unique_txn_id: Mapped[int] = mapped_column("unique_txn_id", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bu: Mapped[typing.Optional[str]] = mapped_column("bu", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    txn_id: Mapped[typing.Optional[str]] = mapped_column("txn_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    txn_type: Mapped[typing.Optional[str]] = mapped_column("txn_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    transaction_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("transaction_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    txn_start_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("txn_start_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    txn_end_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("txn_end_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    price: Mapped[typing.Optional[float]] = mapped_column("price", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    quantity: Mapped[typing.Optional[float]] = mapped_column("quantity", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    amount: Mapped[typing.Optional[float]] = mapped_column("amount", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    fuel_equip_type: Mapped[typing.Optional[str]] = mapped_column("fuel_equip_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    vehicle_no: Mapped[typing.Optional[str]] = mapped_column("vehicle_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product_id: Mapped[typing.Optional[str]] = mapped_column("product_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product: Mapped[typing.Optional[str]] = mapped_column("product", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    tank_no: Mapped[typing.Optional[str]] = mapped_column("tank_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    tank_name: Mapped[typing.Optional[str]] = mapped_column("tank_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    pump_no: Mapped[typing.Optional[str]] = mapped_column("pump_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    nozzle_id: Mapped[typing.Optional[str]] = mapped_column("nozzle_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    global_nozzle_id: Mapped[typing.Optional[str]] = mapped_column("global_nozzle_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(unique_txn_id, name="consumer_pump_transactions_unique_txn_id"),)


class ConsumerPumpTransactionsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'consumer_pump_transactions'
    
    unique_txn_id: int
    bu: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    txn_id: typing.Optional[str] = pydantic.Field("", **{})
    txn_type: typing.Optional[str] = pydantic.Field("", **{})
    transaction_date: typing.Optional[datetime.datetime] | None = None
    txn_start_time: typing.Optional[datetime.datetime] | None = None
    txn_end_time: typing.Optional[datetime.datetime] | None = None
    price: typing.Optional[float] = pydantic.Field(0.0, **{})
    quantity: typing.Optional[float] = pydantic.Field(0.0, **{})
    amount: typing.Optional[float] = pydantic.Field(0.0, **{})
    fuel_equip_type: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_no: typing.Optional[str] = pydantic.Field("", **{})
    product_id: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    tank_no: typing.Optional[str] = pydantic.Field("", **{})
    tank_name: typing.Optional[str] = pydantic.Field("", **{})
    pump_no: typing.Optional[str] = pydantic.Field("", **{})
    nozzle_id: typing.Optional[str] = pydantic.Field("", **{})
    global_nozzle_id: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ConsumerPumpTransactionsSchema
        upsert_keys = ['unique_txn_id']
        access_key_mapping = ['ROID:sap_id']


class ConsumerPumpTransactions(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'consumer_pump_transactions'
    
    unique_txn_id: typing.Optional[int] | None = None
    bu: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    txn_id: typing.Optional[str] = pydantic.Field("", **{})
    txn_type: typing.Optional[str] = pydantic.Field("", **{})
    transaction_date: typing.Optional[datetime.datetime] | None = None
    txn_start_time: typing.Optional[datetime.datetime] | None = None
    txn_end_time: typing.Optional[datetime.datetime] | None = None
    price: typing.Optional[float] = pydantic.Field(0.0, **{})
    quantity: typing.Optional[float] = pydantic.Field(0.0, **{})
    amount: typing.Optional[float] = pydantic.Field(0.0, **{})
    fuel_equip_type: typing.Optional[str] = pydantic.Field("", **{})
    vehicle_no: typing.Optional[str] = pydantic.Field("", **{})
    product_id: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    tank_no: typing.Optional[str] = pydantic.Field("", **{})
    tank_name: typing.Optional[str] = pydantic.Field("", **{})
    pump_no: typing.Optional[str] = pydantic.Field("", **{})
    nozzle_id: typing.Optional[str] = pydantic.Field("", **{})
    global_nozzle_id: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ConsumerPumpTransactionsSchema
        upsert_keys = ['unique_txn_id']
        access_key_mapping = ['ROID:sap_id']


class ConsumerPumpTransactionsGetResp(pydantic.BaseModel):
    data: typing.List[ConsumerPumpTransactions]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Consumerpumptransactions_Bulk_Update_Cp_TransactionsParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class ConsumerPumpTankInventorySchema(UrdhvaPostgresBase):
    __tablename__ = 'consumer_pump_tank_inventory'
    
    unique_txn_id: Mapped[int] = mapped_column("unique_txn_id", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bu: Mapped[typing.Optional[str]] = mapped_column("bu", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    inventory_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("inventory_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    tank_id: Mapped[typing.Optional[str]] = mapped_column("tank_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    tank_name: Mapped[typing.Optional[str]] = mapped_column("tank_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    stock_txn_code: Mapped[typing.Optional[str]] = mapped_column("stock_txn_code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    stock_txn_id: Mapped[typing.Optional[str]] = mapped_column("stock_txn_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product_id: Mapped[typing.Optional[str]] = mapped_column("product_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product: Mapped[typing.Optional[str]] = mapped_column("product", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    prod_gross_qty: Mapped[typing.Optional[float]] = mapped_column("prod_gross_qty", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    tank_capacity: Mapped[typing.Optional[float]] = mapped_column("tank_capacity", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    product_volume: Mapped[typing.Optional[float]] = mapped_column("product_volume", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    ullage: Mapped[typing.Optional[float]] = mapped_column("ullage", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    product_level: Mapped[typing.Optional[float]] = mapped_column("product_level", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    density: Mapped[typing.Optional[float]] = mapped_column("density", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    density_at_15: Mapped[typing.Optional[float]] = mapped_column("density_at_15", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(unique_txn_id, name="consumer_pump_tank_inventory_unique_txn_id"),)


class ConsumerPumpTankInventoryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'consumer_pump_tank_inventory'
    
    unique_txn_id: int
    bu: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    inventory_date: typing.Optional[datetime.datetime] | None = None
    tank_id: typing.Optional[str] = pydantic.Field("", **{})
    tank_name: typing.Optional[str] = pydantic.Field("", **{})
    stock_txn_code: typing.Optional[str] = pydantic.Field("", **{})
    stock_txn_id: typing.Optional[str] = pydantic.Field("", **{})
    product_id: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    prod_gross_qty: typing.Optional[float] = pydantic.Field(0.0, **{})
    tank_capacity: typing.Optional[float] = pydantic.Field(0.0, **{})
    product_volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    ullage: typing.Optional[float] = pydantic.Field(0.0, **{})
    product_level: typing.Optional[float] = pydantic.Field(0.0, **{})
    density: typing.Optional[float] = pydantic.Field(0.0, **{})
    density_at_15: typing.Optional[float] = pydantic.Field(0.0, **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ConsumerPumpTankInventorySchema
        upsert_keys = ['unique_txn_id']
        access_key_mapping = ['sap_id']


class ConsumerPumpTankInventory(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'consumer_pump_tank_inventory'
    
    unique_txn_id: typing.Optional[int] | None = None
    bu: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    inventory_date: typing.Optional[datetime.datetime] | None = None
    tank_id: typing.Optional[str] = pydantic.Field("", **{})
    tank_name: typing.Optional[str] = pydantic.Field("", **{})
    stock_txn_code: typing.Optional[str] = pydantic.Field("", **{})
    stock_txn_id: typing.Optional[str] = pydantic.Field("", **{})
    product_id: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    prod_gross_qty: typing.Optional[float] = pydantic.Field(0.0, **{})
    tank_capacity: typing.Optional[float] = pydantic.Field(0.0, **{})
    product_volume: typing.Optional[float] = pydantic.Field(0.0, **{})
    ullage: typing.Optional[float] = pydantic.Field(0.0, **{})
    product_level: typing.Optional[float] = pydantic.Field(0.0, **{})
    density: typing.Optional[float] = pydantic.Field(0.0, **{})
    density_at_15: typing.Optional[float] = pydantic.Field(0.0, **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ConsumerPumpTankInventorySchema
        upsert_keys = ['unique_txn_id']
        access_key_mapping = ['sap_id']


class ConsumerPumpTankInventoryGetResp(pydantic.BaseModel):
    data: typing.List[ConsumerPumpTankInventory]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Consumerpumptankinventory_Bulk_Update_Cp_Tank_InventoryParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class ConsumerPumpStocksReceiptsSchema(UrdhvaPostgresBase):
    __tablename__ = 'consumer_pump_stocks_receipts'
    
    unique_txn_id: Mapped[str] = mapped_column("unique_txn_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    bu: Mapped[typing.Optional[str]] = mapped_column("bu", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    stock_receipt_id: Mapped[typing.Optional[str]] = mapped_column("stock_receipt_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    source: Mapped[typing.Optional[str]] = mapped_column("source", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    prod_qty_start: Mapped[typing.Optional[float]] = mapped_column("prod_qty_start", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    prod_qty_end: Mapped[typing.Optional[float]] = mapped_column("prod_qty_end", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    product_id: Mapped[typing.Optional[str]] = mapped_column("product_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product: Mapped[typing.Optional[str]] = mapped_column("product", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    quantity: Mapped[typing.Optional[float]] = mapped_column("quantity", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    density: Mapped[typing.Optional[float]] = mapped_column("density", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    amount: Mapped[typing.Optional[float]] = mapped_column("amount", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    tank_no: Mapped[typing.Optional[str]] = mapped_column("tank_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    tank_name: Mapped[typing.Optional[str]] = mapped_column("tank_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    decantation_start_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("decantation_start_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    decantation_end_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("decantation_end_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(unique_txn_id, name="consumer_pump_stocks_receipts_unique_txn_id"),)


class ConsumerPumpStocksReceiptsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'consumer_pump_stocks_receipts'
    
    unique_txn_id: str
    bu: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    stock_receipt_id: typing.Optional[str] = pydantic.Field("", **{})
    source: typing.Optional[str] = pydantic.Field("", **{})
    prod_qty_start: typing.Optional[float] = pydantic.Field(0.0, **{})
    prod_qty_end: typing.Optional[float] = pydantic.Field(0.0, **{})
    product_id: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    quantity: typing.Optional[float] = pydantic.Field(0.0, **{})
    density: typing.Optional[float] = pydantic.Field(0.0, **{})
    amount: typing.Optional[float] = pydantic.Field(0.0, **{})
    tank_no: typing.Optional[str] = pydantic.Field("", **{})
    tank_name: typing.Optional[str] = pydantic.Field("", **{})
    decantation_start_time: typing.Optional[datetime.datetime] | None = None
    decantation_end_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ConsumerPumpStocksReceiptsSchema
        upsert_keys = ['unique_txn_id']
        access_key_mapping = ['roid:sap_id']


class ConsumerPumpStocksReceipts(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'consumer_pump_stocks_receipts'
    
    unique_txn_id: typing.Optional[str] | None = None
    bu: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    stock_receipt_id: typing.Optional[str] = pydantic.Field("", **{})
    source: typing.Optional[str] = pydantic.Field("", **{})
    prod_qty_start: typing.Optional[float] = pydantic.Field(0.0, **{})
    prod_qty_end: typing.Optional[float] = pydantic.Field(0.0, **{})
    product_id: typing.Optional[str] = pydantic.Field("", **{})
    product: typing.Optional[str] = pydantic.Field("", **{})
    quantity: typing.Optional[float] = pydantic.Field(0.0, **{})
    density: typing.Optional[float] = pydantic.Field(0.0, **{})
    amount: typing.Optional[float] = pydantic.Field(0.0, **{})
    tank_no: typing.Optional[str] = pydantic.Field("", **{})
    tank_name: typing.Optional[str] = pydantic.Field("", **{})
    decantation_start_time: typing.Optional[datetime.datetime] | None = None
    decantation_end_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ConsumerPumpStocksReceiptsSchema
        upsert_keys = ['unique_txn_id']
        access_key_mapping = ['roid:sap_id']


class ConsumerPumpStocksReceiptsGetResp(pydantic.BaseModel):
    data: typing.List[ConsumerPumpStocksReceipts]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Consumerpumpstocksreceipts_Bulk_Update_Cp_Stock_ReceiptsParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class HostSickTtsSchema(UrdhvaPostgresBase):
    __tablename__ = 'host_sick_tts'
    
    load_number: Mapped[typing.Optional[int]] = mapped_column("load_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    truck_number: Mapped[typing.Optional[str]] = mapped_column("truck_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    created_date: Mapped[typing.Optional[datetime.date]] = mapped_column("created_date", DATE, index=False, nullable=True, default=None, primary_key=False, unique=False)
    customer_name: Mapped[typing.Optional[str]] = mapped_column("customer_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    compartment_number: Mapped[typing.Optional[int]] = mapped_column("compartment_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    product_name: Mapped[typing.Optional[str]] = mapped_column("product_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    required_qty: Mapped[typing.Optional[int]] = mapped_column("required_qty", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    loaded_qty: Mapped[typing.Optional[int]] = mapped_column("loaded_qty", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    sick_declared_by: Mapped[typing.Optional[str]] = mapped_column("sick_declared_by", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sick_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("sick_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    remarks: Mapped[typing.Optional[str]] = mapped_column("remarks", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bcu_number: Mapped[typing.Optional[str]] = mapped_column("bcu_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bay_number: Mapped[typing.Optional[str]] = mapped_column("bay_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    date: Mapped[typing.Optional[datetime.date]] = mapped_column("date", DATE, index=False, nullable=True, default=None, primary_key=False, unique=False)
    date_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("date_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(load_number, truck_number, customer_name, compartment_number, product_name, sap_id, bcu_number, bay_number, date, name="host_sick_tts_loadn_truck_custo_compa_produ_sapid_bcunu_baynu_"),)


class HostSickTtsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'host_sick_tts'
    
    load_number: typing.Optional[int] = pydantic.Field(0, **{})
    truck_number: typing.Optional[str] = pydantic.Field("", **{})
    created_date: typing.Optional[datetime.date] | None = None
    customer_name: typing.Optional[str] = pydantic.Field("", **{})
    compartment_number: typing.Optional[int] = pydantic.Field(0, **{})
    product_name: typing.Optional[str] = pydantic.Field("", **{})
    required_qty: typing.Optional[int] = pydantic.Field(0, **{})
    loaded_qty: typing.Optional[int] = pydantic.Field(0, **{})
    sick_declared_by: typing.Optional[str] = pydantic.Field("", **{})
    sick_date: typing.Optional[datetime.datetime] | None = None
    remarks: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    bay_number: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostSickTtsSchema
        upsert_keys = ['load_number', 'truck_number', 'customer_name', 'compartment_number', 'product_name', 'sap_id', 'bcu_number', 'bay_number', 'date']


class HostSickTts(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'host_sick_tts'
    
    load_number: typing.Optional[int] = pydantic.Field(0, **{})
    truck_number: typing.Optional[str] = pydantic.Field("", **{})
    created_date: typing.Optional[datetime.date] | None = None
    customer_name: typing.Optional[str] = pydantic.Field("", **{})
    compartment_number: typing.Optional[int] = pydantic.Field(0, **{})
    product_name: typing.Optional[str] = pydantic.Field("", **{})
    required_qty: typing.Optional[int] = pydantic.Field(0, **{})
    loaded_qty: typing.Optional[int] = pydantic.Field(0, **{})
    sick_declared_by: typing.Optional[str] = pydantic.Field("", **{})
    sick_date: typing.Optional[datetime.datetime] | None = None
    remarks: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    bay_number: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostSickTtsSchema
        upsert_keys = ['load_number', 'truck_number', 'customer_name', 'compartment_number', 'product_name', 'sap_id', 'bcu_number', 'bay_number', 'date']


class HostSickTtsGetResp(pydantic.BaseModel):
    data: typing.List[HostSickTts]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Hostsicktts_Download_DataParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class HostCancelledTtsSchema(UrdhvaPostgresBase):
    __tablename__ = 'host_cancelled_tts'
    
    load_number: Mapped[typing.Optional[int]] = mapped_column("load_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    truck_number: Mapped[typing.Optional[str]] = mapped_column("truck_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    created_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("created_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    customer_name: Mapped[typing.Optional[str]] = mapped_column("customer_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product_name: Mapped[typing.Optional[str]] = mapped_column("product_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    required_qty: Mapped[typing.Optional[int]] = mapped_column("required_qty", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    cancelled_by: Mapped[typing.Optional[str]] = mapped_column("cancelled_by", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    cancelled_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("cancelled_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    compartment_number: Mapped[typing.Optional[int]] = mapped_column("compartment_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    entry_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("entry_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    exit_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("exit_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    remarks: Mapped[typing.Optional[str]] = mapped_column("remarks", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    date: Mapped[typing.Optional[datetime.date]] = mapped_column("date", DATE, index=False, nullable=True, default=None, primary_key=False, unique=False)
    date_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("date_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(load_number, truck_number, customer_name, product_name, sap_id, compartment_number, date, name="host_cancelled_tts_loadn_truck_custo_produ_sapid_compa_date"),)


class HostCancelledTtsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'host_cancelled_tts'
    
    load_number: typing.Optional[int] = pydantic.Field(0, **{})
    truck_number: typing.Optional[str] = pydantic.Field("", **{})
    created_date: typing.Optional[datetime.datetime] | None = None
    customer_name: typing.Optional[str] = pydantic.Field("", **{})
    product_name: typing.Optional[str] = pydantic.Field("", **{})
    required_qty: typing.Optional[int] = pydantic.Field(0, **{})
    cancelled_by: typing.Optional[str] = pydantic.Field("", **{})
    cancelled_date: typing.Optional[datetime.datetime] | None = None
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    compartment_number: typing.Optional[int] = pydantic.Field(0, **{})
    entry_time: typing.Optional[datetime.datetime] | None = None
    exit_time: typing.Optional[datetime.datetime] | None = None
    remarks: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostCancelledTtsSchema
        upsert_keys = ['load_number', 'truck_number', 'customer_name', 'product_name', 'sap_id', 'compartment_number', 'date']


class HostCancelledTts(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'host_cancelled_tts'
    
    load_number: typing.Optional[int] = pydantic.Field(0, **{})
    truck_number: typing.Optional[str] = pydantic.Field("", **{})
    created_date: typing.Optional[datetime.datetime] | None = None
    customer_name: typing.Optional[str] = pydantic.Field("", **{})
    product_name: typing.Optional[str] = pydantic.Field("", **{})
    required_qty: typing.Optional[int] = pydantic.Field(0, **{})
    cancelled_by: typing.Optional[str] = pydantic.Field("", **{})
    cancelled_date: typing.Optional[datetime.datetime] | None = None
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    compartment_number: typing.Optional[int] = pydantic.Field(0, **{})
    entry_time: typing.Optional[datetime.datetime] | None = None
    exit_time: typing.Optional[datetime.datetime] | None = None
    remarks: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostCancelledTtsSchema
        upsert_keys = ['load_number', 'truck_number', 'customer_name', 'product_name', 'sap_id', 'compartment_number', 'date']


class HostCancelledTtsGetResp(pydantic.BaseModel):
    data: typing.List[HostCancelledTts]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class HostKFactorChangesSchema(UrdhvaPostgresBase):
    __tablename__ = 'host_k_factor_changes'
    
    sr_number: Mapped[typing.Optional[int]] = mapped_column("sr_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    bay_number: Mapped[typing.Optional[str]] = mapped_column("bay_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bcu_number: Mapped[typing.Optional[str]] = mapped_column("bcu_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    preset_number: Mapped[typing.Optional[str]] = mapped_column("preset_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    timestamp: Mapped[typing.Optional[datetime.datetime]] = mapped_column("timestamp", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    bcu_parameter: Mapped[typing.Optional[str]] = mapped_column("bcu_parameter", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    initial_setting: Mapped[typing.Optional[str]] = mapped_column("initial_setting", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    final_setting: Mapped[typing.Optional[str]] = mapped_column("final_setting", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(bcu_number, preset_number, timestamp, initial_setting, final_setting, sap_id, name="host_k_factor_changes_bcunu_prese_times_initi_final_sapid"),)


class HostKFactorChangesCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'host_k_factor_changes'
    
    sr_number: typing.Optional[int] = pydantic.Field(0, **{})
    bay_number: typing.Optional[str] = pydantic.Field("", **{})
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    preset_number: typing.Optional[str] = pydantic.Field("", **{})
    timestamp: typing.Optional[datetime.datetime] | None = None
    bcu_parameter: typing.Optional[str] = pydantic.Field("", **{})
    initial_setting: typing.Optional[str] = pydantic.Field("", **{})
    final_setting: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostKFactorChangesSchema
        upsert_keys = ['bcu_number', 'preset_number', 'timestamp', 'initial_setting', 'final_setting', 'sap_id']


class HostKFactorChanges(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'host_k_factor_changes'
    
    sr_number: typing.Optional[int] = pydantic.Field(0, **{})
    bay_number: typing.Optional[str] = pydantic.Field("", **{})
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    preset_number: typing.Optional[str] = pydantic.Field("", **{})
    timestamp: typing.Optional[datetime.datetime] | None = None
    bcu_parameter: typing.Optional[str] = pydantic.Field("", **{})
    initial_setting: typing.Optional[str] = pydantic.Field("", **{})
    final_setting: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostKFactorChangesSchema
        upsert_keys = ['bcu_number', 'preset_number', 'timestamp', 'initial_setting', 'final_setting', 'sap_id']


class HostKFactorChangesGetResp(pydantic.BaseModel):
    data: typing.List[HostKFactorChanges]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class HostLocalLoadedTtsSchema(UrdhvaPostgresBase):
    __tablename__ = 'host_local_loaded_tts'
    
    sr_number: Mapped[typing.Optional[int]] = mapped_column("sr_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    bay_number: Mapped[typing.Optional[str]] = mapped_column("bay_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bcu_number: Mapped[typing.Optional[str]] = mapped_column("bcu_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    recipe_name: Mapped[typing.Optional[str]] = mapped_column("recipe_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    truck_number: Mapped[typing.Optional[str]] = mapped_column("truck_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    card_number: Mapped[typing.Optional[str]] = mapped_column("card_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    start_totalizer: Mapped[typing.Optional[float]] = mapped_column("start_totalizer", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    end_totalizer: Mapped[typing.Optional[float]] = mapped_column("end_totalizer", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    loaded_qty: Mapped[typing.Optional[int]] = mapped_column("loaded_qty", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    transaction_end_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("transaction_end_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    compartment_number: Mapped[typing.Optional[int]] = mapped_column("compartment_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    date: Mapped[typing.Optional[datetime.date]] = mapped_column("date", DATE, index=False, nullable=True, default=None, primary_key=False, unique=False)
    date_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("date_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(sr_number, bcu_number, recipe_name, truck_number, card_number, start_totalizer, end_totalizer, loaded_qty, sap_id, compartment_number, date, name="host_local_loaded_tts_srnum_bcunu_recip_truck_cardn_start_endt"),)


class HostLocalLoadedTtsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'host_local_loaded_tts'
    
    sr_number: typing.Optional[int] = pydantic.Field(0, **{})
    bay_number: typing.Optional[str] = pydantic.Field("", **{})
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    recipe_name: typing.Optional[str] = pydantic.Field("", **{})
    truck_number: typing.Optional[str] = pydantic.Field("", **{})
    card_number: typing.Optional[str] = pydantic.Field("", **{})
    start_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    loaded_qty: typing.Optional[int] = pydantic.Field(0, **{})
    transaction_end_time: typing.Optional[datetime.datetime] | None = None
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    compartment_number: typing.Optional[int] = pydantic.Field(0, **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostLocalLoadedTtsSchema
        upsert_keys = ['sr_number', 'bcu_number', 'recipe_name', 'truck_number', 'card_number', 'start_totalizer', 'end_totalizer', 'loaded_qty', 'sap_id', 'compartment_number', 'date']


class HostLocalLoadedTts(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'host_local_loaded_tts'
    
    sr_number: typing.Optional[int] = pydantic.Field(0, **{})
    bay_number: typing.Optional[str] = pydantic.Field("", **{})
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    recipe_name: typing.Optional[str] = pydantic.Field("", **{})
    truck_number: typing.Optional[str] = pydantic.Field("", **{})
    card_number: typing.Optional[str] = pydantic.Field("", **{})
    start_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    loaded_qty: typing.Optional[int] = pydantic.Field(0, **{})
    transaction_end_time: typing.Optional[datetime.datetime] | None = None
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    compartment_number: typing.Optional[int] = pydantic.Field(0, **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostLocalLoadedTtsSchema
        upsert_keys = ['sr_number', 'bcu_number', 'recipe_name', 'truck_number', 'card_number', 'start_totalizer', 'end_totalizer', 'loaded_qty', 'sap_id', 'compartment_number', 'date']


class HostLocalLoadedTtsGetResp(pydantic.BaseModel):
    data: typing.List[HostLocalLoadedTts]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class HostBayReAssignmentSchema(UrdhvaPostgresBase):
    __tablename__ = 'host_bay_re_assignment'
    
    created_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("created_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    load_number: Mapped[typing.Optional[int]] = mapped_column("load_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    fan_number: Mapped[typing.Optional[str]] = mapped_column("fan_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    truck_number: Mapped[typing.Optional[str]] = mapped_column("truck_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    customer_name: Mapped[typing.Optional[str]] = mapped_column("customer_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    compartment_number: Mapped[typing.Optional[int]] = mapped_column("compartment_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    product_name: Mapped[typing.Optional[str]] = mapped_column("product_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    required_qty: Mapped[typing.Optional[int]] = mapped_column("required_qty", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    loaded_qty: Mapped[typing.Optional[int]] = mapped_column("loaded_qty", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    reassigned_bay: Mapped[typing.Optional[str]] = mapped_column("reassigned_bay", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bay_reassignment_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("bay_reassignment_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    remarks: Mapped[typing.Optional[str]] = mapped_column("remarks", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    assigned_bay: Mapped[typing.Optional[str]] = mapped_column("assigned_bay", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    reassign_loaded_qty: Mapped[typing.Optional[int]] = mapped_column("reassign_loaded_qty", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    date: Mapped[typing.Optional[datetime.date]] = mapped_column("date", DATE, index=False, nullable=True, default=None, primary_key=False, unique=False)
    date_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("date_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(load_number, truck_number, customer_name, compartment_number, product_name, required_qty, loaded_qty, sap_id, assigned_bay, reassign_loaded_qty, date, name="host_bay_re_assignment_loadn_truck_custo_compa_produ_requi_loa"),)


class HostBayReAssignmentCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'host_bay_re_assignment'
    
    created_date: typing.Optional[datetime.datetime] | None = None
    load_number: typing.Optional[int] = pydantic.Field(0, **{})
    fan_number: typing.Optional[str] = pydantic.Field("", **{})
    truck_number: typing.Optional[str] = pydantic.Field("", **{})
    customer_name: typing.Optional[str] = pydantic.Field("", **{})
    compartment_number: typing.Optional[int] = pydantic.Field(0, **{})
    product_name: typing.Optional[str] = pydantic.Field("", **{})
    required_qty: typing.Optional[int] = pydantic.Field(0, **{})
    loaded_qty: typing.Optional[int] = pydantic.Field(0, **{})
    reassigned_bay: typing.Optional[str] = pydantic.Field("", **{})
    bay_reassignment_time: typing.Optional[datetime.datetime] | None = None
    remarks: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    assigned_bay: typing.Optional[str] = pydantic.Field("", **{})
    reassign_loaded_qty: typing.Optional[int] = pydantic.Field(0, **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostBayReAssignmentSchema
        upsert_keys = ['load_number', 'truck_number', 'customer_name', 'compartment_number', 'product_name', 'required_qty', 'loaded_qty', 'sap_id', 'assigned_bay', 'reassign_loaded_qty', 'date']


class HostBayReAssignment(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'host_bay_re_assignment'
    
    created_date: typing.Optional[datetime.datetime] | None = None
    load_number: typing.Optional[int] = pydantic.Field(0, **{})
    fan_number: typing.Optional[str] = pydantic.Field("", **{})
    truck_number: typing.Optional[str] = pydantic.Field("", **{})
    customer_name: typing.Optional[str] = pydantic.Field("", **{})
    compartment_number: typing.Optional[int] = pydantic.Field(0, **{})
    product_name: typing.Optional[str] = pydantic.Field("", **{})
    required_qty: typing.Optional[int] = pydantic.Field(0, **{})
    loaded_qty: typing.Optional[int] = pydantic.Field(0, **{})
    reassigned_bay: typing.Optional[str] = pydantic.Field("", **{})
    bay_reassignment_time: typing.Optional[datetime.datetime] | None = None
    remarks: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    assigned_bay: typing.Optional[str] = pydantic.Field("", **{})
    reassign_loaded_qty: typing.Optional[int] = pydantic.Field(0, **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostBayReAssignmentSchema
        upsert_keys = ['load_number', 'truck_number', 'customer_name', 'compartment_number', 'product_name', 'required_qty', 'loaded_qty', 'sap_id', 'assigned_bay', 'reassign_loaded_qty', 'date']


class HostBayReAssignmentGetResp(pydantic.BaseModel):
    data: typing.List[HostBayReAssignment]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class HostManualBayAssignedSchema(UrdhvaPostgresBase):
    __tablename__ = 'host_manual_bay_assigned'
    
    sr_number: Mapped[typing.Optional[int]] = mapped_column("sr_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    user_name: Mapped[typing.Optional[str]] = mapped_column("user_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    timestamp: Mapped[typing.Optional[datetime.datetime]] = mapped_column("timestamp", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    text: Mapped[typing.Optional[str]] = mapped_column("text", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(user_name, timestamp, sap_id, name="host_manual_bay_assigned_user_name_timestamp_sap_id"),)


class HostManualBayAssignedCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'host_manual_bay_assigned'
    
    sr_number: typing.Optional[int] = pydantic.Field(0, **{})
    user_name: typing.Optional[str] = pydantic.Field("", **{})
    timestamp: typing.Optional[datetime.datetime] | None = None
    text: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostManualBayAssignedSchema
        upsert_keys = ['user_name', 'timestamp', 'sap_id']


class HostManualBayAssigned(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'host_manual_bay_assigned'
    
    sr_number: typing.Optional[int] = pydantic.Field(0, **{})
    user_name: typing.Optional[str] = pydantic.Field("", **{})
    timestamp: typing.Optional[datetime.datetime] | None = None
    text: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostManualBayAssignedSchema
        upsert_keys = ['user_name', 'timestamp', 'sap_id']


class HostManualBayAssignedGetResp(pydantic.BaseModel):
    data: typing.List[HostManualBayAssigned]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class HostManualFanPrintedSchema(UrdhvaPostgresBase):
    __tablename__ = 'host_manual_fan_printed'
    
    manual_fan_count: Mapped[typing.Optional[int]] = mapped_column("manual_fan_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    auto_fan_count: Mapped[typing.Optional[int]] = mapped_column("auto_fan_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    total_count: Mapped[typing.Optional[int]] = mapped_column("total_count", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    date: Mapped[typing.Optional[datetime.date]] = mapped_column("date", DATE, index=False, nullable=True, default=None, primary_key=False, unique=False)
    date_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("date_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(auto_fan_count, total_count, date, sap_id, name="host_manual_fan_printed_auto_fan_count_total_count_date_sap_id"),)


class HostManualFanPrintedCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'host_manual_fan_printed'
    
    manual_fan_count: typing.Optional[int] = pydantic.Field(0, **{})
    auto_fan_count: typing.Optional[int] = pydantic.Field(0, **{})
    total_count: typing.Optional[int] = pydantic.Field(0, **{})
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostManualFanPrintedSchema
        upsert_keys = ['auto_fan_count', 'total_count', 'date', 'sap_id']


class HostManualFanPrinted(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'host_manual_fan_printed'
    
    manual_fan_count: typing.Optional[int] = pydantic.Field(0, **{})
    auto_fan_count: typing.Optional[int] = pydantic.Field(0, **{})
    total_count: typing.Optional[int] = pydantic.Field(0, **{})
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostManualFanPrintedSchema
        upsert_keys = ['auto_fan_count', 'total_count', 'date', 'sap_id']


class HostManualFanPrintedGetResp(pydantic.BaseModel):
    data: typing.List[HostManualFanPrinted]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class HostUnauthorisedFlowSchema(UrdhvaPostgresBase):
    __tablename__ = 'host_unauthorised_flow'
    
    bay_number: Mapped[typing.Optional[str]] = mapped_column("bay_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bcu_number: Mapped[typing.Optional[str]] = mapped_column("bcu_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    meter_number: Mapped[typing.Optional[int]] = mapped_column("meter_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    timestamp: Mapped[typing.Optional[datetime.datetime]] = mapped_column("timestamp", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    start_totalizer: Mapped[typing.Optional[float]] = mapped_column("start_totalizer", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    end_totalizer: Mapped[typing.Optional[float]] = mapped_column("end_totalizer", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    net_totalizer: Mapped[typing.Optional[float]] = mapped_column("net_totalizer", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    date: Mapped[typing.Optional[datetime.date]] = mapped_column("date", DATE, index=False, nullable=True, default=None, primary_key=False, unique=False)
    date_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("date_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    nettotalizer: Mapped[typing.Optional[float]] = mapped_column("nettotalizer", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(bcu_number, meter_number, timestamp, start_totalizer, end_totalizer, net_totalizer, sap_id, date, nettotalizer, name="host_unauthorised_flow_bcunu_meter_times_start_endto_netto_sap"),)


class HostUnauthorisedFlowCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'host_unauthorised_flow'
    
    bay_number: typing.Optional[str] = pydantic.Field("", **{})
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    meter_number: typing.Optional[int] = pydantic.Field(0, **{})
    timestamp: typing.Optional[datetime.datetime] | None = None
    start_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    net_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None
    nettotalizer: typing.Optional[float] = pydantic.Field(0.0, **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostUnauthorisedFlowSchema
        upsert_keys = ['bcu_number', 'meter_number', 'timestamp', 'start_totalizer', 'end_totalizer', 'net_totalizer', 'sap_id', 'date', 'nettotalizer']


class HostUnauthorisedFlow(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'host_unauthorised_flow'
    
    bay_number: typing.Optional[str] = pydantic.Field("", **{})
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    meter_number: typing.Optional[int] = pydantic.Field(0, **{})
    timestamp: typing.Optional[datetime.datetime] | None = None
    start_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    end_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    net_totalizer: typing.Optional[float] = pydantic.Field(0.0, **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None
    nettotalizer: typing.Optional[float] = pydantic.Field(0.0, **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostUnauthorisedFlowSchema
        upsert_keys = ['bcu_number', 'meter_number', 'timestamp', 'start_totalizer', 'end_totalizer', 'net_totalizer', 'sap_id', 'date', 'nettotalizer']


class HostUnauthorisedFlowGetResp(pydantic.BaseModel):
    data: typing.List[HostUnauthorisedFlow]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class HostOverLoadedTtsSchema(UrdhvaPostgresBase):
    __tablename__ = 'host_over_loaded_tts'
    
    load_number: Mapped[typing.Optional[int]] = mapped_column("load_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    truck_number: Mapped[typing.Optional[str]] = mapped_column("truck_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    compartment_number: Mapped[typing.Optional[int]] = mapped_column("compartment_number", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    product_name: Mapped[typing.Optional[str]] = mapped_column("product_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    required_qty: Mapped[typing.Optional[int]] = mapped_column("required_qty", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    loaded_qty: Mapped[typing.Optional[int]] = mapped_column("loaded_qty", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    created_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("created_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    bcu_number: Mapped[typing.Optional[str]] = mapped_column("bcu_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bay_number: Mapped[typing.Optional[str]] = mapped_column("bay_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)
    date: Mapped[typing.Optional[datetime.date]] = mapped_column("date", DATE, index=False, nullable=True, default=None, primary_key=False, unique=False)
    date_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column("date_time", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(load_number, truck_number, compartment_number, product_name, required_qty, loaded_qty, sap_id, bcu_number, bay_number, date, name="host_over_loaded_tts_loadn_truck_compa_produ_requi_loade_sapid"),)


class HostOverLoadedTtsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'host_over_loaded_tts'
    
    load_number: typing.Optional[int] = pydantic.Field(0, **{})
    truck_number: typing.Optional[str] = pydantic.Field("", **{})
    compartment_number: typing.Optional[int] = pydantic.Field(0, **{})
    product_name: typing.Optional[str] = pydantic.Field("", **{})
    required_qty: typing.Optional[int] = pydantic.Field(0, **{})
    loaded_qty: typing.Optional[int] = pydantic.Field(0, **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    created_date: typing.Optional[datetime.datetime] | None = None
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    bay_number: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostOverLoadedTtsSchema
        upsert_keys = ['load_number', 'truck_number', 'compartment_number', 'product_name', 'required_qty', 'loaded_qty', 'sap_id', 'bcu_number', 'bay_number', 'date']


class HostOverLoadedTts(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'host_over_loaded_tts'
    
    load_number: typing.Optional[int] = pydantic.Field(0, **{})
    truck_number: typing.Optional[str] = pydantic.Field("", **{})
    compartment_number: typing.Optional[int] = pydantic.Field(0, **{})
    product_name: typing.Optional[str] = pydantic.Field("", **{})
    required_qty: typing.Optional[int] = pydantic.Field(0, **{})
    loaded_qty: typing.Optional[int] = pydantic.Field(0, **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    created_date: typing.Optional[datetime.datetime] | None = None
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    bay_number: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )
    date: typing.Optional[datetime.date] | None = None
    date_time: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostOverLoadedTtsSchema
        upsert_keys = ['load_number', 'truck_number', 'compartment_number', 'product_name', 'required_qty', 'loaded_qty', 'sap_id', 'bcu_number', 'bay_number', 'date']


class HostOverLoadedTtsGetResp(pydantic.BaseModel):
    data: typing.List[HostOverLoadedTts]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class HostMFMFactorSchema(UrdhvaPostgresBase):
    __tablename__ = 'host_mfm_factor'
    
    mfm_number: Mapped[typing.Optional[str]] = mapped_column("mfm_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    bcu_number: Mapped[typing.Optional[str]] = mapped_column("bcu_number", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    stock_code: Mapped[typing.Optional[str]] = mapped_column("stock_code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    current_k_factor: Mapped[typing.Optional[float]] = mapped_column("current_k_factor", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    last_k_factor: Mapped[typing.Optional[str]] = mapped_column("last_k_factor", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    last_k_factor_change_date: Mapped[typing.Optional[str]] = mapped_column("last_k_factor_change_date", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    current_meter_factor: Mapped[typing.Optional[float]] = mapped_column("current_meter_factor", Numeric, index=False, nullable=True, default=0.0, primary_key=False, unique=False)
    last_meter_factor: Mapped[typing.Optional[str]] = mapped_column("last_meter_factor", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    last_meter_factor_change_date: Mapped[typing.Optional[str]] = mapped_column("last_meter_factor_change_date", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(mfm_number, stock_code, sap_id, name="host_mfm_factor_mfm_number_stock_code_sap_id"),)


class HostMFMFactorCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'host_mfm_factor'
    
    mfm_number: typing.Optional[str] = pydantic.Field("", **{})
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    stock_code: typing.Optional[str] = pydantic.Field("", **{})
    current_k_factor: typing.Optional[float] = pydantic.Field(0.0, **{})
    last_k_factor: typing.Optional[str] = pydantic.Field("", **{})
    last_k_factor_change_date: typing.Optional[str] = pydantic.Field("", **{})
    current_meter_factor: typing.Optional[float] = pydantic.Field(0.0, **{})
    last_meter_factor: typing.Optional[str] = pydantic.Field("", **{})
    last_meter_factor_change_date: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostMFMFactorSchema
        upsert_keys = ['mfm_number', 'stock_code', 'sap_id']


class HostMFMFactor(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'host_mfm_factor'
    
    mfm_number: typing.Optional[str] = pydantic.Field("", **{})
    bcu_number: typing.Optional[str] = pydantic.Field("", **{})
    stock_code: typing.Optional[str] = pydantic.Field("", **{})
    current_k_factor: typing.Optional[float] = pydantic.Field(0.0, **{})
    last_k_factor: typing.Optional[str] = pydantic.Field("", **{})
    last_k_factor_change_date: typing.Optional[str] = pydantic.Field("", **{})
    current_meter_factor: typing.Optional[float] = pydantic.Field(0.0, **{})
    last_meter_factor: typing.Optional[str] = pydantic.Field("", **{})
    last_meter_factor_change_date: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = HostMFMFactorSchema
        upsert_keys = ['mfm_number', 'stock_code', 'sap_id']


class HostMFMFactorGetResp(pydantic.BaseModel):
    data: typing.List[HostMFMFactor]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class MasterStatusSchema(UrdhvaPostgresBase):
    __tablename__ = 'master_status'
    
    status: Mapped[typing.Optional[int]] = mapped_column("status", Integer, index=False, nullable=True, default=0, primary_key=False, unique=False)
    location_code: Mapped[typing.Optional[str]] = mapped_column("location_code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    active_server_name: Mapped[typing.Optional[str]] = mapped_column("active_server_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_created: Mapped[typing.Optional[bool]] = mapped_column("alert_created", Boolean, index=False, nullable=True, default=False, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(status, location_code, sap_id, name="master_status_status_location_code_sap_id"),)


class MasterStatusCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'master_status'
    
    status: typing.Optional[int] = pydantic.Field(0, **{})
    location_code: typing.Optional[str] = pydantic.Field("", **{})
    active_server_name: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = MasterStatusSchema
        upsert_keys = ['status', 'location_code', 'sap_id']


class MasterStatus(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'master_status'
    
    status: typing.Optional[int] = pydantic.Field(0, **{})
    location_code: typing.Optional[str] = pydantic.Field("", **{})
    active_server_name: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    alert_created: typing.Optional[bool] = pydantic.Field(False, )

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = MasterStatusSchema
        upsert_keys = ['status', 'location_code', 'sap_id']


class MasterStatusGetResp(pydantic.BaseModel):
    data: typing.List[MasterStatus]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class TagsDataSchema(UrdhvaPostgresBase):
    __tablename__ = 'tags_data'
    
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    name: Mapped[typing.Optional[str]] = mapped_column("name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_type: Mapped[typing.Optional[str]] = mapped_column("device_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    count: Mapped[typing.Optional[str]] = mapped_column("count", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_count: Mapped[typing.Optional[str]] = mapped_column("device_count", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    system: Mapped[typing.Optional[str]] = mapped_column("system", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    equipment_name: Mapped[typing.Optional[str]] = mapped_column("equipment_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    mf_count: Mapped[typing.Optional[str]] = mapped_column("mf_count", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class TagsDataCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'tags_data'
    
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    name: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    count: typing.Optional[str] = pydantic.Field("", **{})
    device_count: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    system: typing.Optional[str] = pydantic.Field("", **{})
    equipment_name: typing.Optional[str] = pydantic.Field("", **{})
    mf_count: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = TagsDataSchema
        upsert_keys = []
        search_fields = ['sap_id', 'name', 'device_type', 'zone', 'system']


class TagsData(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'tags_data'
    
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    name: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    count: typing.Optional[str] = pydantic.Field("", **{})
    device_count: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    system: typing.Optional[str] = pydantic.Field("", **{})
    equipment_name: typing.Optional[str] = pydantic.Field("", **{})
    mf_count: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = TagsDataSchema
        upsert_keys = []
        search_fields = ['sap_id', 'name', 'device_type', 'zone', 'system']


class TagsDataGetResp(pydantic.BaseModel):
    data: typing.List[TagsData]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Tagsdata_Things_Board_Device_DataParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Tagsdata_Get_Tags_DataParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class ArchitectureDataSchema(UrdhvaPostgresBase):
    __tablename__ = 'architecture_data'
    
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    name: Mapped[typing.Optional[str]] = mapped_column("name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_type: Mapped[typing.Optional[str]] = mapped_column("device_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    count: Mapped[typing.Optional[str]] = mapped_column("count", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    system: Mapped[typing.Optional[str]] = mapped_column("system", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    equipment_name: Mapped[typing.Optional[str]] = mapped_column("equipment_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)


class ArchitectureDataCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'architecture_data'
    
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    name: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    count: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    system: typing.Optional[str] = pydantic.Field("", **{})
    equipment_name: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ArchitectureDataSchema
        upsert_keys = []


class ArchitectureData(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'architecture_data'
    
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    name: typing.Optional[str] = pydantic.Field("", **{})
    device_type: typing.Optional[str] = pydantic.Field("", **{})
    count: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    system: typing.Optional[str] = pydantic.Field("", **{})
    equipment_name: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = ArchitectureDataSchema
        upsert_keys = []


class ArchitectureDataGetResp(pydantic.BaseModel):
    data: typing.List[ArchitectureData]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Architecturedata_Architecture_DetailsParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Architecturedata_Architecture_DataParams(pydantic.BaseModel):
    pass

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class PerformanceIndexSchema(UrdhvaPostgresBase):
    __tablename__ = 'performance_index'
    
    bu: Mapped[str] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    category: Mapped[str] = mapped_column("category", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[str] = mapped_column("zone", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[str] = mapped_column("region", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    name: Mapped[str] = mapped_column("name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    score: Mapped[float] = mapped_column("score", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)


class PerformanceIndexCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'performance_index'
    
    bu: str
    sap_id: str
    category: str
    zone: str
    region: str
    name: str
    score: float

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = PerformanceIndexSchema
        upsert_keys = []


class PerformanceIndex(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'performance_index'
    
    bu: typing.Optional[str] | None = None
    sap_id: typing.Optional[str] | None = None
    category: typing.Optional[str] | None = None
    zone: typing.Optional[str] | None = None
    region: typing.Optional[str] | None = None
    name: typing.Optional[str] | None = None
    score: typing.Optional[float] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = PerformanceIndexSchema
        upsert_keys = []


class PerformanceIndexGetResp(pydantic.BaseModel):
    data: typing.List[PerformanceIndex]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Performanceindex_Get_Pi_ScoreParams(pydantic.BaseModel):
    bu: str
    category: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    strategy: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Performanceindex_Get_Pi_Score_By_CategoryParams(pydantic.BaseModel):
    bu: str
    region: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class PerformanceScoreResultsSchema(UrdhvaPostgresBase):
    __tablename__ = 'performance_score_results'
    
    name: Mapped[str] = mapped_column("name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    score: Mapped[float] = mapped_column("score", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    weightage: Mapped[float] = mapped_column("weightage", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    module: Mapped[str] = mapped_column("module", String, index=False, nullable=False, default=None, primary_key=False, unique=False)


class PerformanceScoreResultsCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'performance_score_results'
    
    name: str
    score: float
    weightage: float
    module: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = PerformanceScoreResultsSchema
        upsert_keys = []


class PerformanceScoreResults(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'performance_score_results'
    
    name: typing.Optional[str] | None = None
    score: typing.Optional[float] | None = None
    weightage: typing.Optional[float] | None = None
    module: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = PerformanceScoreResultsSchema
        upsert_keys = []


class PerformanceScoreResultsGetResp(pydantic.BaseModel):
    data: typing.List[PerformanceScoreResults]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class PerformanceScoreCategorySchema(UrdhvaPostgresBase):
    __tablename__ = 'performance_score_category'
    
    name: Mapped[str] = mapped_column("name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    score: Mapped[float] = mapped_column("score", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    weightage: Mapped[float] = mapped_column("weightage", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    results: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("results", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)


class PerformanceScoreCategoryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'performance_score_category'
    
    name: str
    score: float
    weightage: float
    results: typing.Optional[typing.List[PerformanceScoreResults]] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = PerformanceScoreCategorySchema
        upsert_keys = []


class PerformanceScoreCategory(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'performance_score_category'
    
    name: typing.Optional[str] | None = None
    score: typing.Optional[float] | None = None
    weightage: typing.Optional[float] | None = None
    results: typing.Optional[typing.List[PerformanceScoreResults]] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = PerformanceScoreCategorySchema
        upsert_keys = []


class PerformanceScoreCategoryGetResp(pydantic.BaseModel):
    data: typing.List[PerformanceScoreCategory]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class PerformanceScoreSchema(UrdhvaPostgresBase):
    __tablename__ = 'performance_score'
    
    bu: Mapped[str] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    timestamp: Mapped[datetime.datetime] = mapped_column("timestamp", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[str] = mapped_column("zone", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[str] = mapped_column("region", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    name: Mapped[str] = mapped_column("name", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    score: Mapped[float] = mapped_column("score", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    national_score: Mapped[float] = mapped_column("national_score", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    rank: Mapped[int] = mapped_column("rank", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    category: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("category", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(sap_id, name="performance_score_sap_id"),)


class PerformanceScoreCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'performance_score'
    
    bu: str
    sap_id: str
    timestamp: datetime.datetime
    zone: str
    region: str
    name: str
    score: float
    national_score: float
    rank: int
    category: typing.Optional[typing.List[PerformanceScoreCategory]] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = PerformanceScoreSchema
        upsert_keys = ['sap_id']
        access_key_mapping = ['location_id:sap_id']


class PerformanceScore(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'performance_score'
    
    bu: typing.Optional[str] | None = None
    sap_id: typing.Optional[str] | None = None
    timestamp: typing.Optional[datetime.datetime] | None = None
    zone: typing.Optional[str] | None = None
    region: typing.Optional[str] | None = None
    name: typing.Optional[str] | None = None
    score: typing.Optional[float] | None = None
    national_score: typing.Optional[float] | None = None
    rank: typing.Optional[int] | None = None
    category: typing.Optional[typing.List[PerformanceScoreCategory]] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = PerformanceScoreSchema
        upsert_keys = ['sap_id']
        access_key_mapping = ['location_id:sap_id']


class PerformanceScoreGetResp(pydantic.BaseModel):
    data: typing.List[PerformanceScore]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Performancescore_Get_Pi_ScoreParams(pydantic.BaseModel):
    bu: str
    category: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    zone: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    strategy: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class PerformanceScoreHistorySchema(UrdhvaPostgresBase):
    __tablename__ = 'performance_score_history'
    
    bu: Mapped[str] = mapped_column("bu", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    timestamp: Mapped[datetime.datetime] = mapped_column("timestamp", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[str] = mapped_column("zone", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    region: Mapped[str] = mapped_column("region", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    name: Mapped[str] = mapped_column("name", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    score: Mapped[float] = mapped_column("score", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    national_score: Mapped[float] = mapped_column("national_score", Numeric, index=False, nullable=False, default=None, primary_key=False, unique=False)
    rank: Mapped[int] = mapped_column("rank", Integer, index=False, nullable=False, default=None, primary_key=False, unique=False)
    category: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("category", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)


class PerformanceScoreHistoryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'performance_score_history'
    
    bu: str
    sap_id: str
    timestamp: datetime.datetime
    zone: str
    region: str
    name: str
    score: float
    national_score: float
    rank: int
    category: typing.Optional[typing.List[PerformanceScoreCategory]] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = PerformanceScoreHistorySchema
        upsert_keys = []
        access_key_mapping = ['location_id:sap_id']


class PerformanceScoreHistory(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'performance_score_history'
    
    bu: typing.Optional[str] | None = None
    sap_id: typing.Optional[str] | None = None
    timestamp: typing.Optional[datetime.datetime] | None = None
    zone: typing.Optional[str] | None = None
    region: typing.Optional[str] | None = None
    name: typing.Optional[str] | None = None
    score: typing.Optional[float] | None = None
    national_score: typing.Optional[float] | None = None
    rank: typing.Optional[int] | None = None
    category: typing.Optional[typing.List[PerformanceScoreCategory]] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = PerformanceScoreHistorySchema
        upsert_keys = []
        access_key_mapping = ['location_id:sap_id']


class PerformanceScoreHistoryGetResp(pydantic.BaseModel):
    data: typing.List[PerformanceScoreHistory]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class CrisAlertHistorySchema(UrdhvaPostgresBase):
    __tablename__ = 'cris_alert_history'
    
    vendor_name: Mapped[typing.Optional[str]] = mapped_column("vendor_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    vendor_id: Mapped[typing.Optional[str]] = mapped_column("vendor_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_id: Mapped[typing.Optional[str]] = mapped_column("location_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_type: Mapped[typing.Optional[str]] = mapped_column("location_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    ro_code: Mapped[typing.Optional[str]] = mapped_column("ro_code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_type: Mapped[typing.Optional[str]] = mapped_column("interlock_type", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_description: Mapped[typing.Optional[str]] = mapped_column("interlock_description", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_name: Mapped[typing.Optional[str]] = mapped_column("device_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    device_id: Mapped[typing.Optional[str]] = mapped_column("device_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    severity: Mapped[typing.Optional[str]] = mapped_column("severity", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    tank_id: Mapped[typing.Optional[str]] = mapped_column("tank_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    nozzle_id: Mapped[typing.Optional[str]] = mapped_column("nozzle_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    pump_no: Mapped[typing.Optional[str]] = mapped_column("pump_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alarm_id: Mapped[str] = mapped_column("alarm_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    occurrence_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("occurrence_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    closure_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("closure_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    indent_no: Mapped[typing.Optional[str]] = mapped_column("indent_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    products: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("products", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(alarm_id, name="cris_alert_history_alarm_id"),)


class CrisAlertHistoryCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'cris_alert_history'
    
    vendor_name: typing.Optional[str] = pydantic.Field("", **{})
    vendor_id: typing.Optional[str] = pydantic.Field("", **{})
    location_id: typing.Optional[str] = pydantic.Field("", **{})
    location_type: typing.Optional[str] = pydantic.Field("", **{})
    ro_code: typing.Optional[str] = pydantic.Field("", **{})
    interlock_type: typing.Optional[str] = pydantic.Field("", **{})
    interlock_description: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] = pydantic.Field("", **{})
    severity: typing.Optional[str] = pydantic.Field("", **{})
    tank_id: typing.Optional[str] = pydantic.Field("", **{})
    nozzle_id: typing.Optional[str] = pydantic.Field("", **{})
    pump_no: typing.Optional[str] = pydantic.Field("", **{})
    alarm_id: str
    occurrence_date: typing.Optional[datetime.datetime] | None = None
    closure_date: typing.Optional[datetime.datetime] | None = None
    indent_no: typing.Optional[str] = pydantic.Field("", **{})
    products: typing.Optional[typing.List[productsDetailsCreate]] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = CrisAlertHistorySchema
        upsert_keys = ['alarm_id']
        access_key_mapping = ['location_id:sap_id']


class CrisAlertHistory(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'cris_alert_history'
    
    vendor_name: typing.Optional[str] = pydantic.Field("", **{})
    vendor_id: typing.Optional[str] = pydantic.Field("", **{})
    location_id: typing.Optional[str] = pydantic.Field("", **{})
    location_type: typing.Optional[str] = pydantic.Field("", **{})
    ro_code: typing.Optional[str] = pydantic.Field("", **{})
    interlock_type: typing.Optional[str] = pydantic.Field("", **{})
    interlock_description: typing.Optional[str] = pydantic.Field("", **{})
    device_name: typing.Optional[str] = pydantic.Field("", **{})
    device_id: typing.Optional[str] = pydantic.Field("", **{})
    severity: typing.Optional[str] = pydantic.Field("", **{})
    tank_id: typing.Optional[str] = pydantic.Field("", **{})
    nozzle_id: typing.Optional[str] = pydantic.Field("", **{})
    pump_no: typing.Optional[str] = pydantic.Field("", **{})
    alarm_id: typing.Optional[str] | None = None
    occurrence_date: typing.Optional[datetime.datetime] | None = None
    closure_date: typing.Optional[datetime.datetime] | None = None
    indent_no: typing.Optional[str] = pydantic.Field("", **{})
    products: typing.Optional[typing.List[productsDetailsCreate]] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = CrisAlertHistorySchema
        upsert_keys = ['alarm_id']
        access_key_mapping = ['location_id:sap_id']


class CrisAlertHistoryGetResp(pydantic.BaseModel):
    data: typing.List[CrisAlertHistory]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class DryOutAlertReportSchema(UrdhvaPostgresBase):
    __tablename__ = 'dry_out_alert_report'
    
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sales_area: Mapped[typing.Optional[str]] = mapped_column("sales_area", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[typing.Optional[str]] = mapped_column("sap_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    location_name: Mapped[typing.Optional[str]] = mapped_column("location_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    terminal_plant_id: Mapped[typing.Optional[str]] = mapped_column("terminal_plant_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    indent_no: Mapped[typing.Optional[str]] = mapped_column("indent_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    product_code: Mapped[typing.Optional[str]] = mapped_column("product_code", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    indent_status: Mapped[typing.Optional[str]] = mapped_column("indent_status", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    dry_out_in_days: Mapped[typing.Optional[str]] = mapped_column("dry_out_in_days", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    assigned_to_locn: Mapped[typing.Optional[str]] = mapped_column("assigned_to_locn", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    prod_reqd_dt: Mapped[typing.Optional[str]] = mapped_column("prod_reqd_dt", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    truck_regno: Mapped[typing.Optional[str]] = mapped_column("truck_regno", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    valid_indent: Mapped[typing.Optional[str]] = mapped_column("valid_indent", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    send_to_jde_time: Mapped[typing.Optional[str]] = mapped_column("send_to_jde_time", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    delivery_date: Mapped[typing.Optional[str]] = mapped_column("delivery_date", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    indent_hold_release_time: Mapped[typing.Optional[str]] = mapped_column("indent_hold_release_time", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    indent_executable_time: Mapped[typing.Optional[str]] = mapped_column("indent_executable_time", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    qty: Mapped[typing.Optional[str]] = mapped_column("qty", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    prod_allot_time: Mapped[typing.Optional[str]] = mapped_column("prod_allot_time", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sales_orderno: Mapped[typing.Optional[str]] = mapped_column("sales_orderno", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    invoice_no: Mapped[typing.Optional[str]] = mapped_column("invoice_no", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    loaded_on: Mapped[typing.Optional[str]] = mapped_column("loaded_on", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    avgsales_7days: Mapped[typing.Optional[str]] = mapped_column("avgsales_7days", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    alert_id: Mapped[str] = mapped_column("alert_id", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    run_id: Mapped[str] = mapped_column("run_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(alert_id, name="dry_out_alert_report_alert_id"),)


class DryOutAlertReportCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'dry_out_alert_report'
    
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    sales_area: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    terminal_plant_id: typing.Optional[str] = pydantic.Field("", **{})
    indent_no: typing.Optional[str] = pydantic.Field("", **{})
    product_code: typing.Optional[str] = pydantic.Field("", **{})
    indent_status: typing.Optional[str] = pydantic.Field("", **{})
    dry_out_in_days: typing.Optional[str] = pydantic.Field("", **{})
    assigned_to_locn: typing.Optional[str] = pydantic.Field("", **{})
    prod_reqd_dt: typing.Optional[str] = pydantic.Field("", **{})
    truck_regno: typing.Optional[str] = pydantic.Field("", **{})
    valid_indent: typing.Optional[str] = pydantic.Field("", **{})
    send_to_jde_time: typing.Optional[str] = pydantic.Field("", **{})
    delivery_date: typing.Optional[str] = pydantic.Field("", **{})
    indent_hold_release_time: typing.Optional[str] = pydantic.Field("", **{})
    indent_executable_time: typing.Optional[str] = pydantic.Field("", **{})
    qty: typing.Optional[str] = pydantic.Field("", **{})
    prod_allot_time: typing.Optional[str] = pydantic.Field("", **{})
    sales_orderno: typing.Optional[str] = pydantic.Field("", **{})
    invoice_no: typing.Optional[str] = pydantic.Field("", **{})
    loaded_on: typing.Optional[str] = pydantic.Field("", **{})
    avgsales_7days: typing.Optional[str] = pydantic.Field("", **{})
    alert_id: str
    run_id: str

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = DryOutAlertReportSchema
        upsert_keys = ['alert_id']


class DryOutAlertReport(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'dry_out_alert_report'
    
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    sales_area: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    terminal_plant_id: typing.Optional[str] = pydantic.Field("", **{})
    indent_no: typing.Optional[str] = pydantic.Field("", **{})
    product_code: typing.Optional[str] = pydantic.Field("", **{})
    indent_status: typing.Optional[str] = pydantic.Field("", **{})
    dry_out_in_days: typing.Optional[str] = pydantic.Field("", **{})
    assigned_to_locn: typing.Optional[str] = pydantic.Field("", **{})
    prod_reqd_dt: typing.Optional[str] = pydantic.Field("", **{})
    truck_regno: typing.Optional[str] = pydantic.Field("", **{})
    valid_indent: typing.Optional[str] = pydantic.Field("", **{})
    send_to_jde_time: typing.Optional[str] = pydantic.Field("", **{})
    delivery_date: typing.Optional[str] = pydantic.Field("", **{})
    indent_hold_release_time: typing.Optional[str] = pydantic.Field("", **{})
    indent_executable_time: typing.Optional[str] = pydantic.Field("", **{})
    qty: typing.Optional[str] = pydantic.Field("", **{})
    prod_allot_time: typing.Optional[str] = pydantic.Field("", **{})
    sales_orderno: typing.Optional[str] = pydantic.Field("", **{})
    invoice_no: typing.Optional[str] = pydantic.Field("", **{})
    loaded_on: typing.Optional[str] = pydantic.Field("", **{})
    avgsales_7days: typing.Optional[str] = pydantic.Field("", **{})
    alert_id: typing.Optional[str] | None = None
    run_id: typing.Optional[str] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = DryOutAlertReportSchema
        upsert_keys = ['alert_id']


class DryOutAlertReportGetResp(pydantic.BaseModel):
    data: typing.List[DryOutAlertReport]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class VendorApiAuditSchema(UrdhvaPostgresBase):
    __tablename__ = 'vendor_api_audit'
    
    method: Mapped[str] = mapped_column("method", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    url: Mapped[str] = mapped_column("url", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    payload: Mapped[typing.Optional[dict]] = mapped_column("payload", JSONB, index=False, nullable=True, default=pydantic.Field(default_factory=dict), primary_key=False, unique=False)
    alert_id: Mapped[str] = mapped_column("alert_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    request_no: Mapped[typing.Optional[str]] = mapped_column("request_no", String, index=True, nullable=True, default="", primary_key=False, unique=False)
    response: Mapped[str] = mapped_column("response", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    response_msg: Mapped[typing.Optional[str]] = mapped_column("response_msg", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    request_datetime: Mapped[datetime.datetime] = mapped_column("request_datetime", DateTime(timezone=True), index=False, nullable=False, default=None, primary_key=False, unique=False)
    api_ack: Mapped[typing.Optional[str]] = mapped_column("api_ack", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    api_ack_datetime: Mapped[typing.Optional[datetime.datetime]] = mapped_column("api_ack_datetime", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(alert_id, name="vendor_api_audit_alert_id"),)


class VendorApiAuditCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'vendor_api_audit'
    
    method: str
    url: str
    payload: typing.Optional[dict] = pydantic.Field(pydantic.Field(default_factory=dict), )
    alert_id: str
    request_no: typing.Optional[str] = pydantic.Field("", **{})
    response: str
    response_msg: typing.Optional[str] = pydantic.Field("", **{})
    request_datetime: datetime.datetime
    api_ack: typing.Optional[str] = pydantic.Field("", **{})
    api_ack_datetime: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = VendorApiAuditSchema
        upsert_keys = ['alert_id']


class VendorApiAudit(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'vendor_api_audit'
    
    method: typing.Optional[str] | None = None
    url: typing.Optional[str] | None = None
    payload: typing.Optional[dict] = pydantic.Field(pydantic.Field(default_factory=dict), )
    alert_id: typing.Optional[str] | None = None
    request_no: typing.Optional[str] = pydantic.Field("", **{})
    response: typing.Optional[str] | None = None
    response_msg: typing.Optional[str] = pydantic.Field("", **{})
    request_datetime: typing.Optional[datetime.datetime] | None = None
    api_ack: typing.Optional[str] = pydantic.Field("", **{})
    api_ack_datetime: typing.Optional[datetime.datetime] | None = None

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = VendorApiAuditSchema
        upsert_keys = ['alert_id']


class VendorApiAuditGetResp(pydantic.BaseModel):
    data: typing.List[VendorApiAudit]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)
