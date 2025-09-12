from hpcl_ceg_ticketing_enum import *
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
    Ticketing_Download_File_AttachmentParams,
    Ticketing_Add_Comment_To_TicketParams,
    Ticketing_Delete_DescriptionParams,
    Ticketing_Attach_File_To_CommentParams,
    Ticketing_Delete_File_From_CommentParams

)
import os
from fastapi import UploadFile, File, Depends
from datetime import datetime
import urdhva_base
import api_manager
import hpcl_ceg_model
import fastapi
import traceback
from hpcl_ceg_enum import AlertActionType
from datetime import datetime
from orchestrator.alerting import alert_helper
router = fastapi.APIRouter(prefix='/ticketing')


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

from dateutil import parser
@router.post('/create_ticket', tags=['Ticketing'])
async def ticketing_create_ticket(data: Ticketing_Create_TicketParams):
    """
    Create a new ticket
    """
    rpt = urdhva_base.context.context.get('rpt', None)
    user_name = rpt.get('user_name') if rpt else None

    tdata = data.model_dump()

    # Build the alert query
    query = (
        f"bu='{tdata['bu']}' and alert_section='{tdata['alert_section']}' "
        f"and sap_id='{tdata['sap_id']}' and location_name='{tdata['location_name']}'"
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
            ticket_data['bu'], ticket_data['sap_id'], ticket_data.get('sop_id')
        )

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

        startdate_str = ticket_data.get('startdate')  # from request payload

        if startdate_str:
            try:
                # Try parsing ISO 8601 and other common formats
                startdate = parser.isoparse(startdate_str)
            except Exception:
                try:
                    startdate = datetime.strptime(startdate_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        startdate = datetime.strptime(startdate_str, "%Y-%m-%d")
                    except ValueError:
                        startdate = None  # fallback if nothing matches
        else:
            startdate = None  # or datetime.now() if you want a default
        # Defaults
        ticket_state_str = ticket_data.get('ticket_state')
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
        }.items():
            ticket_data[key] = value
            
        action_type_str = TicketType[ticket_state_str].value
        action_type = AlertActionType[action_type_str]

        # Append first history entry
        processed_time = datetime.now()
        ticket_data['ticket_history'].append({
            "processed_time": processed_time.isoformat(),
            "allocated_time": startdate.isoformat() if startdate else processed_time.isoformat(),
            "action_msg": f"Ticket is created and is in {ticket_data['ticket_state']} state",
            "action_type": action_type_str,
            "description": ticket_data.get("comment") or ""
        })

        # Create the ticket
        ticket_resp = await TicketingCreate(**ticket_data).create()
        params = urdhva_base.queryparams.QueryParams()
        params.q = f"ticket_id='{ticket_data['ticket_id']}'"
        params.limit = 1
        params.fields = ["id", "ticket_id"]
        resp = await Ticketing.get_all(params, resp_type='plain')
        db_ticket_id = resp['data'][0]['id']

        
        for lr in linked_res:
            if lr.get("interlock_name") == selected_type:
                alert_hist = lr.get("alert_history") or []
                action_type_str = TicketType[ticket_state_str].value  
                action_type = AlertActionType[action_type_str]        
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
            "id": db_ticket_id,
            "ticket_id": ticket_data['ticket_id'],
            "ticket_name": ticket_data['ticket_name'],
            "alert_type": selected_type,
            "alert_data": selected_alert,
            "reporter": user_name,
            "ticket_history": ticket_data['ticket_history'],
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
@router.post('/update_ticket', tags=['Ticketing'])
async def ticketing_update_ticket(data: Ticketing_Update_TicketParams):
    # data_dict = data.model_dump()
    # print("Ticket Data: ", data_dict)
    # await Ticketing(**{"id": data.update_id, **data_dict}).modify()
    # return {"status": True,"message": "Ticket updated successfully", "data": data.update_id}
    try:
        data_dict = data.model_dump()
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

        # --- TIMINGS as per _update_alert_history ---
        processed_time = datetime.utcnow()
        existing_history = existing_ticket.get("ticket_history", []) or []
        last_allocated_time = processed_time.isoformat()
        if existing_history:
            last_allocated_time = existing_history[-1].get("processed_time", processed_time.isoformat())

        # --- UPDATE ticket_history ---
        ticket_state = data_dict.get("ticket_state")  # e.g., "InProgress"
        action_type_enum = TicketType[ticket_state].value  # e.g., "TicketInProgress"
        ticket_update_entry = {
            "action_msg": f"Ticket updated, state changed to {ticket_state}",
            "action_type": action_type_enum,
            "allocated_time": last_allocated_time,
            "processed_time": processed_time.isoformat()
        }
        updated_history = existing_history + [ticket_update_entry]
        data_dict["ticket_history"] = updated_history

        # --- UPDATE THE TICKET ---
        await Ticketing(id=ticket_id, **data_dict).modify()

        # --- UPDATE ALERT HISTORY for linked_alert_id ---
        linked_alert_ids = data_dict.get("linked_alert_id", []) or existing_ticket.get("linked_alert_id", [])
        for alert_id in linked_alert_ids:
            # Fetch alert
            params = urdhva_base.queryparams.QueryParams()
            params.q = f"id='{alert_id}'"
            params.limit = 1
            params.fields = ["id", "alert_history"]
            resp_alert = await hpcl_ceg_model.Alerts.get_all(params, resp_type='plain')
            if not resp_alert or not resp_alert.get("data"):
                continue

            alert_obj = resp_alert["data"][0]
            alert_history = alert_obj.get("alert_history", []) or []

            # Determine allocated_time from last relevant entry
            last_alloc = processed_time.isoformat()
            for entry in reversed(alert_history):
                if entry.get("action_type") in [
                    "TicketRaised", "TicketInProgress", "TicketCancelled", "TicketResolved", "TicketOnHold"
                ]:
                    last_alloc = entry.get("processed_time", processed_time.isoformat())
                    break

            # Append new alert_history entry
            new_alert_entry = {
                "action_msg": f"Ticket updated, state changed to {ticket_state}",
                "action_type": action_type_enum,
                "allocated_time": last_alloc,
                "processed_time": processed_time.isoformat()
            }
            updated_alert_history = alert_history + [new_alert_entry]

            await hpcl_ceg_model.Alerts(id=alert_id, alert_history=updated_alert_history).modify()

        # return {"status": True, "message": "Ticket updated successfully", "data": ticket_id}
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
        # return {"status": False, "message": str(e)}
        return {
            "status": True,
            "message": "Ticket updated successfully",
            "data": {
                "ticket_id": ticket_id,
                "ticket_history": updated_history
            }
        }


# Action delete_ticket
@router.post('/delete_ticket', tags=['Ticketing'])
async def ticketing_delete_ticket(data: Ticketing_Delete_TicketParams):
    await Ticketing.delete(data.delete_id)
    return {"status": True, "message": "Ticket deleted successfully", "data": data.delete_id}

from fastapi import UploadFile, File, Form
import os, uuid
# # Action attach_file
@router.post('/attach_file', tags=['Ticketing'])
async def ticketing_attach_file(
    ticket_id: str = Form(...),
    tid: int = Form(...),
    uploadfile: UploadFile = File(...)
):
    try:
        # Only create the directory if it doesn't exist
        target_dir = urdhva_base.settings.ticketing_attachments
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        # Path to save the file
        temp_file_path = os.path.join(target_dir, uploadfile.filename)
        # Save file in /tmp
        # temp_file_path = os.path.join(urdhva_base.settings.ticketing_attachments, uploadfile.filename)
        with open(temp_file_path, "wb") as file_to_attach:
            file_to_attach.write(await uploadfile.read())

        # Query ticket
        query = f"ticket_id='{ticket_id}' and id = {tid}"  # tid ==> id column
        params = urdhva_base.queryparams.QueryParams(q=query)
        result = await Ticketing.get_all(params, resp_type='plain')
        resp = result.get("data", [])
        if not resp:
            return {"status": False, "message": "Ticket not found"}

        # Attach file to ticket (must be a list)
        await Ticketing(
            **{
                "id": resp[0].get("id"),
                "file_attachment": [temp_file_path]
            }
        ).modify()
        

        # Generate UUID for file
        file_uuid = str(uuid.uuid4())

        return {
            "status": True,
            "message": f"File {uploadfile.filename} saved successfully",
            "file_attachment": temp_file_path,          # full path
            "file_attachment_name": uploadfile.filename, # only filename
            "file_attachment_id": file_uuid,            # generated uuid
            "content_type": uploadfile.content_type     # file type
        }

    except Exception as e:
        return {"status": False, "message": f"Error saving file: {str(e)}"}


# Action delete_file_attachment
@router.post('/delete_file_attachment', tags=['Ticketing'])
async def ticketing_delete_file_attachment(data: Ticketing_Delete_File_AttachmentParams):
    ...


# Action download_file_attachment
@router.post('/download_file_attachment', tags=['Ticketing'])
async def ticketing_download_file_attachment(data: Ticketing_Download_File_AttachmentParams):
    ...


# Action update_assignee
@router.post('/update_assignee', tags=['Ticketing'])
async def ticketing_update_assignee(data: Ticketing_Update_AssigneeParams):
    ...


# Action update_reporter
@router.post('/update_reporter', tags=['Ticketing'])
async def ticketing_update_reporter(data: Ticketing_Update_ReporterParams):
    ...


# Action update_priority
@router.post('/update_priority', tags=['Ticketing'])
async def ticketing_update_priority(data: Ticketing_Update_PriorityParams):
    ...


# Action add_comment_to_ticket
@router.post('/add_comment_to_ticket', tags=['Ticketing'])
async def ticketing_add_comment_to_ticket(data: Ticketing_Add_Comment_To_TicketParams):
    ...


# Action edit_comment
@router.post('/edit_comment', tags=['Ticketing'])
async def ticketing_edit_comment(data: Ticketing_Edit_CommentParams):
    ...


# Action delete_comment
@router.post('/delete_comment', tags=['Ticketing'])
async def ticketing_delete_comment(data: Ticketing_Delete_CommentParams):
    ...


# Action edit_description
@router.post('/edit_description', tags=['Ticketing'])
async def ticketing_edit_description(data: Ticketing_Edit_DescriptionParams):
    ...


# Action delete_description
@router.post('/delete_description', tags=['Ticketing'])
async def ticketing_delete_description(data: Ticketing_Delete_DescriptionParams):
    ...


# Action attach_file_to_comment
@router.post('/attach_file_to_comment', tags=['Ticketing'])
async def ticketing_attach_file_to_comment(data: Ticketing_Attach_File_To_CommentParams):
    ...


# Action delete_file_from_comment
@router.post('/delete_file_from_comment', tags=['Ticketing'])
async def ticketing_delete_file_from_comment(data: Ticketing_Delete_File_From_CommentParams):
    ...


# Action create_ticket
@router.post('/create_ticket', tags=['Ticketing'])
async def ticketing_create_ticket(data: Ticketing_Create_TicketParams):
    ...


# Action attach_file
@router.post('/attach_file', tags=['Ticketing'])
async def ticketing_attach_file(data: Ticketing_Attach_FileParams):
    ...
