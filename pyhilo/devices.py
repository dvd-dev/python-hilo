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
            device = self.find_device(device_identifier)
            # If device_id was 0 and hilo_id lookup failed, this is likely
            # a gateway reading that arrives before GatewayValuesReceived
            # assigns the real ID. Fall back to the gateway device.
            if device is None and reading.device_id == 0:
                device = next((d for d in self.devices if d.type == "Gateway"), None)
            if device:
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
            LOG.warning("Unknown device type %s, adding as Sensor", dev.type)
            device_type = "Sensor"
        dev.__class__ = globals()[device_type]
        return dev

    async def update(self) -> None:
        """Update device list from websocket cache + gateway from REST."""
        # Get devices from websocket cache (already populated by DeviceListInitialValuesReceived)
        cached_devices = self._api.get_device_cache(self.location_id)
        generated_devices = []
        for raw_device in cached_devices:
            LOG.debug("Generating device %s", raw_device)
            dev = self.generate_device(raw_device)
            generated_devices.append(dev)
            if dev not in self.devices:
                self.devices.append(dev)

        # Append gateway from REST API (still available)
        try:
            gw = await self._api.get_gateway(self.location_id)
            LOG.debug("Generating gateway device %s", gw)
            gw_dev = self.generate_device(gw)
            generated_devices.append(gw_dev)
            if gw_dev not in self.devices:
                self.devices.append(gw_dev)
        except Exception as err:
            LOG.error("Failed to get gateway: %s", err)

        # Now add devices from external sources (e.g. unknown source tracker)
        for callback in self._api._get_device_callbacks:
            try:
                cb_device = callback()
                dev = self.generate_device(cb_device)
                generated_devices.append(dev)
                if dev not in self.devices:
                    self.devices.append(dev)
            except Exception as err:
                LOG.error("Failed to generate callback device: %s", err)

        for device in self.devices:
            if device not in generated_devices:
                LOG.debug("Device unpaired %s", device)
                # Don't do anything with unpaired device for now.

    async def update_devicelist_from_signalr(
        self, values: list[dict[str, Any]]
    ) -> list[HiloDevice]:
        """Process device list received from SignalR websocket.

        This is called when DeviceListInitialValuesReceived arrives.
        It populates the API device cache and generates HiloDevice objects.
        """
        # Populate the API cache so future update() calls use this data
        self._api.set_device_cache(values)

        new_devices = []
        for raw_device in self._api.get_device_cache(self.location_id):
            LOG.debug("Generating device from SignalR %s", raw_device)
            dev = self.generate_device(raw_device)
            if dev not in self.devices:
                self.devices.append(dev)
                new_devices.append(dev)

        return new_devices

    async def add_device_from_signalr(
        self, values: list[dict[str, Any]]
    ) -> list[HiloDevice]:
        """Process individual device additions from SignalR websocket.

        This is called when DeviceAdded arrives. It appends to the existing
        cache rather than replacing it.
        """
        self._api.add_to_device_cache(values)

        new_devices = []
        for raw_device in self._api.get_device_cache(self.location_id):
            LOG.debug("Generating added device from SignalR %s", raw_device)
            dev = self.generate_device(raw_device)
            if dev not in self.devices:
                self.devices.append(dev)
                new_devices.append(dev)

        return new_devices

    async def async_init(self) -> None:
        """Initialize the Hilo "manager" class.

        Gets location IDs from REST API, then waits for the websocket
        to deliver the device list via DeviceListInitialValuesReceived.
        The gateway is appended from REST.
        """
        LOG.info("Initialising: getting location IDs")
        location_ids = await self._api.get_location_ids()
        self.location_id = location_ids[0]
        self.location_hilo_id = location_ids[1]
        # Device list will be populated when DeviceListInitialValuesReceived
        # arrives on the websocket. The hilo integration's async_init will
        # call wait_for_device_cache() and then update() after subscribing.
