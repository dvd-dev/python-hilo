from typing import Any, Union

from pyhilo import API
from pyhilo.const import HILO_DEVICE_TYPES, LOG
from pyhilo.device import DeviceReading, HiloDevice
from pyhilo.device.climate import Climate  # noqa
from pyhilo.device.light import Light  # noqa
from pyhilo.device.sensor import Sensor  # noqa
from pyhilo.device.switch import Switch  # noqa


class Devices:
    def __init__(self, api: API):
        self._api = api
        self.devices: list[HiloDevice] = []
        self.location_id: int = 0

    @property
    def all(self) -> list[HiloDevice]:
        return self.devices

    @property
    def attributes_list(self) -> list[Union[int, dict[int, list[str]]]]:
        """This is sent to websocket to subscribe to the device attributes updates

        :return: Dict of devices (key) with their attributes.
        :rtype: list
        """
        return [
            self.location_id,
            {
                d.id: d.hilo_attributes
                for d in self.devices
                if d.id > 1 and len(d.hilo_attributes)
            },
        ]

    def parse_values_received(self, values: list[dict[str, Any]]) -> list[HiloDevice]:
        readings = []
        for val in values:
            val["device_attribute"] = self._api.dev_atts(
                val.pop("attribute"), val.pop("valueType", None)
            )
            readings.append(DeviceReading(**val))
        return self._map_readings_to_devices(readings)

    def _map_readings_to_devices(
        self, readings: list[DeviceReading]
    ) -> list[HiloDevice]:
        updated_devices = []
        for reading in readings:
            if device := self.find_device(reading.device_id):
                device.update_readings(reading)
                LOG.debug(f"{device} Received {reading}")
                if device not in updated_devices:
                    updated_devices.append(device)
            else:
                LOG.warning(
                    f"Unable to find device {reading.device_id} for reading {reading}"
                )
        return updated_devices

    def find_device(self, id: int) -> HiloDevice:
        return next((d for d in self.devices if d.id == id), None)  # type: ignore

    def generate_device(self, device: dict) -> HiloDevice:
        device["location_id"] = self.location_id
        if dev := self.find_device(device["id"]):
            dev.update(**device)
            return dev
        dev = HiloDevice(self._api, **device)
        try:
            device_type = HILO_DEVICE_TYPES[dev.type]
        except KeyError:
            LOG.warning(f"Unknown device type {dev.type}, adding as Sensor")
            device_type = "Sensor"
        dev.__class__ = globals()[device_type]
        return dev

    async def update(self) -> None:
        fresh_devices = await self._api.get_devices(self.location_id)
        generated_devices = []
        for raw_device in fresh_devices:
            LOG.debug(f"Generating device {raw_device}")
            dev = self.generate_device(raw_device)
            generated_devices.append(dev)
            if dev not in self.devices:
                self.devices.append(dev)
        for device in self.devices:
            if device not in generated_devices:
                LOG.debug(f"Device unpaired {device}")
                # Don't do anything with unpaired device for now.
                # self.devices.remove(device)

    async def update_gateway(self) -> None:
        gateway = await self._api.get_gateway(self.location_id)
        LOG.debug(f"Generating device (gateway) {gateway}")
        self.generate_device(gateway)

    async def async_init(self) -> None:
        """Initialize the Hilo "manager" class."""
        LOG.info("Initialising after websocket is connected")
        self.location_id = await self._api.get_location_id()
        await self.update()
