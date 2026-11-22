"""Tests for Event updates, using message shapes captured from a real Hilo event."""

import pytest

from pyhilo.event import Event, OptOutDevice

EVENT_ID = 101
THERMOSTAT_A = 1001
THERMOSTAT_B = 1002
CHARGER = 2001


def _device(device_id: int, opt_out: bool = False) -> dict[str, object]:
    return {
        "id": device_id,
        "deviceUid": f"uid-{device_id}",
        "deviceType": "Thermostat",
        "name": f"Device {device_id}",
        "roomName": "Room",
        "optOut": opt_out,
        "preheat": False,
    }


def _initial_message(
    devices: list[dict[str, object]], baseline_wh: float = 0.0
) -> dict[str, object]:
    """Shape of ChallengeDetailsInitialValuesReceived."""
    return {
        "id": EVENT_ID,
        "progress": "scheduled",
        "isParticipating": True,
        "isConfigurable": False,
        "period": "PM",
        "phases": {
            "settingsDeadlineUTC": "2026-11-17T05:00:00Z",
            "preheatStartDateUTC": "2026-11-17T19:00:00Z",
            "preheatEndDateUTC": "2026-11-17T21:00:00Z",
            "reductionStartDateUTC": "2026-11-17T21:00:00Z",
            "reductionEndDateUTC": "2026-11-18T01:00:00Z",
            "recoveryStartDateUTC": "2026-11-18T01:00:00Z",
            "recoveryEndDateUTC": "2026-11-18T02:00:00Z",
        },
        "parameters": {"mode": "Extreme", "devices": devices},
        "consumption": {"baselineWh": baseline_wh},
        "optOutDevices": [],
    }


def _opt_out(device_id: int, trigger_type_id: int = 3) -> OptOutDevice:
    return {
        "id": device_id,
        "eventDateUtc": "2026-11-17T21:00:00.4189642Z",
        "triggerTypeId": trigger_type_id,
        "triggerApplicationId": 1 if trigger_type_id == 3 else None,
    }


def _opt_out_notice(*opt_outs: OptOutDevice) -> dict[str, object]:
    """Shape of ChallengeDetailsUpdatedValuesReceived: everything but the opt-outs is None."""
    return {
        "id": EVENT_ID,
        "progress": None,
        "isParticipating": None,
        "isConfigurable": None,
        "currentPhase": None,
        "parameters": None,
        "report": None,
        "optOutDevices": list(opt_outs),
    }


def _event(devices: list[dict[str, object]] | None = None) -> Event:
    devices = (
        devices
        if devices is not None
        else [_device(THERMOSTAT_A), _device(THERMOSTAT_B), _device(CHARGER)]
    )
    return Event(**_initial_message(devices))


@pytest.mark.parametrize(
    ("devices", "expected"),
    [
        pytest.param([_device(THERMOSTAT_A)], 0, id="none_opted_out"),
        pytest.param(
            [_device(THERMOSTAT_A, opt_out=True), _device(THERMOSTAT_B)],
            1,
            id="one_flagged",
        ),
    ],
)
def test_initial_opt_out_count_comes_from_device_flags(
    devices: list[dict[str, object]], expected: int
) -> None:
    assert _event(devices).opt_out_devices == expected


@pytest.mark.parametrize(
    ("notices", "expected"),
    [
        pytest.param([[_opt_out(THERMOSTAT_A)]], 1, id="single_notice"),
        pytest.param(
            [[_opt_out(THERMOSTAT_A)], [_opt_out(THERMOSTAT_A, trigger_type_id=1)]],
            1,
            id="same_device_repeated",
        ),
        pytest.param(
            [[_opt_out(THERMOSTAT_A)], [_opt_out(THERMOSTAT_B)]],
            2,
            id="distinct_devices",
        ),
        pytest.param(
            [[_opt_out(THERMOSTAT_A), _opt_out(THERMOSTAT_B)]],
            2,
            id="several_in_one_notice",
        ),
    ],
)
def test_opt_out_notices_count_each_device_once(
    notices: list[list[OptOutDevice]], expected: int
) -> None:
    event = _event()

    for opt_outs in notices:
        event.update(_opt_out_notice(*opt_outs))

    assert event.opt_out_devices == expected


def test_opt_out_notice_and_device_flag_for_same_device_count_once() -> None:
    event = _event([_device(THERMOSTAT_A, opt_out=True), _device(THERMOSTAT_B)])

    event.update(_opt_out_notice(_opt_out(THERMOSTAT_A)))

    assert event.opt_out_devices == 1


@pytest.mark.parametrize(
    ("attribute", "expected"),
    [
        pytest.param("progress", "scheduled", id="progress"),
        pytest.param("participating", True, id="participating"),
        pytest.param("total_devices", 3, id="total_devices"),
        pytest.param("mode", "Extreme", id="mode"),
        pytest.param("period", "pm", id="period"),
    ],
)
def test_opt_out_notice_keeps_other_fields(attribute: str, expected: object) -> None:
    event = _event()

    event.update(_opt_out_notice(_opt_out(THERMOSTAT_A)))

    assert getattr(event, attribute) == expected


@pytest.mark.parametrize(
    ("baseline_wh", "expected_kwh"),
    [
        pytest.param(0.0, 14.76, id="zero_before_baseline_is_computed"),
        pytest.param(14777.26, 14.78, id="revised_baseline"),
    ],
)
def test_update_baseline(baseline_wh: float, expected_kwh: float) -> None:
    event = _event()
    event.update_allowed_wh(14762.21)

    event.update({"id": EVENT_ID, "consumption": {"baselineWh": baseline_wh}})

    assert event.allowed_kWh == expected_kwh


def test_update_leaves_used_wh_to_consumption_messages() -> None:
    event = _event()
    event.update_wh(5987.98)

    event.update({"id": EVENT_ID, "consumption": {"currentWh": 0.0}})

    assert event.used_kWh == 5.99
