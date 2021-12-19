"""Climate object """

from typing import Any, Union

from pyhilo import API
from pyhilo.const import LOG
from pyhilo.device import HiloDevice


class Light(HiloDevice):
    def __init__(self, api: API, **kwargs: dict[str, Union[str, int]]):
        super().__init__(api, **kwargs)
        LOG.debug(f"Setting up Light device: {self.name}")

    @property
    def brightness(self) -> float:
        attr = self.get_attribute("intensity")
        return attr.value if attr else 0

    @property
    def state(self) -> str:
        attr = self.get_attribute("is_on")
        return attr.value if attr else "unavailable"  # type: ignore

    @property
    def supported_color_modes(self) -> set:
        """Flag supported modes."""
        supports = set("onoff")
        if "intensity" in self.hilo_attributes:
            supports.add("brightness")
        return supports

    async def async_turn_on(self, **kwargs: dict[str, Any]) -> None:
        brightness = kwargs.get("brightness")
        LOG.info(f"{self._tag} Turning on, brightness {brightness}")
        await self.set_attribute("is_on", True)
        if brightness:
            await self.set_attribute("brightness", brightness)  # type: ignore
