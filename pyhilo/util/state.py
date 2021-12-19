from datetime import datetime
from os.path import isfile
from typing import Any, Optional, Type, TypedDict, TypeVar, Union

import ruyaml as yaml

from pyhilo.const import LOG


class TokenDict(TypedDict):
    access: Optional[str]
    refresh: Optional[str]
    expires_at: datetime


class AndroidDeviceDict(TypedDict):
    token: str
    device_id: int


class WebsocketTransportsDict(TypedDict):
    transport: str
    transfer_formats: list[str]


class WebsocketDict(TypedDict, total=False):
    token: str
    connection_id: str
    full_ws_url: str
    url: str
    available_transports: list[WebsocketTransportsDict]


class RegistrationDict(TypedDict, total=False):
    reg_id: str
    expires_at: datetime


class FirebaseDict(TypedDict):
    fid: Optional[str]
    name: Optional[str]  # "projects/18450192328/installations/d7N8yHopRWOiTYCrnYLi8a"
    token: TokenDict


class StateDict(TypedDict, total=False):
    token: TokenDict
    registration: RegistrationDict
    firebase: FirebaseDict
    android: AndroidDeviceDict
    websocket: WebsocketDict


T = TypeVar("T", bound="StateDict")


def __get_defaults__(cls: Type[T]) -> dict[str, Any]:
    """Generates a default dict based on typed dict

    :param cls: TypedDict class
    :type cls: Type[T]
    :return: Dictionary with empty values
    :rtype: dict[str, Any]
    """
    # NOTE(dvd): Find a better way of identifying another TypedDict.
    new_dict: StateDict = {}
    for k, v in cls.__annotations__.items():
        if hasattr(v, "__annotations__"):
            new_dict[k] = __get_defaults__(v)  # type: ignore
        else:
            new_dict[k] = None  # type: ignore
    return new_dict  # type: ignore


def get_state(state_yaml: str) -> StateDict:
    """Read in state yaml.
    :param state_yaml: filename where to read the state
    :type state_yaml: ``str``
    :rtype: ``StateDict``
    """
    if not isfile(state_yaml):
        return __get_defaults__(StateDict)  # type: ignore
    with open(state_yaml) as yaml_file:
        LOG.debug("Loading state from yaml")
        state_yaml_payload: StateDict = yaml.load(yaml_file, Loader=yaml.Loader)
    return state_yaml_payload


def set_state(
    state_yaml: str,
    key: str,
    state: Union[
        TokenDict, RegistrationDict, FirebaseDict, AndroidDeviceDict, WebsocketDict
    ],
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
    current_state = get_state(state_yaml)
    merged_state: dict[str, Any] = {key: {**current_state.get(key, {}), **state}}  # type: ignore
    new_state: dict[str, Any] = {**current_state, **merged_state}
    with open(state_yaml, "w") as yaml_file:
        LOG.debug("Saving state to yaml file")
        yaml.dump(new_state, yaml_file, Dumper=yaml.RoundTripDumper)
