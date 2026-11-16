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


def _hub(connection_status: str | None, device_type: str = "Hub") -> dict[str, object]:
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
            "onAnyDeviceUpdated-tstat.json", None, True, id="tstat-null-status"
        ),
        pytest.param(
            "onAnyDeviceUpdated-cee.json", "CONNECTED", False, id="cee-connected"
        ),
        pytest.param(
            "onAnyDeviceUpdated-cee.json", "DISCONNECTED", True, id="cee-disconnected"
        ),
        pytest.param("onAnyDeviceUpdated-cee.json", None, True, id="cee-null-status"),
        pytest.param(
            "onAnyDeviceUpdated-meter.json", "CONNECTED", False, id="meter-connected"
        ),
        pytest.param(
            "onAnyDeviceUpdated-meter.json",
            "DISCONNECTED",
            True,
            id="meter-disconnected",
        ),
        pytest.param(
            "onAnyDeviceUpdated-meter.json", None, True, id="meter-null-status"
        ),
    ],
)
def test_device_disconnected_follows_connection_status(
    filename: str, connection_status: str | None, expected: bool
) -> None:
    """Only CONNECTED maps to Disconnected=False; DISCONNECTED or null maps to True."""
    device = _device(filename)
    device["connectionStatus"] = connection_status

    assert _disconnected_values(device) == [expected]


def test_device_disconnected_when_connection_status_absent() -> None:
    """Payloads omitting connectionStatus default to Disconnected=True."""
    device = _device("onAnyDeviceUpdated-tstat.json")
    del device["connectionStatus"]

    assert _disconnected_values(device) == [True]


@pytest.mark.parametrize(
    ("device_type", "connection_status", "expected"),
    [
        pytest.param("Hub", "CONNECTED", False, id="hub-connected"),
        pytest.param("Hub", "DISCONNECTED", True, id="hub-disconnected"),
        pytest.param("Hub", None, True, id="hub-null-status"),
        pytest.param("Gateway", "CONNECTED", False, id="gateway-connected"),
        pytest.param("Gateway", "DISCONNECTED", True, id="gateway-disconnected"),
        pytest.param("Gateway", None, True, id="gateway-null-status"),
    ],
)
def test_hub_disconnected_follows_connection_status(
    device_type: str, connection_status: str | None, expected: bool
) -> None:
    """The gateway's Disconnected attribute is derived for both Hub and Gateway types."""
    assert _disconnected_values(_hub(connection_status, device_type)) == [expected]


@pytest.mark.parametrize(
    "device_entry",
    [
        pytest.param(
            {
                "__typename": "BasicDevice",
                "deviceType": "IndoorWeatherStation",
                "hiloId": "urn:hilo:netatmo:station:0",
                "connectionStatus": None,
            },
            id="basic-device-stub",
        ),
        pytest.param(
            {
                "deviceType": "IndoorWeatherStation",
                "hiloId": "urn:hilo:netatmo:station:0",
                "connectionStatus": None,
            },
            id="unrecognized-device-type",
        ),
        pytest.param(
            {"deviceType": "Tstat", "connectionStatus": "DISCONNECTED"},
            id="missing-hilo-id",
        ),
    ],
)
def test_query_values_skips_unmigrated_or_incomplete_devices(
    device_entry: dict[str, object],
) -> None:
    """getLocation skips BasicDevice stubs, unknown deviceType values, and missing hiloId."""
    assert GraphqlValueMapper().map_query_values([device_entry]) == []


@pytest.mark.parametrize(
    ("connection_status", "expected"),
    [
        pytest.param("CONNECTED", False, id="connected"),
        pytest.param("DISCONNECTED", True, id="disconnected"),
        pytest.param(None, True, id="null-status"),
    ],
)
def test_location_subscription_maps_connection_status(
    connection_status: str | None, expected: bool
) -> None:
    """Location updates only carry hiloId and connectionStatus without full device fields."""
    payload: dict[str, object] = {
        "devices": [
            {
                "__typename": "BasicThermostat",
                "hiloId": "urn:hilo:philo:1a2b3c4d5e6f0001:0",
                "connectionStatus": connection_status,
            }
        ]
    }

    attributes = GraphqlValueMapper().map_location_subscription_values(payload)

    by_name = {a["attribute"]: a["value"] for a in attributes}
    assert by_name == {"Unpaired": False, "Disconnected": expected}


@pytest.mark.parametrize(
    "device_entry",
    [
        pytest.param(
            {
                "__typename": "BasicDevice",
                "hiloId": "urn:hilo:netatmo:station:0",
                "connectionStatus": None,
            },
            id="basic-device-stub",
        ),
        pytest.param(
            {"__typename": "BasicThermostat", "connectionStatus": "DISCONNECTED"},
            id="missing-hilo-id",
        ),
    ],
)
def test_location_subscription_skips_ignored_entries(
    device_entry: dict[str, object],
) -> None:
    """Unmigrated BasicDevice stubs and entries missing hiloId produce no readings."""
    payload: dict[str, object] = {"devices": [device_entry]}

    assert GraphqlValueMapper().map_location_subscription_values(payload) == []


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
