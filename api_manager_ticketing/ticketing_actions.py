import urdhva_base
from hpcl_ceg_ticketing_enum import *
from typing import Optional
from fastapi.responses import FileResponse
from fastapi import Form, File, UploadFile
from hpcl_ceg_ticketing_model import (
    Ticketing,
    TicketingCreate,
    Ticketing_Get_TicketParams,
    Ticketing_Create_TicketParams,
    Ticketing_Delete_TicketParams,
    Ticketing_Close_TicketParams,
    Ticketing_Update_TicketParams,
    Ticketing_Attach_FileParams,
    Ticketing_Delete_CommentParams,
    Ticketing_Edit_DescriptionParams,
    Ticketing_Edit_CommentParams,
    Ticketing_Update_PriorityParams,
    Ticketing_Update_ReporterParams,
    Ticketing_Update_AssigneeParams,
    Ticketing_Delete_File_AttachmentParams,
    Ticketing_Merge_TicketParams,
    Ticketing_Download_File_AttachmentParams,
    Ticketing_Add_Comment_To_TicketParams,
    Ticketing_Delete_DescriptionParams,
    Ticketing_Attach_File_To_CommentParams,
    Ticketing_Delete_File_From_CommentParams,
    Ticketing_Get_Location_DataParams

)
import os, uuid
import fastapi
import logging
import traceback
import urdhva_base
import api_manager
import hpcl_ceg_model
from dateutil import parser
from datetime import datetime
from hpcl_ceg_enum import AlertActionType
from fastapi import UploadFile, File, Depends
from orchestrator.alerting import alert_helper
from fastapi import APIRouter, HTTPException
from urdhva_base.queryparams import QueryParams
from fastapi import UploadFile, File, Form
import utilities.minio_connector as minio_connector



router = fastapi.APIRouter(prefix='/ticketing')
logger = logging.getLogger(__name__)


# Action get_ticket
@router.post('/get_ticket', tags=['Ticketing'])
async def ticketing_get_ticket(data: Ticketing_Get_TicketParams):
    """
    Get ticket details by ticket id
    """
    try:
        id = data.ticket_id
        result = await Ticketing.get(int(id))            
        return result
    except Exception as e:
        print(traceback.format_exc())
        print(f"Error in getting ticket: {e}, InputData {data.dict()}, Traceback: {traceback.format_exc()}")
        return False, "Error in getting ticket"

# Action create_ticket
@router.post('/create_ticket', tags=['Ticketing'])
async def ticketing_create_ticket(data: Ticketing_Create_TicketParams):
    """
    Create a new ticket
    """
    rpt = urdhva_base.context.context.get('rpt', None)
    print("rpt",rpt)
    user_name = rpt.get('user_name') if rpt else None
    employee_id = rpt.get('employee_id') if rpt else None
    

    tdata = data.model_dump()
    if not tdata.get("subtask_id"):
            tdata["subtask_id"] = []
            
    location_value = (
        tdata["location_name"][0]
        if isinstance(tdata.get("location_name"), list)
        else tdata.get("location_name")
    )

    sap_value = (
        tdata["sap_id"][0]
        if isinstance(tdata.get("sap_id"), list)
        else tdata.get("sap_id")
    )

    # Build the alert query
    query = (
        f"bu='{tdata['bu']}' "
        f"and alert_section='{tdata['alert_section']}' "
        f"and sap_id='{sap_value}' "
        f"and location_name='{location_value}'"
    )
    params = urdhva_base.queryparams.QueryParams(q=query, limit=10000)
    params.fields = ['bu', 'sop_id', 'alert_section', 'sap_id',
                     'location_name', 'interlock_name', 'unique_id']
    resp = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')

    if not resp or len(resp) == 0:
        raise fastapi.HTTPException(status_code=404, detail="Alerts not found")

    alert_data = resp.get('data', [])

    # Group alerts by interlock_name
    grouped_alerts = {}
    for alert in alert_data:
        alert_type = alert.get('interlock_name')
        if alert_type:
            grouped_alerts.setdefault(alert_type, []).append(alert)

    selected_type_raw = tdata.get("alert_type")

    # If alert_type is NOT provided
    if not selected_type_raw:
        result = [
            {
                "alert_type": alert_type,
                "sop_id": alerts[0].get('sop_id') if alerts else None
            }
            for alert_type, alerts in grouped_alerts.items()
        ]
        return {"reporter": user_name, "alert_types": result}

    # Always treat as list
    selected_types = selected_type_raw if isinstance(selected_type_raw, list) else [selected_type_raw]

    # Validate
    for selected_type in selected_types:
        if selected_type not in grouped_alerts:
            raise fastapi.HTTPException(status_code=400, detail=f"Alert type '{selected_type}' not found.")

    tickets_created = []

    # ----------------------------
    # Proceed to TICKET CREATION
    # ----------------------------
    for selected_type in selected_types:
        alerts_for_type = grouped_alerts[selected_type]
        selected_alert = alerts_for_type[0]

        ticket_data = tdata.copy()  # avoid overwriting



        # Core fields
        ticket_data['alert_id'] = selected_alert.get('unique_id')
        ticket_data['ticket_id'] = await alert_helper.get_alert_unique_id(
            ticket_data['bu'],
            ticket_data['sap_id'][0] if isinstance(ticket_data['sap_id'], list) else ticket_data['sap_id'],
            ticket_data.get('sop_id')
        )

        ticket_data['ticket_id'] = f"TKT-{ticket_data['ticket_id']}"


        # Generate incremental ticket_name
        redis_ins = await urdhva_base.redispool.get_redis_connection()
        redis_key = f"ticket_counter:{ticket_data['bu']}"
        ticket_count = await redis_ins.incr(redis_key)
        ticket_data['ticket_name'] = (
            f"{ticket_data['bu']}_{ticket_data['sap_id']}_{ticket_count}"
            if not ticket_data.get('ticket_name')
            else f"{ticket_data.get('ticket_name')}_{ticket_data['bu']}_{ticket_data['sap_id']}_{ticket_count}"
        )

        # Linked alerts if provided
        linked_data = (
            f"id in ({','.join(map(str, data.linked_alert_id))})"
            if data.linked_alert_id else None
        )
        linked_res = []
        if linked_data:
            params = urdhva_base.queryparams.QueryParams(q=linked_data, limit=10000)
            # params.fields = [""]
            resp = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
            linked_res = resp.get('data', [])

        startdate_str = ticket_data.get('start_date')
         # from request payload

        # if startdate_str:
        #     try:
        #         # Try parsing ISO 8601 and other common formats
        #         startdate = parser.isoparse(startdate_str)
        #     except Exception:
        #         try:
        #             startdate = datetime.strptime(startdate_str, "%Y-%m-%d %H:%M:%S")
        #         except ValueError:
        #             try:
        #                 startdate = datetime.strptime(startdate_str, "%Y-%m-%d")
        #             except ValueError:
        #                 startdate = None  # fallback if nothing matches
        # else:
        #     startdate = None  # or datetime.now() if you want a default
        startdate = ticket_data.get("start_date")

        # Defaults
        ticket_state_str = ticket_data.get('ticket_state')
        ticket_end_date = ticket_data.get('ticket_end_date')
        for key, value in {
            'ticket_name': ticket_data['ticket_name'],
            'sop_id': ticket_data.get('sop_id', selected_alert.get('sop_id')),
            'reporter': user_name,
            'ticket_status': Status.Open.value,
            'ticket_state': getattr(State, ticket_state_str).value,
            'ticket_severity': ticket_data.get('ticket_severity') or Severity.Medium.value,
             'startdate': startdate, 
            'ticket_history': [],
            'linked_alert_id': data.linked_alert_id,
            'interlock_name': [selected_type],
            'comment': ticket_data.get('comment'),
            'file_attachment': data.file_attachment,
            'file_attachment_name': data.file_attachment_name,
            'file_attachment_id': data.file_attachment_id,
            'ticket_id': ticket_data['ticket_id'],
            'comment_text': '',
            'comment_id': '',
            'ticket_end_date': ticket_end_date,
            'truck_no': ticket_data.get('truck_no'),
            'ticket_section': ticket_data.get('ticket_section'),
            'category':ticket_data.get('category'),
            'sub_category':ticket_data.get('sub_category')
        }.items():
            ticket_data[key] = value
        ticket_data['parent_id'] = tdata.get('parent_id')

            
        action_type_str = TicketType[ticket_state_str].value
        action_type = AlertActionType(action_type_str)


        # Append first history entry
        processed_time = datetime.now()
        ticket_data['ticket_history'].append({
            "processed_time": processed_time.isoformat(),
            "allocated_time": startdate.isoformat() if startdate else processed_time.isoformat(),
            "action_msg": f"Ticket is created and is in {ticket_data['ticket_state']} state",
            "action_type": action_type_str,
            "description": ticket_data.get("comment") or "",
            "employee_id": employee_id

        })

        # Create the ticket
        print("ticket_data",ticket_data)
        ticket_resp = await TicketingCreate(**ticket_data).create()
        params = urdhva_base.queryparams.QueryParams()
        params.q = f"ticket_id='{ticket_data['ticket_id']}'"
        params.limit = 1
        params.fields = ["id", "ticket_id"]
        resp = await Ticketing.get_all(params, resp_type='plain')
        db_ticket_id = resp['data'][0]['id']
        parent_tid = ticket_data.get("parent_id")

        if parent_tid:
            # Fetch parent ticket by ticket_id
            params_p = urdhva_base.queryparams.QueryParams()
            params_p.q = f"ticket_id='{parent_tid}'"
            params_p.limit = 1
            params_p.fields = ["id", "subtask_id"]

            parent_resp = await Ticketing.get_all(params_p, resp_type='plain')

            if parent_resp and parent_resp.get("data"):
                parent_ticket = parent_resp["data"][0]
                parent_db_id = parent_ticket["id"]

                # existing subtask list
                existing_subtasks = parent_ticket.get("subtask_id") or []

                # ensure list format
                if not isinstance(existing_subtasks, list):
                    existing_subtasks = []

                # remove empty strings
                existing_subtasks = [x for x in existing_subtasks if x]


                # add new subtask (this ticket)
                new_subtask_id = ticket_data["ticket_id"]

                if new_subtask_id not in existing_subtasks:
                    existing_subtasks.append(new_subtask_id)

                # update parent ticket
                await Ticketing(
                    id=parent_db_id,
                    subtask_id=existing_subtasks
                ).modify()

        
        for lr in linked_res:
            if lr.get("interlock_name") == selected_type:
                alert_hist = lr.get("alert_history") or []
                action_type_str = TicketType[ticket_state_str].value  
                action_type = AlertActionType(action_type_str)       
                alert_action = {
                    "action_type": action_type,
                    "alert_id": lr["id"],
                    "action_msg": f"Ticket is raised and is in {ticket_state_str} state"
                }



                processed_time = datetime.now()

                # Append minimal history entry
                alert_hist.append({
                    "processed_time": processed_time.isoformat(),  # current time
                    "allocated_time": startdate.isoformat() if startdate else processed_time.isoformat(),  # start date or fallback
                    "action_msg": f"Ticket is raised and is in {ticket_data['ticket_state']} state",
                    "action_type": action_type
                })

                # Update Alerts table by alert ID
                await hpcl_ceg_model.Alerts(
                    id=lr["id"],
                    alert_history=alert_hist
                ).modify()

                # Update in memory for API response
                lr["alert_history"] = alert_hist
        # Append to results
        tickets_created.append({
            "tid": db_ticket_id,
            "ticket_id": ticket_data['ticket_id'],
            "ticket_name": ticket_data['ticket_name'],
            "alert_type": selected_type,
            "alert_data": selected_alert,
            "reporter": user_name,
            "ticket_history": ticket_data['ticket_history'],
            "parent_id": parent_tid,
            "subtask_id": existing_subtasks if parent_tid else [],
            "ticket_end_date":ticket_data['ticket_end_date'],
            "linked_alerts": [
                {
                    "sap_id": lr.get("sap_id"),
                    "location_name": lr.get("location_name"),
                    "alert_type": lr.get("interlock_name"),
                    "unique_id": lr.get("unique_id"),
                    "created_at": lr.get("created_at"),
                    "alert_history": lr.get("alert_history", [])
                }
                for lr in linked_res
                if lr.get("interlock_name") == selected_type  
            ]
        })

    # ----------------------------
    # END OF TICKET CREATION
    # ----------------------------

    return {
        "message": "Tickets created successfully",
        "tickets": tickets_created
        
    }

# Action close_ticket
@router.post('/close_ticket', tags=['Ticketing'])
async def ticketing_close_ticket(data: Ticketing_Close_TicketParams):
    await Ticketing(**{"id": data.close_id, "ticket_status": Status.Close.value, "ticket_state": State.Resolved.value, "end_date": data.end_date}).modify()
    return {"status": True, "message": "Ticket closed successfully", "data": data.close_id}


# Action update_ticket
# @router.post('/update_ticket', tags=['Ticketing'])
# async def ticketing_update_ticket(data: Ticketing_Update_TicketParams):
#     # data_dict = data.model_dump()
#     # print("Ticket Data: ", data_dict)
#     # await Ticketing(**{"id": data.update_id, **data_dict}).modify()
#     # return {"status": True,"message": "Ticket updated successfully", "data": data.update_id}
#     try:
#         data_dict = data.model_dump()
#         print("data_dict",data_dict)
#         if "alert_type" in data_dict:
#             data_dict["interlock_name"] = data_dict.pop("alert_type")
#         ticket_id = data.update_id
#         # print("data_dict",data_dict)
#         # Fetch existing ticket
#         params = urdhva_base.queryparams.QueryParams()
#         params.q = f"id='{ticket_id}'"
#         params.limit = 1
#         params.fields = ["id", "ticket_state", "ticket_history", "linked_alert_id"]
#         resp = await Ticketing.get_all(params, resp_type='plain')
#         if not resp or not resp.get("data"):
#             return {"status": False, "message": f"Ticket {ticket_id} not found"}

#         existing_ticket = resp["data"][0]

#         # --- TIMINGS as per _update_alert_history ---
#         processed_time = datetime.utcnow()
#         existing_history = existing_ticket.get("ticket_history", []) or []
#         last_allocated_time = processed_time.isoformat()
#         if existing_history:
#             last_allocated_time = existing_history[-1].get("processed_time", processed_time.isoformat())

#         # --- UPDATE ticket_history ---
#         ticket_state = data_dict.get("ticket_state")  # e.g., "InProgress"
#         action_type_enum = TicketType[ticket_state].value  # e.g., "TicketInProgress"
#         ticket_update_entry = {
#             "action_msg": f"Ticket updated, state changed to {ticket_state}",
#             "action_type": action_type_enum,
#             "allocated_time": last_allocated_time,
#             "processed_time": processed_time.isoformat()
#         }
#         updated_history = existing_history + [ticket_update_entry]
#         if ticket_state in ["Resolved", "Cancelled"]:
#             data_dict["ticket_status"] = "Close"
#         else:
#             data_dict["ticket_status"] = "Open"
#             # print("ticket_status>>>>>>>",data_dict["ticket_status"])
#         data_dict["ticket_history"] = updated_history

#         # --- UPDATE THE TICKET ---
#         await Ticketing(id=ticket_id, **data_dict).modify()

#         # --- UPDATE ALERT HISTORY for linked_alert_id ---
#         linked_alert_ids = data_dict.get("linked_alert_id", []) or existing_ticket.get("linked_alert_id", [])
#         for alert_id in linked_alert_ids:
#             # Fetch alert
#             params = urdhva_base.queryparams.QueryParams()
#             params.q = f"id='{alert_id}'"
#             params.limit = 1
#             params.fields = ["id", "alert_history"]
#             resp_alert = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
#             if not resp_alert or not resp_alert.get("data"):
#                 continue

#             alert_obj = resp_alert["data"][0]
#             alert_history = alert_obj.get("alert_history", []) or []

#             # Determine allocated_time from last relevant entry
#             last_alloc = processed_time.isoformat()
#             for entry in reversed(alert_history):
#                 if entry.get("action_type") in [
#                     "TicketRaised", "TicketInProgress", "TicketCancelled", "TicketResolved", "TicketOnHold"
#                 ]:
#                     last_alloc = entry.get("processed_time", processed_time.isoformat())
#                     break

#             # Append new alert_history entry
#             new_alert_entry = {
#                 "action_msg": f"Ticket updated, state changed to {ticket_state}",
#                 "action_type": action_type_enum,
#                 "allocated_time": last_alloc,
#                 "processed_time": processed_time.isoformat()
#             }
#             updated_alert_history = alert_history + [new_alert_entry]

#             await hpcl_ceg_model.Alerts(id=alert_id, alert_history=updated_alert_history).modify()

#         # return {"status": True, "message": "Ticket updated successfully", "data": ticket_id}
#         return {
#             "status": True,
#             "message": "Ticket updated successfully",
#             "data": {
#                 "ticket_id": ticket_id,
#                 "ticket_history": updated_history
#             }
#         }

#     except Exception as e:
#         print(f"Error in update_ticket: {str(e)}")
#         # return {"status": False, "message": str(e)}
#         return {
#             "status": True,
#             "message": "Ticket updated successfully",
#             "data": {
#                 "ticket_id": ticket_id,
#                 "ticket_history": updated_history
#             }
#         }
@router.post('/update_ticket', tags=['Ticketing'])
async def ticketing_update_ticket(data: Ticketing_Update_TicketParams):
    try:
        data_dict = data.model_dump()
        # Normalize truck_no
        if data_dict.get("truck_no") in ["", [""]]:
            data_dict["truck_no"] = None

        # Normalize ticket_section
        if data_dict.get("ticket_section") == "":
            data_dict["ticket_section"] = None
            
        # Normalize sub_category  
        if data_dict.get("sub_category") in ["", [""]]:
            data_dict["sub_category"] = None
            
        # Normalize category     
        if data_dict.get("category") in ["", [""]]:
            data_dict["category"] = None
            
        # print("data_dict", data_dict)
        # ------------------------------------------------------------
        # FIX → Convert subtask_id "" → []
        # ------------------------------------------------------------
        #if not data_dict.get("subtask_id"):
        if data_dict.get("subtask_id") == [""]:
            data_dict["subtask_id"] = []
        

        # Rename alert_type → interlock_name
        if "alert_type" in data_dict:
            data_dict["interlock_name"] = data_dict.pop("alert_type")

        ticket_id = data.update_id

        # Fetch existing ticket
        params = urdhva_base.queryparams.QueryParams()
        params.q = f"id='{ticket_id}'"
        params.limit = 1
        params.fields = ["id", "ticket_state", "ticket_history", "linked_alert_id"]
        resp = await Ticketing.get_all(params, resp_type='plain')

        if not resp or not resp.get("data"):
            return {"status": False, "message": f"Ticket {ticket_id} not found"}

        existing_ticket = resp["data"][0]

        # ---------------------------------------
        # TIMINGS
        # ---------------------------------------
        processed_time = datetime.utcnow()
        existing_history = existing_ticket.get("ticket_history", []) or []
        last_allocated_time = processed_time.isoformat()

        if existing_history:
            last_allocated_time = existing_history[-1].get("processed_time", processed_time.isoformat())

        # ---------------------------------------
        # NEW LOGIC → CHECK ALERT STATUSES FIRST
        # ---------------------------------------
        if "linked_alert_id" in data_dict:
            linked_alert_ids = data_dict["linked_alert_id"]
        else:
            linked_alert_ids = existing_ticket.get("linked_alert_id", [])

        linked_alert_ids = linked_alert_ids or []
        all_alerts_closed = bool(linked_alert_ids)

            
        for alert_id in linked_alert_ids:
            params = urdhva_base.queryparams.QueryParams()
            params.q = f"id='{alert_id}'"
            params.limit = 1
            params.fields = ["id", "alert_status"]

            alert_resp = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')

            if not alert_resp or not alert_resp.get("data"):
                all_alerts_closed = False
                break

            alert_status = alert_resp["data"][0].get("alert_status")

            if alert_status in ["Open", "Pending", None]:
                all_alerts_closed = False
                break

        # ---------------------------------------
        # UPDATE ticket_history
        # ---------------------------------------
        ticket_state = data_dict.get("ticket_state") or existing_ticket.get("ticket_state")
        if ticket_state not in TicketType.__members__:
            raise Exception(f"Invalid ticket_state: {ticket_state}")

        action_type_str = TicketType[ticket_state].value
        action_type_enum = AlertActionType(action_type_str).value


        rpt = urdhva_base.context.context.get('rpt', None)
        employee_id = rpt.get('employee_id') if rpt else None

        if all_alerts_closed:
            action_msg = "All linked alerts are closed, so ticket moved to Closed state"
            action_type_val = "TicketResolved"
        else:
            action_msg = f"Ticket updated, state changed to {ticket_state}"
            action_type_val = action_type_enum

        ticket_update_entry = {
            "action_msg": action_msg,
            "action_type": action_type_val,
            "allocated_time": last_allocated_time,
            "processed_time": processed_time.isoformat(),
            "employee_id": employee_id,
            "remarks": data_dict.get("remarks"),
            "reason": data_dict.get("reason")
        }

        updated_history = existing_history + [ticket_update_entry]

        # ---------------------------------------
        # APPLY FINAL DECISION → CLOSE TICKET IF ALL ALERTS CLOSED
        # ---------------------------------------
        if all_alerts_closed:
            data_dict["ticket_status"] = Status.Close.value

            data_dict["ticket_state"] = "Resolved"
        else:
            if ticket_state in ["Resolved", "Cancelled"]:
                data_dict["ticket_status"] = Status.Close.value

            else:
                data_dict["ticket_status"] = Status.Open.value


        data_dict["ticket_history"] = updated_history

        # ---------------------------------------
        # UPDATE THE TICKET IN DB
        # ---------------------------------------
        await Ticketing(id=ticket_id, **data_dict).modify()

        new_subtask = data_dict.get("subtask_id") or []

        if new_subtask:
            # 1️⃣ Fetch this ticket again to get parent_id
            params_parent = urdhva_base.queryparams.QueryParams()
            params_parent.q = f"id='{ticket_id}'"
            params_parent.limit = 1
            params_parent.fields = ["id", "parent_id"]

            parent_info = await Ticketing.get_all(params_parent, resp_type='plain')

            if parent_info and parent_info.get("data"):
                parent_id = parent_info["data"][0].get("parent_id")

                if parent_id:
                    params_p = urdhva_base.queryparams.QueryParams()
                    params_p.q = f"ticket_id='{parent_id}'"
                    params_p.limit = 1
                    params_p.fields = ["id", "subtask_id"]

                    parent_resp = await Ticketing.get_all(params_p, resp_type='plain')

                    if parent_resp and parent_resp.get("data"):
                        parent_ticket = parent_resp["data"][0]
                        parent_db_id = parent_ticket["id"]

                        existing_subtasks = parent_ticket.get("subtask_id") or []
                        if not isinstance(existing_subtasks, list):
                            existing_subtasks = []

                        if new_subtask not in existing_subtasks:
                            existing_subtasks.append(new_subtask)

                        await Ticketing(
                            id=parent_db_id,
                            subtask_id=existing_subtasks
                        ).modify()

        # ---------------------------------------
        # UPDATE ALERT HISTORY 
        # ---------------------------------------
        for alert_id in linked_alert_ids:
            params = urdhva_base.queryparams.QueryParams()
            params.q = f"id='{alert_id}'"
            params.limit = 1
            params.fields = ["id", "alert_history"]

            resp_alert = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
            if not resp_alert or not resp_alert.get("data"):
                continue

            alert_obj = resp_alert["data"][0]
            alert_history = alert_obj.get("alert_history", []) or []

            last_alloc = processed_time.isoformat()
            for entry in reversed(alert_history):
                if entry.get("action_type") in [
                    "TicketRaised", "TicketInProgress", "TicketCancelled",
                    "TicketResolved", "TicketOnHold","TicketReOpen","TicketOnCompleted"
                ]:
                    last_alloc = entry.get("processed_time", processed_time.isoformat())
                    break

            new_alert_entry = {
                "action_msg": f"Ticket updated, state changed to {ticket_state}",
                "action_type": action_type_enum,
                "allocated_time": last_alloc,
                "processed_time": processed_time.isoformat(),
                "remarks": data_dict.get("remarks"),
                "reason": data_dict.get("reason")
            }

            updated_alert_history = alert_history + [new_alert_entry]

            await hpcl_ceg_model.Alerts(id=alert_id, alert_history=updated_alert_history).modify()

        return {
            "status": True,
            "message": "Ticket updated successfully",
            "data": {
                "ticket_id": ticket_id,
                "ticket_history": updated_history
            }
        }

    except Exception as e:
        print(f"Error in update_ticket: {str(e)}")
        return {
            "status": False,
            "message": str(e)
        }

# Action delete_ticket
@router.post('/delete_ticket', tags=['Ticketing'])
async def ticketing_delete_ticket(data: Ticketing_Delete_TicketParams):
    await Ticketing.delete(data.delete_id)
    return {"status": True, "message": "Ticket deleted successfully", "data": data.delete_id}


# Action attach_file
@router.post('/attach_file', tags=['Ticketing'])
async def ticketing_attach_file(
    ticket_id: Optional[str] = Form(None),
    tid: Optional[str] = Form(None),
    uploadfile: UploadFile = File(None)
):
    try:
        if not uploadfile:
            return {"status": False, "message": "No file provided"}

        if not ticket_id or not tid:
            return {"status": False, "message": "ticket_id and tid are required"}

        # print("ticket_id -->", ticket_id)
        # print("tid -->", tid)

        # ---------------- FETCH TICKET ----------------
        query = f"ticket_id='{ticket_id}' and id={tid}"
        params = urdhva_base.queryparams.QueryParams(q=query)
        result = await Ticketing.get_all(params, resp_type='plain')
        resp = result.get("data", [])

        if not resp:
            return {"status": False, "message": "Ticket not found"}

        # ---------------- MINIO UPLOAD (DIRECT) ----------------

        base_folder = "ticketing"

        unique_filename = f"{uuid.uuid4()}_{uploadfile.filename}"

        # final object structure
        object_name = f"{ticket_id}/{tid}/{unique_filename}"

        # read file bytes
        file_bytes = await uploadfile.read()

        status, minio_path = minio_connector.upload_bytes_to_minio(
            base_folder,          # folder name
            object_name,          # object path inside folder
            file_bytes,
            uploadfile.content_type
        )

        if not status:
            return {
                "status": False,
                "message": "File upload to Minio failed",
                "file_path": minio_path
            }

        # ---------------- UPDATE DB ----------------
        existing_files = resp[0].get("file_attachment") or []
        updated_files = existing_files + [minio_path]

        await Ticketing(
            **{
                "id": resp[0].get("id"),
                "file_attachment": updated_files
            }
        ).modify()

        return {
            "status": True,
            "message": f"File {uploadfile.filename} uploaded successfully",
            "file_attachment": minio_path,
            "file_attachment_name": uploadfile.filename,
            "file_attachment_id": str(uuid.uuid4()),
            "content_type": uploadfile.content_type
        }

    except Exception as e:
        return {"status": False, "message": f"Error saving file: {str(e)}"}



# Action delete_file_attachment
@router.post('/delete_file_attachment', tags=['Ticketing'])
async def ticketing_delete_file_attachment(data: Ticketing_Delete_File_AttachmentParams):
    ticket_id = data.ticket_id

    # Prepare query params to fetch the ticket
    params = QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1

    # Fetch ticket row
    main_resp = await Ticketing.get_all(params, resp_type="plain")
    if not main_resp or len(main_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")

    db_record = main_resp["data"][0]

    # Extract file paths from the DB (file_attachment is a list)
    file_list = db_record.get("file_attachment") or []

    # Delete each file from the server if it exists
    for file_path in file_list:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    
    update_payload = {
        "file_attachment": [],
        "file_attachment_name": "",
        "file_attachment_id": ""
    }

    await Ticketing(**{"id": ticket_id, **update_payload}).modify()

    return {
        "status": True,
        "message": "File attachment deleted successfully",
        "data": ticket_id
    }
# Action download_file_attachment
@router.post('/download_file_attachment', tags=['Ticketing'])
async def ticketing_download_file_attachment(data: Ticketing_Download_File_AttachmentParams):

    ticket_id = data.ticket_id
    requested_file_name = data.file_attachment_name

    # ---------------- FETCH TICKET ----------------
    params = urdhva_base.queryparams.QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1

    ticket_resp = await Ticketing.get_all(params, resp_type="plain")

    if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = ticket_resp["data"][0]

    file_paths = ticket.get("file_attachment") or []
    db_file_name = ticket.get("file_attachment_name")

    if not file_paths:
        raise HTTPException(status_code=404, detail="No file attachments found")

    # Since you're storing list
    matched_path = None
    for path in file_paths:
        if requested_file_name in path:
            matched_path = path
            break

    if not matched_path:
        raise HTTPException(status_code=404, detail="Requested file not found")

    print("Downloading from MinIO path:", matched_path)

    # ---------------- DOWNLOAD FROM MINIO ----------------
    success, local_file_path = minio_connector.download_from_minio(matched_path)

    if not success:
        raise HTTPException(status_code=500, detail=local_file_path)

    print("Downloaded to temp path:", local_file_path)

    return FileResponse(
        path=local_file_path,
        filename=requested_file_name,
        media_type="application/octet-stream"
    )
    
# Action update_assignee
@router.post('/update_assignee', tags=['Ticketing'])
async def ticketing_update_assignee(data: Ticketing_Update_AssigneeParams):
    ticket_id = data.ticket_id
    new_assignee = data.assignee

    # Check if ticket exists
    params = QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1
    ticket_resp = await Ticketing.get_all(params, resp_type="plain")

    if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update assignee
    await Ticketing(**{
        "id": ticket_id,
        "assignee": new_assignee
    }).modify()

    return {
        "status": True,
        "message": f"Ticket {ticket_id} assigned to {new_assignee} successfully",
        "data": {
            "ticket_id": ticket_id,
            "assignee": new_assignee
        }
    }


# Action update_reporter
@router.post('/update_reporter', tags=['Ticketing'])
async def ticketing_update_reporter(data: Ticketing_Update_ReporterParams):
    ticket_id = data.ticket_id
    new_reporter = data.reporter  # from request

    # Check if ticket exists
    params = QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1
    ticket_resp = await Ticketing.get_all(params, resp_type="plain")

    if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update reporter
    await Ticketing(**{
        "id": ticket_id,
        "reporter": new_reporter
    }).modify()

    return {
        "status": True,
        "message": f"Ticket {ticket_id} reporter updated to {new_reporter} successfully",
        "data": {
            "ticket_id": ticket_id,
            "reporter": new_reporter
        }
    }

# Action update_priority
@router.post('/update_priority', tags=['Ticketing'])
async def ticketing_update_priority(data: Ticketing_Update_PriorityParams):
    ticket_id = data.ticket_id
    new_priority = data.ticket_priority  # from request

    # Check if ticket exists
    params = QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1
    ticket_resp = await Ticketing.get_all(params, resp_type="plain")

    if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update ticket_severity (column in DB)
    await Ticketing(**{
        "id": ticket_id,
        "ticket_severity": new_priority
    }).modify()

    return {
        "status": True,
        "message": f"Ticket {ticket_id} priority updated to {new_priority} successfully",
        "data": {
            "ticket_id": ticket_id,
            "ticket_priority": new_priority
        }
    }


# Action add_comment_to_ticket
@router.post('/add_comment_to_ticket', tags=['Ticketing'])
async def ticketing_add_comment_to_ticket(data: Ticketing_Add_Comment_To_TicketParams):
    ticket_id = data.ticket_id
    comment_text = data.comment_text

    # Check if ticket exists
    params = QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1
    ticket_resp = await Ticketing.get_all(params, resp_type="plain")

    if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Generate unique comment_id
    comment_id = str(uuid.uuid4())

    # Add comment to ticket (assumes your DB has a 'comments' list field)
    ticket = ticket_resp["data"][0]
    existing_comments = ticket.get("comments", [])
    existing_comments.append({
        "comment_id": comment_id,
        "comment_text": comment_text
    })

    await Ticketing(**{
        "id": ticket_id,
        "comment_text": comment_text,
        "comment_id": comment_id
    }).modify()
    # Return response
    return {
        "status": True,
        "message": f"Comment added to ticket {ticket_id} successfully",
        "data": {
            "ticket_id": ticket_id,
            "comment_id": comment_id,
            "comment_text": comment_text
        }
    }


# Action edit_comment
@router.post('/edit_comment', tags=['Ticketing'])
async def ticketing_edit_comment(data: Ticketing_Edit_CommentParams):
    ticket_id = data.ticket_id
    comment_id = data.comment_id
    new_comment = data.new_comment

    # Fetch ticket details
    params = QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1
    ticket_resp = await Ticketing.get_all(params, resp_type="plain")

    if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = ticket_resp["data"][0]

    # Verify comment_id matches
    if ticket.get("comment_id") != comment_id:
        raise HTTPException(status_code=404, detail="Comment not found for this ticket")

    # Move old comment_text to comment (history)
    old_comment = ticket.get("comment_text", "")
    existing_history = ticket.get("comment", "")
    updated_history = existing_history
    if old_comment:
        if existing_history:
            updated_history += f"\n{old_comment}"
        else:
            updated_history = old_comment

    # Update ticket with new comment_text
    await Ticketing(**{
        "id": ticket_id,
        "comment_text": new_comment,
        "comment": updated_history
    }).modify()

    # Return response
    return {
        "status": True,
        "message": f"Comment {comment_id} on ticket {ticket_id} updated successfully",
        "data": {
            "ticket_id": ticket_id,
            "comment_id": comment_id,
            "comment_text": new_comment,
            "comment_history": updated_history
        }
    }


# Action delete_comment
@router.post('/delete_comment', tags=['Ticketing'])
async def ticketing_delete_comment(data: Ticketing_Delete_CommentParams):
    ticket_id = data.ticket_id
    comment_id = data.comment_id
    existing_comment_text = data.existing_comment_text

    # Fetch ticket details
    params = QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1
    ticket_resp = await Ticketing.get_all(params, resp_type="plain")

    if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = ticket_resp["data"][0]

    # Debug: show current comments
    print("[DEBUG] Ticket data before deletion:", ticket)

    # Check if the comment_id matches current comment_text
    current_comment_text = ticket.get("comment_text", "")
    current_comment_id = ticket.get("comment_id", "")

    if current_comment_id != comment_id or current_comment_text != existing_comment_text:
        raise HTTPException(status_code=400, detail="Comment ID or text does not match")

    # Clear the comment_text, comment_id, and comment (history) columns
    await Ticketing(**{
        "id": ticket_id,
        "comment_text": "",
        "comment_id": "",
        "comment": ""
    }).modify()

    # Debug: show after deletion
    print(f"[DEBUG] Comment {comment_id} deleted. Updated ticket fields: comment_text='', comment_id='', comment=''")

    return {
        "status": True,
        "message": f"Comment {comment_id} deleted successfully from ticket {ticket_id}",
        "data": {
            "ticket_id": ticket_id,
            "comment_id": comment_id
        }
    }


# Action edit_description
@router.post('/edit_description', tags=['Ticketing'])
async def ticketing_edit_description(data: Ticketing_Edit_DescriptionParams):
    ticket_id = data.ticket_id
    new_description = data.new_description

    # Fetch ticket details
    params = QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1
    ticket_resp = await Ticketing.get_all(params, resp_type="plain")

    if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update description
    await Ticketing(**{
        "id": ticket_id,
        "description": new_description
    }).modify()

    return {
        "status": True,
        "message": f"Description updated successfully for ticket {ticket_id}",
        "data": {
            "ticket_id": ticket_id,
            "description": new_description
        }
    }


# Action delete_description
@router.post('/delete_description', tags=['Ticketing'])
async def ticketing_delete_description(data: Ticketing_Delete_DescriptionParams):
    ticket_id = data.ticket_id
    existing_description = data.delete_existing_desctiption  # value from request

    # Fetch ticket details
    params = QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1
    ticket_resp = await Ticketing.get_all(params, resp_type="plain")

    if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket = ticket_resp["data"][0]
    current_description = ticket.get("description", "")
    print(f"[DEBUG] Current description for ticket {ticket_id}: {current_description}")

    # Validate existing description
    if current_description != existing_description:
        raise HTTPException(status_code=400, detail="Existing description does not match")

    # Clear description
    await Ticketing(**{
        "id": ticket_id,
        "description": ""
    }).modify()

    print(f"[DEBUG] Description cleared for ticket {ticket_id}")

    return {
        "status": True,
        "message": f"Description deleted successfully for ticket {ticket_id}",
        "data": {
            "ticket_id": ticket_id,
            "description": ""
        }
    }


# Action attach_file_to_comment
@router.post('/attach_file_to_comment', tags=['Ticketing'])
async def ticketing_attach_file_to_comment(
    ticket_id: str = Form(...),
    comment_id: str = Form(...),
    uploadfile: UploadFile = File(...)
):
    try:
        target_dir = urdhva_base.settings.ticketing_attachments
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        saved_file_path = os.path.join(target_dir, uploadfile.filename)
        with open(saved_file_path, "wb") as f:
            f.write(await uploadfile.read())

        # Fetch ticket record by ticket_id
        params = urdhva_base.queryparams.QueryParams(q=f"id='{ticket_id}'", limit=1)
        ticket_resp = await Ticketing.get_all(params, resp_type='plain')
        if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
            return {"status": False, "message": "Ticket not found"}

        ticket = ticket_resp["data"][0]

        # Check comment_id matches the ticket's comment_id
        if ticket.get("comment_id") != comment_id:
            return {"status": False, "message": "Comment not found"}

        # Update comment_attachment_path field
        await Ticketing(
            **{
                "id": ticket.get("id"),
                "comment_attachment_path": saved_file_path
            }
        ).modify()

        return {
            "status": True,
            "message": f"File {uploadfile.filename} attached to comment successfully",
            "comment_attached_path": saved_file_path
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error attaching file to comment: {str(e)}"
        }


# Action delete_file_from_comment
@router.post('/delete_file_from_comment', tags=['Ticketing'])
async def ticketing_delete_file_from_comment(data: Ticketing_Delete_File_From_CommentParams):
    try:
        ticket_id = data.ticket_id
        comment_id = data.comment_id

        # Fetch ticket record by ticket_id
        params = urdhva_base.queryparams.QueryParams(q=f"id='{ticket_id}'", limit=1)
        ticket_resp = await Ticketing.get_all(params, resp_type='plain')
        if not ticket_resp or len(ticket_resp.get("data", [])) == 0:
            return {"status": False, "message": "Ticket not found"}

        ticket = ticket_resp["data"][0]

        # Check if comment_id matches
        if ticket.get("comment_id") != comment_id:
            return {"status": False, "message": "Comment not found"}

        # Clear the comment_attachment_path field
        await Ticketing(
            **{
                "id": ticket.get("id"),
                "comment_attachment_path": ""
            }
        ).modify()

        return {
            "status": True,
            "message": f"Attachment cleared for comment {comment_id} successfully"
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error clearing attachment from comment: {str(e)}"
        }

# Action merge_ticket
@router.post('/merge_ticket', tags=['Ticketing'])
async def ticketing_merge_ticket(data: Ticketing_Merge_TicketParams):
    ticket_id = data.ticket_id  # main ticket internal ID
    merge_ticket_ids = data.merge_ticket_id or []
    comment_text = data.comment or ""

    # Fetch main ticket
    params = urdhva_base.queryparams.QueryParams()
    params.q = f"id='{ticket_id}'"
    params.limit = 1
    main_resp = await Ticketing.get_all(params, resp_type="plain")
    
    if not main_resp or len(main_resp.get("data", [])) == 0:
        raise HTTPException(status_code=404, detail="Main ticket not found")
    
    main_ticket = main_resp["data"][0]
    if "merge_history" not in main_ticket:
        main_ticket["merge_history"] = []
    if "ticket_history" not in main_ticket:
        main_ticket["ticket_history"] = []

    processed_time = datetime.now()

    for merge_ticket_id in merge_ticket_ids:
        # Fetch ticket to merge by ticket_id (name)
        merge_params = urdhva_base.queryparams.QueryParams()
        merge_params.q = f"ticket_id='{merge_ticket_id}'"
        merge_params.limit = 1
        merge_resp = await Ticketing.get_all(merge_params, resp_type="plain")
        
        if not merge_resp or len(merge_resp.get("data", [])) == 0:
            continue  # skip if merge ticket not found
        
        merge_ticket = merge_resp["data"][0]

        # Determine if SAP IDs or ticket_status differ
        main_sap_id = main_ticket.get("alert_data", {}).get("sap_id")
        merge_sap_id = merge_ticket.get("alert_data", {}).get("sap_id")
        main_status = main_ticket.get("ticket_status")
        merge_status = merge_ticket.get("ticket_status")

        entry_comment = comment_text
        if main_sap_id != merge_sap_id or main_status != merge_status:
            entry_comment = "Merging different SAP IDs or statuses"

        # Build merge_history entry (add 'merge_ticket_id' for Pydantic validation)
        merge_entry = {
            "processed_time": processed_time.isoformat(),
            "allocated_time": processed_time.isoformat(),
            "action_msg": f"Ticket {merge_ticket_id} merged into {main_ticket['ticket_id']}",
            "action_type": "TicketMerged",
            "description": entry_comment,
            "merge_ticket_id": [merge_ticket_id],  # <- list of strings
            "comment": entry_comment
        }

        # Append to merge_history
        # Ensure merge_history and ticket_history are always lists
        main_ticket["merge_history"] = main_ticket.get("merge_history") or []
        main_ticket["ticket_history"] = main_ticket.get("ticket_history") or []

        # Append the merge entry
        main_ticket["merge_history"].append(merge_entry)

        # For the merge ticket as well
        merge_ticket["merge_history"] = merge_ticket.get("merge_history") or []
        merge_ticket["ticket_history"] = merge_ticket.get("ticket_history") or []

        merge_ticket_entry = {
            "processed_time": processed_time.isoformat(),
            "allocated_time": processed_time.isoformat(),
            "action_msg": f"Ticket {merge_ticket_id} merged into {main_ticket['ticket_id']}",
            "action_type": "TicketMerged",
            "description": entry_comment,
            "merge_ticket_id": [main_ticket["ticket_id"]],
            "comment": entry_comment
        }
        if merge_ticket["merge_history"] is None:
            merge_ticket["merge_history"] = []
        merge_ticket["merge_history"].append(merge_ticket_entry)

        if merge_ticket["ticket_history"] is None:
            merge_ticket["ticket_history"] = []
        merge_ticket_history_entry = {
            "processed_time": processed_time.isoformat(),
            "allocated_time": processed_time.isoformat(),
            "action_msg": f"Ticket {merge_ticket_id} merged into {main_ticket['ticket_id']}",
            "action_type": "TicketMerged",
            "comment": entry_comment
        }
        merge_ticket["ticket_history"].append(merge_ticket_history_entry)
        merge_ticket["merge_status"] = "Merged"

        await Ticketing(id=merge_ticket["id"], merge_history=merge_ticket["merge_history"], ticket_history=merge_ticket["ticket_history"],merge_status=merge_ticket["merge_status"]).modify()

        # ----- NEW: Update ticket_history also -----
        ticket_history_entry = {
            "processed_time": processed_time.isoformat(),
            "allocated_time": processed_time.isoformat(),
            "action_msg": f"Ticket {merge_ticket_id} merged into {main_ticket['ticket_id']}",
            "action_type": "TicketMerged",
            "comment": entry_comment
        }
        main_ticket["ticket_history"].append(ticket_history_entry)

        # Update linked alerts (commented out if not needed)
        # for alert in merge_ticket.get("linked_alerts", []):
        #     alert_hist = alert.get("alert_history", [])
        #     alert_hist.append({
        #         "processed_time": processed_time.isoformat(),
        #         "allocated_time": processed_time.isoformat(),
        #         "action_msg": f"Ticket {merge_ticket_id} merged into {main_ticket['ticket_id']}",
        #         "action_type": "TicketMerged"
        #     })
        #     await Alerts(id=alert["id"], alert_history=alert_hist).modify()
        #     alert["alert_history"] = alert_hist

        # Optionally keep linked_alerts in main ticket
        main_ticket.setdefault("linked_alerts", []).extend(merge_ticket.get("linked_alerts", []))
        main_ticket["merge_status"] = None
        print("coming")

    # Save main ticket with updated merge_history and ticket_history
    await Ticketing(id=main_ticket["id"], merge_history=main_ticket["merge_history"], ticket_history=main_ticket["ticket_history"], merge_status=None).modify()

    return {
        "message": "Tickets merged successfully",
        "ticket": main_ticket
    }

# Action get_location_data
@router.post('/get_location_data', tags=['Ticketing'])
async def ticketing_get_location_data(data: Ticketing_Get_Location_DataParams):

    # ------------------ BUILD FILTERS ------------------
    filters = []

    def add_filter(field, value):
        if not value:
            return

        # If list → remove empty values
        if isinstance(value, list):
            cleaned = [v for v in value if v not in ("", None)]
            if not cleaned:
                return
            formatted_values = ",".join([f"'{v}'" for v in cleaned])
            filters.append(f"{field} IN ({formatted_values})")
        else:
            if value not in ("", None):
                filters.append(f"{field} = '{value}'")


    add_filter("bu", data.bu)
    add_filter("zone", data.zone)
    add_filter("region", data.region)
    add_filter("sales_area", data.sales_area)
    add_filter("sap_id", data.sap_id)

    # ------------------ QUERY PARAMS ------------------
    params = urdhva_base.queryparams.QueryParams()
    params.q = " AND ".join(filters) if filters else None
    params.limit = 100000000
    params.fields = ["sap_id", "bu", "zone", "region", "sales_area", "name"]

    resp = await hpcl_ceg_model.LocationMaster.get_all(params, resp_type="plain")
    rows = resp.get("data", [])

    # ------------------ PREPARE UNIQUE VALUES (Single Loop) ------------------
    import ast

    bu_set = set()
    zone_set = set()
    region_set = set()
    sales_area_set = set()

    for r in rows:

        # Collect BU
        bu = r.get("bu")
        if bu:
            bu_set.add(bu)

        # Collect Zone
        zone = r.get("zone")
        if zone:
            zone_set.add(zone)

        # Collect Region
        region = r.get("region")
        if region:
            region_set.add(region)

        # Collect Sales Area (convert string list to real list)
        raw_sales_area = r.get("sales_area")
        if raw_sales_area:
            try:
                parsed = ast.literal_eval(raw_sales_area)
                if isinstance(parsed, list):
                    sales_area_set.update(parsed)
                else:
                    sales_area_set.add(raw_sales_area)
            except:
                sales_area_set.add(raw_sales_area)

    # Sort results
    bu_list = sorted(bu_set)
    zones = sorted(zone_set)
    regions = sorted(region_set)
    sales_areas = sorted(sales_area_set)

    # ------------------ SORT LOCATIONS ------------------
    rows.sort(key=lambda x: x["name"])

    locations = [
        {"sap_id": r["sap_id"], "name": r["name"]}
        for r in rows
    ]

    # ------------------ RETURN ------------------
    return {
        "status": True,
        "message": "All filter values",
        "data": {
            "bu_list": bu_list,
            "zones": zones,
            "regions": regions,
            "sales_areas": sales_areas,
            "locations": locations
        }
    }

