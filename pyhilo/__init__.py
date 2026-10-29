"""Define the hilo package."""

from pyhilo.api import API
from pyhilo.auth import AbstractAuth
from pyhilo.const import UNMONITORED_DEVICES
from pyhilo.device import HiloDevice
from pyhilo.device.switch import Switch
from pyhilo.devices import Devices
from pyhilo.event import Event
from pyhilo.exceptions import HiloError, InvalidCredentialsError, SignalRError
from pyhilo.signalr import SignalREvent
from pyhilo.util import from_utc_timestamp, time_diff

__all__ = [
    "API",
    "AbstractAuth",
    "Devices",
    "HiloDevice",
    "Event",
    "HiloError",
    "InvalidCredentialsError",
    "SignalRError",
    "from_utc_timestamp",
    "time_diff",
    "SignalREvent",
    "UNMONITORED_DEVICES",
    "Switch",
]
