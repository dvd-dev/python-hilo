from pyhilo.device import DeviceAttribute


class GraphqlValueMapper: 
    def __init__(self, value):
        self.value = value

    def map_thermostat(self)-> list[DeviceAttribute]:
        return [
            DeviceAttribute(
                name="disconnected",
                value=self.value["disconnected"],
                unit="none",
                value_type="bool",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="unpaired",
                value=False,
                unit="none",
                value_type="bool",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="CurrentTemperature",
                value=self.value["mode"],
                value_type="string",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="TargetTemperature",
                value=self.value["battery"],
                unit="%",
                value_type="int",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="HeatDemand",
                value=self.value["low_battery"],
                value_type="bool",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="Heating",
                value=self.value["state"],
                value_type="string",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="Power",
                value=self.value["state"],
                value_type="string",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="GdState",
                value=self.value["state"],
                value_type="string",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="Version",
                value=self.value["state"],
                value_type="string",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="ZigbeeVersion",
                value=self.value["state"],
                value_type="string",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="Humidity",
                value=self.value["state"],
                value_type="string",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="ThermostatAllowedModes",
                value=self.value["state"],
                value_type="string",
                device_id=self.value["device_id"],
            ),
            DeviceAttribute(
                name="ThermostatMode",
                value=self.value["state"],
                value_type="string",
                device_id=self.value["device_id"],
            ),
        ]

