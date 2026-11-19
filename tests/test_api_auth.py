import base64
import json
import logging
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyhilo import API, AbstractAuth
from pyhilo.const import API_HOSTNAME

URN = "urn:hilo:crm:abc-123"


def _jwt(claims: dict[str, Any]) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"header.{payload.decode()}.signature"


TOKEN = _jwt({"urn:com:hiloenergie:profile:location_hilo_id": [URN]})


@pytest.fixture
def mock_session() -> MagicMock:
    """Fixture providing a mock aiohttp ClientSession with async context manager response."""
    session = MagicMock()
    response = MagicMock()
    response.headers = {"content-type": "application/json"}
    response.json = AsyncMock(return_value={"ok": True})
    response.raise_for_status = MagicMock()

    # Configure async context manager on session.request(...)
    session.request.return_value.__aenter__ = AsyncMock(return_value=response)
    session.request.return_value.__aexit__ = AsyncMock(return_value=None)
    return session


def test_import_does_not_require_homeassistant() -> None:
    assert "homeassistant" not in sys.modules


async def test_async_create_fetches_token_through_auth(
    mock_session: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop(self: API) -> None:
        pass

    monkeypatch.setattr(API, "_async_post_init", _noop)
    auth = AsyncMock(spec=AbstractAuth)
    auth.async_get_access_token.return_value = TOKEN

    api = await API.async_create(session=mock_session, auth=auth)

    auth.async_get_access_token.assert_awaited_once()
    assert api.urn == URN


async def test_each_request_uses_a_fresh_token_from_auth(
    mock_session: MagicMock,
) -> None:
    auth = AsyncMock(spec=AbstractAuth)
    auth.async_get_access_token.side_effect = [TOKEN, "refreshed-token"]
    api = API(session=mock_session, auth=auth)

    await api._async_request("get", "/first")
    await api._async_request("get", "/second")

    assert auth.async_get_access_token.await_count == 2
    assert mock_session.request.call_count == 2

    first_call_headers = mock_session.request.call_args_list[0].kwargs["headers"]
    second_call_headers = mock_session.request.call_args_list[1].kwargs["headers"]

    assert first_call_headers["authorization"] == f"Bearer {TOKEN}"
    assert second_call_headers["authorization"] == "Bearer refreshed-token"
    assert second_call_headers["Host"] == API_HOSTNAME


@pytest.mark.parametrize(
    ("claims", "expected_urn"),
    [
        ({"urn:com:hiloenergie:profile:location_hilo_id": [URN]}, URN),
        ({"urn:com:hiloenergie:profile:location_hilo_id": []}, None),
        ({"urn:com:hiloenergie:profile:location_hilo_id": "not-a-list"}, None),
        ({}, None),
    ],
)
async def test_urn_extraction(
    mock_session: MagicMock, claims: dict[str, Any], expected_urn: str | None
) -> None:
    auth = AsyncMock(spec=AbstractAuth)
    auth.async_get_access_token.return_value = _jwt(claims)
    api = API(session=mock_session, auth=auth)

    await api.async_get_access_token()

    assert api.urn == expected_urn


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({}, "An auth provider is required"),
        (
            {"auth": MagicMock(spec=AbstractAuth), "oauth_session": MagicMock()},
            "Pass either auth or oauth_session, not both",
        ),
    ],
)
def test_invalid_auth_configuration(
    mock_session: MagicMock, kwargs: dict[str, Any], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        API(session=mock_session, **kwargs)


async def test_deprecated_oauth_session_still_works(
    mock_session: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    oauth_session = MagicMock(
        valid_token=False,
        token={"access_token": TOKEN},
        async_ensure_token_valid=AsyncMock(),
    )

    with caplog.at_level(logging.WARNING):
        api = API(session=mock_session, oauth_session=oauth_session)

    assert "deprecated" in caplog.text
    assert await api.async_get_access_token() == TOKEN
    oauth_session.async_ensure_token_valid.assert_awaited_once()
    assert api.urn == URN
