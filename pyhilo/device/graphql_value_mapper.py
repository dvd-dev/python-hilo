from typing import Any, Dict
from pyhilo.device import DeviceAttribute, DeviceReading


class GraphqlValueMapper:
    """
    A class to map GraphQL values to DeviceReading instances.
    """

    def map_values(self, values: Dict[str, Any]) -> list[DeviceReading]:
        devices_values: list[any] = values["getLocation"]["devices"]
        readings: list[DeviceReading] = []
        for device in devices_values:
            if device.get("deviceType") is not None:
                attributes = self._map_devices_values(device)
                reading = DeviceReading(hilo_id=device["hiloId"], attributes=attributes)
                readings.append(reading)
        return readings

    def _map_devices_values(self, device: Dict[str, Any]) -> list[DeviceAttribute]:
        match device["deviceType"]:
            case "Tstat":
                return []  # self._map_thermostats(device)
            case _:
                # Add the default logic here if needed
                pass

    # TODO Abi: Figurer comment bien faire le mapping
    # def _map_thermostats(self, thermostat: Dict[str, Any]) -> list[DeviceAttribute]:
    #     return [
    #         DeviceAttribute(
    #             hilo_attribute="Disconnected",
    #             # TODO mettre dans des constantes
    #             attr=thermostat["connectionStatus"] == "Disconnected",
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="Unpaired",
    #             attr=False,
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="CurrentTemperature",
    #             attr=thermostat["ambientTemperature"]["value"],
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="TargetTemperature",
    #             attr=thermostat["ambientTempSetpoint"]["value"],
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="HeatDemand",
    #             attr=thermostat["heatDemand"],
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="Heating",
    #             attr=thermostat["power"]["value"] != "0"
    #             or thermostat["power"]["value"] is not None,
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="Power",
    #             attr=thermostat["power"]["value"],
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="GdState",
    #             attr=thermostat["gdState"] == "Active",
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="Version",
    #             attr=thermostat["version"],
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="ZigbeeVersion",
    #             attr=thermostat["zigbeeVersion"],
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="Humidity",
    #             attr=thermostat["ambientHumidity"],
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="ThermostatAllowedModes",
    #             attr=thermostat["allowedModes"],
    #         ),
    #         DeviceAttribute(
    #             hilo_attribute="ThermostatMode",
    #             attr=thermostat["mode"],
    #         ),
    #     ]
