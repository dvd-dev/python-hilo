"""Climate object """

from typing import Union, cast

from pyhilo import API
from pyhilo.const import LOG
from pyhilo.device import HiloDevice


class Climate(HiloDevice):
    def __init__(self, api: API, **kwargs: dict[str, Union[str, int]]):
        super().__init__(api, **kwargs)
        LOG.debug(f"Setting up Climate device: {self.name}")

    @property
    def current_temperature(self) -> float:
        return cast(float, self.get_value("current_temperature", 0))

    @property
    def target_temperature(self) -> float:
        return cast(float, self.get_value("target_temperature", 0))

    @property
    def max_temp(self) -> float:
        return cast(float, self.get_value("max_temp_setpoint", 0))

    @property
    def min_temp(self) -> float:
        return cast(float, self.get_value("min_temp_setpoint", 0))

    @property
    def hvac_mode(self) -> str:
        attr = self.get_value("heating", 0)
        return "heat" if attr > 0 else "off"

    async def async_set_temperature(self, **kwargs: dict[str, int]) -> None:
        temperature = kwargs.get("temperature", 0)
        if temperature:
            LOG.info(f"{self._tag} Setting temperature to {temperature}")
            await self.set_attribute("target_temperature", temperature)  # type: ignore
