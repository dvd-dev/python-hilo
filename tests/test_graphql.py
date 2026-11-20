"""Tests for GraphQlHelper Gateway creation and device subscription updates."""

from __future__ import annotations

import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyhilo import API, HiloDevice
from pyhilo.devices import Devices
from pyhilo.graphql import GraphQlHelper

GATEWAY_HILO_ID = "urn:hilo:ihub:AA11BB22CC33:0"
TSTAT_HILO_ID = "urn:hilo:philo:1a2b3c4d5e6f0001:0"
SWITCH_HILO_ID = "urn:hilo:philo:9a8b7c6d5e4f0002:0"


def _make_helper() -> tuple[GraphQlHelper, Devices]:
    auth = MagicMock()
    auth.async_get_access_token = AsyncMock(return_value="token")
    api = API(session=MagicMock(), auth=auth)
    devices = Devices(api)
    devices.location_id = 42
    devices.location_hilo_id = "urn:hilo:crm:00000-abcdef:0"
    helper = GraphQlHelper(api, devices)
    helper._ssl_context = MagicMock(spec=ssl.SSLContext)
    return helper, devices


def _gateway_payload(
    connection_status: str, device_type: str = "Hub"
) -> dict[str, object]:
    return {
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


def _make_helper_with_gateway() -> tuple[GraphQlHelper, Devices, HiloDevice]:
    helper, devices = _make_helper()
    helper._handle_query_result(
        {"getLocation": {"devices": [_gateway_payload("CONNECTED")]}}
    )
    gateway = devices.find_device(GATEWAY_HILO_ID)
    assert gateway is not None
    return helper, devices, gateway


@pytest.mark.parametrize(
    ("connection_status", "expected_available"),
    [
        pytest.param("CONNECTED", True, id="connected"),
        pytest.param("DISCONNECTED", False, id="disconnected"),
    ],
)
def test_gateway_query_populates_hilo_id_and_availability(
    connection_status: str, expected_available: bool
) -> None:
    """getLocation creates the Gateway with its real hilo_id and availability."""
    helper, devices = _make_helper()

    updated_ids = helper._handle_query_result(
        {"getLocation": {"devices": [_gateway_payload(connection_status)]}}
    )

    gateway = devices.find_device(GATEWAY_HILO_ID)
    assert gateway is not None
    assert updated_ids == [GATEWAY_HILO_ID]
    assert gateway.hilo_id == GATEWAY_HILO_ID
    assert gateway.identifier == "AA11BB22CC33"
    assert gateway.available is expected_available
    assert gateway.get_value("online_status") == connection_status


def test_gateway_device_subscription_updates_availability_and_notifies_callback() -> (
    None
):
    """onAnyDeviceUpdated updates Gateway availability and passes its hilo_id to callback."""
    helper, _, gateway = _make_helper_with_gateway()
    notified: list[str] = []
    sse_payload: dict[str, object] = {
        "data": {
            "onAnyDeviceUpdated": {
                "device": _gateway_payload("DISCONNECTED", device_type="hub"),
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


def test_unknown_hilo_id_reading_does_not_overwrite_gateway_availability() -> None:
    """GraphQL readings for an unknown hiloId must not fall back to the Gateway device."""
    helper, _, gateway = _make_helper_with_gateway()
    notified: list[str] = []
    sse_payload: dict[str, object] = {
        "data": {
            "onAnyDeviceUpdated": {
                "device": {
                    "deviceType": "Switch",
                    "hiloId": "urn:hilo:philo:unpaired-switch:0",
                    "connectionStatus": "DISCONNECTED",
                    "state": "OFF",
                }
            }
        }
    }

    helper._handle_sse_message(
        sse_payload, helper._handle_device_subscription_result, notified.append
    )

    assert gateway.available is True
    assert notified == []


async def test_resync_after_reconnect_updates_gateway_and_notifies_callback() -> None:
    """SSE reconnect resync parses getLocation and forwards updated hilo_ids to callback."""
    helper, devices, gateway = _make_helper_with_gateway()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "data": {"getLocation": {"devices": [_gateway_payload("DISCONNECTED")]}}
    }
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client_cm = AsyncMock()
    client_cm.__aenter__.return_value = client

    notified: list[str] = []
    with patch("pyhilo.graphql.httpx.AsyncClient", return_value=client_cm):
        await helper._resync_after_reconnect(devices.location_hilo_id, notified.append)

    assert gateway.available is False
    assert notified == [GATEWAY_HILO_ID]


def test_location_subscription_updates_devices_and_notifies_each_hilo_id() -> None:
    """onAnyLocationUpdated updates device availability and invokes callback per hilo_id."""
    helper, devices, gateway = _make_helper_with_gateway()
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
    weather_station = devices.generate_device(
        {
            "id": 102,
            "hilo_id": "urn:hilo:netatmo:station:0",
            "name": "Weather Station",
            "type": "IndoorWeatherStation",
            "provider": 2,
            "supportedAttributes": "Disconnected",
            "settableAttributes": "",
            "Disconnected": {"value": True},
        }
    )
    devices.devices.extend([tstat, switch, weather_station])

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
    assert weather_station.available is False
    assert notified == [GATEWAY_HILO_ID, TSTAT_HILO_ID, SWITCH_HILO_ID]
