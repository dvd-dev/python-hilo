"""Custom OAuth2 implementation."""
import base64
import hashlib
import os
import re
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import LocalOAuth2Implementation

from pyhilo.const import (
    AUTH_AUTHORIZE,
    AUTH_CHALLENGE_METHOD,
    AUTH_CLIENT_ID,
    AUTH_SCOPE,
    AUTH_TOKEN,
    DOMAIN,
)


class AuthCodeWithPKCEImplementation(LocalOAuth2Implementation):  # type: ignore[misc]
    """Custom OAuth2 implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize AuthCodeWithPKCEImplementation."""
        super().__init__(
            hass,
            DOMAIN,
            AUTH_CLIENT_ID,
            "",
            AUTH_AUTHORIZE,
            AUTH_TOKEN,
        )
        self._code_verifier = self._get_code_verifier()
        self._code_challenge = self._get_code_challange(self._code_verifier)

    # ... Override AbstractOAuth2Implementation details
    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Hilo"

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": AUTH_SCOPE,
            "code_challenge": self._code_challenge,
            "code_challenge_method": AUTH_CHALLENGE_METHOD,
        }

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return cast(
            dict,
            await self._token_request(
                {
                    "grant_type": "authorization_code",
                    "code": external_data["code"],
                    "redirect_uri": external_data["state"]["redirect_uri"],
                    "code_verifier": self._code_verifier,
                },
            ),
        )

    # Ref : https://blog.sanghviharshit.com/reverse-engineering-private-api-oauth-code-flow-with-pkce/
    def _get_code_verifier(self) -> str:
        code = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        return re.sub("[^a-zA-Z0-9]+", "", code)

    def _get_code_challange(self, verifier: str) -> str:
        sha_verifier = hashlib.sha256(verifier.encode("utf-8")).digest()
        code = base64.urlsafe_b64encode(sha_verifier).decode("utf-8")
        return code.replace("=", "")
