from datetime import datetime
import re
from typing import Any, Union, cast

from pyhilo.util import camel_to_snake, from_utc_timestamp


def event_parsing(event: dict[str, Any]) -> dict[str, Any]:
    parsed_event: dict[str, Union[datetime, bool, str]] = {}
    current_event = "off"
    phases = event.get("phases", {})
    if not len(phases):
        return {}
    for key, value in phases.items():
        if not key.endswith("DateUTC"):
            continue
        phase_match = re.match(r"(.*)DateUTC", key)
        if not phase_match:
            continue
        phase = camel_to_snake(phase_match.group(1))
        parsed_event[phase] = from_utc_timestamp(value)
    now = datetime.now(parsed_event["preheat_start"].tzinfo)  # type: ignore
    if cast(datetime, parsed_event["preheat_start"]) > now:
        current_event = "scheduled"
    elif (
        cast(datetime, parsed_event["preheat_start"])
        <= now
        < cast(datetime, parsed_event["preheat_end"])
    ):
        current_event = "pre_heat"
    elif (
        cast(datetime, parsed_event["reduction_start"])
        <= now
        < cast(datetime, parsed_event["reduction_end"])
    ):
        current_event = "reduction"
    elif (
        cast(datetime, parsed_event["recovery_start"])
        <= now
        < cast(datetime, parsed_event["recovery_end"])
    ):
        current_event = "recovery"
    elif event.get("progress", "") == "scheduled":
        current_event = "scheduled"
    elif event.get("progress", "NotInProgress") == "inProgress":
        # if something's fishy with the parsed_event but the isProgress is enabled
        # let's just flip the switch on.
        current_event = "on"
    parsed_event["current"] = current_event
    parsed_event["participating"] = event.get("isParticipating", False)
    parsed_event["configurable"] = event.get("isConfigurable", False)
    parsed_event["period"] = event.get("period", "")
    return parsed_event
