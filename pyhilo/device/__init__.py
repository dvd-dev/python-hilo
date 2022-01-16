"""Define devices"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Union, cast

from pyhilo.const import (
    HILO_DEVICE_ATTRIBUTES,
    HILO_LIST_ATTRIBUTES,
    HILO_PROVIDERS,
    HILO_READING_TYPES,
    HILO_UNIT_CONVERSION,
    JASCO_MODELS,
    JASCO_OUTLETS,
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
        self.model: Union[str, None] = None
        self.manufacturer: Union[str, None] = None
        self.supported_attributes: list[DeviceAttribute] = []
        self.settable_attributes: list[DeviceAttribute] = []
        self.readings: list[DeviceReading] = []
        self.update(**kwargs)

    def update(self, **kwargs: dict[str, Union[str, int]]) -> None:
        # TODO(dvd): This has to be re-written, this is not dynamic at all.
        if self._api.log_traces:
            LOG.debug(f"[TRACE] Adding device {kwargs}")
        for orig_att, val in kwargs.items():
            att = camel_to_snake(orig_att)
            if att not in HILO_DEVICE_ATTRIBUTES:
                LOG.warning(f"Unknown device attribute {att}: {val}")
                continue
            elif att in HILO_LIST_ATTRIBUTES:
                # This is where we generated the supported_attributes and settable_attributes
                # list using the DeviceAttribute object.
                new_val: list[DeviceAttribute] = [
                    DeviceAttribute(k, HILO_READING_TYPES.get(k, ""))
                    for k in map(str.strip, val.split(","))  # type: ignore
                    if k and k != "None"
                ]
                if len(new_val) == 0:
                    # Some sensors like the OneLink FirstAlert don't have any attributes
                    # but they have a "Disconnected" attribute even though it doesn't show
                    # up in supported_attributes.
                    new_val.append(DeviceAttribute("Disconnected", "null"))
            elif att == "provider":
                att = "manufacturer"
                new_val = HILO_PROVIDERS.get(int(val), f"Unknown ({val})")  # type: ignore
            else:
                if att == "serial":
                    att = "identifier"
                elif att == "model_number":
                    att = "model"
                new_val = val  # type: ignore
            setattr(self, att, new_val)
        if self.model:
            self.model = self.model.replace("Model_", "")
        elif self.type == "Thermostat":
            self.model = "EQ000016"
        if self.manufacturer == "Hilo" and self.model in JASCO_MODELS:
            self.manufacturer = "Jasco Enbrighten"
            if self.model in JASCO_OUTLETS:
                self.type = "Outlet"
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
        reading = next(
            (r for r in self.readings if r.device_attribute == attribute), None
        )
        return reading

    def has_attribute(self, attr: str) -> bool:
        return next((True for k in self.supported_attributes if k.attr == attr), False)

    def get_value(
        self, attribute: str, default: Union[str, int, float, None] = None
    ) -> Any:
        attr = self.get_attribute(attribute)
        return attr.value if attr else default

    @property
    def hilo_attributes(self) -> list[str]:
        return [
            k.hilo_attribute
            for k in self.supported_attributes
            if k.hilo_attribute != "Humidity"
        ]

    @property
    def attributes(self) -> list[str]:
        return [
            cast(str, k.attr) for k in self.supported_attributes if k.attr != "Humidity"
        ]

    @property
    def is_on(self) -> bool:
        return cast(bool, self.get_value("is_on"))

    @property
    def available(self) -> bool:
        return not self.get_value("disconnected") or False

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
        self.value: Union[int, bool, str] = 0
        self.device_id = 0
        self.device_attribute: DeviceAttribute
        self.__dict__.update({camel_to_snake(k): v for k, v in kwargs.items()})
        self.unit_of_measurement = (
            self.device_attribute.value_type
            if self.device_attribute and self.device_attribute.value_type != "boolean"
            else ""
        )
        if not self.device_attribute:
            LOG.warning(f"Received invalid reading for {self.device_id}: {kwargs}")

    def __repr__(self) -> str:
        return f"<Reading {self.device_attribute.attr} {self.value}{self.unit_of_measurement}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DeviceReading):
            return NotImplemented
        return self.device_attribute.attr == other.device_attribute.attr
