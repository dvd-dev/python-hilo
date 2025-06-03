"""OAuth2 Helper for Hilo"""

import base64
import hashlib
import os
import re

from pyhilo.const import AUTH_CHALLENGE_METHOD, AUTH_CLIENT_ID, AUTH_SCOPE


class OAuth2Helper:
    """Custom OAuth2 implementation."""

    def __init__(self) -> None:
        self._code_verifier = self._get_code_verifier()
        self._code_challenge = self._get_code_challenge(self._code_verifier)

    # Ref : https://blog.sanghviharshit.com/reverse-engineering-private-api-oauth-code-flow-with-pkce/
    def _get_code_verifier(self) -> str:
        """Generates a random cryptographic key string to be used as a code verifier in PKCE."""
        code = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        return re.sub("[^a-zA-Z0-9]+", "", code)

    def _get_code_challenge(self, verifier: str) -> str:
        """Generates a SHA-256 code challenge for PKCE"""
        sha_verifier = hashlib.sha256(verifier.encode("utf-8")).digest()
        code = base64.urlsafe_b64encode(sha_verifier).decode("utf-8")
        return code.replace("=", "")

    def get_authorize_parameters(self) -> dict[str, str]:
        """
        Returns the parameters required for the authorization request.

        Returns:
            dict[str, str]: A dictionary containing the authorization parameters.
        """
        return {
            "scope": AUTH_SCOPE,
            "code_challenge": self._code_challenge,
            "code_challenge_method": AUTH_CHALLENGE_METHOD,
            "response_type": "code",
            "client_id": AUTH_CLIENT_ID,
        }

    def get_token_request_parameters(
        self, code: str, redirect_uri: str
    ) -> dict[str, str]:
        """
        Returns the parameters required for the token request.

        This method prepares the payload for the request to exchange an authorization
        code for an access token. It includes the necessary parameters for the
        authorization code grant type with PKCE.

        Args:
            code: The authorization code received from the authorization server.
            redirect_uri: The redirect URI used in the authorization request.

        Returns:
            dict[str, str]: A dictionary containing the token request parameters.
        """
        return {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": self._code_verifier,
        }
