import os
import re
import json
import glob
import uuid
import httpx
import typing
import base64
import random
import fastapi
import datetime
import traceback
import importlib
import contextvars
import fastapi.security
import urdhva_base.entity
import urdhva_base.context
import urdhva_base.settings
import urdhva_base.redispool
from jose import jwt, JWTError
import urdhva_base.elasticmodel
from pydantic.fields import Field
from urllib.parse import urlparse
from slowapi.extension import Limiter
from cryptography.fernet import Fernet
from starlette.datastructures import URL
import urdhva_base.ttl_cache as ttl_cache
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from urllib.parse import parse_qs, urlencode
from slowapi.middleware import SlowAPIMiddleware
from mangum import Mangum
from starlette.responses import RedirectResponse
from hpcl_ceg_model import UserLoginAudit

logger = urdhva_base.Logger.getInstance("urdhva_api")

app = fastapi.FastAPI()
cookie_name = urdhva_base.settings.cookie_name

@app.exception_handler(RateLimitExceeded)
def rate_limit_exceeded_handler(request: fastapi.Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."}
    )

# Set a default limit (e.g., 1000 requests per minute)
limiter = Limiter(key_func=get_remote_address, application_limits=["1000/second"])

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Add SlowAPI middleware (built-in middleware)
app.add_middleware(SlowAPIMiddleware)



# This function will give keycloak auth redirection url based on realm name given
async def get_customer_authentication_extension(realm):
    return "auth"


# Alternative implementation using FastAPI's middleware decorator
@app.middleware("http")
async def decrypt_middleware(request: fastapi.Request, call_next):
    if (urdhva_base.settings.enable_encrypted_payload and
            len(urdhva_base.settings.encryption_key) > 0):
        # Initialize cipher (in production, get this from env or config)
        key = urdhva_base.settings.encryption_key
        if isinstance(key, str):
            key = key.encode()
        cipher = Fernet(key)
        path = request.url.path
        if path in ['/api/session/me', '/api/session/encryption-status', '/api/ping', '/docs',
                    '/openapi.json', '/api/logout', '/api/users/sso_auth_url',
                    '/api/users/sso_redirection_url']:
            response = await call_next(request)
            return response

        # Only process requests with encrypted payloads
        if request.method in ["GET"]:
            if not request.query_params:
                query_list = path.split('/')
                query_id = query_list[-1]
                try:
                    encrypted_data = base64.b64decode(query_id.replace('"', ''), validate=True)
                    decrypted_string = cipher.decrypt(encrypted_data)
                    query_list[-1] = decrypted_string.decode()
                    request.scope["path"] = '/'.join(query_list)
                except Exception as e:
                    print(f"Middleware error: {str(e)}")
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Invalid request body"}
                    )
            else:
                params = dict(request.query_params)
                decrypted_params = {}
                try:
                    for key, value in params.items():
                        if len(value) > 0 and value not in ['=', '==']:
                            return JSONResponse(
                                status_code=400,
                                content={"error": "Invalid request body"}
                            )
                        try:
                            encrypted_data = base64.b64decode(key.replace('"', ''), validate=True)
                        except Exception as e:
                            try:
                                encrypted_data = base64.b64decode(key.replace('"', '') + '=',
                                                                  validate=True)
                            except Exception as e:
                                encrypted_data = base64.b64decode(key.replace('"', '') + '==',
                                                                  validate=True)
                        decrypted_string = cipher.decrypt(encrypted_data)
                        decrypted_params.update(json.loads(decrypted_string))
                except Exception as e:
                    print(f"Middleware error: {str(e)}")
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Invalid request body"}
                    )
                if decrypted_params:
                    # Reconstruct URL with decrypted params
                    new_query = urlencode(decrypted_params, doseq=True)
                    request.scope["query_string"] = new_query.encode()
        elif request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    # Decrypt the payload
                    encrypted_data = base64.b64decode(body.decode().replace('"', ''), validate=True)
                    decrypted_string = cipher.decrypt(encrypted_data)
                    request.scope["body"] = decrypted_string
                    request._body = decrypted_string
            except Exception as e:
                if 'multipart/form-data' not in request.headers.get("content-type"):
                    print(f"Middleware error: {str(e)}")
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Invalid request body"}
                    )
        elif request.method in ["DELETE"]:
            query_list = path.split('/')
            query_id = query_list[-1]
            try:
                encrypted_data = base64.b64decode(query_id.replace('"', ''), validate=True)
                decrypted_string = cipher.decrypt(encrypted_data)
                query_list[-1] = decrypted_string.decode()
                request.scope["path"] = '/'.join(query_list)
            except Exception as e:
                print(f"Middleware error: {str(e)}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid request body"}
                )
    response = await call_next(request)
    return response


@app.on_event("startup")
def onStart():
    for filename in glob.glob("**/*.py", recursive=True):
        if filename.startswith("_"):
            continue
        modname = os.path.splitext(filename)[0].replace(os.sep, '.')
        # print("Loading:",modname)
        mod = importlib.import_module(modname)

        # If a variable by name "roter" is defined load that directly
        # Else go through the module and if any of the variable is a router load that...
        symbol = getattr(mod, 'router', None)
        if isinstance(symbol, fastapi.APIRouter):
            app.include_router(symbol, prefix="/api")
        else:
            for attr in dir(mod):
                if not attr.startswith("_"):
                    symbol = getattr(mod, attr)
                    if isinstance(symbol, fastapi.APIRouter):
                        app.include_router(symbol, prefix="/api")
    # print("Loaded modules:")
    # for route in app.routes:
    #     print(route.path, route.name)


# Api to push data to redis server
async def createInternalErrorMessage(errFormat):
    logger.error(f"internalerror_{urdhva_base.ctx['entity_id']} {errFormat}")
    try:
        id = str(uuid.uuid4()).replace("-", "")
        conn = await urdhva_base.redispool.get_redis_connection()
        await conn.setex("internalerror_" + id, 60, errFormat)
        return True, id
    except:
        return False, ""


async def get_baseurl(request: fastapi.Request, redirect_type="RedirectionUrl", entity_id=""):
    return os.environ.get(redirect_type, request.base_url.hostname)


async def get_permission():
    rpt = urdhva_base.context.context.get('rpt', {})
    data = {"is_authenticated": False, "allowed_roles": []}
    if rpt.get("username") and rpt.get("system_role") and rpt.get("novex_role"):
        data['is_authenticated'] = True
        data["allowed_roles"] = rpt.get("allowed_roles", [])
    # data = {"me": ['read'], "logout": ["read"]}
    # data.update({permission['rsname'].lower().split("_")[0]: permission.get('scopes', []) for permission in
    #              rpt.get('authorization', {}).get('permissions', [])})
    # data['includes'] = rpt.get('includes', '')
    # data['excludes'] = rpt.get('excludes', '')
    return data


async def get_resource_operation(method, path):
    path_params = path.split('/')
    resource = path_params[2].lower()
    operation = {'post': 'create', 'put': 'update', 'get': 'read', 'delete': 'delete'}.get(method.lower())
    if path_params[-1] == "":
        path_params = path_params[:-1]
    if method.lower() == 'post' and len(path_params) == 4 and path_params[3]:
        operation = path_params[3].lower()
    elif method.lower() == 'post' and len(path_params) == 5:
        operation = path_params[4].lower()
    elif method.lower() == 'get' and len(path_params) == 5:
        operation = path_params[4].lower()
    elif method.lower() == 'get' and len(path_params) == 6:
        operation = path_params[5].lower()
    return resource, operation


async def has_permission(method: str, path: str):
    return True
    permissions = await get_permission()
    resource, operation = await get_resource_operation(method, path)
    return True if resource in permissions and operation in permissions[resource] else False


async def get_vendor_authorization_details():
    """Cache data loader"""
    redis_ins = await urdhva_base.redispool.get_redis_connection()
    vendor_details = {}
    resp = await redis_ins.hgetall("vendor_auth")
    for key, info in resp.items():
        if isinstance(key, bytes):
            key = key.decode()
        if isinstance(info, bytes):
            info = info.decode()
        if key.endswith('_access_key'):
            vendor = key.split("_access_key")[0]
            if vendor not in vendor_details:
                vendor_details[vendor] = {}
            vendor_details[vendor]['access_key'] = info
        elif key.endswith('_allowed_apis'):
            vendor = key.split("_allowed_apis")[0]
            if vendor not in vendor_details:
                vendor_details[vendor] = {}
            vendor_details[vendor]['allowed_apis'] = json.loads(info)
    return vendor_details


async def validate_header_based_authentication(request: fastapi.Request):
    """
        Validates the authentication of an incoming HTTP request based on headers.

        Args:
            request (fastapi.Request): The incoming HTTP request object.

        Steps:
        1. Extract the Authorization header from the request.
        2. Check if the Authorization header is missing or malformed.
        3. Validate the token (e.g., a JWT) from the Authorization header.
        4. Return an appropriate response if the authentication fails.
        5. If authentication is successful, allow the request to proceed.

        Returns:
            True, None: If the authentication is valid, the function does not return anything, and the request proceeds.
            False, 403: If the authentication fails, an HTTP exception is raised with the appropriate status code and message.
            False, None: If header based authentication not enabled or auth token not available in headers
        """
    if not urdhva_base.settings.enable_header_auth:
        return False, None
    headers = request.headers
    access_key = headers.get("ceg-auth-token")
    if access_key:
        vendor = headers.get("vendor")
        if vendor:
            ins = ttl_cache.CacheDataInstance.get_instance("vendor_auth", get_vendor_authorization_details)
            cache_data = await ins.get(vendor)
            vendor_data = cache_data.get(vendor) if cache_data else {}
            if not vendor_data or access_key != vendor_data.get('access_key'):
                return False, fastapi.responses.JSONResponse("Invalid Authentication Credentials", 401)
            if vendor_data.get('allowed_apis') and request.url.path not in vendor_data.get('allowed_apis'):
                return False, fastapi.responses.JSONResponse("Permission Denied", 403)
            return True, None
            #
            # redis_ins = await urdhva_base.redispool.get_redis_connection()
            # # Validate Access key
            # if await redis_ins.hexists("vendor_auth", f"{vendor}_access_key"):
            #     db_access_key = await redis_ins.hget("vendor_auth", f"{vendor}_access_key")
            #     if db_access_key and isinstance(db_access_key, bytes):
            #         db_access_key = db_access_key.decode()
            #     if db_access_key == access_key:
            #         allowed_apis = json.loads(await redis_ins.hget("vendor_auth", f"{vendor}_allowed_apis"))
            #         if allowed_apis and request.url.path not in allowed_apis:
            #             return False, fastapi.responses.JSONResponse("Invalid permissions", 403)
            #         return True, None
            #     return False, fastapi.responses.JSONResponse("Invalid token", 403)
    return False, None


def add_security_headers(response):
    # response.headers["Content-Security-Policy"] = "default-src 'self' style-src 'self' 'unsafe-inline'"
    return response


@app.middleware('http')
async def authMiddleware(request: fastapi.Request, call_next):
    status, resp = await validate_header_based_authentication(request)
    if status:
        return add_security_headers(await call_next(request))
    elif not status and resp:
        return add_security_headers(resp)
    # return await call_next(request)
    response = fastapi.Response(None, 403)
    if (request.url.path in ['/docs', '/openapi.json', '/api/login', '/api/session/me', '/api/users/login',
                             '/api/session/encryption-status', '/api/ping',
                             '/api/users/sso_auth_url', '/api/users/sso_auth_callback',
                             '/api/users/sso_redirection_url'] +
            urdhva_base.settings.noauth_urls or \
            re.match(r"/api/[\S\s\w]*login\b(?![a-zA-Z])", request.url.path) \
            or re.match(r"/api/[\S\s\w]*authorize", request.url.path)):
        return add_security_headers(await call_next(request))
    rpt = urdhva_base.context.context.get('rpt', {})
    cookie = request.cookies.get(cookie_name, None)
    if not cookie and not rpt:
        base_url = urdhva_base.ctx["base_url"]
        if not base_url:
            response = fastapi.responses.JSONResponse("Provided entity is Invalid", 403)
            return add_security_headers(response)
        # redirect_url = f"https://{request.base_url.hostname}/login"
        # resp_dict = {"url": redirect_url}
        response = fastapi.responses.HTMLResponse("Invalid Session", 401)
    elif cookie and not rpt:
        response = fastapi.responses.HTMLResponse("Invalid Session", 401)
    elif cookie or rpt:
        if await has_permission(request.method, request.scope['path']):
            response: fastapi.responses.Response = await call_next(request)
            if response.status_code == 307:
                for index, header in enumerate(response.raw_headers):
                    if header[0].decode() == 'location' and header[1].decode().startswith('http://'):
                        url = header[1].decode().replace('http://', 'https://')
                        response.raw_headers[index] = ('location'.encode(), url.encode())
    return add_security_headers(response)


def verify_security_policy(host_name, header_value):
    if not urdhva_base.settings.origin_check_enabled or  not header_value:
        return True
    parsed_origin = urlparse(header_value)
    return host_name == parsed_origin.netloc


@app.middleware('http')
async def contextMiddleware(request: fastapi.Request, call_next):
    # Verifying Content Length, To avoid man in middle attack
    # if request.headers.get("content-length"):
    #     actual_body = await request.body()  # Read the request body
    #     actual_length = len(actual_body)
    #     if actual_length != len(request.headers.get("content-length")):
    #         return fastapi.responses.Response("Content-Length mismatch", 400)
    # Verifying request origin and hostname
    if not verify_security_policy(request.base_url.hostname, request.headers.get('origin')):
        return fastapi.responses.Response("Origin mismatch", 403)
    # Verifying request referer and hostname
    if not verify_security_policy(request.base_url.hostname, request.headers.get('referer')):
        return fastapi.responses.Response("Refer mismatch", 403)
    data = {}
    cookie_id = request.cookies.get(cookie_name, None)
    redis_client = await urdhva_base.redispool.get_redis_connection()
    entity_id = "Novex"
    if cookie_id:
        try:
            f = Fernet(urdhva_base.settings.fernet_key)
            d = json.loads(f.decrypt(cookie_id.encode()).decode())
            entity_id = d["entity_id"]
            data['base_url'] = d.get("base_url", '')
            cookie_id = d["cookie_id"]
        except:
            pass
    else:
        # JWT-based login flow
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, urdhva_base.settings.jwt_secret_key, 
                                     algorithms=urdhva_base.settings.jwt_algorithm)
                entity_id = payload.get("entity_id", entity_id)
                data['base_url'] = payload.get("base_url", '')
                data['rpt'] = payload
            except JWTError as e:
                print(f"JWT decode error: {e}")
    if not entity_id:
        if request.headers.get("entity_id", ""):
            entity_id = request.headers.get("entity_id", "")
        elif not urdhva_base.settings.multi_tenant_support:
            entity_id = request.base_url.hostname.split('.')[0]
        elif urdhva_base.settings.default_realm:
            entity_id = urdhva_base.settings.default_realm

    data['domain'] = request.base_url
    data['entity_obj'] = urdhva_base.entity.Entity()
    data['entity_id'] = entity_id
    if cookie_id:
        rkey = f"Novex_SessionData_{cookie_id}"
        cookie = await redis_client.get(rkey)
        if cookie:
            if isinstance(cookie, bytes):
                cookie = cookie.decode()
            cookie = cookie.split("$$_##_##_$$")
            if "=====" in cookie[0]:
                data['rpt'] = json.loads(base64.urlsafe_b64decode(cookie[0].split('.')[1] + '=====').decode())
            else:
                data['rpt'] = json.loads(base64.urlsafe_b64decode(cookie[0]).decode())
            data['id_auth_token'] = cookie[1] if len(cookie) > 1 else ""
        else:
            data["base_url"] = await get_baseurl(request, "OAUTH_RedirectUrl", entity_id)
            data['oauth_redirect'] = f'https://{data["base_url"]}/api/{entity_id}/login'
    else:
        data["base_url"] = await get_baseurl(request, "OAUTH_RedirectUrl", entity_id)
        data['oauth_redirect'] = f'https://{data["base_url"]}/api/{entity_id}/login'
    if data.get('rpt'):
        data['rpt']['includes'] = ",".join([v for k, v in data['rpt'].items() if k.startswith("includes")])
        data['rpt']['excludes'] = ",".join([v for k, v in data['rpt'].items() if k.startswith("excludes")])

    _starlette_context_token: contextvars.Token = urdhva_base.context._request_scope_context_storage.set(data)
    try:
        resp = await call_next(request)
    except Exception as error:
        print(error)
        """
        Exception error
        """
        err_format = '''Error:
        Stack Trace:
        %s
        ''' % (traceback.format_exc())
        print(err_format)
        status, id = await createInternalErrorMessage(traceback.format_exc())
        resp_message = "Internal Error"
        if status:
            resp_message += ":- %s" % id
        response = fastapi.responses.JSONResponse(resp_message, 500)
        return response
    urdhva_base.context._request_scope_context_storage.reset(_starlette_context_token)
    return resp


# @app.get("/api/login")
async def login_old(request: fastapi.Request, code: typing.Optional[str] = None):
    return await login(request, code, urdhva_base.ctx["entity_id"])


# @app.get("/api/{entity_id}/login")
async def login(request: fastapi.Request, code: typing.Optional[str] = None,
                entity_id: typing.Optional[str] = ""):
    base_url = ""
    if not entity_id:
        entity_id = urdhva_base.ctx["entity_id"]
    auth = await get_customer_authentication_extension(entity_id)
    if code:
        # Connect to Keycloak and get the client secret
        # 1. Connect to master realm and get access token (Login)
        # 2. Get the Id of the client
        # 3. With the Id get the client secret
        resp = None
        async with httpx.AsyncClient(verify=False, timeout=90) as client:
            login_data = {
                "client_id": "admin-cli",
                "username": urdhva_base.settings.keycloak_admin,
                "password": urdhva_base.settings.keycloak_password,
                "grant_type": "password"
            }
            login_url = (f'{urdhva_base.settings.keycloak_internal_url}/{auth}/'
                         f'realms/master/protocol/openid-connect/token')
            master_login_resp = await client.post(login_url, data=login_data)
            # print('Keycloak Login response:', master_login_resp.text)
            auth_resp = master_login_resp.json()

            client_id_url = f'{urdhva_base.settings.keycloak_internal_url}/{auth}/admin/realms/{entity_id}/' \
                          f'clients?clientId={entity_id}_client'
            headers = {
                "Authorization": f'Bearer {auth_resp["access_token"]}'
            }
            client_id_resp = await client.get(client_id_url, headers=headers)
            if client_id_resp.status_code // 100 != 2:
                print(f"URL:- {client_id_url}, StatusCode:- {client_id_resp.status_code}, Resp:- {client_id_resp.text}")
            client_id_resp = client_id_resp.json()

            client_secret_url = f'{urdhva_base.settings.keycloak_internal_url}/{auth}/admin/realms/{entity_id}/' \
                              f'clients/{client_id_resp[0]["id"]}/client-secret'
            # print("Client Secret Url: %s" % clientSecretUrl)
            client_secret_resp = await client.get(client_secret_url, headers=headers)
            if client_secret_resp.status_code // 100 != 2:
                print(
                    f"URL:- {client_secret_url}, StatusCode:- {client_secret_resp.status_code}, "
                    f"Resp:- {client_secret_resp.text}")
            client_secret_resp = client_secret_resp.json()
            # print("Client Secret Url Resp: %s" % clientsecret_resp)

            # Get Access token for the loggedin user
            url = f'{urdhva_base.settings.keycloak_internal_url}/{auth}/realms/{entity_id}/protocol/openid-connect/token'
            base_url = await get_baseurl(request, "OAUTH_RedirectUrl", entity_id)
            oauth_redirect_url = f'https://{base_url}/api/{entity_id}/login'
            data = {
                'grant_type': 'authorization_code',
                'client_id': f'{entity_id}_client',
                'client_secret': client_secret_resp['value'],
                'redirect_uri': oauth_redirect_url,
                'code': code
            }
            resp = await client.post(url, data=data)
            if resp.status_code // 100 != 2:
                print(f"Validate Token Output url: {url}")
                print("Token:", resp.status_code, resp.text)
            resp = resp.json()
            id_auth_token = resp.get("id_token", "")

            # Using the access token obtained above, get the RPT token
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:uma-ticket",
                "audience": f'{entity_id}_client',
            }
            headers = {"Authorization": f'Bearer {resp["access_token"]}'}
            resp = await client.post(url, data=data, headers=headers)
            if resp.status_code // 100 != 2:
                print("RPT Token:", resp.status_code, resp.text)
    else:
        response = fastapi.responses.JSONResponse({"status": "Invalid parameters"}, 403)
        return response

    if not code:
        response = fastapi.responses.JSONResponse({"status": "Logged in Successfully"}, 200)
    else:
        redirect_url = "/"
        response = fastapi.responses.RedirectResponse(redirect_url)
    if resp and resp.status_code / 100 == 2:
        # Writing cookie details to redis for reducing cookie size
        cookie_id = str(uuid.uuid4())
        redis_client = await urdhva_base.redispool.get_redis_connection()
        rkey = f"{entity_id}_SessionData_{cookie_id}"
        f = Fernet(urdhva_base.settings.fernet_key)
        d = {"entity_id": entity_id, "cookie_id": cookie_id, "base_url": base_url}
        cookie_key = f.encrypt(json.dumps(d).encode()).decode()
        time = 3 * 60 * 60 if not code else 24 * 60 * 60
        # ID Auth Hint Adding with separator `$$_##_##_$$`
        if not id_auth_token:
            await redis_client.setex(rkey, time, resp.json()["access_token"])
        else:
            await redis_client.setex(rkey, time, resp.json()["access_token"] + "$$_##_##_$$" + id_auth_token)
        response.set_cookie(cookie_name, cookie_key, httponly=urdhva_base.settings.session_httponly,
                            secure=urdhva_base.settings.session_secure, samesite=urdhva_base.settings.session_same_site)
    else:
        if not code:
            response = fastapi.responses.JSONResponse({"status": "Invalid Credentials"}, 401)
    return response


@app.get("/api/logout")
async def logout(request: fastapi.Request):
    # {'url': f"https://{request.base_url.hostname}/login"}    
    response = fastapi.responses.HTMLResponse("", 401)
    cookie_id = request.cookies.get(cookie_name, None)
    if cookie_id:
        try:
            f = Fernet(urdhva_base.settings.fernet_key)
            d = json.loads(f.decrypt(cookie_id.encode()).decode())
            cookie_id = d["cookie_id"]
        except:
            ...
        
        audit = await UserLoginAudit.get_all(
            urdhva_base.queryparams.QueryParams(q=f"login_id='{cookie_id}'"),
            resp_type='plain')

        if audit["data"]:
            await UserLoginAudit(
                **{
                    "id": audit["data"][0]["id"], 
                    "login_status": "Logged Out", 
                    "logout_time": urdhva_base.utilities.get_present_time()
                    }
            ).modify()

        redis_client = await urdhva_base.redispool.get_redis_connection()
        rkey = f"Novex_SessionData_{cookie_id}"
        await redis_client.delete(rkey)
    response.delete_cookie(cookie_name, httponly = urdhva_base.settings.session_httponly,
                           secure=urdhva_base.settings.session_secure, samesite=urdhva_base.settings.session_same_site)
    # todo:- Need to clear dashboard sessions    
    return response


@app.get("/api/{entity_id}/authorize")
async def authorize(request: fastapi.Request, entity_id: str):
    base_url = await get_baseurl(request, "OAUTH_RedirectUrl", entity_id)
    redis_client = await urdhva_base.redispool.get_redis_connection()
    oauth_redirect_url = f'https://{base_url}/api/{entity_id}/login'
    if await redis_client.hget(f"{entity_id}_domainMapping", request.base_url.hostname):
        data = await redis_client.hget(f"{entity_id}_domainMapping", request.base_url.hostname)
        url = json.loads(data)["base_url"]
        oauth_redirect_url = f'https://{request.base_url.hostname}/api/{entity_id}/login'
    redis_client = await urdhva_base.redispool.get_redis_connection()
    data = await redis_client.hget(f"{entity_id}_domainMapping", request.base_url.hostname)
    if data:
        base_url = json.loads(data)["base_url"]
    redirect_url = f'https://{base_url}/{await get_customer_authentication_extension(entity_id)}' \
                   f'/realms/{entity_id}/protocol/openid-connect/auth?client_id={entity_id}' \
                   f'_client&response_type=code&redirect_uri={oauth_redirect_url}&scope=email openid&state=123'
    return RedirectResponse(url=redirect_url)


@app.get("/api/session/me")
async def me(request: fastapi.Request):
    rpt = urdhva_base.context.context.get('rpt', {})
    resp = {"is_authenticated": False}
    permission_data = await get_permission()
    if permission_data["is_authenticated"]:
        resp = {"permissions": permission_data["allowed_roles"], "is_authenticated": True}
        base_keys = ["first_name", "last_name", "system_role", "allowed_roles", "email", "employee_id", "novex_role"]
        permission_keys = ["bu", "region", "zone", "state", "sales_area", "sap_id"]
        resp.update({key: rpt.get(key, '') for key in base_keys})
        resp.update({key: rpt.get(key, []) for key in permission_keys})
    return resp


# API to give whether security/encryption module enabled or not
@app.get("/api/session/encryption-status")
async def encryption_enabled(request: fastapi.Request):
    return "enabled" if urdhva_base.settings.enable_encrypted_payload and \
                        len(urdhva_base.settings.encryption_key) > 0 else "disabled"


@app.get("/api/ping")
async def ping():
    return "pong"


def convert_role_dict(role_data):
    role_dict = {}
    if "authorization" in role_data and "permissions" in role_data['authorization']:
        for roleScop in role_data['authorization']['permissions']:
            if roleScop['rsname'].lower() not in role_dict:
                role_dict[roleScop['rsname'].lower()] = roleScop['scopes']
    return role_dict


handler = Mangum(app)
