from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pyhilo.const import HILO_READING_TYPES
from pyhilo.device import DeviceAttribute, DeviceReading, HiloDevice, get_device_attributes


class TestDeviceAttribute:
    def test_onoff_maps_to_is_on(self):
        attr = DeviceAttribute("OnOff", "OnOff")
        assert attr.attr == "is_on"
        assert attr.value_type == "boolean"

    def test_camel_case_conversion(self):
        attr = DeviceAttribute("CurrentTemperature", "Celsius")
        assert attr.attr == "current_temperature"
        assert attr.value_type == "°C"

    def test_null_value_type(self):
        attr = DeviceAttribute("Disconnected", "null")
        assert attr.value_type == "boolean"

    def test_known_unit_conversion(self):
        attr = DeviceAttribute("Power", "Watt")
        assert attr.value_type == "W"

    def test_unknown_unit_conversion(self):
        attr = DeviceAttribute("Foo", "SomeUnknownType")
        assert attr.value_type == "some_unknown_type"

    def test_frozen_equality(self):
        a1 = DeviceAttribute("Power", "Watt")
        a2 = DeviceAttribute("Power", "Watt")
        assert a1 == a2

    def test_frozen_inequality_different_attr(self):
        a1 = DeviceAttribute("Power", "Watt")
        a2 = DeviceAttribute("Intensity", "Percentage")
        assert a1 != a2

    def test_equality_uses_attr_only(self):
        a1 = DeviceAttribute("Power", "Watt")
        a2 = DeviceAttribute("Power", "SomethingElse")
        assert a1 == a2


class TestGetDeviceAttributes:
    def test_returns_list(self):
        attrs = get_device_attributes()
        assert isinstance(attrs, list)
        assert len(attrs) > 0

    def test_all_have_attr_set(self):
        attrs = get_device_attributes()
        for attr in attrs:
            assert attr.attr is not None
            assert isinstance(attr.hilo_attribute, str)


class TestDeviceReading:
    def _make_reading(self, **overrides):
        defaults = {
            "deviceId": 1,
            "hiloId": "hilo-123",
            "locationId": 10,
            "timeStampUTC": "2024-01-15T10:30:00Z",
            "value": 42.0,
            "device_attribute": DeviceAttribute("Power", "Watt"),
        }
        defaults.update(overrides)
        return DeviceReading(**defaults)

    def test_basic_construction(self):
        r = self._make_reading()
        assert r.device_id == 1
        assert r.hilo_id == "hilo-123"
        assert r.value == 42.0
        assert r.unit_of_measurement == "W"

    def test_timestamp_converted(self):
        r = self._make_reading()
        assert isinstance(r.time_stamp, datetime)

    def test_boolean_attribute_has_no_unit(self):
        r = self._make_reading(
            device_attribute=DeviceAttribute("OnOff", "OnOff"),
            value=True,
        )
        assert r.unit_of_measurement == ""

    def test_equality_by_attr_name(self):
        r1 = self._make_reading(value=10.0)
        r2 = self._make_reading(value=20.0)
        assert r1 == r2

    def test_inequality_different_attr(self):
        r1 = self._make_reading(device_attribute=DeviceAttribute("Power", "Watt"))
        r2 = self._make_reading(device_attribute=DeviceAttribute("Intensity", "Percentage"))
        assert r1 != r2

    def test_repr(self):
        r = self._make_reading()
        rep = repr(r)
        assert "power" in rep
        assert "42.0" in rep

    def test_equality_with_non_reading(self):
        r = self._make_reading()
        assert r != "not a reading"


def _mock_api(**overrides):
    api = MagicMock()
    api.log_traces = False
    api.dev_atts.side_effect = lambda attr, value_type=None: next(
        (
            x
            for x in get_device_attributes()
            if x.hilo_attribute == attr or x.attr == attr
        ),
        DeviceAttribute(attr, HILO_READING_TYPES.get(value_type, "null"))
        if value_type
        else attr,
    )
    for k, v in overrides.items():
        setattr(api, k, v)
    return api


class TestHiloDevice:
    def test_basic_init(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, name="Test Device", type="Thermostat")
        assert d.id == 1
        assert d.name == "Test Device"
        assert d.type == "Thermostat"

    def test_provider_lookup(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, provider=1)
        assert d.manufacturer == "Hilo"

    def test_unknown_provider(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, provider=99)
        assert d.manufacturer == "Unknown (99)"

    def test_identifier_set_directly(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, identifier="ABC123")
        assert d.identifier == "ABC123"

    def test_model_number_maps_to_model(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, model_number="X100")
        assert d.model == "X100"

    def test_model_prefix_stripped(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, model_number="Model_EQ000016")
        assert d.model == "EQ000016"

    def test_thermostat_default_model(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, type="Thermostat")
        assert d.model == "EQ000016"

    def test_jasco_detection(self):
        api = _mock_api()
        d = HiloDevice(
            api,
            id=1,
            provider=1,
            model_number="43080",
            type="LightSwitch",
        )
        assert d.manufacturer == "Jasco Enbrighten"

    def test_jasco_outlet_type_change(self):
        api = _mock_api()
        d = HiloDevice(
            api,
            id=1,
            provider=1,
            model_number="42405",
            type="LightSwitch",
        )
        assert d.type == "Outlet"
        assert d.manufacturer == "Jasco Enbrighten"

    def test_supported_attributes_from_csv(self):
        api = _mock_api()
        d = HiloDevice(
            api,
            id=1,
            supported_attributes="Power, Intensity, OnOff",
        )
        assert len(d.supported_attributes) == 3
        assert d.supported_attributes[0].hilo_attribute == "Power"

    def test_empty_supported_attributes_gets_disconnected(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, supported_attributes="None")
        assert len(d.supported_attributes) == 1
        assert d.supported_attributes[0].hilo_attribute == "Disconnected"

    def test_update_readings(self):
        api = _mock_api()
        d = HiloDevice(api, id=1)
        reading = DeviceReading(
            **{
                "deviceId": 1,
                "hiloId": "h-1",
                "locationId": 10,
                "timeStampUTC": "2024-01-15T10:30:00Z",
                "value": 100.0,
                "device_attribute": DeviceAttribute("Power", "Watt"),
            }
        )
        d.update_readings(reading)
        assert d.get_value("power") == 100.0

    def test_update_readings_replaces_existing(self):
        api = _mock_api()
        d = HiloDevice(api, id=1)
        da = DeviceAttribute("Power", "Watt")
        r1 = DeviceReading(
            deviceId=1, hiloId="h-1", locationId=10,
            timeStampUTC="2024-01-15T10:30:00Z", value=100.0,
            device_attribute=da,
        )
        r2 = DeviceReading(
            deviceId=1, hiloId="h-1", locationId=10,
            timeStampUTC="2024-01-15T11:00:00Z", value=200.0,
            device_attribute=da,
        )
        d.update_readings(r1)
        d.update_readings(r2)
        assert len([r for r in d.readings if r.device_attribute == da]) == 1
        assert d.get_value("power") == 200.0

    def test_get_value_default(self):
        api = _mock_api()
        d = HiloDevice(api, id=1)
        assert d.get_value("nonexistent") == "unknown"

    def test_get_value_custom_default(self):
        api = _mock_api()
        d = HiloDevice(api, id=1)
        assert d.get_value("nonexistent", 0) == 0

    def test_has_attribute(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, supported_attributes="Power, OnOff")
        assert d.has_attribute("is_on") is True
        assert d.has_attribute("power") is True
        assert d.has_attribute("intensity") is False

    def test_is_on(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, OnOff=True)
        assert d.is_on is True

    def test_available(self):
        api = _mock_api()
        d = HiloDevice(api, id=1)
        assert d.available is False

    def test_available_when_not_disconnected(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, Disconnected=False)
        assert d.available is True

    def test_hilo_attributes_excludes_humidity(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, supported_attributes="Power, Humidity, OnOff")
        assert "Power" in d.hilo_attributes

    def test_attributes_includes_humidity_snake_case(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, supported_attributes="Power, Humidity, OnOff")
        assert "humidity" in d.attributes

    def test_equality_by_id(self):
        api = _mock_api()
        d1 = HiloDevice(api, id=1, name="A")
        d2 = HiloDevice(api, id=1, name="B")
        assert d1 == d2

    def test_inequality_by_id(self):
        api = _mock_api()
        d1 = HiloDevice(api, id=1)
        d2 = HiloDevice(api, id=2)
        assert d1 != d2

    def test_eq_with_non_device(self):
        api = _mock_api()
        d = HiloDevice(api, id=1)
        assert d != "not a device"

    def test_str(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, type="Thermostat", name="Living Room")
        s = str(d)
        assert "Thermostat" in s
        assert "Living Room" in s
        assert "1" in s

    def test_update_with_dict_value(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, Power={"value": 150.0})
        assert d.get_value("power") == 150.0

    def test_get_attribute(self):
        api = _mock_api()
        d = HiloDevice(api, id=1, Power={"value": 42.0})
        result = d.get_attribute("power")
        assert result is not None
        assert result.value == 42.0

    def test_get_attribute_unknown(self):
        api = _mock_api()
        d = HiloDevice(api, id=1)
        result = d.get_attribute("nonexistent")
        assert result is None
