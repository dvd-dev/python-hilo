from datetime import datetime, timezone
from typing import Any, Dict

from pyhilo.device import DeviceReading


class GraphqlValueMapper:
    """
    A class to map GraphQL values to DeviceReading instances.
    """

    OnState = "on"

    def map_query_values(self, values: Dict[str, Any]) -> list[Dict[str, Any]]:
        readings: list[Dict[str, Any]] = []
        for device in values:
            if device.get("deviceType") is not None:
                reading = self._map_devices_values(device)
                readings.extend(reading)
        return readings

    def map_device_subscription_values(
        self, device: list[Dict[str, Any]]
    ) -> list[Dict[str, Any]]:
        readings: list[Dict[str, Any]] = []
        if device.get("deviceType") is not None:
            reading = self._map_devices_values(device)
            readings.extend(reading)
        return readings

    def map_location_subscription_values(
        self, values: Dict[str, Any]
    ) -> list[Dict[str, Any]]:
        readings: list[Dict[str, Any]] = []
        for device in values:
            if device.get("deviceType") is not None:
                reading = self._map_devices_values(device)
                readings.extend(reading)
        return readings

    def _map_devices_values(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes: list[Dict[str, Any]] = self._map_basic_device(device)
        match device["deviceType"].lower():
            case "tstat":
                attributes.extend(self._build_thermostat(device))
            case "cee":  # Water Heater
                attributes.extend(self._build_water_heater(device))
            case "ccr":  # ChargeController
                attributes.extend(self._build_charge_controller(device))
            case "heatingfloor":
                attributes.extend(self._build_floor_thermostat(device))
            case "lowvoltagetstat":
                attributes.extend(self._build_lowvoltage_thermostat(device))
            case "chargingpoint":
                attributes.extend(self._build_charging_point(device))
            case "meter":  # Smart Meter
                attributes.extend(self._build_smart_meter(device))
            case "hub":  # Gateway
                attributes.extend(self._build_gateway(device))
            case "colorbulb":
                attributes.extend(self._build_light(device))
            case "whitebulb":
                attributes.extend(self._build_light(device))
            case "dimmer":
                attributes.extend(self._build_dimmer(device))
            case "switch":
                attributes.extend(self._build_switch(device))
            case _:
                pass
        return attributes

    def _map_to_device_reading(
        self, attributes: list[Dict[str, Any]]
    ) -> list[DeviceReading]:
        return [DeviceReading(**attr) for attr in attributes]

    def _build_smart_meter(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = []
        if device.get("zigbeeChannel") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"], "ZigbeeChannel", device["zigBeeChannel"]
                )
            )
        attributes.append(
            self.build_attribute(
                device["hiloId"], "Disconnected", device["connectionStatus"] == 2
            ),
        )
        if device.get("power") is not None:
            attributes.append(self._map_power(device))
        return attributes

    def _build_gateway(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = []
        attributes.append(
            self.build_attribute(
                device["hiloId"], "LastStatusTime", device["lastConnectionTime"]
            )
        )
        attributes.append(
            self.build_attribute(
                device["hiloId"], "Version", device["controllerSoftwareVersion"]
            )
        )
        attributes.append(
            self.build_attribute(
                device["hiloId"], "Disconnected", device["connectionStatus"] == 2
            )
        )  # Offline
        attributes.append(
            self.build_attribute(
                device["hiloId"],
                "ZigbeePairingActivated",
                device["zigBeePairingModeEnhanced"],
            )
        )
        if device.get("zigBeeChannel") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"], "ZigbeeChannel", device["zigBeeChannel"]
                )
            )
        attributes.append(
            self.build_attribute(
                device["hiloId"],
                "WillBeConnectedToSmartMeter",
                device["willBeConnectedToSmartMeter"],
            )
        )
        attributes.append(
            self.build_attribute(
                device["hiloId"],
                "SmartMeterUnpaired",
                device["smartMeterPairingStatus"],
            )
        )
        return attributes

    def _build_thermostat(
        self, device: Dict[str, Any], withDefaultMinMaxTemp: bool = True
    ) -> list[Dict[str, Any]]:
        attributes = []

        if device.get("ambientTemperature") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "CurrentTemperature",
                    device["ambientTemperature"]["value"],
                )
            )

        if device.get("ambientTempSetpoint") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "TargetTemperature",
                    device["ambientTempSetpoint"]["value"],
                )
            )

        if device.get("heatDemand") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"], "HeatDemand", device["heatDemand"]
                )
            )
        attributes.append(
            self.build_attribute(device["hiloId"], "Version", device["version"])
        )
        attributes.append(
            self.build_attribute(
                device["hiloId"], "ZigbeeVersion", device["zigbeeVersion"]
            )
        )
        attributes.append(
            self.build_attribute(
                device["hiloId"], "Humidity", device.get("ambientHumidity") or 0
            )
        )
        if device.get("allowedModes") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"], "ThermostatAllowedModes", device["allowedModes"]
                )
            )

        if device.get("power") is not None:
            attributes.append(self._map_power(device))
        attributes.append(self._map_heating(device))
        attributes.append(
            self.build_attribute(
                device["hiloId"],
                "ThermostatMode",
                device.get("mode"),
            )
        )
        attributes.append(self._map_gd_state(device))

        if device.get("maxAmbientTempSetpoint") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "MaxTempSetpoint",
                    device["maxAmbientTempSetpoint"]["value"],
                )
            )
        if device.get("minAmbientTempSetpoint") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "MinTempSetpoint",
                    device["minAmbientTempSetpoint"]["value"],
                )
            )

        if device.get("maxAmbientTempSetpointLimit") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "MaxTempSetpointLimit",
                    device["maxAmbientTempSetpointLimit"]["value"],
                )
            )
        if device.get("minAmbientTempSetpointLimit") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "MinTempSetpointLimit",
                    device["minAmbientTempSetpointLimit"]["value"],
                )
            )
        return attributes

    def _build_floor_thermostat(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = self._build_thermostat(device)
        attributes.append(
            self.build_attribute(
                device["hiloId"],
                "FloorMode",
                device["floorMode"],
            )
        )
        if device.get("floorLimit") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"], "FloorLimit", device["floorLimit"]["value"]
                )
            )
        return attributes

    def _build_lowvoltage_thermostat(
        self, device: Dict[str, Any]
    ) -> list[Dict[str, Any]]:
        attributes = self._build_thermostat(device)
        if device.get("coolTempSetpoint") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "CoolTemperatureSet",
                    device["coolTempSetpoint"]["value"],
                )
            )
        if device.get("minAmbientCoolSetPoint") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "MinCoolSetpoint",
                    device["minAmbientCoolSetPoint"]["value"],
                )
            )
        if device.get("maxAmbientCoolSetPoint") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "MaxCoolSetpoint",
                    device["maxAmbientCoolSetPoint"]["value"],
                )
            )
        attributes.extend(
            [
                self.build_attribute(
                    device["hiloId"],
                    "Thermostat24VAllowedMode",
                    device["allowedModes"],
                ),
                self.build_attribute(
                    device["hiloId"],
                    "Thermostat24VAllowedFanMode",
                    device["fanAllowedModes"],
                ),
                self.build_attribute(
                    device["hiloId"],
                    "FanMode",
                    device["fanMode"],
                ),
                self.build_attribute(
                    device["hiloId"],
                    "Thermostat24VMode",
                    device["mode"],
                ),
                self.build_attribute(
                    device["hiloId"],
                    "CurrentState",
                    device["currentState"],
                ),
                self.build_attribute(
                    device["hiloId"], "FanSpeed", device.get("fanSpeed")
                ),
            ]
        )
        return attributes

    def _build_water_heater(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = self._build_charge_controller(device)
        attributes.append(
            self.build_attribute(
                device["hiloId"],
                "AbnormalTemperature",
                device.get("alerts") is not None
                and "30" in device["alerts"],  # AbnormalTemperature alert
            )
        )
        if device.get("probeTemp") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "CurrentTemperature",
                    device["probeTemp"]["value"],  # AbnormalTemperature alert
                )
            )
        attributes.append(self._map_heating(device))
        return attributes

    def _build_charge_controller(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = []
        if device.get("power") is not None:
            attributes.append(self._map_power(device))

        attributes.append(
            self.build_attribute(device["hiloId"], "Version", device["version"])
        )
        attributes.append(
            self.build_attribute(
                device["hiloId"], "ZigbeeVersion", device["zigbeeVersion"]
            )
        )
        attributes.append(self._map_gd_state(device))
        attributes.append(self._map_drms_state(device))
        if device.get("ccrAllowedModes") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"], "CcrAllowedModes", device["ccrAllowedModes"]
                )
            )
        if device.get("ccrMode") is not None:
            attributes.append(
                self.build_attribute(device["hiloId"], "CcrMode", device["ccrMode"])
            )
        attributes.append(
            self.build_attribute(
                device["hiloId"], "OnOff", device["state"].lower() == self.OnState
            )
        )
        return attributes

    def _build_charging_point(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = []
        status = device["status"]
        if status in (1, 0):  # is available (1) or OutOfService (0)
            attributes.append(self.build_attribute(device["hiloId"], "Power", 0))
        elif device.get("power") is not None:
            attributes.append((self._map_power(device)))

        attributes.append(self.build_attribute(device["hiloId"], "Status", status))
        return attributes

    def _build_switch(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = []
        if device.get("power") is not None:
            attributes.append(self._map_power(device))
        attributes.append(
            self.build_attribute(
                device["hiloId"], "Status", device["state"].lower() == self.OnState
            )
        )
        attributes.append(
            self.build_attribute(
                device["hiloId"], "OnOff", device["state"].lower() == self.OnState
            )
        )
        return attributes

    def _build_dimmer(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = []
        if device.get("power") is not None:
            attributes.append(self._map_power(device))
        if device.get("level") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"], "Intensity", device["level"] / 100
                )
            )
        attributes.append(
            self.build_attribute(
                device["hiloId"], "OnOff", device["state"].lower() == self.OnState
            )
        )
        return attributes

    def _build_light(self, device: Dict[str, Any]) -> list[Dict[str, Any]]:
        attributes = []
        if device.get("colorTemperature") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"],
                    "ColorTemperature",
                    device["colorTemperature"],
                )
            )
        if device.get("level") is not None:
            attributes.append(
                self.build_attribute(
                    device["hiloId"], "Intensity", device["level"] / 100
                )
            )
        if device.get("lightType").lower() == "color":
            attributes.append(
                self.build_attribute(device["hiloId"], "Hue", device.get("hue") or 0)
            )
            attributes.append(
                self.build_attribute(
                    device["hiloId"], "Saturation", device.get("saturation") or 0
                )
            )
        attributes.append(
            self.build_attribute(
                device["hiloId"], "OnOff", device["state"].lower() == self.OnState
            )
        )
        return attributes

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

    def _map_drms_state(self, device: Dict[str, Any]) -> Dict[str, Any]:
        return self.build_attribute(
            device["hiloId"], "DrmsState", device["gDState"] == "Active"
        )

    def _map_heating(self, device: Dict[str, Any]) -> Dict[str, Any]:
        power = device.get("power")
        if (
            power is not None
            and device["power"]["value"] is not None
            and device["power"]["value"] > 0
        ):
            return self.build_attribute(device["hiloId"], "Heating", 1)

        return self.build_attribute(device["hiloId"], "Heating", 0)

    def _map_power(self, device: Dict[str, Any]) -> Dict[str, Any]:
        value = device["power"]["value"] if device["power"]["value"] is not None else 0
        return self.build_attribute(
            device["hiloId"],
            "Power",
            self._power_kw_to_w(value, device["power"]["kind"]),
        )

    def _power_kw_to_w(self, power: float, power_kind: str) -> float:
        if power_kind.lower() == "kilowatt":
            return power * 1000

        return power

    def build_attribute(
        self, hilo_id: str, device_attribute: str, value: Any
    ) -> Dict[str, Any]:
        return {
            "hilo_id": hilo_id,
            "attribute": device_attribute,
            "valueType": "null",
            "value": value,
            "timeStampUTC": datetime.now(timezone.utc).isoformat(),
        }
