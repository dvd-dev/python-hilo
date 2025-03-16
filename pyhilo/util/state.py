"""Utility functions for state management."""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict, TypeVar

import aiofiles
import ruyaml as yaml

from pyhilo.const import LOG

lock = asyncio.Lock()

# These should ideally be data classes and not "TypedDict"


class TokenDict(TypedDict):
    """Represents a dictionary containing token information."""

    access: str | None
    refresh: str | None
    expires_at: datetime


class AndroidDeviceDict(TypedDict):
    """Represents a dictionary containing Android device information."""

    token: str
    device_id: int


class WebsocketTransportsDict(TypedDict):
    """Represents a dictionary containing Websocket connection information."""

    transport: str
    transfer_formats: list[str]


class WebsocketDict(TypedDict, total=False):
    """Represents a dictionary containing registration information."""

    token: str
    connection_id: str
    full_ws_url: str
    url: str
    available_transports: list[WebsocketTransportsDict]


class RegistrationDict(TypedDict, total=False):
    """Represents a dictionary containing registration information."""

    reg_id: str
    expires_at: datetime


class FirebaseDict(TypedDict):
    """Represents a dictionary containing Firebase information."""

    fid: str | None
    # "projects/18450192328/installations/d7N8yHopRWOiTYCrnYLi8a"
    name: str | None
    token: TokenDict


class StateDict(TypedDict, total=False):
    """Represents a dictionary containing the overall application state."""

    token: TokenDict
    registration: RegistrationDict
    firebase: FirebaseDict
    android: AndroidDeviceDict
    websocket: WebsocketDict


T = TypeVar("T", bound="StateDict")


def _get_defaults(cls: type[T]) -> dict[str, Any]:
    """Generate a default dict based on typed dict.

    :param cls: TypedDict class
    :type cls: type[T]
    :return: Dictionary with empty values
    :rtype: dict[str, Any]
    """
    # NOTE(dvd): Find a better way of identifying another TypedDict.
    new_dict: StateDict = {}
    for k, v in cls.__annotations__.items():
        if hasattr(v, "__annotations__"):
            new_dict[k] = _get_defaults(v)  # type: ignore[literal-required]
        else:
            new_dict[k] = None  # type: ignore[literal-required]
    return new_dict  # type: ignore[return-value]


async def get_state(state_yaml: str) -> StateDict:
    """Read in state yaml.

    :param state_yaml: filename where to read the state
    :type state_yaml: ``str``
    :rtype: ``StateDict``
    """
    if not Path(state_yaml).is_file():
        return _get_defaults(StateDict)
    async with aiofiles.open(state_yaml, mode="r") as yaml_file:
        LOG.debug("Loading state from yaml")
        content = await yaml_file.read()
        state_yaml_payload: StateDict = yaml.safe_load(content)
    return state_yaml_payload


async def set_state(
    state_yaml: str,
    key: str,
    state: TokenDict
    | RegistrationDict
    | FirebaseDict
    | AndroidDeviceDict
    | WebsocketDict,
) -> None:
    """Save state yaml.

    :param state_yaml: filename where to read the state
    :type state_yaml: ``str``
    :param key: Key name
    :type key: ``str``
    :param state: Dictionary containing the state
    :type state: ``StateDict``
    :rtype: ``StateDict``
    """
    async with lock:  # note ic-dev21: on lock le fichier pour être sûr de finir la job
        current_state = await get_state(state_yaml) or {}
        merged_state: dict[str, Any] = {
            key: {**current_state.get(key, {}), **state}
        }  # type: ignore[dict-item]
        new_state: dict[str, Any] = {**current_state, **merged_state}
        async with aiofiles.open(state_yaml, mode="w") as yaml_file:
            LOG.debug("Saving state to yaml file")
            content = yaml.dump(new_state)
            await yaml_file.write(content)
