import base64
import hashlib
import os
import re
from typing import Any, cast

from pyhilo.const import (
    AUTH_AUTHORIZE,
    AUTH_CHALLENGE_METHOD,
    AUTH_CLIENT_ID,
    AUTH_SCOPE,
    AUTH_TOKEN,
)

class OAuth2Helper:
    """Custom OAuth2 implementation."""

    def __init__(self) -> None:
        self._code_verifier = self._get_code_verifier()
        self._code_challenge = self._get_code_challenge(self._code_verifier)

    # Ref : https://blog.sanghviharshit.com/reverse-engineering-private-api-oauth-code-flow-with-pkce/
    def _get_code_verifier(self) -> str:
        code = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        return re.sub("[^a-zA-Z0-9]+", "", code)

    def _get_code_challenge(self, verifier: str) -> str:
        sha_verifier = hashlib.sha256(verifier.encode("utf-8")).digest()
        code = base64.urlsafe_b64encode(sha_verifier).decode("utf-8")
        return code.replace("=", "")

    def get_authorize_parameters(self):
        return {
            "scope": AUTH_SCOPE,
            "code_challenge": self._code_challenge,
            "code_challenge_method": AUTH_CHALLENGE_METHOD,
            "response_type": "code",
            "client_id": AUTH_CLIENT_ID,
        }

    def get_token_request_parameters(self, code, redirect_uri):
        return {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": self._code_verifier,
        }
