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
        """Initialize."""
        self._api = api
        self.devices: list[HiloDevice] = []
        self.location_id: int = 0
        self.location_hilo_id: str = ""

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
        """Places value received in a dict while removing null attributes,
        this returns values to be mapped to devices.
        """
        readings = []
        for val in values:
            val["device_attribute"] = self._api.dev_atts(
                val.pop("attribute"), val.pop("valueType", "null")
            )
            readings.append(DeviceReading(**val))
        return self._map_readings_to_devices(readings)

    def _map_readings_to_devices(
        self, readings: list[DeviceReading]
    ) -> list[HiloDevice]:
        """Uses the dict from parse_values_received to map the values to devices."""
        updated_devices = []
        for reading in readings:
            device_identifier: Union[int, str] = reading.device_id
            if device_identifier == 0:
                device_identifier = reading.hilo_id
            if device := self.find_device(device_identifier):
                device.update_readings(reading)
                LOG.debug("%s Received %s", device, reading)
                if device not in updated_devices:
                    updated_devices.append(device)
            else:
                LOG.warning(
                    f"Unable to find device {reading.device_id} for reading {reading}"
                )
        return updated_devices

    def find_device(self, device_identifier: int | str) -> HiloDevice | None:
        """Makes sure the devices received have an identifier, this means some need to be hardcoded
        like the unknown power meter.
        """
        if isinstance(device_identifier, int):
            return next((d for d in self.devices if d.id == device_identifier), None)
        return next((d for d in self.devices if d.hilo_id == device_identifier), None)

    def generate_device(self, device: dict) -> HiloDevice:
        """Generate all devices from the list received."""
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
            LOG.debug("Generating device %s", raw_device)
            dev = self.generate_device(raw_device)
            generated_devices.append(dev)
            if dev not in self.devices:
                self.devices.append(dev)
        for device in self.devices:
            if device not in generated_devices:
                LOG.debug("Device unpaired %s", device)
                # Don't do anything with unpaired device for now.
                # self.devices.remove(device)

    async def update_devicelist_from_signalr(
        self, values: list[dict[str, Any]]
    ) -> list[HiloDevice]:
        # ic-dev21 not sure if this is dead code?
        new_devices = []
        for raw_device in values:
            LOG.debug("Generating device %s", raw_device)
            dev = self.generate_device(raw_device)
            if dev not in self.devices:
                self.devices.append(dev)
                new_devices.append(dev)

        return new_devices

    async def async_init(self) -> None:
        """Initialize the Hilo "manager" class."""
        LOG.info("Initialising after websocket is connected")
        location_ids = await self._api.get_location_ids()
        self.location_id = location_ids[0]
        self.location_hilo_id = location_ids[1]
        await self.update()
