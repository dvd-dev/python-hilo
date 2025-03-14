"""Climate object."""
from __future__ import annotations

from typing import Any, cast

from pyhilo import API
from pyhilo.const import LOG
from pyhilo.device import HiloDevice


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
