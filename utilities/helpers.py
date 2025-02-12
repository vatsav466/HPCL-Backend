import urdhva_base
import httpx
import base64
import string
import hashlib
import datetime
import traceback
import urdhva_base.redispool
from calendar import monthrange
try:
    from secrets import choice
except ImportError:
    from random import choice
from dateutil.relativedelta import relativedelta


def month_short_to_number(short_name):
    # Parses the short month name (%b) and extracts the month as an integer.
    return datetime.datetime.strptime(short_name, '%b').month


def password_generator(password_length=16, special_characters_allowed=True, case_sensitive=True):
    """
    @description: function to generate random password
    @param password_length: length of the password
    @param special_characters_allowed: whether to allow special characters
    @param case_sensitive: whether to allow case sensitive(ascii uppercase allowed or not)
    @return: generated password of length password_length
    """
    password_chars = list(string.digits) + list(string.ascii_lowercase)
    if case_sensitive:
        password_chars += list(string.ascii_uppercase)
    if special_characters_allowed:
        password_chars += ["!", "#", "$", "%", "^", "&", "*", "(", ")", ",", ".", "-", "_", "+", "=", "<", ">", "?"]
    random_pass = "".join([choice(password_chars) for i in range(password_length)])
    return random_pass


def get_time_stamp_by_delta(dt=None, months=0, days=0, years=0, with_month_start_day=True,
                            date_time_format="%Y-%m-%d", ascending=False, with_month_end_day=False):
    """
    Get the timestamp by descending or ascending a specified number of months from the current date.
    :param dt: datetime object
    :param months: Total months to descend
    :param days: Total days to descend
    :param years: Total years to descend
    :param with_month_start_day: whether date should start from day 1 or present day
    :param date_time_format: Format to return the date
    :param ascending: To use in incremental or decremental format
    :param with_month_end_day: whether date should be actual or month end date
    :return: Formatted date string
    Example:
    on 2025-01-19
      Case 1
        input:- utilities.helpers.get_time_stamp_by_delta(days=1, with_month_start_day=False, year=1, ascending=True)
        response:- '2026-01-20'
      Case 2
        input:- utilities.helpers.get_time_stamp_by_delta(days=1, with_month_start_day=False, year=1, ascending=False)
        response:- '2024-01-18'
      Case 3
        input:- utilities.helpers.get_time_stamp_by_delta(days=1, with_month_start_day=True, year=1, ascending=False)
        response:- '2023-12-31'
      Case 4
        input:- utilities.helpers.get_time_stamp_by_delta(with_month_start_day=True, year=1, ascending=False)
        response:- '2024-01-01'
      Case 5
        input:- utilities.helpers.get_time_stamp_by_delta(days=1, year=0, date_time_format=None, ascending=False)
        response:- datetime.datetime(2024, 12, 31, 7, 56, 43, 663410, tzinfo=datetime.timezone.utc)
    """
    # Todo:- Need to add default timezone from settings file and requested timezone as input for changes
    if not dt:
        dt = datetime.datetime.now(tz=datetime.timezone.utc)

    # Set the day to 1 if with_month_start_day is True
    if with_month_start_day:
        dt = dt.replace(day=1)
    elif not months and with_month_end_day:
        _, months_days = monthrange(dt.year, dt.month)
        dt = dt.replace(day=months_days)

    # Subtract the specified number of months
    if months > 0:
        dt = dt - relativedelta(months=months) if not ascending else dt + relativedelta(months=months)
        if with_month_end_day:
            _, months_days = monthrange(dt.year, dt.month)
            dt = dt.replace(day=months_days)
    elif years > 0:
        day_filter = 0
        if days > 0:
            day_filter = days
        dt = dt - relativedelta(year=dt.year-years, days=day_filter) if not ascending \
            else dt + relativedelta(year=dt.year+years, days=day_filter)
    elif days > 0:
        dt = dt - relativedelta(days=days) if not ascending else dt + relativedelta(days=days)

    # Format the date
    if date_time_format:
        return dt.strftime(date_time_format)

    return dt


def generate_hash(list_of_strings, bit_size=64):
    """
    Generates unique hash key for the given inputs
    :param list_of_strings:
    :param bit_size:
    :return: unique string
    """
    # Convert the list of strings to a single string
    combined_string = ''.join(list_of_strings)
    # Create a hash object
    if bit_size > 40:
        # SHA256 for 64-bit key
        hash_object = hashlib.sha256()
    elif bit_size > 32:
        # SHA1 for 40-bit key
        hash_object = hashlib.sha1()
    else:
        # SHA1 for 32-bit key
        hash_object = hashlib.md5()
    # Update the hash object with the combined string
    hash_object.update(combined_string.encode('utf-8'))
    # Get the hexadecimal digest of the hash
    hash_value = hash_object.hexdigest()
    return hash_value


def encrypt_file(file_path):
    """
    Encrypt a file using the provided encryption key.
    
    Args:
        file_path (str): Path to the file to be encrypted.
        encryption_key (bytes): Encryption key.

    Returns:
        str: Path to the encrypted file.
    """
    encrypted_file_path = f"{file_path}.enc"

    with open(file_path, "rb") as file:
        file_data = file.read()  # Read file content
        with open(encrypted_file_path, "wb") as encrypted_file:
            encrypted_file.write(file_data)  # Save encrypted data
    file_path = str(urdhva_base.types.Secret().validate(encrypted_file_path, ''))
    return base64.b64encode(file_path.encode()).decode()


def normalize_string(input_value):
    """
    Normalizes provided string, If binary convert to string and return else return string
    :param input_value:
    :return:
    """
    if isinstance(input_value, bytes):
        return input_value.decode()
    return input_value


async def get_location_details(bu, sap_id):
    """
    Retrieves location details based on the provided business unit and SAP ID.

    Parameters:
    bu (str): The business unit identifier.
    sap_id (str): The SAP ID of the location.

    Returns:
    dict: Location details, including name, address, coordinates, etc., or None if not found.
    """
    if not bu or not sap_id:
        print("Invalid parameters: 'bu' and 'sap_id' are required.")
        return False, {"msg": "Invalid parameters: 'bu' and 'sap_id' are required."}
    async with httpx.AsyncClient(verify=False) as client:
        base_url = f"http://{urdhva_base.settings.cache_gateway_host}:{urdhva_base.settings.cache_gateway_port}"
        resp = await client.get(f"{base_url}/api_cache/v1/get_location_data", params={"bu": bu,
                                                                                      'location_id': sap_id})
        if resp.status_code // 100 == 2:
            return resp.json()
        else:
            print(resp.status_code, resp.text)
    return False, {}


async def get_alert_camunda_url(alert_id, base_url):
    """
    API to get camunda based on the alertid
    :param alert_id:
    :return:
    """
    redis_ins = urdhva_base.redispool.get_synchronous_redis_connection()
    try:
        if redis_ins.hexists("alert_camunda_url", f"{alert_id}"):
            url = redis_ins.hget("alert_camunda_url", f"{alert_id}")
            return url.decode() if isinstance(url, bytes) else url
        return base_url
    except:
        return base_url
    finally:
        try:
            redis_ins.close()
        except:
            ...


def validate_camunda_settings_rule(camunda_settings, location_id, bu):
    """
    Verifying rule configuring for camunda, Validating odd/even settings
    :param camunda_settings:
    :param location_id:
    :param bu:
    :return:
    """
    if not camunda_settings.get("rule"):
        return True
    try:
        if camunda_settings['rule'] == "even":
            if int(location_id) // 2 == 0:
                return True
        elif camunda_settings['rule'] == "odd":
            if int(location_id) // 2 != 0:
                return True
    except Exception as e:
        print(f"Exception while handling rule {e}, Traceback {traceback.format_exc()}")
    return False


async def get_camunda_url(bu, sap_id, alert_section):
    """
    Logic to decide serving camunda url for given bu and sap_id
    :param bu:
    :param sap_id:
    :param alert_section:
    :return:
    """
    camunda_config = urdhva_base.settings.camunda_configuration
    default_url = urdhva_base.settings.camunda_url

    # If configuration is missing or BU is not in the config, return default
    if not camunda_config or bu not in camunda_config:
        return default_url

    status, location_data = await get_location_details(bu, sap_id)
    if not status:
        return default_url

    # Fields to check in settings
    match_keys = ['sap_id', 'sales_area', 'region', 'zone']

    # Checking ones having alert section
    for settings in camunda_config[bu]:
        if settings.get('alert_section') == alert_section:
            if (any(settings.get(k) and location_data.get(k, "") in settings[k] for k in match_keys) and
                    validate_camunda_settings_rule(settings, sap_id, bu)):
                return settings['url']

    # Checking ones not having alert section
    for settings in camunda_config[bu]:
        if not settings.get('alert_section'):
            if (any(settings.get(k) and location_data.get(k, "") in settings[k] for k in match_keys) and
                    validate_camunda_settings_rule(settings, sap_id, bu)):
                return settings['url']

    # Checking for single URL with alert section
    for settings in camunda_config[bu]:
        if settings.get('alert_section') == alert_section and validate_camunda_settings_rule(settings, sap_id, bu):
            return settings['url']

    # Checking for single URL without alert section
    for settings in camunda_config[bu]:
        if not settings.get('alert_section') and validate_camunda_settings_rule(settings, sap_id, bu):
            return settings['url']

    # Checking for global match
    for settings in camunda_config[bu]:
        if (any(not settings.get(k) or "*" in settings[k] for k in match_keys) and
                validate_camunda_settings_rule(settings, sap_id, bu)):
            return settings['url']

    return default_url

async def get_doc_link(file_name: str):
    return f"https://10.90.38.161/api/alerts/stored_document?file_name={file_name}"
