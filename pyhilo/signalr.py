"""Define a connection to the Hilo SignalR hubs via pysignalr."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Sequence
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
import ssl
from typing import Any, Callable, Optional, Tuple

from pysignalr.client import SignalRClient
from pysignalr.messages import Message

from pyhilo.const import LOG


class SignalRMsgType(IntEnum):
    INVOKE = 0x1
    CLOSE = 0x7
    UNKNOWN = 0xFF

    @classmethod
    def has_value(cls, value: int) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def value(cls, value: int) -> IntEnum:  # type: ignore
        return cls._value2member_map_.get(value, cls.UNKNOWN)  # type: ignore


@dataclass(frozen=True)
class SignalREvent:
    """Define a representation of a message."""

    event_type_id: int
    target: str
    arguments: list[list]
    invocation: int | None
    error: str | None
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str | None = field(init=False)

    def __post_init__(self) -> None:
        if SignalRMsgType.has_value(self.event_type_id):
            object.__setattr__(
                self, "event_type", SignalRMsgType.value(self.event_type_id).name
            )
        if self.event_type_id == SignalRMsgType.CLOSE:
            LOG.error(
                "Received close event from SignalR: Error: %s Target: %s Args: %s",
                self.event_type,
                self.target,
                self.arguments,
            )


def signalr_event_from_payload(payload: dict[str, Any]) -> SignalREvent:
    """Create a SignalREvent object from a SignalR event payload."""
    return SignalREvent(
        payload.get("type", SignalRMsgType.UNKNOWN),
        payload.get("target", ""),
        payload.get("arguments", ""),
        payload.get("invocationId"),
        payload.get("error"),
    )


class SignalRHub:
    """Wraps pysignalr.SignalRClient for a single hub endpoint.

    Lifecycle:
      ``run()``        — negotiate fresh token, build client, block until disconnect
      ``invoke()``     — send a hub method invocation
      ``disconnect()`` — cancel the task awaiting ``run()`` to stop cleanly
    """

    # Azure SignalR sends PingMessage every ~15s; 60s catches silent dead links.
    _SERVER_TIMEOUT: float = 60.0

    def __init__(
        self,
        negotiate_callback: Callable[[], Any],
    ) -> None:
        """Initialize.

        :param negotiate_callback: async callable returning ``(azure_url, access_token)``
        """
        self._negotiate = negotiate_callback
        self._client: Optional[SignalRClient] = None
        self._task: Optional[asyncio.Task] = None
        self._connected: bool = False
        self._connect_callbacks: list[Callable[..., Any]] = []
        self._disconnect_callbacks: list[Callable[..., Any]] = []
        self._event_callbacks: list[Callable[..., Any]] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """Return True if the SignalR connection is currently open."""
        return self._connected

    def add_connect_callback(self, callback: Callable[..., Any]) -> Callable[..., None]:
        """Register a callback to fire after a successful connection."""
        self._connect_callbacks.append(callback)

        def remove() -> None:
            self._connect_callbacks.remove(callback)

        return remove

    def add_disconnect_callback(
        self, callback: Callable[..., Any]
    ) -> Callable[..., None]:
        """Register a callback to fire after a disconnection."""
        self._disconnect_callbacks.append(callback)

        def remove() -> None:
            self._disconnect_callbacks.remove(callback)

        return remove

    def add_event_callback(self, callback: Callable[..., Any]) -> Callable[..., None]:
        """Register a callback to fire for every inbound hub message."""
        self._event_callbacks.append(callback)

        def remove() -> None:
            self._event_callbacks.remove(callback)

        return remove

    async def run(self) -> None:
        """Negotiate, create the SignalR client, and block until it disconnects.

        Raises on hard errors (auth failure, negotiation failure, server timeout,
        or close before open). Returns normally on a clean server-side
        disconnect after the connection has opened.
        """
        azure_url, access_token = await self._negotiate()
        LOG.info("SignalRHub: negotiate succeeded, connecting to %s", azure_url)

        # Pre-create SSL context off the event loop to avoid blocking HA's loop monitor (Lesson ❷)
        ssl_context = await asyncio.get_running_loop().run_in_executor(
            None, ssl.create_default_context
        )

        client = SignalRClient(
            url=azure_url,
            headers={"Authorization": f"Bearer {access_token}"},
            retry_count=0,
            ssl=ssl_context,
        )
        self._client = client

        activity_event = asyncio.Event()
        orig_callback = client._transport._callback

        async def _tracked_on_message(message: Message) -> None:
            activity_event.set()
            await orig_callback(message)

        client._transport._callback = _tracked_on_message

        # Install catch-all handler — must be set AFTER __init__ and BEFORE run() (Lesson ❹)
        hub_self = self

        class _CatchAllDict(defaultdict):  # noqa: N805
            def __missing__(self_dict, target: str) -> list[Any]:  # noqa: N805
                async def _handler(arguments: Any) -> None:
                    LOG.debug("SignalRHub: received target=%s", target)
                    event = SignalREvent(
                        event_type_id=SignalRMsgType.INVOKE,
                        target=target,
                        arguments=(
                            arguments if isinstance(arguments, list) else [arguments]
                        ),
                        invocation=None,
                        error=None,
                    )
                    for cb in hub_self._event_callbacks:
                        await cb(event)

                self_dict[target] = [_handler]
                return [_handler]

        client._message_handlers = _CatchAllDict(list)

        was_connected = False
        server_closed = False
        server_timed_out = False
        watchdog_task: asyncio.Task[None] | None = None
        client_task: asyncio.Task[None]

        def _on_timeout() -> None:
            nonlocal server_timed_out
            server_timed_out = True

        async def _on_open() -> None:
            nonlocal was_connected, watchdog_task
            self._connected = True
            was_connected = True
            watchdog_task = asyncio.create_task(
                self._watch_server_timeout(activity_event, client_task, _on_timeout)
            )
            LOG.info("SignalRHub: connected")
            await self._fire_callbacks(self._connect_callbacks, "connect")

        async def _on_close() -> None:
            nonlocal server_closed
            self._connected = False
            # pysignalr's WebsocketTransport loops forever in websockets.connect() with
            # the already-negotiated URL/token; cancel client_task so run() exits
            # and callers can re-negotiate a fresh Azure SignalR token.
            server_closed = True
            if not client_task.done():
                client_task.cancel()

        # Wire connect/disconnect/error hooks
        client.on_open(_on_open)
        client.on_close(_on_close)
        client.on_error(self._on_error)

        self._task = asyncio.current_task()
        client_task = asyncio.create_task(client.run())
        try:
            await client_task
        except asyncio.CancelledError:
            current_task = asyncio.current_task()
            outer_cancelled = current_task is not None and current_task.cancelling() > 0
            if not outer_cancelled:
                if server_closed:
                    if was_connected:
                        return
                    raise ConnectionError(
                        "SignalR connection closed before open"
                    ) from None
                if server_timed_out:
                    raise TimeoutError(
                        f"SignalR server timeout ({self._SERVER_TIMEOUT}s without messages)"
                    ) from None
            raise
        finally:
            self._connected = False
            if watchdog_task is not None:
                if not watchdog_task.done():
                    watchdog_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await watchdog_task
            if not client_task.done():
                client_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await client_task
            self._client = None
            self._task = None
            if was_connected:
                LOG.info("SignalRHub: disconnected")
                await self._fire_callbacks(self._disconnect_callbacks, "disconnect")

    async def invoke(self, method: str, args: list[Any]) -> None:
        """Invoke a hub method on the server.

        :param method: Hub method name
        :param args: Positional arguments for the method
        """
        if not self._connected or self._client is None:
            LOG.warning("SignalRHub: invoke(%s) called while disconnected", method)
            return
        LOG.debug("SignalRHub: invoke method=%s args=%s", method, args)
        await self._client.send(method, args)

    async def disconnect(self) -> None:
        """Request the client to stop.

        ``pysignalr.SignalRClient`` has no ``stop()``/``close()`` method --
        its ``run()`` coroutine blocks until the connection ends and is
        meant to be cancelled by the caller (see pysignalr's
        ``WebsocketTransport.run()``, an unconditional reconnect loop with
        no external stop hook). Cancel the task that's awaiting ``run()``
        instead of calling a nonexistent client method.
        """
        task = self._task
        if task is not None:
            LOG.info("SignalRHub: disconnecting")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Internal pysignalr hooks
    # ------------------------------------------------------------------

    async def _fire_callbacks(
        self, callbacks: Sequence[Callable[..., object]], label: str
    ) -> None:
        for cb in list(callbacks):
            try:
                result = cb()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                LOG.error("SignalRHub: %s callback error: %s", label, exc)

    async def _watch_server_timeout(
        self,
        activity_event: asyncio.Event,
        client_task: asyncio.Task[None],
        on_timeout: Callable[[], None],
    ) -> None:
        while not client_task.done():
            activity_event.clear()
            try:
                await asyncio.wait_for(
                    activity_event.wait(), timeout=self._SERVER_TIMEOUT
                )
            except TimeoutError:
                if not self._connected:
                    return
                LOG.warning(
                    "SignalRHub: server timeout (%ss without inbound messages)",
                    self._SERVER_TIMEOUT,
                )
                self._connected = False
                on_timeout()
                if not client_task.done():
                    client_task.cancel()
                return

    async def _on_error(self, message: str) -> None:
        LOG.error("SignalRHub: error: %s", message)


class SignalRManager:
    def __init__(
        self,
        async_request: Callable[..., Any],
    ) -> None:
        """Initialize.

        :param async_request: The ``API.async_request`` coroutine-factory
        """
        self._async_request = async_request

    async def _negotiate(self, endpoint: str) -> Tuple[str, str]:
        """POST ``{endpoint}/negotiate`` and return ``(azure_url, access_token)``.

        :param endpoint: e.g. ``/DeviceHub`` or ``/ChallengeHub``
        :returns: Tuple of (azure_url, access_token)
        """
        url = f"{endpoint}/negotiate"
        LOG.debug("SignalRManager: negotiating %s", url)
        resp = await self._async_request("post", url)
        azure_url: str = resp["url"]
        access_token: str = resp["accessToken"]
        LOG.info("SignalRManager: negotiate succeeded for %s → %s", endpoint, azure_url)
        return azure_url, access_token

    def build_hub(
        self,
        endpoint: str,
    ) -> SignalRHub:
        """Create a ``SignalRHub`` whose negotiate lambda hits ``endpoint``.

        :param endpoint: Hilo hub path (``/DeviceHub`` or ``/ChallengeHub``)
        :returns: A ready-to-run ``SignalRHub``
        """

        async def _negotiate_for_endpoint() -> Tuple[str, str]:
            return await self._negotiate(endpoint)

        return SignalRHub(
            negotiate_callback=_negotiate_for_endpoint,
        )
