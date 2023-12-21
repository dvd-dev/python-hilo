"""Define package errors."""
from __future__ import annotations


class HiloError(Exception):
    """A base error."""

    pass


class EndpointUnavailableError(HiloError):
    """An error related to accessing an endpoint that isn't available in the plan."""

    pass


class InvalidCredentialsError(HiloError):
    """An error related to invalid credentials."""

    pass


class RequestError(HiloError):
    """An error related to invalid requests."""

    pass


class WebsocketError(HiloError):
    """An error related to generic websocket errors."""

    pass


class CannotConnectError(WebsocketError):
    """Define a error when the websocket can't be connected to."""

    pass


class ConnectionClosedError(WebsocketError):
    """Define a error when the websocket closes unexpectedly."""

    pass


class ConnectionFailedError(WebsocketError):
    """Define a error when the websocket connection fails."""

    pass


class InvalidMessageError(WebsocketError):
    """Define a error related to an invalid message from the websocket server."""

    pass


class NotConnectedError(WebsocketError):
    """Define a error when the websocket isn't properly connected to."""

    pass
