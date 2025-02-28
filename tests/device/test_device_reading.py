"""Tests for `device/__init__.py`."""

import unittest
from pyhilo.device import DeviceReading


class TestDeviceReading(unittest.TestCase):
    """Unit tests for the class DeviceReading."""

    def test_eq(self) -> None:
        """Test the equality operator of the DeviceReading class."""
        device_reading_1 = DeviceReading(
            device_attribute={"value_type": "int"})
        device_reading_2 = DeviceReading(
            device_attribute={"value_type": "int"})
        device_reading_3 = DeviceReading(
            device_attribute={"value_type": "boolean"})
        self.assertEqual(device_reading_1, device_reading_2)
        self.assertNotEqual(device_reading_1, device_reading_3)
