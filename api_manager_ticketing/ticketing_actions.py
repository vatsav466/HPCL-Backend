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
import fastapi
import traceback
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


# Action create_ticket
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
    params.fields =['bu','sop_id','alert_section','sap_id','location_name','interlock_name','unique_id']
    resp = await Alerts.get_all(params, resp_type='plain')

    if not resp or len(resp) == 0:
        raise fastapi.HTTPException(status_code=404, detail="Alerts not found")

    alert_data = resp.get('data', [])

    # Group alerts by interlock_name
    grouped_alerts = {}
    print("Alert Data: ", alert_data)
    for alert in alert_data:
        alert_type = alert.get('interlock_name')
        if alert_type:
            grouped_alerts.setdefault(alert_type, []).append(alert)

    # If alert_type is NOT provided, return alert_type and sop_id for each group
    if not tdata.get("alert_type"):
        result = [
            {
                "alert_type": alert_type,
                "sop_id": alerts[0].get('sop_id') if alerts else None
            }
            for alert_type, alerts in grouped_alerts.items()
        ]
        return {
            "reporter": user_name,
            "alert_types": result
        }


    # ----------------------------
    # Proceed to TICKET CREATION
    # ----------------------------

    selected_type = tdata["alert_type"]
    if selected_type not in grouped_alerts:
        raise fastapi.HTTPException(status_code=404, detail=f"No alerts found for alert_type: {selected_type}")

    # Select the first alert to associate with the ticket
    selected_alert = grouped_alerts[selected_type][0]
    tdata['alert_id'] = selected_alert.get('unique_id')  # or appropriate alert ID field

    # Generate ticket_id using helper
    tdata['ticket_id'] = await alert_helper.get_alert_unique_id(tdata['bu'], tdata['sap_id'], tdata.get('sop_id'))
    # Get the ticket_name
    redis_ins = await urdhva_base.redispool.get_redis_connection()
    # Redis key to increment (namespaced if needed)
    redis_key = f"ticket_counter:{tdata['bu']}"

    # Increment the counter
    ticket_count = await redis_ins.incr(redis_key)

    # You can optionally use this number in your ticket (e.g., to generate ticket_id)
    tdata['ticket_name'] = f"{tdata['bu']}_{tdata['sap_id']}_{ticket_count}" if not tdata.get('ticket_name') else f"{tdata.get('ticket_name')}_{tdata['bu']}_{tdata['sap_id']}_{ticket_count}"
    # Set default values
        # Set default values (including interlock_name as a list)
    ticket_state_str = tdata.get('ticket_state')
    for key, value in {
        'ticket_name': tdata.get('ticket_name'),
        'sop_id': tdata.get('sop_id', selected_alert.get('sop_id')),
        'reporter': user_name,
        'ticket_status': Status.Open.value,
        'ticket_state': getattr(State, ticket_state_str).value,
        'ticket_severity': tdata.get('ticket_severity') or Severity.Medium.value,
        'start_date': tdata.get('start_date'),
        'ticket_history': [],
        'linked_alert_id': data.linked_alert_id,
        'interlock_name': [selected_type],  # <-- this is the fix
        'comment': tdata.get('comment'),
        'file_attachment': [],
        'file_attachment_name': '',
        'file_attachment_id': "",
        'comment_text': '',
        'comment_id': '',
    }.items():
        tdata[key] = value

    print("Ticket Data: ", tdata)
    # Required fields
    required_fields = [
        'ticket_name', 'ticket_id', 'alert_id', 'bu', 'sop_id', 'alert_section', 'sap_id', 'location_name', 'zone', 'region',
        'ticket_status', 'ticket_state', 'start_date', 'end_date', 'summary', 'description',
        'ticket_severity', 'assignee', 'reporter', 'ticket_history', 'linked_alert_id',
        'interlock_name', 'comment'
    ]
    res = {field: tdata.get(field) for field in required_fields}

    # Create the ticket
    await TicketingCreate(**tdata).create()

    # Return success response
    return {
        "message": "Ticket created successfully",
        "ticket_id": tdata['ticket_id'],
        "alert_type": selected_type,
        "alert_data": selected_alert,
        "reporter": user_name,
        "ticket_name": tdata['ticket_name'],
        "ticker_id": tdata['ticket_id'],
    }


# Action close_ticket
@router.post('/close_ticket', tags=['Ticketing'])
async def ticketing_close_ticket(data: Ticketing_Close_TicketParams):
    await Ticketing(**{"id": data.close_id, "ticket_status": Status.Close.value, "ticket_state": State.Resolved.value, "end_date": data.end_date}).modify()
    return {"status": True, "message": "Ticket closed successfully", "data": data.close_id}


# Action update_ticket
@router.post('/update_ticket', tags=['Ticketing'])
async def ticketing_update_ticket(data: Ticketing_Update_TicketParams):
    data_dict = data.model_dump()
    print("Ticket Data: ", data_dict)
    await Ticketing(**{"id": data.update_id, **data_dict}).modify()
    return {"status": True,"message": "Ticket updated successfully", "data": data.update_id}

# Action delete_ticket
@router.post('/delete_ticket', tags=['Ticketing'])
async def ticketing_delete_ticket(data: Ticketing_Delete_TicketParams):
    await Ticketing.delete(data.delete_id)
    return {"status": True, "message": "Ticket deleted successfully", "data": data.delete_id}


# Action attach_file
@router.post('/attach_file', tags=['Ticketing'])
async def ticketing_attach_file(data: Ticketing_Attach_FileParams):
    try:
        # Create /tmp if not exists
        os.makedirs("/tmp", exist_ok=True)

        # Use original filename (any type: .csv, .pdf, .png, .zip, etc.)
        temp_file_path = os.path.join("/tmp", uploadfile.filename)

        # Write the file contents
        with open(temp_file_path, "wb") as file_to_attach:
            file_to_attach.write(await uploadfile.read())
        
        query = f"ticket_id='{data.ticket_id}'"
        params = urdhva_base.queryparams.QueryParams(q=query)
        result = await Ticketing.get_all(params, resp_type='plain')
        resp = result.get("data", [])
        if not resp:
            return {
                "status": False,
                "message": "Ticket not found"
            }
        # Attach the file to the issue
        await Ticketing(**{"id": resp[0].get("id"),"file_attachment": temp_file_path}).modify()
        return {
            "status": True,
            "message": f"File {uploadfile.filename} saved successfully",
            "data": temp_file_path,
            "content_type": uploadfile.content_type  # info about file type
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error saving file: {str(e)}"
        }


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
