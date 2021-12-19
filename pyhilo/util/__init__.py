"""Define utility modules."""
import asyncio
from datetime import datetime, timedelta
import re
from typing import Any, Callable

from dateutil import tz
from dateutil.parser import parse

from pyhilo.const import LOG  # noqa: F401

CAMEL_REX_1 = re.compile("(.)([A-Z][a-z]+)")
CAMEL_REX_2 = re.compile("([a-z0-9])([A-Z])")


def schedule_callback(callback: Callable[..., Any], *args: Any) -> None:
    """Schedule a callback to be called."""
    if asyncio.iscoroutinefunction(callback):
        asyncio.create_task(callback(*args))
    else:
        loop = asyncio.get_running_loop()
        loop.call_soon(callback, *args)


def camel_to_snake(string: str) -> str:
    string = CAMEL_REX_1.sub(r"\1_\2", string)
    return CAMEL_REX_2.sub(r"\1_\2", string).lower()


def snake_to_camel(string: str) -> str:
    components = string.split("_")
    return components[0].title() + "".join(x.title() for x in components[1:])


def from_utc_timestamp(date_string: str) -> datetime:
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    return parse(date_string).replace(tzinfo=from_zone).astimezone(to_zone)


def time_diff(ts1: datetime, ts2: datetime) -> timedelta:
    to_zone = tz.tzlocal()
    return ts1.astimezone(to_zone) - ts2.astimezone(to_zone)
