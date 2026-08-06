"""Climate object."""

from __future__ import annotations

from typing import Any, cast

from pyhilo import API
from pyhilo.const import LOG, STATE_UNKNOWN
from pyhilo.device import HiloDevice

# Attributes reported only by low voltage (24 V) thermostats. Thermostat24VMode
# is emitted solely by GraphqlValueMapper._build_lowvoltage_thermostat(), which
# makes its presence an exact discriminator.
LOW_VOLTAGE_MODE = "thermostat24_v_mode"
LOW_VOLTAGE_ALLOWED_MODES = "thermostat24_v_allowed_mode"
LOW_VOLTAGE_ALLOWED_FAN_MODES = "thermostat24_v_allowed_fan_mode"


def as_list(value: Any) -> list[str]:
    """Return a list of strings from a Hilo list attribute.

    Hilo sends those either as a real list or as a comma separated string
    depending on the transport, so accept both.
    """
    if value is None or value in ("", STATE_UNKNOWN):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(",") if v.strip()]


class Climate(HiloDevice):
    """
    Represents a climate device within the Hilo ecosystem.

    This class provides methods to interact with and control climate-related
    devices such as thermostats.
    """

    def __init__(
        self, api: API, **kwargs: dict[str, str | int | dict[Any, Any]]
    ) -> None:
        """Initialize the Climate object.

        Args:
            api: The Hilo API instance.
            **kwargs: Keyword arguments containing device data.
        """
        super().__init__(api, **kwargs)
        LOG.debug("Setting up Climate device: %s", self.name)

    @property
    def current_temperature(self) -> float:
        """
        Gets the current temperature reported by the device.

        Returns:
            float: The current temperature.
        """
        return cast(float, self.get_value("current_temperature", 0))

    @property
    def target_temperature(self) -> float:
        """
        Gets the target temperature set for the device.

        Returns:
            float: The target temperature.
        """
        return cast(float, self.get_value("target_temperature", 0))

    @property
    def max_temp(self) -> float:
        """
        Gets the maximum temperature setpoint allowed for the device.

        Returns:
            float: The maximum temperature. Defaults to 36.0 if not defined.
        """
        value = self.get_value("max_temp_setpoint", 0)

        if value is None or value == 0:
            return 36.0
        return float(value)

    @property
    def min_temp(self) -> float:
        """
        Gets the minimum temperature setpoint allowed for the device.

        Returns:
            float: The minimum temperature. Defaults to 5.0 if not defined.
        """
        value = self.get_value("min_temp_setpoint", 0)

        if value is None or value == 0:
            return 5.0
        return float(value)

    @property
    def hvac_action(self) -> str:
        """
        Gets the current HVAC action of the device.

        Returns:
            str: 'heating' if heating is active, 'idle' otherwise.
        """
        attr = self.get_value("heating", 0)
        return "heating" if attr > 0 else "idle"

    async def async_set_temperature(self, temperature: float) -> None:
        """
        Sets the target temperature of the device.

        Args:
            temperature: The desired target temperature.
        """
        if self.is_low_voltage:
            await self.async_set_low_voltage_state(target_temperature=temperature)
            return
        if temperature != self.target_temperature:
            LOG.info("%s Setting temperature to %s", self._tag, temperature)
            await self.set_attribute("target_temperature", str(temperature))

    def _optional_float(self, attribute: str) -> float | None:
        """Return a numeric reading, or None when absent or unusable."""
        value = self.get_value(attribute, None)
        if value is None or value == STATE_UNKNOWN:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _optional_str(self, attribute: str) -> str | None:
        """Return a textual reading, or None when absent or unusable."""
        value = self.get_value(attribute, None)
        if value is None or value == STATE_UNKNOWN:
            return None
        return str(value)

    @property
    def is_low_voltage(self) -> bool:
        """Whether this is a low voltage (24 V) thermostat.

        Baseboard thermostats report none of the 24 V attributes and therefore
        keep their heat-only behaviour.
        """
        return self.low_voltage_mode is not None

    @property
    def low_voltage_mode(self) -> str | None:
        """Operating mode reported by a 24 V thermostat, in Hilo's vocabulary."""
        return self._optional_str(LOW_VOLTAGE_MODE)

    @property
    def allowed_modes(self) -> list[str]:
        """Mode vocabulary advertised by a 24 V thermostat."""
        return as_list(self.get_value(LOW_VOLTAGE_ALLOWED_MODES, None))

    @property
    def fan_mode(self) -> str | None:
        """Current fan mode, when the device reports one."""
        return self._optional_str("fan_mode")

    @property
    def allowed_fan_modes(self) -> list[str]:
        """Fan mode vocabulary advertised by a 24 V thermostat."""
        return as_list(self.get_value(LOW_VOLTAGE_ALLOWED_FAN_MODES, None))

    @property
    def current_state(self) -> str | None:
        """Raw running state reported by a 24 V thermostat.

        Exposed for consumers, but deliberately not mapped to hvac_action yet:
        its vocabulary has not been observed in enough operating conditions.
        """
        return self._optional_str("current_state")

    @property
    def cool_setpoint(self) -> float | None:
        """Cooling setpoint of a 24 V thermostat."""
        return self._optional_float("cool_temperature_set")

    @property
    def min_cool_setpoint(self) -> float | None:
        """Lowest cooling setpoint allowed by a 24 V thermostat."""
        return self._optional_float("min_cool_setpoint")

    @property
    def max_cool_setpoint(self) -> float | None:
        """Highest cooling setpoint allowed by a 24 V thermostat."""
        return self._optional_float("max_cool_setpoint")

    @property
    def current_humidity(self) -> int | None:
        """Ambient humidity, rounded to the nearest percent.

        GraphqlValueMapper reports 0 for a device without a humidity sensor,
        not None, so a reading of 0 is a real (if degenerate) value rather
        than an absent one.
        """
        value = self._optional_float("humidity")
        return None if value is None else round(value)

    async def async_set_low_voltage_state(
        self,
        mode: str | None = None,
        target_temperature: float | None = None,
        cool_setpoint: float | None = None,
        fan_mode: str | None = None,
    ) -> None:
        """Write the mode and both setpoints together.

        24 V thermostats reject partial writes: the mode and both setpoints
        have to be sent in one request even when only one of them changed.
        Arguments left out keep their current value; values the device does
        not report at all are omitted from the payload.
        """
        payload: dict[str, Any] = {
            "Thermostat24VMode": mode if mode is not None else self.low_voltage_mode,
            "TargetTemperature": (
                target_temperature
                if target_temperature is not None
                else self._optional_float("target_temperature")
            ),
            "CoolTemperatureSet": (
                cool_setpoint if cool_setpoint is not None else self.cool_setpoint
            ),
        }
        if fan_mode is not None:
            payload["FanMode"] = fan_mode
        payload = {k: v for k, v in payload.items() if v is not None}
        LOG.info("%s Setting low voltage state to %s", self._tag, payload)
        await self.set_attributes(payload)
