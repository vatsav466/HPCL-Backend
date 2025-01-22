import urdhva_base
import base64
import string
import hashlib
import datetime
import urdhva_base.redispool
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
                            date_time_format="%Y-%m-%d", ascending=False):
    """
    Get the timestamp by descending or ascending a specified number of months from the current date.
    :param dt: datetime object
    :param months: Total months to descend
    :param days: Total days to descend
    :param years: Total years to descend
    :param with_month_start_day: whether date should start from day 1 or present day
    :param date_time_format: Format to return the date
    :param ascending: To use in incremental or decremental format
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

    # Subtract the specified number of months
    if months > 0:
        dt = dt - relativedelta(months=months) if not ascending else dt + relativedelta(months=months)
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
