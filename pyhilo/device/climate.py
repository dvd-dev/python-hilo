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

    @property
    def is_low_voltage(self) -> bool:
        """Whether this is a low voltage (24 V) thermostat.

        Baseboard thermostats report none of the 24 V attributes and therefore
        keep their heat-only behaviour.
        """
        return self.get_value(LOW_VOLTAGE_MODE, None) is not None

    @property
    def mode(self) -> str | None:
        """Operating mode reported by a 24 V thermostat, in Hilo's vocabulary."""
        value = self.get_value(LOW_VOLTAGE_MODE, None)
        return None if value is None else str(value)

    @property
    def allowed_modes(self) -> list[str]:
        """Mode vocabulary advertised by a 24 V thermostat."""
        return as_list(self.get_value(LOW_VOLTAGE_ALLOWED_MODES, None))

    @property
    def fan_mode(self) -> str | None:
        """Current fan mode, when the device reports one."""
        value = self.get_value("fan_mode", None)
        return None if value is None else str(value)

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
        value = self.get_value("current_state", None)
        return None if value is None else str(value)

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
        """Ambient humidity, when the device reports it."""
        value = self._optional_float("humidity")
        return None if value is None else int(value)
