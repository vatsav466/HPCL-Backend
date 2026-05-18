import urdhva_base
import hpcl_ceg_model
import email_users_actions
import asyncio


async def test_email_users():

    payload_dict = {
    "email_type": "Nozzle",
    "bu": "ro",
    "name": "Nozzle Sales",
    "subject": "Novex Daily sales Report",
    "description": "",
    "enabled": True,
    "audience": "testing",
    "to_recipients": ["poojitha.gumma@algofusiontech.com"],
    "cc_recipients": ["vamsi.c@algofusiontech.com"],
    "bcc_recipients": ["yesu.p@algofusiontech.com"],
    "action": "add"
    }


    payload_obj = email_users_actions.Email_Users_Add_UserParams(**payload_dict)
    response =  await email_users_actions.email_users_add_user(payload_obj)
    print(response)

    return response

if __name__ == "__main__":
    asyncio.run(test_email_users())
