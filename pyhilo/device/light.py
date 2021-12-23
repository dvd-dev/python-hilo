"""Climate object """

from typing import Union

from pyhilo import API
from pyhilo.const import LOG
from pyhilo.device import HiloDevice


class Light(HiloDevice):
    def __init__(self, api: API, **kwargs: dict[str, Union[str, int]]):
        super().__init__(api, **kwargs)
        LOG.debug(f"Setting up Light device: {self.name}")

    @property
    def brightness(self) -> float:
        return self.get_value("intensity") * 255 or 0

    @property
    def state(self) -> str:
        return "on" if self.get_value("is_on") else "off"
