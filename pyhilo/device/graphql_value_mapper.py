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
            case "CCE":  # Water Heater
                 attributes.extend(self._build_water_heater(device))
            case "CCR":  # ChargeController
                attributes.extend(self._build_charge_controller(device))
            case "HeatingFloor":
                 attributes.extend(self._build_floor_thermostat(device))
            # case "LowVoltageTstat":
            # case "ChargingPoint":
            case "Meter":
                attributes.extend(self._build_smart_meter(device))
            case "Hub": # Gateway
                attributes.extend(self._build_gateway(device))
            case "ColorBulb":
                attributes.extend(self._build_light(device))
            case "Dimmer":
                attributes.extend(self._build_dimmer(device))
            case "Switch":
                attributes.extend(self._build_switch(device))
            case _:
                pass
        return self._map_to_device_reading(attributes)

    def _map_to_device_reading(
        self, attributes: list[Dict[str, Any]]
    ) -> list[DeviceReading]:
        return [DeviceReading(**attr) for attr in attributes]

    def _build_smart_meter(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            self.build_attribute(device["hiloId"], "LastUpdate", device["LastUpdate"]),
            self.build_attribute(device["hiloId"], "ZigbeeChannel", device["zigbeeChannel"]),
            self.build_attribute(device["hiloId"], "Disconnected", device["IsDisconnected"]), #??? gateway value??
            self._map_power(device),
        ]

    def _build_gateway(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            self.build_attribute(device["hiloId"], "LastStatusTime", device["LastConnectionTime"]),
            self.build_attribute(device["hiloId"], "Version", device["controllerSoftwareVersion"]),
            self.build_attribute(device["hiloId"], "Disconnected", device["connectionStatus"] == 2), # Offline
            self.build_attribute(device["hiloId"], "ZigbeePairingActivated", device["zigBeePairingMode"]),
            self.build_attribute(device["hiloId"], "ZigbeeChannel", device["zigbeeChannel"]),
            self.build_attribute(device["hiloId"], "WillBeConnectedToSmartMeter", device["willBeConnectedToSmartMeter"]),
            self.build_attribute(device["hiloId"], "SmartMeterUnpaired", device["smartMeterPairingStatus"]),
        ]

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
            self._map_power(device),
            self._map_heating(device),
            self.build_attribute(device["hiloId"], "ThermostatMode", device["mode"]),
            self._map_gd_state(device),
        ]

    def _build_floor_thermostat(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = self._build_thermostat(device)
        return attributes.extend(
            self.build_attribute(
                device["hiloId"], "FloorMode", self._map_to_floor_mode(device["floorMode"])
            ),
            self.build_attribute(
                device["hiloId"], "FloorLimit", device["FloorLimit"]["value"]
            ),
        )

    def _build_water_heater(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = self._build_charge_controller(device)
        return attributes.extend(
            [
                self.build_attribute(
                    device["hiloId"], "AbnormalTemperature", device["alerts"].contains("30") # AbnormalTemperature alert
                ),
                 self.build_attribute(
                    device["hiloId"], "CurrentTemperature", device["ProbeTemperature"]["value"]# AbnormalTemperature alert
                ),
                self._map_heating(device),
            ]
        )

    def _build_charge_controller(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            self._map_power(device),
            self.build_attribute(device["hiloId"], "Version", device["version"]),
            self.build_attribute(
                device["hiloId"], "ZigbeeVersion", device["zigbeeVersion"]
            ),
            self._map_gd_state(device),
            self._map_drms_state(device),
            self.build_attribute(
                    device["hiloId"], "CcrAllowedModes", device["ccrAllowedModes"]
            ),
            self.build_attribute(
                    device["hiloId"], "CcrMode", device["ccrMode"]
            ),
        ]

    def _build_switch(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            self._map_power(device),
            self.build_attribute(device["hiloId"], "Status", device["State"]),
            self.build_attribute(device["hiloId"], "OnOff", device["State"]),
        ]

    def _build_dimmer(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            self._map_power(device),
            self.build_attribute(device["hiloId"], "Intensity", device["Level"]["value"]/100),
            self.build_attribute(device["hiloId"], "OnOff", device["State"]),
        ]

    def _build_light(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        return [
            self.build_attribute(device["hiloId"], "ColorTemperature", device["ColorTemperature"]["value"]),
            self.build_attribute(device["hiloId"], "Intensity", device["Level"]["value"]/100),
            self.build_attribute(device["hiloId"], "OnOff", device["State"]),
            self.build_attribute(device["hiloId"], "Hue", device.get("Hue") or 0),
            self.build_attribute(device["hiloId"], "Saturation", device.get("Saturation") or 0),
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

    def _map_heating(self, device: Dict[str, Any]) -> Dict[str, Any]:
       return self.build_attribute(
                device["hiloId"],
                "Heating",
                device["power"]["value"] != "0" or device["power"]["value"] is not None,
            ),

    def _map_power(self, device: Dict[str, Any]) -> Dict[str, Any]:
        return self.build_attribute( device["hiloId"],"Power", self._powerKwToW(device["power"]["value"], device["power"]["kind"]))

    def _powerKwToW(self, power: float, power_kind: int) -> float:
        if power_kind == 12: # PowerKind.KW
            return power * 1000

        return power

    def build_attribute(
        self, hilo_id: str, device_attribute: str, value: Any
    ) -> dict[str, Any]:
        return {
            "hilo_id": hilo_id,
            "device_attribute": self._api.dev_atts(device_attribute, "null"),
            "value": value,
            "timeStampUTC": datetime.now(timezone.utc).isoformat(),
        }

    def _map_to_floor_mode( self, floor_mode: int) -> str:
        match floor_mode:
            case 0:
                return "Ambient"
            case 1:
                return "Floor"
            case 2:
                return "Hybrid"
