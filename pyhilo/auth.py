"""Authentication interface for the Hilo API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pyhilo.const import LOG


class AbstractAuth(ABC):
    """Supplies valid Hilo access tokens to :class:`pyhilo.api.API`.

    Applications subclass this and implement :meth:`async_get_access_token`.
    In Home Assistant, the integration wraps its ``OAuth2Session``; standalone
    scripts can return a static token or run their own refresh logic.
    """

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token, refreshing it if needed."""


class _LegacyOAuthSessionAuth(AbstractAuth):
    """Adapts a Home Assistant ``OAuth2Session`` passed as ``oauth_session``.

    Deprecated: kept so integration releases that still pass ``oauth_session``
    keep working. The session is duck-typed so pyhilo never imports
    Home Assistant.
    """

    def __init__(self, oauth_session: Any) -> None:
        LOG.warning(
            "Passing oauth_session to pyhilo.API is deprecated and will be "
            "removed in a future release; pass an AbstractAuth via auth instead"
        )
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()
        return str(self._oauth_session.token["access_token"])
