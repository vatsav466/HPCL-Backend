import urdhva_base
import uuid
import fastapi
import urllib.parse
import hpcl_ceg_model
from msal import ConfidentialClientApplication
from fastapi.responses import RedirectResponse
import authenticator.authentication_manager_ad as authentication_manager_ad

BaseUrl = "https://login.microsoftonline.com"
SCOPE = ["User.Read"]


# ----------------------------
# MSAL Client
# ----------------------------
async def create_msal_app(client_id, client_secret, tenant_id):
    return ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"{BaseUrl}/{tenant_id}",
    )


# ----------------------------
# Generating Azure Authorization URL
# ----------------------------
async def get_redirect_url(
        tenant_id: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
):
    msal_app = create_msal_app(client_id, client_secret, tenant_id)
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPE,
        state=str(uuid.uuid4()),
        redirect_uri=redirect_uri
    )
    return RedirectResponse(auth_url)


async def auth_callback(code: str, tenant_id: str, client_id: str, client_secret: str,
                        redirect_uri: str):
    if not code:
        return False, "Missing expected input", {}

    msal_app = create_msal_app(client_id, client_secret, tenant_id)

    result = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=SCOPE,
        redirect_uri=redirect_uri
    )

    if "id_token_claims" not in result:
        return False, result.get("error_description"), {}

    user_claims = result["id_token_claims"]
    user_name = user_claims.get("preferred_username", "")
    if not user_name:
        return False, "Not a valid User", {}

    # Checking user exists in database or not
    query = f"username='{user_name.split('@')[0].strip()}'"
    user_info = await hpcl_ceg_model.Users.get_all(urdhva_base.QueryParams(q=query, limit=1))
    if not user_info['data']:
        return False, "Not a valid User", {}
    return await authentication_manager_ad.AuthenticationManager.generate_auth_info(
        user_info=user_info['data'][0])
