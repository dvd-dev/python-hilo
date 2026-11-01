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


def _hub(connection_status: str) -> dict:
    return {
        "hiloId": "hub-1",
        "deviceType": "Hub",
        "connectionStatus": connection_status,
        "lastConnectionTime": "2026-11-01T12:00:00Z",
        "controllerSoftwareVersion": "1.0.0",
        "zigBeePairingModeEnhanced": False,
        "willBeConnectedToSmartMeter": False,
        "smartMeterPairingStatus": False,
    }


def _disconnected_values(device: dict) -> set[bool]:
    attributes = GraphqlValueMapper().map_device_subscription_values(device)
    return {a["value"] for a in attributes if a["attribute"] == "Disconnected"}


@pytest.mark.parametrize(
    ("filename", "connection_status", "expected"),
    [
        pytest.param(
            "onAnyDeviceUpdated-tstat.json", "CONNECTED", False, id="tstat-connected"
        ),
        pytest.param(
            "onAnyDeviceUpdated-tstat.json",
            "DISCONNECTED",
            True,
            id="tstat-disconnected",
        ),
        pytest.param(
            "onAnyDeviceUpdated-cee.json", "CONNECTED", False, id="cee-connected"
        ),
        pytest.param(
            "onAnyDeviceUpdated-cee.json", "DISCONNECTED", True, id="cee-disconnected"
        ),
        pytest.param(
            "onAnyDeviceUpdated-meter.json", "CONNECTED", False, id="meter-connected"
        ),
        pytest.param(
            "onAnyDeviceUpdated-meter.json",
            "DISCONNECTED",
            True,
            id="meter-disconnected",
        ),
    ],
)
def test_device_disconnected_follows_connection_status(
    filename: str, connection_status: str, expected: bool
) -> None:
    """Hilo reports connectionStatus as a string; DISCONNECTED maps to Disconnected=True."""
    device = _device(filename)
    device["connectionStatus"] = connection_status

    assert _disconnected_values(device) == {expected}


@pytest.mark.parametrize(
    ("connection_status", "expected"),
    [
        pytest.param("CONNECTED", False, id="connected"),
        pytest.param("DISCONNECTED", True, id="disconnected"),
    ],
)
def test_hub_disconnected_follows_connection_status(
    connection_status: str, expected: bool
) -> None:
    """The gateway's Disconnected attribute is derived from the string status."""
    assert _disconnected_values(_hub(connection_status)) == {expected}
