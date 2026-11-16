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


def _hub(connection_status: str, device_type: str = "Hub") -> dict[str, object]:
    return {
        "hiloId": "hub-1",
        "deviceType": device_type,
        "connectionStatus": connection_status,
        "lastConnectionTime": "2026-11-01T12:00:00Z",
        "controllerSoftwareVersion": "1.0.0",
        "zigBeePairingModeEnhanced": False,
        "willBeConnectedToSmartMeter": False,
        "smartMeterPairingStatus": False,
    }


def _disconnected_values(device: dict[str, object]) -> list[bool]:
    attributes = GraphqlValueMapper().map_device_subscription_values(device)
    return [a["value"] for a in attributes if a["attribute"] == "Disconnected"]


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

    assert _disconnected_values(device) == [expected]


@pytest.mark.parametrize(
    ("device_type", "connection_status", "expected"),
    [
        pytest.param("Hub", "CONNECTED", False, id="hub-connected"),
        pytest.param("Hub", "DISCONNECTED", True, id="hub-disconnected"),
        pytest.param("Gateway", "CONNECTED", False, id="gateway-connected"),
        pytest.param("Gateway", "DISCONNECTED", True, id="gateway-disconnected"),
    ],
)
def test_hub_disconnected_follows_connection_status(
    device_type: str, connection_status: str, expected: bool
) -> None:
    """The gateway's Disconnected attribute is derived for both Hub and Gateway types."""
    assert _disconnected_values(_hub(connection_status, device_type)) == [expected]


@pytest.mark.parametrize(
    ("ambient_humidity", "expected"),
    [
        pytest.param(45.5, [45.5], id="reading"),
        pytest.param(0, [], id="no-sensor-zero"),
        pytest.param(None, [], id="null"),
    ],
)
def test_thermostat_humidity_reports_only_real_readings(
    ambient_humidity: float | None, expected: list[float]
) -> None:
    """Non-zero humidity is kept; 0 (no sensor, e.g. HT402) or null is dropped."""
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
