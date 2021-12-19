import asyncio
from datetime import datetime
from typing import Any, Union

from pyhilo import API
from pyhilo.const import DEVICE_REFRESH_TIME, HILO_DEVICE_TYPES, LOG
from pyhilo.device import DeviceReading, HiloDevice
from pyhilo.device.climate import Climate  # noqa
from pyhilo.device.light import Light  # noqa
from pyhilo.device.sensor import Sensor  # noqa
from pyhilo.util import from_utc_timestamp, time_diff
from pyhilo.websocket import WebsocketEvent


class Hilo:
    def __init__(self, api: API):
        self._api = api
        self.devices: list[HiloDevice] = []
        self.location_id: int = 0

    async def _async_websocket_on_connect(self) -> None:
        """Define a callback for connecting to the websocket."""
        LOG.info("Listening to websocket from test.py")

    def _on_websocket_event(self, event: WebsocketEvent) -> None:
        """Define a callback for receiving a websocket event."""
        if event.target == "Heartbeat":
            self._validate_heartbeat(event)
        elif event.target == "DevicesValuesReceived":
            self._parse_values_received(event.arguments[0])
        else:
            LOG.debug(f"New unhandled websocket event: {event}")

    def _parse_values_received(self, values: list[dict[str, Any]]) -> None:
        readings = []
        for val in values:
            val["device_attribute"] = self._api.dev_atts(val.pop("attribute"))
            val.pop("valueType")
            readings.append(DeviceReading(**val))
        self._map_readings_to_devices(readings)

    def _map_readings_to_devices(self, readings: list[DeviceReading]) -> None:
        for reading in readings:
            if device := self.find_device(reading.device_id):
                device.readings = [r for r in device.readings if r != reading] + [
                    reading
                ]
                device.last_update = datetime.now()
                LOG.debug(f"{device} Received {reading}")

    def _validate_heartbeat(self, event: WebsocketEvent) -> None:
        heartbeat_time = from_utc_timestamp(event.arguments[0])  # type: ignore
        LOG.debug(f"Heartbeat: {time_diff(heartbeat_time, event.timestamp)}")

    def find_device(self, id: int) -> HiloDevice:
        return next((d for d in self.devices if d.id == id), None)  # type: ignore

    @property
    def list_device_attributes(self) -> list[Union[int, dict[int, list[str]]]]:
        return [
            self.location_id,
            {d.id: d.hilo_attributes for d in self.devices if len(d.hilo_attributes)},
        ]

    async def update_devices(self) -> None:
        for device in await self._api.get_devices(self.location_id):
            device["location_id"] = self.location_id
            device_type = HILO_DEVICE_TYPES[device["type"]]
            klass = globals()[device_type]
            dev = self.find_device(device.get("id", 0)) or klass(self._api, **device)
            dev.update(**device)
            LOG.debug(f"Adding {klass} {dev}")
            if dev not in self.devices:
                self.devices.append(dev)

    async def async_subscribe_to_location(self) -> None:
        """Sends the json payload to receive updates from the location."""
        LOG.debug(f"Subscribing to location {self.location_id}")
        await self._api.websocket.async_invoke(
            [self.location_id], "SubscribeToLocation", 1
        )

    async def async_subscribe_to_attributes(self) -> None:
        """Sends the json payload to receive the device attributes."""
        await self._api.websocket.async_invoke(
            self.list_device_attributes, "SubscribeDevicesAttributes", 1
        )

    async def async_init(self) -> None:
        """Initialize the Hilo "manager" class."""
        LOG.info("Initialising after websocket is connected")
        loop = asyncio.get_event_loop()
        self.location_id = await self._api.get_location_id()
        await self.update_devices()
        self._api.websocket.add_connect_callback(self.async_subscribe_to_location)
        self._api.websocket.add_connect_callback(self.async_subscribe_to_attributes)
        self._api.websocket.add_event_callback(self._on_websocket_event)
        LOG.debug("Scheduling device refresh in {DEVICE_REFRESH_TIME}")
        loop.call_later(DEVICE_REFRESH_TIME, self.update_devices)
        task = asyncio.create_task(self._api.websocket.async_connect())
        LOG.debug(f"created task {task}")
        await asyncio.gather(task, return_exceptions=True)
