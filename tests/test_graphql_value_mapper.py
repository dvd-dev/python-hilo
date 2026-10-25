"""Tests for mapping GraphQL subscription payloads to device attributes."""

import json
from pathlib import Path

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