from datetime import datetime, timezone

from pyhilo.util import camel_to_snake, from_utc_timestamp, time_diff


def test_camel_to_snake() -> None:
    assert camel_to_snake("CurrentTemperature") == "current_temperature"
    assert camel_to_snake("OnOff") == "on_off"
    assert camel_to_snake("zigBeeChannel") == "zig_bee_channel"
    assert camel_to_snake("already_snake") == "already_snake"


def test_from_utc_timestamp() -> None:
    result = from_utc_timestamp("2024-01-15T10:30:00Z")
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_time_diff() -> None:
    now = datetime.now(timezone.utc)
    earlier = datetime(2020, 1, 1, tzinfo=timezone.utc)
    diff = time_diff(now, earlier)
    assert diff.total_seconds() > 0
