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


class SignalRError(HiloError):
    """An error related to generic SignalR errors."""

    pass


class CannotConnectError(SignalRError):
    """Define a error when the SignalR hub can't be connected to."""

    pass


class ConnectionClosedError(SignalRError):
    """Define a error when the SignalR hub closes unexpectedly."""

    pass


class ConnectionFailedError(SignalRError):
    """Define a error when the SignalR connection fails."""

    pass


class InvalidMessageError(SignalRError):
    """Define a error related to an invalid message from the SignalR server."""

    pass


class NotConnectedError(SignalRError):
    """Define a error when the SignalR hub isn't properly connected to."""

    pass
