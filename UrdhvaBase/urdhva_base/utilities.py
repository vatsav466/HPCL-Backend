import re
import pytz
import asyncio
import datetime
import functools
import threading
import snakecase


# Custom JSON serializer for datetime objects
def datetime_serializer(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()


def run_once(func):
    """
    This decorator wraps a function and makes sure it is executed only once for the lifetime of the process.
    Depending on whether the wrapped function is normal or async it wraps accordingly.
    It cache's the response returned by the original function and returns the cached response on subsequent calls.

    Usage:
    @run_once
    def foo():
        pass

    @run_once
    async def async_foo():
        pass
    
    """
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with wrapper.lock:
                if not wrapper.has_executed:
                    wrapper.has_executed = True
                    wrapper.response = await func(*args, **kwargs)
            return wrapper.response
        wrapper.lock = asyncio.Lock()
    else:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with wrapper.lock:
                if not wrapper.has_executed:
                    wrapper.has_executed = True
                    wrapper.response = func(*args, **kwargs)
            return wrapper.response
                    
        wrapper.lock = threading.Lock()
    wrapper.has_executed = False
    return wrapper


def snake_case(s):
    """
    # Replace hyphens with spaces, then apply regular expression substitutions for title case conversion
    # and add an underscore between words, finally convert the result to lowercase
    :param s: string
    :return: converted snake case string
    Example:- snake_case("AlgoFusion")
              return:- algo_fusion
    """
    return snakecase.convert(s)    


def get_present_time(utc=False):
    """
    Function to get present time in utc or local format
    :param utc:
    :return:
    """
    time_stamp = datetime.datetime.now(datetime.timezone.utc)
    if not utc:
        time_stamp = time_stamp.astimezone(pytz.timezone('Asia/Kolkata'))
    return time_stamp

