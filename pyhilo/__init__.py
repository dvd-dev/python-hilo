"""Define the hilo package."""

from pyhilo.api import API
from pyhilo.const import UNMONITORED_DEVICES
from pyhilo.device import HiloDevice
from pyhilo.device.switch import Switch
from pyhilo.devices import Devices
from pyhilo.event import Event
from pyhilo.exceptions import HiloError, InvalidCredentialsError, WebsocketError
from pyhilo.oauth2 import AuthCodeWithPKCEImplementation
from pyhilo.util import from_utc_timestamp, time_diff
from pyhilo.websocket import WebsocketEvent

__all__ = [
    "API",
    "UNMONITORED_DEVICES",
    "AuthCodeWithPKCEImplementation",
    "Devices",
    "Event",
    "HiloDevice",
    "HiloError",
    "InvalidCredentialsError",
    "Switch",
    "WebsocketError",
    "WebsocketEvent",
    "from_utc_timestamp",
    "time_diff",
]
