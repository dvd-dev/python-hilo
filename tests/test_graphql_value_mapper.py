"""Tests for mapping GraphQL subscription payloads to device attributes."""

import json
from pathlib import Path

import pytest

from pyhilo.device.graphql_value_mapper import GraphqlValueMapper

PAYLOADS = Path(__file__).parent.parent / "doc" / "graphql"


def _device(filename: str) -> dict:
    payload = json.loads((PAYLOADS / filename).read_text(encoding="utf-8"))
    return payload["data"]["onAnyDeviceUpdated"]["device"]


def test_smart_meter_maps_zigbee_channel() -> None:
    """The meter's Zigbee channel is reported as the ZigbeeChannel attribute."""
    attributes = GraphqlValueMapper().map_device_subscription_values(
        _device("onAnyDeviceUpdated-meter.json")
    )

    channel = [a["value"] for a in attributes if a["attribute"] == "ZigbeeChannel"]
    assert channel == [24]


@pytest.mark.parametrize(
    ("ambient_humidity", "expected"),
    [
        pytest.param(45.5, [45.5], id="reading"),
        pytest.param(0, [], id="no-sensor-zero"),
        pytest.param(None, [], id="null"),
    ],
)
def test_thermostat_humidity_skips_missing_sensor(
    ambient_humidity: float | None, expected: list[float]
) -> None:
    """Models without a humidity sensor report 0, which must not surface as 0%."""
    device = _device("onAnyDeviceUpdated-tstat.json")
    device["ambientHumidity"] = ambient_humidity

    attributes = GraphqlValueMapper().map_device_subscription_values(device)

    assert [a["value"] for a in attributes if a["attribute"] == "Humidity"] == expected


def test_thermostat_humidity_absent_field() -> None:
    """Payloads that omit ambientHumidity produce no Humidity attribute."""
    device = _device("onAnyDeviceUpdated-tstat.json")
    del device["ambientHumidity"]

    attributes = GraphqlValueMapper().map_device_subscription_values(device)

    assert not [a for a in attributes if a["attribute"] == "Humidity"]
