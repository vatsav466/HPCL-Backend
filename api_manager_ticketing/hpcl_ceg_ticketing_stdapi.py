import urdhva_base.postgresmodel
import urdhva_base.queryparams
import urdhva_base.types
from hpcl_ceg_ticketing_enum import *
from hpcl_ceg_ticketing_model import *
import fastapi
router = fastapi.APIRouter()


@router.get('/ticketing/{id}', response_model=Ticketing, tags=['Ticketing'])
async def get(id: str):
    return await Ticketing.get(id, skip_secrets=True)


@router.get('/ticketing', response_model=TicketingGetResp, tags=['Ticketing'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await Ticketing.get_all(params, skip_secrets=True)


@router.get('/ticketusermails/{id}', response_model=TicketUserMails, tags=['TicketUserMails'])
async def get(id: str):
    return await TicketUserMails.get(id, skip_secrets=True)


@router.get('/ticketusermails', response_model=TicketUserMailsGetResp, tags=['TicketUserMails'])
async def get_all(response: fastapi.Response, params=fastapi.Depends(urdhva_base.queryparams.QueryParams)):
    return await TicketUserMails.get_all(params, skip_secrets=True)

