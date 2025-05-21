"""Utility functions for state management."""

from __future__ import annotations

import asyncio
from datetime import datetime
from os.path import isfile
from typing import Any, ForwardRef, TypedDict, TypeVar, get_type_hints

import aiofiles
import yaml

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
    """Generate a default dict based on typed dict

    This function recursively creates a nested dictionary structure that mirrors
    the structure of a TypedDict (like StateDict, FirebaseDict, etc.). All the
    values in the resulting dictionary are initialized to None. This is used to
    create a template or a default "empty" state object.

    This function is designed to work correctly whether or not
    `from __future__ import annotations` is used.

    :param cls: The TypedDict class (e.g., StateDict, FirebaseDict) for which
                to generate the default dictionary.
    :type cls: type[T]
    :return: A dictionary with the same structure as the TypedDict, but with
             all values set to None.
    :rtype: dict[str, Any]
    """
    new_dict: StateDict = {}
    # Iterate through the type hints of the TypedDict class.
    # get_type_hints handles both string-based type hints (from
    # `from __future__ import annotations`) and regular type hints.
    # include_extras=True is added to make sure the function works correctly with `Literal` types.
    for k, v in get_type_hints(cls, include_extras=True).items():
        # When using `get_type_hints`, some types are returned as `ForwardRef` objects.
        # This is a special type used to represent a type that is not yet defined.
        # We need to check if `v` is a `ForwardRef` and, if so, get the actual type
        # using `v.__forward_value__`.
        if isinstance(v, ForwardRef):
            v = v.__forward_value__
        # Check if the type `v` itself has `__annotations__`.
        # If it does, it means that `v` is also a TypedDict (or something that
        # behaves like one), indicating a nested structure.
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
    if not isfile(
        state_yaml
    ):  # noqa: PTH113 - isfile is fine and simpler in this case.
        return _get_defaults(StateDict)  # type: ignore
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
        merged_state: dict[str, Any] = {key: {**current_state.get(key, {}), **state}}  # type: ignore[dict-item]
        new_state: dict[str, Any] = {**current_state, **merged_state}
        async with aiofiles.open(state_yaml, mode="w") as yaml_file:
            LOG.debug("Saving state to yaml file")
            # TODO: Use asyncio.get_running_loop() and run_in_executor to write
            # to the file in a non blocking manner. Currently, the file writes
            # are properly async but the yaml dump is done synchronously on the
            # main event loop.
            content = yaml.dump(new_state)
            await yaml_file.write(content)
