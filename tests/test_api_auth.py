import base64
import json
import logging
from typing import Any

import pytest

from pyhilo import API, AbstractAuth
from pyhilo.const import API_HOSTNAME

URN = "urn:hilo:crm:abc-123"


def _jwt(claims: dict[str, Any]) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"header.{payload.decode()}.signature"


TOKEN = _jwt({"urn:com:hiloenergie:profile:location_hilo_id": [URN]})


class FakeAuth(AbstractAuth):
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self.calls = 0

    async def async_get_access_token(self) -> str:
        token = self._tokens[min(self.calls, len(self._tokens) - 1)]
        self.calls += 1
        return token


class FakeResponse:
    headers = {"content-type": "application/json"}

    async def json(self, content_type: Any = None) -> dict[str, Any]:
        return {"ok": True}

    def raise_for_status(self) -> None:
        pass

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


class FakeSession:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        return FakeResponse()


class FakeOAuth2Session:
    """Duck-types Home Assistant's OAuth2Session."""

    def __init__(self, token: str, valid: bool = True) -> None:
        self.token = {"access_token": token}
        self.valid_token = valid
        self.ensure_calls = 0

    async def async_ensure_token_valid(self) -> None:
        self.ensure_calls += 1
        self.valid_token = True


def test_import_does_not_require_homeassistant() -> None:
    import sys

    assert "homeassistant" not in sys.modules


async def test_async_create_fetches_token_through_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop(self: API) -> None:
        pass

    monkeypatch.setattr(API, "_async_post_init", _noop)
    auth = FakeAuth([TOKEN])

    api = await API.async_create(session=FakeSession(), auth=auth)  # type: ignore[arg-type]

    assert auth.calls == 1
    assert api.urn == URN


async def test_each_request_uses_a_fresh_token_from_auth() -> None:
    session = FakeSession()
    auth = FakeAuth([TOKEN, "refreshed-token"])
    api = API(session=session, auth=auth)  # type: ignore[arg-type]

    await api._async_request("get", "/first")
    await api._async_request("get", "/second")

    assert auth.calls == 2
    assert session.requests[0]["headers"]["authorization"] == f"Bearer {TOKEN}"
    assert session.requests[1]["headers"]["authorization"] == "Bearer refreshed-token"
    assert session.requests[1]["headers"]["Host"] == API_HOSTNAME


async def test_urn_is_none_for_token_without_claim() -> None:
    api = API(session=FakeSession(), auth=FakeAuth([_jwt({})]))  # type: ignore[arg-type]

    await api.async_get_access_token()

    assert api.urn is None


def test_auth_is_required() -> None:
    with pytest.raises(ValueError):
        API(session=FakeSession())  # type: ignore[arg-type]


def test_auth_and_oauth_session_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError):
        API(
            session=FakeSession(),  # type: ignore[arg-type]
            auth=FakeAuth([TOKEN]),
            oauth_session=FakeOAuth2Session(TOKEN),
        )


async def test_deprecated_oauth_session_still_works(
    caplog: pytest.LogCaptureFixture,
) -> None:
    oauth_session = FakeOAuth2Session(TOKEN, valid=False)

    with caplog.at_level(logging.WARNING):
        api = API(session=FakeSession(), oauth_session=oauth_session)  # type: ignore[arg-type]

    assert "deprecated" in caplog.text
    assert await api.async_get_access_token() == TOKEN
    assert oauth_session.ensure_calls == 1
    assert api.urn == URN
