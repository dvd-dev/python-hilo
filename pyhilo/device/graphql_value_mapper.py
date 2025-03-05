from typing import Any, Dict, Union
from pyhilo.device import DeviceReading
from datetime import datetime, timezone


class GraphqlValueMapper:
    """
    A class to map GraphQL values to DeviceReading instances.
    """

    def __init__(self, api: Any):
        self._api = api

    def map_values(self, values: Dict[str, Any]) -> list[DeviceReading]:
        devices_values: list[any] = values["getLocation"]["devices"]
        readings: list[DeviceReading] = []
        for device in devices_values:
            if device.get("deviceType") is not None:
                reading = self._map_devices_values(device)
                readings.extend(reading)
        return readings

    def _map_devices_values(self, device: Dict[str, Any]) -> list[DeviceReading]:
        match device["deviceType"]:
            case "Tstat":
                attributes = self._map_thermostats(device)
                return self._map_to_device_reading(attributes)
            case _:
                # Add the default logic here if needed
                pass

    def _map_to_device_reading(
        self, attributes: list[Dict[str, Any]]
    ) -> list[DeviceReading]:
        return [DeviceReading(**attr) for attr in attributes]

    def _map_thermostats(self, thermostat: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("Disconnected", "null"),
                "value": thermostat["connectionStatus"] == "Disconnected",
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("Unpaired", "null"),
                "value": False,
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("CurrentTemperature", "null"),
                "value": thermostat["ambientTemperature"]["value"],
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("TargetTemperature", "null"),
                "value": thermostat["ambientTempSetpoint"]["value"],
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("HeatDemand", "null"),
                "value": thermostat["heatDemand"],
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("Heating", "null"),
                "value": thermostat["power"]["value"] != "0"
                or thermostat["power"]["value"] is not None,
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("Power", "null"),
                "value": thermostat["power"]["value"],
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("GdState", "null"),
                "value": thermostat["gDState"] == "Active",
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("Version", "null"),
                "value": thermostat["version"],
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("ZigbeeVersion", "null"),
                "value": thermostat["zigbeeVersion"],
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("Humidity", "null"),
                "value": thermostat["ambientHumidity"],
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts(
                    "ThermostatAllowedModes", "null"
                ),
                "value": thermostat["allowedModes"],
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
            {
                "hilo_id": thermostat["hiloId"],
                "device_attribute": self._api.dev_atts("ThermostatMode", "null"),
                "value": thermostat["mode"],
                "timeStampUTC": datetime.now(timezone.utc).isoformat(),
            },
        ]
