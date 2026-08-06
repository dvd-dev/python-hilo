from unittest.mock import AsyncMock, MagicMock

from pyhilo.const import HILO_READING_TYPES, STATE_UNKNOWN
from pyhilo.device import DeviceAttribute, DeviceReading, get_device_attributes
from pyhilo.device.climate import Climate, as_list


def _api():
    api = MagicMock()
    api.dev_atts.side_effect = lambda attribute, value_type=None: next(
        (
            a
            for a in get_device_attributes()
            if a.hilo_attribute == attribute or a.attr == attribute
        ),
        attribute,
    )
    api.log_traces = False
    return api


def _climate(**readings):
    """Build a Climate device carrying the given readings, by Hilo attribute name."""
    device = Climate(
        _api(), id=1, hilo_id="h-1", location_id=10, name="T", type="Thermostat24V"
    )
    for hilo_attribute, value in readings.items():
        device.update_readings(
            DeviceReading(
                deviceId=1,
                locationId=10,
                timeStampUTC="2026-08-02T12:00:00Z",
                value=value,
                device_attribute=DeviceAttribute(
                    hilo_attribute, HILO_READING_TYPES[hilo_attribute]
                ),
            )
        )
    return device


class TestAsList:
    def test_none_is_empty(self):
        assert as_list(None) == []

    def test_real_list_is_kept(self):
        assert as_list(["ON", "AUTO"]) == ["ON", "AUTO"]

    def test_comma_separated_string_is_split(self):
        assert as_list("ON, AUTO ,CIRCULATE") == ["ON", "AUTO", "CIRCULATE"]

    def test_empty_list_stays_empty(self):
        assert as_list([]) == []


class TestLowVoltageDetection:
    def test_baseboard_is_not_low_voltage(self):
        assert _climate(CurrentTemperature=21).is_low_voltage is False

    def test_device_reporting_a_mode_is_low_voltage(self):
        assert _climate(Thermostat24VMode="COOL").is_low_voltage is True

    def test_device_reporting_unknown_mode_is_not_low_voltage(self):
        assert _climate(Thermostat24VMode=STATE_UNKNOWN).is_low_voltage is False


class TestLowVoltageProperties:
    def test_reads_mode_and_vocabularies(self):
        device = _climate(
            Thermostat24VMode="COOL",
            Thermostat24VAllowedMode=["HEAT", "OFF", "COOL"],
            Thermostat24VAllowedFanMode=["ON", "AUTO"],
            FanMode="ON",
        )
        assert device.low_voltage_mode == "COOL"
        assert device.allowed_modes == ["HEAT", "OFF", "COOL"]
        assert device.allowed_fan_modes == ["ON", "AUTO"]
        assert device.fan_mode == "ON"

    def test_reads_cool_setpoints_as_floats(self):
        device = _climate(
            Thermostat24VMode="COOL",
            CoolTemperatureSet=24,
            MinCoolSetpoint=10,
            MaxCoolSetpoint=32,
        )
        assert device.cool_setpoint == 24.0
        assert device.min_cool_setpoint == 10.0
        assert device.max_cool_setpoint == 32.0

    def test_missing_values_are_none(self):
        device = _climate(Thermostat24VMode="HEAT")
        assert device.cool_setpoint is None
        assert device.min_cool_setpoint is None
        assert device.current_humidity is None

    def test_humidity_is_an_int(self):
        device = _climate(Thermostat24VMode="COOL", Humidity=57)
        assert device.current_humidity == 57

    def test_humidity_rounds_rather_than_truncates(self):
        device = _climate(Thermostat24VMode="COOL", Humidity=57.8)
        assert device.current_humidity == 58

    def test_unknown_state_is_treated_as_absent(self):
        device = _climate(
            Thermostat24VMode="COOL",
            FanMode=STATE_UNKNOWN,
            CurrentState=STATE_UNKNOWN,
        )
        assert device.fan_mode is None
        assert device.current_state is None


class TestSetTemperature:
    async def test_low_voltage_device_delegates_to_low_voltage_state(self):
        device = _climate(Thermostat24VMode="COOL", TargetTemperature=19)
        device.async_set_low_voltage_state = AsyncMock()
        await device.async_set_temperature(21)
        device.async_set_low_voltage_state.assert_awaited_once_with(
            target_temperature=21
        )

    async def test_non_low_voltage_device_still_uses_set_attribute(self):
        device = _climate(TargetTemperature=19)
        device.set_attribute = AsyncMock()
        device.async_set_low_voltage_state = AsyncMock()
        await device.async_set_temperature(21)
        device.set_attribute.assert_awaited_once_with("target_temperature", "21")
        device.async_set_low_voltage_state.assert_not_awaited()


class TestSetLowVoltageState:
    def _device(self):
        device = _climate(
            Thermostat24VMode="COOL",
            TargetTemperature=19,
            CoolTemperatureSet=24,
            FanMode="ON",
        )
        device.set_attributes = AsyncMock()
        return device

    async def test_changing_one_value_still_sends_the_triplet(self):
        device = self._device()
        await device.async_set_low_voltage_state(cool_setpoint=22)
        device.set_attributes.assert_awaited_once_with(
            {
                "Thermostat24VMode": "COOL",
                "TargetTemperature": 19.0,
                "CoolTemperatureSet": 22,
            }
        )

    async def test_mode_change_keeps_current_setpoints(self):
        device = self._device()
        await device.async_set_low_voltage_state(mode="HEAT")
        device.set_attributes.assert_awaited_once_with(
            {
                "Thermostat24VMode": "HEAT",
                "TargetTemperature": 19.0,
                "CoolTemperatureSet": 24.0,
            }
        )

    async def test_fan_mode_is_added_to_the_triplet(self):
        device = self._device()
        await device.async_set_low_voltage_state(fan_mode="AUTO")
        device.set_attributes.assert_awaited_once_with(
            {
                "Thermostat24VMode": "COOL",
                "TargetTemperature": 19.0,
                "CoolTemperatureSet": 24.0,
                "FanMode": "AUTO",
            }
        )

    async def test_absent_values_are_not_sent(self):
        device = _climate(Thermostat24VMode="HEAT", TargetTemperature=21)
        device.set_attributes = AsyncMock()
        await device.async_set_low_voltage_state(target_temperature=22)
        device.set_attributes.assert_awaited_once_with(
            {"Thermostat24VMode": "HEAT", "TargetTemperature": 22}
        )
