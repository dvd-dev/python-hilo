"""Climate object """

from typing import Union

from pyhilo import API
from pyhilo.const import LOG
from pyhilo.device import HiloDevice


class Sensor(HiloDevice):
    def __init__(self, api: API, **kwargs: dict[str, Union[str, int]]):
        super().__init__(api, **kwargs)
        LOG.debug(f"Setting up Sensor device: {self.name}")

    @property
    def state(self) -> str:
        return "on" if self.get_value("disconnected") else "off"
