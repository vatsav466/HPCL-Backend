import urdhva_base
import base64
import string
import hashlib
import datetime
try:
    from secrets import choice
except ImportError:
    from random import choice
from dateutil.relativedelta import relativedelta



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


def get_time_stamp_by_delta(dt=None, months=0, days=0, with_month_start_day=True, date_time_format="%Y-%m-%d", ascending=False):
    """
    Get the timestamp by descending or ascending a specified number of months from the current date.
    :param dt: datetime object
    :param months: Total months to descend
    :param days: Total days to descend
    :param with_month_start_day: whether date should start from day 1 or present day
    :param date_time_format: Format to return the date
    :return: Formatted date string
    """
    if not dt:
        dt = datetime.datetime.now(tz=datetime.timezone.utc)

    # Set the day to 1 if with_month_start_day is True
    if with_month_start_day:
        dt = dt.replace(day=1)

    # Subtract the specified number of months
    if months > 0:
        dt = dt - relativedelta(months=months) if not ascending else dt + relativedelta(months=months)
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