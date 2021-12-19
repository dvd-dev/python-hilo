"""Define devices"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Union

from pyhilo.const import (
    HILO_DEVICE_ATTRIBUTES,
    HILO_LIST_ATTRIBUTES,
    HILO_PROVIDERS,
    HILO_READING_TYPES,
    HILO_UNIT_CONVERSION,
    LOG,
)
from pyhilo.util import camel_to_snake, from_utc_timestamp

if TYPE_CHECKING:
    from pyhilo import API


def get_device_attributes() -> list[DeviceAttribute]:
    attributes = []
    for attribute, value_type in HILO_READING_TYPES.items():
        attributes.append(DeviceAttribute(attribute, value_type))
    return attributes


class HiloDevice:
    def __init__(self, api: API, **kwargs: dict[str, Union[str, int]]) -> None:
        self._api = api
        self.id = 0
        self.location_id = 0
        self.type = "Unknown"
        self.name = "Unknown"
        self.supported_attributes: list[DeviceAttribute] = []
        self.settable_attributes: list[DeviceAttribute] = []
        self.readings: list[DeviceReading] = []
        self.update(**kwargs)

    def update(self, **kwargs: dict[str, Union[str, int]]) -> None:
        for att, val in kwargs.items():
            att = camel_to_snake(att)
            if att not in HILO_DEVICE_ATTRIBUTES:
                LOG.warning(f"Unknown device attribute {att}: {val}")
                continue
            elif att in HILO_LIST_ATTRIBUTES:
                new_val: list[DeviceAttribute] = [
                    DeviceAttribute(k, HILO_READING_TYPES.get(k, ""))
                    for k in map(str.strip, val.split(","))  # type: ignore
                    if k and k != "None"
                ]
            elif att == "provider":
                att = "manufacturer"
                new_val = HILO_PROVIDERS.get(int(val), f"Unknown ({val})")  # type: ignore
            elif att == "model_number":
                att = "model"
            else:
                new_val = val  # type: ignore
            setattr(self, att, new_val)
        self._tag = f"[{self.type} {self.name} ({self.id})]"
        self.last_update = datetime.now()

    async def set_attribute(self, attribute: str, value: Union[str, int, None]) -> None:
        if dev_attribute := self._api.dev_atts(attribute):
            LOG.debug(f"{self._tag} Setting {dev_attribute} to {value}")
            await self._set_attribute(dev_attribute, value)
            return
        LOG.warning(
            f"{self._tag} Unable to set attribute {attribute}: Unknown attribute"
        )

    async def _set_attribute(
        self, attribute: DeviceAttribute, value: Union[str, int, None]
    ) -> None:
        if attribute in self.settable_attributes:
            await self._api._set_device_attribute(self, attribute, value)
        else:
            LOG.warning(f"{self._tag} Invalid attribute {attribute} for device")

    def get_attribute(self, attribute: str) -> Union[DeviceReading, None]:
        if dev_attribute := self._api.dev_atts(attribute):
            return self._get_attribute(dev_attribute)
        LOG.warning(
            f"{self._tag} Unable to get attribute {attribute}: Unknown attribute"
        )
        return None

    def _get_attribute(self, attribute: DeviceAttribute) -> Union[DeviceReading, None]:
        reading = next((r for r in self.readings if r.device_attribute == attribute), None)
        return reading

    @property
    def hilo_attributes(self) -> list[str]:
        return [k.hilo_attribute for k in self.supported_attributes]

    @property
    def is_on(self) -> bool:
        attr = self.get_attribute("is_on")
        return attr.value if attr else False  # type: ignore

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HiloDevice):
            return NotImplemented
        return self.id == other.id

    def __str__(self) -> str:
        return self._tag


@dataclass(frozen=True, eq=True)
class DeviceAttribute:
    """Define a representation of an Attribute returned by Hilo."""

    hilo_attribute: str = field(compare=False)
    hilo_value_type: str = field(compare=False)
    attr: str | None = field(init=False, compare=True)
    value_type: str | None = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if self.hilo_attribute == "OnOff":
            attr = "is_on"
        else:
            attr = camel_to_snake(self.hilo_attribute)
        if self.hilo_value_type in ("null", "OnOff"):
            value = "boolean"
        else:
            value = HILO_UNIT_CONVERSION.get(
                self.hilo_value_type, camel_to_snake(self.hilo_value_type)
            )
        object.__setattr__(self, "attr", attr)
        object.__setattr__(self, "value_type", value)


class DeviceReading:
    def __init__(self, **kwargs: dict[str, Any]):
        kwargs["timeStamp"] = from_utc_timestamp(kwargs.pop("timeStampUTC", ""))  # type: ignore
        self.id = 0
        self.value: Union[int, bool] = 0
        self.device_id = 0
        self.device_attribute: DeviceAttribute
        self.__dict__.update({camel_to_snake(k): v for k, v in kwargs.items()})
        self.unit_of_measurement = (
            self.device_attribute.value_type
            if self.device_attribute.value_type != "boolean"
            else ""
        )

    def __repr__(self) -> str:
        return f"<Reading {self.device_attribute.attr} {self.value}{self.unit_of_measurement}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DeviceReading):
            return NotImplemented
        return self.device_attribute.attr == other.device_attribute.attr
