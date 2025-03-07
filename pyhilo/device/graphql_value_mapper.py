from typing import Any, Dict, Generator, Union
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
        attributes: list[Dict[str, Any]] = self._map_basic_device(device)
        match device["deviceType"]:
            case "Tstat":
                attributes.extend(self._build_thermostat(device))
                return self._map_to_device_reading(attributes)
            # case "CCE":  # Water Heater
            #     attributes.extend(self._build_water_heater(device))
            #     return self._map_to_device_reading(attributes)
            # case "CCR":  # ChargeController
            #     attributes.extend(self._build_charge_controller(device))
            #     return self._map_to_device_reading(attributes)
            # case "HeatingFloor":
            # case "LowVoltageTstat":
            # case "ChargingPoint":
            # case "Meter":
            # case "Hub": # Gateway
            # case "ColorBulb":
            # case "Dimmer":
            # case "Switch":
            case _:
                # Add the default logic here if needed
                pass

    def _map_to_device_reading(
        self, attributes: list[Dict[str, Any]]
    ) -> list[DeviceReading]:
        return [DeviceReading(**attr) for attr in attributes]

    def _build_thermostat(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            self.build_attribute(
                device["hiloId"],
                "CurrentTemperature",
                device["ambientTemperature"]["value"],
            ),
            self.build_attribute(
                device["hiloId"],
                "TargetTemperature",
                device["ambientTempSetpoint"]["value"],
            ),
            self.build_attribute(device["hiloId"], "HeatDemand", device["heatDemand"]),
            self.build_attribute(
                device["hiloId"],
                "Heating",
                device["power"]["value"] != "0" or device["power"]["value"] is not None,
            ),
            self.build_attribute(device["hiloId"], "Power", device["power"]["value"]),
            self.build_attribute(device["hiloId"], "Version", device["version"]),
            self.build_attribute(
                device["hiloId"], "ZigbeeVersion", device["zigbeeVersion"]
            ),
            self.build_attribute(
                device["hiloId"], "Humidity", device["ambientHumidity"]
            ),
            self.build_attribute(
                device["hiloId"], "ThermostatAllowedModes", device["allowedModes"]
            ),
            self.build_attribute(device["hiloId"], "ThermostatMode", device["mode"]),
            self._map_gd_state(device),
        ]

    def _build_water_heater(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = self._build_charge_controller(device)
        attributes.extend(
            [
                self.build_attribute(
                    device["hiloId"], "Power", device["power"]["value"]
                ),
                self.build_attribute(
                    device["hiloId"], "GdState", device["gDState"] == "Active"
                ),
                self.build_attribute(device["hiloId"], "Version", device["version"]),
                self.build_attribute(
                    device["hiloId"], "ZigbeeVersion", device["zigbeeVersion"]
                ),
                self.build_attribute(
                    device["hiloId"], "Alerts", device["ambientHumidity"]
                ),
                self.build_attribute(
                    device["hiloId"], "ThermostatAllowedModes", device["allowedModes"]
                ),
                self.build_attribute(
                    device["hiloId"], "ThermostatMode", device["mode"]
                ),
                self.build_attribute(
                    device["hiloId"],
                    "Disconnected",
                    device["connectionStatus"] == "Disconnected",
                ),
                self.build_attribute(device["hiloId"], "Unpaired", False),
            ]
        )

    def _build_charge_controller(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            self.build_attribute(device["hiloId"], "Power", device["power"]["value"]),
            self.build_attribute(device["hiloId"], "Version", device["version"]),
            self.build_attribute(
                device["hiloId"], "ZigbeeVersion", device["zigbeeVersion"]
            ),
            self._map_gd_state(device),
            self._map_drms_state(device),
        ]

    def _map_basic_device(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            self.build_attribute(device["hiloId"], "Unpaired", False),
            self.build_attribute(
                device["hiloId"],
                "Disconnected",
                device["connectionStatus"] == "Disconnected",
            ),
        ]

    def _map_gd_state(self, device: Dict[str, Any]) -> Dict[str, Any]:
        return self.build_attribute(
            device["hiloId"], "GdState", device["gDState"] == "Active"
        )

    # TODO - AA Map selon le GD STATE
    def _map_drms_state(self, device: Dict[str, Any]) -> Dict[str, Any]:
        return (
            self.build_attribute(
                device["hiloId"], "DrmsState", device["gDState"] == "Active"
            ),
        )

    def build_attribute(
        self, hilo_id: str, device_attribute: str, value: Any
    ) -> dict[str, Any]:
        return {
            "hilo_id": hilo_id,
            "device_attribute": self._api.dev_atts(device_attribute, "null"),
            "value": value,
            "timeStampUTC": datetime.now(timezone.utc).isoformat(),
        }
