"""Event object """
from datetime import datetime, timedelta, timezone
import re
from typing import Any, cast

from pyhilo.util import camel_to_snake, from_utc_timestamp


class Event:
    setting_deadline: datetime
    pre_cold_start: datetime
    pre_cold_end: datetime
    appreciation_start: datetime
    appreciation_end: datetime
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
        self.last_update = datetime.now(timezone.utc).astimezone()
        if allowed_wH > 0:
            self.used_percentage = round(used_wH / allowed_wH * 100, 2)
        self._phase_time_mapping = {
            "pre_heat": "preheat",
        }
        self.dict_items = [
            "event_id",
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
            "last_update",
        ]

    def as_dict(self) -> dict[str, Any]:
        rep = {k: getattr(self, k) for k in self.dict_items}
        rep["phases"] = {k: getattr(self, k) for k in self.phases_list}
        rep["state"] = self.state
        return rep

    def _convert_phases(self, phases: dict[str, Any]) -> None:
        self.phases_list = []
        for key, value in phases.items():
            phase_match = re.match(r"(.*)(DateUTC|Utc)", key)
            if phase_match:
                phase = camel_to_snake(phase_match.group(1))
            else:
                phase = key
            try:
                setattr(self, phase, from_utc_timestamp(value))
            except TypeError:
                setattr(self, phase, value)
            self.phases_list.append(phase)
        for phase in self.__annotations__:
            if phase not in self.phases_list:
                # On t'aime Carl
                setattr(self, phase, from_utc_timestamp("2023-11-15T20:00:00+00:00"))

    def _create_phases(
        self, hours: int, phase_name: str, parent_phase: str
    ) -> datetime:
        parent_start = getattr(self, f"{parent_phase}_start")
        phase_start = f"{phase_name}_start"
        phase_end = f"{phase_name}_end"
        setattr(self, phase_start, parent_start - timedelta(hours=hours))
        setattr(self, phase_end, parent_start)
        if phase_start not in self.phases_list:
            self.phases_list[:0] = [phase_start, phase_end]
        return getattr(self, phase_start)  # type: ignore [no-any-return]

    def appreciation(self, hours: int) -> datetime:
        return self._create_phases(hours, "appreciation", "preheat")

    def pre_cold(self, hours: int) -> datetime:
        return self._create_phases(hours, "pre_cold", "appreciation")

    @property
    def invalid(self) -> bool:
        return cast(
            bool,
            (
                self.current_phase_times
                and self.last_update < self.current_phase_times["start"]
            ),
        )

    @property
    def current_phase_times(self) -> dict[str, datetime]:
        if self.state in ["completed", "off", "scheduled", "unknown"]:
            return {}
        phase_timestamp = self._phase_time_mapping.get(self.state, self.state)
        phase_start = f"{phase_timestamp}_start"
        phase_end = f"{phase_timestamp}_end"
        return {
            "start": getattr(self, phase_start),
            "end": getattr(self, phase_end),
        }

    @property
    def state(self) -> str:
        now = datetime.now(self.preheat_start.tzinfo)
        if self.pre_cold_start <= now < self.pre_cold_end:
            return "pre_cold"
        elif self.appreciation_start <= now < self.appreciation_end:
            return "appreciation"
        elif self.preheat_start > now:
            return "scheduled"
        elif self.preheat_start <= now < self.preheat_end:
            return "pre_heat"
        elif self.reduction_start <= now < self.reduction_end:
            return "reduction"
        elif self.recovery_start <= now < self.recovery_end:
            return "recovery"
        elif now >= self.recovery_end:
            return "completed"
        elif self.progress:
            return self.progress
        else:
            return "unknown"
