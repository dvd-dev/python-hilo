"""Event object """
from datetime import datetime, timedelta
import re
from typing import Any, cast

from pyhilo.util import camel_to_snake, from_utc_timestamp


class Event:
    preheat_start: datetime
    preheat_end: datetime
    reduction_start: datetime
    reduction_end: datetime
    recovery_start: datetime
    recovery_end: datetime

    def __init__(self, **event: dict[str, Any]):
        self._convert_phases(cast(dict[str, Any], event.get("phases")))
        params: dict[str, Any] = event.get("parameters", {})
        devices: list[dict[str, Any]] = params.get("devices", [])
        consumption: dict[str, Any] = event.get("consumption", {})
        allowed_wH: int = consumption.get("baselineWh", 0) or 0
        used_wH: int = consumption.get("currentWh", 0) or 0
        self.participating: bool = cast(bool, event.get("isParticipating", False))
        self.configurable: bool = cast(bool, event.get("isConfigurable", False))
        self.period: str = cast(str, event.get("period", ""))
        self.event_id: int = cast(int, event["id"])
        self.total_devices: int = len(devices)
        self.opt_out_devices: int = len([x for x in devices if x["optOut"]])
        self.pre_heat_devices: int = len([x for x in devices if x["preheat"]])
        self.progress: str = cast(str, event.get("progress", "unknown"))
        self.mode: str = cast(str, params.get("mode", "Unknown"))
        self.allowed_kWh: float = round(allowed_wH / 1000, 2)
        self.used_kWh: float = round(used_wH / 1000, 2)
        self.used_percentage: float = 0
        if allowed_wH > 0:
            self.used_percentage = round(used_wH / allowed_wH * 100, 2)
        self.dict_items = [
            "participating",
            "configurable",
            "period",
            "total_devices",
            "opt_out_devices",
            "pre_heat_devices",
            "mode",
            "allowed_kWh",
            "used_kWh",
            "used_percentage",
        ]

    def as_dict(self) -> dict[str, Any]:
        rep = {k: getattr(self, k) for k in self.dict_items}
        rep["phases"] = {k: getattr(self, k) for k in self.phases_list}
        rep["state"] = self.state
        return rep

    def _convert_phases(self, phases: dict[str, Any]) -> None:
        if not len(phases):
            return
        self.phases_list = []
        for key, value in phases.items():
            if not key.endswith("DateUTC"):
                continue
            phase_match = re.match(r"(.*)DateUTC", key)
            if not phase_match:
                continue
            phase = camel_to_snake(phase_match.group(1))
            setattr(self, phase, from_utc_timestamp(value))
            self.phases_list.append(phase)

    def appreciation(self, hours: int) -> datetime:
        """Wrapper to return X hours before pre_heat.
        Will also set appreciation_start and appreciation end phases.
        """
        self.appreciation_start = self.preheat_start - timedelta(hours=hours)
        self.appreciation_end = self.preheat_start
        if "appreciation_start" not in self.phases_list:
            self.phases_list[:0] = ["appreciation_start", "appreciation_end"]
        return self.appreciation_start

    @property
    def state(self) -> str:
        now = datetime.now(self.preheat_start.tzinfo)
        if (
            "appreciation_start" in self.phases_list
            and self.appreciation_start <= now < self.appreciation_end
        ):
            return "appreciation"
        elif self.preheat_start > now:
            return "scheduled"
        elif self.preheat_start <= now < self.preheat_end:
            return "pre_heat"
        elif self.reduction_start <= now < self.reduction_end:
            return "reduction"
        elif self.recovery_start <= now < self.recovery_end:
            return "recovery"
        elif now <= self.recovery_end:
            return "completed"
        elif self.progress:
            return self.progress
        else:
            return "unknown"
