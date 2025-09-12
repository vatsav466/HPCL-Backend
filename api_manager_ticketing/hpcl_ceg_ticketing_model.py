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
import hpcl_ceg_ticketing_enum

from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import *
from sqlalchemy.orm import *
from urdhva_base.postgresmodel import UrdhvaPostgresBase


class Ticket_HistoryCreate(pydantic.BaseModel):
    description: typing.Optional[str] = pydantic.Field("", **{})
    processed_time: typing.Optional[str] = pydantic.Field("", **{})
    allocated_time: typing.Optional[str] = pydantic.Field("", **{})
    action_msg: typing.Optional[str] = pydantic.Field("", **{})
    action_type: typing.Optional[str] = pydantic.Field("", **{})


class Merge_HistoryCreate(pydantic.BaseModel):
    ticket_id: typing.Optional[str] = pydantic.Field("", **{})
    merge_ticket_id: typing.List[str]
    comment: typing.Optional[str] = pydantic.Field("", **{})
    processed_time: typing.Optional[str] = pydantic.Field("", **{})
    allocated_time: typing.Optional[str] = pydantic.Field("", **{})
    action_msg: typing.Optional[str] = pydantic.Field("", **{})
    action_type: typing.Optional[str] = pydantic.Field("", **{})


class TicketingSchema(UrdhvaPostgresBase):
    __tablename__ = 'ticketing'
    
    ticket_name: Mapped[str] = mapped_column("ticket_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ticket_id: Mapped[str] = mapped_column("ticket_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    alert_id: Mapped[str] = mapped_column("alert_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    bu: Mapped[typing.Any] = mapped_column("bu", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    alert_section: Mapped[typing.Optional[str]] = mapped_column("alert_section", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sop_id: Mapped[typing.Optional[str]] = mapped_column("sop_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    sap_id: Mapped[str] = mapped_column("sap_id", String, index=True, nullable=False, default=None, primary_key=False, unique=False)
    location_name: Mapped[str] = mapped_column("location_name", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    zone: Mapped[typing.Optional[str]] = mapped_column("zone", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    region: Mapped[typing.Optional[str]] = mapped_column("region", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    ticket_status: Mapped[typing.Any] = mapped_column("ticket_status", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ticket_state: Mapped[typing.Any] = mapped_column("ticket_state", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    start_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("start_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    end_date: Mapped[typing.Optional[datetime.datetime]] = mapped_column("end_date", DateTime(timezone=True), index=False, nullable=True, default=None, primary_key=False, unique=False)
    summary: Mapped[str] = mapped_column("summary", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    description: Mapped[str] = mapped_column("description", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    ticket_severity: Mapped[typing.Any] = mapped_column("ticket_severity", String, index=False, nullable=False, default=None, primary_key=False, unique=False)
    assignee: Mapped[typing.Optional[typing.Any]] = mapped_column("assignee", String, index=False, nullable=True, default=None, primary_key=False, unique=False)
    reporter: Mapped[typing.Optional[str]] = mapped_column("reporter", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    ticket_history: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("ticket_history", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    merge_history: Mapped[typing.Optional[typing.List[typing.Any]]] = mapped_column("merge_history", JSONB, index=False, nullable=True, default=None, primary_key=False, unique=False)
    linked_alert_id: Mapped[typing.Optional[typing.List[str]]] = mapped_column("linked_alert_id", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    interlock_name: Mapped[typing.Optional[typing.List[str]]] = mapped_column("interlock_name", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    comment: Mapped[typing.Optional[str]] = mapped_column("comment", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    file_attachment: Mapped[typing.Optional[typing.List[str]]] = mapped_column("file_attachment", ARRAY(String), index=False, nullable=True, default="", primary_key=False, unique=False)
    file_attachment_name: Mapped[typing.Optional[str]] = mapped_column("file_attachment_name", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    file_attachment_id: Mapped[typing.Optional[str]] = mapped_column("file_attachment_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    comment_text: Mapped[typing.Optional[str]] = mapped_column("comment_text", String, index=False, nullable=True, default="", primary_key=False, unique=False)
    comment_id: Mapped[typing.Optional[str]] = mapped_column("comment_id", String, index=False, nullable=True, default="", primary_key=False, unique=False)

    __table_args__ = (UniqueConstraint(ticket_id, sap_id, name="ticketing_ticket_id_sap_id"),)


class TicketingCreate(urdhva_base.postgresmodel.BasePostgresModel):
    __tablename__ = 'ticketing'
    
    ticket_name: str
    ticket_id: str
    alert_id: str
    bu: hpcl_ceg_ticketing_enum.BusinessUnit
    alert_section: typing.Optional[str] = pydantic.Field("", **{})
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: str
    location_name: str
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    ticket_status: hpcl_ceg_ticketing_enum.Status
    ticket_state: hpcl_ceg_ticketing_enum.State
    start_date: typing.Optional[datetime.datetime] | None = None
    end_date: typing.Optional[datetime.datetime] | None = None
    summary: str
    description: str
    ticket_severity: hpcl_ceg_ticketing_enum.Severity
    assignee: typing.Optional[hpcl_ceg_ticketing_enum.Assignee] | None = None
    reporter: typing.Optional[str] = pydantic.Field("", **{})
    ticket_history: typing.Optional[typing.List[Ticket_HistoryCreate]] | None = None
    merge_history: typing.Optional[typing.List[Merge_HistoryCreate]] | None = None
    linked_alert_id: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    interlock_name: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    comment: typing.Optional[str] = pydantic.Field("", **{})
    file_attachment: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    file_attachment_name: typing.Optional[str] = pydantic.Field("", **{})
    file_attachment_id: typing.Optional[str] = pydantic.Field("", **{})
    comment_text: typing.Optional[str] = pydantic.Field("", **{})
    comment_id: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = TicketingSchema
        upsert_keys = ['ticket_id', 'sap_id']


class Ticketing(urdhva_base.postgresmodel.PostgresModel):
    __tablename__ = 'ticketing'
    
    ticket_name: typing.Optional[str] | None = None
    ticket_id: typing.Optional[str] | None = None
    alert_id: typing.Optional[str] | None = None
    bu: typing.Optional[hpcl_ceg_ticketing_enum.BusinessUnit] | None = None
    alert_section: typing.Optional[str] = pydantic.Field("", **{})
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] | None = None
    location_name: typing.Optional[str] | None = None
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    ticket_status: typing.Optional[hpcl_ceg_ticketing_enum.Status] | None = None
    ticket_state: typing.Optional[hpcl_ceg_ticketing_enum.State] | None = None
    start_date: typing.Optional[datetime.datetime] | None = None
    end_date: typing.Optional[datetime.datetime] | None = None
    summary: typing.Optional[str] | None = None
    description: typing.Optional[str] | None = None
    ticket_severity: typing.Optional[hpcl_ceg_ticketing_enum.Severity] | None = None
    assignee: typing.Optional[hpcl_ceg_ticketing_enum.Assignee] | None = None
    reporter: typing.Optional[str] = pydantic.Field("", **{})
    ticket_history: typing.Optional[typing.List[Ticket_HistoryCreate]] | None = None
    merge_history: typing.Optional[typing.List[Merge_HistoryCreate]] | None = None
    linked_alert_id: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    interlock_name: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    comment: typing.Optional[str] = pydantic.Field("", **{})
    file_attachment: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    file_attachment_name: typing.Optional[str] = pydantic.Field("", **{})
    file_attachment_id: typing.Optional[str] = pydantic.Field("", **{})
    comment_text: typing.Optional[str] = pydantic.Field("", **{})
    comment_id: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        collection_name = 'data_flow'
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields
        schema_class = TicketingSchema
        upsert_keys = ['ticket_id', 'sap_id']


class TicketingGetResp(pydantic.BaseModel):
    data: typing.List[Ticketing]
    total: int = pydantic.Field(0)
    count: int = pydantic.Field(0)


class Ticketing_Get_TicketParams(pydantic.BaseModel):
    ticket_id: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Create_TicketParams(pydantic.BaseModel):
    bu: str
    alert_section: typing.Optional[str] = pydantic.Field("", **{})
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: str
    location_name: str
    zone: typing.Optional[str] = pydantic.Field("", **{})
    region: typing.Optional[str] = pydantic.Field("", **{})
    alert_type: typing.List[str]
    assignee: typing.Optional[hpcl_ceg_ticketing_enum.Assignee] | None = None
    summary: str
    description: str
    ticket_state: hpcl_ceg_ticketing_enum.State
    ticket_severity: hpcl_ceg_ticketing_enum.Severity
    comment: typing.Optional[str] = pydantic.Field("", **{})
    start_date: datetime.datetime
    file_attachment: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    file_attachment_name: typing.Optional[str] = pydantic.Field("", **{})
    file_attachment_id: typing.Optional[str] = pydantic.Field("", **{})
    linked_alert_id: typing.Optional[typing.List[str]] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Close_TicketParams(pydantic.BaseModel):
    close_id: str
    end_date: datetime.datetime

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Update_TicketParams(pydantic.BaseModel):
    bu: typing.Optional[str] = pydantic.Field("", **{})
    sap_id: typing.Optional[str] = pydantic.Field("", **{})
    sop_id: typing.Optional[str] = pydantic.Field("", **{})
    alert_section: typing.Optional[str] = pydantic.Field("", **{})
    location_name: typing.Optional[str] = pydantic.Field("", **{})
    assignee: typing.Optional[str] = pydantic.Field("", **{})
    summary: typing.Optional[str] = pydantic.Field("", **{})
    description: typing.Optional[str] = pydantic.Field("", **{})
    ticket_state: typing.Optional[str] = pydantic.Field("", **{})
    ticket_severity: typing.Optional[str] = pydantic.Field("", **{})
    comment: typing.Optional[str] = pydantic.Field("", **{})
    update_id: str
    file_attachment: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    file_attachment_name: typing.Optional[str] = pydantic.Field("", **{})
    file_attachment_id: typing.Optional[str] = pydantic.Field("", **{})
    linked_alert_id: typing.Optional[typing.List[str]] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Merge_TicketParams(pydantic.BaseModel):
    ticket_id: str
    merge_ticket_id: typing.Optional[typing.List[str]] = pydantic.Field("", **{})
    comment: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Delete_TicketParams(pydantic.BaseModel):
    delete_id: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Attach_FileParams(pydantic.BaseModel):
    ticket_id: str
    file_path: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Delete_File_AttachmentParams(pydantic.BaseModel):
    ticket_id: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Download_File_AttachmentParams(pydantic.BaseModel):
    ticket_id: str
    file_attachment_name: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Update_AssigneeParams(pydantic.BaseModel):
    ticket_id: str
    assignee: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Update_ReporterParams(pydantic.BaseModel):
    ticket_id: str
    reporter: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Update_PriorityParams(pydantic.BaseModel):
    ticket_id: str
    ticket_priority: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Add_Comment_To_TicketParams(pydantic.BaseModel):
    ticket_id: str
    comment_text: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Edit_CommentParams(pydantic.BaseModel):
    ticket_id: str
    comment_id: str
    existing_comment_text: str
    new_comment: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Delete_CommentParams(pydantic.BaseModel):
    ticket_id: str
    comment_id: str
    existing_comment_text: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Edit_DescriptionParams(pydantic.BaseModel):
    ticket_id: str
    new_description: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Delete_DescriptionParams(pydantic.BaseModel):
    ticket_id: str
    delete_existing_desctiption: str

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Attach_File_To_CommentParams(pydantic.BaseModel):
    ticket_id: str
    comment_id: str
    file_path: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields


class Ticketing_Delete_File_From_CommentParams(pydantic.BaseModel):
    ticket_id: str
    comment_id: str
    attachment_id: str
    file_path: typing.Optional[str] = pydantic.Field("", **{})

    class Config:
        if urdhva_base.settings.disable_api_extra_inputs:
            extra = "forbid"  # Disallow extra fields