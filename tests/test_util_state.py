import os

import pytest

from pyhilo.util.state import (
    StateDict,
    TokenDict,
    FirebaseDict,
    AndroidDeviceDict,
    _get_defaults,
    _write_state,
    get_state,
    set_state,
)


class TestGetDefaults:
    def test_state_dict(self):
        defaults = _get_defaults(StateDict)
        assert "token" in defaults
        assert "registration" in defaults
        assert "firebase" in defaults
        assert "android" in defaults
        assert defaults["token"] is not None

    def test_nested_defaults(self):
        defaults = _get_defaults(StateDict)
        assert isinstance(defaults["token"], dict)
        assert defaults["token"]["access"] is None
        assert defaults["token"]["refresh"] is None

    def test_firebase_dict(self):
        defaults = _get_defaults(FirebaseDict)
        assert "fid" in defaults
        assert "name" in defaults
        assert "token" in defaults

    def test_android_dict(self):
        defaults = _get_defaults(AndroidDeviceDict)
        assert "token" in defaults
        assert "device_id" in defaults

    def test_token_dict(self):
        defaults = _get_defaults(TokenDict)
        assert "access" in defaults
        assert "refresh" in defaults
        assert "expires_at" in defaults

    def test_all_none_values(self):
        defaults = _get_defaults(StateDict)
        assert defaults["token"]["access"] is None


class TestWriteState:
    def test_writes_yaml(self, tmp_path):
        state_file = str(tmp_path / "state.yaml")
        state = {"token": {"access": "abc", "refresh": "def"}}
        _write_state(state_file, state)
        assert os.path.exists(state_file)
        with open(state_file) as f:
            content = f.read()
        assert "access" in content

    def test_atomic_write(self, tmp_path):
        state_file = str(tmp_path / "state.yaml")
        _write_state(state_file, {"key": "value1"})
        _write_state(state_file, {"key": "value2"})
        with open(state_file) as f:
            content = f.read()
        assert "value2" in content


class TestGetState:
    async def test_missing_file_returns_defaults(self, tmp_path):
        state_file = str(tmp_path / "nonexistent.yaml")
        result = await get_state(state_file)
        assert result == _get_defaults(StateDict)

    async def test_valid_file(self, tmp_path):
        state_file = str(tmp_path / "state.yaml")
        _write_state(state_file, {"token": {"access": "test123"}})
        result = await get_state(state_file)
        assert result["token"]["access"] == "test123"

    async def test_empty_file_returns_defaults(self, tmp_path):
        state_file = str(tmp_path / "state.yaml")
        with open(state_file, "w") as f:
            f.write("")
        result = await get_state(state_file)
        assert result == _get_defaults(StateDict)

    async def test_corrupted_yaml_returns_defaults(self, tmp_path):
        state_file = str(tmp_path / "state.yaml")
        with open(state_file, "w") as f:
            f.write("{{invalid yaml:::")
        result = await get_state(state_file)
        assert result == _get_defaults(StateDict)

    async def test_non_dict_yaml_returns_defaults(self, tmp_path):
        state_file = str(tmp_path / "state.yaml")
        with open(state_file, "w") as f:
            f.write("- just\n- a\n- list\n")
        result = await get_state(state_file)
        assert result == _get_defaults(StateDict)


class TestSetState:
    async def test_set_creates_file(self, tmp_path):
        state_file = str(tmp_path / "state.yaml")
        await set_state(state_file, "firebase", {"fid": "test-fid", "name": None, "token": {"access": None, "refresh": None, "expires_at": None}})
        result = await get_state(state_file)
        assert result["firebase"]["fid"] == "test-fid"

    async def test_set_merges_with_existing(self, tmp_path):
        state_file = str(tmp_path / "state.yaml")
        await set_state(state_file, "firebase", {"fid": "first", "name": None, "token": {"access": None, "refresh": None, "expires_at": None}})
        await set_state(state_file, "android", {"token": "device-token", "device_id": 0})
        result = await get_state(state_file)
        assert result["firebase"]["fid"] == "first"
        assert result["android"]["token"] == "device-token"

    async def test_set_merges_within_key(self, tmp_path):
        state_file = str(tmp_path / "state.yaml")
        await set_state(state_file, "firebase", {"fid": "first", "name": None, "token": {"access": None, "refresh": None, "expires_at": None}})
        await set_state(state_file, "firebase", {"fid": "second", "name": "updated", "token": {"access": "tok", "refresh": None, "expires_at": None}})
        result = await get_state(state_file)
        assert result["firebase"]["fid"] == "second"
        assert result["firebase"]["name"] == "updated"
