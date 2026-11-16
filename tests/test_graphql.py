"""Tests for GraphQlHelper Gateway creation and subscription result routing."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyhilo import API
from pyhilo.devices import Devices
from pyhilo.graphql import GraphQlHelper

GATEWAY_HILO_ID = "urn:hilo:ihub:AA11BB22CC33:0"
TSTAT_HILO_ID = "urn:hilo:philo:1a2b3c4d5e6f0001:0"
SWITCH_HILO_ID = "urn:hilo:philo:9a8b7c6d5e4f0002:0"


def _make_helper() -> tuple[GraphQlHelper, Devices]:
    api = API(session=MagicMock(), auth=MagicMock())
    devices = Devices(api)
    devices.location_id = 42
    devices.location_hilo_id = "urn:hilo:crm:00000-abcdef:0"
    return GraphQlHelper(api, devices), devices


def _gateway_payload(
    connection_status: str,
    device_type: str | None = "Gateway",
    typename: str | None = "Gateway",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "deviceType": device_type,
        "hiloId": GATEWAY_HILO_ID,
        "physicalAddress": "AA11BB22CC33",
        "connectionStatus": connection_status,
        "controllerSoftwareVersion": "1.2.3",
        "lastConnectionTime": "2026-11-11T12:00:00Z",
        "willBeConnectedToSmartMeter": True,
        "zigBeeChannel": 15,
        "zigBeePairingModeEnhanced": False,
        "smartMeterZigBeeChannel": 24,
        "smartMeterPairingStatus": True,
    }
    if typename is not None:
        payload["__typename"] = typename
    return payload


@pytest.mark.parametrize(
    ("typename", "device_type", "connection_status", "expected_available"),
    [
        pytest.param(None, "Gateway", "CONNECTED", True, id="gateway-connected"),
        pytest.param(None, "Gateway", "DISCONNECTED", False, id="gateway-disconnected"),
        pytest.param(None, "hub", "CONNECTED", True, id="lowercase-hub-connected"),
        pytest.param(
            None, "gateway", "DISCONNECTED", False, id="lowercase-gateway-offline"
        ),
        pytest.param(
            "Gateway", None, "CONNECTED", True, id="typename-only-null-device-type"
        ),
        pytest.param(
            "Gateway",
            "ihub",
            "DISCONNECTED",
            False,
            id="typename-with-unrecognized-device-type",
        ),
    ],
)
def test_gateway_query_populates_hilo_id_and_availability(
    typename: str | None,
    device_type: str | None,
    connection_status: str,
    expected_available: bool,
) -> None:
    """getLocation creates the Gateway with its real hilo_id across typename and deviceType forms."""
    helper, devices = _make_helper()
    payload = _gateway_payload(
        connection_status, device_type=device_type, typename=typename
    )

    updated_ids = helper._handle_query_result({"getLocation": {"devices": [payload]}})

    gateway = devices.find_device(GATEWAY_HILO_ID)
    assert gateway is not None
    assert updated_ids == [GATEWAY_HILO_ID]
    assert gateway.hilo_id == GATEWAY_HILO_ID
    assert gateway.identifier == "AA11BB22CC33"
    assert gateway.available is expected_available
    assert gateway.get_value("online_status") == connection_status


def test_gateway_query_does_not_duplicate_when_gateway_id_changed() -> None:
    """Re-running getLocation after SignalR updates gateway.id refreshes it in place."""
    helper, devices = _make_helper()
    helper._handle_query_result(
        {"getLocation": {"devices": [_gateway_payload("CONNECTED")]}}
    )
    gateway = devices.find_device(GATEWAY_HILO_ID)
    assert gateway is not None
    gateway.id = 98765

    helper._handle_query_result(
        {"getLocation": {"devices": [_gateway_payload("DISCONNECTED")]}}
    )

    gateways = [d for d in devices.all if d.type == "Gateway"]
    assert len(gateways) == 1
    assert gateway.available is False


def test_gateway_query_backfills_hilo_id_on_existing_gateway() -> None:
    """An existing Gateway without hilo_id gets its hilo_id populated by getLocation."""
    helper, devices = _make_helper()
    existing_gw = devices.generate_device(
        {
            "id": 1,
            "name": "Hilo Gateway",
            "type": "Gateway",
            "provider": 1,
            "supportedAttributes": "Disconnected",
            "settableAttributes": "",
            "Disconnected": {"value": False},
        }
    )
    devices.devices.append(existing_gw)

    helper._handle_query_result(
        {"getLocation": {"devices": [_gateway_payload("DISCONNECTED")]}}
    )

    assert existing_gw.hilo_id == GATEWAY_HILO_ID
    assert existing_gw.available is False


def test_gateway_device_subscription_updates_availability_and_notifies_callback() -> (
    None
):
    """onAnyDeviceUpdated updates Gateway availability and passes its hilo_id to callback."""
    helper, devices = _make_helper()
    helper._handle_query_result(
        {"getLocation": {"devices": [_gateway_payload("CONNECTED")]}}
    )
    gateway = devices.find_device(GATEWAY_HILO_ID)
    assert gateway is not None
    assert gateway.available is True

    notified: list[str] = []
    sse_payload: dict[str, object] = {
        "data": {
            "onAnyDeviceUpdated": {
                "device": _gateway_payload(
                    "DISCONNECTED", device_type=None, typename="Gateway"
                ),
            }
        }
    }

    retry, had_success = helper._handle_sse_message(
        sse_payload, helper._handle_device_subscription_result, notified.append
    )

    assert (retry, had_success) == (False, True)
    assert gateway.available is False
    assert gateway.get_value("online_status") == "DISCONNECTED"
    assert notified == [GATEWAY_HILO_ID]


def test_device_subscription_skips_callback_for_unmapped_device() -> None:
    """onAnyDeviceUpdated does not invoke callback when no device was updated."""
    helper, _ = _make_helper()
    notified: list[str] = []
    sse_payload: dict[str, object] = {
        "data": {
            "onAnyDeviceUpdated": {
                "device": {},
            }
        }
    }

    retry, had_success = helper._handle_sse_message(
        sse_payload, helper._handle_device_subscription_result, notified.append
    )

    assert (retry, had_success) == (False, True)
    assert notified == []


def test_unknown_hilo_id_reading_does_not_overwrite_gateway_availability() -> None:
    """GraphQL readings for an unknown hiloId must not fall back to the Gateway device."""
    helper, devices = _make_helper()
    helper._handle_query_result(
        {"getLocation": {"devices": [_gateway_payload("CONNECTED")]}}
    )
    gateway = devices.find_device(GATEWAY_HILO_ID)
    assert gateway is not None
    assert gateway.available is True

    notified: list[str] = []
    sse_payload: dict[str, object] = {
        "data": {
            "onAnyLocationUpdated": {
                "transmissionTime": "2026-11-11T12:05:00Z",
                "operationId": "00000000-0000-0000-0000-000000000011",
                "location": {
                    "devices": [
                        {
                            "__typename": "BasicSwitch",
                            "hiloId": "urn:hilo:philo:unpaired-switch:0",
                            "connectionStatus": "DISCONNECTED",
                        }
                    ]
                },
            }
        }
    }

    helper._handle_sse_message(
        sse_payload, helper._handle_location_subscription_result, notified.append
    )

    assert gateway.available is True
    assert notified == []


def test_signalr_zero_device_id_without_hilo_id_falls_back_to_gateway() -> None:
    """SignalR readings with deviceId=0 and no hiloId route to the Gateway, not other unset-hilo_id devices."""
    helper, devices = _make_helper()
    legacy_sensor = devices.generate_device(
        {
            "id": 500,
            "name": "Weather Station",
            "type": "IndoorWeatherStation",
            "provider": 2,
            "supportedAttributes": "Disconnected",
            "settableAttributes": "",
            "Disconnected": {"value": False},
        }
    )
    devices.devices.append(legacy_sensor)
    helper._handle_query_result(
        {"getLocation": {"devices": [_gateway_payload("CONNECTED")]}}
    )
    gateway = devices.find_device(GATEWAY_HILO_ID)
    assert gateway is not None

    updated = devices.parse_values_received(
        [
            {
                "deviceId": 0,
                "timeStampUTC": "2026-11-11T12:00:00Z",
                "attribute": "Disconnected",
                "value": True,
            }
        ]
    )

    assert updated == [gateway]
    assert gateway.available is False
    assert legacy_sensor.available is True


async def test_resync_after_reconnect_notifies_callback_with_updated_hilo_ids() -> None:
    """SSE reconnect state resync forwards updated device hilo_ids to callback."""
    helper, _ = _make_helper()
    notified: list[str] = []

    with patch.object(
        helper,
        "call_get_location_query",
        new=AsyncMock(return_value=[GATEWAY_HILO_ID, TSTAT_HILO_ID]),
    ):
        await helper._resync_after_reconnect(
            "urn:hilo:crm:00000-abcdef:0", notified.append
        )

    assert notified == [GATEWAY_HILO_ID, TSTAT_HILO_ID]


def test_subscription_device_updated_gateway_fragment_requests_identity_fields() -> (
    None
):
    """The Gateway inline fragment in SUBSCRIPTION_DEVICE_UPDATED must include deviceType and hiloId."""
    match = re.search(
        r"\.\.\.\s*on\s+Gateway\s*\{([^}]*)\}",
        GraphQlHelper.SUBSCRIPTION_DEVICE_UPDATED,
    )
    assert match is not None
    fields = set(match.group(1).split())
    assert {"deviceType", "hiloId", "physicalAddress", "connectionStatus"} <= fields


def test_location_subscription_updates_devices_and_dispatches_each_hilo_id() -> None:
    """onAnyLocationUpdated updates each device's availability and invokes callback per hilo_id."""
    helper, devices = _make_helper()
    helper._handle_query_result(
        {"getLocation": {"devices": [_gateway_payload("CONNECTED")]}}
    )
    gateway = devices.find_device(GATEWAY_HILO_ID)
    assert gateway is not None
    tstat = devices.generate_device(
        {
            "id": 100,
            "hilo_id": TSTAT_HILO_ID,
            "name": "Living Room",
            "type": "Thermostat",
            "provider": 1,
            "supportedAttributes": "Disconnected, CurrentTemperature",
            "settableAttributes": "",
            "Disconnected": {"value": False},
        }
    )
    switch = devices.generate_device(
        {
            "id": 101,
            "hilo_id": SWITCH_HILO_ID,
            "name": "Porch Light",
            "type": "LightSwitch",
            "provider": 1,
            "supportedAttributes": "Disconnected, OnOff",
            "settableAttributes": "OnOff",
            "Disconnected": {"value": True},
        }
    )
    devices.devices.extend([tstat, switch])

    notified: list[str] = []
    sse_payload: dict[str, object] = {
        "data": {
            "onAnyLocationUpdated": {
                "transmissionTime": "2026-11-11T12:05:00Z",
                "operationId": "00000000-0000-0000-0000-000000000010",
                "location": {
                    "devices": [
                        {
                            "__typename": "Gateway",
                            "hiloId": GATEWAY_HILO_ID,
                            "connectionStatus": "DISCONNECTED",
                        },
                        {
                            "__typename": "BasicThermostat",
                            "hiloId": TSTAT_HILO_ID,
                            "connectionStatus": "DISCONNECTED",
                        },
                        {
                            "__typename": "BasicSwitch",
                            "hiloId": SWITCH_HILO_ID,
                            "connectionStatus": "CONNECTED",
                        },
                        {
                            "__typename": "BasicDevice",
                            "hiloId": "urn:hilo:netatmo:station:0",
                            "connectionStatus": None,
                        },
                    ]
                },
            }
        }
    }

    retry, had_success = helper._handle_sse_message(
        sse_payload, helper._handle_location_subscription_result, notified.append
    )

    assert (retry, had_success) == (False, True)
    assert gateway.available is False
    assert gateway.get_value("online_status") == "DISCONNECTED"
    assert tstat.available is False
    assert switch.available is True
    assert notified == [GATEWAY_HILO_ID, TSTAT_HILO_ID, SWITCH_HILO_ID]
