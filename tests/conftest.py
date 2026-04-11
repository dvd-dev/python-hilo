import sys
import types


def pytest_configure(config):
    ha = types.ModuleType("homeassistant")
    ha_helpers = types.ModuleType("homeassistant.helpers")
    oauth2 = types.ModuleType("homeassistant.helpers.config_entry_oauth2_flow")
    oauth2.OAuth2Session = type("OAuth2Session", (), {})
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.config_entry_oauth2_flow"] = oauth2


def pytest_unconfigure(config):
    sys.modules.pop("homeassistant", None)
    sys.modules.pop("homeassistant.helpers", None)
    sys.modules.pop("homeassistant.helpers.config_entry_oauth2_flow", None)
