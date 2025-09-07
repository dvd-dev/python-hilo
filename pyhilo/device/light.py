"""Light object """

from typing import Union

from pyhilo import API
from pyhilo.const import LOG
from pyhilo.device import HiloDevice


class Light(HiloDevice):
    def __init__(self, api: API, **kwargs: dict[str, Union[str, int]]):
        super().__init__(api, **kwargs)  # type: ignore
        LOG.debug("Setting up Light device: %s", self.name)

    @property
    def brightness(self) -> float:
        return self.get_value("intensity") * 255 or 0

    @property
    def state(self) -> str:
        return "on" if self.get_value("is_on") else "off"

    @property
    def hue(self) -> int:
        return self.get_value("hue") or 0

    @property
    def intensity(self) -> int:
        return self.get_value("intensity") * 255 or 0

    @property
    def saturation(self) -> int:
        return self.get_value("saturation") or 0

    @property
    def color_temperature(self) -> int:
        return self.get_value("ColorTemperature") or 0
