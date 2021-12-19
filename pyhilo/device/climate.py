"""Climate object """

from typing import Union

from pyhilo import API
from pyhilo.const import LOG
from pyhilo.device import HiloDevice


class Climate(HiloDevice):
    def __init__(self, api: API, **kwargs: dict[str, Union[str, int]]):
        super().__init__(api, **kwargs)
        LOG.debug(f"Setting up Climate device: {self.name}")

    @property
    def current_temperature(self) -> float:
        attr = self.get_attribute("current_temperature")
        return attr.value if attr else 0

    @property
    def target_temperature(self) -> float:
        attr = self.get_attribute("target_temperature")
        return attr.value if attr else 0

    @property
    def max_temp(self) -> float:
        attr = self.get_attribute("max_temp_setpoint")
        return attr.value if attr else 0

    @property
    def min_temp(self) -> float:
        attr = self.get_attribute("min_temp_setpoint")
        return attr.value if attr else 0

    @property
    def hvac_mode(self) -> str:
        attr = self.get_attribute("heating")
        if attr and attr.value > 0:
            return "heat"
        return "off"

    async def async_set_temperature(self, **kwargs: dict[str, int]) -> None:
        temperature = kwargs.get("temperature", 0)
        if temperature:
            LOG.info(f"{self._tag} Setting temperature to {temperature}")
            await self.set_attribute("target_temperature", temperature)  # type: ignore
