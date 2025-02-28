"""Define package errors."""

from __future__ import annotations


class HiloError(Exception):
    """A base error."""


class EndpointUnavailableError(HiloError):
    """An error related to accessing an endpoint that isn't available in the plan."""


class InvalidCredentialsError(HiloError):
    """An error related to invalid credentials."""


class RequestError(HiloError):
    """An error related to invalid requests."""


class WebsocketError(HiloError):
    """An error related to generic websocket errors."""


class CannotConnectError(WebsocketError):
    """Define a error when the websocket can't be connected to."""


class ConnectionClosedError(WebsocketError):
    """Define a error when the websocket closes unexpectedly."""


class ConnectionFailedError(WebsocketError):
    """Define a error when the websocket connection fails."""


class InvalidMessageError(WebsocketError):
    """Define a error related to an invalid message from the websocket server."""


class NotConnectedError(WebsocketError):
    """Define a error when the websocket isn't properly connected to."""
